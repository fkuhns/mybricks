from machine import Pin, I2C
from picobricks import MotorDriver
from utime import sleep

I2C_SDA_PIN =  4
I2C_SCL_PIN =  5
MOTOR_ID = 2

i2c   = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN))
motor = MotorDriver(i2c)

print(i2c.scan())

sleep(1)
motor.dc(MOTOR_ID,0,0)
sleep(1)

try:
    for speed in range(10, 100, 10):
        #print("Setting speed to {}".format(speed))
        motor.dc(MOTOR_ID, speed, 0)
        sleep(1)
    motor.dc(MOTOR_ID, 0, 0)
    sleep(1)

except KeyboardInterrupt:
    motor.dc(MOTOR_ID, 0, 0)
    print("Keyboard interrupt received")
except Exception as e:
     print("Program terminating with e: ", e)
    