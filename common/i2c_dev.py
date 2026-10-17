from machine import Pin, I2C # , reset, enable_irq, disable_irq
from picobricks import MotorDriver
from ir_sensor import NEC_8, IR_RX
from utime import sleep_ms, sleep_us, ticks_ms, ticks_diff, ticks_us
from ssd1306 import SSD1306_I2C

I2C0_ID       = 0
I2C0_SDA_PIN  = 4
I2C0_SCL_PIN  = 5

I2C1_ID       = 1
I2C1_SDA_PIN  = 2
I2C1_SCL_PIN  = 3

I2C_MAX_TRIES = 3

#############################################################################
# Motors
#############################################################################
#MOTOR_MAX_SPEED  = 255
#MOTOR_MIN_SPEED  =   0
#MOTOR_TURN_SPEED = 150
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
    def __init__(self):
        # I2C0 bus for devices other than the motor
        # I2C1 bus for the motors (SDA Pin & SCL Pin)
        # 2&3, 6&7, 10&11, 14&15, 18&19, 22&23, 26&27
        # used: 
        #   6/7 (LED), 10 (Button), 14/15 ultrasonic, 18/19 SPI,
        #   23 (SMPS control), 26 (Pot), 27 (LDR)
        # Available: Pins 2 & 3
        self.DEBUG = 1
        self.i2c = [{"OBJ": None, "SCL": I2C0_SCL_PIN, "SDA": I2C0_SDA_PIN, "FREQ": 400_000},
                    {"OBJ": None, "SCL": I2C1_SCL_PIN, "SDA": I2C1_SDA_PIN, "FREQ": 100_000}]
        
        self.i2c[I2C0_ID]["OBJ"] = I2C(I2C0_ID, 
                                        scl  = Pin(self.i2c[I2C0_ID]["SCL"]), 
                                        sda  = Pin(self.i2c[I2C0_ID]["SDA"]), 
                                        freq = self.i2c[I2C0_ID]["FREQ"])
        # FIXME: fix assumption that only one bus is used!
        # self.i2c[I2C1_ID]["OBJ"] = I2C(I2C1_ID, 
        #                                scl  = Pin(self.i2c[I2C1_ID]["SCL"]), 
        #                                sda  = Pin(self.i2c[I2C1_ID]["SDA"]), 
        #   
        sleep_ms(5)        

        if self.DEBUG:
            print("I2cCtl: I2C 0 ", self.i2c[I2C0_ID]["OBJ"])
            print("I2cCtl: I2C 1 ", self.i2c[I2C1_ID]["OBJ"])
    
    def reset_i2c(self, id):
        if not self.i2c[id]["OBJ"]:
            if self.DEBUG:
                print("I2CTL.reset_i2c: i2c ID 2 not defined")
            return

        if self.DEBUG:
                    print("I2cCtl.reset_i2c: Resetting I2C bus ", id)
        # if id == 0:
        #     try:
        #         self.i2c0.deinit()
        #     except: Exception:
        #         pass

        scl = Pin(self.i2c[id]["SCL"], Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
        sda = Pin(self.i2c[id]["SDA"], Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
        
        sleep_us(10)

        for _ in range(9):
            if sda.value():
                break
            scl.value(0)
            sleep_us(5)
            scl.value(1)
            sleep_us(5)

        sda.value(0)
        sleep_us(5)
        scl.value(1)
        sleep_us(5)
        sda.value(1)
        sleep_us(5)

        self.i2c[id]["OBJ"] = I2C(id, 
                                  scl =Pin(self.i2c[id]["SCL"]), 
                                  sda =Pin(self.i2c[id]["SDA"]), 
                                  freq=self.i2c[id]["FREQ"])

        if self.DEBUG:
            print("** I2cCtl: New bus ", self.i2c[id]["OBJ"])

        return self.i2c[id]["OBJ"]

class MotorsI2c():
    _DEBUG = 1

    def __init__(self, i2c):
        self.state = MOTOR_STATE_INIT
        self._init_motors(i2c)

    def _init_motors(self, i2c):
        # Motor controller is address 0x22, its hard coded in the MotorDriver class.
        self._mctrl = MotorDriver(i2c)
        sleep_ms(5)
        self.stop_motors()
        #sleep_ms(5)

    def _set_motor(self, mid, speed, direction):
        #print("_set_motor: {}, {}, {}".format(mid, speed, direction))
        for i in range(MOTOR_MAX_TRIES):
            try:
                self._mctrl.dc(mid, speed, direction)
                return
            except OSError as e:
                if MotorsI2c._DEBUG:
                    print("** Set_motor exception: ", e)
                sleep_ms(0.5)
            except Exception as e:
                print("_set_motor Unexpected exception ", e)
            print("set_motor loop: ", i)

        raise I2CException("set_motor failed")

    def forward(self, speed=MOTOR_DEF_SPEED):
        self.state = MOTOR_STATE_UNK
        self._set_motor(1, speed, 0)
        self._set_motor(2, speed, 0)
        self.state = MOTOR_STATE_FWD

    def backward(self, speed=MOTOR_DEF_SPEED):
        self.state = MOTOR_STATE_UNK
        self._set_motor(1, speed, 1)
        self._set_motor(2, speed, 1)
        self.state = MOTOR_STATE_BKWD

    def turn_right(self, speed=MOTOR_DEF_SPEED):
        self.state = MOTOR_STATE_UNK
        self._set_motor(1, speed, 0)
        self._set_motor(2, speed, 1)
        self.state = MOTOR_STATE_RIGHT

    def turn_left(self, speed=MOTOR_DEF_SPEED):
        self.state = MOTOR_STATE_UNK
        self._set_motor(1, speed, 1)
        self._set_motor(2, speed, 0)
        self.state = MOTOR_STATE_LEFT

    def stop_motors(self):
        self.state = MOTOR_STATE_UNK
        self._set_motor(1, 0, 0)
        self._set_motor(2, 0, 0)
        self.state = MOTOR_STATE_STOP

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
    _DEBUG = 0
    
    def __init__(self, i2c, hdr):
        # Chars per Row: 16
        # Row 1: | FK Car|
        # FIXME: Row 2: | motor state |
        # Row 3: | Errors |
        self._hdr = hdr
        self._obuf = [["row 1", 0, 0], ["row 2", 0, OLED_ROW_HEIGHT], ["row 3", 0, 2 * OLED_ROW_HEIGHT]]
        self._init(i2c)
    
    def _init(self, i2c):
        self.octrl = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, OLED_I2C_ADDR)
        self._init_buf()
        sleep_ms(5)

    def _init_buf(self):
        self.update_row1()
        self.update_row2("Dist: -")
        self.update_row3("Status: Good")

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
                self.octrl.show()
                return
            except OSError as e:
                if OledI2c._DEBUG:
                    print("** OLED OS Error Exception: ", e)
                pass
            sleep_ms(5)
        else:
            raise I2CException("Oled show failed")
  
    def clear(self):
        self.octrl.fill(0)
        return self._show()

    def show(self):
        self.octrl.fill(0)
        for row in self._obuf:
            self.octrl.text(row[0], row[1], row[2])
        return self._show()