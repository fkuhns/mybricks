from machine import Pin,ADC
from utime import sleep

# POT_PIN = 26

#
pot_pin = Pin(26, Pin.IN)
#
pot = ADC(pot_pin)

conv_factor = 3.3 / ((1 << 16) - 1)
last_raw  = 0.0 # ADC digital output u16 number
min_vdiff = 0.2 # Volts

while True:
    raw  = pot.read_u16()
    vdiff = abs(raw - last_raw) * conv_factor
    if vdiff > min_vdiff:
        volts = raw * conv_factor
        last_raw = raw
        print("Raw output of ADC {0:6,}, equivalent voltage {1:4.3}V".format(raw, volts))
    sleep(0.5)

