from machine import Pin,PWM,ADC,I2C #to access the hardware picobricks
from picobricks import SSD1306_I2C
from utime import ticks_ms # sleep

# Default I2C data and clock Pin numbers (using I2C #0)
I2C_ID       = 0
I2C_SDA_PIN  = 4
I2C_SCL_PIN  = 5

# OLED, SSD1306 (pico display), specific constants
OLED_WIDTH=128
OLED_HEIGHT=64
I2C_OLED_ADDR = 0x3c # I2C device address

# Potentiometer GPIO Pin number
POT_PIN=26

# Buzzer GPIO Pin number
BUZZ_PIN=20

# Button GPIO Pin
BUTT_PIN=10

# Create an I2C object instance using pins 4 & 5 (controller 0)
# set bus speed to 2Mbps (bps == bits/second)
i2c = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN)) #, freq=2000000)

# Show all devices on the I2C buss
# print(i2c.scan())

## create oled object and assign to the I2C bus just created
oled=SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, I2C_OLED_ADDR)

## Create GPIO Pin object for the button
button = Pin(BUTT_PIN, Pin.IN, Pin.PULL_DOWN)

## Assign an ADC to the pin attached to the potentiometer (pot)
pot = ADC(Pin(POT_PIN))

## Associate a PWM controller to the pin attached to the buzzer
buzzer= PWM(Pin(BUZZ_PIN))

pressed = False
rhythm = 0

# Define the note sequence and timing using an immutable list
# Time is in seconds
mysong = (("A3", 1.0),
          ("E4", 0.5),
          ("E4", 0.5),
          ("E4", 0.5),
          ("E4", 0.5),
          ("E4", 0.5),
          ("E4", 0.5),
          ("F4", 0.5),
          ("E4", 0.5),
          ("D4", 0.5),
          ("F4", 0.5),
          ("E4", 1.0))

# Python dictionary to associate the note name with its corresponding frequency
tones = {
    "A3": 220,
    "D4": 294,
    "E4": 330,
    "F4": 349
}
        
def playtone(frequency):
    print("Playtone {0}".format(frequency))
    buzzer.duty_u16(6000)
    buzzer.freq(frequency)

def playsong(pin):
    global pressed
    print("playsong - setting pressed to True")
    pressed = True

# Assign an interrupt handler to the button's input pin
# this handler is called whenever the button is depressed
button.irq(trigger=Pin.IRQ_RISING, handler=playsong)

note_count = 9999
played_time = 0
while True:
    # returns a value in millisec 
    current_time = ticks_ms()

    oled.show()
    oled.text("Press the button", 0, 0)


    if (note_count < len(mysong)):
        print(note_count)
        oled.fill(0)

        oled.text("Dominate ", 30, 10)
        oled.text("the ", 45, 25)
        oled.text("Rhythm ", 35, 40)

        # 65535 is the max value the ADC will return
        # so pot.read_u16()/65535 will return a value between 0 and 1
        # 1 <= rhythm <= 21 
        rhythm=((pot.read_u16()/65535.0)*20) + 1

        #print("Rhythm = {0}".format(rhythm))
        # millisec count divided by 1000 gives seconds
        played_sec = (current_time - played_time)/1000.0
        play_note  = mysong[note_count][0]
        play_sec   = mysong[note_count][1]

        if played_sec  >= play_sec/rhythm:
            played_time = ticks_ms()
            print("Played sec {0} rhythm {1}".format(played_sec, play_sec/rhythm))
            playtone(tones[play_note])
            note_count += 1

    else:
        buzzer.duty_u16(0)
        
    if pressed:
        note_count = 0
        pressed = False
        
        
        
