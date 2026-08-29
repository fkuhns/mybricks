from machine import Pin
from utime import sleep

# Define constants
SLEEP_INTERVAL = 0.5
LED_PIN = 7

# Create GPIO pin for the LED
# - i.e. GPIO Pin 7 is physically attached to the LED
led = Pin(LED_PIN, Pin.OUT)

# First verify the LED is off when you start up
if led.value() != False:
    print("*** Error, LED should be off when starting!!!")
    raise Exception("LED not working properly")

# ***************************************************************************
# Turn the LED on and off 4 times using different functions
# ***************************************************************************
# ---------------------------------------------------------------------------
# 1 - Toggle the LED on & off. Using led.value(1) and led.value(0)
led.value(1)
print("\tLed ON 1 - led.value() = ", led.value())
# pause so you can see the light on!
sleep(SLEEP_INTERVAL)

# Then turn the LED back off
led.value(0)
print("\t\tLed OFF 1 - led.value() = ", led.value())
# Pause a second time so you can verify the LED is off
sleep(SLEEP_INTERVAL)

# ---------------------------------------------------------------------------
# 2 - Toggle the LED on, using led.on() and led.off()
led.on()
print("\tLed ON 2 - led.value() = ", led.value())
sleep(SLEEP_INTERVAL)

led.off()
print("\t\tLed OFF 2 - led.value() = ", led.value())
sleep(SLEEP_INTERVAL)

# ---------------------------------------------------------------------------
# 3 - Toggle the LED on, using led.high() and led.low()
led.high()
print("\tLed ON 3 - led.value() = ", led.value())
sleep(SLEEP_INTERVAL)

led.low()
print("\t\tLed OFF 3 - led.value() = ", led.value())
sleep(SLEEP_INTERVAL)

# ---------------------------------------------------------------------------
# 4 - Toggle the LED on, using led.toggle()
led.toggle()
print("\tLed ON 4 - led.value() = ", led.value())
sleep(SLEEP_INTERVAL)

led.toggle()
print("\t\tLed OFF 4 - led.value() = ", led.value())
sleep(SLEEP_INTERVAL)

# LED should remain off after program runs
print("Done, exiting ...")
