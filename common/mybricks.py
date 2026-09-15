# from machine import Pin, PWM, ADC, I2C
# from picobricks import SSD1306_I2C, WS2812, SHTC3
# from utime import ticks_ms # sleep

#############################################################################
# GPIO Default pin assignments
#############################################################################

GEN_SENSOR_PIN   =  1

RGB_LED_PIN =  6
LED_PIN     =  7
BUTT_PIN    = 10
BUZZ_PIN    = 20
POT_PIN     = 26
LDR_PIN     = 27

#############################################################################
# I2C Bus 
#############################################################################
I2C_ID       = 0
I2C_SDA_PIN  = 4
I2C_SCL_PIN  = 5
I2C_DEF_FREQ = 1000000

#############################################################################
# SHTC3 Temperature and Humidity Sensor
#############################################################################
SHTC3_I2C_ADDR = 0x70

#############################################################################
# NeoPixel WS2812
#############################################################################
NEO_DEFAULT_BRIGHTNESS = 0.3

NEO_RED   = (255,   0,   0)
NEO_GREEN = (  0, 255,   0)
NEO_BLUE  = (  0,   0, 255)
NEO_WHITE = (255, 255, 255)
NEO_BLACK = (  0,   0,   0)

def neo_reset(neo):
    neo.pixels_fill(NEO_BLACK)
    neo.pixels_show()

def neo_set(neo, color):
    neo.pixels_fill(color)
    neo.pixels_show()

#############################################################################
# Button debounce
#############################################################################
BUTT_DEBOUNCE_MS = 200  # Milliseconds to ignore subsequent bounces

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
#############################################################################
OLED_WIDTH    = 128 # 16 chars within a row
OLED_HEIGHT   =  64 #  8 chars within a column
OLED_I2C_ADDR = 0x3c

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

def percent_diff(a, b):
    # |a-b|/((a+b)/2) * 100
    return 200 * abs(b - a)/(a+b)

def adc_percent2Volt(percent):
    return (percent/100)*GPIO_VOLT_MAX

def adc_volt2Percent(v):
    return 100 * v / GPIO_VOLT_MAX

def adc_raw2percent(r):
    return 100 * r / ADC_MAX_VALUE

def adc_percent2Raw(percent):
    return (percent/100)*ADC_MAX_VALUE

def adc_raw2Volt(raw):
    return raw*ADC_CONV_FACTOR

def adc_volt2Raw(volt):
    return volt/ADC_CONV_FACTOR