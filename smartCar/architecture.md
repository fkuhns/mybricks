# Smart car v6 architecture
```mermaid
flowchart TD
    app["smartCar/main.py<br/>MyApp: modes, inputs, behavior"]

    subgraph shared["Shared application modules: common/"]
        inputs["common.py<br/>Button, Pot"]
        sensors["usonic.py · ir_sensor.py<br/>Distance and IR input"]
        control["motor.py<br/>CarMotors and command queue"]
        display["i2c_dev.py<br/>I2C control and OLED"]
        drivers["picobricks.py · ssd1306.py · buzzer.py<br/>Hardware drivers"]
    end

    subgraph hardware["Pico hardware runtime"]
        mp["MicroPython platform modules<br/>machine · utime · framebuf"]
        devices["GPIO / ADC · ultrasonic · IR"]
        bus["I2C bus"]
        outputs["Motor controller · OLED · buzzer"]
    end

    subgraph simulation["Laptop simulation"]
        runner["sim/run.py<br/>Loads MyApp and scenarios"]
        stubs["sim/ platform stubs<br/>machine · utime · framebuf · micropython"]
        world["simcore.py<br/>Virtual clock, simulated devices, car model"]
        scenarios["sim/scenarios/<br/>Inputs, faults, expectations"]
    end

    examples["dev_examples/<br/>Standalone hardware examples"]

    app --> inputs
    app --> sensors
    app --> control
    app --> display
    control --> display
    display --> drivers

    app --> mp
    inputs --> devices
    sensors --> devices
    display --> bus
    drivers --> bus
    bus --> outputs

    runner --> app
    scenarios --> runner
    runner --> stubs
    stubs --> world
    app --> stubs
    inputs --> stubs
    sensors --> stubs
    display --> stubs
    world --> devices
    world --> outputs

    examples -. separate examples .-> hardware
```

`main.py` is the application entrypoint. Its `main()` constructs `MyApp` in
distance mode, runs the application loop, and shuts the car down before
resetting the board.

```mermaid
flowchart TD
    entry["smartCar/main.py<br/>main()"] --> app["MyApp"]
    app --> loop["MyApp.run()<br/>main loop and mode dispatch"]
    loop --> distance["CarDist.run()<br/>autonomous distance behavior"]
    loop --> infrared["MyApp.run_ir()<br/>remote command handling"]
    loop --> controls["Button / Pot<br/>mode gate and turn delay"]
    app --> shutdown["MyApp.shutdown()<br/>stop motors and refresh display"]

    subgraph common["Library modules in common/"]
        common_mod["common.py<br/>Button, Pot"]
        distance_mod["distance.py<br/>CarDist"]
        ultrasonic_mod["usonic.py<br/>UltrasonicSensor"]
        ir_mod["ir_sensor.py<br/>NEC_8, IR_RX"]
        i2c_mod["i2c_dev.py<br/>I2cCtl, MotorsI2c, OledI2c"]
        motor_lib["picobricks.py<br/>MotorDriver"]
        display_lib["ssd1306.py<br/>SSD1306_I2C"]
        buzzer_lib["buzzer.py<br/>Buzzer"]
        resources["resources.py<br/>(not used by main.py)"]
    end

    app --> common_mod
    app --> distance_mod
    app --> ir_mod
    app --> i2c_mod
    controls -. uses .-> common_mod
    distance --> distance_mod
    distance_mod --> ultrasonic_mod
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
