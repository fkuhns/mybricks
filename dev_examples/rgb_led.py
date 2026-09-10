from machine import Pin, ADC
from picobricks import  WS2812
from utime import sleep

RGB_LED_PIN =  6
# NeoPixel RGB LED WS2812
neo = WS2812(RGB_LED_PIN, brightness=0.4)

neo.pixels_fill((255, 0, 0))
neo.pixels_show()
sleep(0.5)

neo.pixels_fill((0, 255, 0))
neo.pixels_show()
sleep(0.5)

neo.pixels_fill((0, 0, 255))
neo.pixels_show()
sleep(0.5)

neo.pixels_fill((100, 100, 0))
neo.pixels_show()
sleep(1)

neo.pixels_fill((0, 100, 50))
neo.pixels_show()
sleep(1)

neo.pixels_fill((100, 0, 50))
neo.pixels_show()
sleep(1)

neo.pixels_fill((100, 100, 100))
neo.pixels_show()
sleep(1)

neo.pixels_fill((0,0,0))  #turn off the RGB
neo.pixels_show()
sleep(0.5)