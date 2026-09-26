from machine import Pin, I2C
from utime import sleep
from picobricks import MotorDriver, NEC_16, IR_RX
from utime import sleep, sleep_ms
from ssd1306 import SSD1306_I2C
import sys

I2C_ID       = 0
I2C_SDA_PIN  = 4
I2C_SCL_PIN  = 5
I2C_MAX_TRIES = 3

#############################################################################
# IR
#############################################################################
IR_PIN = 0
ir_rx  = False
ir_cmd = 0x00

class I2CException(Exception):
    pass

class MyApp():
    def __init__(self):
        self._init_ir_env()
        self._init_i2c_env()

    def _init_ir_env(self):
        self.ir_cmd = 0
        self.ir_rx = False
        self.ir = NEC_16(Pin(IR_PIN, Pin.IN), self.ir_callback)

    def _init_i2c_env(self):
        self.i2c  = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN))
        sleep_ms(100)        
        
        self.oled  = OledI2c(self.i2c, "FK Car")
        self.motor = MotorsI2c(self.i2c)

    def reset_i2c_env(self):
        self._init_i2c_env()

    def ir_callback(self, cmd, addr, _):
        if cmd > 0:
            self.ir_cmd = cmd
            self.ir_rx  = True
            print('IR -> Cmd: 0x{:02x} Addr: 0x{:04x}'.format(cmd, addr))
    
    def process_ir(self):
        global motor, oled
        if not ir_rx:
            return

        self.ir_rx  = False
        code   = self.ir_cmd
        self.ir_cmd = 0

        if   code == IR_RX.number_up:
            self.motor.forward()
            self.oled.update_motor("m1=Fwd, m2=Fwd")
        elif code == IR_RX.number_down:
            self.motor.backward()
            self.oled.update_motor("m1=Bkwd, m2=Bkwd")
        elif code == IR_RX.number_left:
            self.motor.turn_left()
            self.oled.update_motor("m1=Bkwd, m2=Fwd")
        elif code == IR_RX.number_right:
            self.motor.turn_right()
            self.oled.update_motor("m1=Fwd, m2=Bkwd")
        elif code == IR_RX.number_ok:
            self.motor.stop_motors()
            self.oled.update_motor("m1=Stop, m2=Stop")
        else:
            print("Not implemented IR Code: 0x{:02x}".format(code))
            self.oled.update_err("IR cmd not impl")
        sleep_ms(100)
        self.oled.show()
    
    def run(self):
        while True:
            try:
                self.process_ir()
                sleep_ms(100)
            except OSError as e:
                print("Caught an OS error, continuing: ", e)
            except KeyboardInterrupt as e:
                print("Keyboard interrupt ... exiting: ", e)
                self.motor.stop_motors()
                self.oled.clear()
                sys.exit(0) #return
            except Exception as e:
                print("Caught an unexpected exception, exiting: ", e)
                self.motor.stop_motors()
                self.oled.clear()
                sys.exit(1) #return


#############################################################################
# Motors
#############################################################################
#MOTOR_MAX_SPEED  = 255
#MOTOR_MIN_SPEED  =   0
#MOTOR_TURN_SPEED = 150
MOTOR_DEF_SPEED  = 200

MOTOR_MAX_TRIES = I2C_MAX_TRIES

