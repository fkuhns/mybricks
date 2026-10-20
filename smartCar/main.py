from machine import Pin, I2C, reset, enable_irq, disable_irq
from ir_sensor import NEC_8, IR_RX
from utime import sleep_ms, sleep_us, ticks_ms, ticks_diff #, ticks_us
#from ssd1306 import SSD1306_I2C
from usonic import UltrasonicSensor, UltraSonicTimeout
from i2c_dev import I2cCtl, MotorsI2c, OledI2c, I2CException, MOTOR_STATE_BKWD, MOTOR_STATE_FWD, MOTOR_STATE_LEFT, MOTOR_STATE_RIGHT, MOTOR_STATE_STOP, MOTOR_STATE_INIT, MOTOR_STATE_UNK

MODE_DIST = const(1)  # bin 0001
MODE_IR   = const(2)  # bin 0010

I2C0_ID       = 0
I2C0_SDA_PIN  = 4
I2C0_SCL_PIN  = 5

I2C1_ID       = 1
I2C1_SDA_PIN  = 2
I2C1_SCL_PIN  = 3

IR_PIN = 0

DIST_MIN_CHANGE  = 1 # inches
DIST_INTERVAL_MS = 1_000

_DEBUG = const(0)

class AppException(Exception):
    pass

class MyApp():

    def __init__(self):
        self.init_i2c_env()
        self.init_ir_env()
        self.init_dist()

    # ########## I2C ##########
    def init_i2c_env(self):
        self.i2ctl  = I2cCtl()
        self.oled   = OledI2c(self.i2ctl.i2c[I2C0_ID]["OBJ"], "FK Car")
        self.motors = MotorsI2c(self.i2ctl.i2c[I2C0_ID]["OBJ"])

        if _DEBUG:
            print("MyApp: I2C environment up")
            print("MyAPP: OLED ",  self.oled.octrl)
            print("MyAPP: Motors ",self.motors._mctrl)

    def i2c_reset(self, id=I2C0_ID):
        # throws AppException
        if id != I2C0_ID:
            # FIXME: fix assumption that only one bus is used!
            raise AppException("i2c_reset id %d not used" % id)
        
        i2c = self.i2ctl.reset_i2c(id)
        
        self.oled   = OledI2c(i2c, "FK Car")
        self.motors = MotorsI2c(i2c)

    # ########## OLED ##########
    def display(self):
        # throws AppException from i2c_reset
        try:
            self.oled.show()
        except I2CException as e:
            if _DEBUG:
                print("\tDisplay: I2C exception, OLED show, reset I2C: ", e)
            self.i2c_reset()

    # ########## IR ##########
    def init_ir_env(self):
        self._ir_cmd  = 0x00
        self._ir_rx   = False
        self._ir_ctrl = NEC_8(Pin(IR_PIN, Pin.IN), self.ir_callback) # type: ignore
        self._ir_ctrl._errf = self.ir_err
        if _DEBUG:
            print("** MyApp: IR up: ", self._ir_ctrl)

    def ir_callback(self, cmd, addr, _):
        # An IR message has been received, ignore address.
        self._ir_cmd = cmd
        self._ir_rx  = True
        if _DEBUG:
            print('# IR Callback -> Cmd: 0x{:02x} Addr: 0x{:04x}'.format(cmd, addr))

    def ir_err(self, err):
        if err == IR_RX.BADSTART:
            self.oled.update_row3("IR: BADSTART")
            if _DEBUG:
                print("*** IR Error: BADSTART ({})".format(err))
        elif err == IR_RX.BADBLOCK:
            self.oled.update_row3("IR: BADBLOCK")
            if _DEBUG:
                print("*** IR Error: BADBLOCK ({})".format(err))
        elif err == IR_RX.BADREP:
            self.oled.update_row3("IR: BADREP")
            if _DEBUG:
                print("*** IR Error: BADREP ({})".format(err))
        elif err == IR_RX.OVERRUN:
            self.oled.update_row3("IR: OVERRUN")
            if _DEBUG:
                print("*** IR Error: OVERRUN ({})".format(err))
        elif err == IR_RX.BADDATA:
            self.oled.update_row3("IR: BADDATA")
            if _DEBUG:
                print("*** IR Error: BADDATA ({})".format(err))
        elif err == IR_RX.BADADDR:
            self.oled.update_row3("IR: BADADDR")
            if _DEBUG:
                print("*** IR Error: BADADDR ({})".format(err))
        else:
            self.oled.update_row3("IR: {}".format(err))
            if _DEBUG:
                print("*** IR Error: Unknown{}".format(err))

    def process_ir(self, cmd):
        # throws AppException from i2c_reset
        if   cmd == IR_RX.number_up:
            if _DEBUG:
                print("\t# IR cmd Up ... moving forward")
            try:
                self.motors.forward()
            except I2CException as e:
                if _DEBUG:
                    print("\t** IR cmd, forward, I2C exception, reset I2C: ", e)
                self.i2c_reset()

        elif cmd == IR_RX.number_down:
            if _DEBUG:
                print("\t# IR cmd Down ... moving backward")
            try:
                self.motors.backward()
            except I2CException as e:
                if _DEBUG:
                    print("\t** IR cmd, backward, I2C exception, reset I2C: ", e)
                self.i2c_reset()

        elif cmd == IR_RX.number_left:
            if _DEBUG:
                print("\t# IR cmd Left ... turning left")
            try:
                self.motors.turn_left()
            except I2CException as e:
                if _DEBUG:
                    print("\t** IR cmd, left, I2C exception, reset I2C: ", e)
                self.i2c_reset()

        elif cmd == IR_RX.number_right:
            if _DEBUG:
                print("\t# IR cmd Right ... turning right")
            try:
                self.motors.turn_right()
            except I2CException as e:
                if _DEBUG:
                    print("\t** IR cmd, right, I2C exception, reset I2C: ", e)
                self.i2c_reset()

        elif cmd == IR_RX.number_ok:
            if _DEBUG:
                print("\t# IR cmd OK ... stopping motors")
            try:
                self.motors.stop_motors()
            except I2CException as e:
                if _DEBUG:
                    print("\t** IR cmd, stop, I2C exception, reset I2C: ", e)
                self.i2c_reset()

        elif cmd == IR_RX.REPEAT:
            # FIXME: Handle repeat code ...
            if _DEBUG:
                print("\t# IR cmd Repeat ... ignoring")
            self.oled.update_row3("IR Repeat code")
            
        elif cmd >= 0:
            if _DEBUG:
                print('\t* IR cmd: Not implemented: 0x{:02x}'.format(cmd))
            self.oled.update_row3("IR cmd not Impl")
            
        else:
            if _DEBUG:
                print('\t* IR cmd Err: Unrecognized error code: 0x{:02x}'.format(cmd))
            self.oled.update_row3("IR cmd error")

        return

    def run_ir(self):
        # throws AppException from i2c_reset in process_ir and display
        # Called only if ir_rx is true, which means an IR message has been received and is ready to be processed.
        if not self._ir_rx:
            return

        s = disable_irq()
        try:
            # critical section
            self._ir_rx  = False
            code         = self._ir_cmd
            self._ir_cmd = 0
        finally:
            enable_irq(s)

        try:
            self.process_ir(code) # throws AppException from i2c_reset
            self.display() # throws AppException from i2c_reset
        # I2CExceptions & OSError are handled in process_ir and display
        except AppException as e:
            raise
        except Exception as e:
            if _DEBUG:
                print("** run_ir: General exception, ignoring: ", e)

    # ########## Distance ##########
    def init_dist(self):
        self.sonic = UltrasonicSensor()
        self.dist_min_change = DIST_MIN_CHANGE
        self.dist_last       = -1
        self.dist_ticks_last =  0
        #self.sonic.tout_us = 1_000_000

    def process_dist(self):
        # throws AppException from i2c_reset
        dist = 0.0
        try:
            # throws Ultrasonic exception for timeouts or other errors
            dist = self.sonic.get_distance() # distance in inches
        except UltraSonicTimeout:
            if _DEBUG:
                print("process_dist: echo not received in timeout")
            return -1.0

        if abs(dist - self.dist_last) < self.dist_min_change:
            return dist

        if _DEBUG:
            print("process_dist dist = %.2f ... %.2f\' %.2f\"" % (dist, dist // 12, dist % 12))

        self.dist_last = dist
        
        self.oled.update_row2("%.2f\' %.2f\"" % (dist // 12, dist % 12))
        self.display()

        return dist

    def run_dist(self): 
        # throws AppException from i2c_reset & process_dist
        # Get distance
        t = ticks_ms()
        if ticks_diff(t, self.dist_ticks_last) >= DIST_INTERVAL_MS:
            self.dist_ticks_last = t
            
            dist = self.process_dist() # AppException
            if dist < 0 or dist > 24.0:
                # FIXME: Assume <0 means the distance is > max dist.
                try:
                    self.motors.forward()
                except I2CException as e:
                    if _DEBUG:
                        print("\t** run_dist, forward, I2C exception, reset I2C: ", e)
                    self.i2c_reset()

            elif dist < 12.0:
                try:
                    self.motors.backward()
                except I2CException as e:
                    if _DEBUG:
                        print("\t** run_dist, backward, I2C exception, reset I2C: ", e)
                    self.i2c_reset()
            else:
                try:
                    self.motors.turn_left()
                    sleep_ms(500)
                    self.motors.stop_motors()
                except I2CException as e:
                    if _DEBUG:
                        print("\t** run_dist, left ... stop, I2C exception, reset I2C: ", e)
                    self.i2c_reset()
        
    # ########## App ##########
    def run(self, mode):

        while True:
            try:
                if mode & MODE_DIST:
                    self.run_dist()

                if mode & MODE_IR:
                    self.run_ir()

            except KeyboardInterrupt:
                if _DEBUG:
                    print("Keyboard interrupt ... exiting")
                raise
            except AppException:
                if _DEBUG:
                    print("run caught AppException - let it bubble up")
                raise
            except Exception as e:
                if _DEBUG:
                    print("run caught exception, ignoring: ", e)

    def shutdown(self):
        sleep_ms(1)
        self.motors.stop_force()
        sleep_ms(1)
        self.oled.clear()

#============================================================================

def main():
    myApp = MyApp()

    try:
        myApp.run(MODE_DIST)
    except KeyboardInterrupt:
        print("Keyboard interrupt ... resetting")
    except Exception as e:
        print("@@ Caught top level exception (main), resetting board: ", e)
    finally:
        myApp.shutdown()
        # reset vs soft_reset() ... soft_reset() is not implemented in micropython for the Pico W
        # machine.reset will reset the Pico W and restart the program from the beginning.
        reset()
    
if __name__ == "__main__":
    main()