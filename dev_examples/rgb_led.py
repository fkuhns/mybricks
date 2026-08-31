from machine import Pin, ADC
from picobricks import  WS2812
from utime import sleep

RGB_LED_PIN =  6
rgb_led = WS2812(RGB_LED_PIN, brightness=0.4)



rgb_led.pixels_fill((255, 0, 0))
rgb_led.pixels_show()
sleep(0.5)

rgb_led.pixels_fill((0, 255, 0))
rgb_led.pixels_show()
sleep(0.5)

rgb_led.pixels_fill((0, 0, 255))
rgb_led.pixels_show()
sleep(0.5)

rgb_led.pixels_fill((100, 100, 0))
rgb_led.pixels_show()
sleep(1)

rgb_led.pixels_fill((0, 100, 50))
rgb_led.pixels_show()
sleep(1)

rgb_led.pixels_fill((100, 0, 50))
rgb_led.pixels_show()
sleep(1)

rgb_led.pixels_fill((100, 100, 100))
rgb_led.pixels_show()
sleep(1)

rgb_led.pixels_fill((0,0,0))  #turn off the RGB
rgb_led.pixels_show()
sleep(0.5)