from machine import Pin
from time import sleep

# create an instance of the GPIO pin for the LED
led = Pin(7, Pin.OUT) #Pin("LED", Pin.OUT)

print("LED starts flashing...")
while True:
    try:
        # rather than keep track of the LED state, just
        # tell it to take on the opposite value.
        led.toggle() # pin.value(not pin.value())
        sleep(0.5)
    except KeyboardInterrupt:
        break

led.off()
print("Finished.")
