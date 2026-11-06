# Tests for common.motor.CarMotors.add_cmd and run_cmds.
# Run from anywhere:  python3 tests/motor_tests.py
# Uses the sim/ stubs for machine/utime, a fake I2C bus that records the motor
# driver writes (and can be told to fail) and a fake clock that only moves when
# a test moves it.
import builtins
import contextlib
import io
import os
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

import motor
from motor import (CarMotors, I2cException, MotorException,
                   MOTOR_CMD_NOOP, MOTOR_CMD_FORWARD, MOTOR_CMD_REVERSE,
                   MOTOR_CMD_LEFT, MOTOR_CMD_RIGHT, MOTOR_CMD_STOP,
                   MOTOR_CMD_STOP_FORCE, MOTOR_CMD_MAX,
                   MOTOR_STATE_FWD, MOTOR_STATE_BKWD, MOTOR_STATE_LEFT,
                   MOTOR_STATE_RIGHT, MOTOR_STATE_STOP, MOTOR_STATE_UNK,
                   MOTOR_INTER_CMD_MS, MOTOR_CMD_RETRY_MS, MOTOR_CMD_MAX_TRIES,
                   MOTOR_TURN_DELAY_MS, MOTOR_DEF_SPEED, MOTOR_QSIZE as QSIZE)


class FakeClock:
    def __init__(self, now=1000):
        self.now = now

    def ticks_ms(self):
        return self.now

    def ticks_diff(self, a, b):
        return a - b

    def advance(self, ms):
        self.now += ms


class FakeBus:
    """Stands in for the I2cBus. Records motor driver writes as (motor, speed, dir)."""
    def __init__(self):
        self.writes = []
        self.fail = 0        # next N writes raise I2cException
        self.exc = None      # if set, every write raises this instead

    def writeto(self, addr, buf):
        if self.exc is not None:
            raise self.exc
        if self.fail > 0:
            self.fail -= 1
            raise I2cException("fake i2c failure")
        self.writes.append((buf[1], buf[2], buf[3]))


def stop_entry(delay=MOTOR_INTER_CMD_MS):
    return (MOTOR_CMD_STOP, 0, delay, 0)

# motor driver writes made by stop_motors()/stop_force()
STOP_WRITES = [(1, 0, 0), (2, 0, 0)]

# With MOTOR_CMD_ADD_STOP add_cmd queues a STOP in front of every FORWARD,
# REVERSE, LEFT and RIGHT. Everything below assumes it is on.
assert motor.MOTOR_CMD_ADD_STOP


class MotorTestBase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self._saved = (motor.ticks_ms, motor.ticks_diff)
        motor.ticks_ms = self.clock.ticks_ms
        motor.ticks_diff = self.clock.ticks_diff
        self._out = contextlib.redirect_stdout(io.StringIO()) # motor prints a lot
        self._out.__enter__()
        self.bus = FakeBus()
        self.m = CarMotors(self.bus, buzz=False)

    def tearDown(self):
        self._out.__exit__(None, None, None)
        motor.ticks_ms, motor.ticks_diff = self._saved

    def queued(self):
        # non destructive copy of the queue contents
        rb = self.m.rbuf
        items = []
        i = rb.tail
        while i != rb.head:
            w = rb.width
            items.append(tuple(rb.buf[i * w:i * w + w]))
            i = (i + 1) % rb.slots
        return items

    def qlen(self):
        return len(self.m.rbuf)

    def push(self, *entries):
        # put raw entries on the queue, bypassing add_cmd
        for e in entries:
            self.assertTrue(self.m.rbuf.put(e))

    def fill_queue(self, n):
        # n raw entries, bypassing add_cmd (which adds a stop in front of moves)
        self.push(*[(MOTOR_CMD_FORWARD, 0, 0, 0)] * n)


