from machine import Pin,ADC
from utime import sleep

POT_PIN = 26

# Maximum voltage to expect
POT_MAX_VOLT =  3.3

CONV_FACTOR = POT_MAX_VOLT / ((1 << 16) - 1)

# Volt(raw) = Raw * CONV_FACTOR
# Raw(volt) = Volt / CONV_FACTOR

# Report pot change if volts change by 0.02V or more
MIN_ADC_DIFF = 0.02 / CONV_FACTOR

pot = ADC(Pin(POT_PIN, Pin.IN))

last_raw = 0.0

while True:
    # Read as an unsigned 16-bit integer
    raw  = pot.read_u16()
    diff = abs(raw - last_raw)

    if diff > MIN_ADC_DIFF:
        volts = raw * CONV_FACTOR
        last_raw = raw
        print("Raw value of Pot {0:6,}, voltage {1:4.3}V".format(raw, volts))
    sleep(0.5)

