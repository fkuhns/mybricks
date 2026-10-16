from machine import Pin, I2C, reset # enable_irq, disable_irq
from picobricks import MotorDriver
from ir_sensor import NEC_8, IR_RX
from utime import sleep_ms, sleep_us, ticks_ms, ticks_diff, ticks_us
from ssd1306 import SSD1306_I2C
from usonic import UltrasonicSensor, UltraSonicTimeout, US_MAX_DIST

I2C0_ID       = 0
I2C0_SDA_PIN  = 4
I2C0_SCL_PIN  = 5

I2C1_ID       = 1
I2C1_SDA_PIN  = 2
I2C1_SCL_PIN  = 3

I2C_MAX_TRIES = 3

IR_PIN = 0

DIST_MIN_CHANGE = 1 # inches

class I2CException(Exception):
    pass

class MyApp():
    DEBUG = 1

    def __init__(self):
        self._init_i2c_env()
        self._init_ir_env()
        self.sonic = UltrasonicSensor()
        self.min_change = DIST_MIN_CHANGE
        self.last_dist = -1
        if MyApp.DEBUG:
            print("MyApp: Ultrasonic up")

    # ########## I2C ##########
    def _init_i2c_env(self):
        # I2C0 bus for devices other than the motor
        # I2C1 bus for the motors (SDA Pin & SCL Pin)
        # 2&3, 6&7, 10&11, 14&15, 18&19, 22&23, 26&27
        # used: 
        #   6/7 (LED), 10 (Button), 14/15 ultrasonic, 18/19 SPI,
        #   23 (SMPS control), 26 (Pot), 27 (LDR)
        # Available: Pins 2 & 3
        self.i2c = [{"OBJ": None, "SCL": I2C0_SCL_PIN, "SDA": I2C0_SDA_PIN, "FREQ": 400_000}, # I2C0_ID
                    {"OBJ": None, "SCL": I2C1_SCL_PIN, "SDA": I2C1_SDA_PIN, "FREQ":   100_000}] # I2C1_ID

        self.i2c[I2C0_ID]["OBJ"] = I2C(I2C0_ID, 
                                       scl  = Pin(self.i2c[I2C0_ID]["SCL"]), 
                                       sda  = Pin(self.i2c[I2C0_ID]["SDA"]), 
                                       freq = self.i2c[I2C0_ID]["FREQ"])

        # self.i2c[I2C1_ID]["OBJ"] = I2C(I2C1_ID, 
        #                                scl  = Pin(self.i2c[I2C1_ID]["SCL"]), 
        #                                sda  = Pin(self.i2c[I2C1_ID]["SDA"]), 
        #                                freq = self.i2c[I2C1_ID]["FREQ"])
        
        sleep_ms(5)        

        self._oled   = OledI2c(self.i2c[I2C0_ID]["OBJ"], "FK Car")
        self._motors = MotorsI2c(self.i2c[I2C0_ID]["OBJ"])

        if MyApp.DEBUG:
            print("MyAPP: I2C 0 ", self.i2c[I2C0_ID]["OBJ"])
            print("MyAPP: I2C 1 ", self.i2c[I2C1_ID]["OBJ"])
            print("MyAPP: OLED ",  self._oled.octrl)
            print("MyAPP: Motors ",self._motors._mctrl)

    def reset_i2c(self, id):
        # if id == 0:
        #     try:
        #         self.i2c0.deinit()
        #     except: Exception:
        #         pass
        if MyApp.DEBUG:
            print("** MyAPP: Resetting I2C bus ", id)

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

        if MyApp.DEBUG:
            print("** MyApp: New bus ", self.i2c[id]["OBJ"])

        return self.i2c[id]["OBJ"]

    # ########## OLED ##########
    def display(self):
        try:
            self._oled.show()
        except I2CException as e:
            if MyApp.DEBUG:
                print("\tDisplay: I2C exception, OLED show, reset I2C: ", e)
            self.reset_i2c(I2C0_ID)

    # ########## IR ##########

    def _init_ir_env(self):
        self._ir_cmd  = 0x00
        self._ir_rx   = False
        self._ir_ctrl = NEC_8(Pin(IR_PIN, Pin.IN), self.ir_callback) # type: ignore
        self._ir_ctrl._errf = self.ir_err
        if MyApp.DEBUG:
            print("** MyApp: IR up: ", self._ir_ctrl)

    def ir_callback(self, cmd, addr, _):
        # An IR message has been received, ignore address.
        self._ir_cmd = cmd
        self._ir_rx  = True
        if MyApp.DEBUG:
            print('# IR Callback -> Cmd: 0x{:02x} Addr: 0x{:04x}'.format(cmd, addr))

    def ir_err(self, err):
        if err == IR_RX.BADSTART:
            self._oled.update_row3("IR: BADSTART")
            if MyApp.DEBUG:
                print("*** IR Error: BADSTART ({})".format(err))
        elif err == IR_RX.BADBLOCK:
            self._oled.update_row3("IR: BADBLOCK")
            if MyApp.DEBUG:
                print("*** IR Error: BADBLOCK ({})".format(err))
        elif err == IR_RX.BADREP:
            self._oled.update_row3("IR: BADREP")
            if MyApp.DEBUG:
                print("*** IR Error: BADREP ({})".format(err))
        elif err == IR_RX.OVERRUN:
            self._oled.update_row3("IR: OVERRUN")
            if MyApp.DEBUG:
                print("*** IR Error: OVERRUN ({})".format(err))
        elif err == IR_RX.BADDATA:
            self._oled.update_row3("IR: BADDATA")
            if MyApp.DEBUG:
                print("*** IR Error: BADDATA ({})".format(err))
        elif err == IR_RX.BADADDR:
            self._oled.update_row3("IR: BADADDR")
            if MyApp.DEBUG:
                print("*** IR Error: BADADDR ({})".format(err))
        else:
            self._oled.update_row3("IR: {}".format(err))
            if MyApp.DEBUG:
                print("*** IR Error: Unknown{}".format(err))

    def process_ir_cmd(self, cmd):
        try:
            if   cmd == IR_RX.number_up:
                if MyApp.DEBUG:
                    print("\t# IR cmd Up ... moving forward")
                self._motors.forward()
                # self._oled.update_row2("m1=Fwd, m2=Fwd")
            elif cmd == IR_RX.number_down:
                if MyApp.DEBUG:
                    print("\t# IR cmd Down ... moving backward")
                self._motors.backward()
                # self._oled.update_row2("m1=Bkwd, m2=Bkwd")
            elif cmd == IR_RX.number_left:
                if MyApp.DEBUG:
                    print("\t# IR cmd Left ... turning left")
                self._motors.turn_left()
                # self._oled.update_row2("m1=Bkwd, m2=Fwd")
            elif cmd == IR_RX.number_right:
                if MyApp.DEBUG:
                    print("\t# IR cmd Right ... turning right")
                self._motors.turn_right()
                # self._oled.update_row2("m1=Fwd, m2=Bkwd")
            elif cmd == IR_RX.number_ok:
                if MyApp.DEBUG:
                    print("\t# IR cmd OK ... stopping motors")
                self._motors.stop_motors()
                # self._oled.update_row2("m1=Stop, m2=Stop")
            elif cmd == IR_RX.REPEAT:
                if MyApp.DEBUG:
                    print("\t# IR cmd Repeat ... ignoring")
                self._oled.update_row3("IR Repeat code")
                # Handle repeat code ...
            elif cmd >= 0:
                if MyApp.DEBUG:
                    print('\t* IR cmd Err: Not implemented: 0x{:02x}'.format(cmd))
                self._oled.update_row3("IR cmd not Impl")
            else:
                if MyApp.DEBUG:
                    print('\t* IR cmd Err: Unrecognized error code: 0x{:02x}'.format(cmd))
                self._oled.update_row3("IR cmd error")
            
        except I2CException as e:
            if MyApp.DEBUG:
                print("\t** IR cmd, I2C exception, Motor, reset I2C: ", e)
            self.reset_i2c(I2C0_ID)

    def process_ir_rx(self):
        # Called only if ir_rx is true, which means an IR message has been received and is ready to be processed.
        if not self._ir_rx:
            return
        
        if MyApp.DEBUG:
            print("# IR RX, ir_rx = {}, ir_cmd = 0x{:02x}".format(self._ir_rx, self._ir_cmd))

        self._ir_rx  = False
        code         = self._ir_cmd
        self._ir_cmd = 0

        try:
            self.process_ir_cmd(code)
            self.display()
        except I2CException as e:
            if MyApp.DEBUG:
                print("** IR RX, I2C Exception ignoring: ", e)
        except OSError as e:
            if MyApp.DEBUG:
                print("** IR RX, OS error exception, ignoring: ", e)       

    def process_dist(self):
        try:
            dist = self.sonic.get_distance() # distance in inches
        except UltraSonicTimeout:
            print("Dist: echo not received in timeout")
            return -1.0
        except Exception as e:
            print("Dist: Unexpected exception from ultrasonic get_distance(): ", e)
            return -1.0

        if abs(dist - self.last_dist) < self.min_change:
            return dist

        if dist >= 12.0:
            ft = dist // 12
            inch = dist % 12
            print("Distance {:.2f} / {} ft {:.2f} inches".format(dist, ft, inch))
        else:
            print("Distance {:.2f} in".format(dist))
        self.last_dist = dist
        self._oled.update_row2("Dist: %.2f" % dist)
        self._oled.show()

        return dist

    # ########## App ##########
    def run(self):
        self.min_change = 1 # inch
        self.sonic.tout_us = 1_000_000

        if self.DEBUG:
            print("MyApp.run() ...")
            print("tout: ", self.sonic.tout_us)

        last = 0
        dist = 0.0
        while True:
            try:
                # Get distance
                t = ticks_ms()
                if ticks_diff(t, last) >= 1000:
                    last = t
                    dist = self.process_dist()
                    if dist < 12:
                        self._motors.backward()
                        continue
                    elif dist <= 24.0:
                        self._motors.stop_motors()
                        continue
                    else:
                        self._motors.forward()
            except Exception as e:
                print("FIXME RUN: dist exception: ", e)
                self.shutdown()
                raise e

            # Get IR commands
            try:
                self.process_ir_rx()
            except KeyboardInterrupt as e:
                if MyApp.DEBUG:
                    print("** MyApp run, Keyboard interrupt ... exiting: ", e)
                self.shutdown()
                raise e
            except Exception as e:
                if MyApp.DEBUG:
                    print("** Caught an unexpected exception: ", e)
                self.shutdown()
                raise e

    def shutdown(self):
        self._motors.stop_motors()
        self._oled.clear()

#############################################################################
# Motors
#############################################################################
#MOTOR_MAX_SPEED  = 255
#MOTOR_MIN_SPEED  =   0
#MOTOR_TURN_SPEED = 150
MOTOR_DEF_SPEED  = 80

MOTOR_MAX_TRIES = I2C_MAX_TRIES

class MotorsI2c():
    _DEBUG = 0

    def __init__(self, i2c):
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
                    print("** OLED Exception: ", e)
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

#============================================================================

def main():
    myApp = MyApp()

    # check_motors()
    # sys.exit(1)
    try:
        myApp.run()
    except Exception as e:
        print("@@ Caught top level exception (main), resetting board: ", e)
        myApp.shutdown()
        # reset vs soft_reset() ... soft_reset() is not implemented in micropython for the Pico W
        # machine.reset will reset the Pico W and restart the program from the beginning.
        reset()
    
if __name__ == "__main__":
    main()