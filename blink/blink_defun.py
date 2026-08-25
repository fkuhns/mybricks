from machine import Pin
import utime

# Define any global constants ... by convention global constants 
# are always defined using capital letters

# Led is connected to GPIO pin 7
LED_PIN = 7


def doit(delay):
    # create an instance of the GPIO pin for the LED
    led = Pin(LED_PIN, Pin.OUT)

    # Loop indefinitely 
    while True:
        # rather than keep track of the LED state, just
        # tell it to take on the opposite state.
        led.toggle() #

        # wait 1/2 second so we can actually see the LED toggle!
        utime.sleep(delay)


# run program using a delay of 1/2 second between loop iterations
doit(0.5)
