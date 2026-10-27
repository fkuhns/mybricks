# Drive with the IR remote, including a repeat code and corrupted frames.
MODE        = "MODE_2"   # IR + button + pot + buzzer
DURATION_MS = 14_000

UP, DOWN, LEFT, RIGHT, OK = 0x18, 0x52, 0x08, 0x5a, 0x1c


def scenario(sim):
    sim.set_pot_ms(500)
    sim.at(500, sim.press_button)

    sim.at(1_000, sim.ir_send, UP)
    sim.expect(2_500, lambda: sim.motor.wheels() == [80, 80], "up drives forward")

    sim.at(3_000, sim.ir_send, LEFT)
    sim.expect(4_200, lambda: sim.motor.wheels() == [-80, 80], "left pivots left")
    sim.expect(6_000, lambda: sim.motor.wheels() == [0, 0], "turn ends with a stop")

    sim.at(6_200, sim.ir_send, UP, 0x00, None, True)  # repeat code is a no-op
    sim.expect(7_500, lambda: sim.motor.wheels() == [0, 0], "repeat code does nothing")

    sim.at(7_600, sim.ir_send, UP, 0x00, "data")      # bad checksum
    sim.expect(8_800, lambda: sim.app.oled._obuf[2][0] == "BADDATA", "bad frame reported")
    sim.expect(8_800, lambda: sim.motor.wheels() == [0, 0], "bad frame ignored")

    sim.at(9_000, sim.ir_send, DOWN)
    sim.expect(10_500, lambda: sim.motor.wheels() == [-80, -80], "down reverses")

    sim.at(11_000, sim.ir_send, OK)
    sim.expect(12_500, lambda: sim.motor.wheels() == [0, 0], "ok stops")
