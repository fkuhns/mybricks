# Smart Car Class Diagram

The diagram centers on `MyApp` and shows its application collaborators, class inheritance, and key object relationships.

```mermaid
classDiagram
    class MyApp
    class AppException
    class Device
    class Button
    class Pot

    class I2cCtl
    class I2cBus
    class OledI2c
    class I2cException
    class I2cBusException
    class I2cNackException
    class SSD1306_I2C

    class CarMotors
    class MotorDriver
    class Buzzer
    class RingBuffer
    class MotorException

    class CarDist
    class UltrasonicSensor
    class DistException
    class UltraSonicTimeout

    class IRMgr
    class IR_RX
    class NEC_8

    Exception <|-- AppException
    Exception <|-- I2cException
    I2cException <|-- I2cBusException
    I2cException <|-- I2cNackException
    Exception <|-- MotorException
    Exception <|-- DistException
    Exception <|-- UltraSonicTimeout

    Device <|-- I2cCtl
    Device <|-- OledI2c
    Device <|-- CarMotors
    Device <|-- CarDist
    Device <|-- IR_RX
    IR_RX <|-- NEC_8
    Device <|-- IRMgr

    MyApp *-- "1" I2cCtl : creates
    MyApp *-- "1" OledI2c : creates
    MyApp *-- "1" CarMotors : creates
    MyApp o-- "0..1" CarDist : mode-dependent
    MyApp o-- "0..1" IRMgr : mode-dependent
    MyApp o-- "0..1" Button : mode-dependent
    MyApp o-- "0..1" Pot : mode-dependent
    MyApp ..> Device : starts and stops device list
    MyApp ..> AppException : catches

    I2cCtl ..> I2cBus : creates
    OledI2c --> I2cBus : uses
    OledI2c *-- SSD1306_I2C : wraps

    CarMotors --> I2cBus : uses
    CarMotors *-- MotorDriver : creates
    CarMotors *-- RingBuffer : command queue
    CarMotors o-- Buzzer : optional

    CarDist --> CarMotors : queues motor commands
    CarDist --> OledI2c : updates display
    CarDist *-- UltrasonicSensor : default sensor
    CarDist ..> UltraSonicTimeout : handles
    CarDist ..> DistException : may raise

    IRMgr --> CarMotors : queues motor commands
    IRMgr --> OledI2c : updates display
    IRMgr *-- NEC_8 : creates receiver
```

`CarDist` and `IRMgr` are created only when their modes are enabled. `Button` and `Pot` are also mode-dependent; the buzzer is optional. The `MyApp.devices` lifecycle list contains the I²C controller, OLED, motors, and any enabled distance/IR devices. The button and potentiometer are not in that list.

`SSD1306_I2C` is an external display-driver class wrapped by `OledI2c`.