#############################################################################
# add_cmd
#############################################################################
class TestAddCmdSimple(MotorTestBase):
    def test_noop_returns_true_and_queues_nothing(self):
        self.assertTrue(self.m.add_cmd(MOTOR_CMD_NOOP))
        self.assertEqual(self.qlen(), 0)

    def test_noop_with_arg_queues_nothing(self):
        self.assertTrue(self.m.add_cmd(MOTOR_CMD_NOOP, 90))
        self.assertEqual(self.qlen(), 0)

    def test_noop_on_full_queue_is_true(self):
        self.fill_queue(QSIZE)
        self.assertTrue(self.m.add_cmd(MOTOR_CMD_NOOP))
        self.assertEqual(self.qlen(), QSIZE)

    def test_stop_commands_are_queued_as_one_entry(self):
        for cmd in (MOTOR_CMD_STOP, MOTOR_CMD_STOP_FORCE):
            self.m.rbuf.clear()
            self.assertTrue(self.m.add_cmd(cmd), cmd)
            self.assertEqual(self.queued(), [(cmd, 0, MOTOR_INTER_CMD_MS, 0)], cmd)

    def test_forward_and_reverse_are_queued_after_a_stop(self):
        for cmd in (MOTOR_CMD_FORWARD, MOTOR_CMD_REVERSE):
            self.m.rbuf.clear()
            self.assertTrue(self.m.add_cmd(cmd), cmd)
            self.assertEqual(self.queued(),
                             [stop_entry(), (cmd, 0, MOTOR_INTER_CMD_MS, 0)], cmd)

    def test_stop_is_queued_even_if_car_is_already_stopped(self):
        # the car state may be stale so it is not used to skip the stop
        self.m.state[0] = MOTOR_STATE_STOP
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.assertEqual(self.queued()[0], stop_entry())

    def test_arg_is_stored(self):
        self.m.add_cmd(MOTOR_CMD_FORWARD, 42)
        self.assertEqual(self.queued(),
                         [stop_entry(), (MOTOR_CMD_FORWARD, 42, MOTOR_INTER_CMD_MS, 0)])

    def test_try_count_starts_at_zero(self):
        self.m.add_cmd(MOTOR_CMD_REVERSE)
        self.assertEqual([e[motor.MOTOR_INDX_COUNT] for e in self.queued()], [0, 0])

    def test_commands_are_fifo(self):
        order = (MOTOR_CMD_FORWARD, MOTOR_CMD_REVERSE, MOTOR_CMD_STOP, MOTOR_CMD_STOP_FORCE)
        for cmd in order:
            self.m.add_cmd(cmd)
        self.assertEqual([e[0] for e in self.queued()],
                         [MOTOR_CMD_STOP, MOTOR_CMD_FORWARD,
                          MOTOR_CMD_STOP, MOTOR_CMD_REVERSE,
                          MOTOR_CMD_STOP, MOTOR_CMD_STOP_FORCE])

    def test_add_does_not_touch_motors(self):
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.add_cmd(MOTOR_CMD_LEFT)
        self.assertEqual(self.bus.writes, [])


class TestAddCmdInvalid(MotorTestBase):
    def test_too_large_raises(self):
        with self.assertRaises(MotorException):
            self.m.add_cmd(MOTOR_CMD_MAX + 1)

    def test_negative_raises(self):
        with self.assertRaises(MotorException):
            self.m.add_cmd(-1)

    def test_invalid_does_not_change_queue(self):
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        before = self.queued()
        for bad in (MOTOR_CMD_MAX + 1, 99, -1):
            with self.assertRaises(MotorException):
                self.m.add_cmd(bad)
        self.assertEqual(self.queued(), before)

    def test_max_command_is_valid(self):
        self.assertTrue(self.m.add_cmd(MOTOR_CMD_MAX))


