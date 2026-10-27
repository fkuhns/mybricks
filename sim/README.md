# smartCar simulator

Runs `smartCar/main.py` and `common/*.py` unmodified on a laptop (CPython 3.10+)
against simulated hardware. Stub `machine`, `utime`, `micropython` and `framebuf`
modules sit in front of the real code on `sys.path`.

```
python3 sim/run.py sim/scenarios/i2c_faults.py      # one scenario, full log
python3 sim/run.py sim/scenarios/dist_room.py -q    # hide the app's own prints
python3 sim/run.py sim/scenarios/ir_drive.py -v     # also every I2C error, buzzer toggle
python3 sim/run.py --all                            # every scenario, PASS/FAIL
python3 sim/run.py sim/scenarios/ir_drive.py --start-ms 1073736824  # ticks wrap 5 s in
```

## Time

The clock is virtual. `sleep*`, I2C transfers (bytes x 9 clocks / freq), echo
waits, and a small CPU cost per `ticks_*`/pin/ADC call advance it. A 40 s
scenario runs in about a second and gives the same result on every run.
Timer callbacks and pin IRQs fire when their time comes, between calls, as
interrupts would; while `disable_irq()` is in effect they are held until
`enable_irq()`.

Ticks wrap at 2^30 like MicroPython; `--start-ms` puts the start near the wrap.

## Simulated hardware

| Device | Where | Notes |
|---|---|---|
| I2C bus 0 | `sim.i2c[0]` | `fail(kind, count, addr)`, `clear_faults()`, stats `writes`, `errors`, `created` |
| Motor controller 0x22 | `sim.motor` | checks packet + checksum, `wheels()` -> `[left, right]` signed speeds, `set_offline()` |
| OLED 0x3c | `sim.oled` | logs the text rows on each successful `show()`, `set_offline()` |
| Button GPIO 10, LED GPIO 7 | `sim.press_button(hold_ms, bounces)` | `sim.pin(7).level` |
| Pot ADC 26 | `sim.set_pot_ms(ms)` | value returned by `Pot.get_value()` |
| Ultrasonic | `sim.set_distance(inches / "timeout" / None)` | `None` = measured from the car model |
| IR GPIO 0 | `sim.ir_send(cmd, addr, fault, repeat)` | real NEC edge timings through the real decoder; fault `"data"`, `"addr"`, `"short"`, `"start"` |
| Buzzer PWM | log only | |
| Car | `sim.car` | room, obstacles, pose, `speed_ips`, `turn_dps` at speed 80, `lag_ms`, `bumps` |

I2C fault kinds for `sim.i2c[0].fail(kind, count=1, addr=None, ...)`:

- `"timeout"`: OSError(110)
- `"eio"`: OSError(5)
- `"enodev"`: OSError(19), the address was not acked
- `"short"`: the write returns `acks` (default 0) instead of the byte count, as SoftI2C does on a data NACK
- `"stuck_sda"`: a device holds SDA low and every write times out until the bus recovery has clocked SCL `clocks` times (default 4, -1 = never)

`count=-1` keeps the fault until `clear_faults()`. A device that is offline
fails every write with OSError(19).

## Writing a scenario

```python
MODE        = "MODE_2"        # a MODE_* name from main.py, or an int
DURATION_MS = 10_000

def scenario(sim):
    sim.at(200, sim.press_button)                       # times are ms from start
    sim.at(1_000, sim.ir_send, 0x18)                    # IR "up"
    sim.at(2_000, sim.i2c[0].fail, "timeout", 3, 0x22)
    sim.expect(3_000, lambda: sim.motor.wheels() == [80, 80], "still driving")
    sim.expect(3_000, lambda: sim.app.motors.state[0] == "Forward", "app agrees")
```

`sim.app` is the `MyApp` instance, created after `scenario()` returns, so only
use it inside the lambdas. The run exits non-zero if any check fails.

`known_stop_dropped.py` is expected to fail until the FIXME in
`CarMotors.run_cmds` (a STOP dropped after its retries run out) is fixed.

## Limits

- No real concurrency: an "interrupt" runs at the next simulator call, not
  between any two bytecodes, so it will not catch every race.
- RP2 hardware I2C reports most failures as OSError and may never return a
  short ack count; `"short"` exercises that code path anyway.
- The OLED shows text, not pixels.
