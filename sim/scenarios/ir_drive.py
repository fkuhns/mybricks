# Drive with the IR remote, including a repeat code and corrupted frames.
from motor import MOTOR_DEF_SPEED as S  # wheel speed the app drives at
from ir import IR_ERRS
from ir_sensor import IR_RX
MODE        = "MODE_2"   # IR + button + pot + buzzer
DURATION_MS = 14_000

UP, DOWN, LEFT, RIGHT, OK = (IR_RX.number_up, IR_RX.number_down, IR_RX.number_left,
                             IR_RX.number_right, IR_RX.number_ok)


def scenario(sim):
    sim.set_pot_ms(500)
    sim.at(300, sim.press_button)  # app sees it at ~530 ms and starts IR before the first frame

    sim.at(1_000, sim.ir_send, UP)
    sim.expect(2_500, lambda: sim.motor.wheels() == [S, S], "up drives forward")

    sim.at(3_000, sim.ir_send, LEFT)
    sim.expect(3_400, lambda: sim.motor.wheels() == [-S, S], "left pivots left")
    sim.expect(6_000, lambda: sim.motor.wheels() == [0, 0], "turn ends with a stop")

    sim.at(6_200, sim.ir_send, UP, 0x00, None, True)  # repeat code is a no-op
    sim.expect(7_500, lambda: sim.motor.wheels() == [0, 0], "repeat code does nothing")

    sim.at(7_600, sim.ir_send, UP, 0x00, "data")      # bad checksum
    sim.expect(8_800, lambda: sim.app.oled._obuf[2][0] == IR_ERRS[IR_RX.BADDATA], "bad frame reported")
    sim.expect(8_800, lambda: sim.motor.wheels() == [0, 0], "bad frame ignored")

    sim.at(9_000, sim.ir_send, DOWN)
    sim.expect(10_500, lambda: sim.motor.wheels() == [-S, -S], "down reverses")

    sim.at(11_000, sim.ir_send, OK)
    sim.expect(12_500, lambda: sim.motor.wheels() == [0, 0], "ok stops")