class TestAddCmdTurn(MotorTestBase):
    def test_turn_queues_stop_turn_stop(self):
        for cmd in (MOTOR_CMD_LEFT, MOTOR_CMD_RIGHT):
            self.m.rbuf.clear()
            self.assertTrue(self.m.add_cmd(cmd))
            self.assertEqual(self.queued(), [
                stop_entry(),
                (cmd, 0, MOTOR_INTER_CMD_MS, 0),
                stop_entry(MOTOR_TURN_DELAY_MS)])

    def test_turn_without_arg_uses_default_turn_ms(self):
        self.m.add_cmd(MOTOR_CMD_LEFT)
        self.assertEqual(self.queued()[2][motor.MOTOR_INDX_DELAY], self.m.turn_ms)

    def test_set_turn_ms_changes_stop_delay(self):
        self.m.set_turn_ms(123)
        self.m.add_cmd(MOTOR_CMD_RIGHT)
        self.assertEqual(self.queued()[2][motor.MOTOR_INDX_DELAY], 123)

    def test_turn_with_angle_uses_angle_time(self):
        self.m.add_cmd(MOTOR_CMD_LEFT, 90)
        pre, turn, stop = self.queued()
        self.assertEqual(pre, stop_entry())
        self.assertEqual(turn, (MOTOR_CMD_LEFT, 90, MOTOR_INTER_CMD_MS, 0))
        self.assertEqual(stop, (MOTOR_CMD_STOP, 0, self.m.ms_for_angle(90), 0))

    def test_angle_time_scales_with_angle(self):
        self.m.add_cmd(MOTOR_CMD_RIGHT, 45)
        self.m.add_cmd(MOTOR_CMD_RIGHT, 180)
        # the prefix stops have no delay, the final stops have the turn time
        d = [e[motor.MOTOR_INDX_DELAY] for e in self.queued()
             if e[0] == MOTOR_CMD_STOP and e[motor.MOTOR_INDX_DELAY] != MOTOR_INTER_CMD_MS]
        self.assertEqual(d, [self.m.ms_for_angle(45), self.m.ms_for_angle(180)])
        self.assertLess(d[0], d[1])

    def test_angle_ignores_turn_ms_setting(self):
        self.m.set_turn_ms(9999)
        self.m.add_cmd(MOTOR_CMD_LEFT, 90)
        self.assertEqual(self.queued()[2][motor.MOTOR_INDX_DELAY], self.m.ms_for_angle(90))

    def test_stop_entries_have_no_arg_and_zero_count(self):
        self.m.add_cmd(MOTOR_CMD_LEFT, 90)
        q = self.queued()
        for stop in (q[0], q[2]):
            self.assertEqual((stop[motor.MOTOR_INDX_ARG], stop[motor.MOTOR_INDX_COUNT]), (0, 0))

    def test_turns_keep_order_with_other_commands(self):
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.add_cmd(MOTOR_CMD_LEFT)
        self.m.add_cmd(MOTOR_CMD_REVERSE)
        self.assertEqual([e[0] for e in self.queued()],
                         [MOTOR_CMD_STOP, MOTOR_CMD_FORWARD,
                          MOTOR_CMD_STOP, MOTOR_CMD_LEFT, MOTOR_CMD_STOP,
                          MOTOR_CMD_STOP, MOTOR_CMD_REVERSE])

    def test_turn_fits_with_exactly_three_free(self):
        self.fill_queue(QSIZE - 3)
        self.assertTrue(self.m.add_cmd(MOTOR_CMD_LEFT))
        self.assertEqual(self.qlen(), QSIZE)

    def test_turns_fill_queue_exactly(self):
        # each turn takes 3 entries: stop, turn, stop
        n = QSIZE // 3
        for _ in range(n):
            self.assertTrue(self.m.add_cmd(MOTOR_CMD_RIGHT))
        self.assertEqual(self.qlen(), 3 * n)
        self.fill_queue(QSIZE - 3 * n)
        self.assertEqual(self.qlen(), QSIZE)
        self.assertFalse(self.m.add_cmd(MOTOR_CMD_RIGHT))

    def test_turn_on_full_queue_returns_false_and_changes_nothing(self):
        self.fill_queue(QSIZE)
        before = self.queued()
        self.assertFalse(self.m.add_cmd(MOTOR_CMD_LEFT))
        self.assertEqual(self.queued(), before)

    def test_turn_with_too_few_slots_free_is_rejected_whole(self):
        # a turn is only queued with both of its stops, never without them
        for free in (1, 2):
            self.m.rbuf.clear()
            self.fill_queue(QSIZE - free)
            before = self.queued()
            self.assertFalse(self.m.add_cmd(MOTOR_CMD_LEFT), free)
            self.assertEqual(self.queued(), before,
                             "turn was partly queued with %d slots free" % free)

    def test_forward_with_one_slot_free_is_rejected_whole(self):
        # forward/reverse need 2 slots: the stop and the command
        self.fill_queue(QSIZE - 1)
        before = self.queued()
        for cmd in (MOTOR_CMD_FORWARD, MOTOR_CMD_REVERSE):
            self.assertFalse(self.m.add_cmd(cmd), cmd)
            self.assertEqual(self.queued(), before)

    def test_stop_fits_with_one_slot_free(self):
        self.fill_queue(QSIZE - 1)
        self.assertTrue(self.m.add_cmd(MOTOR_CMD_STOP))
        self.assertEqual(self.qlen(), QSIZE)


