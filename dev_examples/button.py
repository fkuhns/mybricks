from machine import Pin
#from utime import sleep, ticks_ms

BUTT_PIN = 10

# Create a GPIO Pin instance for the push button (input signal)
# Pull down resister means the Pin voltage is a low steady state
# i.e. button is not pressed then pin sees a low
# when button is depressed then the GPIO pin sees a high
button = Pin(BUTT_PIN, Pin.IN, Pin.PULL_DOWN)

# Print all attributes defined on the Button object
print(button.__dict__)

if button.value() == True:
    print("Let go of the button, start with it unpressed/open")

button_pressed = False
while True: 
    if button_pressed == True and button.value() == False:
        print("Button released")
        button_pressed = False
    elif button_pressed == False and button.value() == True:
        print("Button is pressed!")
        button_pressed = True