class MotorsI2c():
    def __init__(self, i2c):
        self.init_motors(i2c)

    def init_motors(self, i2c):
        # Motor controller is address 0x22, its hard coded in the MotorDriver class.
        self.motor = MotorDriver(i2c)
        sleep_ms(100)
        self.stop_motors()
        sleep_ms(100)

    def set_motor(self, mid, speed, direction):
        for i in range(MOTOR_MAX_TRIES):
            try:
                self.motor.dc(mid, speed, direction)
                return True
            except OSError as e:
                print("set_motor: error (try {} of {}): {}".format(i, I2C_MAX_TRIES, e))
                sleep_ms(100)
        print("### Unable to set motor speed and direction, reset i2c env")
        raise I2CException("set_motor failed")
        return False

    def forward(self, speed=MOTOR_DEF_SPEED):
        self.motors_state = "Forward"
        self.set_motor(1, speed, 0)
        self.set_motor(2, speed, 0)

    def backward(self, speed=MOTOR_DEF_SPEED):
        self.motors_state = "Backward"
        self.set_motor(1, speed, 1)
        self.set_motor(2, speed, 1)

    def turn_right(self, speed=MOTOR_DEF_SPEED):
        self.motors_state = "Right"
        self.set_motor(1, speed, 0)
        self.set_motor(2, speed, 1)

    def turn_left(self, speed=MOTOR_DEF_SPEED):
        self.motors_state = "Left"
        self.set_motor(1, speed, 1)
        self.set_motor(2, speed, 0)

    def stop_motors(self):
        self.motors_state = "Stopped"
        self.set_motor(1, 0, 0)
        self.set_motor(2, 0, 0)

# def check_motors():
#     motors.stop_motors()
#     oled_show()
#     sleep(1)
#     #
#     motors.forward()
#     oled_show()
#     sleep(1)
#     #
#     motors.backward()
#     oled_show()
#     sleep(1)
#     #
#     motors.turn_right()
#     oled_show()
#     sleep(1)
#     #
#     motors.turn_left()
#     oled_show()
#     sleep(1)
#     #
#     motors.stop_motors()
#     oled_show()
#     sleep(1)
#     #
#     print("Done")

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
    def __init__(self, i2c, hdr):
        global OLED_ROW_HEIGHT
        # Chars per Row: 16
        # Row 1: | FK Car|
        # Row 2: | motor state |
        # Row 3: | Errors |
        self.hdr = hdr
        self.oled_buf = [["row 1", 0, 0], ["row 2", 0, OLED_ROW_HEIGHT], ["row 3", 0, 2 * OLED_ROW_HEIGHT]]
        self.init(i2c)
    
    def init(self, i2c):
        global OLED_WIDTH, OLED_HEIGHT, OLED_I2C_ADDR
        self.oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, OLED_I2C_ADDR)
        self.init_buf()
        sleep_ms(100)

    def init_buf(self):
        self.update_hdr()
        self.update_motor("Motors: init")
        self.update_err("Status: Good")

    def update_row(self, row, txt):
        global OLED_ROW_HEIGHT, OLED_ROW_CHARS, OLED_ROW_CENTER, OLED_CHAR_SIZE
        tlen    = len(txt)
        xstart  = 0
        yoffset = (row - 1) * OLED_ROW_HEIGHT

        if tlen < OLED_ROW_CHARS:
            xstart  = OLED_ROW_CENTER - ((tlen * OLED_CHAR_SIZE) // 2)
        else: # tlen >= OLED_ROW_CHARS:
            txt  = txt[:OLED_ROW_CHARS]
            xstart = 0
        
        self.oled_buf[row-1][0] = txt
        self.oled_buf[row-1][1] = xstart
        self.oled_buf[row-1][2] = yoffset

        #oled.fill_rect(xstart, yoffset, 128, 8, 0)
        #oled.text(txt, xstart, yoffset)

    def update_hdr(self):
        self.update_row(1, self.hdr)

    def update_motor(self, txt):
        self.update_row(2, txt)

    def update_err(self, txt):
        self.update_row(3, txt)

    def _show(self):
        for i in range(MOTOR_MAX_TRIES):
            try:
                self.oled.show()
                return True
            except OSError as e:
                self.update_err("oled show failed")
                print("oled_show: {}".format(e))
            sleep_ms(100)
        print("oled.show() failed ... reset i2c env")
        raise I2CException("Oled show failed")
        return False

    def clear(self):
        self.oled.fill(0)
        return self._show()

    def show(self):
        self.oled.fill(0)
        for row in self.oled_buf:
            self.oled.text(row[0], row[1], row[2])
        return self._show()


#============================================================================

def main():
    myApp = MyApp()

    # check_motors()
    # sys.exit(1)
    try:
        myApp.run()
    except Exception as e:
        print("Caught an uncaught exception in main! exiting: ", e)
        sys.exit(1) #return
    

if __name__ == "__main__":
    main()