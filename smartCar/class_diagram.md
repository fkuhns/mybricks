# Smart Car Class Diagrams

Five views: an overall top-down diagram, then one each for the motor control path, the IR path, the OLED path and the I²C classes.

## 1. Overall

`MyApp` is at the top, the devices it starts and stops are in the middle, and the hardware wrappers and helpers are at the bottom.

```mermaid
classDiagram
    direction TB

    class MyApp
    class Diag
    class Device {
        <<base>>
    }

    class CarDist
    class IRMgr
    class CarMotors
    class OledI2c
    class I2cCtl
    class Button
    class Pot

    class UltrasonicSensor
    class NEC_8
    class MotorDriver
    class RingBuffer
    class Buzzer
    class SSD1306_I2C
    class I2cBus

    MyApp *-- I2cCtl : creates
    MyApp *-- OledI2c : creates
    MyApp *-- CarMotors : creates
    MyApp *-- Diag : creates
    MyApp o-- "0..1" CarDist : MODE_DIST
    MyApp o-- "0..1" IRMgr : MODE_IR
    MyApp o-- "0..1" Button : MODE_BUTT
    MyApp o-- "0..1" Pot : MODE_POT

    Diag --> OledI2c : status rows
    Diag --> I2cCtl : counters
    Diag --> Button
    Diag --> Buzzer

    CarDist --> CarMotors : queues cmds
    CarDist --> OledI2c : shows zone
    IRMgr --> CarMotors : queues cmds
    IRMgr --> OledI2c : shows status

    CarDist *-- UltrasonicSensor
    IRMgr *-- NEC_8

    CarMotors *-- MotorDriver
    CarMotors *-- RingBuffer
    CarMotors *-- "0..1" Buzzer : MODE_BUZZ
    OledI2c *-- SSD1306_I2C

    I2cCtl ..> I2cBus : bus() creates
    CarMotors --> I2cBus : holds, passes on
    MotorDriver --> I2cBus : writeto
    SSD1306_I2C --> I2cBus : writeto, writevto
    I2cBus --> I2cCtl : reports failures

    Device <|-- I2cCtl
    Device <|-- OledI2c
    Device <|-- CarMotors
    Device <|-- CarDist
    Device <|-- IRMgr
```

The `MyApp.devices` list (started in order, stopped in reverse) holds the I²C controller, OLED, motors and any enabled distance/IR device. `Button`, `Pot` and `Diag` are not in it. `SSD1306_I2C` is the display driver from `ssd1306.py`. `OledI2c` is only handed the bus at construction and passes it straight to `SSD1306_I2C`; it never writes to it itself. Exception classes are shown in the focused diagrams.

## 2. Motor control path (distance, I²C, motors)

```mermaid
classDiagram
    direction TB

    class Device {
        <<base>>
    }
    class CarDist {
        +run()
        +read()
        +find_zone(dist)
        +show(dist)
        +reset()
    }
    class UltrasonicSensor {
        +get_distance()
    }
    class CarMotors {
        +add_cmd(cmd, arg)
        +run_cmds()
        +clear_cmds()
        +forward() backward()
        +turn_left() turn_right()
        +stop_motors() stop_force()
    }
    class RingBuffer {
        command queue
    }
    class MotorDriver {
        +dc(num, speed, dir)
        +servo(num, angle)
    }
    class Buzzer
    class I2cBus {
        +writeto(addr, buf)
        +writevto(addr, bufs)
        retries failed writes
    }
    class I2cCtl {
        +bus(id, tries)
        +count_fail(addr, kind)
        +handle_err(id)
        +clear_err(id)
        owns machine.I2C
    }
    class OledI2c

    class DistException
    class UltraSonicTimeout
    class MotorException
    class I2cException
    class I2cBusException
    class I2cNackException

    Device <|-- CarDist
    Device <|-- CarMotors
    Device <|-- I2cCtl

    CarDist *-- UltrasonicSensor : sonic
    CarDist --> CarMotors : add_cmd
    CarDist --> OledI2c : zone display

    CarMotors *-- RingBuffer : rbuf
    CarMotors *-- MotorDriver : mctrl
    CarMotors *-- "0..1" Buzzer : MODE_BUZZ
    CarMotors --> I2cBus : holds, passes to MotorDriver
    MotorDriver --> I2cBus : writeto

    I2cCtl ..> I2cBus : bus() creates
    I2cBus --> I2cCtl : reports failures, may reset bus

    Exception <|-- DistException
    Exception <|-- UltraSonicTimeout
    Exception <|-- MotorException
    Exception <|-- I2cException
    I2cException <|-- I2cBusException
    I2cException <|-- I2cNackException

    CarDist ..> UltraSonicTimeout : handles
    CarDist ..> DistException : may raise
    I2cBus ..> I2cException : raises when all tries fail
    CarMotors ..> MotorException : may raise
```

