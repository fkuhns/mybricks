# Tests for common.ir.IRMgr.
# Run from anywhere:  python3 tests/ir_tests.py
# Uses the sim/ stubs for machine/utime and fake motors and OLED that record
# what they are given. Most tests call the receiver's do_callback(), the same
# entry point the NEC decoder uses, the end to end tests send real NEC frames
# through the simulated IR pin.
import builtins
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

from simcore import SIM
import ir
from ir import IRMgr, IR_ERRS, IR_CMD_MAP
from ir_sensor import IR_RX, IR_BLOCK_MS
from motor import (MOTOR_CMD_FORWARD, MOTOR_CMD_LEFT, MOTOR_CMD_REVERSE,
                   MOTOR_CMD_RIGHT, MOTOR_CMD_STOP, MOTOR_CMD_NOOP)

SIM.verbose = 0
SIM.app_log = False

UP, DOWN, LEFT, RIGHT, OK = (IR_RX.number_up, IR_RX.number_down, IR_RX.number_left,
                             IR_RX.number_right, IR_RX.number_ok)
UNMAPPED = IR_RX.number_5
FRAME_US = 70_000 + IR_BLOCK_MS * 1000 # an NEC frame (~68ms) plus the decoder's timeout


class FakeMotors:
    def __init__(self):
        self.cmds  = []
        self.fail  = None # exception add_cmd raises while set

    def add_cmd(self, cmd, arg=0):
        if self.fail is not None:
            raise self.fail
        self.cmds.append(cmd)
        return True


class FakeOled:
    def __init__(self):
        self.rows = []
        self.fail = None # exception update_row3 raises while set

    def update_row3(self, txt):
        if self.fail is not None:
            raise self.fail
        self.rows.append(txt)


class IRTestBase(unittest.TestCase):
    def setUp(self):
        SIM.irq_off = 0
        SIM._pending_irqs = []
        self.motors = FakeMotors()
        self.oled = FakeOled()
        self.ir = self.make()

    def make(self, **kw):
        mgr = IRMgr(self.motors, self.oled, **kw)
        mgr.start()
        return mgr

    def send(self, cmd, addr=0x00):
        # what the decoder does at the end of a frame, run as an interrupt
        SIM.irq(self.ir.ctrl.do_callback, cmd, addr, 0, IR_RX.REPEAT)


class TestInit(IRTestBase):
    def test_starts_clear(self):
        self.assertFalse(self.ir.rx)
        self.assertEqual(self.ir.cmd, 0)
        self.assertEqual(self.ir.err_code, 0)

    def test_hooks_receiver(self):
        self.assertEqual(self.ir.ctrl._callback, self.ir.callback)
        self.assertEqual(self.ir.ctrl._errf, self.ir.err)
        self.assertEqual(self.ir.ctrl._pin.id, ir.IR_PIN)

    def test_str(self):
        self.assertIn("IRMgr", str(self.ir))

    def test_run_with_nothing_pending(self):
        self.ir.run()
        self.assertEqual(self.motors.cmds, [])
        self.assertEqual(self.oled.rows, [])


class TestCommands(IRTestBase):
    def test_each_mapped_button(self):
        expect = {UP: MOTOR_CMD_FORWARD, DOWN: MOTOR_CMD_REVERSE,
                  LEFT: MOTOR_CMD_LEFT, RIGHT: MOTOR_CMD_RIGHT, OK: MOTOR_CMD_STOP}
        for cmd, mcmd in expect.items():
            self.send(cmd)
            self.ir.run()
            self.assertEqual(self.motors.cmds[-1], mcmd)
        self.assertEqual(len(self.motors.cmds), len(expect))
        self.assertEqual(self.oled.rows, [])

    def test_repeat_is_noop(self):
        # decode() passes thresh=REPEAT so REPEAT goes to the callback, not
        # the error function, like any other command
        self.send(IR_RX.REPEAT)
        self.assertTrue(self.ir.rx)
        self.assertEqual(self.ir.cmd, IR_RX.REPEAT)
        self.assertEqual(self.ir.err_code, 0)
        self.ir.run()
        self.assertEqual(self.motors.cmds, [MOTOR_CMD_NOOP])
        self.assertEqual(self.oled.rows, [])

    def test_callback_saves_cmd(self):
        self.send(LEFT, 0x12)
        self.assertTrue(self.ir.rx)
        self.assertEqual(self.ir.cmd, LEFT)

    def test_command_used_once(self):
        self.send(UP)
        self.ir.run()
        self.ir.run()
        self.assertEqual(self.motors.cmds, [MOTOR_CMD_FORWARD])
        self.assertFalse(self.ir.rx)
        self.assertEqual(self.ir.cmd, 0)

    def test_latest_command_wins(self):
        # only one command is held, a newer one overwrites an unread one
        self.send(UP)
        self.send(DOWN)
        self.ir.run()
        self.assertEqual(self.motors.cmds, [MOTOR_CMD_REVERSE])

    def test_unmapped_button(self):
        self.send(UNMAPPED)
        self.ir.run()
        self.assertEqual(self.motors.cmds, [])
        self.assertEqual(self.oled.rows, ["Unknown IR cmd"])
        self.assertFalse(self.ir.rx)

    # FIXME: fails, IRMgr no longer takes cmd_map (see the FIXME in ir.py).
    # Restore the argument or remove this test.
    def test_custom_map(self):
        self.ir = self.make(cmd_map={UNMAPPED: MOTOR_CMD_STOP})
        self.send(UNMAPPED)
        self.ir.run()
        self.send(UP)
        self.ir.run()
        self.assertEqual(self.motors.cmds, [MOTOR_CMD_STOP])
        self.assertEqual(self.oled.rows, ["Unknown IR cmd"])

    def test_default_map(self):
        self.assertIs(self.ir.cmd_map, IR_CMD_MAP)


