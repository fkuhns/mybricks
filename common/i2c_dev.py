from machine import Pin, I2C
#from picobricks import MotorDriver
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

class I2cBus():
    # What devices hold instead of a machine.I2C object. Retries failed
    # writes and reports each failure to I2cCtl, which may reset the bus.
    # A reset only swaps the machine.I2C object inside I2cCtl, so devices
    # never need to rebind. Raises I2CException when all tries fail.
    def __init__(self, ctl, id=I2C0_ID):
        self._ctl = ctl
        self._id  = id

    def __str__(self):
        return "I2cBus {}: {}".format(self._id, self._ctl._i2c[self._id]["OBJ"])

    def _write(self, fn_name, addr, buf):
        last_error = None
        assert fn_name != None

        for i in range(I2C_MAX_TRIES):
            try:
                return getattr(self._ctl._i2c[self._id]["OBJ"], fn_name)(addr, buf)
            except OSError as e:
                last_error = e
                if self._ctl.DEBUG:
                    print("I2cBus.{} 0x{:02x} try {} OSError: {}".format(fn_name, addr, i, e))
                self._ctl.handle_err(self._id)
        raise I2CException("I2C {} 0x{:02x} failed after {} tries: {}".format(
                           fn_name, addr, I2C_MAX_TRIES, last_error))

    def writeto(self, addr, buf):
        return self._write("writeto", addr, buf)

    def writevto(self, addr, bufs):
        return self._write("writevto", addr, bufs)

class I2cCtl():
    # bus() returns an I2CBus wrapper object (wraps I2C).
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
        # FIXME: Do I need this -> sleep_ms(1)        

        if self.DEBUG:
            print("I2cCtl: I2C 0 ", self._i2c[I2C0_ID]["OBJ"])
            print("I2cCtl: I2C 1 ", self._i2c[I2C1_ID]["OBJ"])

    def __str__(self):
        return "I2C: {}".format(self._i2c[I2C0_ID]["OBJ"])
    
    def bus(self, id=I2C0_ID):
        assert id == I2C0_ID # FIXME: Temporary until I decide if I want both busses
        return I2cBus(self, id)

    def handle_err(self, id=I2C0_ID):
        # Called by I2cBus for each failed write. Resets the bus once there
        # are I2C_ERR_MAX_CNT errors within I2C_ERR_MAX_MS.
        # Returns True if the bus was reset, does not raise exceptions.
        t = ticks_ms()
        if ticks_diff(t, self.Errors[id]["last"]) > I2cCtl.I2C_ERR_MAX_MS:
            # reset error count and return
            self.Errors[id]["last"]  = t
            self.Errors[id]["count"] = 1
            return False

        # increment error count
        self.Errors[id]["count"] += 1
        if self.Errors[id]["count"] < I2cCtl.I2C_ERR_MAX_CNT:
            return False

        # Over error count, reset bus and init error count
        self.Errors[id]["count"] = 0
        self.Errors[id]["last"]  = 0
        try:
            self._reset_i2c(id)
        except Exception as e:
            if self.DEBUG:
                print("I2cCtl handle_err reset failed: ", e)
            return False

        return True

    def _reset_i2c(self, id=I2C0_ID):
        # Can handle where the master has stopped issuing clock cycles
        # slave is holding sda low waiting.
        # This does not address clock stretching, for that need to give
        # peripheral time 
        # No exception (except for assertions)
        assert id == I2C0_ID # FIXME: Temporary until I decide if I want both busses
        old_i2c = self._i2c[id]["OBJ"]
        if (not old_i2c) and self.DEBUG:
            # Should never happen, but not a problem since we are creating a new one
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

            if self.DEBUG and (sda.value() == 0):
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
            # FIXME: Do I need to redefine pins?
            self._i2c[id]["OBJ"] = old_i2c
            raise e

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

class OledI2c():
    def __init__(self, bus, hdr, debug=0):
        # Chars per Row: 16
        # Row 1: | FK Car|
        # FIXME: Row 2: | motor state |
        # Row 3: | Errors |
        self.DEBUG = debug
        self._hdr = hdr
        self._obuf = [["row 1", 0, 0], ["row 2", 0, OLED_ROW_HEIGHT], ["row 3", 0, 2 * OLED_ROW_HEIGHT]]
        self._octrl = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, bus, OLED_I2C_ADDR)
        self.init_buf()
        sleep_ms(5)

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

    # Not currently used so commenting out
    # def clear(self):
    #     self._octrl.fill(0)
    #     self._octrl.show()

    def show(self):
        # throws I2CException, the bus has already retried and reset
        self._octrl.fill(0)

        for row in self._obuf:
            self._octrl.text(row[0], row[1], row[2])

        self._octrl.show()
