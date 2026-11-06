from machine import Pin, PWM, Timer
from common import BUZZ_PIN, DEBUG_ERROR, DEBUG_INFO, DEBUG_NONE, DEBUG_VERB, DEBUG_WARN

# Buzzer GPIO Pin number
BUZZ_DUTY_CYCLE = 5000

BUZZ_ON_TIME_MS  = 500
BUZZ_OFF_TIME_MS = 500
BUZZ_PERIOD_MS   = 500
BUZZ_FREQ        = 500

BUZZ_STATE_OFF     = 0x00
BUZZ_STATE_ENABLED = 0x01
BUZZ_STATE_BUZZING = 0x02
BUZZ_STATE_MASK    = 0x03 # just two bits are needed

DEBUG = const(0)

class Buzzer():
    def __init__(self, debug):
        self.state   = BUZZ_STATE_OFF
        self.buzzer  = PWM(Pin(BUZZ_PIN, Pin.OUT))
        self.buzzer.freq(BUZZ_FREQ)
        self.timer   = Timer(-1)
        self.err_cnt = 0 # number of times timer.init() raised
        self.DEBUG   = debug

    def off(self):
        if self.state == BUZZ_STATE_OFF:
            return
        
        if self.DEBUG:
            print("Buzzer off")

        self.timer.deinit()     # no exceptions
        self.buzzer.duty_u16(0) # value or type errors
        self.state = BUZZ_STATE_OFF

    def on(self):
        if self.state & BUZZ_STATE_ENABLED:
            return
        
        if self.DEBUG:
            print("Buzzer on")

        self.state = BUZZ_STATE_ENABLED # enabled but not buzzing
        self.handler(None) # start buzzing right away, no exceptions
        try:
            self.timer.init(mode=Timer.PERIODIC, period=BUZZ_PERIOD_MS, callback=self.handler)
        except OSError as e:
            # the buzzer stays on until off() is called
            self.err_cnt += 1
            if self.DEBUG:
                print("Buzzer.on: Error initializing timer:", e)
           # Buzzer is already on from handler call. self.buzzer.duty_u16(BUZZ_DUTY_CYCLE)

    def handler(self, timer):
        # No exceptions
        if self.state == BUZZ_STATE_OFF:
            return

        # Note: timer.init() may raise OSError
        if self.state & BUZZ_STATE_BUZZING: # buzzer is on, stop buzzing
            self.buzzer.duty_u16(0)
            self.state = (self.state & ~BUZZ_STATE_BUZZING) & BUZZ_STATE_MASK
            #self.timer.init(mode=Timer.ONE_SHOT, period=BUZZ_OFF_TIME_MS, callback=self.handler)
        elif self.state & BUZZ_STATE_ENABLED:  # buzzer is off, start buzzing
            self.buzzer.duty_u16(BUZZ_DUTY_CYCLE)
            self.state = (self.state | BUZZ_STATE_BUZZING) & BUZZ_STATE_MASK
            #self.timer.init(mode=Timer.ONE_SHOT, period=BUZZ_ON_TIME_MS, callback=self.handler)
