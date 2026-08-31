from machine import Pin, ADC
from utime import sleep

# Global constants
LDR_PIN     = 27

## ADC
GPIO_VOLT_MAX   = 3.3
LDR_LOW_LIGHT = 10000

ldr = ADC(Pin(LDR_PIN))
dark = None

while True:
    # Note, raw increases when brightness decreases
    raw = ldr.read_u16()
    print("dark = ", dark, "raw = ", raw)
    
    if (dark is None or dark == False) and raw > LDR_LOW_LIGHT:
        print("Low Light/Dark, raw = {}".format(raw))
        dark = True
    elif (dark is None or dark == True) and raw < LDR_LOW_LIGHT:
        dark = False
        print("Bright, raw = ", raw)
   
    sleep(1)