class TestAddCmdInternalErrors(MotorTestBase):
    """The "should not happen" paths: put() failing although there was room."""
    def fail_put_on(self, nth):
        real = self.m.rbuf.put
        calls = []
        def put(item):
            calls.append(item)
            if len(calls) == nth:
                return False
            return real(item)
        self.m.rbuf.put = put

    def test_simple_cmd_put_failure_raises(self):
        self.fail_put_on(1)
        with self.assertRaises(MotorException):
            self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.assertEqual(self.qlen(), 0)

    def test_turn_put_failure_raises_and_queues_nothing(self):
        self.fail_put_on(1)
        with self.assertRaises(MotorException):
            self.m.add_cmd(MOTOR_CMD_LEFT)
        self.assertEqual(self.qlen(), 0)

    # add_cmd does not roll back (see the FIXME: unput in add_cmd). Entries
    # queued before the failing put stay on the queue.
    def test_cmd_put_failure_raises_and_keeps_the_prefix_stop(self):
        self.fail_put_on(2)
        with self.assertRaises(MotorException):
            self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.assertEqual(self.queued(), [stop_entry()])

    def test_final_stop_put_failure_raises_and_keeps_stop_and_turn(self):
        # FIXME: this leaves a turn on the queue with no stop after it
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        before = self.queued()
        self.fail_put_on(3)
        with self.assertRaises(MotorException):
            self.m.add_cmd(MOTOR_CMD_RIGHT)
        self.assertEqual(self.queued(),
                         before + [stop_entry(), (MOTOR_CMD_RIGHT, 0, MOTOR_INTER_CMD_MS, 0)])

    def test_queue_usable_after_internal_error(self):
        self.fail_put_on(3)
        with self.assertRaises(MotorException):
            self.m.add_cmd(MOTOR_CMD_LEFT)
        self.assertEqual(self.qlen(), 2) # stop, left
        del self.m.rbuf.put # back to the class method
        self.assertTrue(self.m.add_cmd(MOTOR_CMD_LEFT))
        self.assertEqual([e[0] for e in self.queued()],
                         [MOTOR_CMD_STOP, MOTOR_CMD_LEFT,
                          MOTOR_CMD_STOP, MOTOR_CMD_LEFT, MOTOR_CMD_STOP])


