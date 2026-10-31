from machine import Pin, reset, enable_irq, disable_irq
from ir_sensor import NEC_8, IR_RX
from utime import sleep_ms, ticks_ms, ticks_us, ticks_diff, sleep
#from ssd1306 import SSD1306_I2C
from array import array
from common import Button, Pot, \
                    DEBUG_ERROR, DEBUG_INFO, DEBUG_NONE, DEBUG_VERB, DEBUG_WARN, \
                    IR_PIN, I2C0_ID
from i2c_dev import I2cCtl, OledI2c, I2cException
from distance import CarDist
from motor import CarMotors, \
                    MOTOR_CMD_FORWARD, MOTOR_CMD_LEFT, MOTOR_CMD_REVERSE, MOTOR_CMD_RIGHT, \
                    MOTOR_CMD_STOP, MOTOR_CMD_NOOP, MOTOR_CMD_STOP_FORCE

MODE_DIST = const( 1) # bin 0_0001, 0x01
MODE_IR   = const( 2) # bin 0_0010, 0x02
MODE_BUTT = const( 4) # bin 0_0100, 0x04
MODE_POT  = const( 8) # bin 0_1000, 0x08
MODE_BUZZ = const(16) # bin 1_0000, 0x10
MODE_MASK = const(0x001F)
# MODE_OLED = const(16) # bin 10_0000, 0x20
MODE_0 = (MODE_DIST | MODE_IR | MODE_BUTT | MODE_POT | MODE_BUZZ) & MODE_MASK
MODE_1 = (MODE_DIST |           MODE_BUTT | MODE_POT | MODE_BUZZ) & MODE_MASK
MODE_2 = (            MODE_IR | MODE_BUTT | MODE_POT | MODE_BUZZ) & MODE_MASK

_DEBUG     = DEBUG_WARN
_DST_DEBUG = DEBUG_WARN
_I2C_DEBUG = DEBUG_WARN
_MTR_DEBUG = DEBUG_WARN
_OLD_DEBUG = DEBUG_WARN
_IR_DEBUG  = DEBUG_WARN

