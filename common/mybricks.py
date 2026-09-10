# from machine import Pin, PWM, ADC, I2C
# from picobricks import SSD1306_I2C, WS2812, SHTC3
# from utime import ticks_ms # sleep


# OLED specific constants
OLED_WIDTH  = 128
OLED_HEIGHT =  64

# I2C Bus constants and addresses
I2C_ID        =    0 # => pins 4 and 5
# Addresses
I2C_OLED_ADDR  = 0x3c
I2C_SHTC3_ADDR = 0x70 # Temperature and humidity

# Default pin assignments
I2C_SDA_PIN =  4
I2C_SCL_PIN =  5
RGB_LED_PIN =  6
LED_PIN     =  7
BUTT_PIN    = 10
BUZZ_PIN    = 20
POT_PIN     = 26
LDR_PIN     = 27

BUTT_DEBOUNCE_MS = 200  # Milliseconds to ignore subsequent bounces

# OLED
def clear_oled(oled):
    oled.fill(0)#clear OLED
    oled.show()

# ADC
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