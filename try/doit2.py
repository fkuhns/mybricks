from machine import Pin,ADC
from utime import sleep

# OLED specific constants
OLED_WIDTH  = 128
OLED_HEIGHT =  64

# I2C Bus constants and addresses
I2C_ID        =    0 # => pins 4 and 5
# Addresses
I2C_OLED_ADDR = 0x3c
I2C_SHTC3_ADDR    = 0x70 # Temperature and humidity

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

## ADC
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

# POT_PIN = 26

#
pot_pin = Pin(26, Pin.IN)
#
pot = ADC(pot_pin)

conv_factor = ADC_CONV_FACTOR
last_raw  = 0.0 # ADC digital output u16 number
min_vdiff = 0.2 # Volts
min_percent = adc_volt2Percent(min_vdiff)
print("Volt ", min_vdiff, ", Percent ", min_percent)
min_rdiff = adc_volt2Raw(min_vdiff)
print("\tRaw pdiff = ", min_rdiff, "Raw Percent = ", adc_raw2percent(min_rdiff))

while True:
    raw  = pot.read_u16()
    #vdiff = abs(raw - last_raw) * conv_factor
    pdiff = percent_diff(raw, last_raw)
    if pdiff > min_percent:
        volts = raw * conv_factor
        last_raw = raw
        print("Raw output of ADC {0:6,}, percent pdiff {1:6,}, equivalent voltage {2:4.3}V".format(raw, pdiff, volts))
    sleep(0.5)