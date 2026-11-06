from machine import Pin, time_pulse_us
import time
from common import US_TRIGGER_PIN, US_ECHO_PIN, DEBUG_ERROR, DEBUG_INFO, DEBUG_NONE, DEBUG_VERB, DEBUG_WARN


## Ultrasonic distance sensor library for Raspberry Pi
# HC-SR04 with CS100A is a common ultrasonic distance sensor that uses sound 
# waves to measure distance.

US_SPEED_IPUS  = 0.01359876  # Inches per microsecond
# Not used ... US_DIST_MAX    = 288.00  # 144 inches = 12 feet
US_MAX_ECHO_US = 35_000 # Out of range lock is 33ms => no timeouts?

_DEBUG = DEBUG_NONE

class UltraSonicTimeout(Exception):
    pass

class UltrasonicSensor:
    # Appears to be a newer CS100A board with extended range.
    # Max range 560cm (some claim 600cm). 560cm => 33ms round trip time.
    # - Out of range lock: 
    #   a) If no echo is received within 33ms the echo pin is pulled low
    #   b) Chip will maintain this low for until next valid trigger
    # - Add buffer of 30-50ms before pulling the trigger hi again.
    # - The recommended time between measurements is 60ms
    # - Min trigger signal is 10us. After valid trigger, echo is held low
    #   for a "few hundred us" before it is brought hi. It remains hi
    #   until either an echo is received or the HW timeout of 33ms occurs.
    # - You time the duration the echo is held hi
    def __init__(self, trigger_pin=US_TRIGGER_PIN, echo_pin=US_ECHO_PIN):
        self.trig = Pin(trigger_pin, Pin.OUT)
        self.echo = Pin(echo_pin, Pin.IN)
        # At 75 degrees F, the speed of sound is 1,133.23 fps
        # 1,133.23 ft/sec * 12 in/ft * 1 sec/1,000,000 us = 0.01359876 in/us
        # or 13.59876 in/ms.
        # So HW timeout of 33ms (round trip time) -> 224" one-way (18' 8')
        # x" oneway => (2*x)/0.01359876 = time to travel
        # 12' = 144" => 21ms round trip
        # 10' = 120" => 18ms round trip
        # 20' = 240" => 35ms > HW timeout of 33ms
        self.tout_us = US_MAX_ECHO_US 

    def get_distance(self):
        """
        Returns the distance in inches by default.
        """
        # Code to trigger the ultrasonic sensor and measure the time taken.
        # The echo Pin is normally low
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
        # Since the CS100A is supposed to have a 33ms out of range lock, 
        # and tout is 35ms, there, in principle, should not be timeouts for rx'ing the echo
        duration = time_pulse_us(self.echo, 1, self.tout_us) 
        if duration < 0:
            raise UltraSonicTimeout("Ultrasonic timeout error")

        # Calculate distance in inches.
        distance = (duration / 2.0) * US_SPEED_IPUS

        if _DEBUG >= DEBUG_VERB:
            print(duration, "us, ", distance, "in")
        
        return distance
    
    