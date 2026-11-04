# Smart car architecture

```mermaid
flowchart TD
    app["smartCar/smart_car.py<br/>MyApp(mode): modes, subsystems, app loop"]

    subgraph appmods["Application modules"]
        common["common/common.py<br/>Button, Pot, debug constants"]
        dist["common/distance.py<br/>CarDist: ultrasonic zone logic"]
        ir["common/ir.py<br/>IRMgr: IR decode + motor queue"]
        i2c["common/i2c_dev.py<br/>I2cCtl, I2cBus, OledI2c"]
        motor["common/motor.py<br/>CarMotors: queued motor commands"]
        sonic["common/usonic.py<br/>UltrasonicSensor"]
        ir_rx["common/ir_sensor.py<br/>NEC_8 decoder / IR_RX"]
        oled["common/ssd1306.py<br/>SSD1306_I2C display driver"]
        buzzer["common/buzzer.py<br/>PWM buzzer driver"]
        motor_hw["common/picobricks.py<br/>Motor controller wrapper"]
    end

    subgraph hardware["Pico runtime"]
        mp["MicroPython runtime<br/>machine, utime, framebuf"]
        gpio["GPIO / ADC<br/>button, pot, ultrasonic, IR"]
        i2c_bus["I2C bus 0"]
        motors["Motor controller"]
        disp["SSD1306 OLED"]
        beep["Buzzer"]
    end

    subgraph sim["Laptop simulation"]
        runner["sim/run.py<br/>loads smart_car.MyApp + scenario"]
        stubs["sim/*.py stubs<br/>machine, utime, micropython, framebuf"]
        world["sim/simcore.py<br/>virtual clock, devices, car model"]
        scenarios["sim/scenarios/*.py<br/>inputs, faults, expectations"]
    end

    app --> common
    app --> dist
    app --> ir
    app --> i2c
    app --> motor

    dist --> sonic
    ir --> ir_rx
    i2c --> oled
    i2c --> buzzer
    motor --> motor_hw

    common --> gpio
    sonic --> gpio
    ir_rx --> gpio
    oled --> i2c_bus
    motor_hw --> i2c_bus
    buzzer --> beep

    i2c_bus --> motors
    i2c_bus --> disp

    app --> mp
    runner --> app
    runner --> stubs
    scenarios --> runner
    stubs --> world
    world --> gpio
    world --> i2c_bus
    world --> motors
    world --> disp
    world --> beep
```

`smartCar/smart_car.py` is the application entry point. `main()` creates a
`MyApp` with a `MODE_*` bitmask, installs the I2C environment, wires in optional
distance and IR managers, and then runs the main loop until a reset is triggered.

```mermaid
flowchart TD
    entry["smartCar/smart_car.py<br/>main()"] --> app["MyApp(mode)"]
    app --> init["init_i2c_env()<br/>I2cCtl + OledI2c + CarMotors"]

    app --> dist["CarDist(self.motors, self.oled)<br/>optional"]
    app --> ir["IRMgr(self.motors, self.oled)<br/>optional"]
    app --> butt["Button()<br/>optional"]
    app --> pot["Pot()<br/>optional"]

    app --> loop["MyApp.run()<br/>main loop"]

    loop --> gate["button.enabled()<br/>start/stop gate"]
    loop --> turn["Pot.get_value() -> set_turn_ms()"]
    loop --> sonar["CarDist.run()<br/>ping + zone state + motor queue"]
    loop --> remote["IRMgr.run()<br/>decode + motor queue"]
    loop --> motors["CarMotors.run_cmds()"]
    loop --> display["OledI2c.show()"]

    dist --> sonic["UltrasonicSensor.get_distance()"]
    ir --> ir_rx["NEC_8 callback + IR_RX command map"]
    sonar --> motorq["motor queue"]
    remote --> motorq
    motorq --> motors

    motors --> bus["I2C bus 0"]
    display --> bus

    gate --> start["MyApp.start()<br/>Device.start() on each device"]
    loop --> shutdown["MyApp.shutdown()<br/>Device.stop() on each device, in reverse"]
```

The app loop is mode-driven: button and potentiometer inputs are optional, and the
car may run in distance-only, IR-only, or combined modes. The actual hardware
interaction is mediated by I2C wrappers in `common/i2c_dev.py`, while the
MicroPython runtime (`machine`, `utime`, etc.) remains external to this repo.

`I2cCtl`, `OledI2c`, `CarMotors`, `CarDist`, `IRMgr` and `IR_RX` derive from
`common.Device`. Each constructor ends with `init()`, leaving the device off;
`MyApp.start()` turns them on when the button enables the car and
`MyApp.shutdown()` turns them off. A new device overrides the `_init()`,
`_start()` and `_stop()` hooks and adds itself to `MyApp.devices`.
