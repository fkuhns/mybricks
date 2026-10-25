from machine import I2C
from buzzer import Buzzer
from time import sleep_ms, ticks_ms, ticks_diff, ticks_add
from i2c_dev import I2CException
from common import RingBuffer

MOTOR_DEF_SPEED  = 80

MOTOR_STATE_FWD   = "Forward"
MOTOR_STATE_BKWD  = "Backward"
MOTOR_STATE_LEFT  = "Left"
MOTOR_STATE_RIGHT = "Right"
MOTOR_STATE_STOP  = "Stopped"
MOTOR_STATE_INIT  = "Init"
MOTOR_STATE_UNK   = "Unknown"

MOTOR_CMD_NOOP       = 0
MOTOR_CMD_FORWARD    = 1
MOTOR_CMD_REVERSE    = 2
MOTOR_CMD_LEFT       = 3
MOTOR_CMD_RIGHT      = 4
MOTOR_CMD_STOP       = 5
MOTOR_CMD_STOP_FORCE = 6
MOTOR_CMD_MAX        = 6

MOTOR_INDX_CMD    = 0
MOTOR_INDX_ARG    = 1
MOTOR_INDX_DELAY  = 2
MOTOR_INDX_COUNT  = 3

MOTOR_TURN_DELAY_MS = 500 # default turn time, see set_turn_ms()
MOTOR_INTER_CMD_MS  =   0
MOTOR_RETRY_MS      =  10 # wait before retrying a failed command
MOTOR_CMD_MAX_TRIES =   3 # each try is I2C_MAX_TRIES I2C writes

# Turn calibration: ms = MOTOR_TURN_T0_MS + degrees / MOTOR_TURN_DEG_PER_MS
# FIXME: placeholders, measure at MOTOR_DEF_SPEED
MOTOR_TURN_T0_MS      = 0   # motor spin up lag
MOTOR_TURN_DEG_PER_MS = 0.18 # 90 deg in 500 ms

class MotorDriver:
    def __init__(self, i2c, addr=0x22):
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
        self.i2c.writeto(self.addr, buf) # send Stop by default

