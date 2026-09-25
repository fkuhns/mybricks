from machine import Pin, I2C
from utime import sleep
from picobricks import MotorDriver, NEC_16, IR_RX
from utime import sleep, sleep_ms
from ssd1306 import SSD1306_I2C
import sys


#############################################################################
# I2C
#############################################################################
I2C_ID       = 0
I2C_SDA_PIN  = 4
I2C_SCL_PIN  = 5
I2C_MAX_TRIES = 3

#############################################################################
# IR
#############################################################################
IR_PIN = 0
ir_rx  = False
ir_cmd = 0x00

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

    ir_rx  = False
    code   = ir_cmd
    ir_cmd = 0

    if   code == IR_RX.number_up:
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
        oled_update_err("IR cmd not impl")
    sleep_ms(100)
    oled_show()

#############################################################################
# Motors
#############################################################################
MOTOR_MAX_SPEED  = 255
MOTOR_MIN_SPEED  =   0
MOTOR_TURN_SPEED = 150
MOTOR_DEF_SPEED  = 200

MOTOR_MAX_TRIES = I2C_MAX_TRIES

def set_motor(ctrl, mid, speed, direction):
    for i in range(MOTOR_MAX_TRIES):
        try:
            ctrl.dc(mid, speed, direction)
            return True
        except OSError as e:
            print("set_motor error (try {} of {}): {}".format(i, I2C_MAX_TRIES, e))
            sleep_ms(100)
    print("### Unable to set motor speed and direction, reset i2c env")
    reset_i2c_env()
    sleep_ms(100)
    return False

def forward(speed=MOTOR_DEF_SPEED):
    global motor, motors_state
    motors_state = "Forward"
    set_motor(motor, 1, speed, 0)
    set_motor(motor, 2, speed, 0)
    oled_update_motor("m1=Fwd, m2=Fwd")

def backward(speed=MOTOR_DEF_SPEED):
    global motor, motors_state
    motors_state = "Backward"
    set_motor(motor, 1, speed, 1)
    set_motor(motor, 2, speed, 1)
    oled_update_motor("m1=Mkwd, m2=Bkwd")

def turn_right(speed=MOTOR_DEF_SPEED):
    global motor, motors_state
    motors_state = "Right"
    set_motor(motor, 1, speed, 0)
    set_motor(motor, 2, speed, 1)
    oled_update_motor("m1=Fwd, m2=Bkwd")

def turn_left(speed=MOTOR_DEF_SPEED):
    global motor, motors_state
    motors_state = "Left"
    set_motor(motor, 1, speed, 1)
    set_motor(motor, 2, speed, 0)
    oled_update_motor("m1=Bkwd, m2=Fwd")

def stop_motors():
    global motor, motors_state
    motors_state = "Stopped"
    set_motor(motor, 1, 0, 0)
    set_motor(motor, 2, 0, 0)
    oled_update_motor("m1=Stop, m2=Stop")

def check_motors():
    stop_motors()
    oled_show()
    sleep(1)
    #
    forward()
    oled_show()
    sleep(1)
    #
    backward()
    oled_show()
    sleep(1)
    #
    turn_right()
    oled_show()
    sleep(1)
    #
    turn_left()
    oled_show()
    sleep(1)
    #
    stop_motors()
    oled_show()
    sleep(1)
    #
    print("Done")

#############################################################################
# OLED
#############################################################################
OLED_I2C_ADDR = 0x3c

OLED_WIDTH       = 128 # 16 chars within a row
OLED_HEIGHT      =  64 #  8 chars within a column
OLED_CHAR_SIZE   =   8
OLED_ROW_CHARS   =  16 # OLED_WIDTH // OLED_CHAR_SIZE
OLED_ROW_CENTER  = OLED_WIDTH // 2
OLED_ROW_HEIGHT  = 16
OLED_MAX_TRIES   = I2C_MAX_TRIES

# Chars per Row: 16
# Row 1: | FK Car|
# Row 2: | motor state |
# Row 3: | Errors |
oled_buf = [["row 1", 0, 0], ["row 2", 0, OLED_ROW_HEIGHT], ["row 3", 0, 2 * OLED_ROW_HEIGHT]]

def _oled_show():
    global oled
    for i in range(MOTOR_MAX_TRIES):
        try:
            oled.show()
            return True
        except OSError as e:
            oled_update_err("oled show failed")
            print("oled_show: {}".format(e))
        sleep_ms(100)
    print("oled.show() failed ... reset i2c env")
    reset_i2c_env()
    sleep_ms(100)
    return False

def oled_clear():
    global oled
    oled.fill(0)
    return _oled_show()

def oled_show():
    global oled, oled_buf

    oled.fill(0)
    for row in oled_buf:
        oled.text(row[0], row[1], row[2])

    return _oled_show()

def oled_update_row(row, txt):
    global oled_buf
    tlen    = len(txt)
    xstart  = 0
    yoffset = (row - 1) * OLED_ROW_HEIGHT

    if tlen < OLED_ROW_CHARS:
        xstart  = OLED_ROW_CENTER - ((tlen * OLED_CHAR_SIZE) // 2)
    else: # tlen >= OLED_ROW_CHARS:
        txt  = txt[:OLED_ROW_CHARS]
        xstart = 0
    
    oled_buf[row-1][0] = txt
    oled_buf[row-1][1] = xstart
    oled_buf[row-1][2] = yoffset

    #oled.fill_rect(xstart, yoffset, 128, 8, 0)
    #oled.text(txt, xstart, yoffset)

def oled_update_hdr():
    txt = "Car FK"
    oled_update_row(1, txt)

def oled_update_motor(txt):
    oled_update_row(2, txt)

def oled_update_err(txt):
    oled_update_row(3, txt)

def oled_init_buf():
    oled_update_hdr()
    oled_update_motor("Motors: init")
    oled_update_err("Status: Good")

def reset_i2c_env():
    init_i2c_env()

def init_i2c_env():
    global oled, motor, i2c
    i2c  = I2C(I2C_ID, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN))
    sleep_ms(100)

    oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, OLED_I2C_ADDR)
    oled_init_buf()
    sleep_ms(100)

    # Motor controller is address 0x22, its hard coded in the MotorDriver class.
    motor = MotorDriver(i2c)
    sleep_ms(100)
    stop_motors()
    sleep_ms(100)

def init_ir_env():
    global ir, ir_cmd, ir_rx
    ir_cmd = 0
    ir_rx  = False
    ir     = NEC_16(Pin(IR_PIN, Pin.IN), ir_callback)



#============================================================================

def main():
    global oled, motor, ir_cmd, ir_rx, ir, i2c

    init_i2c_env()
    init_ir_env()

    oled_show()

    # check_motors()
    # sys.exit(1)
    while True:
        try:
            process_ir()
            sleep_ms(100)
        except OSError as e:
            print("Caught an OS error, continuing: ", e)
        except KeyboardInterrupt as e:
            print("Keyboard interrupt ... exiting: ", e)
            stop_motors()
            oled_clear()
            sys.exit(0) #return
        except Exception as e:
            print("Caught an unexpected exception, exiting: ", e)
            stop_motors()
            oled_clear()
            sys.exit(1) #return
        

if __name__ == "__main__":
    main()