from machine import I2C
from buzzer import Buzzer
from time import ticks_ms, ticks_diff
from i2c_dev import I2cException #, I2cBusException, I2cNackException
from common import Device, RingBuffer, I2C_ADDR_MOTOR, \
                   DEBUG_ERROR, DEBUG_INFO, DEBUG_NONE, DEBUG_VERB, DEBUG_WARN

# --------------------------------------------------------------------------
# Constants affecting processing commands
# The number of times a command is tried before it is removed from the q
# Note, the I2C write command will also trie I2C_MAX_TRIES before it 
# reports that an attempt to execute a command has failed.
MOTOR_CMD_MAX_TRIES  =  3 
# After a command fails, the command q entry will have it's delay set to this value
# Effectively adds a delay before a failed command is tried again. Note, this does 
# block the queue until the command is retired.
MOTOR_CMD_RETRY_MS   =  1 
# if true add a stop command before any non-stop cmd
# goal is to reduce current surge to motors from a sudden 
# change of direction
MOTOR_CMD_ADD_STOP   =  1 

# Command tuple: (CMD, ARG, DELAY, CNT)
MOTOR_INDX_CMD    = 0 # MOTOR_CMD_*
MOTOR_INDX_ARG    = 1 # Integer argument for command (e.g. angle for turn)
MOTOR_INDX_DELAY  = 2 # required min delay between last and this command
MOTOR_INDX_COUNT  = 3 # number of times the command has been unsuccessfully tried

# Motor speed for all movement commands
MOTOR_DEF_SPEED  = 100
# Command q size
MOTOR_QSIZE      = 10   # command buffer entries

# For turns the delay between the left/Right command and a following stop command
# defaults to MOTOR_TURN_DELAY_MS. It can be overridden by specifying an angle or 
# changing the pot setting
MOTOR_TURN_DELAY_MS = 500 # default turn time, see set_turn_ms()
# Default time of delay between individual commands.   
MOTOR_INTER_CMD_MS  =   0
# Turn calibration: ms = MOTOR_TURN_T0_MS + degrees / MOTOR_TURN_DEG_PER_MS
# FIXME: placeholders, measure at MOTOR_DEF_SPEED
MOTOR_TURN_T0_MS      = 0    # motor spin up lag
MOTOR_TURN_DEG_PER_MS = 0.18 # 90 deg in 500 ms

# --------------------------------------------------------------------------
# Car & Motor states
MOTOR_STATE_FWD   = "Forward"
MOTOR_STATE_BKWD  = "Backward"
MOTOR_STATE_LEFT  = "Left"
MOTOR_STATE_RIGHT = "Right"
MOTOR_STATE_STOP  = "Stopped"
MOTOR_STATE_INIT  = "Init"
MOTOR_STATE_UNK   = "Unknown"

def state2str(state):
    return state

def state_is_stopped(s):
    return s == MOTOR_STATE_STOP

def state_is_unknown(s):
    return s == MOTOR_STATE_UNK

def state_is_moving(s):
    return not (state_is_stopped(s) or state_is_unknown(s))

def state_is_turning(s):
    return (s == MOTOR_STATE_LEFT) or (s == MOTOR_STATE_RIGHT)

# Motor state is a 3-tuple (Car State, M1 state, M2 state)
# e.g. (MOTOR_STATE_LEFT, MOTOR_STATE_BKWD, MOTOR_STATE_FWD)
MOTOR_STATE_CAR_INDX = 0
MOTOR_STATE_M1_INDX  = 1
MOTOR_STATE_M2_INDX  = 2

# --------------------------------------------------------------------------
# Commands
MOTOR_CMD_MIN        = 0
MOTOR_CMD_NOOP       = 0
MOTOR_CMD_FORWARD    = 1
MOTOR_CMD_REVERSE    = 2
MOTOR_CMD_LEFT       = 3
MOTOR_CMD_RIGHT      = 4
MOTOR_CMD_STOP       = 5
MOTOR_CMD_STOP_FORCE = 6
MOTOR_CMD_MAX        = 6

Cmd2Str = {
    MOTOR_CMD_NOOP:       "NoOp",
    MOTOR_CMD_FORWARD:    "Forward",
    MOTOR_CMD_REVERSE:    "Reverse",
    MOTOR_CMD_LEFT:       "Left",
    MOTOR_CMD_RIGHT:      "Right",
    MOTOR_CMD_STOP:       "Stop",
    MOTOR_CMD_STOP_FORCE: "Stop_Forced"
}

