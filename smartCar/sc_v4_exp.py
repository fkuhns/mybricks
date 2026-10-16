from machine import Pin, I2C, reset # enable_irq, disable_irq
from picobricks import MotorDriver
from ir_sensor import NEC_8, IR_RX
from utime import sleep_ms, sleep_us
from ssd1306 import SSD1306_I2C
import sys
from array import array

I2C0_ID       = 0
I2C0_SDA_PIN  = 4
I2C0_SCL_PIN  = 5

I2C1_ID       = 1
I2C1_SDA_PIN  = 2
I2C1_SCL_PIN  = 3

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
    _DEBUG = const(0)

    def __init__(self):
        self._init_i2c_env()
        self._init_ir_env()
        
    def _init_ir_env(self):
        MyApp._DEBUG = True
        self._ir_cmd  = 0x00
        self._ir_rx   = False
        self._ir_ctrl = NEC_8(Pin(IR_PIN, Pin.IN), self.ir_callback) # type: ignore
        self._ir_ctrl._errf = self.ir_err

    def _init_i2c_env(self):

        # I2C0 bus for devices other than the motor
        # I2C1 bus for the motors (SDA Pin & SCL Pin)
        # 2&3, 6&7, 10&11, 14&15, 18&19, 22&23, 26&27
        # used: 
        #   6/7 (LED), 10 (Button), 14/15 ultrasonic, 18/19 SPI,
        #   23 (SMPS control), 26 (Pot), 27 (LDR)
        # Available: Pins 2 & 3
        self.i2c = [
            I2C(0, scl=Pin(I2C0_SCL_PIN), sda=Pin(I2C0_SDA_PIN), freq=1_000_000),
            I2C(1, scl=Pin(I2C1_SCL_PIN), sda=Pin(I2C1_SDA_PIN), freq=100_000) ]

        sleep_ms(5)        
        
        self._oled   = OledI2c(self.i2c[0], "FK Car")
        self._motors = MotorsI2c(self.i2c[1])

    def reset_i2c(self, id):
        # if id == 0:
        #     try:
        #         self.i2c0.deinit()
        #     except: Exception:
        #         pass
        scl = None
        sda = None
        
        if id == 0:
            scl = Pin(I2C0_SCL_PIN, Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
            sda = Pin(I2C0_SDA_PIN, Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
        else:
            scl = Pin(I2C1_SCL_PIN, Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
            sda = Pin(I2C1_SDA_PIN, Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
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

        if id == 0:
            self.i2c[0] = I2C(0, scl=Pin(I2C0_SCL_PIN), sda=Pin(I2C0_SDA_PIN), freq=1_000_000)
            self._oled   = OledI2c(self.i2c[0], "FK Car")
        else:
            self.i2c[1] = I2C(1, scl=Pin(I2C1_SCL_PIN), sda=Pin(I2C1_SDA_PIN), freq=100_000)
            self._motors = MotorsI2c(self.i2c[1])

    def reset_i2c_env(self, id):
        self.reset_i2c(id)

    def ir_callback(self, cmd, addr, _):
        # An IR message has been received, ignore address.
        self._ir_cmd = cmd
        self._ir_rx  = True
        if MyApp._DEBUG:
            print('# IR Callback -> Cmd: 0x{:02x} Addr: 0x{:04x}'.format(cmd, addr))

    def display(self):
        try:
            self._oled.show()
        except I2CException as e:
            if MyApp._DEBUG:
                print("\t** I2C exception, OLED show, reset I2C: ", e)
            self.reset_i2c(0)

    def ir_err(self, err):
        if err == IR_RX.BADSTART:
            self._oled.update_err("Decode: BADSTART")
            if MyApp._DEBUG:
                print("*** Decode Error: BADSTART ({})".format(err))
        elif err == IR_RX.BADBLOCK:
            self._oled.update_err("Decode: BADBLOCK")
            if MyApp._DEBUG:
                print("*** Decode Error: BADBLOCK ({})".format(err))
        elif err == IR_RX.BADREP:
            self._oled.update_err("Decode: BADREP")
            if MyApp._DEBUG:
                print("*** Decode Error: BADREP ({})".format(err))
        elif err == IR_RX.OVERRUN:
            self._oled.update_err("Decode: OVERRUN")
            if MyApp._DEBUG:
                print("*** Decode Error: OVERRUN ({})".format(err))
        elif err == IR_RX.BADDATA:
            self._oled.update_err("Decode: BADDATA")
            if MyApp._DEBUG:
                print("*** Decode Error: BADDATA ({})".format(err))
        elif err == IR_RX.BADADDR:
            self._oled.update_err("Decode: BADADDR")
            if MyApp._DEBUG:
                print("*** Decode Error: BADADDR ({})".format(err))
        else:
            self._oled.update_err("Decode: {}".format(err))
            if MyApp._DEBUG:
                print("*** Decode Error: Unknown{}".format(err))

    def process_motor_cmd(self, cmd):
        try:
            str = self._motors.process_motor_cmd(cmd)
        except I2CException as e:
            if MyApp._DEBUG:
                print("\t** I2C error, Resetting env: ", e)
            self.reset_i2c(1)
            raise

        self._oled.update
        try:
            if   cmd == IR_RX.number_up:
                if MyApp._DEBUG:
                    print("\t# IR Up code received ... moving forward")
                self._motors.forward()
                self._oled.update_motor("m1=Fwd, m2=Fwd")
            elif cmd == IR_RX.number_down:
                if MyApp._DEBUG:
                    print("\t# IR Down cmd received ... moving backward")
                self._motors.backward()
                self._oled.update_motor("m1=Bkwd, m2=Bkwd")
            elif cmd == IR_RX.number_left:
                if MyApp._DEBUG:
                    print("\t# IR Left cmd received ... turning left")
                self._motors.turn_left()
                self._oled.update_motor("m1=Bkwd, m2=Fwd")
            elif cmd == IR_RX.number_right:
                if MyApp._DEBUG:
                    print("\t# IR Right cmd received ... turning right")
                self._motors.turn_right()
                self._oled.update_motor("m1=Fwd, m2=Bkwd")
            elif cmd == IR_RX.number_ok:
                if MyApp._DEBUG:
                    print("\t# IR OK cmd received ... stopping motors")
                self._motors.stop_motors()
                self._oled.update_motor("m1=Stop, m2=Stop")
            elif cmd == IR_RX.REPEAT:
                if MyApp._DEBUG:
                    print("\t# IR Repeat cmd received ... ignoring")
                self._oled.update_err("IR Repeat cmd")
                # Handle repeat cmd ...
            elif cmd >= 0:
                if MyApp._DEBUG:
                    print('\t* Error: IR cmd not implemented: 0x{:02x}'.format(cmd))
                self._oled.update_err("IR cmd not Impl")
            else:
                if MyApp._DEBUG:
                    print('\t* Error: IR cmd error: 0x{:02x}'.format(cmd))
                self._oled.update_err("IR cmd error")
            
        except I2CException as e:
            if MyApp._DEBUG:
                print("\t** I2C error, Resetting env: ", e)
            self.reset_i2c(1)
            raise

    def process_ir(self):
        # Called only if ir_rx is true, which means an IR message has been received and is ready to be processed.
        if MyApp._DEBUG:
            print("# IR Processing, ir_rx = {}, ir_cmd = 0x{:02x}".format(self._ir_rx, self._ir_cmd))

        self._ir_rx  = False
        code         = self._ir_cmd
        self._ir_cmd = 0


        self.display()
        
    def run(self):
        while True:
            try:
                if self._ir_rx:
                    self.process_ir()
                #sleep_ms(100)
            except OSError as e:
                if MyApp._DEBUG:
                    print("-- Caught an OS error, continuing: ", e)
            except KeyboardInterrupt as e:
                if MyApp._DEBUG:
                    print("-- Keyboard interrupt ... exiting: ", e)
                self._motors.stop_motors()
                self._oled.clear()
                sys.exit(0) #return
            except Exception as e:
                if MyApp._DEBUG:
                    print("-- Caught an unexpected exception: ", e)
                self._motors.stop_motors()
                self._oled.clear()
                raise e

#############################################################################
# Motors
#############################################################################
#MOTOR_MAX_SPEED  = 255
#MOTOR_MIN_SPEED  =   0
#MOTOR_TURN_SPEED = 150
MOTOR_DEF_SPEED  = 80

MOTOR_MAX_TRIES = I2C_MAX_TRIES

class MotorsI2c():
    def __init__(self, i2c):
        self._init_motors(i2c)

    def _init_motors(self, i2c):
        # Motor controller is address 0x22, its hard coded in the MotorDriver class.
        self._mctrl = MotorDriver(i2c)
        sleep_ms(5)
        self.stop_motors()
        #sleep_ms(5)

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

    def process_motor_cmd(self, cmd):
        try:
            if   cmd == IR_RX.number_up:
                if MyApp._DEBUG:
                    print("\t# IR Up code received ... moving forward")
                self.forward()
                str="m1=Fwd, m2=Fwd"
            elif cmd == IR_RX.number_down:
                if MyApp._DEBUG:
                    print("\t# IR Down cmd received ... moving backward")
                self.backward()
                str = "m1=Bkwd, m2=Bkwd"
            elif cmd == IR_RX.number_left:
                if MyApp._DEBUG:
                    print("\t# IR Left cmd received ... turning left")
                self.turn_left()
                str = "m1=Bkwd, m2=Fwd"
            elif cmd == IR_RX.number_right:
                if MyApp._DEBUG:
                    print("\t# IR Right cmd received ... turning right")
                self.turn_right()
                str = "m1=Fwd, m2=Bkwd"
            elif cmd == IR_RX.number_ok:
                if MyApp._DEBUG:
                    print("\t# IR OK cmd received ... stopping motors")
                self.stop_motors()
                str = "m1=Stop, m2=Stop"
            elif cmd == IR_RX.REPEAT:
                if MyApp._DEBUG:
                    print("\t# IR Repeat cmd received ... ignoring")
                str = "IR Repeat cmd"
                # Handle repeat cmd ...
            elif cmd >= 0:
                if MyApp._DEBUG:
                    print('\t* Error: IR cmd not implemented: 0x{:02x}'.format(cmd))
                str = "IR cmd not Impl"
            else:
                if MyApp._DEBUG:
                    print('\t* Error: IR cmd error: 0x{:02x}'.format(cmd))
                str = "IR cmd error"
            
        except I2CException as e:
            if MyApp._DEBUG:
                print("\t** I2C error, Resetting env: ", e)
            raise

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
        sleep_ms(5)

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
        print("@@ Caught top level exception (main), resetting board: ", e)
        # reset vs soft_reset() ... soft_reset() is not implemented in micropython for the Pico W
        # machine.reset will reset the Pico W and restart the program from the beginning.
        reset()
    
if __name__ == "__main__":
    main()