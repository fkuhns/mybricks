from machine import Pin, I2C
#from picobricks import MotorDriver
from utime import sleep_ms, sleep_us, ticks_diff, ticks_ms
from ssd1306 import SSD1306_I2C
from buzzer import Buzzer
from common import I2C0_ID, I2C0_SDA_PIN, I2C0_SCL_PIN, \
                   I2C1_ID, I2C1_SDA_PIN, I2C1_SCL_PIN, \
                   Device, I2C_ADDR_OLED, I2C_ADDR_MOTOR, \
                   DEBUG_ERROR, DEBUG_INFO, DEBUG_NONE, DEBUG_VERB, DEBUG_WARN

I2C0_FREQ  = 400_000 # hz
I2C1_FREQ  = 100_000 # hz
I2C0_TOUT  = 100_000 # us
I2C1_TOUT  = 250_000 # us

I2C_ERROR_WINDOW_MS = 60_000

I2C_MAX_TRIES = 3

class I2cException(Exception):
    pass

class I2cBusException(I2cException):
    pass

class I2cNackException(I2cException):
    pass

class I2cBus():
    # What devices hold instead of a machine.I2C object. Retries failed
    # writes and reports each failure to I2cCtl, which may reset the bus.
    # A reset only swaps the machine.I2C object inside I2cCtl, so devices
    # never need to rebind. Raises I2CException when all tries fail.
    # Assumes only 7-bit addresses are supported. So for a write there 
    # should be 1 ack for the address frame and N ack's for the N data frames
    # Although the I2C.writeto method only returns the number of data Bytes ack'ed
    def __init__(self, ctl, id=I2C0_ID, tries=I2C_MAX_TRIES):
        self._ctl   = ctl
        self._id    = id
        self._tries = tries # each failed try can block for up to I2C_TOUT

    def __str__(self):
        return "I2cBus {}: {}".format(self._id, self._ctl.i2c(self._id))

    def _write(self, fname, addr, buf):
        assert fname != None

        last_error = None
        acks    = 0
        exp_ack = 0
        if fname == "writeto":
            exp_ack = len(buf)
        else:
            exp_ack = sum(len(x) for x in buf)

        for i in range(self._tries):
            try:
                acks = getattr(self._ctl.i2c(self._id), fname)(addr, buf)
                if acks == exp_ack:
                    self._ctl.clear_err(self._id)
                    if self._ctl.DEBUG >= DEBUG_VERB:
                        print("I2cBus.%s ack %d == expected %d - success"% (fname, acks, exp_ack))
                    return True

                # acks != exp_ack
                last_error = None # this try was a NACK, not an OSError
                if self._ctl.DEBUG >= DEBUG_INFO:
                    print("I2cBus.%s try %d NACK: ack %d != expected %d" % (fname, i, acks, exp_ack))

                sleep_us(500) # arbitrary delay to give the slave time to recover

            except OSError as e:
                last_error = e
                if self._ctl.DEBUG >= DEBUG_INFO:
                    print("I2cBus.{} 0x{:02x} try {} OSError: {}".format(fname, addr, i, e))
                self._ctl.handle_err(self._id) # FIXME: Move outside of loop
        # end of for loop
        # report whatever the last error was
        # kind is "nack" or the OSError errno, 5 = EIO, 110 = ETIMEDOUT
        kind = "nack" if last_error is None else last_error.args[0]
        self._ctl.count_fail(addr, kind)
        if last_error is None:
            raise I2cNackException("I2cBus.%s I2cNackException addr 0x%02x failed, RX acks %d != expected %d"
                                    % (fname, addr, acks, exp_ack))
        # else
        raise I2cBusException("I2cBus.%s I2cBusException addr 0x%02x failed after %d tries: %s"
                              % (fname, addr, self._tries, last_error))

    def writeto(self, addr, buf):
        # returns the number of ACKs received, 
        # will always send a stop even when a nack is given
        return self._write("writeto", addr, buf)

    def writevto(self, addr, bufs):
        # returns the number of ACKs received, 
        # will always send a stop even when a nack is given
        return self._write("writevto", addr, bufs)

