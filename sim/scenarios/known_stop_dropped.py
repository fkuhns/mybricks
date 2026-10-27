# KNOWN ISSUE (FIXME in CarMotors.run_cmds): when the motor controller stops
# answering, a STOP is dropped after MOTOR_CMD_MAX_TRIES and the car keeps
# driving after the controller comes back. Expected to FAIL until fixed.
MODE        = "MODE_2"
DURATION_MS = 9_000

DOWN, OK = 0x52, 0x1c


def scenario(sim):
    sim.at(500, sim.press_button)
    sim.at(1_000, sim.ir_send, DOWN)
    sim.expect(2_500, lambda: sim.motor.wheels() == [-80, -80], "reversing")

    sim.at(3_000, sim.motor.set_offline, True)
    sim.at(3_100, sim.ir_send, OK)
    sim.at(6_000, sim.motor.set_offline, False)
    sim.expect(8_500, lambda: sim.motor.wheels() == [0, 0],
               "car stopped once the controller is back (STOP not lost)")
