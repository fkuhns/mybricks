from machine import Pin, PWM, Timer
from utime import sleep # sleep

# Buzzer GPIO Pin number
BUZZ_PIN = 20
BUZZ_DUTY_CYCLE = 5000

BUZZ_ON_TIME_MS = 500
BUZZ_OFF_TIME_MS = 500

BUZZ_STATE_RUNNING = 0x01
BUZZ_STATE_BUZZING = 0x02

DEBUG = const(0)

class Buzzer():
    def __init__(self, debug):
        self.state   = 0x00
        self.buzzer  = PWM(Pin(BUZZ_PIN, Pin.OUT))
        self.buzzer.freq(500)
        self.timer   = Timer(-1)
        self.DEBUG   = debug

    def off(self):
        if not (self.state & BUZZ_STATE_RUNNING):
            return
        
        if self.DEBUG:
            print("Buzzer off")

        self.timer.deinit() # no exceptions
        self.buzzer.duty_u16(0) # value or type errors
        self.state = 0x00

    def on(self):
        if self.state & BUZZ_STATE_RUNNING:
            return
        
        if self.DEBUG:
            print("Buzzer on")

        #self.timer.init(mode=Timer.ONE_SHOT, period=BUZZ_OFF_TIME_MS, callback=self.handler)
        self.state = BUZZ_STATE_RUNNING
        self.handler(None)

    def handler(self, timer):
        # No exceptions"
        if not (self.state & BUZZ_STATE_RUNNING):
            return
        
        if self.state & BUZZ_STATE_BUZZING: # then stop buzzing
            self.buzzer.duty_u16(0)
            self.state = self.state & ~BUZZ_STATE_BUZZING
            self.timer.init(mode=Timer.ONE_SHOT, period=BUZZ_OFF_TIME_MS, callback=self.handler)
        else:  # start buzzing
            self.buzzer.duty_u16(BUZZ_DUTY_CYCLE)
            self.state = self.state | BUZZ_STATE_BUZZING
            self.timer.init(mode=Timer.ONE_SHOT, period=BUZZ_ON_TIME_MS, callback=self.handler)

