from machine import Pin,I2C
from picobricks import SHTC3, SSD1306_I2C
import utime #time library
import time

I2C_ID      =  0
I2C_SDA_PIN =  4
I2C_SCL_PIN =  5

# OLED specific constants
OLED_WIDTH  = 128
OLED_HEIGHT =  64

I2C_OLED_ADDR  = 0x3c
I2C_SHTC3_ADDR = 0x70

def clear_oled(oled):
    oled.fill(0)#clear OLED
    oled.show()

def doit():
    # create object to represent the i2c bus
    i2c = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN))

    # addrs = i2c.scan()
    # Addrs: 0x3c (60), 0x22 (34), 0x70 (112)
    # 	0x3c = oled
    # 	0x22 = Motor drive
    # 	0x70 = Temp/Humid (shtc3)
    # print("I2C device addresses")
    # for a in addrs:
    #     print("\t%d = 0x%0x" % (a,a))

    # create object for the SHTC3 device on i2c bus (temp & humid)
    shtc3 = SHTC3(i2c, I2C_SHTC3_ADDR)  

    # create object for the SSD1306 on the i2c bus (mini display screen)
    oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, I2C_OLED_ADDR)

    current_time=utime.time()
    #print("Start:\n\tTemperature = %df, Humidity = %d%%" % (shtc3.temperature() * 1.8 + 32, shtc3.humidity()))
    try:
        while True:
            time.sleep(1)
            if utime.time() - current_time >= 3:
                current_time = utime.time()
                
                #print("Measuring")
                temp = shtc3.temperature() * 1.8 + 32 # convert c to fahrenheit
                humid = shtc3.humidity() # percentage
                #print("\tTemperature = %df, Humidity = %d%%" % (temp, humid))
                
                #oled.fill(0)#clear OLED
                #oled.show()
                clear_oled(oled)
                
                oled.text("Temperature: ", 15, 10)#print "Temperature: " on the OLED at x=15 y=10
                oled.text(str(int(temp)), 55, 25)
                oled.text("Humidity: ", 30, 40)
                oled.text(str(int(humid)), 55, 55)
                oled.show()#show on OLED
                
                utime.sleep(0.5)#wait for a half second
    except KeyboardInterrupt:
        print("Keyboard interrupt ... Program stopped by user")
        clear_oled(oled)
    except Exception as e:
        print("Program terminating with e: ", e)
        clear_oled(oled)    
    
doit()
