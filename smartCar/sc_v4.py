from machine import Pin, I2C, reset # enable_irq, disable_irq
from picobricks import MotorDriver
from ir_sensor import NEC_8, IR_RX
from utime import sleep_ms
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
# ir_rx  = False
# ir_cmd = 0x00

class I2CException(Exception):
    pass

class MyApp():
    def __init__(self):
        self._init_i2c_env()
        self._init_ir_env()
        
    def _init_ir_env(self):
        self.verbose = False
        self._ir_cmd  = 0x00
        self._ir_rx   = False
        self._ir_ctrl = NEC_8(Pin(IR_PIN, Pin.IN), self.ir_callback)
        self._ir_ctrl._errf = self.ir_err

    def _init_i2c_env(self):
        self.i2c  = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN))
        sleep_ms(100)        
        
        self._oled   = OledI2c(self.i2c, "FK Car")
        self._motors = MotorsI2c(self.i2c)

    def reset_i2c_env(self):
        self._init_i2c_env()

    def ir_callback(self, cmd, addr, _):
        # An IR message has been received, ignore address.
        self._ir_cmd = cmd
        self._ir_rx  = True
        if self.verbose:
            print('\t(1) IR Callback -> Cmd: 0x{:02x} Addr: 0x{:04x}'.format(cmd, addr))

    def display(self):
        try:
            self._oled.show()
        except I2CException as e:
            if self.verbose:
                print("I2C exception, OLED show, reset I2C: ", e)
            self.reset_i2c_env()

    def ir_err(self, err):
        if err == IR_RX.BADSTART:
            self._oled.update_err("IR Error: BADSTART")
            if self.verbose:
                print("\t\t(3) IR Error code received: BADSTART")
        elif err == IR_RX.BADBLOCK:
            self._oled.update_err("IR Error: BADBLOCK")
            if self.verbose:
                print("\t\t(3) IR Error code received: BADBLOCK")
        elif err == IR_RX.BADREP:
            self._oled.update_err("IR Error: BADREP")
            if self.verbose:
                print("\t\t(3) IR Error code received: BADREP")
        elif err == IR_RX.OVERRUN:
            self._oled.update_err("IR Error: OVERRUN")
            if self.verbose:
                print("\t\t(3) IR Error code received: OVERRUN")
        elif err == IR_RX.BADDATA:
            self._oled.update_err("IR Error: BADDATA")
            if self.verbose:
                print("\t\t(3) IR Error code received: BADDATA")
        elif err == IR_RX.BADADDR:
            self._oled.update_err("IR Error: BADADDR")
            if self.verbose:
                print("\t\t(3) IR Error code received: BADADDR")
        else:
            self._oled.update_err("IR Error: {}".format(err))
            if self.verbose:
                print("\t\t(3) IR Error code received: {}".format(err))

    def process_ir(self):
        if self.verbose:
            print("IR Processing, ir_rx = {}, ir_cmd = 0x{:02x}".format(self._ir_rx, self._ir_cmd))
  
        if not self._ir_rx:
            return

        self._ir_rx  = False
        code         = self._ir_cmd
        self._ir_cmd = 0

        try:
            if   code == IR_RX.number_up:
                self._motors.forward()
                self._oled.update_motor("m1=Fwd, m2=Fwd")
            elif code == IR_RX.number_down:
                self._motors.backward()
                self._oled.update_motor("m1=Bkwd, m2=Bkwd")
            elif code == IR_RX.number_left:
                self._motors.turn_left()
                self._oled.update_motor("m1=Bkwd, m2=Fwd")
            elif code == IR_RX.number_right:
                self._motors.turn_right()
                self._oled.update_motor("m1=Fwd, m2=Bkwd")
            elif code == IR_RX.number_ok:
                self._motors.stop_motors()
                self._oled.update_motor("m1=Stop, m2=Stop")
            elif code == IR_RX.REPEAT:
                if self.verbose:
                    print("\t\t(3) IR Repeat code received ... ignoring")
                self._oled.update_err("IR Repeat code")
                # Handle repeat code ...
            else:
                if self.verbose:
                    print('\t\t(3) IR cmd Not Implemented: 0x{:02x}'.format(code))
                self._oled.update_err("IR cmd not impl")
            self.display()
        except I2CException as e:
            if self.verbose:
                print("Reset I2C environment: ", e)
            self.reset_i2c_env()
        
    def run(self):
        while True:
            try:
                if self._ir_rx:
                    self.process_ir()
                #sleep_ms(100)
            except OSError as e:
                if self.verbose:
                    print("Caught an OS error, continuing: ", e)
            except KeyboardInterrupt as e:
                if self.verbose:
                    print("Keyboard interrupt ... exiting: ", e)
                self._motors.stop_motors()
                self._oled.clear()
                sys.exit(0) #return
            except Exception as e:
                if self.verbose:
                    print("Caught an unexpected exception, exiting: ", e)
                self._motors.stop_motors()
                self._oled.clear()
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
        self._init_motors(i2c)

    def _init_motors(self, i2c):
        # Motor controller is address 0x22, its hard coded in the MotorDriver class.
        self._mctrl = MotorDriver(i2c)
        sleep_ms(100)
        self.stop_motors()
        #sleep_ms(100)

    def _set_motor(self, mid, speed, direction):
        for i in range(MOTOR_MAX_TRIES):
            try:
                self._mctrl.dc(mid, speed, direction)
                return
            except OSError as e:
                pass #sleep_ms(20)
        raise I2CException("set_motor {} failed".format(mid))

    def forward(self, speed=MOTOR_DEF_SPEED):
        self.motors_state = "Forward"
        self._set_motor(1, speed, 0)
        self._set_motor(2, speed, 0)

    def backward(self, speed=MOTOR_DEF_SPEED):
        self.motors_state = "Backward"
        self._set_motor(1, speed, 1)
        self._set_motor(2, speed, 1)

    def turn_right(self, speed=MOTOR_DEF_SPEED):
        self.motors_state = "Right"
        self._set_motor(1, speed, 0)
        self._set_motor(2, speed, 1)

    def turn_left(self, speed=MOTOR_DEF_SPEED):
        self.motors_state = "Left"
        self._set_motor(1, speed, 1)
        self._set_motor(2, speed, 0)

    def stop_motors(self):
        self.motors_state = "Stopped"
        self._set_motor(1, 0, 0)
        self._set_motor(2, 0, 0)

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
        # Chars per Row: 16
        # Row 1: | FK Car|
        # Row 2: | motor state |
        # Row 3: | Errors |
        self._hdr = hdr
        self._obuf = [["row 1", 0, 0], ["row 2", 0, OLED_ROW_HEIGHT], ["row 3", 0, 2 * OLED_ROW_HEIGHT]]
        self._init(i2c)
    
    def _init(self, i2c):
        self.octrl = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, OLED_I2C_ADDR)
        self._init_buf()
        sleep_ms(100)

    def _init_buf(self):
        self.update_hdr()
        self.update_motor("Motors: init")
        self.update_err("Status: Good")

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

    def update_hdr(self):
        self._update_row(1, self._hdr)

    def update_motor(self, txt):
        self._update_row(2, txt)

    def update_err(self, txt):
        self._update_row(3, txt)

    def _show(self):
        for i in range(MOTOR_MAX_TRIES):
            try:
                self.octrl.show()
                return
            except OSError:
                pass
            sleep_ms(20)
        raise I2CException("Oled show failed")
        return False

    def clear(self):
        self.octrl.fill(0)
        return self._show()

    def show(self):
        self.octrl.fill(0)
        for row in self._obuf:
            self.octrl.text(row[0], row[1], row[2])
        return self._show()

#============================================================================

def main():
    myApp = MyApp()

    # check_motors()
    # sys.exit(1)
    try:
        myApp.run()
    except Exception as e:
        print("Caught an uncaught exception in main! resetting board: ", e)
        # reset vs soft_reset() ... soft_reset() is not implemented in micropython for the Pico W
        # machine.reset will reset the Pico W and restart the program from the beginning.
        reset()
    
if __name__ == "__main__":
    main()