class I2cCtl(Device):
    # Creates object referenced by the application to represent I2C busses
    # I2C:
    #   - Idle both SDL and SCL are 1
    #   - Repeated START instead of a STOP to retain bus
    #   - Data bits: SDA can only change while scl is low
    #        * SDA 0 or 1, SCL transitions 0-1-0 (SCL pulsed)
    #        * SDA only changes when SCL is 0
    #   - Changing SDA while SCL is high is reserved for control commands
    #        * START: a) SCL=1 & SDA=1; b) SDA 1->0; c) SCL 1->0
    #        * STOP:  a) SCL=0 & SDA=0; b) SCL 0->1; c) SDA 0->1
    #        * ACK:   SDA 1 to 0
    #   - No limit to message size in spec, though buffer sz may limit
    #   - Slave holding SDA low: Error. 1) state machine is waiting 
    #     for a clock that never comes or 2) a bus fault.
    #   - Slave holding SCL low: Clock Stretching. slave can hold SCL 
    #     low to indicate it is not ready for the next frame. The controller
    #     will refrain from sending/reading more data until the clock is released.
    #  
    # Message format:
    # -----------------------------------------------------
    #    START => SDA 1 to 0 then SCL 1 to 0
    #       | 7 bit addr  | R/W | ACK/NACK |  <= 9 bits
    #       | 8 bits data | ack/nack |        <= 9 bits
    #       | 8 bits data | ack/nack |        <= 9 bits
    #              ...                        ...        
    #    STOP  => SCL 0 to 1 then SDA 0 to 1
    # -----------------------------------------------------
    # For Standard Mode (up to 100 kHz) and Fast Mode (up to 400 kHz), the minimum
    # low and high pulse widths of the SCL clock are specified as follows:
    #   - Standard Mode (100 kHz, period = 10us):
    #       * SCL Low   Pulse Width t_low:  ≥ 4.7 us
    #       * SCL High  Pulse Width t_high: ≥ 4.0 us
    #
    #   - Fast Mode (400 kHz, period = 2.5us):
    #       * SCL Low  Pulse Width t_low:  ≥ 1.3 us
    #       * SCL High Pulse Width t_high: ≥ 0.6 us
    #
    #   - Fast Mode Plus (1 MHz, period = 1us):
    #       * SCL Low  Pulse Width t_low:  ≥ 0.5 us
    #       * SCL High Pulse Width t_high: ≥ 0.26 us
    #  RC time controls rise and fall times which impact the actual low/hi times.
    # Reset the bus after this many OSErrors in a row, any successful
    # write clears the count. Not a count per time window, a timed out try
    # takes up to the I2C timeout, so a slow bus could never reach it.

    # From Device:
    # They must also call self.init() in their __init__() to set the device state to STATE_INIT 
    # Child classes must implement the following hooks
    #  _init()  called from Device.init()  - Device state = Device.STATE_INIT
    #  _stop()  called from Device.stop()  - Device state = Device.STATE_STOP
    #  _start() called from Device.start() - Device state = Device.STATE_START
    # Inherits is_on() and is_off() from Device, which check the Device state.
    I2C_BUS_ERR_MAX = 9 # FIXME: 9 there is some evidence that resetting the bus may make things worse
                        # But I also believe it occasionally works. 


    def __init__(self, debug=0):
        self.DEBUG = debug

        self.Errors = [{"count": 0, "last": 0},
                       {"count": 0, "last": 0}]
        self.fail_cnt  = 0  # writes that failed all their tries
        self.fails     = {} # the same by "addr:kind", e.g. "22:110"
        self.reset_cnt = 0  # bus resets
        # I2C0 bus for devices other than the motor
        # I2C1 bus for the motors (SDA Pin & SCL Pin)
        # 2&3, 6&7, 10&11, 14&15, 18&19, 22&23, 26&27
        # used: 
        #   6/7 (LED), 10 (Button), 14/15 ultrasonic, 18/19 SPI,
        #   23 (SMPS control), 26 (Pot), 27 (LDR)
        # Available: Pins 2 & 3
        self._i2c = [{"OBJ": None, "SCL": I2C0_SCL_PIN, "SDA": I2C0_SDA_PIN, "FREQ": I2C0_FREQ, "TOUT": I2C0_TOUT},
                     {"OBJ": None, "SCL": I2C1_SCL_PIN, "SDA": I2C1_SDA_PIN, "FREQ": I2C1_FREQ, "TOUT": I2C1_TOUT}]
        self.init() # the bus is needed by other devices' __init__, so create it now

    # Device hooks, the bus is usable once initialized so start/stop do nothing
    def _init(self):
        self.Errors = [{"count": 0, "last": 0},
                       {"count": 0, "last": 0}]
        self._i2c[I2C0_ID]["OBJ"] = I2C(I2C0_ID, 
                                        scl = Pin(self._i2c[I2C0_ID]["SCL"]), 
                                        sda = Pin(self._i2c[I2C0_ID]["SDA"]), 
                                        freq    = self._i2c[I2C0_ID]["FREQ"],
                                        timeout = self._i2c[I2C0_ID]["TOUT"])
        # FIXME: Is a second bus needed?
        # self.i2c[I2C1_ID]["OBJ"] = I2C(I2C1_ID, 
        #                                scl  = Pin(self.i2c[I2C1_ID]["SCL"]), 
        #                                sda  = Pin(self.i2c[I2C1_ID]["SDA"]),
        #                                freq    = self._i2c[I2C1_ID]["FREQ"],
        #                                timeout = self._i2c[I2C1_ID]["TOUT"])   

        if self.DEBUG >= DEBUG_INFO:
            print("I2cCtl._init: I2C 0 ", self._i2c[I2C0_ID]["OBJ"])
            print("I2cCtl._init: I2C 1 ", self._i2c[I2C1_ID]["OBJ"])

    def _stop(self):
        # FIXME: Reset error counts
        self.clear_err()

    def _start(self):
        pass

    def __str__(self):
        return "I2C: {}".format(self._i2c[I2C0_ID]["OBJ"])
    
    def bus(self, id=I2C0_ID, tries=I2C_MAX_TRIES):
        assert id == I2C0_ID # FIXME: 2nd bus?
        return I2cBus(self, id, tries)

    def i2c(self, id=I2C0_ID):
        assert id == I2C0_ID # FIXME: 2nd bus?
        return self._i2c[id]["OBJ"]

    def count_fail(self, addr, kind):
        # called by I2cBus for each write that failed all its tries
        self.fail_cnt += 1
        key = "%02x:%s" % (addr, kind)
        self.fails[key] = self.fails.get(key, 0) + 1

    def clear_err(self, id=I2C0_ID):
        # Called by I2cBus for each successful write
        self.Errors[id]["count"] = 0
        self.Errors[id]["last"]  = 0

    def handle_err(self, id=I2C0_ID):
        # Called by I2cBus for each failed write due to a bus error.
        # Resets the bus once there are I2C_BUS_ERR_MAX errors in a row.
        # Returns True if the bus was reset, does not raise exceptions.
        now = ticks_ms()

        if ticks_diff(now, self.Errors[id]["last"]) > I2C_ERROR_WINDOW_MS:
            print("ticks diff %d, %d" % (ticks_diff(now, self.Errors[id]["last"]), I2C_ERROR_WINDOW_MS))
            self.clear_err()
            return False

        self.Errors[id]["last"]   = now
        self.Errors[id]["count"] += 1

        if self.Errors[id]["count"] < I2cCtl.I2C_BUS_ERR_MAX:
            return False

        if self.DEBUG >= DEBUG_INFO:
            print("I2cCtl.handle_err: bus errors exceeded limit. Cnt = %d" % self.Errors[id]["count"])

        # Over error count, reset bus and init error count
        self.clear_err()
        try:
            return self._reset_i2c(id)
        except Exception as e:
            if self.DEBUG >= DEBUG_WARN:
                print("I2cCtl handle_err reset failed: ", e)
            return False

    def _reset_i2c(self, id=I2C0_ID):
        # Can handle where the master has stopped issuing clock cycles
        # because the slave is holding sda low.
        # This does not address clock stretching, for that need to give
        # peripheral time 
        # No exception (except for assertions)
        assert id == I2C0_ID # FIXME: 2nd bus?
        old_i2c = self._i2c[id]["OBJ"]
        if (not old_i2c) and self.DEBUG >= DEBUG_WARN:
            # Should never happen, but not a problem since we are creating a new one
            print("reset_i2c: i2c ID 2 not defined")

        if self.DEBUG >= DEBUG_INFO:
            print("I2cCtl.reset_i2c: Resetting I2C bus ", id)

        self._i2c[id]["OBJ"] = None

        try:
            scl = Pin(self._i2c[id]["SCL"], Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
            sda = Pin(self._i2c[id]["SDA"], Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
            
            sleep_us(10) # FIXME: Needed?

            if (self.DEBUG >= DEBUG_INFO) and (sda.value() == 0):
                print("reset_i2c: sda is being held low", sda.value())

            # if SDA is being held low by the peripheral, we wont be able 
            # to send STOP. So need to see if we can clock out data until
            # SDA goes high.
            for _ in range(9):
                if sda.value():
                    break
                scl.value(0)
                sleep_us(5)  # sleep is part of the protocol so is needed
                scl.value(1)
                sleep_us(5)  # sleep is part of the protocol so is needed

            if not sda.value():
                if self.DEBUG >= DEBUG_WARN:
                    print("\treset_i2c: SDA is still being held low => unable to send stop!")
                self._i2c[id]["OBJ"] = old_i2c
                return False
            
            # Send stop, start with SCL LOW
            scl.value(0)
            sleep_us(5)
            # with SCL LOW, then Transition SDA HIGH to LOW. 
            # Normally SDA would not transition while SCL is LOW
            sda.value(0)
            sleep_us(5)
            # SCL transition LOW to HIGH
            scl.value(1)
            sleep_us(5)

            sda.value(1)
            sleep_us(5)
        except:
            if self.DEBUG >= DEBUG_WARN:
                print("reset_i2c: Unable to gety the I2C buss going again")
            self._i2c[id]["OBJ"] = old_i2c
            return False # or raise FIXME: Just let it pass through for now, don't want caller thinking bus is reset

        try:
            self._i2c[id]["OBJ"] = I2C(id, 
                                    scl = Pin(self._i2c[id]["SCL"]), 
                                    sda = Pin(self._i2c[id]["SDA"]), 
                                    freq    = self._i2c[id]["FREQ"],
                                    timeout = self._i2c[id]["TOUT"])
            
            if self.DEBUG >= DEBUG_VERB:
                print("** reset_i2c: New bus ", self._i2c[id]["OBJ"])
            self.reset_cnt += 1

        except Exception as e:
            if self.DEBUG >= DEBUG_WARN:
                print("reset_i2c exception: ", e)
            # FIXME: Do I need to redefine pins?
            Pin(self._i2c[id]["SCL"])
            Pin(self._i2c[id]["SDA"])
            self._i2c[id]["OBJ"] = old_i2c
            return False
        
        return True

#############################################################################
# OLED
#############################################################################
OLED_WIDTH       = 128 # 16 chars within a row
OLED_HEIGHT      =  64 #  8 chars within a column
OLED_CHAR_SIZE   =   8
OLED_ROW_CHARS   =  16 # OLED_WIDTH // OLED_CHAR_SIZE
OLED_ROW_CENTER  = OLED_WIDTH // 2
OLED_ROW_HEIGHT  =  16
OLED_ROW_COUNT   =   4 # Fixed since the below assumes 4 rows. OLED_HEIGHT // OLED_ROW_HEIGHT

class OledI2c(Device):
    # From Device:
    #  _init()  called from Device.init()  - Device state = Device.STATE_INIT
    #  _stop()  called from Device.stop()  - Device state = Device.STATE_STOP
    #  _start() called from Device.start() - Device state = Device.STATE_START
    # Inherits is_on() and is_off() from Device, which check the Device state.
    def __init__(self, bus, hdr, debug=0):
        # Chars per Row: 16
        # Row 1: | FK Car|
        # Row 2: | car distance to obstruction |
        # Row 3: | Errors/Diag |
        # Row 4: | Diag |
        self.DEBUG = debug
        self._hdr  = hdr
        self._obuf = [(f"Row {n+1}", 0, n * OLED_ROW_HEIGHT) for n in range(OLED_ROW_COUNT)]
        # self._obuf = [ ("Row 1", 0, 0),
        #                ("Row 2", 0, 1 * OLED_ROW_HEIGHT),
        #                ("Row 3", 0, 2 * OLED_ROW_HEIGHT),
        #                ("Row 4", 0, 3 * OLED_ROW_HEIGHT)]
        self.updated = True
        self._octrl = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, bus, I2C_ADDR_OLED)
        self.init() 

    # Device hooks, only the buffer is reset, it is written by show()
    def _init(self):
        self.init_buf()

    def _stop(self):
        # FIXME: self._octrl.poweroff()
        # self.init_buf()
        pass

    def _start(self):
        # FIXME: self._octrl.poweron()
        # self.init_buf()
        pass

    def init_buf(self):
        self._update_row(1, "Hdr:  --")
        self._update_row(2, "Dist: --")
        self._update_row(3, "Err:  --")
        self._update_row(4, "Diag: --")

    def __str__(self):
        return "Oled\n\t1) {}\n\t2) {}\n\t 3) {}\n\t4) {}".format(self._obuf[0][0], self._obuf[1][0], self._obuf[2][0], self._obuf[3][0])

    def _update_row(self, row, txt):
        # row is 1-based, txt is a string to display. If txt is longer than the row, it will be truncated.
        if self.DEBUG >= DEBUG_VERB:
            print("Update row %d with %s" % (row, txt))

        tlen    = len(txt)
        xstart  = 0
        yoffset = (row - 1) * OLED_ROW_HEIGHT

        if tlen < OLED_ROW_CHARS:
            xstart  = OLED_ROW_CENTER - ((tlen * OLED_CHAR_SIZE) // 2)
        else: # tlen >= OLED_ROW_CHARS:
            txt  = txt[:OLED_ROW_CHARS]
            xstart = 0

        self._obuf[row-1] = (txt, xstart, yoffset)
        # self._obuf[row-1][0] = txt
        # self._obuf[row-1][1] = xstart
        # self._obuf[row-1][2] = yoffset
        self.updated = True

        #oled.fill_rect(xstart, yoffset, 128, 8, 0)
        #oled.text(txt, xstart, yoffset)

    def update_row1(self, txt=None):
        if txt == None: txt = self._hdr
        self._update_row(1, txt)

    def update_row2(self, txt):
        self._update_row(2, txt)

    def update_row3(self, txt):
        self._update_row(3, txt)

    def update_row4(self, txt):
        self._update_row(4, txt)

    # Not currently used so commenting out
    # def clear(self):
    #     self._octrl.fill(0)
    #     self._octrl.show()

    def show(self):
        if not self.updated:
            if self.DEBUG >= DEBUG_VERB:
                print("OledI2c.show: no changes to buf, so skip writing to oled")
            return

        # Assume framebuffer.fill or text() will not raise exceptions     
        self._octrl.fill(0)
        for row in self._obuf:
            self._octrl.text(row[0], row[1], row[2])

        # Can throw I2CExceptions from I2CBus.write()
        self._octrl.show()
        self.updated = False