class CarMotors():
    
    def __init__(self, bus, buzz=True, debug=0):
        # bus is an I2cBus, it retries and resets the bus on errors
        self.DEBUG = debug
        self.i2c = bus
        # state = [Car level, left motor, right motor]
        self.state = [MOTOR_STATE_INIT, MOTOR_STATE_INIT, MOTOR_STATE_INIT]
        if buzz:
            self.buzzer = Buzzer(debug=0)
        else:
            self.buzzer = None
        self.mctrl = MotorDriver(self.i2c)

        # Command buffer, entry tuple = (CMD, ARG, DELAY, COUNT)
        #   CMD   = one of the MOTOR_CMD_* values
        #   ARG   = integer, command argument (degrees for turns), 0 = default
        #   DELAY = integer, ms to wait after the previous command ran
        #   COUNT = integer, number of times cmd was tried without success
        self.rbuf = RingBuffer(size=10, init=(MOTOR_CMD_NOOP, 0, 0, 0)) # type: ignore
        self._last_run = ticks_ms() # when the last command was run or tried
        self.turn_ms   = MOTOR_TURN_DELAY_MS
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

    def __str__(self):
        return "Motors: state {}, M1 {}, M2 {}".format(self.state[0], self.state[1], self.state[2])

    # def _set_motor(self, mid, speed, dir):
    #     # throws I2CException
    #     # Motor IDs: 1 (Left), 2 (Right)
    #     # Speed: 0 (Stop), Range 1-255, Default 80
    #     # Direction: 0=Forward, 1=Reverse
    #     if self.DEBUG:
    #         print("_set_motor: {}, {}, {}".format(mid, speed, dir))

    #     self.mctrl.dc(mid, speed, dir)

    def forward(self, speed=MOTOR_DEF_SPEED):
        # throws I2CException
        if self.state[0] == MOTOR_STATE_FWD:
            return
        if self.buzzer != None:
            self.buzzer.off()

        self.state[0] = MOTOR_STATE_UNK
        self.mctrl.dc(1, speed, 0)
        self.state[1] = MOTOR_STATE_FWD

        self.mctrl.dc(2, speed, 0)
        self.state[2] = MOTOR_STATE_FWD
        self.state[0] = MOTOR_STATE_FWD

    def backward(self, speed=MOTOR_DEF_SPEED):
        # throws I2CException
        if self.state[0] == MOTOR_STATE_BKWD:
            return
        # FIXME: Should I first stop the buzzer if its on?

        self.state[0] = MOTOR_STATE_UNK
        self.mctrl.dc(1, speed, 1)
        self.state[1] = MOTOR_STATE_BKWD

        self.mctrl.dc(2, speed, 1)
        self.state[2] = MOTOR_STATE_BKWD
        self.state[0] = MOTOR_STATE_BKWD

        if self.buzzer:
            self.buzzer.on()

    def turn_right(self, speed=MOTOR_DEF_SPEED):
        # throws I2CException
        if self.state[0] == MOTOR_STATE_RIGHT:
            return
        if self.buzzer != None:
            self.buzzer.off()

        self.state[0] = MOTOR_STATE_UNK
        self.mctrl.dc(1, speed, 0)
        self.state[1] = MOTOR_STATE_FWD

        self.mctrl.dc(2, speed, 1)
        self.state[2] = MOTOR_STATE_BKWD
        self.state[0] = MOTOR_STATE_RIGHT

    def turn_left(self, speed=MOTOR_DEF_SPEED):
        # throws I2CException
        if self.state[0] == MOTOR_STATE_LEFT:
            return
        if self.buzzer != None:
            self.buzzer.off()

        self.state[0] = MOTOR_STATE_UNK
        self.mctrl.dc(1, speed, 1)
        self.state[1] = MOTOR_STATE_BKWD

        self.mctrl.dc(2, speed, 0)
        self.state[2] = MOTOR_STATE_FWD
        self.state[0] = MOTOR_STATE_LEFT

    def stop_motors(self):
        # throws I2CException
        if self.state[0] == MOTOR_STATE_STOP:
            return
        if self.buzzer != None:
            self.buzzer.off()

        self.state[0] = MOTOR_STATE_UNK
        self.mctrl.dc(1, 0, 0)
        self.state[1] = MOTOR_STATE_STOP

        self.mctrl.dc(2, 0, 0)
        self.state[2] = MOTOR_STATE_STOP
        self.state[0] = MOTOR_STATE_STOP

    def stop_force(self):
        # throws I2CException
        if self.buzzer != None:
            self.buzzer.off()

        self.state[0] = MOTOR_STATE_UNK
        self.mctrl.dc(1, 0, 0)
        self.state[1] = MOTOR_STATE_STOP

        self.mctrl.dc(2, 0, 0)
        self.state[2] = MOTOR_STATE_STOP
        self.state[0] = MOTOR_STATE_STOP

    def repeat(self):
        # FIXME: Handle repeat code
        pass

    def reset(self):
        self.rbuf.clear()
        self.stop_force()

    def set_turn_ms(self, ms):
        # turn time used when a turn has no angle
        self.turn_ms = ms

    def ms_for_angle(self, deg):
        return MOTOR_TURN_T0_MS + int(deg / MOTOR_TURN_DEG_PER_MS)

    def add_cmd(self, cmd, arg=0):
        # Returns False if the command did not fit in the buffer
        if cmd == MOTOR_CMD_NOOP:
            return True

        if cmd > MOTOR_CMD_MAX or cmd < MOTOR_CMD_NOOP:
            raise RuntimeError("Invalid motor command ", cmd)

        if cmd == MOTOR_CMD_LEFT or cmd == MOTOR_CMD_RIGHT:
            # a turn is only queued with its stop, never without it
            if self.rbuf.free() < 2:
                return False
            ms = self.ms_for_angle(arg) if arg else self.turn_ms
            self.rbuf.put((cmd, arg, MOTOR_INTER_CMD_MS, 0))
            self.rbuf.put((MOTOR_CMD_STOP, 0, ms, 0))
            return True

        return self.rbuf.put((cmd, arg, MOTOR_INTER_CMD_MS, 0))

    def run_cmds(self):
        while not self.rbuf.is_empty():
            item = self.rbuf.peek()
            if ticks_diff(ticks_ms(), self._last_run) < item[MOTOR_INDX_DELAY]: # type: ignore
                break

            try:
                self.actions[item[MOTOR_INDX_CMD]]() # type: ignore
                self._last_run = ticks_ms()
                self.rbuf.advance_tail()
            except I2CException as e:
                self._last_run = ticks_ms()
                count = item[MOTOR_INDX_COUNT] + 1 # type: ignore
                if self.DEBUG:
                    print("run_cmds I2CException, try ", count, ": ", e)
                if count >= MOTOR_CMD_MAX_TRIES:
                    # FIXME: a dropped stop leaves the car moving
                    self.rbuf.advance_tail() # delete command
                else:
                    self.rbuf.update_tail((item[MOTOR_INDX_CMD], # type: ignore
                                           item[MOTOR_INDX_ARG], # type: ignore
                                           MOTOR_RETRY_MS,
                                           count))
                break
            except Exception as e:
                print("run_cmds: Unexpected exception ", e)
                self.rbuf.advance_tail() # do not retry it forever
                raise
