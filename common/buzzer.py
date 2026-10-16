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
        self.buzz = False
        self.buzzer = PWM(Pin(BUZZ_PIN, Pin.OUT))
        self.buzzer.freq(500)
        self.timer = Timer(-1)
        self.debug = debug

    def off(self):
        if self.buzz == False:
            return
        if self.debug:
            print("Buzzer off")
        self.timer.deinit()
        self.buzz = False
        self.buzzer.duty_u16(0)

    def on(self):
        if self.buzz == True:
            return
        if self.debug:
            print("Buzzer on")
        self.buzz = False
        self.timer.init(mode=Timer.ONE_SHOT, period=500, callback=self.handler)

    def handler(self, timer):
        if self.buzz:
            #print("\tBuzz == True")
            self.buzzer.duty_u16(0)
            self.buzz = False
            self.timer.init(mode=Timer.ONE_SHOT, period=BUZZ_OFF_TIME_MS, callback=self.handler)
        else:
            #print("\tBuzz == False")
            self.buzzer.duty_u16(BUZZ_DUTY_CYCLE)
            self.buzz = True
            self.timer.init(mode=Timer.ONE_SHOT, period=BUZZ_ON_TIME_MS, callback=self.handler)

# buz = Buzzer()
# buz.on()
# sleep(5)
# buz.off()
# sleep(1)
