from machine import Pin, I2C
from picobricks import MotorDriver, SHTC3
from utime import sleep

TEMP_LIMIT = 25

i2c    = I2C(0, scl=Pin(5), sda=Pin(4))
motor  = MotorDriver(i2c)
sensor = SHTC3(i2c) 

print(i2c.scan())
print("Sensor: {}".format(sensor))

motor.dc(2,0,0)

try:
	while True:
		#print("Reading temperature again ...")
		temp = sensor.temperature()
		#print("Temp: {}".format(temp))
		if temp >= TEMP_LIMIT:
			motor.dc(2, 100, 0)
			print("Temp is above limit, turning on cooler")
		else:
			motor.dc(2, 0, 0)
			print("Temp is within limit, turning off cooler")
		sleep(1)

except KeyboardInterrupt:
	motor.dc(2, 0, 0)
	print("Keyboard interrupt received, turning off cooler")

