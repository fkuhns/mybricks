import os
import sys
from machine import Pin, ADC, Timer
from utime import ticks_ms, ticks_diff
from common import DEBUG_ERROR, DEBUG_INFO, DEBUG_NONE, DEBUG_VERB, DEBUG_WARN

## Diagnostics for running on battery with no USB, so print() goes nowhere.
# Counts problems, shows them on the OLED and appends them to a log file on
# flash that survives a reset. Read it later with USB connected, e.g.
#   mpremote cat errors.log
# OLED rows, updated every DIAG_UPDATE_MS:
#   Row 3: V<vsys now> m<vsys min> T<ok|-->   T-- = heartbeat timer stopped
#   Row 4: E<app exceptions> I<failed I2C writes> R<bus resets> T<timer.init errors>
# vsys is the Pico's supply. On the PicoBricks board that is a ~5V rail
# boosted from the battery, so it is not the battery voltage.

DIAG_LOG_FILE  = "errors.log"
DIAG_LOG_OLD   = "errors.old"
DIAG_LOG_MAX   = const(100)  # lines logged per boot, limits flash writes
DIAG_LOG_SIZE  = const(8192) # bytes, a bigger log is moved to DIAG_LOG_OLD at boot
DIAG_UPDATE_MS = const(1000) # OLED refresh and heartbeat check
DIAG_COUNT_MS  = const(10_000) # log changed counters at most this often
DIAG_BEAT_MS   = const(100)  # heartbeat timer period
DIAG_VMIN_STEP = 0.1         # log the min vsys each time it drops this much

VSYS_ADC = const(3) # ADC3 = GPIO29 = VSYS/3

class Diag():
    def __init__(self, oled, i2ctl, butt=None, buzz=None, vsys_row=True, debug=0):
        # vsys_row: False if row 3 is used by someone else (IR status)
        self.DEBUG    = debug
        self.oled     = oled
        self.i2ctl    = i2ctl
        self.butt     = butt
        self.buzz     = buzz
        self.vsys_row = vsys_row

        self.exc_cnt  = 0    # exceptions caught by the app loop
        self.last_exc = None # text of the last one logged, repeats are not logged
        self.log_cnt  = 0
        self.counts   = None # last counters logged
        self.count_ms = ticks_ms()
        self.vmin     = 99.0
        self.vmin_log = 99.0 # vmin when last logged
        self.upd_ms   = ticks_ms()
        self.prev_ms  = self.upd_ms # last run() call
        self.loop_max = 0           # longest time between run() calls while running

        # only log to flash on the board, not in the simulator
        self.to_file = sys.implementation.name == "micropython"
        # On a Pico W GPIO29 is shared with the wireless chip, see vsys()
        self.pico_w  = "Pico W" in getattr(sys.implementation, "_machine", "")

        self._rotate()
        self.log("boot, reset cause %s" % self._reset_cause())

        # Heartbeat, a periodic timer so it never calls init() again. If the
        # count stops the timers have stopped.
        self.beats      = 0
        self.last_beats = -1
        self.beat_ok    = True
        self.timer      = Timer(-1)
        try:
            self.timer.init(mode=Timer.PERIODIC, period=DIAG_BEAT_MS, callback=self._beat)
        except OSError as e:
            self.log("heartbeat timer.init: %r" % e)

    def _beat(self, _):
        self.beats += 1

    def _reset_cause(self):
        try:
            from machine import reset_cause
            return reset_cause()
        except Exception:
            return "?"

    def _rotate(self):
        if not self.to_file:
            return
        try:
            if os.stat(DIAG_LOG_FILE)[6] < DIAG_LOG_SIZE:
                return
            try:
                os.remove(DIAG_LOG_OLD)
            except OSError:
                pass
            os.rename(DIAG_LOG_FILE, DIAG_LOG_OLD)
        except OSError:
            pass # no log yet

    def log(self, msg):
        # Note, a flash write can stall the loop for a few ms
        if self.DEBUG >= DEBUG_WARN:
            print("Diag:", msg)
        if not self.to_file or self.log_cnt >= DIAG_LOG_MAX:
            return
        self.log_cnt += 1
        try:
            with open(DIAG_LOG_FILE, "a") as f:
                f.write("%d %s\n" % (ticks_ms(), msg))
                if self.log_cnt == DIAG_LOG_MAX:
                    f.write("... log full\n")
        except OSError:
            pass

    def exception(self, e):
        # called for each exception the app loop catches and ignores
        self.exc_cnt += 1
        msg = "%s: %s" % (type(e).__name__, e)
        if msg != self.last_exc:
            self.last_exc = msg
            self.log(msg)

    def vsys(self):
        # Returns the supply voltage, -1.0 if it could not be read.
        # On a Pico W GPIO29 is also the wireless chip's SPI clock and GPIO25
        # its chip select, so take them over for the read then give GPIO29
        # back. Fine since the wireless is not used.
        try:
            if self.pico_w:
                Pin(25, Pin.OUT, value=1)
                Pin(29, Pin.IN, pull=None)
            v = ADC(VSYS_ADC).read_u16() * 3 * 3.3 / 65535
            if self.pico_w:
                Pin(29, Pin.ALT, pull=Pin.PULL_DOWN, alt=7)
            return v
        except Exception:
            return -1.0

    def run(self, running=True):
        # Call every loop, the min vsys is sampled each call so it catches
        # the dips when the motors start or reverse. running is False while
        # the app waits for the button, those loops sleep so are not timed.
        now = ticks_ms()
        if running and self.prev_ms is not None:
            self.loop_max = max(self.loop_max, ticks_diff(now, self.prev_ms))
        # None while stopped, so the first running loop does not time the sleep
        self.prev_ms = now if running else None

        v = self.vsys()
        if 0 < v < self.vmin:
            self.vmin = v
            if self.vmin_log - v >= DIAG_VMIN_STEP:
                self.vmin_log = v
                self.log("vsys min %.2f" % v)

        if ticks_diff(now, self.upd_ms) < DIAG_UPDATE_MS:
            return
        self.upd_ms = now

        beats = self.beats
        if beats == self.last_beats:
            if self.beat_ok:
                self.beat_ok = False
                self.log("heartbeat timer stopped")
        elif not self.beat_ok:
            self.beat_ok = True
            self.log("heartbeat timer running again")
        self.last_beats = beats

        tmr = (self.butt.err_cnt if self.butt else 0) + (self.buzz.err_cnt if self.buzz else 0)
        counts = (self.exc_cnt, self.i2ctl.fail_cnt, self.i2ctl.reset_cnt, tmr)
        if counts != self.counts and ticks_diff(now, self.count_ms) >= DIAG_COUNT_MS:
            self.counts   = counts
            self.count_ms = now
            # I2C failures by "addr:kind", 22 = motors, 3c = OLED
            # L = longest loop in ms since the last counts line
            fails = " ".join("%s=%d" % (k, self.i2ctl.fails[k]) for k in sorted(self.i2ctl.fails))
            self.log("counts E%d I%d R%d T%d L%d %s" % (counts + (self.loop_max, fails)))
            self.loop_max = 0

        if self.vsys_row:
            self.oled.update_row3("V%.2f m%.2f T%s" % (v, self.vmin, "ok" if self.beat_ok else "--"))
        self.oled.update_row4("E%d I%d R%d T%d" % tuple(min(c, 99) for c in counts))