class TestAddCmdFull(MotorTestBase):
    def test_fills_to_capacity(self):
        # each forward takes 2 entries: stop, forward
        for _ in range(QSIZE // 2):
            self.assertTrue(self.m.add_cmd(MOTOR_CMD_FORWARD))
        self.assertEqual(self.qlen(), QSIZE)

    def test_simple_command_on_full_queue_returns_false(self):
        # add_cmd: "Returns False if the command did not fit in the buffer"
        self.fill_queue(QSIZE)
        for cmd in (MOTOR_CMD_FORWARD, MOTOR_CMD_REVERSE,
                    MOTOR_CMD_STOP, MOTOR_CMD_STOP_FORCE):
            self.assertFalse(self.m.add_cmd(cmd), cmd)

    def test_full_queue_is_not_modified_by_rejected_command(self):
        self.fill_queue(QSIZE)
        before = self.queued()
        self.m.add_cmd(MOTOR_CMD_STOP)
        self.assertEqual(self.queued(), before)

    def test_space_returns_after_run(self):
        self.fill_queue(QSIZE)
        self.m.run_cmds()
        self.assertTrue(self.m.add_cmd(MOTOR_CMD_REVERSE))
        self.assertEqual(self.qlen(), 2)


#############################################################################
# run_cmds
#############################################################################
class TestRunCmdsBasic(MotorTestBase):
    def test_empty_queue_does_nothing(self):
        self.m.run_cmds()
        self.assertEqual(self.bus.writes, [])
        self.assertEqual(self.qlen(), 0)

    def test_forward(self):
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.run_cmds()
        # the prefix stop runs first
        self.assertEqual(self.bus.writes,
                         STOP_WRITES + [(1, MOTOR_DEF_SPEED, 0), (2, MOTOR_DEF_SPEED, 0)])
        self.assertEqual(self.m.state, [MOTOR_STATE_FWD] * 3)
        self.assertEqual(self.qlen(), 0)

    def test_reverse(self):
        self.m.add_cmd(MOTOR_CMD_REVERSE)
        self.m.run_cmds()
        self.assertEqual(self.bus.writes,
                         STOP_WRITES + [(1, MOTOR_DEF_SPEED, 1), (2, MOTOR_DEF_SPEED, 1)])
        self.assertEqual(self.m.state, [MOTOR_STATE_BKWD] * 3)

    def test_left_turn(self):
        self.m.add_cmd(MOTOR_CMD_LEFT)
        self.m.run_cmds()
        self.assertEqual(self.bus.writes,
                         STOP_WRITES + [(1, MOTOR_DEF_SPEED, 1), (2, MOTOR_DEF_SPEED, 0)])
        self.assertEqual(self.m.state[0], MOTOR_STATE_LEFT)
        self.assertEqual(self.qlen(), 1) # the stop waits for the turn time

    def test_right_turn(self):
        self.m.add_cmd(MOTOR_CMD_RIGHT)
        self.m.run_cmds()
        self.assertEqual(self.bus.writes,
                         STOP_WRITES + [(1, MOTOR_DEF_SPEED, 0), (2, MOTOR_DEF_SPEED, 1)])
        self.assertEqual(self.m.state[0], MOTOR_STATE_RIGHT)

    def test_stop(self):
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.add_cmd(MOTOR_CMD_STOP)
        self.m.run_cmds()
        self.assertEqual(self.bus.writes[-2:], [(1, 0, 0), (2, 0, 0)])
        self.assertEqual(self.m.state, [MOTOR_STATE_STOP] * 3)

    def test_stop_when_already_stopped_is_consumed_without_writes(self):
        self.m.state[0] = MOTOR_STATE_STOP
        self.m.add_cmd(MOTOR_CMD_STOP)
        self.m.run_cmds()
        self.assertEqual(self.bus.writes, [])
        self.assertEqual(self.qlen(), 0)

    def test_stop_force_writes_even_when_stopped(self):
        self.m.state[0] = MOTOR_STATE_STOP
        self.m.add_cmd(MOTOR_CMD_STOP_FORCE)
        self.m.run_cmds()
        self.assertEqual(self.bus.writes, [(1, 0, 0), (2, 0, 0)])
        self.assertEqual(self.qlen(), 0)

    def test_repeated_forward_is_consumed_without_second_write(self):
        self.push((MOTOR_CMD_FORWARD, 0, 0, 0), (MOTOR_CMD_FORWARD, 0, 0, 0))
        self.m.run_cmds()
        self.assertEqual(len(self.bus.writes), 2)
        self.assertEqual(self.qlen(), 0)

    def test_repeated_forward_via_add_cmd_stops_in_between(self):
        # the prefix stop changes the state so the second forward is written
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.run_cmds()
        fwd = [(1, MOTOR_DEF_SPEED, 0), (2, MOTOR_DEF_SPEED, 0)]
        self.assertEqual(self.bus.writes, STOP_WRITES + fwd + STOP_WRITES + fwd)
        self.assertEqual(self.qlen(), 0)

    def test_noop_entry_is_removed_without_writes(self):
        self.push((MOTOR_CMD_NOOP, 0, 0, 0))
        self.m.run_cmds()
        self.assertEqual(self.bus.writes, [])
        self.assertEqual(self.qlen(), 0)

    def test_runs_all_ready_commands_in_one_call_in_order(self):
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.add_cmd(MOTOR_CMD_REVERSE)
        self.m.add_cmd(MOTOR_CMD_STOP)
        self.m.run_cmds()
        self.assertEqual(self.bus.writes,
            STOP_WRITES + [(1, MOTOR_DEF_SPEED, 0), (2, MOTOR_DEF_SPEED, 0)] +
            STOP_WRITES + [(1, MOTOR_DEF_SPEED, 1), (2, MOTOR_DEF_SPEED, 1)] +
            STOP_WRITES)
        self.assertEqual(self.qlen(), 0)

    def test_second_call_with_empty_queue_is_noop(self):
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.run_cmds()
        n = len(self.bus.writes)
        self.m.run_cmds()
        self.assertEqual(len(self.bus.writes), n)

    def test_last_run_updated_on_success(self):
        self.clock.advance(50)
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.run_cmds()
        self.assertEqual(self.m._last_run, self.clock.now)

    def test_last_run_unchanged_when_nothing_runs(self):
        before = self.m._last_run
        self.clock.advance(50)
        self.m.run_cmds()
        self.assertEqual(self.m._last_run, before)

    def test_commands_added_after_a_run_work(self):
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.run_cmds()
        self.m.add_cmd(MOTOR_CMD_REVERSE)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_BKWD)

    def test_queue_wraparound(self):
        # push the ring buffer indexes round the end several times
        for _ in range(QSIZE * 3):
            self.m.add_cmd(MOTOR_CMD_FORWARD)
            self.m.add_cmd(MOTOR_CMD_REVERSE)
            self.m.run_cmds()
            self.assertEqual(self.qlen(), 0)
        self.assertEqual(self.m.state[0], MOTOR_STATE_BKWD)


