from machine import Pin,I2C
from picobricks import SHTC3, SSD1306_I2C
from utime import sleep

I2C_ID      =  0
I2C_SDA_PIN =  4
I2C_SCL_PIN =  5

# OLED specific constants
# Character size is 8x8, so 16 chars per line (16 * 8 = 128)
# with 8 lines (8 * 8 = 64)
OLED_WIDTH  = 128
OLED_HEIGHT =  64

I2C_OLED_ADDR  = 0x3c

def clear_oled(oled):
    oled.fill(0)#clear OLED
    oled.show()


i2c = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN))

oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, I2C_OLED_ADDR)

clear_oled(oled)

# Write text to the FrameBuffer using the coordinates as the upper-left corner
# of the text. The color of the text can be defined by the optional argument
# but is otherwise a default value of 1. All characters have dimensions of 8x8
# pixels and there is currently no way to change the font.
oled.text("1 Fred Kuhns", 0, 0)
oled.text("2 Derf", 55, 10)
oled.text("3 Sam", 30, 20)
oled.text("4 Ben", 55, 30)
oled.text("5", 0, 40)
oled.text("6", 0, 48)
oled.text("7", 0, 56)

oled.show()#show on OLED
sleep(1)
clear_oled(oled)