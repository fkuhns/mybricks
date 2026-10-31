# Tests for common.distance.CarDist.
# Run from anywhere:  python3 tests/distance_tests.py
# Uses the sim/ stubs for machine/utime, a fake sensor that returns scripted
# readings, fake motors and OLED that record what they are given, and a fake
# clock that only moves when a test moves it.
import builtins
import os
import random
import sys
import time as _host_time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "sim"), os.path.join(ROOT, "common")]
import micropython
builtins.const = micropython.const
# "time" is built into CPython, give it the MicroPython calls motor.py imports
for _n in ("ticks_ms", "ticks_diff"):
    setattr(_host_time, _n, lambda *a: 0)

import distance
from distance import (CarDist, DistException, DIST_ZONES,
                      DIST_ZONE_INVALID, DIST_ZONE_0, DIST_ZONE_1,
                      DIST_ZONE_2, DIST_ZONE_3, DIST_ZONE_PEND_CNT,
                      DIST_TIMEOUT, DIST_MIN_INCHES, DIST_INTERVAL_MS,
                      DIST_MAX_IN, ZONE_REFRESH_INDX)
from usonic import UltraSonicTimeout
from motor import (MOTOR_CMD_FORWARD, MOTOR_CMD_LEFT, MOTOR_CMD_REVERSE,
                   MOTOR_CMD_STOP)

TIMEOUT = None # FakeSonic reading that raises UltraSonicTimeout
REFRESH_MS = DIST_ZONES[DIST_ZONE_2][ZONE_REFRESH_INDX]

# a distance in the middle of each zone
IN_ZONE = {DIST_ZONE_0: TIMEOUT, DIST_ZONE_1: 6.0, DIST_ZONE_2: 20.0, DIST_ZONE_3: 60.0}
ZONE_CMD = {DIST_ZONE_0: MOTOR_CMD_STOP, DIST_ZONE_1: MOTOR_CMD_REVERSE,
            DIST_ZONE_2: MOTOR_CMD_LEFT, DIST_ZONE_3: MOTOR_CMD_FORWARD}


class FakeClock:
    def __init__(self, now=1000):
        self.now = now

    def ticks_ms(self):
        return self.now

    def ticks_diff(self, a, b):
        return a - b

    def advance(self, ms):
        self.now += ms


class FakeSonic:
    """Returns self.dist on every ping, TIMEOUT raises UltraSonicTimeout."""
    def __init__(self, dist=60.0):
        self.dist = dist
        self.pings = 0

    def get_distance(self):
        self.pings += 1
        if self.dist is TIMEOUT:
            raise UltraSonicTimeout("fake timeout")
        return self.dist


class FakeMotors:
    """Records calls as ("add", cmd, arg, ms) and ("clear", ms)."""
    def __init__(self, clock):
        self.clock = clock
        self.calls = []
        self.full = False # add_cmd returns False while set

    def add_cmd(self, cmd, arg=0):
        if self.full:
            return False
        self.calls.append(("add", cmd, arg, self.clock.now))
        return True

    def clear_cmds(self):
        self.calls.append(("clear", self.clock.now))

    def cmds(self):
        return [c[1] for c in self.calls if c[0] == "add"]

    def cmd_times(self):
        return [c[3] for c in self.calls if c[0] == "add"]


class FakeOled:
    def __init__(self):
        self.rows = []

    def update_row2(self, txt):
        self.rows.append(txt)


class DistTestBase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self._saved = (distance.ticks_ms, distance.ticks_diff)
        distance.ticks_ms = self.clock.ticks_ms
        distance.ticks_diff = self.clock.ticks_diff
        self.sonic = FakeSonic()
        self.motors = FakeMotors(self.clock)
        self.oled = FakeOled()
        self.d = self.make()

    def tearDown(self):
        distance.ticks_ms, distance.ticks_diff = self._saved

    def make(self, **kw):
        return CarDist(self.motors, self.oled, sonic=self.sonic, **kw)

    def ping(self, dist, n=1):
        # n readings of dist, each one ping interval apart
        self.sonic.dist = dist
        for _ in range(n):
            self.clock.advance(DIST_INTERVAL_MS)
            self.d.run()

    def settle(self, zid):
        # put the car in zone zid and forget the calls that took
        self.ping(IN_ZONE[zid], DIST_ZONE_PEND_CNT)
        self.assertEqual(self.d.zid, zid)
        self.motors.calls = []