Flow: `CarDist.run()` reads the sonic sensor, maps the distance to a zone and queues a command with `CarMotors.add_cmd()`. `CarMotors.run_cmds()` drains the queue through `MotorDriver`, which calls `I2cBus.writeto()`. `CarMotors` itself only holds the bus and hands it to `MotorDriver`. A failed write is retried, reported to `I2cCtl`, and `I2cException` is raised if all tries fail.

## 3. IR path

```mermaid
classDiagram
    direction TB

    class Device {
        <<base>>
    }
    class IRMgr {
        +callback(cmd, addr, ext)
        +err(code)
        +ck_err_code()
        +process(cmd)
        +run()
        cmd_map: IR_CMD_MAP
    }
    class IR_RX {
        +decode(e)
        +do_callback()
        +error_function(f)
        +close()
        pin irq + Timer
    }
    class NEC_8
    class NEC_16
    class CarMotors {
        +add_cmd(cmd, arg)
    }
    class OledI2c {
        +update_row3(txt)
    }
    class Pin {
        <<machine>>
        IR_PIN
    }

    Device <|-- IRMgr
    Device <|-- IR_RX
    IR_RX <|-- NEC_8
    IR_RX <|-- NEC_16

    IRMgr *-- NEC_8 : ctrl
    NEC_8 --> Pin : irq on edges
    NEC_8 ..> IRMgr : callback(cmd, addr)
    NEC_8 ..> IRMgr : error_function(code)

    IRMgr --> CarMotors : maps cmd to motor cmd
    IRMgr --> OledI2c : shows status
```

Flow: the pin interrupt feeds `NEC_8`, which decodes frames and calls `IRMgr.callback()` (errors go to `IRMgr.err()`). `IRMgr.run()` processes the saved command through `cmd_map`, queues a motor command and updates the OLED. `NEC_8` is created once; its pin irq is only on while `IRMgr` is started. `NEC_16` is available but unused.

## 4. OLED path

```mermaid
classDiagram
    direction TB

    class Device {
        <<base>>
    }
    class MyApp {
        +display()
        rate-limited by DISPLAY_MS
    }
    class OledI2c {
        +init_buf()
        +update_row1..4(txt)
        +show()
    }
    class SSD1306_I2C {
        +fill() text() show()
        +write_cmd(cmd)
        +write_data(buf)
    }
    class I2cBus {
        tries=1
    }
    class I2cCtl {
        +handle_err()
    }
    class CarDist {
        zone row
    }
    class IRMgr {
        status row
    }
    class Diag {
        status and vsys rows
    }
    class I2cException

    Device <|-- OledI2c
    Device <|-- I2cCtl

    MyApp *-- OledI2c : creates
    MyApp ..> OledI2c : display() calls show()
    MyApp ..> I2cException : catches, backs off DISPLAY_ERR_MS

    CarDist --> OledI2c : update_row
    IRMgr --> OledI2c : update_row3
    Diag --> OledI2c : update_row

    OledI2c *-- SSD1306_I2C : _octrl
    SSD1306_I2C --> I2cBus : writeto, writevto
    OledI2c ..> I2cBus : ctor arg only, passed on
    I2cCtl ..> I2cBus : bus() creates
    I2cBus --> I2cCtl : reports failures
    I2cBus ..> I2cException : raises
```

