from machine import Pin,ADC
from utime import sleep

POT_PIN = 26

# Maximum voltage to expect
POT_MAX_VOLT =  3.3
# minimum voltage, 0V or ground potential
POT_MIN_VOLT =  0


# Number of bits in integer read from the ADC, documentation
# tells us it's 16 bits though the resolution is 12 bits.
ADC_U16_BITS = 16
# Converting between ADC reported integer and detected voltage
# max voltage * number read / MaxValue 
ADC_MAX_NUM = (1 << ADC_U16_BITS) - 1

# Volts = (ADC reported value (u16 or raw)) * (Max Volts)/(ADC max Value)
CONV_FACTOR = POT_MAX_VOLT / ADC_MAX_NUM

# Volt(raw) = Raw * CONV_FACTOR
# Raw(volt) = Volt / CONV_FACTOR

# Minimum voltage difference to report a change
MIN_VOLT_DIFF = 0.02 # Volts
MIN_ADC_DIFF = MIN_VOLT_DIFF / CONV_FACTOR

#
pot_pin = Pin(POT_PIN, Pin.IN)
#
pot = ADC(pot_pin)

#scale = 3.3 / ((1 << 16) - 1)
last_raw = 0.0

while True:
    # Read as an unsigned 16-bit integer
    adc_raw  = pot.read_u16()
    adc_diff = abs(adc_raw - last_raw)

    if adc_diff > MIN_ADC_DIFF:
        pot_volts = adc_raw * CONV_FACTOR
        last_raw = adc_raw
        print("Raw value of Pot {0:6,}, voltage {1:4.3}V".format(adc_raw, pot_volts))
    sleep(0.5)

