from machine import Pin, enable_irq, disable_irq, ADC
from utime import sleep, ticks_ms, ticks_diff
from array import array

#############################################################################
# GPIO Default pin assignments
#############################################################################
I2C0_ID         = 0
I2C1_ID         = 1

# -----------------------------------
# wireless / IR module 0 tx and 1 rx
IR_PIN         =  0 # wireless/ir module, UART0, pin 0 tx?
# Pin 1 - wire example pin, wireless/IR module RX?
I2C1_SDA_PIN   =  2
I2C1_SCL_PIN   =  3
I2C0_SDA_PIN   =  4 # OLED, SHTC3 (temp/humid)
I2C0_SCL_PIN   =  5 # OLED, SHTC3 (temp/humid)
RGB_LED_PIN    =  6 # RGB LED
LED_PIN        =  7 # Red led on button module
# Not used     =  8, 9
BUTT_PIN       = 10 # Button
# Not used     = 11 - 13
US_ECHO_PIN    = 14 # US = Ultrasonic
US_TRIGGER_PIN = 15 # US = Ultrasonic
# Not used     = 16 - 19
BUZZ_PIN       = 20 # Buzzer/Speaker
# Pin 21 - Relay module  = 21 
# Pins 21 & 22 - Motor controller
# System - Pin 23 (output) SMPS power save mode
# System - Pin 24 (input) VBUS sense
# System - Pin 25 (output) on-board LED
POT_PIN        = 26 # ADC0
LDR_PIN        = 27 # ADC1
# Pin 28 - ADC2
# System - Pin 29 (input) ADC3, monitor VSYS/3
#############################################################################
# Button
#############################################################################
class Button():
    BUTT_DEBOUNCE_MS = 200  # Milliseconds to ignore subsequent bounces

    def __init__(self):
        self.last    = 0
        self.count   = 0
        self._enabled = False
        self.led     = Pin(LED_PIN, Pin.OUT)
        self.button  = Pin(BUTT_PIN, Pin.IN, Pin.PULL_DOWN)
        self.button.irq(trigger=Pin.IRQ_RISING, handler=self.handler)

    def handler(self, pin):
        current_time = ticks_ms()

        if ticks_diff(current_time, self.last) < Button.BUTT_DEBOUNCE_MS:
            # print("\tButton chatter, ignoring!")
            return

        self.count  += 1
        self.last    = current_time

    def enabled(self):
        s = disable_irq()
        try:
            if self.count % 2: # odd count (1, 3, 5, ....)
                self._enabled = not self._enabled
            self.count = 0 # all caught up
        finally:
            enable_irq(s)

        if self._enabled:
            self.led.value(1)
        else:
            self.led.value(0)

        return self._enabled

#############################################################################
# Potentiometer
#############################################################################
# assume time for a 360 degree turn is 2 seconds or 2,000 ms.
# Convert 0 - 65,535 (2^16-1) to 1 - 2,048 (2^11) ms.
# approx = value_u16() * 2^11/2^16 = value_16() * 2^-5 = value_16() >> 5

class Pot():
    #GPIO_VOLT_MAX = 3.3
    GPIO_VAL_BITS = 16
    def __init__(self, min=1, bits=11):
        self.shift = Pot.GPIO_VAL_BITS - bits
        self.min = min
        self.pot   = ADC(Pin(POT_PIN, Pin.IN))

    def get_value(self):
        val = self.pot.read_u16()
        return self.min + (val >> self.shift)
  
#############################################################################
# IR
#############################################################################

#############################################################################
# LED
#############################################################################

#############################################################################
# RGB LED, WS2812
#############################################################################

#############################################################################
# Motor Controller
# motor = MotorDriver(i2c)
#############################################################################
MOTOR_MAX_SPEED  = 255
MOTOR_MIN_SPEED  =   0
MOTOR_TURN_SPEED = 200
MOTOR_DEF_SPEED  = 100

#############################################################################
# I2C Bus 
#############################################################################
I2C_ID        = 0

I2C_MAX_TRIES = 3

#############################################################################
# SHTC3 Temperature and Humidity Sensor
#############################################################################
SHTC3_I2C_ADDR = 0x70

#############################################################################
# NeoPixel WS2812
# RGB LED
#############################################################################
NEO_DEFAULT_BRIGHTNESS = 0.3

