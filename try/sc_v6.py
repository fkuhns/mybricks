from machine import Pin, reset, enable_irq, disable_irq
from ir_sensor import NEC_8, IR_RX
from utime import sleep_ms, ticks_ms, ticks_diff, ticks_add, sleep
#from ssd1306 import SSD1306_I2C
from array import array
from common import Button, Pot
from usonic import UltrasonicSensor, UltraSonicTimeout
from i2c_dev import I2cCtl, CarMotors, OledI2c, I2CException

MODE_DIST = const( 1) # bin 0_0001, 0x01
MODE_IR   = const( 2) # bin 0_0010, 0x02
MODE_BUTT = const( 4) # bin 0_0100, 0x04
MODE_POT  = const( 8) # bin 0_1000, 0x08
MODE_BUZZ = const(16) # bin 1_0000, 0x10
# MODE_OLED = const(16) # bin 10_0000, 0x20
MODE_1 = (MODE_DIST | MODE_BUTT | MODE_POT | MODE_BUZZ) & 0x001F
MODE_2 = (MODE_IR   | MODE_BUTT | MODE_POT | MODE_BUZZ) & 0x001F

I2C0_ID       = 0
IR_PIN        = 0

DIST_MIN_CHANGE  = 1 # inches
DIST_INTERVAL_MS = 1000 # FIXME:100 # HC-SR04 needs >= 60ms between pings

TURN_DELAY_MS    = 500 # FIXME: default turn time when the pot is not used

_DEBUG = const(1)

class AppException(Exception):
    pass

