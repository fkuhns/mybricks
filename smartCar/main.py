from machine import Pin, I2C, reset # enable_irq, disable_irq
from ir_sensor import NEC_8, IR_RX
from utime import sleep_ms, sleep_us, ticks_ms, ticks_diff #, ticks_us
#from ssd1306 import SSD1306_I2C
from usonic import UltrasonicSensor, UltraSonicTimeout
from buzzer import Buzzer
from i2c_dev import I2cCtl, MotorsI2c, OledI2c, I2CException

MODE_DIST = const(1)  # bin 0001
MODE_IR   = const(2)  # bin 0010

I2C0_ID       = 0
I2C0_SDA_PIN  = 4
I2C0_SCL_PIN  = 5

I2C1_ID       = 1
I2C1_SDA_PIN  = 2
I2C1_SCL_PIN  = 3

IR_PIN = 0

DIST_MIN_CHANGE = 1 # inches

class AppException(Exception):
    pass

class MyApp():
    DEBUG = 1

    def __init__(self):
        self.init_i2c_env()
        self._init_ir_env()
        self.sonic = UltrasonicSensor()
        self.min_change = DIST_MIN_CHANGE
        self.last_dist  = -1
        self.last_ticks =  0
        self.buzzer = Buzzer(MyApp.DEBUG)
        if MyApp.DEBUG:
            print("MyApp: Ultrasonic up")

    # ########## I2C ##########
    def init_i2c_env(self):
        self.i2ctl = I2cCtl()

        self.oled   = OledI2c(self.i2ctl.i2c[I2C0_ID]["OBJ"], "FK Car")
        self.motors = MotorsI2c(self.i2ctl.i2c[I2C0_ID]["OBJ"])

        if MyApp.DEBUG:
            print("MyAPP: OLED ",  self.oled.octrl)
            print("MyAPP: Motors ",self.motors._mctrl)

    def reset_i2c(self, id):
        self.i2ctl.reset_i2c(id)
        # FIXME: fix assumption that only one bus is used!
        if id == I2C0_ID:
            self.oled   = OledI2c(self.i2ctl.i2c[I2C0_ID]["OBJ"], "FK Car")
            self.motors = MotorsI2c(self.i2ctl.i2c[I2C0_ID]["OBJ"])
        else:
            raise AppException("reset_i2c id %d not used" % id)

    # ########## OLED ##########
    def display(self):
        try:
            self.oled.show()
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
            self.oled.update_row3("IR: BADSTART")
            if MyApp.DEBUG:
                print("*** IR Error: BADSTART ({})".format(err))
        elif err == IR_RX.BADBLOCK:
            self.oled.update_row3("IR: BADBLOCK")
            if MyApp.DEBUG:
                print("*** IR Error: BADBLOCK ({})".format(err))
        elif err == IR_RX.BADREP:
            self.oled.update_row3("IR: BADREP")
            if MyApp.DEBUG:
                print("*** IR Error: BADREP ({})".format(err))
        elif err == IR_RX.OVERRUN:
            self.oled.update_row3("IR: OVERRUN")
            if MyApp.DEBUG:
                print("*** IR Error: OVERRUN ({})".format(err))
        elif err == IR_RX.BADDATA:
            self.oled.update_row3("IR: BADDATA")
            if MyApp.DEBUG:
                print("*** IR Error: BADDATA ({})".format(err))
        elif err == IR_RX.BADADDR:
            self.oled.update_row3("IR: BADADDR")
            if MyApp.DEBUG:
                print("*** IR Error: BADADDR ({})".format(err))
        else:
            self.oled.update_row3("IR: {}".format(err))
            if MyApp.DEBUG:
                print("*** IR Error: Unknown{}".format(err))

    def process_ir(self, cmd):
        try:
            if   cmd == IR_RX.number_up:
                if MyApp.DEBUG:
                    print("\t# IR cmd Up ... moving forward")
                self.motors.forward()
                # self.oled.update_row2("m1=Fwd, m2=Fwd")
            elif cmd == IR_RX.number_down:
                if MyApp.DEBUG:
                    print("\t# IR cmd Down ... moving backward")
                self.motors.backward()
                # self.oled.update_row2("m1=Bkwd, m2=Bkwd")
            elif cmd == IR_RX.number_left:
                if MyApp.DEBUG:
                    print("\t# IR cmd Left ... turning left")
                self.motors.turn_left()
                # self.oled.update_row2("m1=Bkwd, m2=Fwd")
            elif cmd == IR_RX.number_right:
                if MyApp.DEBUG:
                    print("\t# IR cmd Right ... turning right")
                self.motors.turn_right()
                # self.oled.update_row2("m1=Fwd, m2=Bkwd")
            elif cmd == IR_RX.number_ok:
                if MyApp.DEBUG:
                    print("\t# IR cmd OK ... stopping motors")
                self.motors.stop_motors()
                # self.oled.update_row2("m1=Stop, m2=Stop")
            elif cmd == IR_RX.REPEAT:
                if MyApp.DEBUG:
                    print("\t# IR cmd Repeat ... ignoring")
                self.oled.update_row3("IR Repeat code")
                # Handle repeat code ...
            elif cmd >= 0:
                if MyApp.DEBUG:
                    print('\t* IR cmd Err: Not implemented: 0x{:02x}'.format(cmd))
                self.oled.update_row3("IR cmd not Impl")
            else:
                if MyApp.DEBUG:
                    print('\t* IR cmd Err: Unrecognized error code: 0x{:02x}'.format(cmd))
                self.oled.update_row3("IR cmd error")
            
        except I2CException as e:
            if MyApp.DEBUG:
                print("\t** IR cmd, I2C exception, Motor, reset I2C: ", e)
            self.reset_i2c(I2C0_ID)

    def run_ir(self):
        # Called only if ir_rx is true, which means an IR message has been received and is ready to be processed.
        if not self._ir_rx:
            return
        
        if MyApp.DEBUG:
            print("# IR RX, ir_rx = {}, ir_cmd = 0x{:02x}".format(self._ir_rx, self._ir_cmd))

        self._ir_rx  = False
        code         = self._ir_cmd
        self._ir_cmd = 0

        try:
            self.process_ir(code)
            self.display()
        except AppException as e:
            if MyApp.DEBUG:
                print("** run_ir: ", e)
        except I2CException as e:
            if MyApp.DEBUG:
                print("** run_ir: IR RX, I2C Exception ignoring: ", e)
        except OSError as e:
            if MyApp.DEBUG:
                print("** run_ir: IR RX, OS error exception, ignoring: ", e)       

    # ########## Distance ##########
    def process_dist(self):
        dist = 0.0
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

        if self.DEBUG:
            print("Distance: %.2f ... %.2f\' %.2f\"" % (dist, dist // 12, dist % 12))
        self.last_dist = dist
        self.oled.update_row2("%.2f\' %.2f\"" % (dist // 12, dist % 12))
        self.oled.show()

        return dist

    def run_dist(self): 
        try:
            # Get distance
            t = ticks_ms()
            if ticks_diff(t, self.last_ticks) >= 1000:
                self.last_ticks = t
                dist = self.process_dist()
                if dist < 0:
                    print("run_dist: error from process_dist ... ignoring")
                elif dist < 12.0:
                    self.motors.backward()
                    self.buzzer.on()
                elif dist <= 24.0:
                    self.buzzer.off()
                    self.motors.stop_motors()
                    print("XXX Turning RIGHT")
                    self.motors.turn_right()
                    # sleep_us(5000)
                    # self.motors.stop_motors()
                else: # > 2'
                    self.buzzer.off()
                    self.motors.forward()
                    self.buzzer.off()
        except AppException as e:
            if MyApp.DEBUG:
                print("** run_ir: ", e)
        except Exception as e:
            print("FIXME RUN: dist exception: ", e)
            #self.shutdown()
            #raise e
        
    # ########## App ##########
    def run(self, mode):
        self.min_change = 1 # inch
        self.sonic.tout_us = 1_000_000

        if self.DEBUG:
            print("MyApp.run() ...")
            print("tout: ", self.sonic.tout_us)

        while True:
            try:
                if mode & MODE_DIST:
                    self.run_dist()

                if mode & MODE_IR:
                    self.run_ir()

            except KeyboardInterrupt:
                print("Keyboard interrupt ... exiting")
                raise
    
    def shutdown(self):
        self.motors.stop_motors()
        self.oled.clear()

#============================================================================

def main():
    myApp = MyApp()

    # check_motors()
    # sys.exit(1)
    try:
        myApp.run(MODE_DIST)
    except KeyboardInterrupt:
        print("Keyboard interrupt ... resetting")
        reset()
    except Exception as e:
        print("@@ Caught top level exception (main), resetting board: ", e)
        myApp.shutdown()
        # reset vs soft_reset() ... soft_reset() is not implemented in micropython for the Pico W
        # machine.reset will reset the Pico W and restart the program from the beginning.
        reset()
    
if __name__ == "__main__":
    main()