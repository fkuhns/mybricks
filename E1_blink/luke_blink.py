
from machine import Pin
import utime

LED_PIN = 7
led = Pin (LED_PIN, Pin.OUT)

try:
    while True:
        led.toggle()
        utime.sleep(0.5)
except KeyboardInterrupt:
    led.value(0)

except Exception as e:
    print("exception ", e)
    led.value(0)
    