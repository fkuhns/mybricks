from machine import Pin
import utime

# Led is connected to GPIO pin 7
LED_PIN = 7

# create an instance of the GPIO pin object for the LED
# LED_PIN is replaced with the number 7
# Pin.OUT is defined in the machine module, Pin class as an integer constant 1.
led = Pin(LED_PIN, Pin.OUT) # Pin(7,1)

try:
    # Loop indefinitely 
    while True:
        # rather than keep track of the LED state, just
        # tell it to take on the opposite state.
        led.toggle() #

        # wait 1/2 second so we can actually see the LED toggle!
        utime.sleep(0.5)
except KeyboardInterrupt:
       led.value(0)
except Exception as e:
     print("Program terminating with e: ", e)
    