Flow: `CarDist`, `IRMgr` and `Diag` only update text rows in the `OledI2c` buffer. `MyApp.display()` calls `show()` at most every `DISPLAY_MS`, which pushes the buffer through `SSD1306_I2C` and `I2cBus`. The OLED bus uses `tries=1` so a failing display cannot block the loop. On `I2cException` the app waits `DISPLAY_ERR_MS`, and the buffer stays marked updated so the next `show()` redraws it.

## 5. I²C classes and how `machine.I2C` is reached

```mermaid
classDiagram
    direction TB

    class CarMotors
    class MotorDriver
    class OledI2c
    class SSD1306_I2C {
        -i2c
        +write_cmd(cmd)
        +write_data(buf)
    }
    class SSD1306 {
        <<ssd1306.py>>
    }
    class FrameBuffer {
        <<framebuf>>
    }
    class I2cBus {
        -_ctl
        -_id
        -_tries
        +writeto(addr, buf)
        +writevto(addr, bufs)
        -_write(fname, addr, buf)
    }
    class I2cCtl {
        -_i2c[id] : OBJ, SCL, SDA, FREQ, TOUT
        +Errors[id] : count, last
        +fail_cnt, fails, reset_cnt
        +bus(id, tries) I2cBus
        +i2c(id) machine.I2C
        +clear_err(id)
        +handle_err(id)
        +count_fail(addr, kind)
        -_reset_i2c(id)
    }
    class I2C {
        <<machine>>
        +writeto(addr, buf)
        +writevto(addr, bufs)
    }
    class Pin {
        <<machine>>
        SCL, SDA
    }
    class I2cException
    class I2cBusException
    class I2cNackException

    CarMotors --> I2cBus : self.bus, only passed on
    CarMotors *-- MotorDriver : mctrl
    MotorDriver --> I2cBus : self.i2c, writeto
    OledI2c *-- SSD1306_I2C : _octrl
    OledI2c ..> I2cBus : ctor arg only, tries=1
    SSD1306_I2C --> I2cBus : self.i2c, writeto + writevto
    FrameBuffer <|-- SSD1306
    SSD1306 <|-- SSD1306_I2C

    I2cCtl ..> I2cBus : bus() creates one per client
    I2cBus --> I2cCtl : _ctl, held for every call
    I2cCtl *-- I2C : _i2c[id]["OBJ"], the only reference
    I2cCtl ..> Pin : builds SCL and SDA pins
    I2cBus ..> I2C : fetched per write via _ctl.i2c(id), never stored

    Exception <|-- I2cException
    I2cException <|-- I2cBusException
    I2cException <|-- I2cNackException
    I2cBus ..> I2cBusException : OSError on every try
    I2cBus ..> I2cNackException : ack count wrong on every try
```

`I2cCtl` is the sole owner of the `machine.I2C` object, held in `_i2c[id]["OBJ"]`. Nothing else holds it. `MyApp` asks `I2cCtl.bus()` for an `I2cBus`: one with default tries goes to `CarMotors`, which keeps it and passes it to `MotorDriver`; one with `tries=1` goes to `OledI2c`, which does not keep it and passes it to `SSD1306_I2C`. The classes that write (`MotorDriver` via `writeto`; `SSD1306_I2C` via `writeto` for commands and `writevto` for pixel data) call the bus, and on every write `I2cBus._write()` calls `_ctl.i2c(id)` to fetch the current `machine.I2C` and invokes `writeto` or `writevto` on it.

Because the lookup happens per write, `I2cCtl._reset_i2c()` can recover a stuck bus by clocking out SDA, then replacing `_i2c[id]["OBJ"]` with a new `I2C`. The motors, OLED and any other bus holders pick up the new object without rebinding.

On each `OSError`, `I2cBus` calls `I2cCtl.handle_err()`, and a run of errors triggers the reset. A good write calls `clear_err()`. After the last try fails, `I2cBus` calls `count_fail()` and raises `I2cBusException` (OSError) or `I2cNackException` (wrong ack count).
