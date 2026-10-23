from machine import Pin, I2C
from picobricks import MotorDriver
from utime import sleep_ms, sleep_us, ticks_diff, ticks_ms
from ssd1306 import SSD1306_I2C
from buzzer import Buzzer

I2C0_ID       = 0
I2C0_SDA_PIN  = 4
I2C0_SCL_PIN  = 5

I2C1_ID       = 1
I2C1_SDA_PIN  = 2
I2C1_SCL_PIN  = 3

I2C_TOUT      = 100_000

I2C_MAX_TRIES = 3

#############################################################################
# Motors
#############################################################################
MOTOR_DEF_SPEED  = 80

MOTOR_MAX_TRIES = I2C_MAX_TRIES

MOTOR_STATE_FWD   = "Forward"
MOTOR_STATE_BKWD  = "Backward"
MOTOR_STATE_LEFT  = "Left"
MOTOR_STATE_RIGHT = "Right"
MOTOR_STATE_STOP  = "Stopped"
MOTOR_STATE_INIT  = "Init"
MOTOR_STATE_UNK   = "Unknown"

class I2CException(Exception):
    pass

class I2cCtl():
    I2C_ERR_MAX_MS  = 1_000
    I2C_ERR_MAX_CNT =     3
    # I2C:
    # Idle both SDL and SCL are 1
    # START | 7 or 10 bits addr | R/W bit | ACK/NACK bit |
    #       | [ 8 bits data | ack/nack ]  | [ 8 - bits data | ack/nack ] ...
    #       | STOP
    # Normal data
    # SDA can only change while scl is low
    # Bits: SDA 0 or 1 holds while SCL 0 to 1 back to 0 (SCL pulsed)
    # Changing SDA while SCL is high is reserved for control commands
    #      START: SDA 1 to 0 then SCL 1 to 0
    #      STOP:  SCL 0 to 1 then SDA 0 to 1
    #      ACK:   SDA 1 to 0
    # Repeated START instead of a STOP to retain bus
    # Clock Stretching: device may hold SCL low to indicate it is not ready
    # for the next frame. The controller will refrain from sending/reading
    # more data until the clock is released.
    def __init__(self, debug=0):
        self.DEBUG = debug

        self.Errors = [{"count": 0, "last": 0},
                       {"count": 0, "last": 0}]
        # I2C0 bus for devices other than the motor
        # I2C1 bus for the motors (SDA Pin & SCL Pin)
        # 2&3, 6&7, 10&11, 14&15, 18&19, 22&23, 26&27
        # used: 
        #   6/7 (LED), 10 (Button), 14/15 ultrasonic, 18/19 SPI,
        #   23 (SMPS control), 26 (Pot), 27 (LDR)
        # Available: Pins 2 & 3
        self._i2c = [{"OBJ": None, "SCL": I2C0_SCL_PIN, "SDA": I2C0_SDA_PIN, "FREQ": 400_000},
                    {"OBJ": None, "SCL": I2C1_SCL_PIN, "SDA": I2C1_SDA_PIN, "FREQ": 100_000}]
        
        self._i2c[I2C0_ID]["OBJ"] = I2C(I2C0_ID, 
                                        scl  = Pin(self._i2c[I2C0_ID]["SCL"]), 
                                        sda  = Pin(self._i2c[I2C0_ID]["SDA"]), 
                                        freq = self._i2c[I2C0_ID]["FREQ"],
                                        timeout = I2C_TOUT)
        # FIXME: fix assumption that only one bus is used!
        # self.i2c[I2C1_ID]["OBJ"] = I2C(I2C1_ID, 
        #                                scl  = Pin(self.i2c[I2C1_ID]["SCL"]), 
        #                                sda  = Pin(self.i2c[I2C1_ID]["SDA"]), 
        #   
        sleep_ms(1)        

        if self.DEBUG:
            print("I2cCtl: I2C 0 ", self._i2c[I2C0_ID]["OBJ"])
            print("I2cCtl: I2C 1 ", self._i2c[I2C1_ID]["OBJ"])

    def __str__(self):
        return "I2C: {}".format(self._i2c[I2C0_ID]["OBJ"])
    
    def i2c(self, id):
        return self._i2c[id]["OBJ"]

    def set_i2c(self, id, i2c):
        self._i2c[id]["OBJ"] = i2c

    def handle_err(self, id):
        # assume this is being called due to an I2CException
        t = ticks_ms()
        if ticks_diff(t, self.Errors[id]["last"]) > I2cCtl.I2C_ERR_MAX_MS:
            self.Errors[id]["last"] = t
            self.Errors[id]["count"] = 1
            # do nothing for the first error
            return None

        self.Errors[id]["count"] += 1
        if self.Errors[id]["count"] < I2cCtl.I2C_ERR_MAX_CNT:
            return None
        
        self.Errors[id]["count"] = 1
        try:
            self._reset_i2c(id)
        except OSError as e:
            if self.DEBUG:
                print("I2C handle_err caught OSError: ", e)
            return None
        except RuntimeError as e:
            if self.DEBUG:
                print("I2C handle_err caught RuntimeError, assume temp: ", e)
            return None

        return self._i2c[id]["OBJ"]

    def _reset_i2c(self, id):
        # Can handle where the master has stopped issuing clock cycles
        # slave is holding sda low waiting.
        # This does not address clock stretching, for that need to give
        # peripheral time 
        old_i2c = self._i2c[id]["OBJ"]
        if (not old_i2c) and self.DEBUG:
            # Should never happen!!
            if self.DEBUG:
                print("reset_i2c: i2c ID 2 not defined")

        if self.DEBUG:
            print("I2cCtl.reset_i2c: Resetting I2C bus ", id)

        self._i2c[id]["OBJ"] = None

        try:
            scl = Pin(self._i2c[id]["SCL"], Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
            sda = Pin(self._i2c[id]["SDA"], Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
            
            # FIXME: is a sleep needed here?? sleep_us(10)
            sleep_us(10)

            if self.DEBUG and sda.value() == 0:
                print("reset_i2c: sda is being held low", sda.value())

            # if SDA is being held low by the peripheral, we wont be able 
            # to send STOP. So need to see if we can clock out data until
            # SDA goes high.
            for _ in range(9):
                if sda.value():
                    break
                scl.value(0)
                sleep_us(5)
                scl.value(1)
                sleep_us(5)

            # Generate stop
            scl.value(0)
            sleep_us(5)

            sda.value(0)
            sleep_us(5)

            scl.value(1)
            sleep_us(5)

            sda.value(1)
            sleep_us(5)
        except:
            pass

        try:
            self._i2c[id]["OBJ"] = I2C(id, 
                                    scl =Pin(self._i2c[id]["SCL"]), 
                                    sda =Pin(self._i2c[id]["SDA"]), 
                                    freq=self._i2c[id]["FREQ"],
                                    timeout=I2C_TOUT)
            if self.DEBUG:
                print("** reset_i2c: New bus ", self._i2c[id]["OBJ"])

        except Exception as e:
            if self.DEBUG:
                print("reset_i2c exception: ", e)
            self._i2c[id]["OBJ"] = old_i2c
            raise e

class MotorsI2c():
    def __init__(self, i2c, buzz=True, debug=0):
        self.DEBUG = debug
        self.state = [MOTOR_STATE_INIT, MOTOR_STATE_INIT, MOTOR_STATE_INIT]
        if buzz:
            self.buzzer = Buzzer(debug=0)
        else:
            self.buzzer = None

        self._init_motors(i2c)

    def rebind(self, i2c):
        mctrl = self._mctrl
        try:
            self._init_motors(i2c)
            return self._mctrl
        except Exception as e:
            if self.DEBUG:
                print("rebind motor exception: ", e)
            self._mctrl = mctrl
        return None

    def _init_motors(self, i2c):
        # Motor controller is address 0x22, its hard coded in the MotorDriver class.
        self._mctrl = MotorDriver(i2c)
        sleep_ms(5)
        # force: after a bus reset the controller state is unknown
        self.stop_force()

    def _set_motor(self, mid, speed, direction):
        # throws I2CException
        # ID: 1 (Left), 2 (Right)
        # Speed: 0 (Stop), 1-255
        # Direction: 0=Forward, 1=Reverse
        if self.DEBUG:
            print("_set_motor: {}, {}, {}".format(mid, speed, direction))

        last_error = None
        for i in range(MOTOR_MAX_TRIES):
            try:
                self._mctrl.dc(mid, speed, direction)
                return
            except OSError as e:
                last_error = e
                if self.DEBUG:
                    print("_set_motor: Set_motor OSError: ", e)

            except Exception as e:
                last_error = e
                if self.DEBUG:
                    print("_set_motor Unexpected exception ", e)

            sleep_ms(15)

            if self.DEBUG:
                print("set_motor loop iteration ", i, " failed")
        else:
            raise I2CException(
                "set_motor %d (state %s/%s, dir %d) failed after %d tries: %s"
                % (mid, self.state[0], self.state[mid], direction, MOTOR_MAX_TRIES, last_error)
            )

    def __str__(self):
        return "Motors: state {}, M1 {}, M2 {}".format(self.state[0], self.state[1], self.state[2])

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
        if self.buzzer != None:
            self.buzzer.off()
        self.state[0] = MOTOR_STATE_UNK

        self._set_motor(1, speed, 1)
        self.state[1] = MOTOR_STATE_BKWD

        self._set_motor(2, speed, 1)
        self.state[2] = MOTOR_STATE_BKWD

        self.state[0] = MOTOR_STATE_BKWD
        if self.buzzer != None:
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

        sleep_ms(5)

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

#############################################################################
# OLED
#############################################################################
OLED_I2C_ADDR = 0x3c

OLED_WIDTH       = 128 # 16 chars within a row
OLED_HEIGHT      =  64 #  8 chars within a column
OLED_CHAR_SIZE   =   8
OLED_ROW_CHARS   =  16 # OLED_WIDTH // OLED_CHAR_SIZE
OLED_ROW_CENTER  = OLED_WIDTH // 2
OLED_ROW_HEIGHT  = 16
OLED_MAX_TRIES   = I2C_MAX_TRIES

class OledI2c():
    def __init__(self, i2c, hdr, debug=0):
        # Chars per Row: 16
        # Row 1: | FK Car|
        # FIXME: Row 2: | motor state |
        # Row 3: | Errors |
        self.DEBUG = debug
        self._hdr = hdr
        self._obuf = [["row 1", 0, 0], ["row 2", 0, OLED_ROW_HEIGHT], ["row 3", 0, 2 * OLED_ROW_HEIGHT]]
        self._octrl = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, OLED_I2C_ADDR)
        self.init_buf()
        sleep_ms(5)

    def rebind(self, i2c):
        oled = self._octrl
        try:
            self._octrl = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, OLED_I2C_ADDR)
            return self._octrl
        except Exception as e:
            if self.DEBUG:
                print("rebind oled exception: ", e)
            self._octrl = oled
        return None

    def init_buf(self):
        self.update_row1()
        self.update_row2("Dist: --")
        self.update_row3("Status: --")

    def __str__(self):
        return "Oled\n\t1) {}\n\t2) {}\n\t 3) {}".format(self._obuf[0][0], self._obuf[1][0], self._obuf[2][0])

    def _update_row(self, row, txt):
        tlen    = len(txt)
        xstart  = 0
        yoffset = (row - 1) * OLED_ROW_HEIGHT

        if tlen < OLED_ROW_CHARS:
            xstart  = OLED_ROW_CENTER - ((tlen * OLED_CHAR_SIZE) // 2)
        else: # tlen >= OLED_ROW_CHARS:
            txt  = txt[:OLED_ROW_CHARS]
            xstart = 0
        
        self._obuf[row-1][0] = txt
        self._obuf[row-1][1] = xstart
        self._obuf[row-1][2] = yoffset

        #oled.fill_rect(xstart, yoffset, 128, 8, 0)
        #oled.text(txt, xstart, yoffset)

    def update_row1(self):
        self._update_row(1, self._hdr)

    def update_row2(self, txt):
        self._update_row(2, txt)

    def update_row3(self, txt):
        self._update_row(3, txt)

    def _show(self):
        for i in range(MOTOR_MAX_TRIES):
            try:
                self._octrl.show()
                return
            except OSError as e:
                if self.DEBUG:
                    print("** OLED OS Error Exception: ", e)
                pass
            sleep_ms(1)
        else:
            raise I2CException("Oled show failed")

    # Not currently used so commenting out
    # def clear(self):
    #     self._octrl.fill(0)
    #     return self._show()

    def show(self):
        self._octrl.fill(0)

        for row in self._obuf:
            self._octrl.text(row[0], row[1], row[2])

        self._show()
