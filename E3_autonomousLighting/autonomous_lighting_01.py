
from machine import Pin, ADC
from picobricks import  WS2812
from utime import sleep


# Global constants
LDR_PIN     = 27
RGB_LED_PIN =  6

# local variables
#
# Create an instance of an ADC (analog to digital converter)
# In python you can use the output of a function call as an argument 
# in the call of another function
# # LDR = Light Dependent Resister
ldr = ADC(Pin(LDR_PIN))

# The RGB LED's Pin is used as PIO (programmable IO) pin.
rgb_led = WS2812(RGB_LED_PIN, brightness=0.4)

#define colors
# Format  (Byte value for RED, Byte value for Green, Byte value for Blue).
# Note a Byte is 8 bits and when unsigned it can have any value between 0
# and 255 (all 1's)
RED   = (255,   0,   0) # Red = 255, Green = 0 and Blue = 0.
GREEN = (  0, 255,   0)
BLUE  = (  0,   0, 255)

# In Python this creates a list of lists
# Colors = ((255,   0,   0),
#           (  0, 255,   0),
#           (  0,   0, 255) )
COLORS = (RED, GREEN, BLUE)

while True:
    #print the value of the LDR sensor to the screen.
    print(ldr.read_u16())
    

    # If the LDR detects a "darkness" > 10,000 then turn on the LED
    # Recall the ADC is just measuring the voltage which varies from 0 to
    # 3.3V. When it gets dark the voltage goes up (LDR resistance also
    # increases). When it gets brighter, the voltage increases as the LDR
    # resistance
    if(ldr.read_u16() > 10000):
        # getting dark so turn on the LED. First flash Red, then Green and
        # finally Blue. The light remains blue until the next iteration of
        # the enclosing while loop.
        for color in COLORS:
            rgb_led.pixels_fill(color)
            rgb_led.pixels_show()
            sleep(1)
    else:
        # Its getting brighter so the voltage decreases until the else
        # clause is triggered. The the light is turned off
        rgb_led.pixels_fill((0,0,0))  #turn off the RGB
        rgb_led.pixels_show()
    
    # sleep for 2 seconds before starting the next iteration of the while loop
    sleep(2)


