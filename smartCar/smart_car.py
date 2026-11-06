from machine import reset
from utime import sleep_ms, ticks_ms, ticks_us, ticks_diff, sleep
#from ssd1306 import SSD1306_I2C
from array import array
from common import Button, Pot, \
                    DEBUG_ERROR, DEBUG_INFO, DEBUG_NONE, DEBUG_VERB, DEBUG_WARN, \
                    I2C0_ID
from i2c_dev import I2cCtl, OledI2c, I2cException
from diag import Diag
from distance import CarDist
from ir import IRMgr
from motor import CarMotors

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

_DEBUG      = DEBUG_WARN
_DST_DEBUG  = DEBUG_WARN
_I2C_DEBUG  = DEBUG_WARN
_MTR_DEBUG  = DEBUG_WARN
_OLD_DEBUG  = DEBUG_WARN
_IR_DEBUG   = DEBUG_WARN
_DIAG_DEBUG = DEBUG_WARN

PERF_ON = const(0)

# The OLED is not needed to drive, so it must not hold up the loop: one
# try per write, at most one update per DISPLAY_MIN_WAIT_MS and none for
# DISPLAY_ERR_WAIT_MS after a failure
DISPLAY_MIN_WAIT_MS = const( 250)
DISPLAY_ERR_WAIT_MS = const(2000)

class AppException(Exception):
    pass

class MyApp():
    def __init__(self, mode):
        self.mode = mode
        #self.turn_delay = TURN_DELAY_MS

        self.init_i2c_env() # need for motors and oled

        if self.mode & MODE_IR:
            self.ir = IRMgr(self.motors, self.oled, debug=_IR_DEBUG)
        else:
            self.ir = None

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

        # IR shows its status on row 3, so only show vsys there without IR
        self.diag = Diag(self.oled, self.i2ctl, self.butt, self.motors.buzzer,
                         vsys_row=not (self.mode & MODE_IR), debug=_DIAG_DEBUG)

        # Devices are started in this order and stopped in reverse:
        # the motors are stopped after the inputs that queue commands for them
        self.devices = [d for d in (self.i2ctl, self.oled, self.motors, self.dist, self.ir)
                        if d is not None]

    #############################################################################
    # I2C 
    #############################################################################
    def init_i2c_env(self):
        # I2C errors and bus resets are handled by the bus, below this level
        self.i2ctl  = I2cCtl(debug=_I2C_DEBUG)
        bus         = self.i2ctl.bus(I2C0_ID)
        self.oled   = OledI2c(self.i2ctl.bus(I2C0_ID, tries=1), "FK Car", debug=_OLD_DEBUG)
        self.disp_ms   = ticks_ms() # last OLED update
        self.disp_wait = 0          # ms until the next one is allowed
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
        
        now = ticks_ms()
        if ticks_diff(now, self.disp_ms) < self.disp_wait:
            return
        self.disp_ms   = now
        self.disp_wait = DISPLAY_MIN_WAIT_MS
        try:
            self.oled.show()
        except I2cException as e:
            # the bus resets itself if needed, the buffer is still marked
            # updated so the next show() redraws it
            self.disp_wait = DISPLAY_ERR_WAIT_MS
            if _OLD_DEBUG >= DEBUG_WARN:
                print("\tDisplay: I2C exception, OLED show: ", e)

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
                            try:
                                self.stop()
                                running = 0
                            except I2cException as e:
                                # The motors may still be running. Keep
                                # trying, with the display and diagnostics
                                # still updated below.
                                self.diag.exception(e)
                        # keep the diagnostics up while stopped
                        self.diag.run(running=False)
                        self.display()
                        sleep(0.5)

                if not running:
                    self.start()
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
                    assert self.ir is not None
                    if PERF_ON: s = ticks_us()
                    self.ir.run()
                    if PERF_ON: d = ticks_diff(ticks_us(), s); print("\tRun ir time %dus" % d)

                # ----------------------------------------------------------
                # Assume there could be motor commands to process
                # either from IR, Dist or both
                if PERF_ON: s = ticks_us()
                self.motors.run_cmds()
                if PERF_ON: d = ticks_diff(ticks_us(), s); print("\tRun commands time %dus" % d)
                
                # ----------------------------------------------------------
                # Likewise assume there has been an update to the oled buffer, so show it. 
                # The OLED is not needed to drive, so it must not hold up the loop
                self.diag.run()
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
                self.diag.exception(e)

            if PERF_ON: diff_ms = ticks_diff(ticks_ms(), start_ms); print("--- Run loop time %dms\n" % diff_ms)
            if PERF_ON: sleep(0.5)

    def start(self):
        # start() is a no-op for a device that is already on, so if one
        # raises the next call only retries the ones that did not start
        for d in self.devices:
            d.start()
        self.diag.log("running")

    def stop(self):
        # stop() is a no-op for a device that is already off
        for d in reversed(self.devices):
            try:
                d.stop()
            except:
                pass
        self.diag.log("stopped")

    def shutdown(self):
        try:
            self.display()
        except:
            pass
        self.stop()
        # XXX: self.motors.add_cmd
        self.diag.log("shutting down")

        

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