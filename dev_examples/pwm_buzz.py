from machine import Pin, PWM
from utime import sleep # sleep

# Buzzer GPIO Pin number
BUZZ_PIN=20


# Associate a PWM controller to the pin attached to the buzzer
buzzer= PWM(Pin(BUZZ_PIN))

buzzer.duty_u16(5000)
buzzer.freq(1000)
sleep(0.5)
buzzer.duty_u16(0)
sleep(0.5)
buzzer.duty_u16(5000)
buzzer.freq(500)
sleep(0.5)