def cmd2str(cmd):
    return Cmd2Str.get(cmd, "Invalid")

Cmd2State = {MOTOR_CMD_FORWARD:    MOTOR_STATE_FWD, 
             MOTOR_CMD_REVERSE:    MOTOR_STATE_BKWD,
             MOTOR_CMD_LEFT:       MOTOR_STATE_LEFT,
             MOTOR_CMD_RIGHT:      MOTOR_STATE_RIGHT,
             MOTOR_CMD_STOP:       MOTOR_STATE_STOP,
             MOTOR_CMD_STOP_FORCE: MOTOR_STATE_STOP}

def cmd2state(cmd):
    # returns state ("...") or None
    global Cmd2State
    return Cmd2State.get(cmd, "")

def cmd_is_active(cmd):
    return (cmd > MOTOR_CMD_MIN) and (cmd <= MOTOR_CMD_MAX)

def cmd_is_valid(cmd):
    return (cmd >= MOTOR_CMD_MIN) and (cmd <= MOTOR_CMD_MAX)

def cmd_is_stop(cmd):
    return (cmd == MOTOR_CMD_STOP) or (cmd == MOTOR_CMD_STOP_FORCE)

def cmd_is_turn(cmd):
    return (cmd == MOTOR_CMD_LEFT) or (cmd == MOTOR_CMD_RIGHT)

def cmd_is_noop(cmd):
    return cmd == MOTOR_CMD_NOOP

# --------------------------------------------------------------------------

class MotorException(Exception):
    pass

class MotorDriver:
    def __init__(self, i2c, addr=I2C_ADDR_MOTOR):
        self.i2c  = i2c
        self.addr = addr
        
    def servo(self, servoNumber, angle):
        buf = bytearray(5)
        buf[0] = 0x26
        buf[1] = servoNumber + 2
        buf[2] = 0
        buf[3] = angle
        buf[4] = buf[1] ^ buf[2] ^ buf[3]
        self.i2c.writeto(self.addr, buf) # send Stop by default
        
    def dc(self, dcNumber, speed, direction):
        buf = bytearray(5)
        buf[0] = 0x26
        buf[1] = dcNumber
        buf[2] = speed
        buf[3] = direction
        buf[4] = buf[1] ^ buf[2] ^ buf[3]
        self.i2c.writeto(self.addr, buf) # may raise exceptions: I2cException, I2cBusException, I2cNackException

