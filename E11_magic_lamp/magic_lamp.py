from machine import Pin
from utime import sleep

sensor = Pin( 1, Pin.IN)
led    = Pin( 7, Pin.OUT)

led.value(0)

try:
    while True:
        #print(sensor.value())
        if sensor.value() == 1:
            led.toggle()
            sleep(0.5) # ignore any noise in the sensor value
        # else:
        #     led.value(0)
        #     sleep(0.5) # ignore any noise in the sensor value
except KeyboardInterrupt:
    print("Program stopped by user")
    led.value(0) 

