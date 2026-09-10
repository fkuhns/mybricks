from machine import Pin, Timer, I2C, ADC
from picobricks import SSD1306_I2C
import utime

# I2C Constants
I2C_ID      =  0

# OLED constants
OLED_WIDTH     = 128
OLED_HEIGHT    =  64
I2C_OLED_ADDR  = 0x3c

# GPIO Constants
I2C_SDA_PIN =  4
I2C_SCL_PIN =  5
BUTT_PIN    = 10
POT_PIN     = 26

# Frequency = 1 Mhz
i2c = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN)) # , freq=1000000)

oled   = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, I2C_OLED_ADDR)
pot    = ADC(Pin(POT_PIN, Pin.IN))
button = Pin(BUTT_PIN, Pin.IN, Pin.PULL_DOWN)

def clear_oled(oled):
    oled.fill(0)#clear OLED
    oled.show()

def minute(timer):
    global min
    if min > 0:
        min -= 1
    
def second(timer):
    global min, sec
    if min == 0 and sec == 0:
        return
    if sec == 0:
        sec = 59
    else:
        sec -= 1
        
def msecond(timer):
    global min, sec, msec
    if min == 0 and sec == 0 and msec == 0:
        return
    if msec == 0:
        msec = 99
    else:
        msec -= 1

def shutdown():
    time1.deinit()
    time2.deinit()
    time3.deinit()
    clear_oled(oled)


time1 = Timer(-1)
time2 = Timer(-1)
time3 = Timer(-1)

min  = 0
sec  = 0
msec = 0

clear_oled(oled)

while button.value() == 0:
    min = int((pot.read_u16()*60)/65536) + 1
    oled.text("Set timer:" + str(min) + " min",0,12)
    oled.show()
    utime.sleep(0.2)
    clear_oled(oled)
while button.value() == 1:
    continue
try:
    time1.init(mode=Timer.PERIODIC, period=60000, callback=minute) # 60 sec
    time2.init(mode=Timer.PERIODIC, period=1000,  callback=second) #  1 sec
    time3.init(mode=Timer.PERIODIC, period=10,    callback=msecond)# 10 ms

    while button.value() == 0:
        oled.text("min:" + str(min),  50, 10)
        oled.text("sec:" + str(sec),  50, 20)
        oled.text("ms:"  + str(msec), 50, 30)
        oled.show()

        utime.sleep(0.1)
        clear_oled(oled)

        if(min == 0 and sec == 0 and msec == 0):
            break;
     
    oled.text(str(min),   60, 10)
    oled.text(str(sec),        60, 20)
    oled.text(str(msec),       60, 30)
    oled.text("Time is Over!", 10, 48)
    oled.show()
    utime.sleep(0.5)
    shutdown() 

except KeyboardInterrupt:
    print("Keyboard Interrupt!")
    shutdown()
except Exception as e:
    print("Unexpected exception:", e)
    shutdown()