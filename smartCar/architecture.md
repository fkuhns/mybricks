# Smart car v6 architecture

`main.py` is the application entrypoint. Its `main()` constructs `MyApp` in
distance mode, runs the application loop, and shuts the car down before
resetting the board.

```mermaid
flowchart TD
    entry["smartCar/main.py<br/>main()"] --> app["MyApp"]
    app --> loop["MyApp.run()<br/>main loop and mode dispatch"]
    loop --> distance["MyApp.run_dist()<br/>autonomous distance behavior"]
    loop --> infrared["MyApp.run_ir()<br/>remote command handling"]
    loop --> controls["Button / Pot<br/>mode gate and turn delay"]
    app --> shutdown["MyApp.shutdown()<br/>stop motors and refresh display"]

    subgraph common["Library modules in common/"]
        common_mod["common.py<br/>Button, Pot"]
        ultrasonic_mod["usonic.py<br/>UltrasonicSensor"]
        ir_mod["ir_sensor.py<br/>NEC_8, IR_RX"]
        i2c_mod["i2c_dev.py<br/>I2cCtl, MotorsI2c, OledI2c"]
        motor_lib["picobricks.py<br/>MotorDriver"]
        display_lib["ssd1306.py<br/>SSD1306_I2C"]
        buzzer_lib["buzzer.py<br/>Buzzer"]
        resources["resources.py<br/>(not used by main.py)"]
    end

    app --> common_mod
    app --> ultrasonic_mod
    app --> ir_mod
    app --> i2c_mod
    controls -. uses .-> common_mod
    distance --> ultrasonic_mod
    distance --> i2c_mod
    infrared --> ir_mod
    infrared --> i2c_mod
    shutdown --> i2c_mod

    i2c_mod --> motor_lib
    i2c_mod --> display_lib
    i2c_mod --> buzzer_lib

    subgraph hardware["Board and attached hardware"]
        gpio["GPIO / ADC<br/>button, potentiometer, ultrasonic sensor, IR receiver"]
        bus["I²C bus<br/>motor controller and OLED"]
        motor["Motors"]
        oled["SSD1306 OLED"]
        sound["Buzzer"]
    end

    common_mod --> gpio
    ultrasonic_mod --> gpio
    ir_mod --> gpio
    motor_lib --> bus
    display_lib --> bus
    buzzer_lib --> sound
    bus --> motor
    bus --> oled
```

The libraries also rely on MicroPython platform modules such as `machine` and
`utime`, which are provided by the board runtime rather than this repository.