class CarMotors(Device):
    # From Device:
    #  _init()  called from Device.init()  - Device state = Device.STATE_INIT
    #  _stop()  called from Device.stop()  - Device state = Device.STATE_STOP
    #  _start() called from Device.start() - Device state = Device.STATE_START
    # Inherits is_on() and is_off() from Device, which check the Device state.
    def __init__(self, bus, buzz=True, debug=0):
        # bus is an I2cBus, it retries and resets the bus on errors
        self.DEBUG = debug
        self.bus   = bus
        if buzz:
            self.buzzer = Buzzer(debug=0)
        else:
            self.buzzer = None
        self.mctrl = MotorDriver(self.bus)

        # Command buffer, entry tuple = (CMD, ARG, DELAY, COUNT)
        #   CMD   = one of the MOTOR_CMD_* values
        #   ARG   = integer, command argument (degrees for turns), 0 = default
        #   DELAY = integer, ms to wait after the previous command ran
        #   COUNT = integer, number of times cmd was tried without success
        self.rbuf   = RingBuffer(size=MOTOR_QSIZE, init=(MOTOR_CMD_NOOP, 0, 0, 0)) # type: ignore
        self.actions = {
                # Command: function,
                MOTOR_CMD_NOOP:       lambda: None,
                MOTOR_CMD_FORWARD:    lambda: self.forward(),
                MOTOR_CMD_REVERSE:    lambda: self.backward(),
                MOTOR_CMD_LEFT:       lambda: self.turn_left(),
                MOTOR_CMD_RIGHT:      lambda: self.turn_right(),
                MOTOR_CMD_STOP:       lambda: self.stop_motors(),
                MOTOR_CMD_STOP_FORCE: lambda: self.stop_force(),
            }
        self.init() # Superclass Device init() which calls self._init()
                    # to initialize the motors and command buffer

    # Device hooks
    def _init(self):
        self.turn_ms = MOTOR_TURN_DELAY_MS
        # called from Device.init() to initialize the motors and command buffer
        # state    = [Car level,        left motor,       right motor]
        self.state = [MOTOR_STATE_INIT, MOTOR_STATE_INIT, MOTOR_STATE_INIT]
        self.clear_cmds()
        self._last_run = ticks_ms()

    def _stop(self):
        # Called from Device.stop() to stop the motors and command buffer
        # raises I2cException if the motors could not be stopped, the
        # device then stays on and stop() can be called again
        self.force_stop()

    def __str__(self):
        return "Motors: state {}, M1 {}, M2 {}".format(self.state[MOTOR_STATE_CAR_INDX], 
                                                       self.state[MOTOR_STATE_M1_INDX], 
                                                       self.state[MOTOR_STATE_M2_INDX])

    def forward(self, speed=MOTOR_DEF_SPEED):
        # throws I2CException
        # FIXME: this and the other moves trust the cached state. If the
        # controller resets (e.g. a brownout) the motors stop, but the state
        # still says Forward, so a FORWARD is never sent again.
        if self.state[MOTOR_STATE_CAR_INDX] == MOTOR_STATE_FWD:
            return
        if self.buzzer != None:
            self.buzzer.off()

        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_UNK
        self.mctrl.dc(1, speed, 0)
        self.state[MOTOR_STATE_M1_INDX] = MOTOR_STATE_FWD

        self.mctrl.dc(2, speed, 0)
        self.state[MOTOR_STATE_M2_INDX] = MOTOR_STATE_FWD
        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_FWD

    def backward(self, speed=MOTOR_DEF_SPEED):
        # throws I2CException
        if self.state[MOTOR_STATE_CAR_INDX] == MOTOR_STATE_BKWD:
            return
        # FIXME: Should I first stop the buzzer if its on?

        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_UNK
        self.mctrl.dc(1, speed, 1)
        self.state[MOTOR_STATE_M1_INDX] = MOTOR_STATE_BKWD

        self.mctrl.dc(2, speed, 1)
        self.state[MOTOR_STATE_M2_INDX] = MOTOR_STATE_BKWD
        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_BKWD

        if self.buzzer:
            self.buzzer.on()

    def turn_right(self, speed=MOTOR_DEF_SPEED):
        # throws I2CException
        if self.state[MOTOR_STATE_CAR_INDX] == MOTOR_STATE_RIGHT:
            return
        if self.buzzer != None:
            self.buzzer.off()

        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_UNK
        self.mctrl.dc(1, speed, 0)
        self.state[MOTOR_STATE_M1_INDX] = MOTOR_STATE_FWD

        self.mctrl.dc(2, speed, 1)
        self.state[MOTOR_STATE_M2_INDX] = MOTOR_STATE_BKWD
        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_RIGHT

    def turn_left(self, speed=MOTOR_DEF_SPEED):
        # throws I2CException
        if self.state[MOTOR_STATE_CAR_INDX] == MOTOR_STATE_LEFT:
            return
        if self.buzzer != None:
            self.buzzer.off()

        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_UNK
        self.mctrl.dc(1, speed, 1)
        self.state[MOTOR_STATE_M1_INDX] = MOTOR_STATE_BKWD

        self.mctrl.dc(2, speed, 0)
        self.state[MOTOR_STATE_M2_INDX] = MOTOR_STATE_FWD
        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_LEFT

    def stop_motors(self):
        # throws I2CException
        if self.state[MOTOR_STATE_CAR_INDX] == MOTOR_STATE_STOP:
            return
        if self.buzzer != None:
            self.buzzer.off()

        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_UNK
        self.mctrl.dc(1, 0, 0)
        self.state[MOTOR_STATE_M1_INDX] = MOTOR_STATE_STOP

        self.mctrl.dc(2, 0, 0)
        self.state[MOTOR_STATE_M2_INDX] = MOTOR_STATE_STOP
        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_STOP

    def stop_force(self):
        # throws I2CException
        if self.buzzer != None:
            self.buzzer.off()

        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_UNK
        self.mctrl.dc(1, 0, 0)
        self.state[MOTOR_STATE_M1_INDX] = MOTOR_STATE_STOP

        self.mctrl.dc(2, 0, 0)
        self.state[MOTOR_STATE_M2_INDX] = MOTOR_STATE_STOP
        self.state[MOTOR_STATE_CAR_INDX] = MOTOR_STATE_STOP

    def repeat(self):
        # FIXME: Handle repeat code
        pass

    def set_turn_ms(self, ms):
        # turn time used when a turn has no angle
        self.turn_ms = ms

    def ms_for_angle(self, deg):
        return MOTOR_TURN_T0_MS + int(deg / MOTOR_TURN_DEG_PER_MS)

    def car_state(self):
        return self.state[MOTOR_STATE_CAR_INDX]
    
    def is_stopped(self):
        return state_is_stopped(self.state[MOTOR_STATE_CAR_INDX])

    def is_moving(self):
        return  state_is_moving(self.state[MOTOR_STATE_CAR_INDX])

    def is_turning(self):
        return state_is_turning(self.state[MOTOR_STATE_CAR_INDX])

    def clear_cmds(self):
        if self.DEBUG >= DEBUG_VERB:
            print("CarMotors.clear_cmds: Clear command buf - len(q) %d" % len(self.rbuf))
        self.rbuf.clear()

    def force_stop(self):
        if self.DEBUG >= DEBUG_INFO:
            print("CarMotors.force_stop: stopping motors and clearing cmd buffer")

        self.clear_cmds()
        if self.buzzer != None:
            self.buzzer.off()
        try:
            self.stop_force()
            self._last_run = ticks_ms()
        except I2cException as e:
            if self.DEBUG >= DEBUG_WARN:
                print("CatMotors.force_stop: Caught %s doc %s " % (type(e).__name__, e))
        except Exception as e:
            if self.DEBUG >= DEBUG_WARN:
                print("CatMotors.force_stop: Caught %s doc %s " % (type(e).__name__, e))

    def add_cmd(self, cmd, arg=0):
        # cmd = MOTOR_CMD_*, arg is an argument for self.cmd()
        # Returns False if the command did not fit in the buffer, True otherwise
        if self.DEBUG >= DEBUG_VERB:
            print("CarMotors.add_cmd: Rx cmd %s, len(q) = %d" % (cmd2str(cmd), len(self.rbuf)))

        # ------------------------------------------------------------------
        # Verify command is valid/supported
        if not cmd_is_valid(cmd):
            raise MotorException("CarMotors.add_cmd: Invalid motor command ", cmd)
        
        # Simple case, do nothing
        if cmd_is_noop(cmd):
            return True

        # FIXME: Assuming it is possible that the car state is stale so always add cmd
        # if self.get_car_state() == cmd2state(cmd)
        #     return False

        # ------------------------------------------------------------------
        # make sure the buffer has at least 1 slot
        if self.rbuf.is_full():
            if self.DEBUG >= DEBUG_INFO:
                print("CarMotors.add_cmd: buffer is full, dropping command %s" % cmd2state(cmd))
            return False 

        # If MOTOR_CMD_ADD_STOP then add a stop command before cmd
        # If motors are running (i.e. car not stopped)
        #   Turns: [*(stop, 0, delay, 0), (turn, arg, delay, 0), (stop, 0, turn_delay, 0)]
        #   Stops: [ (stop, 0, delay, 0)]
        #   Other: [*(stop, 0, delay, 0), (cmd, arg, delay, 0)]
        # Car stopped
        #   Turns: [(turn, arg, delay, 0), (stop, 0, turn_delay, 0)]
        #   Stops: NA
        #   Other: [(cmd, arg, delay, 0)]
        if cmd_is_stop(cmd):
            # we only need 1 space, since rbuf not full its a go
            if not self.rbuf.put((cmd, arg, MOTOR_INTER_CMD_MS, 0)):
                raise MotorException("add_cmd: Error adding a stop command: ", cmd)
            if self.DEBUG >= DEBUG_VERB:
                print("CarMotors.add_cmd: added stop cmd %s, len(q) = %d" % (cmd2str(cmd), len(self.rbuf)))
            return True
        
        # ------------------------------------------------------------------
        if cmd_is_turn(cmd):
            space_needed = 3 if MOTOR_CMD_ADD_STOP else 2
        else: # forward or reverse
            space_needed = 2 if MOTOR_CMD_ADD_STOP else 1
        
        if self.rbuf.free() < space_needed:
            if self.DEBUG >= DEBUG_INFO:
                print("CarMotors.add_cmd: insufficient buffer space, dropping command %s" % cmd2str(cmd))
            return False
        
        # ------------------------------------------------------------------
        # First if required, have the car stop before applying a new command
        if MOTOR_CMD_ADD_STOP: # FIXME: add this back in later and self.is_moving():
            if not self.rbuf.put((MOTOR_CMD_STOP, 0, MOTOR_INTER_CMD_MS, 0)):
                raise MotorException("add_cmd: Error prefixing a stop for command ", cmd)

        # Second add the requested command, cmd != STOP from previous
        if not self.rbuf.put((cmd, arg, MOTOR_INTER_CMD_MS, 0)):
            # Unlikely but if for some reason a new command can not be put on buffer
            # keep the above stop for MOTOR_CMD_ADD_STOP=1 in case the car was about 
            # to have a collision or miss a turn etc.  It gives the user time to
            # adjust
            if MOTOR_CMD_ADD_STOP: self.rbuf.unput()
            raise MotorException("add_cmd: Error adding the requested command ", cmd)

        # Last is for turn commands, add a final stop so it doesn't just keep turning
        if cmd_is_turn(cmd):
            delay = self.ms_for_angle(arg) if arg else self.turn_ms
            if not self.rbuf.put((MOTOR_CMD_STOP, 0, delay, 0)):
                # for now don't drop the above turn command
                self.rbuf.unput()
                if MOTOR_CMD_ADD_STOP: self.rbuf.unput()
                raise MotorException("add_cmd: Error adding final stop for a turn cmd ", cmd)   
        
        # ------------------------------------------------------------------    
        if self.DEBUG >= DEBUG_VERB:
            print("CarMotors.add_cmd: added cmd %s, len(q) = %d" % (cmd2str(cmd), len(self.rbuf)))

        return True

    def run_cmds(self):
        while not self.rbuf.is_empty():
            # ------------------------------------------------------------------
            item = self.rbuf.peek()
            now  = ticks_ms()
            if ticks_diff(now, self._last_run) < item[MOTOR_INDX_DELAY]: # type: ignore
                break
            
            # ------------------------------------------------------------------
            cmd = item[MOTOR_INDX_CMD] # type: ignore
            if not cmd_is_valid(cmd):
                self.rbuf.advance_tail() # delete command
                raise MotorException("CarMotors.exec_cmd: Invalid command ", cmd)

            # ------------------------------------------------------------------
            if self.DEBUG >= DEBUG_VERB:
                print("CarMotors.run_cmds executing command %s" % cmd2str(cmd))

            try:
                self._last_run = now
                self.actions[cmd]() # type: ignore
                # FIXME: self._last_run = now # FIXME: should we always update? Could slow down q processing
            # ------------------------------------------------------------------
            except I2cException as e:
                count = item[MOTOR_INDX_COUNT] + 1 # type: ignore

                if self.DEBUG >= DEBUG_WARN:
                    print("CarMotor.run_cmds I2CException, try ", count, ": ", e) # type: ignore
                    print("\tState %s (%s/%s)" % (self.state[MOTOR_STATE_CAR_INDX], 
                                                  self.state[MOTOR_STATE_M1_INDX], 
                                                  self.state[MOTOR_STATE_M2_INDX]))

                if count >= MOTOR_CMD_MAX_TRIES:
                    # FIXME: self.rbuf.advance_tail() # delete command
                    pass
                else:
                    self.rbuf.update_tail((item[MOTOR_INDX_CMD], # type: ignore
                                           item[MOTOR_INDX_ARG], # type: ignore
                                           MOTOR_CMD_RETRY_MS,   # delay so test is not immediately rerun
                                           count))
                break
            # FIXME: Handle unexpected exceptions. Without this handler an
            # unexpected exception leaves the command at the head of the queue,
            # it is retried every loop and blocks every command behind it, and
            # the app loop ignores the exception. TestRunCmdsUnexpected in
            # tests/motor_tests.py expects the command to be dropped.
            except Exception as e:
                # self._last_run = now
                if self.DEBUG >= DEBUG_ERROR:
                    print("CarMotor.run_cmds: Unexpected exception ", e)
                self.rbuf.advance_tail() # do not retry it forever
                raise

            # ------------------------------------------------------------------
            # self._last_run = now
            self.rbuf.advance_tail()
            if self.DEBUG >= DEBUG_INFO:
                print("\tCarMotor.run_cmds Cmd %s State %s (%s/%s)" 
                        % (cmd2str(cmd), 
                           self.state[MOTOR_STATE_CAR_INDX], 
                           self.state[MOTOR_STATE_M1_INDX], 
                           self.state[MOTOR_STATE_M2_INDX]))