from machine import I2C
from buzzer import Buzzer
from time import sleep_ms, ticks_ms, ticks_diff, ticks_add
from i2c_dev import I2CException
from common import RingBuffer

MOTOR_DEF_SPEED  = 80

MOTOR_MAX_TRIES = 3 # I2C_MAX_TRIES

MOTOR_STATE_FWD   = "Forward"
MOTOR_STATE_BKWD  = "Backward"
MOTOR_STATE_LEFT  = "Left"
MOTOR_STATE_RIGHT = "Right"
MOTOR_STATE_STOP  = "Stopped"
MOTOR_STATE_INIT  = "Init"
MOTOR_STATE_UNK   = "Unknown"

MOTOR_CMD_NONE    = -1
MOTOR_CMD_FORWARD = 0
MOTOR_CMD_REVERSE = 1
MOTOR_CMD_LEFT    = 2
MOTOR_CMD_RIGHT   = 3
MOTOR_CMD_STOP    = 4
MOTOR_CMD_STOP_FORCE = 5
MOTOR_CMD_MAX     = 6

MOTOR_TURN_DELAY_MS = 500

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
        self.i2c.writeto(0x22, buf) # send Stop by default

class CarMotors():
    def __init__(self, i2c, buzz=True, debug=0):
        self.DEBUG = debug
        self.i2c = i2c
        # state = [Car level, left motor, right motor]
        self.state = [MOTOR_STATE_INIT, MOTOR_STATE_INIT, MOTOR_STATE_INIT]
        if buzz:
            self.buzzer = Buzzer(debug=0)
        else:
            self.buzzer = None
        self.mctrl = MotorDriver(self.i2c) # FIXME: self._init_motors()
        self.rbuf = RingBuffer(size=10, init=(MOTOR_CMD_NONE, 0, 0)) # type: ignore
        self.actions = {
                # Command: function,
                MOTOR_CMD_FORWARD: lambda: self.forward(),
                MOTOR_CMD_REVERSE: lambda: self.backward(),
                MOTOR_CMD_LEFT:    lambda: self.turn_left(),
                MOTOR_CMD_RIGHT:   lambda: self.turn_right(),
                MOTOR_CMD_STOP:    lambda: self.stop_motors(),

            }

    # def _init_motors(self):
    #     self._mctrl = MotorDriver(self.i2c)
    #     # FIXME: sleep_ms(5)
    #     # FIXME: self.stop_force()

    def rebind(self, i2c):
        self.i2c = i2c
        self.mctrl = MotorDriver(self.i2c) # FIXME:self._init_motors()
        return True

    def __str__(self):
        return "Motors: state {}, M1 {}, M2 {}".format(self.state[0], self.state[1], self.state[2])

    def _set_motor(self, mid, speed, dir):
        # throws I2CException
        # Motor IDs: 1 (Left), 2 (Right)
        # Speed: 0 (Stop), Range 1-255, Default 80
        # Direction: 0=Forward, 1=Reverse
        if self.DEBUG:
            print("_set_motor: {}, {}, {}".format(mid, speed, dir))

        last_error = None
        for i in range(MOTOR_MAX_TRIES):
            try:
                self.mctrl.dc(mid, speed, dir)
                return
            except OSError as e:
                last_error = e
                if self.DEBUG:
                    print("_set_motor: Set_motor OSError: ", e)

            except Exception as e:
                last_error = e
                if self.DEBUG:
                    print("_set_motor Unexpected exception ", e)

            sleep_ms(5) # FIXME: do I need this sleep_ms(15) 

            if self.DEBUG:
                print("set_motor loop iteration ", i, " failed")
        else:
            raise I2CException(
                "set_motor %d (state %s/%s, dir %d) failed after %d tries: %s"
                % (mid, self.state[0], self.state[mid], dir, MOTOR_MAX_TRIES, last_error)
            )

    def forward(self, speed=MOTOR_DEF_SPEED):
        # throws I2CException
        if self.state[0] == MOTOR_STATE_FWD:
            return
        if self.buzzer != None:
            self.buzzer.off()

        self.state[0] = MOTOR_STATE_UNK
        self._set_motor(1, speed, 0)
        self.state[1] = MOTOR_STATE_FWD

        self._set_motor(2, speed, 0)
        self.state[2] = MOTOR_STATE_FWD
        self.state[0] = MOTOR_STATE_FWD

    def backward(self, speed=MOTOR_DEF_SPEED):
        # throws I2CException
        if self.state[0] == MOTOR_STATE_BKWD:
            return
        # FIXME: Should I first stop the buzzer if its on?

        self.state[0] = MOTOR_STATE_UNK
        self._set_motor(1, speed, 1)
        self.state[1] = MOTOR_STATE_BKWD

        self._set_motor(2, speed, 1)
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
        self._set_motor(1, speed, 0)
        self.state[1] = MOTOR_STATE_FWD

        self._set_motor(2, speed, 1)
        self.state[2] = MOTOR_STATE_BKWD
        self.state[0] = MOTOR_STATE_RIGHT

    def turn_left(self, speed=MOTOR_DEF_SPEED):
        # throws I2CException
        if self.state[0] == MOTOR_STATE_LEFT:
            return
        if self.buzzer != None:
            self.buzzer.off()

        self.state[0] = MOTOR_STATE_UNK
        self._set_motor(1, speed, 1)
        self.state[1] = MOTOR_STATE_BKWD

        self._set_motor(2, speed, 0)
        self.state[2] = MOTOR_STATE_FWD
        self.state[0] = MOTOR_STATE_LEFT

    def stop_motors(self):
        # throws I2CException
        if self.state[0] == MOTOR_STATE_STOP:
            return
        if self.buzzer != None:
            self.buzzer.off()

        self.state[0] = MOTOR_STATE_UNK
        self._set_motor(1, 0, 0)
        self.state[1] = MOTOR_STATE_STOP

        self._set_motor(2, 0, 0)
        self.state[2] = MOTOR_STATE_STOP
        self.state[0] = MOTOR_STATE_STOP

    def stop_force(self):
        # throws I2CException
        if self.buzzer != None:
            self.buzzer.off()

        self.state[0] = MOTOR_STATE_UNK
        self._set_motor(1, 0, 0)
        self.state[1] = MOTOR_STATE_STOP

        self._set_motor(2, 0, 0)
        self.state[2] = MOTOR_STATE_STOP
        self.state[0] = MOTOR_STATE_STOP

    def repeat(self):
        # FIXME: Handle repeat code
        pass

    def add_cmd(self, cmd):
        if cmd == MOTOR_CMD_NONE or cmd == MOTOR_CMD_MAX:
            return
        
        if cmd > MOTOR_CMD_MAX or cmd < MOTOR_CMD_NONE:
            raise RuntimeError("Invalid motor command ", cmd)

        self.rbuf.put((cmd, 0, 0))

        if cmd == MOTOR_CMD_LEFT:
            self.rbuf.put((MOTOR_CMD_STOP, ticks_ms(), MOTOR_TURN_DELAY_MS))
        elif cmd == MOTOR_CMD_RIGHT:
            self.rbuf.put((MOTOR_CMD_STOP, ticks_ms(), MOTOR_TURN_DELAY_MS))
        
    def run_cmds(self):
        while not self.rbuf.is_empty():
            item = self.rbuf.get()
            if not item or  ticks_diff(ticks_ms(), item[1]) < item[3]: # type: ignore
                break
            self.actions[item[0]]() # type: ignore