#############################################################################
# find_zone / read
#############################################################################
class TestFindZone(DistTestBase):
    def zid(self, dist):
        return self.d.find_zone(dist)[0]

    def test_timeout_is_zone_0(self):
        self.assertEqual(self.zid(DIST_TIMEOUT), DIST_ZONE_0)

    def test_boundaries(self):
        self.assertEqual(self.zid(0), DIST_ZONE_1)
        self.assertEqual(self.zid(11.99), DIST_ZONE_1)
        self.assertEqual(self.zid(12), DIST_ZONE_2)
        self.assertEqual(self.zid(29.99), DIST_ZONE_2)
        self.assertEqual(self.zid(30), DIST_ZONE_3)
        self.assertEqual(self.zid(DIST_MAX_IN - 0.01), DIST_ZONE_3)

    def test_past_max_is_last_zone(self):
        # the sensor reads up to 288", past the end of the table
        self.assertEqual(self.zid(DIST_MAX_IN), DIST_ZONE_3)
        self.assertEqual(self.zid(300), DIST_ZONE_3)

    def test_below_table_raises(self):
        with self.assertRaises(DistException):
            self.d.find_zone(-5)


class TestRead(DistTestBase):
    def test_returns_sensor_distance(self):
        self.sonic.dist = 42.5
        self.assertEqual(self.d.read(), 42.5)

    def test_timeout_returns_dist_timeout(self):
        self.sonic.dist = TIMEOUT
        self.assertEqual(self.d.read(), DIST_TIMEOUT)


