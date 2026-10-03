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

from machine import Timer, Pin, enable_irq, disable_irq 
from array import array
from utime import ticks_us
from utime import ticks_us, ticks_diff
from micropython import schedule

# from micropython import alloc_emergency_exception_buf
# alloc_emergency_exception_buf(100)

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
    number_1     = 0x45
    number_2     = 0x46
    number_3     = 0x47
    number_4     = 0x44
    number_5     = 0x40
    number_6     = 0x43
    number_7     = 0x07
    number_8     = 0x15
    number_9     = 0x09
    number_0     = 0x19
    number_ok    = 0x1c
    number_up    = 0x18
    number_down  = 0x52
    number_right = 0x5a
    number_left  = 0x08
    number_star  = 0x16
    number_sharp = 0x0d

    def __init__(self, pin, extended, callback, *args):  # Optional args for callback
        self._pin       = pin 

        self._callback  = callback
        self._args      = args
        
        self._errf      = lambda _: None
        

        self._nedges    = 68 # Block lasts <= 80ms (extended mode) and has 68 edges
        self._edge      = 0
        self._times     = array("i", (0 for _ in range(self._nedges + 1)))  # +1 for overrun

        self._extended  = extended # True for 16, False for 8
        self._addr      = 0
        self._leader    = 4000  # 4.5ms for Samsung else 9ms

        self.cb      = self.decode
        self._tblock = 80
        self.verbose = False
        self.tim     = Timer(self.Timer_id)

        self._pin.irq(handler=self._cb_pin, trigger=(Pin.IRQ_FALLING | Pin.IRQ_RISING))

    # **** Pin interrupt. Save time of each edge for later decode.
    def _cb_pin(self, line):
        t = ticks_us()
        # On overrun ignore pulses until software timer times out
        if self._edge <= self._nedges:  # Allow 1 extra pulse to record overrun
            if not self._edge:  # First edge received
                self.tim.init(period=self._tblock, mode=Timer.ONE_SHOT, callback=self.cb)
            self._times[self._edge] = t
            self._edge += 1
            # FIXME: Prcobricks.py adds. 
            # if self._edge > 68 :
            #     self._edge = 0

    def do_callback(self, cmd, addr, ext, thresh=0):
        if cmd >= thresh:
            self._callback(cmd, addr, ext, *self._args)
        else:
            self._errf(cmd)

    def error_function(self, func):
        self._errf = func

    def close(self):
        self._pin.irq(handler=None)
        self.tim.deinit()

    def decode(self, e):
        try:
            val = 0
            cmd = 0
            addr = 0
            if self._edge > 68:
                raise RuntimeError(self.OVERRUN)

            # The leading burst. NEC protocol has a 9ms leading pulse
            # followed by a 4.5ms space for normal data or 2.25ms for a repeat
            # code.
            width = ticks_diff(self._times[1], self._times[0])
            if width < self._leader:
                raise RuntimeError(self.BADSTART)

            width = ticks_diff(self._times[2], self._times[1]) # should be 4500us
            if width > 3000:
                # Valid start of message, not a REPEAT msg.
                # there should be 68 edges for a full message. If not then it's a bad block.
                if self._edge < 68:
                    raise RuntimeError(self.BADBLOCK)
                
                # Time spaces only (data/addr bursts are always 562.5µs)
                # '1' space is 1.6875ms, total = 2.25ms  (4 x 562.5µs)
                # '0' space is  562.5µs, total = 1.125ms (2 x 562.5µs)
                # Skip last bit which is always 1
                val = 0
                for e in range(3, 68 - 2, 2): #3, 5, ... 65
                    val >>= 1 # shift bits right one place
                    # spaces correspond to edge pairs 3-4, 5-6, etc. Ignore 
                    # 3-2 since it marks teh start of msg. Edge pair 4-3 is
                    # the lsb of the address byte.
                    # If space is > 1120us then it's a '1' else it's a '0'. 
                    # stop bit is at edges 66-67
                    if ticks_diff(self._times[e + 1], self._times[e]) > 1120:
                        # Logical '1'. Bits are received LSB first, so shift
                        # in a '1' at the MSB position.
                        val |= 0x80000000
            elif width > 1700:
                # Must be a repeat code, which has a 2.5ms space. 
                # Repeat code only has 2 pulses, or 4 edges.
                raise RuntimeError(self.REPEAT if self._edge == 4 else self.BADREP)
            else:
                # Otherwise not a valid leading space.
                raise RuntimeError(self.BADSTART)

            # data is the low order byte, its inverse the high byte
            # First address 2 bytes then command's 2 bytes
            addr = val & 0xff 
            if self._extended:
                addr |= val & 0xff00  # pass assumed 16 bit address to callback
            elif addr != ((val >> 8) ^ 0xff) & 0xff:  # 8 bit addr doesn't match check
                raise RuntimeError(self.BADADDR)
            self._addr = addr

            cmd = (val >> 16) & 0xff 
            if cmd != (val >> 24) ^ 0xff: # Verify inverse bytes
                raise RuntimeError(self.BADDATA)
            
        except RuntimeError as e:
            cmd = e.args[0] # Set to error code or REPEAT
            addr = self._addr if cmd == self.REPEAT else 0

        # Reset edge and run user callback 
        self._edge = 0
        # print("*** DECODE: VAL = 0x{:08x} ADDR = 0x{:04x} CMD = 0x{:02x}".format(val, addr, cmd))
        self.do_callback(cmd, addr, 0, self.REPEAT)

class NEC_8(IR_RX):
    def __init__(self, pin, callback, *args):
        super().__init__(pin, False, callback, *args)

class NEC_16(IR_RX):
    def __init__(self, pin, callback, *args):
        super().__init__(pin, True, callback, *args)
