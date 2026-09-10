from machine import Pin, I2C
from picobricks import MotorDriver, SHTC3
import utime

TEMP_LIMIT = 20

i2c    = I2C(0, scl=Pin(5), sda=Pin(4))
motor  = MotorDriver(i2c)
sensor = SHTC3(i2c) 

print(i2c.scan())
print("Sensor: {}".format(sensor))

motor.dc(2,0,0)

while True:
	temp = sensor.temperature()
	print("Temp: {}".format(temp))
	if temp >= TEMP_LIMIT:
		print("Temp is above limit, turning on cooler")
		print("Writeto: ", motor.dc(2, 100, 0)) # DC Number, Speed and Direction
	else:
		print("Temp is within limit, turning off cooler")
		print("Writeto: ", motor.dc(2, 0, 0)) # DC Number, Speed and Direction