#############################################################################
# ping rate
#############################################################################
class TestPingInterval(DistTestBase):
    def test_no_ping_before_interval(self):
        self.ping(60.0)
        self.assertEqual(self.sonic.pings, 1)
        self.clock.advance(DIST_INTERVAL_MS - 1)
        self.d.run()
        self.assertEqual(self.sonic.pings, 1)
        self.clock.advance(1)
        self.d.run()
        self.assertEqual(self.sonic.pings, 2)

    def test_stable_distance_still_waits_interval(self):
        # a reading equal to the last one must not let the next ping in early
        self.ping(60.0)
        for _ in range(20):
            self.clock.advance(10)
            self.d.run()
        self.assertEqual(self.sonic.pings, 1 + 200 // DIST_INTERVAL_MS)

    def test_timeouts_wait_interval(self):
        self.ping(TIMEOUT)
        self.clock.advance(1)
        self.d.run()
        self.assertEqual(self.sonic.pings, 1)


#############################################################################
# zone changes
#############################################################################
class TestFirstReading(DistTestBase):
    def test_first_reading_sends_zone_cmd(self):
        for zid in (DIST_ZONE_1, DIST_ZONE_2, DIST_ZONE_3):
            self.d.reset()
            self.motors.calls = []
            self.ping(IN_ZONE[zid])
            self.assertEqual(self.motors.cmds(), [ZONE_CMD[zid]])
            self.assertEqual(self.d.zid, zid)

    def test_first_timeout_clears_and_stops(self):
        self.ping(TIMEOUT)
        self.assertEqual(self.motors.calls, [("clear", self.clock.now),
                                             ("add", MOTOR_CMD_STOP, 0, self.clock.now)])


class TestDebounce(DistTestBase):
    def setUp(self):
        super().setUp()
        self.settle(DIST_ZONE_3)

    def test_needs_pend_cnt_readings(self):
        self.ping(IN_ZONE[DIST_ZONE_2], DIST_ZONE_PEND_CNT - 1)
        self.assertEqual(self.motors.cmds(), [])
        self.assertEqual(self.d.zid, DIST_ZONE_3)
        self.ping(IN_ZONE[DIST_ZONE_2])
        self.assertEqual(self.motors.cmds(), [MOTOR_CMD_LEFT])
        self.assertEqual(self.d.zid, DIST_ZONE_2)
        self.assertEqual(self.d.zone_pending, DIST_ZONE_INVALID)

    def test_current_zone_reading_cancels_pending(self):
        self.ping(IN_ZONE[DIST_ZONE_2], DIST_ZONE_PEND_CNT - 1)
        self.ping(IN_ZONE[DIST_ZONE_3])
        self.assertEqual(self.d.zone_pending, DIST_ZONE_INVALID)
        self.ping(IN_ZONE[DIST_ZONE_2], DIST_ZONE_PEND_CNT - 1)
        self.assertEqual(self.motors.cmds(), [])

    def test_other_new_zone_restarts_count(self):
        self.ping(IN_ZONE[DIST_ZONE_2], DIST_ZONE_PEND_CNT - 1)
        self.ping(IN_ZONE[DIST_ZONE_1], DIST_ZONE_PEND_CNT - 1)
        self.assertEqual(self.motors.cmds(), [])
        self.ping(IN_ZONE[DIST_ZONE_1])
        self.assertEqual(self.motors.cmds(), [MOTOR_CMD_REVERSE])

    def test_unchanged_distance_counts(self):
        # car is parked: the same reading over and over still changes zones
        self.ping(25.0, DIST_ZONE_PEND_CNT)
        self.assertEqual(self.motors.cmds(), [MOTOR_CMD_LEFT])

    def test_jitter_on_boundary_sends_nothing(self):
        for k in range(100):
            self.ping(29.9 if k % 2 else 30.1)
        self.assertEqual(self.motors.cmds(), [])

    def test_zone_0_clears_queue_first(self):
        self.ping(TIMEOUT, DIST_ZONE_PEND_CNT)
        self.assertEqual([c[0] for c in self.motors.calls], ["clear", "add"])
        self.assertEqual(self.motors.cmds(), [MOTOR_CMD_STOP])

    def test_other_zones_do_not_clear(self):
        for zid in (DIST_ZONE_2, DIST_ZONE_1, DIST_ZONE_3):
            self.ping(IN_ZONE[zid], DIST_ZONE_PEND_CNT)
        self.assertNotIn("clear", [c[0] for c in self.motors.calls])
        self.assertEqual(self.motors.cmds(),
                         [MOTOR_CMD_LEFT, MOTOR_CMD_REVERSE, MOTOR_CMD_FORWARD])

    def test_pend_cnt_1_changes_at_once(self):
        self.d = self.make(pend_cnt=1)
        self.settle(DIST_ZONE_3)
        self.ping(IN_ZONE[DIST_ZONE_2])
        self.assertEqual(self.motors.cmds(), [MOTOR_CMD_LEFT])


class TestRefresh(DistTestBase):
    def test_refresh_zone_repeats_cmd(self):
        self.ping(IN_ZONE[DIST_ZONE_2])
        t0 = self.clock.now
        self.ping(IN_ZONE[DIST_ZONE_2], 30)
        times = self.motors.cmd_times()
        self.assertEqual(self.motors.cmds(), [MOTOR_CMD_LEFT] * len(times))
        self.assertEqual(times[0], t0)
        self.assertGreater(len(times), 2)
        for a, b in zip(times, times[1:]):
            # first reading at or after REFRESH_MS
            self.assertGreaterEqual(b - a, REFRESH_MS)
            self.assertLess(b - a, REFRESH_MS + DIST_INTERVAL_MS)

    def test_no_refresh_zone_sends_once(self):
        self.ping(IN_ZONE[DIST_ZONE_3], 100)
        self.assertEqual(self.motors.cmds(), [MOTOR_CMD_FORWARD])

    def test_refresh_timed_from_zone_change(self):
        self.settle(DIST_ZONE_3)
        self.ping(IN_ZONE[DIST_ZONE_2], DIST_ZONE_PEND_CNT)
        t0 = self.clock.now
        self.ping(IN_ZONE[DIST_ZONE_2], REFRESH_MS // DIST_INTERVAL_MS + 1)
        self.assertEqual(self.motors.cmd_times(), [t0, t0 + 10 * DIST_INTERVAL_MS])


class TestQueueFull(DistTestBase):
    def test_failed_change_is_retried(self):
        self.settle(DIST_ZONE_3)
        self.motors.full = True
        self.ping(IN_ZONE[DIST_ZONE_2], DIST_ZONE_PEND_CNT + 2)
        self.assertEqual(self.d.zid, DIST_ZONE_3)
        self.motors.full = False
        self.ping(IN_ZONE[DIST_ZONE_2])
        self.assertEqual(self.motors.cmds(), [MOTOR_CMD_LEFT])
        self.assertEqual(self.d.zid, DIST_ZONE_2)

    def test_failed_first_cmd_is_retried(self):
        self.motors.full = True
        self.ping(IN_ZONE[DIST_ZONE_3])
        self.assertEqual(self.d.zid, DIST_ZONE_INVALID)
        self.motors.full = False
        self.ping(IN_ZONE[DIST_ZONE_3])
        self.assertEqual(self.motors.cmds(), [MOTOR_CMD_FORWARD])

    def test_failed_refresh_is_retried(self):
        self.ping(IN_ZONE[DIST_ZONE_2])
        self.motors.full = True
        self.ping(IN_ZONE[DIST_ZONE_2], 12)
        self.motors.full = False
        self.ping(IN_ZONE[DIST_ZONE_2])
        self.assertEqual(self.motors.cmds(), [MOTOR_CMD_LEFT, MOTOR_CMD_LEFT])


class TestReset(DistTestBase):
    def test_same_zone_after_reset_resends(self):
        # button off/on: motors were reset so the zone command must go again
        self.settle(DIST_ZONE_3)
        self.d.reset()
        self.ping(IN_ZONE[DIST_ZONE_3])
        self.assertEqual(self.motors.cmds(), [MOTOR_CMD_FORWARD])

    def test_reset_drops_pending(self):
        self.settle(DIST_ZONE_3)
        self.ping(IN_ZONE[DIST_ZONE_2], DIST_ZONE_PEND_CNT - 1)
        self.d.reset()
        self.assertEqual((self.d.zid, self.d.zone_pending, self.d.pending_cnt),
                         (DIST_ZONE_INVALID, DIST_ZONE_INVALID, 0))


#############################################################################
# OLED
#############################################################################
class TestShow(DistTestBase):
    def test_shows_feet_and_inches(self):
        self.ping(30.5)
        self.assertEqual(self.oled.rows, ["2' 6.50\""])

    def test_small_change_not_shown(self):
        self.ping(30.0)
        self.ping(30.0 + DIST_MIN_INCHES - 0.01)
        self.assertEqual(len(self.oled.rows), 1)
        self.ping(30.0 + DIST_MIN_INCHES)
        self.assertEqual(len(self.oled.rows), 2)

    def test_timeout_shown_once(self):
        self.ping(30.0)
        self.ping(TIMEOUT, 5)
        self.assertEqual(self.oled.rows, ["2' 6.00\"", "Dist: --"])
        self.ping(30.0)
        self.assertEqual(self.oled.rows[-1], "2' 6.00\"")

    def test_first_timeout_not_shown(self):
        # the OLED starts with "Dist: --"
        self.ping(TIMEOUT)
        self.assertEqual(self.oled.rows, [])


#############################################################################
# motor command rate
#############################################################################
class TestCmdRate(DistTestBase):
    MIN_GAP_MS = DIST_ZONE_PEND_CNT * DIST_INTERVAL_MS

    def check_gaps(self, times):
        for a, b in zip(times, times[1:]):
            self.assertGreaterEqual(b - a, self.MIN_GAP_MS)

    def test_random_readings_rate_limited(self):
        # whatever the sensor says, commands are >= PEND_CNT pings apart
        rng = random.Random(1)
        choices = [TIMEOUT, 0.5, 6.0, 11.9, 12.1, 20.0, 29.9, 30.1, 60.0, 280.0]
        self.sonic.dist = 60.0
        for _ in range(60 * 1000 // 10): # 60s with a 10ms main loop
            if rng.random() < 0.3:
                self.sonic.dist = rng.choice(choices)
            self.clock.advance(10)
            self.d.run()
        times = self.motors.cmd_times()
        self.assertGreater(len(times), 10)
        self.check_gaps(times)

    def test_fastest_zone_changes(self):
        # a new zone on every PEND_CNT pings is the most a reading stream can do
        zones = [DIST_ZONE_1, DIST_ZONE_2, DIST_ZONE_3, DIST_ZONE_0]
        for k in range(40):
            self.ping(IN_ZONE[zones[k % 4]], DIST_ZONE_PEND_CNT)
        times = self.motors.cmd_times()
        self.assertEqual(len(times), 40)
        self.check_gaps(times)
        per_sec = 1000.0 / self.MIN_GAP_MS
        self.assertLessEqual(len(times) - 1, per_sec * (times[-1] - times[0]) / 1000.0)


if __name__ == "__main__":
    unittest.main()