class TestRunCmdsDelay(MotorTestBase):
    def test_turn_stop_waits_for_turn_time(self):
        self.m.add_cmd(MOTOR_CMD_LEFT)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_LEFT)
        self.clock.advance(MOTOR_TURN_DELAY_MS - 1)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_LEFT)
        self.assertEqual(self.qlen(), 1)

    def test_turn_stop_runs_at_exactly_turn_time(self):
        self.m.add_cmd(MOTOR_CMD_RIGHT)
        self.m.run_cmds()
        self.clock.advance(MOTOR_TURN_DELAY_MS)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_STOP)
        self.assertEqual(self.qlen(), 0)

    def test_turn_stop_runs_after_turn_time(self):
        self.m.add_cmd(MOTOR_CMD_RIGHT)
        self.m.run_cmds()
        self.clock.advance(MOTOR_TURN_DELAY_MS + 100)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_STOP)

    def test_angle_turn_time_is_used(self):
        self.m.add_cmd(MOTOR_CMD_LEFT, 45)
        self.m.run_cmds()
        t = self.m.ms_for_angle(45)
        self.clock.advance(t - 1)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_LEFT)
        self.clock.advance(1)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_STOP)

    def test_delay_is_measured_from_last_run_not_from_add(self):
        self.m.add_cmd(MOTOR_CMD_LEFT)
        self.clock.advance(10_000) # long time before the turn runs
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_LEFT) # stop must still wait
        self.clock.advance(MOTOR_TURN_DELAY_MS)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_STOP)

    def test_waiting_command_blocks_those_behind_it(self):
        self.m.add_cmd(MOTOR_CMD_LEFT)
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.run_cmds()
        self.clock.advance(MOTOR_TURN_DELAY_MS - 1)
        self.m.run_cmds()
        self.assertEqual(self.qlen(), 3) # turn stop, prefix stop, forward
        self.clock.advance(1)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_FWD)
        self.assertEqual(self.qlen(), 0)

    def test_commands_with_delay_wait_for_first_call(self):
        self.push((MOTOR_CMD_FORWARD, 0, 200, 0))
        self.m.run_cmds()
        self.assertEqual(self.bus.writes, [])
        self.clock.advance(200)
        self.m.run_cmds()
        self.assertEqual(len(self.bus.writes), 2)

    def test_waiting_does_not_reset_last_run(self):
        self.push((MOTOR_CMD_FORWARD, 0, 100, 0))
        start = self.m._last_run
        self.clock.advance(60)
        self.m.run_cmds()
        self.clock.advance(60)
        self.m.run_cmds() # 120 ms since last run, not 60
        self.assertEqual(len(self.bus.writes), 2)
        self.assertGreater(self.m._last_run, start)

    def test_full_turn_sequence(self):
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.add_cmd(MOTOR_CMD_RIGHT, 90)
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_RIGHT)
        self.clock.advance(self.m.ms_for_angle(90))
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_FWD)
        self.assertEqual(self.qlen(), 0)


