# I2C errors the bus layer should recover from without the app noticing.
from motor import MOTOR_DEF_SPEED as S, MOTOR_I2C_ADDR as MOTOR  # wheel speed the app drives at
from i2c_dev import I2cCtl
from ir_sensor import IR_RX
MODE        = "MODE_2"   # IR driven, so each motor write is easy to line up
DURATION_MS = 11_000

UP, DOWN, OK = IR_RX.number_up, IR_RX.number_down, IR_RX.number_ok
ERR_MAX = I2cCtl.I2C_BUS_ERR_MAX # OSErrors in a row that reset the bus


def resets(sim):
    return sim.i2c[0].created - 1


def scenario(sim):
    bus = sim.i2c[0]
    sim.at(300, sim.press_button)  # app sees it at ~530 ms and starts IR before the first frame
    sim.at(1_000, sim.ir_send, UP)
    sim.expect(1_900, lambda: sim.motor.wheels() == [S, S], "forward, no faults")

    # one timeout: retried inside I2cBus, no bus reset
    sim.at(2_000, bus.fail, "timeout", 1, MOTOR)
    sim.at(2_000, sim.ir_send, DOWN)
    sim.expect(3_900, lambda: sim.motor.wheels() == [-S, -S], "reverse after 1 timeout")
    sim.expect(3_900, lambda: resets(sim) == 0, "1 timeout does not reset the bus")

    # ERR_MAX timeouts in a row: bus reset, the queue retries the command
    sim.at(4_000, bus.fail, "timeout", ERR_MAX, MOTOR)
    sim.at(4_000, sim.ir_send, OK)
    sim.expect(5_900, lambda: sim.motor.wheels() == [0, 0], "stop after %d timeouts" % ERR_MAX)
    sim.expect(5_900, lambda: resets(sim) == 1, "%d timeouts reset the bus once" % ERR_MAX)

    # a device holding SDA low: recovery clocks it free, then a new bus object
    sim.at(6_000, bus.fail, "stuck_sda", 1, None, clocks=4)
    sim.at(6_000, sim.ir_send, UP)
    sim.expect(7_900, lambda: sim.motor.wheels() == [S, S], "forward after SDA stuck")
    sim.expect(7_900, lambda: resets(sim) == 2, "stuck SDA recovered by a bus reset")

    # data byte NACKed (short ack count): retried inside I2cBus
    sim.at(8_000, bus.fail, "short", 1, MOTOR, acks=2)
    sim.at(8_000, sim.ir_send, DOWN)
    sim.expect(9_900, lambda: sim.motor.wheels() == [-S, -S], "reverse after a NACK")
    sim.expect(9_900, lambda: sim.motor.bad_packets == 0, "no garbled motor packets")
