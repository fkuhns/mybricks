# Modified from Peter Hinch's NEC IR receiver code
# https://github.com/peterhinch/micropython_ir/blob/master/ir_rx

#############################################################################
#     ***** Headers from Hinch's code *****
# ir_rx __init__.py Decoder for IR remote control using synchronous code
# IR_RX abstract base class for IR receivers.

# Author: Peter Hinch
# Copyright Peter Hinch 2020-2024 Released under the MIT license

# Thanks are due to @Pax-IT for diagnosing a problem with ESP32C3.

# nec.py Decoder for IR remote control using synchronous code
# Supports NEC and Samsung protocols.
# With thanks to J.E. Tannenbaum for information re Samsung protocol

# For a remote using NEC see https://www.adafruit.com/products/389

# Author: Peter Hinch
# Copyright Peter Hinch 2020-2022 Released under the MIT license
#############################################################################

from machine import Timer, Pin
from array import array
from utime import ticks_us
from utime import ticks_us, ticks_diff

# from micropython import alloc_emergency_exception_buf
# alloc_emergency_exception_buf(100)

# On 1st edge start a block timer. While the timer is running, record the time
# of each edge. When the timer times out decode the data. Duration must exceed
# the worst case block transmission time, but be less than the interval between
# a block start and a repeat code start (~108ms depending on protocol)

class IR_RX:
    Timer_id = -1  # Software timer but enable override
    # Result/error codes
    # Repeat button code
    REPEAT = -1
    # Error codes
    BADSTART = -2
    BADBLOCK = -3
    BADREP = -4
    OVERRUN = -5
    BADDATA = -6
    BADADDR = -7

    # From PicoBricks 
    number_1 = 0x45
    number_2 = 0x46
    number_3 = 0x47
    number_4 = 0x44
    number_5 = 0x40
    number_6 = 0x43
    number_7 = 0x07
    number_8 = 0x15
    number_9 = 0x09
    number_0 = 0x19
    number_ok = 0x1c
    number_up = 0x18
    number_down = 0x52
    number_right = 0x5a
    number_left = 0x08
    number_star= 0x16
    number_sharp= 0x0d

    def __init__(self, pin, extended, callback, *args):  # Optional args for callback
        self._pin       = pin 
        self._nedges    = 68 # Block lasts <= 80ms (extended mode) and has 68 edges
        self._tblock    = 80
        self.callback   = callback
        self.args       = args
        self._errf      = lambda _: None
        self.verbose    = False
        self.edge       = 0
        self._times     = array("i", (0 for _ in range(self._nedges + 1)))  # +1 for overrun
        self.tim        = Timer(self.Timer_id) 
        self._extended  = extended # True for 16, False for 8
        self._addr      = 0
        self._leader    = 4000  # 4.5ms for Samsung else 9ms

        self.cb = self.decode

        pin.irq(handler=self._cb_pin, trigger=(Pin.IRQ_FALLING | Pin.IRQ_RISING))

    # **** Pin interrupt. Save time of each edge for later decode.
    def _cb_pin(self, line):
        t = ticks_us()
        # On overrun ignore pulses until software timer times out
        if self.edge <= self._nedges:  # Allow 1 extra pulse to record overrun
            if not self.edge:  # First edge received
                self.tim.init(period=self._tblock, mode=Timer.ONE_SHOT, callback=self.cb)
            self._times[self.edge] = t
            self.edge += 1
            # Prcobricks.py adds
            # if self.edge > 68 : # FIXME: Is this needed??
            #     self.edge = 0

    def do_callback(self, cmd, addr, ext, thresh=0):
        self.edge = 0
        if cmd >= thresh:
            self.callback(cmd, addr, ext, *self.args)
        else:
            self._errf(cmd)

    def error_function(self, func):
        self._errf = func

    def close(self):
        self._pin.irq(handler=None)
        self.tim.deinit()

    def decode(self, _):
        try:
            if self.edge > 68:
                raise RuntimeError(self.OVERRUN)
            
            # width of leading burst is 9ms, for data or repeat code.
            width = ticks_diff(self._times[1], self._times[0])
            if width < self._leader:
                raise RuntimeError(self.BADSTART)
            # width of leading space should be 4.5ms for normal data or 2.25ms for a repeat code
            width = ticks_diff(self._times[2], self._times[1])
            # Leading space is 4.5ms for normal data or 2.25ms for a repeat code
            if width > 3000:
                if self.edge < 68: # Haven't received the correct number of edges
                    raise RuntimeError(self.BADBLOCK)
                # Time spaces only (data/addr bursts are always 562.5µs)
                # '1' space is 1.6875ms, total = 2.25ms
                # '0' space is 562.5µs, total = 1.125ms
                # Skip last bit which is always 1
                val = 0
                for edge in range(3, 68 - 2, 2):
                    val >>= 1
                    # time diff for edge pairs, 3-4, 5-6, etc. If > 1.125ms
                    # then it's a '1' edge 0-1 is the leading pulse, 1-2 is the leading space, 
                    # 2-3 is the first data pulse, 3-4 is the first data space, etc.
                    # 2-66 edges, 34 data bits, 16 addr bits, 8 cmd bits, 8 cmd check bits
                    # 67-68 is the stop bit, which is always a '1' space.
                    if ticks_diff(self._times[edge + 1], self._times[edge]) > 1120:
                        # Logical '1'. Bits are received LSB first, so shift
                        # in a '1' at the MSB position.
                        val |= 0x80000000
            elif width > 1700: # 2.5ms space for a repeat code. Should have exactly 4 edges.
                # Must be a repeat code. Repeat code only has 2 pulses, or 4 edges.
                raise RuntimeError(self.REPEAT if self.edge == 4 else self.BADREP)
            else:
                # Otherwise this is not a valid leading space.
                raise RuntimeError(self.BADSTART)
            # data is the low order byte, the inverse if the high order byte
            addr = val & 0xff
            cmd = (val >> 16) & 0xff
            # Verify inverse byte
            if cmd != (val >> 24) ^ 0xff:
                raise RuntimeError(self.BADDATA)
            if addr != ((val >> 8) ^ 0xff) & 0xff:  # 8 bit addr doesn't match check
                if not self._extended:
                    raise RuntimeError(self.BADADDR)
                addr |= val & 0xff00  # pass assumed 16 bit address to callback
            self._addr = addr
        except RuntimeError as e:
            cmd = e.args[0]
            addr = self._addr if cmd == self.REPEAT else 0  # REPEAT uses last address
        # Set up for new data burst and run user callback
        self.do_callback(cmd, addr, 0, self.REPEAT)

class NEC_8(IR_RX):
    def __init__(self, pin, callback, *args):
        super().__init__(pin, False, False, callback, *args)

class NEC_16(IR_RX):
    def __init__(self, pin, callback, *args):
        super().__init__(pin, True, False, callback, *args)
