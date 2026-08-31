# Import modules used to communicate with the LED and Potentiometer
from machine import Pin,ADC,PWM
from utime import sleep

LED_PIN     =  7

pwm_led = PWM(Pin(LED_PIN))

pwm_led.freq(1000)
pwm_led.duty_u16(50000)
sleep(0.5)

pwm_led.freq(1000)
pwm_led.duty_u16(5000)
sleep(0.5)

pwm_led.freq(1000)
pwm_led.duty_u16(500)
sleep(0.5)