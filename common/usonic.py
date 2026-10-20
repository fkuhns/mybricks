from machine import Pin, time_pulse_us
import time


## Ultrasonic distance sensor library for Raspberry Pi
# HC-SR04 with CS100A is a common ultrasonic distance sensor that uses sound 
# waves to measure distance.
# Key details of the HC-sr04 with CSa00A:
# - It has a trigger pin and an echo pin. The trigger pin is used to send a 
#   pulse, and the echo pin receives the reflected pulse. The time taken
#   for the pulse to return is used to calculate the distance.
# - The sensor can measure distances from 2cm to 400cm with an accuracy of
#   about 3mm.
# - It operates at a voltage of 5V and consumes about 15mA of current.
# - The sensor has a wide detection angle of about 15 degrees, which allows
#   it to detect objects in a broad area.

US_TRIGGER_PIN =   15  # GPIO pin for trigger
US_ECHO_PIN    =   14  # GPIO pin for echo

US_SPEED_IPUS  = 0.01359876  # Inches per microsecond
US_DIST_MAX    = 144.00  # 12 feet

_DEBUG = const(0)

class UltraSonicTimeout(Exception):
    pass

class UltrasonicSensor:
    def __init__(self, trigger_pin=US_TRIGGER_PIN, echo_pin=US_ECHO_PIN):
        self.trig = Pin(trigger_pin, Pin.OUT)
        self.echo = Pin(echo_pin, Pin.IN)
        # At 75 degrees F, the speed of sound is 1,133.23 fps
        # 1,133.23 ft/sec * 12 in/ft * 1 sec/1,000,000 us = 0.01359876 in/us
        # = 0.00113323 ft/usec, or 882.4 usec/ft, 2,647 us for 3 ft.
        #self.cf = 0.01359876  # Speed of sound in inches per microsecond at 75 degrees F
        # 5ms => 5.67 ft, 3ms => 3.4 ft, 
        # 8' => 7.06ms (7059 us)
        # 4' => 3.53ms (3530 us)
        # 3' => 2.6 ms (2647 us)
        # Note: the sonic pulse time out if for the round trip.
        self.tout_us = int(round(2* (US_DIST_MAX / US_SPEED_IPUS)))

    def get_distance(self):
        """
        Returns the distance in inches by default.
        FIXME: Add code for cm
        """
        # Code to trigger the ultrasonic sensor and measure the time taken.
        # The echo Pin is normally high, so first set low then high for 
        # 10 microseconds to trigger the sensor to send the ultrasound pulse.
        # Then measure the time taken for the echo to return.
        self.trig.low()
        time.sleep_us(2)
        self.trig.high()
        time.sleep_us(10)
        self.trig.low()

        # >= 0 is the time in microseconds for the echo to return
        # -2 timed out while waiting for the pin to transition into requested level
        # -1 timed out during the measurement
        duration = time_pulse_us(self.echo, 1, self.tout_us) 
        if duration < 0:
            raise UltraSonicTimeout("Ultrasonic timeout waiting for echo")

        # Calculate distance in inches.
        distance = (duration / 2.0) * US_SPEED_IPUS
        # utime.sleep(0.1) # FIXME: do I need this sleep

        if _DEBUG:
            print(duration, "us, ", distance, "in")
        
        return distance
    