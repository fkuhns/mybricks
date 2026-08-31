from machine import Pin,I2C
from picobricks import SHTC3
import utime

I2C_ID      =  0
I2C_SDA_PIN =  4
I2C_SCL_PIN =  5

I2C_SHTC3_ADDR = 0x70

i2c = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN))

shtc3 = SHTC3(i2c, I2C_SHTC3_ADDR)

current_time=utime.time()
while True:
    utime.sleep(1)
    if utime.time() - current_time >= 3:
        current_time = utime.time()
        temp = shtc3.temperature() * 1.8 + 32 # convert c to fahrenheit
        humid = shtc3.humidity() # percentage
        print("Temp = ", temp, "Humidity = ", humid)