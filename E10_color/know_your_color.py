from machine import Pin, I2C
from picobricks import SSD1306_I2C
import utime
import urandom
import _thread
from picobricks import WS2812

# Constants
OLED_WIDTH  = 128
OLED_HEIGHT = 64

I2C_ID      =  0

I2C_SDA_PIN =  4
I2C_SCL_PIN =  5
RGB_LED_PIN =  6
BUTT_PIN    = 10

OLED_WIDTH     = 128
OLED_HEIGHT    =  64
I2C_OLED_ADDR  = 0x3c

NEO_DEF_BRIGHTNESS = 0.3

NEO_RED   = (255,   0,   0)
NEO_GREEN = (  0, 255,   0)
NEO_BLUE  = (  0,   0, 255)
NEO_WHITE = (255, 255, 255)
NEO_BLACK = (  0,   0,   0)

# Local functions
def oled_clear(oled):
    oled.fill(0)#clear OLED
    oled.show()

def oled_set(oled, txt, x=45, y=32):
    oled.text(txt, x, y)
    oled.show()

def neo_reset(neo):
    neo.pixels_fill(NEO_BLACK)
    neo.pixels_show()

def neo_set(neo, color):
    neo.pixels_fill(color)
    neo.pixels_show()

# Devices
i2c    = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN)) # freq=1000000)
neo    = WS2812(RGB_LED_PIN, brightness=NEO_DEF_BRIGHTNESS)
oled   = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, I2C_OLED_ADDR)
button = Pin(BUTT_PIN, Pin.IN, Pin.PULL_DOWN)

# Initialize devices
neo_reset(neo)

oled_clear(oled)
################
score   = 0
pressed = False
rgb_id  = 5
txt_id  = 5

def random_rgb():
    global rgb_id
    rgb_id=int(urandom.uniform(1,5))
    # Micropython does not support switch/case statements, so we use if/elif/else
    if rgb_id == 1:
        neo_set(neo, NEO_RED)
    elif rgb_id == 2:
        neo_set(neo, NEO_GREEN)
    elif rgb_id == 3:
        neo_set(neo, NEO_BLUE)
    elif rgb_id == 4:
        neo_set(neo, NEO_WHITE)
    else:
        neo_set(neo, NEO_BLACK)

def random_text():
    global txt_id
    txt_id = urandom.randint(1,5)
    # Micropython does not support switch/case statements, so we use if/elif/else
    if txt_id == 1:
        oled_clear(oled)
        oled_set(oled, "RED")
    elif txt_id == 2:
        oled_clear(oled)
        oled_set(oled, "GREEN")
    elif txt_id == 3:
        oled_clear(oled)
        oled_set(oled, "BLUE")
    elif txt_id == 4:
        oled_clear(oled)
        oled_set(oled, "WHITE")
    else:
        oled_clear(oled)
        oled_set(oled, "BLACK")

def button_reader_thread():
    while True:
        global pressed
        if pressed == False:
            if button.value() == 1:
                pressed = True
                global score
                global txt_id
                global rgb_id
                
                if rgb_id == txt_id:
                    score += 10
                else:
                    score -= 10
        utime.sleep(0.01)

_thread.start_new_thread(button_reader_thread, ())

oled.text("The Game Begins",0,10)
oled.show()
utime.sleep(2)

for i in range(10):
    random_text()
    random_rgb()
    pressed=False
    utime.sleep(1.5)
    oled_clear(oled)
    neo_reset(neo)

utime.sleep(1.5)
oled_clear(oled)
#oled_set(oled, "Your total score:", 0, 20)
#oled_set(oled, str(score), 30, 40)

oled.text("Your total score:",0,20)
oled.text(str(score), 30,40)
oled.show()
