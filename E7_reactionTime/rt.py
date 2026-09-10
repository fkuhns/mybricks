from machine import Pin, I2C,Timer
from picobricks import SSD1306_I2C
import utime
import urandom

# I2C data and clock Pin numbers (using I2C #0)
I2C_ID      =  0 # => pins 4 and 5

# OLED, SSD1306 (pico display), specific constants
OLED_WIDTH  = 128
OLED_HEIGHT =  64

I2C_OLED_ADDR = 0x3c # I2C device address

I2C_SDA_PIN =  4
I2C_SCL_PIN =  5
LED_PIN     =  7
POT_PIN     = 26

# Buzzer GPIO Pin number
BUZZ_PIN=20

# Create an I2C object instance using pins 4 & 5 (controller 0)
# set bus speed to 2Mbps (bps == bits/second)
i2c = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN)) #, freq=2000000)

# Show all devices on the I2C buss
# print(i2c.scan())

## create oled object and assign to the I2C bus just created
oled=SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, I2C_OLED_ADDR)

## Create GPIO Pin object for the button
button = Pin(10, Pin.IN, Pin.PULL_DOWN)

## Create GPIO Pin object for the led
led = Pin(LED_PIN, Pin.OUT)


def clear_state():
    global oled
    oled.fill(0)#clear OLED
    oled.show()
    led.value(0)

try:
    # Program loop
    while True:
        led.value(0) # turn off led

        oled.fill(0) # zero out the display
        oled.text("press the button",0,10)
        oled.text("to Start",25,25)
        oled.show()

        #print "Press the button" and "TO START!" on the OLED screen
        while button.value()==0:
            # do nothing, this is called a busy loop waiting for the button to be pushed.
            # there are other, more efficient ways to handle this
            pass  

        oled.fill(0)
        oled.text("Wait For LED",15,30)
        oled.show()
        #write "wait for LED" on the screen when the button is pressed
        utime.sleep(urandom.uniform(1,5))
        led.value(1)
        timer_start=utime.ticks_ms()
        #wait for a random second and turn on the led
        while button.value()==0:
            pass
        timer_reaction=utime.ticks_diff(utime.ticks_ms(), timer_start)
        pressed=True
        oled.fill(0)
        oled.text("Your Time",25,25)
        oled.text(str(timer_reaction),50,50)
        oled.show()
        led.value(0)
        utime.sleep(1.5)
        #print the score and "Your Time" to the screen when the button is pressed.
except KeyboardInterrupt:
    print("Keyboard interrupt ... Program stopped by user")
    clear_state()
except Exception as e:
    print("Program terminating with e: ", e)
    clear_state() 