class TestErrors(IRTestBase):
    def test_each_error_code(self):
        for code, name in IR_ERRS.items():
            self.send(code)
            self.assertFalse(self.ir.rx) # errors don't go to the callback
            self.ir.run()
            self.assertEqual(self.oled.rows[-1], name)
        self.assertEqual(len(self.oled.rows), len(IR_ERRS))
        self.assertEqual(self.motors.cmds, [])

    def test_error_shown_once(self):
        self.send(IR_RX.BADDATA)
        self.ir.run()
        self.ir.run()
        self.assertEqual(self.oled.rows, ["BADDATA"])
        self.assertEqual(self.ir.err_code, 0)

    def test_unknown_error_code(self):
        self.send(-42)
        self.ir.run()
        self.assertEqual(self.oled.rows, ["bad code"])

    def test_error_and_command_pending(self):
        self.send(UP)
        self.send(IR_RX.BADSTART)
        self.ir.run()
        self.assertEqual(self.oled.rows, ["BADSTART"])
        self.assertEqual(self.motors.cmds, [MOTOR_CMD_FORWARD])

    def test_motor_exception_ignored(self):
        self.motors.fail = OSError(5)
        self.send(UP)
        self.ir.run() # must not raise
        self.assertFalse(self.ir.rx)
        self.motors.fail = None
        self.send(DOWN)
        self.ir.run()
        self.assertEqual(self.motors.cmds, [MOTOR_CMD_REVERSE])

    def test_oled_exception_on_unknown_cmd_ignored(self):
        self.oled.fail = OSError(5)
        self.send(UNMAPPED)
        self.ir.run() # must not raise
        self.assertFalse(self.ir.rx)


class TestIrqSafety(IRTestBase):
    def test_reset_clears_pending(self):
        self.send(UP)
        self.send(IR_RX.BADDATA)
        self.ir.stop()
        self.ir.run()
        self.assertEqual(self.motors.cmds, [])
        self.assertEqual(self.oled.rows, [])

    def test_irqs_enabled_after_run(self):
        self.send(UP)
        self.send(IR_RX.BADDATA)
        self.ir.run()
        self.assertEqual(SIM.irq_off, 0)

    def test_command_during_critical_section_not_lost(self):
        # a frame that ends while run() holds interrupts off is delivered when
        # they come back on and must be left for the next run()
        real = ir.disable_irq
        calls = [0]
        def disable_irq():
            s = real()
            calls[0] += 1
            if calls[0] == 2: # 1st is the error check, 2nd takes the command
                self.send(DOWN)
            return s
        ir.disable_irq = disable_irq
        try:
            self.send(UP)
            self.ir.run()
        finally:
            ir.disable_irq = real
        self.assertEqual(self.motors.cmds, [MOTOR_CMD_FORWARD])
        self.assertTrue(self.ir.rx)
        self.ir.run()
        self.assertEqual(self.motors.cmds, [MOTOR_CMD_FORWARD, MOTOR_CMD_REVERSE])


class TestEndToEnd(IRTestBase):
    # NEC frames on the simulated IR pin through the real decoder
    def frame(self, cmd, **kw):
        SIM.ir_send(cmd, **kw)
        SIM.advance_us(FRAME_US)
        self.ir.run()

    def test_frames(self):
        self.frame(UP)
        self.frame(OK)
        self.assertEqual(self.motors.cmds, [MOTOR_CMD_FORWARD, MOTOR_CMD_STOP])

    def test_repeat_frame(self):
        self.frame(UP)
        self.frame(UP, repeat=True)
        self.assertEqual(self.motors.cmds, [MOTOR_CMD_FORWARD, MOTOR_CMD_NOOP])

    def test_fault_frames(self):
        for fault, name in (("data", "BADDATA"), ("addr", "BADADDR"),
                            ("start", "BADSTART"), ("short", "BADBLOCK")):
            self.frame(UP, fault=fault)
            self.assertEqual(self.oled.rows[-1], name)
        self.assertEqual(self.motors.cmds, [])


if __name__ == "__main__":
    unittest.main()
