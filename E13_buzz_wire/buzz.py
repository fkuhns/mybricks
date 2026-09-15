from machine import Pin, I2C, PWM
from picobricks import SSD1306_I2C
from utime import sleep, ticks_ms, ticks_diff
import sys

# I2C Bus
I2C_ID       =  0
I2C_SDA_PIN  =  4
I2C_SCL_PIN  =  5
I2C_DEF_FREQ = 1000000

GEN_SENSOR_PIN   =  1

# OLED Screen
OLED_WIDTH    = 128
OLED_HEIGHT   =  64
OLED_I2C_ADDR = 0x3c

LED_PIN  =  7
BUTT_PIN = 10
BUZZ_PIN = 20

i2c  = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN)) 

try:
    oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, OLED_I2C_ADDR)
except KeyboardInterrupt:
    print("Keyboard interrupt received during initialization")
    sys.exit()
except Exception as e:
    print("Program terminating with e during initialization: ", e)
    sys.exit()

wire   = Pin(GEN_SENSOR_PIN, Pin.OUT) 
led    = Pin(LED_PIN,  Pin.OUT)
#buzzer = Pin(BUZZ_PIN, Pin.OUT)
buzzer= PWM(Pin(BUZZ_PIN, Pin.OUT))
button = Pin(BUTT_PIN, Pin.IN, Pin.PULL_DOWN)

endtime = 0

def reset():
    global endtime, wire, led, buzzer, oled
    endtime = 0
    # wire.low()
    # led.low()
    # buzzer.low()
    # oled.fill(0)
    # oled.show()

endtime = 0
wire.low()
led.low()

buzzer.freq(1000)
oled.fill(0)
oled.show()

try:
    while True:
        led.low()
        oled.fill(0)
        oled.show()

        oled.text("<BUZZ WIRE GAME>",0,0)
        oled.text("Press the button",0,17)
        oled.text("TO START!",25,35)
        oled.show()

        sleep(1)

        while button.value() == 0:
            print("press the button")

        oled.fill(0)
        oled.show()

        oled.text("GAME",25,35)
        oled.text("STARTED",25,45)
        oled.show()

        wire.high()
        timer_start = ticks_ms()

        while wire.value() == 1:
            print("Started")

        endtime = ticks_diff(ticks_ms(), timer_start)
        print(endtime)

        oled.fill(0)
        oled.show()

        oled.text("GAME OVER!",25,35)
        oled.text(str(endtime) + "ms" ,25,45)
        oled.show()

        led.high()
        buzzer.duty_u16(5000)
        #buzzer.high()

        sleep(5)
        buzzer.duty_u16(0)

except KeyboardInterrupt:
	reset()
	print("Keyboard interrupt received")
except Exception as e:
     reset()
     print("Program terminating with e: ", e)