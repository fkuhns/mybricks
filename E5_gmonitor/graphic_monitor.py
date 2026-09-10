# Import modules used to communicate with the LED and Potentiometer
from machine import Pin,ADC,PWM
from utime import sleep

LED_PIN     =  7
POT_PIN     = 26

pwm_led = PWM(Pin(LED_PIN))
pot = ADC(Pin(POT_PIN, Pin.IN))

#define the value we get from the pwm_led and pot.
pwm_led.freq(1000)

while True:#while loop
    
    # Read as an unsigned 16-bit integer
    raw = pot.read_u16()

    # Assume 3.3volts to circuit with pot
    scale = 3.3 / ((1 << 16) - 1)
    volts = raw * scale
    print("Raw value of Pot {0:6,}, Corresponding voltage {1:4.3}V".format(raw, volts))
    
    # Turn on the LED according to the value from the potentiometer.
    # Use the raw uint16 value
    pwm_led.duty_u16(raw)
    
    # slow things down, only sample every second
    sleep(1)
                 
