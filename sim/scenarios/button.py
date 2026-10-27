# Button enables and disables the car. Contact bounce must count as one press.
MODE        = "MODE_2"   # IR + button + pot + buzzer, so the car only moves on command
DURATION_MS = 8_000


def scenario(sim):
    sim.expect(400, lambda: not sim.app.butt._enabled, "car starts disabled")

    sim.at(500, sim.press_button, 150, 3)  # 3 bounces within 6 ms
    sim.expect(2_000, lambda: sim.app.butt._enabled, "one bouncy press enables the car")
    sim.expect(2_000, lambda: sim.pin(7).level == 1, "button LED on while enabled")

    sim.at(2_500, sim.ir_send, 0x18)        # up -> forward
    sim.expect(4_000, lambda: sim.motor.wheels() == [80, 80], "IR up drives forward")

    sim.at(4_500, sim.press_button)
    sim.expect(6_000, lambda: not sim.app.butt._enabled, "second press disables the car")
    sim.expect(6_000, lambda: sim.motor.wheels() == [0, 0], "disabling stops the motors")
    sim.expect(6_000, lambda: sim.pin(7).level == 0, "button LED off while disabled")
