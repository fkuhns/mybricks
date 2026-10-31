from machine import Pin
from time import sleep
#from utime import sleep, ticks_ms

BUTT_PIN = 10

# Create a GPIO Pin instance for the push button (input signal)
# Pull down resister means the Pin voltage is a low steady state
# i.e. button is not pressed then pin sees a low
# when button is depressed then the GPIO pin sees a high
button = Pin(BUTT_PIN, Pin.IN, Pin.PULL_DOWN)

# Print all attributes defined on the Button object
#print(button.__dict__)

if button.value() == True:
    print("Let go of the button, start with it unpressed/open")

now  = False
last = False
while True: 
    now = button.value()
    if last != now:
        print("Button changed value from %d to %d" % (last, now))
    if now == False and last == True:
        print("Button released")
    elif now == True and last == False:
        print("Button pressed")
    last = now
    
