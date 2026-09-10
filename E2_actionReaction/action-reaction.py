from machine import Pin                     
#
# Define global constants
# -----------------------
# Led is connected to GPIO pin 7
LED_PIN  =  7
BUTT_PIN = 10
  
# define local variables
# -----------------------
# create an instance of the GPIO pin for the LED
# output signal
led = Pin(LED_PIN, Pin.OUT)

# Create a GPIO Pin instance for the push button (input signal)
button = Pin(BUTT_PIN, Pin.IN, Pin.PULL_DOWN)


# Loop indefinitely
while True:

    # get current state of button (pushed or not)
    # returns TRUE or FALSE (1 or 0)
    button_pressed = button.value()

    # check to see if button is pushed or not
    if button_pressed == True:
        # turn on LED (button is pushed)
        led.value(1)
    else:
        # otherwise turn off.
        led.value(0)
