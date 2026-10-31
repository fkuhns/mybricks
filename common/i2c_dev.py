from machine import Pin, I2C
#from picobricks import MotorDriver
from utime import sleep_ms, sleep_us, ticks_diff, ticks_ms
from ssd1306 import SSD1306_I2C
from buzzer import Buzzer
from common import DEBUG_ERROR, DEBUG_INFO, DEBUG_NONE, DEBUG_VERB, DEBUG_WARN

I2C0_ID       = 0
I2C0_SDA_PIN  = 4
I2C0_SCL_PIN  = 5

I2C1_ID       = 1
I2C1_SDA_PIN  = 2
I2C1_SCL_PIN  = 3

I2C_TOUT      = 100_000

I2C_MAX_TRIES = 3

#############################################################################
# Motors
#############################################################################
MOTOR_DEF_SPEED  = 80

MOTOR_MAX_TRIES = I2C_MAX_TRIES

MOTOR_STATE_FWD   = "Forward"
MOTOR_STATE_BKWD  = "Backward"
MOTOR_STATE_LEFT  = "Left"
MOTOR_STATE_RIGHT = "Right"
MOTOR_STATE_STOP  = "Stopped"
MOTOR_STATE_INIT  = "Init"
MOTOR_STATE_UNK   = "Unknown"

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
    def __init__(self, ctl, id=I2C0_ID):
        self._ctl = ctl
        self._id  = id

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

        for i in range(I2C_MAX_TRIES):
            try:
                acks = getattr(self._ctl.i2c(self._id), fname)(addr, buf)
                if acks == exp_ack:
                    if self._ctl.DEBUG >= DEBUG_VERB:
                        print("I2cBus.%s ack %d == expected %d - success"% (fname, acks, exp_ack))
                    return True

                # acks != exp_ack
                if self._ctl.DEBUG >= DEBUG_INFO:
                    print("I2cBus.%s try %d NACK: ack %d != expected %d" % (fname, i, acks, exp_ack))

                sleep_us(500) # FIXME: prefer to not have any sleep/delay here

            except OSError as e:
                last_error = e
                if self._ctl.DEBUG >= DEBUG_INFO:
                    print("I2cBus.{} 0x{:02x} try {} OSError: {}".format(fname, addr, i, e))
                self._ctl.handle_err(self._id)
        # end of for loop
        # report whatever the last error was
        if acks != exp_ack:
            raise I2cNackException("I2cBus.%s I2cNackException addr 0x%02x failed, RX acks %d != expected %d"
                                    % (fname, addr, acks, exp_ack))
        # else
        raise I2cBusException("I2cBus.%s I2cBusException addr 0x%02x failed after %d tries: %s"
                              % (fname, addr, I2C_MAX_TRIES, last_error))

    def writeto(self, addr, buf):
        # returns the number of ACKs received, 
        # will always send a stop even when a nack is given
        return self._write("writeto", addr, buf)

    def writevto(self, addr, bufs):
        # returns the number of ACKs received, 
        # will always send a stop even when a nack is given
        return self._write("writevto", addr, bufs)

