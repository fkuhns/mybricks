from machine import Pin
from utime import sleep

LED_PIN          =  7
SOUND_SENSOR_PIN =  1

# Sound level sensor on pin 1
sensor = Pin(SOUND_SENSOR_PIN, Pin.IN)
led    = Pin(LED_PIN, Pin.OUT)

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

