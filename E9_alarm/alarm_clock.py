from machine import Pin, I2C, ADC, PWM
from picobricks import SSD1306_I2C
import utime
from picobricks import WS2812

I2C_ID      =  0

I2C_SDA_PIN =  4
I2C_SCL_PIN =  5
RGB_LED_PIN =  6
BUTT_PIN    = 10
BUZZ_PIN    = 20
POT_PIN     = 26
LDR_PIN     = 27

OLED_WIDTH     = 128
OLED_HEIGHT    =  64
I2C_OLED_ADDR  = 0x3c

LDR_LOW_LIGHT = 4000  # 10000

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

def clear_oled(oled):
    oled.fill(0)#clear OLED
    oled.show()


i2c = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN)) # freq=1000000)

oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c) #, I2C_OLED_ADDR)
clear_oled(oled)

neo = WS2812(RGB_LED_PIN, brightness=0.3)
neo.pixels_fill(BLACK)
neo.pixels_show()

buzzer = PWM(Pin(BUZZ_PIN, Pin.OUT))
buzzer.freq(1000)

button = Pin(BUTT_PIN, Pin.IN, Pin.PULL_DOWN)

ldr = ADC(Pin(LDR_PIN, Pin.IN))
def is_day(ldr):
    if ldr.read_u16() < LDR_LOW_LIGHT:
        return True
    else:
        return False

day_time = is_day(ldr)

try:
    while True:
        while day_time == False:
            clear_oled(oled)
            oled.text("Sleeping", 25, 32)
            oled.show()
            utime.sleep(1)

            if is_day(ldr):
                day_time = True
                while button.value() == 0:
                    clear_oled(oled)
                    oled.text("Wakeup", 15, 32)
                    oled.show()

                    neo.pixels_fill(WHITE)
                    neo.pixels_show()

                    buzzer.duty_u16(6000)

                    utime.sleep(1)

                buzzer.duty_u16(0)
                clear_oled(oled)
                oled.text("Daytime", 15, 32)
                oled.show()
                utime.sleep(0.5)
                neo.pixels_fill(BLACK)
                neo.pixels_show()


        while day_time == True:
            clear_oled(oled)
            oled.text("Daytime", 15, 32)
            oled.show()
            utime.sleep(1)

            if is_day(ldr) == False:
                day_time = False
                clear_oled(oled)
                oled.text("Nighttime", 15, 32)
                neo.pixels_fill(BLACK)
                neo.pixels_show()

                neo.pixels_fill(BLACK)
                neo.pixels_show()
        clear_oled(oled)

except KeyboardInterrupt:
    buzzer.duty_u16(0)
    clear_oled(oled)
    neo.pixels_fill(BLACK)
    neo.pixels_show()


