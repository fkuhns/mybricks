# Tests for common.Device, the init/start/stop lifecycle base class.
# Run from anywhere:  python3 tests/device_tests.py
import builtins
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "sim"), os.path.join(ROOT, "common")]
import micropython
builtins.const = micropython.const

from common import Device


class Rec(Device):
    # From Device:
    #  _init()  called from Device.init()  - Device state = Device.STATE_INIT
    #  _stop()  called from Device.stop()  - Device state = Device.STATE_STOP
    #  _start() called from Device.start() - Device state = Device.STATE_START
    # Inherits is_on() and is_off() from Device, which check the Device state.
    # records hook calls, does not call Device.__init__() on purpose
    def __init__(self, init=True):
        self.calls = []
        self.fail  = None # hook name that raises while set
        if init:
            self.init()

    def _hook(self, name):
        if self.fail == name:
            raise OSError(name)
        self.calls.append(name)

    def _init(self):  self._hook("init")
    def _start(self): self._hook("start")
    def _stop(self):  self._hook("stop")


class TestDevice(unittest.TestCase):
    def test_init_leaves_off(self):
        d = Rec()
        self.assertEqual(d.calls, ["init"])
        self.assertTrue(d.is_off())

    def test_start_stop(self):
        d = Rec()
        d.start()
        self.assertTrue(d.is_on())
        d.stop()
        self.assertTrue(d.is_off())
        self.assertEqual(d.calls, ["init", "start", "stop"])

    def test_start_and_stop_are_idempotent(self):
        d = Rec()
        d.start(); d.start()
        d.stop(); d.stop()
        self.assertEqual(d.calls, ["init", "start", "stop"])

    def test_start_inits_if_needed(self):
        d = Rec(init=False)
        d.start()
        self.assertEqual(d.calls, ["init", "start"])

    def test_stop_before_init_is_noop(self):
        d = Rec(init=False)
        d.stop()
        self.assertEqual(d.calls, [])

    def test_init_while_on_stops_first(self):
        d = Rec()
        d.start()
        d.init()
        self.assertEqual(d.calls, ["init", "start", "stop", "init"])
        self.assertTrue(d.is_off())

    def test_restart_does_not_reinit(self):
        d = Rec()
        d.start(); d.stop(); d.start()
        self.assertEqual(d.calls, ["init", "start", "stop", "start"])

    def test_failed_hook_keeps_state(self):
        d = Rec()
        d.start()
        d.fail = "stop"
        self.assertRaises(OSError, d.stop)
        self.assertTrue(d.is_on()) # still on, stop() can be retried
        d.fail = None
        d.stop()
        self.assertTrue(d.is_off())

        d.fail = "start"
        self.assertRaises(OSError, d.start)
        self.assertTrue(d.is_off())

    def test_state_is_per_instance(self):
        a, b = Rec(), Rec()
        a.start()
        self.assertTrue(b.is_off())


if __name__ == "__main__":
    unittest.main()