class TestRunCmdsI2cErrors(MotorTestBase):
    # These push raw entries so the prefix stop from add_cmd is not involved.
    def test_failure_keeps_command_with_count_and_retry_delay(self):
        self.bus.fail = 1
        self.push((MOTOR_CMD_FORWARD, 0, 0, 0))
        self.m.run_cmds()
        self.assertEqual(self.queued(), [(MOTOR_CMD_FORWARD, 0, MOTOR_CMD_RETRY_MS, 1)])

    def test_failure_keeps_arg(self):
        self.bus.fail = 1
        self.push((MOTOR_CMD_FORWARD, 7, 0, 0))
        self.m.run_cmds()
        self.assertEqual(self.queued()[0][motor.MOTOR_INDX_ARG], 7)

    def test_failure_of_prefix_stop_keeps_it_first(self):
        self.bus.fail = 1
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.run_cmds()
        self.assertEqual(self.queued(),
                         [(MOTOR_CMD_STOP, 0, MOTOR_CMD_RETRY_MS, 1),
                          (MOTOR_CMD_FORWARD, 0, MOTOR_INTER_CMD_MS, 0)])

    def test_failure_does_not_raise(self):
        self.bus.fail = 1
        self.m.add_cmd(MOTOR_CMD_REVERSE)
        self.m.run_cmds()

    def test_failure_stops_the_run_loop(self):
        self.bus.fail = 1
        self.push((MOTOR_CMD_FORWARD, 0, 0, 0))
        self.m.add_cmd(MOTOR_CMD_STOP)
        self.m.run_cmds()
        self.assertEqual(self.qlen(), 2) # later commands do not jump the queue
        self.assertEqual(self.queued()[1][0], MOTOR_CMD_STOP)

    def test_failure_does_not_update_last_run(self):
        self.bus.fail = 1
        self.push((MOTOR_CMD_FORWARD, 0, 0, 0))
        before = self.m._last_run
        self.clock.advance(30)
        self.m.run_cmds()
        self.assertEqual(self.m._last_run, before)

    def test_retry_waits_for_retry_delay(self):
        # the delay is measured from the last successful run (a failed try does
        # not update _last_run), so it only holds the retry back if that was
        # less than MOTOR_CMD_RETRY_MS ago
        self.bus.fail = 1
        self.push((MOTOR_CMD_FORWARD, 0, 0, 0))
        self.m.run_cmds()
        if MOTOR_CMD_RETRY_MS > 0:
            self.clock.advance(MOTOR_CMD_RETRY_MS - 1)
            self.m.run_cmds()
            self.assertEqual(self.qlen(), 1)
            self.assertNotEqual(self.m.state[0], MOTOR_STATE_FWD)
        self.clock.advance(1)
        self.m.run_cmds()
        self.assertEqual(self.qlen(), 0)
        self.assertEqual(self.m.state[0], MOTOR_STATE_FWD)

    def test_delayed_command_is_not_delayed_again_by_a_failed_try(self):
        # a failed try must not push the retry out by the command's own delay
        self.bus.fail = 1
        self.push((MOTOR_CMD_FORWARD, 0, 100, 0))
        self.clock.advance(100)
        self.m.run_cmds()
        self.assertEqual(self.qlen(), 1)
        self.m.run_cmds()
        self.assertEqual(self.qlen(), 0)

    def test_retry_succeeds_after_delay(self):
        self.bus.fail = 1
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.run_cmds()
        self.clock.advance(MOTOR_CMD_RETRY_MS)
        self.m.run_cmds()
        self.assertEqual(self.qlen(), 0)
        self.assertEqual(self.m.state[0], MOTOR_STATE_FWD)

    def test_commands_behind_a_retried_one_run_after_it_succeeds(self):
        self.bus.fail = 1
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        self.m.add_cmd(MOTOR_CMD_REVERSE)
        self.m.run_cmds()
        self.clock.advance(MOTOR_CMD_RETRY_MS)
        self.m.run_cmds()
        self.assertEqual(self.qlen(), 0)
        self.assertEqual(self.m.state[0], MOTOR_STATE_BKWD)

    def test_count_increments_on_each_failure(self):
        self.bus.fail = MOTOR_CMD_MAX_TRIES # more than needed, see below
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        for expect in range(1, MOTOR_CMD_MAX_TRIES):
            self.m.run_cmds()
            self.assertEqual(self.queued()[0][motor.MOTOR_INDX_COUNT], expect)
            self.clock.advance(MOTOR_CMD_RETRY_MS)

    def test_dropped_after_max_tries(self):
        self.bus.fail = 100
        self.push((MOTOR_CMD_FORWARD, 0, 0, 0))
        for _ in range(MOTOR_CMD_MAX_TRIES):
            self.assertEqual(self.qlen(), 1)
            self.m.run_cmds()
            self.clock.advance(MOTOR_CMD_RETRY_MS)
        self.assertEqual(self.qlen(), 0)

    def test_succeeds_on_last_allowed_try(self):
        self.bus.fail = MOTOR_CMD_MAX_TRIES - 1
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        for _ in range(MOTOR_CMD_MAX_TRIES):
            self.m.run_cmds()
            self.clock.advance(MOTOR_CMD_RETRY_MS)
        self.assertEqual(self.qlen(), 0)
        self.assertEqual(self.m.state[0], MOTOR_STATE_FWD)

    def test_next_command_runs_after_one_is_dropped(self):
        self.bus.fail = 100
        self.push((MOTOR_CMD_FORWARD, 0, 0, 0))
        self.m.add_cmd(MOTOR_CMD_STOP_FORCE)
        for _ in range(MOTOR_CMD_MAX_TRIES):
            self.m.run_cmds()
            self.clock.advance(MOTOR_CMD_RETRY_MS)
        self.assertEqual(self.qlen(), 1)
        self.bus.fail = 0
        self.m.run_cmds()
        self.assertEqual(self.qlen(), 0)
        self.assertEqual(self.m.state[0], MOTOR_STATE_STOP)

    def test_partial_command_is_redone_in_full(self):
        # first motor write works, second fails: state is Unknown until retried
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        orig = self.bus.writeto
        calls = []
        def flaky(addr, buf):
            calls.append(buf[1])
            if len(calls) == 2:
                raise I2cException("second write")
            orig(addr, buf)
        self.bus.writeto = flaky
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_UNK)
        self.clock.advance(MOTOR_CMD_RETRY_MS)
        self.m.run_cmds()
        self.assertEqual(self.m.state, [MOTOR_STATE_FWD] * 3)
        self.assertEqual(self.qlen(), 0)

    def test_turn_stop_keeps_its_place_after_turn_retry(self):
        self.bus.fail = 1
        self.m.add_cmd(MOTOR_CMD_LEFT)
        self.m.run_cmds()
        self.clock.advance(MOTOR_CMD_RETRY_MS)
        self.m.run_cmds() # turn succeeds now
        self.assertEqual(self.m.state[0], MOTOR_STATE_LEFT)
        self.assertEqual(self.qlen(), 1)
        self.clock.advance(MOTOR_TURN_DELAY_MS)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_STOP)

    def test_i2c_subclasses_are_retried(self):
        for exc in (motor.I2cException("x"),):
            self.bus.exc = exc
            self.m.rbuf.clear()
            self.m.add_cmd(MOTOR_CMD_FORWARD)
            self.m.run_cmds()
            self.assertEqual(self.queued()[0][motor.MOTOR_INDX_COUNT], 1)