PERF_ON = const(0)

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
        #self.turn_delay = TURN_DELAY_MS

        self.init_i2c_env() # need for motors and oled

        if self.mode & MODE_IR:
            self.init_ir_env()

        if self.mode & MODE_DIST:
            self.dist = CarDist(self.motors, self.oled, debug=_DST_DEBUG)
        else:
            self.dist = None

        if self.mode & MODE_BUTT:
            self.butt = Button()
        else:
            self.butt = None

        if self.mode & MODE_POT:
            self.pot  = Pot()
        else:
            self.pot = None

    #############################################################################
    # I2C 
    #############################################################################
    def init_i2c_env(self):
        # I2C errors and bus resets are handled by the bus, below this level
        self.i2ctl  = I2cCtl(debug=_I2C_DEBUG)
        bus         = self.i2ctl.bus(I2C0_ID)
        self.oled   = OledI2c(bus, "FK Car", debug=_OLD_DEBUG)
        self.motors = CarMotors(bus,
                                self.mode & MODE_BUZZ, 
                                debug=_MTR_DEBUG)

        if _I2C_DEBUG >= DEBUG_INFO:
            print("MyApp: I2C environment up")
            print("MyAPP: OLED ",  self.oled._octrl)
            print("MyAPP: Motors ",self.motors.mctrl)

    #############################################################################
    # OLED 
    #############################################################################
    def display(self):
        if _OLD_DEBUG >= DEBUG_VERB:
            print("MyApp.display")
        try:
            self.oled.show()
        except I2cException as e:
            # the bus has already retried and reset if needed
            if _OLD_DEBUG >= DEBUG_WARN:
                print("\tDisplay: I2C exception, OLED show: ", e)

    #############################################################################
    # IR
    #############################################################################
    def init_ir_env(self):
        self._ir_err_code = 0
        self._ir_cmd  = 0x00
        self._ir_rx   = False

        if self.mode & MODE_IR:
            self._ir_ctrl = NEC_8(Pin(IR_PIN, Pin.IN), self.ir_callback) # type: ignore
            self._ir_ctrl._errf = self.ir_err
                    # in __init__ / init_ir_env:
            self.ir_cmd_map = {
                # Command: function,
                IR_RX.number_up:    MOTOR_CMD_FORWARD,
                IR_RX.number_down:  MOTOR_CMD_REVERSE,
                IR_RX.number_left:  MOTOR_CMD_LEFT,
                IR_RX.number_right: MOTOR_CMD_RIGHT,
                IR_RX.number_ok:    MOTOR_CMD_STOP,
                IR_RX.REPEAT:       MOTOR_CMD_NOOP,
            } # no mapping for MOTOR_CMD_STOP_FORCE
        else:
            self._ir_ctrl = None

        if _IR_DEBUG >= DEBUG_INFO:
            print("MyApp : IR up: ", self._ir_ctrl)

    def ir_callback(self, cmd, addr, _):
        # An IR message has been received, ignore address.
        # FIXME: Add command queue
        self._ir_cmd = cmd
        self._ir_rx  = True
        if _IR_DEBUG >= DEBUG_VERB:
            print('# IR Callback -> Cmd: 0x{:02x} Addr: 0x{:04x}'.format(cmd, addr))

    def ir_err(self, code):
        self._ir_err_code = code

    def ir_ck_err_code(self):
        s = disable_irq()
        try:
            code = self._ir_err_code
            self._ir_err_code = 0
        finally:
            enable_irq(s)

        # Errors are < -1 (repeat cmd), a 0 means no errors
        if  code < IR_RX.REPEAT:
            try:
                if _IR_DEBUG >= DEBUG_ERROR:
                    print("IR Error: ", MyApp._IR_ERRS[code])
                self.oled.update_row3(MyApp._IR_ERRS[code])
            except KeyError:
                self.oled.update_row3("bad code")

    def process_ir(self, cmd):
        motor_cmd = self.ir_cmd_map[cmd]
        if motor_cmd is None:
            if _IR_DEBUG >= DEBUG_ERROR:
                print("process_ir: Invalid command ", cmd)
            self.oled.update_row3("Unknown IR cmd")
            return
        self.motors.add_cmd(motor_cmd)

    def run_ir(self):
        # Called only if ir_rx is true, which means an IR message has been received and is ready to be processed.

        # first see if there is a pending error code
        self.ir_ck_err_code()

        # Now see if there is a pending command
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
            # I2CExceptions & OSError are handled in process_ir
            self.process_ir(code) 
        except Exception as e:
            if _IR_DEBUG >= DEBUG_WARN:
                print("** run_ir: General exception, ignoring: ", e)

    #############################################################################
    # App
    #############################################################################
    def run(self):
        running  = 0
        diff_ms  = 0
        start_ms = 0

        while True:
            if PERF_ON: start_ms = ticks_ms()
            try:
                # ----------------------------------------------------------
                if self.mode & MODE_BUTT:
                    assert self.butt is not None
                    while not self.butt.enabled():
                        if running:
                            self.shutdown()
                            running = 0
                        sleep(0.5)

                running = 1

                # ----------------------------------------------------------
                if self.mode & MODE_POT:
                    assert self.pot is not None
                    self.motors.set_turn_ms(self.pot.get_value())

                # ----------------------------------------------------------
                if self.mode & MODE_DIST:
                    assert self.dist is not None
                    if PERF_ON: s = ticks_us()
                    self.dist.run()
                    if PERF_ON: d = ticks_diff(ticks_us(), s); print("\tRun dist time %dus" % d)

                # ----------------------------------------------------------
                if self.mode & MODE_IR:
                    self.run_ir()

                # ----------------------------------------------------------
                # Assume there are motor commands to process
                # either from IR, Dist or both
                if PERF_ON: s = ticks_us()
                self.motors.run_cmds()
                if PERF_ON: d = ticks_diff(ticks_us(), s); print("\tRun commands time %dus" % d)
                # ----------------------------------------------------------
                # Likewise assume there has been an update to the o
                # 
                # led buffer
                if PERF_ON: s = ticks_ms()
                self.display()
                if PERF_ON: d = ticks_diff(ticks_ms(), s); print("\tDisplay time %dms" % d)
            except KeyboardInterrupt:
                if _DEBUG >= DEBUG_INFO:
                    print("Keyboard interrupt ... exiting")
                raise
            except AppException:
                if _DEBUG >= DEBUG_ERROR:
                    print("run caught AppException - let it bubble up")
                raise
            except Exception as e:
                if _DEBUG >= DEBUG_WARN:
                    print("run caught exception, ignoring: ", e)

            if PERF_ON: diff_ms = ticks_diff(ticks_ms(), start_ms); print("--- Run loop time %dms\n" % diff_ms)
            if PERF_ON: sleep(0.5)

    def shutdown(self):
        self.motors.reset()
        if self.mode & MODE_DIST:
            assert self.dist is not None
            self.dist.reset()
        sleep_ms(1)
        self.oled.init_buf()
        # FIXME: self.display()
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