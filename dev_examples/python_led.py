from machine import Pin
import utime

# An LED is a simple device that has just two states: pressed or released
#   Pressed  = 1, the same as True or a logic one
#   Released = 0, the same as False or a logic zero
# This is modeled as a GPIO (general purpose IO) pin which can be either
# high ( = True or logical 1) or low (= False or a logical 0)

# 1st - define a variable that identifies the GPIO pin which is connected to the LED
LED_PIN = 7

# create an instance of a GPIO pin for the LED
#   LED_PIN identifies which physical GPIO pin to use
#   Pin.OUT indicates it will eb used as an output pin
led = Pin(LED_PIN, Pin.OUT) # same as Pin(7,1)

def my_value(led, val):
    # you can use either version of the print statement
    # experiment with the different approaches
    # print("my_value: Before value", led.value(), ", Setting value to", val)
    # print("my_value: Before value " + str(led.value()) + ", Setting value to " + str(val))
    print("my_value: Before value {0}, Set to {1}".format(led.value(), val), end=": ")
    led.value(val)
    print("After value {}".format(led.value()))

def my_toggle(led):
    print("my_toggle: Before value {}".format(led.value()), end=": ")
    if (led.value() == True):
        led.value(False)
    else:
        led.value(True)
    print("After value {}".format(led.value()))

print("\n** Trying my_value()")

my_value(led, 1)
my_value(led, 0)

print("\n ** Trying my_toggle()")
my_toggle(led)
my_toggle(led)

