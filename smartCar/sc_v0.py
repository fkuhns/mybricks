from machine import Pin, I2C, SoftI2C
from utime import sleep
from picobricks import MotorDriver, NEC_16, IR_RX
from utime import sleep, sleep_ms
from ssd1306 import SSD1306_I2C

#############################################################################
# I2C
#############################################################################
I2C_ID       = 0
I2C_SDA_PIN  = 4
I2C_SCL_PIN  = 5

#############################################################################
# IR
#############################################################################
IR_PIN = 0

def ir_callback(cmd, addr, _):
    global ir_cmd, ir_rx
    if cmd > 0:
        ir_cmd = cmd
        ir_rx  = True
        print('IR -> Data: 0x{:02x} Addr: 0x{:04x}'.format(cmd, addr))

def process_ir():
    global ir_cmd, ir_rx
    if not ir_rx:
        return

    ir_rx = False
    code = ir_cmd
    ir_cmd = 0

    if code == IR_RX.number_up:
        forward()
    elif code == IR_RX.number_down:
        backward()
    elif code == IR_RX.number_left:
        turn_left()
    elif code == IR_RX.number_right:
        turn_right()
    elif code == IR_RX.number_ok:
        stop_motors()
    else:
        print("Not implemented IR Code: 0x{:02x}".format(code))
    show_state()

#############################################################################
# Motors
#############################################################################
MOTOR_MAX_SPEED  = 255
MOTOR_MIN_SPEED  =   0
MOTOR_TURN_SPEED = 200
MOTOR_DEF_SPEED  = 100

I2C_MAX_RETRIES = 3

# Idle, Forward, Backward, Left, Right, Stopped"
car_state = "idle"

def set_motor(ctrl, mid, speed, direction):
    for i in range(I2C_MAX_RETRIES):
        try:
            ctrl.dc(mid, speed, direction)
            return True
        except OSError as e:
            print("*** I2C motor write error (try {} of {}): {}".format(i, I2C_MAX_RETRIES, e))
            sleep_ms(2)
    print("### Unable to set motor speed and direction")
    return False

def forward(speed=MOTOR_DEF_SPEED):
    global motor, car_state
    car_state = "Forward"
    set_motor(motor, 1, speed, 0)
    set_motor(motor, 2, speed, 0)
    # motor.dc(1, speed, 0)
    # motor.dc(2, speed, 0)

def backward(speed=MOTOR_DEF_SPEED):
    global motor, car_state
    car_state = "Backward"
    set_motor(motor, 1, speed, 1)
    set_motor(motor, 2, speed, 1)
    # motor.dc(1, speed, 1)
    # motor.dc(2, speed, 1)

def turn_right(speed=MOTOR_DEF_SPEED):
    global motor, car_state
    car_state = "Right"
    set_motor(motor, 1, speed, 0)
    set_motor(motor, 2, speed, 1)
    # motor.dc(1, speed, 0)
    # motor.dc(2, speed, 1)

def turn_left(speed=MOTOR_DEF_SPEED):
    global motor, car_state
    car_state = "Left"
    set_motor(motor, 1, speed, 1)
    set_motor(motor, 2, speed, 0)
    # motor.dc(1, speed, 1)
    # motor.dc(2, speed, 0)

def stop_motors():
    global motor, car_state
    car_state = "Stopped"
    set_motor(motor, 1, 0, 0)
    set_motor(motor, 2, 0, 0)
    # motor.dc(1, 0, 0)
    # motor.dc(2, 0, 0)

def check_motors():
    stop_motors()
    show_state()
    sleep(1)
    #
    forward()
    show_state()
    sleep(1)
    #
    backward()
    show_state()
    sleep(1)
    #
    turn_right()
    show_state()
    sleep(1)
    #
    turn_left()
    show_state()
    sleep(1)
    #
    stop_motors()
    show_state()
    sleep(1)
    #
    print("Done")

#############################################################################
# OLED
#############################################################################
OLED_I2C_ADDR = 0x3c

OLED_WIDTH       = 128 # 16 chars within a row
OLED_HEIGHT      =  64 #  8 chars within a column
OLED_CHAR_SIZE   = 8
OLED_ROW_CENTER  = OLED_WIDTH // 2
OLED_ROW_HEIGHT  = 12

def oled_show(oled):
    #for i in range(I2C_MAX_RETRIES):
    try:
        oled.show()
        return True
    except OSError as e:
        # print("*** I2C OLED write error (try {} of {}): {}".format(i, I2C_MAX_RETRIES, e))
        print("*** I2C OLED write error: {}".format(e))
        # sleep_ms(10)
    print("\t### OLED.show() Failed")
    return False
    

def show_state():
    global oled, car_state
    oled.fill(0)
    if not oled_show(oled):
        print("*** show_state: Unable to clear screen")
        #return False

    # ROW 1
    txt     = "Car FK"
    tlen    = (len(txt) * OLED_CHAR_SIZE) // 2
    xstart  = OLED_ROW_CENTER - tlen
    yoffset = 0
    oled.text(txt, xstart, yoffset)
    # Row 2
    txt     = "State: " + car_state
    tlen    = (len(txt) * OLED_CHAR_SIZE) // 2
    xstart  = OLED_ROW_CENTER - tlen
    yoffset += OLED_ROW_HEIGHT
    # print("\tText ", txt, "chars ", len(txt)*OLED_CHAR_SIZE,"xstart ", xstart, " yoffset ", yoffset)
    oled.text(txt, xstart, yoffset)
    if not oled_show(oled):
        print("*** show_state: failed!")
        return False
    return True

#============================================================================

i2c  = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN))
oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, OLED_I2C_ADDR)
# Motor controller is address 0x22, its hard coded in the MotorDriver class.
motor = MotorDriver(i2c)

ir_cmd = 0
ir_rx  = False
ir     = NEC_16(Pin(IR_PIN, Pin.IN), ir_callback)
show_state()
sleep(0.5)
stop_motors()
show_state()
sleep(0.5)

check_motors()

while True:
    process_ir()
    sleep_ms(50)
    