class I2cCtl():
    # Creates object referenced by the application to represent I2C busses
    # I2C:
    #   - Idle both SDL and SCL are 1
    #   - Repeated START instead of a STOP to retain bus
    #   - Data bits: SDA can only change while scl is low
    #        * SDA 0 or 1, SCL transitions 0-1-0 (SCL pulsed)
    #        * SDA only changes when SCL is 0
    #   - Changing SDA while SCL is high is reserved for control commands
    #        * START: SDA 1 to 0 then SCL 1 to 0
    #        * STOP:  SCL 0 to 1 then SDA 0 to 1
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
    I2C_ERR_MAX_MS  = 1_000
    I2C_BUS_ERR_MAX =     3


    def __init__(self, debug=0):
        self.DEBUG = debug

        self.Errors = [{"count": 0, "last": 0},
                       {"count": 0, "last": 0}]
        # I2C0 bus for devices other than the motor
        # I2C1 bus for the motors (SDA Pin & SCL Pin)
        # 2&3, 6&7, 10&11, 14&15, 18&19, 22&23, 26&27
        # used: 
        #   6/7 (LED), 10 (Button), 14/15 ultrasonic, 18/19 SPI,
        #   23 (SMPS control), 26 (Pot), 27 (LDR)
        # Available: Pins 2 & 3
        self._i2c = [{"OBJ": None, "SCL": I2C0_SCL_PIN, "SDA": I2C0_SDA_PIN, "FREQ": 400_000},
                     {"OBJ": None, "SCL": I2C1_SCL_PIN, "SDA": I2C1_SDA_PIN, "FREQ": 100_000}]
        
        self._i2c[I2C0_ID]["OBJ"] = I2C(I2C0_ID, 
                                        scl  = Pin(self._i2c[I2C0_ID]["SCL"]), 
                                        sda  = Pin(self._i2c[I2C0_ID]["SDA"]), 
                                        freq = self._i2c[I2C0_ID]["FREQ"],
                                        timeout = I2C_TOUT)
        # FIXME: fix assumption that only one bus is used!
        # self.i2c[I2C1_ID]["OBJ"] = I2C(I2C1_ID, 
        #                                scl  = Pin(self.i2c[I2C1_ID]["SCL"]), 
        #                                sda  = Pin(self.i2c[I2C1_ID]["SDA"]),     

        if self.DEBUG >= DEBUG_INFO:
            print("I2cCtl: I2C 0 ", self._i2c[I2C0_ID]["OBJ"])
            print("I2cCtl: I2C 1 ", self._i2c[I2C1_ID]["OBJ"])

    def __str__(self):
        return "I2C: {}".format(self._i2c[I2C0_ID]["OBJ"])
    
    def bus(self, id=I2C0_ID):
        assert id == I2C0_ID # FIXME: Temporary until I decide if I want both busses
        return I2cBus(self, id)

    def i2c(self, id):
        assert id == I2C0_ID
        return self._i2c[id]["OBJ"]

    def handle_err(self, id=I2C0_ID):
        # Called by I2cBus for each failed write due to a bus error. 
        # Resets the bus once there are I2C_ERR_MAX_CNT errors within I2C_ERR_MAX_MS.
        # Returns True if the bus was reset, does not raise exceptions.
        t = ticks_ms()
        if ticks_diff(t, self.Errors[id]["last"]) > I2cCtl.I2C_ERR_MAX_MS:
            # reset error count and return
            self.Errors[id]["last"]  = t
            self.Errors[id]["count"] = 1
            return False

        # increment error count
        self.Errors[id]["count"] += 1
        if self.Errors[id]["count"] < I2cCtl.I2C_BUS_ERR_MAX:
            return False

        # Over error count, reset bus and init error count
        self.Errors[id]["count"] = 0
        self.Errors[id]["last"]  = 0
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
        assert id == I2C0_ID # FIXME: Temporary until I decide if I want both busses
        old_i2c = self._i2c[id]["OBJ"]
        if (not old_i2c) and self.DEBUG >= DEBUG_WARN:
            # Should never happen, but not a problem since we are creating a new one
            print("reset_i2c: i2c ID 2 not defined")

        if self.DEBUG >= DEBUG_VERB:
            print("I2cCtl.reset_i2c: Resetting I2C bus ", id)

        self._i2c[id]["OBJ"] = None

        try:
            scl = Pin(self._i2c[id]["SCL"], Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
            sda = Pin(self._i2c[id]["SDA"], Pin.OPEN_DRAIN, Pin.PULL_UP, value = 1)
            
            # FIXME: is a sleep needed here?? sleep_us(10)
            sleep_us(10)

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
            sleep_us(5) # sleep is part of the protocol so is needed
            # SCL LOW, Transition SDA HIGH to LOW. 
            # Normally SDA would not transition while SCL is LOW
            sda.value(0)
            sleep_us(5) # sleep is part of the protocol so is needed
            # SCL transition LOW to HIGH
            scl.value(1)
            sleep_us(5) # sleep is part of the protocol so is needed

            sda.value(1)
            sleep_us(5) # sleep is part of the protocol so is needed
        except:
            if self.DEBUG >= DEBUG_WARN:
                print("reset_i2c: Unable to gety the I2C buss going again")
            self._i2c[id]["OBJ"] = old_i2c
            return False # or raise FIXME: Just let it pass through for now, don't want caller thinking bus is reset

        try:
            self._i2c[id]["OBJ"] = I2C(id, 
                                    scl =Pin(self._i2c[id]["SCL"]), 
                                    sda =Pin(self._i2c[id]["SDA"]), 
                                    freq=self._i2c[id]["FREQ"],
                                    timeout=I2C_TOUT)
            
            if self.DEBUG >= DEBUG_VERB:
                print("** reset_i2c: New bus ", self._i2c[id]["OBJ"])

        except Exception as e:
            if self.DEBUG >= DEBUG_WARN:
                print("reset_i2c exception: ", e)
            # FIXME: Do I need to redefine pins?
            self._i2c[id]["OBJ"] = old_i2c
            return False
        
        return True

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

class OledI2c():
    def __init__(self, bus, hdr, debug=0):
        # Chars per Row: 16
        # Row 1: | FK Car|
        # FIXME: Row 2: | motor state |
        # Row 3: | Errors |
        self.DEBUG = debug
        self._hdr = hdr
        self._obuf = [["row 1", 0, 0], ["row 2", 0, OLED_ROW_HEIGHT], ["row 3", 0, 2 * OLED_ROW_HEIGHT]]
        self.updated = True
        self._octrl = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, bus, OLED_I2C_ADDR)
        self.init_buf()
        sleep_ms(5)

    def init_buf(self):
        self.update_row1()
        self.update_row2("Dist: --")
        self.update_row3("Status: --")

    def __str__(self):
        return "Oled\n\t1) {}\n\t2) {}\n\t 3) {}".format(self._obuf[0][0], self._obuf[1][0], self._obuf[2][0])

    def _update_row(self, row, txt):
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
        
        self._obuf[row-1][0] = txt
        self._obuf[row-1][1] = xstart
        self._obuf[row-1][2] = yoffset
        self.updated = True

        #oled.fill_rect(xstart, yoffset, 128, 8, 0)
        #oled.text(txt, xstart, yoffset)

    def update_row1(self):
        self._update_row(1, self._hdr)

    def update_row2(self, txt):
        self._update_row(2, txt)

    def update_row3(self, txt):
        self._update_row(3, txt)

    # Not currently used so commenting out
    # def clear(self):
    #     self._octrl.fill(0)
    #     self._octrl.show()

    def show(self):
        if not self.updated:
            if self.DEBUG >= DEBUG_VERB:
                print("OledI2c.show: no changes to buf, so skip writing to oled")
            return

        self._octrl.fill(0)

        for row in self._obuf:
            self._octrl.text(row[0], row[1], row[2])

        self._octrl.show()
        self.updated = False

