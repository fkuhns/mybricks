from machine import Pin
from utime import ticks_ms, ticks_diff

BUTT_PIN = 10

## Debounce
last_press = 0
DEBOUNCE_MAX = 200  # Milliseconds to ignore subsequent bounces

# IRQ handler globals
pressed = False
pressed_seen = True

# define a function to be used as an interrupt handler. Whenever the button
# is pushed this handler will be called.
def butt_handler(pin):
    global last_press, pressed, pressed_seen
    current_time = ticks_ms()

    if ticks_diff(current_time, last_press) < DEBOUNCE_MAX:
        # print("\tButton chatter, ignoring!")
        return

    pressed = True
    pressed_seen = False
    last_press = current_time

button = Pin(BUTT_PIN, Pin.IN, Pin.PULL_DOWN)
button.irq(trigger=Pin.IRQ_RISING, handler=butt_handler)

if button.value() == True:
    print("Let go of the button, start with it unpressed/open")

count = 0
while True: 
    if pressed == True:
        if pressed_seen == False:
            pressed_seen = True
            count += 1
            print("Button Pressed, count = ", count)
            
        if button.value() == False:
            print("Button released")
            pressed = False