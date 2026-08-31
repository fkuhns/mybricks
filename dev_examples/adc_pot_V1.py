from machine import Pin,ADC
from utime import sleep

POT_PIN = 26

# Maximum voltage to expect
GPIO_VOLT_MAX =  3.3

# Converting between ADC reported integer and detected voltage
# max voltage * number read / MaxValue 
# Max value for unsigned 16 bit = (1 << 16) - 1
#   raw / ADC_MAX_NUM  = volt / GPIO_VOLT_MAX
#   volt(raw) = Raw * CONV_FACTOR
#   raw(volt) = Volt / CONV_FACTOR
CONV_FACTOR = GPIO_VOLT_MAX / ((1 << 16) - 1)

# Report pot change if over this amount
POT_MIN_DIFF = 500
print("Pot min diff = ", POT_MIN_DIFF, ", Volt diff = ", POT_MIN_DIFF*CONV_FACTOR)

pot = ADC(Pin(POT_PIN, Pin.IN))
last = 0.0

while True:
    # Read as an unsigned 16-bit integer
    raw  = pot.read_u16()
    diff = abs(raw - last)

    if diff > POT_MIN_DIFF:
        volts = raw * CONV_FACTOR
        last = raw
        print("Raw value of Pot {0:6,}, voltage {1:4.3}V".format(raw, volts))
        print("\tRaw diff = {}, Volt diff {}".format(diff, diff*CONV_FACTOR))
    sleep(0.5)

