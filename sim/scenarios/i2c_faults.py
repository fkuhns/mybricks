# I2C errors the bus layer should recover from without the app noticing.
MODE        = "MODE_2"   # IR driven, so each motor write is easy to line up
DURATION_MS = 11_000

UP, DOWN, OK = 0x18, 0x52, 0x1c
MOTOR = 0x22


def resets(sim):
    return sim.i2c[0].created - 1


def scenario(sim):
    bus = sim.i2c[0]
    sim.at(500, sim.press_button)
    sim.at(1_000, sim.ir_send, UP)
    sim.expect(1_900, lambda: sim.motor.wheels() == [80, 80], "forward, no faults")

    # one timeout: retried inside I2cBus, no bus reset
    sim.at(2_000, bus.fail, "timeout", 1, MOTOR)
    sim.at(2_000, sim.ir_send, DOWN)
    sim.expect(3_900, lambda: sim.motor.wheels() == [-80, -80], "reverse after 1 timeout")
    sim.expect(3_900, lambda: resets(sim) == 0, "1 timeout does not reset the bus")

    # three timeouts in a row: bus reset, the queue retries the command
    sim.at(4_000, bus.fail, "timeout", 3, MOTOR)
    sim.at(4_000, sim.ir_send, OK)
    sim.expect(5_900, lambda: sim.motor.wheels() == [0, 0], "stop after 3 timeouts")
    sim.expect(5_900, lambda: resets(sim) == 1, "3 timeouts reset the bus once")

    # a device holding SDA low: recovery clocks it free, then a new bus object
    sim.at(6_000, bus.fail, "stuck_sda", 1, None, clocks=4)
    sim.at(6_000, sim.ir_send, UP)
    sim.expect(7_900, lambda: sim.motor.wheels() == [80, 80], "forward after SDA stuck")
    sim.expect(7_900, lambda: resets(sim) == 2, "stuck SDA recovered by a bus reset")

    # data byte NACKed (short ack count): retried inside I2cBus
    sim.at(8_000, bus.fail, "short", 1, MOTOR, acks=2)
    sim.at(8_000, sim.ir_send, DOWN)
    sim.expect(9_900, lambda: sim.motor.wheels() == [-80, -80], "reverse after a NACK")
    sim.expect(9_900, lambda: sim.motor.bad_packets == 0, "no garbled motor packets")
