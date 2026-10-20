from machine import Pin, enable_irq, disable_irq
# from picobricks import SSD1306_I2C, WS2812, SHTC3
from utime import sleep_ms, sleep_us, ticks_ms, ticks_diff #, ticks_us

#############################################################################
# GPIO Default pin assignments
#############################################################################

I2C0_ID         = 0
I2C1_ID         = 1


IR_PIN         =  0
# wire example pin, used GPIO1
I2C1_SDA_PIN   =  2
I2C1_SCL_PIN   =  3
I2C0_SDA_PIN   =  4
I2C0_SCL_PIN   =  5
RGB_LED_PIN    =  6
LED_PIN        =  7
# Not used     =  8, 9
BUTT_PIN       = 10
# Not used     = 11 - 13
US_ECHO_PIN    = 14 # US = Ultrasonic
US_TRIGGER_PIN = 15 # US = Ultrasonic
# Not used     = 16 - 19
BUZZ_PIN       = 20
# Not used     = 21 - 25
POT_PIN        = 26
LDR_PIN        = 27

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
        global last_press, pressed, pressed_seen
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
LED_I2C_ADDR = 0x3c

OLED_WIDTH       = 128 # 16 chars within a row
OLED_HEIGHT      =  64 #  8 chars within a column
OLED_CHAR_SIZE   =   8 # all chars are 8x8 pixels
OLED_ROW_CHARS   =  16 # OLED_WIDTH // OLED_CHAR_SIZE
OLED_ROW_CENTER  = OLED_WIDTH // 2
OLED_ROW_HEIGHT  = 16

# OLED_CHARS_X = OLED_WIDTH // 8 # // = floor division
# OLED_CHARS_Y = OLED_HEIGHT // 8
# OLED_SPACING_Y = 2 # Default spacing between lines in pixels

def clear_oled(oled):
    oled.fill(0)#clear OLED
    oled.show()

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