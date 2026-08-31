from machine import Pin,ADC
from utime import sleep

pot_pin = Pin(26, Pin.IN)

pot = ADC(pot_pin)

last      = 0.0
min_diff  = 500

while True:
    raw  = pot.read_u16()
    diff = abs(raw - last)
    if diff > min_diff:
        last = raw
        print("Raw output of ADC {0:6,}".format(raw))
    sleep(0.5)

