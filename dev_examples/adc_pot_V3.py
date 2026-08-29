from machine import Pin,ADC
from utime import sleep

POT_PIN = 26

POT_MAX_VOLT =  3.3
CONV_FACTOR  = POT_MAX_VOLT / ((1 << 16) - 1)

MIN_VOLT_DIFF = 0.02

def get_pot_volts(pot):
    return pot.read_u16() * CONV_FACTOR

pot = ADC(Pin(POT_PIN, Pin.IN))

last_volt = 0.0

while True:
    volt = get_pot_volts(pot)
    if abs(volt - last_volt) > MIN_VOLT_DIFF:
        print("Voltage ", volt)
        print("\tDiff", abs(volt - last_volt))
        last_volt = volt
    sleep(0.5)

