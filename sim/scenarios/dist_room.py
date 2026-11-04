# Autonomous distance mode in a 10' x 10' room with one obstacle.
# Watch the MOTOR and BUMP lines to see how the avoidance logic behaves.
from motor import MOTOR_DEF_SPEED as S  # wheel speed the app drives at
MODE        = "MODE_1"   # distance + button + pot + buzzer
DURATION_MS = 40_000


def scenario(sim):
    car = sim.car
    car.room = (120, 120)
    car.place(60, 20, 90)               # facing a wall 100" away
    car.obstacles = [(30, 80, 6)]       # (x, y, radius) inches
    car.speed_ips = 12                  # at motor speed Car.REF_SPEED
    car.turn_dps  = 180
    sim.set_pot_ms(500)                 # turn time

    sim.at(500, sim.press_button)
    sim.expect(3_000, lambda: sim.motor.wheels() == [S, S], "drives toward the far wall")

    # sensor loses the echo: the app should stop
    sim.at(20_000, sim.set_distance, "timeout")
    sim.expect(22_500, lambda: sim.motor.wheels() == [0, 0], "no echo stops the car")
    sim.at(23_000, sim.set_distance, None)

    sim.expect(DURATION_MS - 1, lambda: car.bumps == 0, "never hits a wall or obstacle")