class MyApp():
    _IR_ERRS = {IR_RX.BADSTART: "BADSTART", 
                IR_RX.BADBLOCK: "BADBLOCK",
                IR_RX.BADREP:   "BADREP",
                IR_RX.OVERRUN:  "OVERRUN",
                IR_RX.BADDATA:  "BADDATA",
                IR_RX.BADADDR:  "BADADDR"}

    def __init__(self, mode):
        self.mode = mode
        self.turn_delay = TURN_DELAY_MS

        self.init_i2c_env()
        self.init_ir_env()
        self.init_dist()
        
        if self.mode & MODE_BUTT:
            self.butt = Button()
        else:
            self.butt = None

        if self.mode & MODE_POT:
            self.pot  = Pot()
        else:
            self.pot = None

    # ########## I2C ##########
    def init_i2c_env(self):
        self.i2ctl  = I2cCtl(debug=0)
        self.oled   = OledI2c(self.i2ctl._i2c[I2C0_ID]["OBJ"], "FK Car", debug=0)
        self.motors = CarMotors(self.i2ctl._i2c[I2C0_ID]["OBJ"],
                                self.mode & MODE_BUZZ, 
                                debug=0)

        if _DEBUG:
            print("MyApp: I2C environment up")
            print("MyAPP: OLED ",  self.oled._octrl)
            print("MyAPP: Motors ",self.motors._mctrl)

    def i2c_error(self, id=I2C0_ID):
        # throws AppException
        if id != I2C0_ID:
            # FIXME: fix assumption that only one bus is used!
            raise AppException("i2c_reset id %d not used" % id)

        old_i2c = self.i2ctl.i2c(id)

        new_i2c = self.i2ctl.handle_err(id)
        if not new_i2c:
            return

        # motors first: OLED rebind talks to the device and may raise OSError
        try:
            if not self.motors.rebind(new_i2c):
                # can not update motors so stay on the old i2c bus
                return
        except Exception as e:
            if _DEBUG:
                print("i2c_error: exception rebinding motors!")
            self.i2ctl.set_i2c(id, old_i2c)
            return 
        
        try:
            self.oled.rebind(new_i2c) # rebind doesn't raise exceptions
        except Exception as e:
            if _DEBUG:
                print("i2c_error: exception rebinding oled!")
            self.i2ctl.set_i2c(id, old_i2c)
            self.motors.rebind(old_i2c)

        if _DEBUG:
            print("MyApp.i2c_reset: I2C ", new_i2c)
            print("MyAPP.i2c_reset: OLED ",  self.oled._octrl)
            print("MyAPP.i2c_reset: Motors ",self.motors._mctrl)

    # ########## OLED ##########
    def display(self):
        # throws AppException from i2c_reset
        try:
            self.oled.show()
        except I2CException as e:
            if _DEBUG:
                print("\tDisplay: I2C exception, OLED show, reset I2C: ", e)
            self.i2c_error()

    # ########## IR ##########
    def init_ir_env(self):
        self._ir_err_code = 0
        self._ir_cmd  = 0x00
        self._ir_rx   = False

        if self.mode & MODE_IR:
            self._ir_ctrl = NEC_8(Pin(IR_PIN, Pin.IN), self.ir_callback) # type: ignore
            self._ir_ctrl._errf = self.ir_err
                    # in __init__ / init_ir_env:
            self._ir_actions = {
                # Command: function,
                IR_RX.number_up:    lambda: self.motors.forward(),
                IR_RX.number_down:  lambda: self.motors.backward(),
                IR_RX.number_left:  lambda: self.motors.turn_left(),
                IR_RX.number_right: lambda: self.motors.turn_right(),
                IR_RX.number_ok:    lambda: self.motors.stop_motors(),
                IR_RX.REPEAT:       lambda: self.motors.repeat(),
            }
        else:
            self._ir_ctrl = None
            self._ir_actions = {
                # Command: function,
                IR_RX.number_up:    lambda: None,
                IR_RX.number_down:  lambda: None,
                IR_RX.number_left:  lambda: None,
                IR_RX.number_right: lambda: None,
                IR_RX.number_ok:    lambda: None,
                IR_RX.REPEAT:       lambda: None,
            }

        if _DEBUG:
            print("MyApp : IR up: ", self._ir_ctrl)

    def ir_callback(self, cmd, addr, _):
        # An IR message has been received, ignore address.
        # FIXME: Add command queue
        self._ir_cmd = cmd
        self._ir_rx  = True
        if _DEBUG:
            print('# IR Callback -> Cmd: 0x{:02x} Addr: 0x{:04x}'.format(cmd, addr))

    def ir_err(self, code):
        self._ir_err_code = code

    def ir_ck_code(self):
        s = disable_irq()
        try:
            code = self._ir_err_code
            self._ir_err_code = 0
        finally:
            enable_irq(s)

        # Errors are < -1 (repeat cmd), a 0 means no errors
        if  code < IR_RX.REPEAT:
            try:
                if _DEBUG:
                    print("IR Error: ", MyApp._IR_ERRS[code])
                self.oled.update_row3(MyApp._IR_ERRS[code])
            except KeyError:
                self.oled.update_row3("bad code")

    def _motor(self, fn):
        # Helper for updating drive state, raises AppException
        if _DEBUG:
            print("Set motors: before: ", self.motors)
        try:
            fn()
        except I2CException as e:
            if _DEBUG:
                print("\t** motor I2C exception, reset I2C: \n\t", e)
                print(self.motors)
            self.i2c_error()
        if _DEBUG:
            print("\tSet motors  after: ", self.motors)

    def process_ir(self, cmd):
        # throws AppException from i2c_reset
        action = self._ir_actions.get(cmd)
        if action is None:
            if _DEBUG:
                print("process_ir: Invalid command ", cmd)
            self.oled.update_row3("IR cmd error")
            return

        self._motor(action)

    def run_ir(self):
        # throws AppException from i2c_reset in process_ir and display
        # Called only if ir_rx is true, which means an IR message has been received and is ready to be processed.

        # check for IR commands that cause errors
        self.ir_ck_code()

        # check for valid commands
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
        except AppException:
            raise
        except Exception as e:
            if _DEBUG:
                print("** run_ir: General exception, ignoring: ", e)

    # ########## Distance ##########
    def init_dist(self):
        if self.mode & MODE_DIST:
            self.sonic = UltrasonicSensor()
        else:
            self.sonic = None

        self.dist_min_change = DIST_MIN_CHANGE
        self.dist_last       = -1
        self.dist_ticks_last =  0
        self.turn_end        = None # ticks_ms deadline while turning, else None

        if _DEBUG:
            if self.mode & MODE_DIST:
                print("MyApp: Distance env up")
            else:
                print("Myapp: Distance environment not initialized")

    def process_dist(self):
        # throws AppException from i2c_reset
        try:
            # throws Ultrasonic exception for timeouts or other errors
            assert self.sonic is not None
            dist = self.sonic.get_distance() # distance in inches
        except UltraSonicTimeout:
            if _DEBUG:
                print("process_dist: echo not received in timeout")
            # only redraw on the first timeout in a row
            if self.dist_last != -1:
                self.dist_last = -1
                self.oled.update_row2("Dist: --")
                self.display()
            return -1.0

        if abs(dist - self.dist_last) < self.dist_min_change:
            return dist

        # if _DEBUG:
        #     print("process_dist dist = %.2f ... %.2f\' %.2f\"" % (dist, dist // 12, dist % 12))

        self.dist_last = dist
        
        self.oled.update_row2("%d\' %.2f\"" % (dist // 12, dist % 12))
        self.display()

        return dist

    def run_dist(self): 
        # throws AppException from i2c_reset & process_dist
        # Only runs if MODE_DIST is set
        t = ticks_ms()

        # Non-blocking turn: keep turning until the deadline, then stop
        # and take a fresh reading right away.
        if self.turn_end is not None:
            if ticks_diff(t, self.turn_end) < 0:
                return
            self.turn_end = None
            self._motor(self.motors.stop_motors)
            self.dist_ticks_last = t # FIXME: ticks_add(t, -DIST_INTERVAL_MS)

        # Get distance
        if ticks_diff(t, self.dist_ticks_last) < DIST_INTERVAL_MS:
            return
        
        self.dist_ticks_last = t
        dist = self.process_dist() # AppException
        if dist < 0:
            if _DEBUG:
                print("\trun_dist: unknown distance, timeout: ", dist)
            # FIXME: better would be checking previous distance to determine likelihood
            # that the timeout means "infinite"
            self._motor(self.motors.stop_motors)

        elif dist > 24.0:
            self._motor(self.motors.forward)

        elif dist < 12.0:
            self._motor(self.motors.backward)

        else:
            if _DEBUG:
                print("Turn delay = ", self.turn_delay, "ms")
            self._motor(self.motors.turn_left)
            self.turn_end = ticks_add(t, self.turn_delay)
        
    # ########## App ##########
    def run(self):
        running = 0
        while True:
            try:
                if self.mode & MODE_BUTT:
                    assert self.butt is not None
                    while not self.butt.enabled():
                        if running:
                            self.shutdown()
                            running = 0
                        # recheck every half second
                        sleep_ms(500)

                running = 1

                if self.mode & MODE_POT:
                    assert self.pot is not None
                    self.turn_delay = self.pot.get_value()

                if self.mode & MODE_DIST:
                    self.run_dist()

                if self.mode & MODE_IR:
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
        # throws AppException from i2c_reset
        self._motor(self.motors.stop_force)
        if self.mode & MODE_DIST:
            self.dist_last = -1
            self.turn_end  = None
        sleep_ms(1)
        self.oled.init_buf()
        self.display()
        #self.oled.clear()

#============================================================================

def main():

    try:
        myApp = MyApp(MODE_1)
    except Exception as e:
        print("Creating app raised an exception, reset board: ", e)
        reset()

    try:
        myApp.run()
    except KeyboardInterrupt:
        print("Keyboard interrupt ... resetting")
    except Exception as e:
        print("Caught top level exception (main), resetting board: ", e)
    
    try:
        print("Running myapp.shutdown()")
        myApp.shutdown()
    except:
        pass

    # reset vs soft_reset() ... soft_reset() is not implemented in micropython for the Pico W
    # machine.reset will reset the Pico W and restart the program from the beginning.
    print("Reset")
    sleep(1)
    reset()
    
if __name__ == "__main__":
    main()