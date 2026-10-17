from machine import Pin, PWM, Timer
from utime import sleep # sleep

# Buzzer GPIO Pin number
BUZZ_PIN = 20
BUZZ_DUTY_CYCLE = 5000

BUZZ_ON_TIME_MS = 500
BUZZ_OFF_TIME_MS = 500

DEBUG = 1

class Buzzer():
    def __init__(self, debug):
        self.state   = False # false mean Off, True means On
        self.buzzing = False # True means the tone is on
        self.buzzer  = PWM(Pin(BUZZ_PIN, Pin.OUT))
        self.buzzer.freq(500)
        self.timer   = Timer(-1)
        self.DEBUG   = debug

    def off(self):
        if self.state == False:
            return
        if self.DEBUG:
            print("Buzzer off")
        self.timer.deinit()
        self.buzzer.duty_u16(0)
        self.state = False

    def on(self):
        if self.state == True:
            return
        if self.DEBUG:
            print("Buzzer on")
        #self.timer.init(mode=Timer.ONE_SHOT, period=BUZZ_OFF_TIME_MS, callback=self.handler)
        self.state   = True
        self.buzzing = False
        self.handler(None)

    def handler(self, timer):
        if self.state == False:
            return
        
        if self.buzzing: # then stop buzzing
            self.buzzer.duty_u16(0)
            self.buzzing = False
            self.timer.init(mode=Timer.ONE_SHOT, period=BUZZ_OFF_TIME_MS, callback=self.handler)
        else:  # start buzzing
            self.buzzer.duty_u16(BUZZ_DUTY_CYCLE)
            self.buzzing = True
            self.timer.init(mode=Timer.ONE_SHOT, period=BUZZ_ON_TIME_MS, callback=self.handler)