class TestRunCmdsUnexpected(MotorTestBase):
    def test_unexpected_exception_is_reraised(self):
        self.bus.exc = ValueError("boom")
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        with self.assertRaises(ValueError):
            self.m.run_cmds()

    def test_unexpected_exception_drops_the_command(self):
        self.bus.exc = ValueError("boom")
        self.push((MOTOR_CMD_FORWARD, 0, 0, 0))
        with self.assertRaises(ValueError):
            self.m.run_cmds()
        self.assertEqual(self.qlen(), 0)

    def test_unexpected_exception_leaves_later_commands(self):
        self.bus.exc = ValueError("boom")
        self.push((MOTOR_CMD_FORWARD, 0, 0, 0))
        self.m.add_cmd(MOTOR_CMD_REVERSE)
        with self.assertRaises(ValueError):
            self.m.run_cmds()
        self.assertEqual([e[0] for e in self.queued()], [MOTOR_CMD_STOP, MOTOR_CMD_REVERSE])

    def test_unknown_command_in_queue_is_dropped_and_raised(self):
        self.push((99, 0, 0, 0))
        with self.assertRaises(MotorException):
            self.m.run_cmds()
        self.assertEqual(self.qlen(), 0)

    def test_queue_usable_after_unexpected_exception(self):
        self.bus.exc = ValueError("boom")
        self.m.add_cmd(MOTOR_CMD_FORWARD)
        with self.assertRaises(ValueError):
            self.m.run_cmds()
        self.bus.exc = None
        self.m.add_cmd(MOTOR_CMD_REVERSE)
        self.m.run_cmds()
        self.assertEqual(self.m.state[0], MOTOR_STATE_BKWD)


class TestRunCmdsDebug(MotorTestBase):
    def test_debug_levels_do_not_change_behaviour(self):
        for level in (1, 2):
            m = CarMotors(self.bus, buzz=False, debug=level)
            self.bus.writes.clear()
            m.add_cmd(MOTOR_CMD_FORWARD)
            m.run_cmds()
            self.assertEqual(m.state[0], MOTOR_STATE_FWD, level)

    def test_debug_with_i2c_failure(self):
        m = CarMotors(self.bus, buzz=False, debug=2)
        self.bus.fail = 1
        m.add_cmd(MOTOR_CMD_FORWARD)
        m.run_cmds()
        self.assertEqual(len(m.rbuf), 2) # failed prefix stop and the forward


if __name__ == "__main__":
    unittest.main()
