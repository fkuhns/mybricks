from machine import Pin,ADC
from utime import sleep

pot_pin = Pin(26, Pin.IN)

pot = ADC(pot_pin)

conv_factor = 3.3 / ((1 << 16) - 1)
last      = 0.0
min_diff  = 500

while True:
    raw  = pot.read_u16()
    diff = abs(raw - last)
    if diff > min_diff:
        volts = raw * conv_factor
        last = raw
        print("Raw output of ADC {0:6,}, equivalent voltage {1:4.3}V".
              format(raw, volts))
    sleep(0.5)