NEO_RED   = (255,   0,   0)
NEO_GREEN = (  0, 255,   0)
NEO_BLUE  = (  0,   0, 255)
NEO_WHITE = (255, 255, 255)
NEO_BLACK = (  0,   0,   0)

# def neo_reset(neo):
#     neo.pixels_fill(NEO_BLACK)
#     neo.pixels_show()

# def neo_set(neo, color):
#     neo.pixels_fill(color)
#     neo.pixels_show()


#############################################################################
# Light dependent resistor (LDR)
#############################################################################
LDR_LOW_LIGHT = 4000

# def is_day(ldr):
#     if ldr.read_u16() < LDR_LOW_LIGHT:
#         return True
#     else:
#         return False
    
#############################################################################
# OLED, screen chars are 8x8 pixels, so 128x64 = 16x8 chars
# oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, OLED_I2C_ADDR)
# Only works with the default frequency
#############################################################################
OLED_I2C_ADDR = 0x3c

OLED_WIDTH       = 128 # 16 chars within a row
OLED_HEIGHT      =  64 #  8 chars within a column
OLED_CHAR_SIZE   =   8 # all chars are 8x8 pixels
OLED_ROW_CHARS   =  16 # OLED_WIDTH // OLED_CHAR_SIZE
OLED_ROW_CENTER  = OLED_WIDTH // 2
OLED_ROW_HEIGHT  = 16

# OLED_CHARS_X = OLED_WIDTH // 8 # // = floor division
# OLED_CHARS_Y = OLED_HEIGHT // 8
# OLED_SPACING_Y = 2 # Default spacing between lines in pixels

#############################################################################
# ADC
#############################################################################
GPIO_VOLT_MAX   = 3.3
ADC_MAX_VALUE   = ((1 << 16) - 1)
ADC_CONV_FACTOR = GPIO_VOLT_MAX / ((1 << 16) - 1)

# def percent_diff(a, b):
#     # |a-b|/((a+b)/2) * 100
#     return 200 * abs(b - a)/(a+b)

# def adc_percent2Volt(percent):
#     return (percent/100)*GPIO_VOLT_MAX

# def adc_volt2Percent(v):
#     return 100 * v / GPIO_VOLT_MAX

# def adc_raw2percent(r):
#     return 100 * r / ADC_MAX_VALUE

# def adc_percent2Raw(percent):
#     return (percent/100)*ADC_MAX_VALUE

# def adc_raw2Volt(raw):
#     return raw*ADC_CONV_FACTOR

# def adc_volt2Raw(volt):
#     return volt/ADC_CONV_FACTOR

#############################################################################
# Ring Buffer
# Fixed size, backed by an int array. Each entry is either a single int or a
# tuple of ints, set by the init value: RingBuffer(10, 0) or RingBuffer(10, (0, 0)).
# put() returns False when full (never overwrites), get() returns None when empty.
# Safe for one producer (e.g. an ISR) and one consumer without disabling irqs:
# put() only moves head, get() only moves tail. One slot is kept unused so
# full and empty can be told apart without a shared count.
# put() with a single int does not allocate, so it is safe to call from an ISR.
#############################################################################
RING_DEF_SIZE = 10

class RingBuffer():
    def __init__(self, size=RING_DEF_SIZE, init=0):
        if isinstance(init, int):
            self.width = 1
            init = (init,)
        else:
            self.width = len(init)
        self.slots = size + 1 # one unused slot
        self.buf   = array('i', init * self.slots)
        self.head  = 0 # next slot to write, only changed by put()
        self.tail  = 0 # next slot to read, only changed by get()

    def put(self, item):
        nxt = self.head + 1
        if nxt == self.slots:
            nxt = 0
        if nxt == self.tail:
            return False # full
        i = self.head * self.width
        if self.width == 1:
            self.buf[i] = item
        else:
            for j in range(self.width):
                self.buf[i + j] = item[j]
        self.head = nxt
        return True

    def get(self):
        if self.tail == self.head:
            return None # empty
        i = self.tail * self.width
        if self.width == 1:
            item = self.buf[i]
        else:
            item = tuple(self.buf[i:i + self.width])
        nxt = self.tail + 1
        self.tail = 0 if nxt == self.slots else nxt
        return item

    def clear(self):
        # consumer side only
        self.tail = self.head

    def is_empty(self):
        return self.tail == self.head

    def is_full(self):
        return (self.head + 1) % self.slots == self.tail

    def __len__(self):
        return (self.head - self.tail) % self.slots
