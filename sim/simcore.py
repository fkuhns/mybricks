# Simulation core: virtual clock, interrupt model, logging and the simulated
# hardware world (I2C devices, car physics, button, pot, IR, ultrasonic).
# The stub modules (machine, utime, framebuf, micropython) call into the
# single Sim instance, SIM, created at the bottom of this file.
import functools
import heapq
import math
import builtins

TICKS_PERIOD = 1 << 30           # MicroPython ticks wrap at 2^30
TICKS_MAX    = TICKS_PERIOD - 1
TICKS_HALF   = TICKS_PERIOD // 2

ENODEV    = 19
EIO       = 5
ETIMEDOUT = 110

_print = builtins.print


class SimStop(BaseException):
    # BaseException so the app's "except Exception" handlers do not catch it
    pass


class SimReset(BaseException):
    # raised by machine.reset()
    pass


class _Event:
    __slots__ = ("t", "seq", "fn", "args", "irq", "cancelled")

    def __init__(self, t, seq, fn, args, irq):
        self.t, self.seq, self.fn, self.args, self.irq = t, seq, fn, args, irq
        self.cancelled = False

    def __lt__(self, other):
        return (self.t, self.seq) < (other.t, other.seq)


#############################################################################
# I2C
#############################################################################
class I2cFault:
    # kind: "timeout" OSError(110), "eio" OSError(5), "enodev" OSError(19)
    #       "short" write returns fewer acks than bytes sent (SoftI2C style)
    #       "stuck_sda" a device holds SDA low, every write times out until
    #       the bus recovery has clocked SCL `clocks` times (-1 = forever)
    def __init__(self, kind, count=1, addr=None, acks=0, clocks=4):
        self.kind, self.count, self.addr = kind, count, addr
        self.acks, self.clocks = acks, clocks

    def __str__(self):
        a = "any" if self.addr is None else "0x%02x" % self.addr
        return "%s x%d addr %s" % (self.kind, self.count, a)


class I2cWorld:
    # One physical bus: the devices on it and the faults waiting to happen
    def __init__(self, sim, id, sda_pin, scl_pin):
        self.sim, self.id = sim, id
        self.sda_pin, self.scl_pin = sda_pin, scl_pin
        self.devices = {}
        self.faults  = []
        self.sda_stuck = 0  # SCL clocks still needed to free SDA, -1 forever
        self.created = 0    # machine.I2C objects created (1 + bus resets)
        self.writes  = 0
        self.errors  = 0

    def add(self, dev):
        self.devices[dev.addr] = dev
        return dev

    def fail(self, kind, count=1, addr=None, **kw):
        f = I2cFault(kind, count, addr, **kw)
        self.faults.append(f)
        self.sim.log("FAULT", "I2C%d inject %s" % (self.id, f))

    def clear_faults(self):
        self.faults = []
        self.sda_stuck = 0

    def _take_fault(self, addr):
        for f in self.faults:
            if f.count != 0 and (f.addr is None or f.addr == addr):
                if f.count > 0:
                    f.count -= 1
                if f.count == 0:
                    self.faults.remove(f)
                return f
        return None

    def write(self, addr, parts, freq):
        # parts: list of buffers sent in one transaction
        nbytes = sum(len(p) for p in parts)
        self.writes += 1
        # address frame + data frames, 9 clocks each
        self.sim.advance_us(int((1 + nbytes) * 9 * 1_000_000 / freq) + 10)

        f = self._take_fault(addr)
        if f is not None:
            self.errors += 1
            if f.kind == "stuck_sda":
                self.sda_stuck = f.clocks
                self.sim.log("I2C", "I2C%d SDA stuck low" % self.id)
            elif f.kind == "short":
                self.sim.log("I2C", "0x%02x short write, %d of %d acks" % (addr, f.acks, nbytes), 2)
                return f.acks
            else:
                code = {"timeout": ETIMEDOUT, "eio": EIO, "enodev": ENODEV}[f.kind]
                self.sim.log("I2C", "0x%02x write -> OSError(%d)" % (addr, code), 2)
                raise OSError(code)

        if self.sda_stuck:
            self.errors += 1
            self.sim.log("I2C", "0x%02x write -> OSError(%d), SDA stuck" % (addr, ETIMEDOUT), 2)
            raise OSError(ETIMEDOUT)

        dev = self.devices.get(addr)
        if dev is None or dev.offline:
            self.errors += 1
            self.sim.log("I2C", "0x%02x no ack -> OSError(%d)" % (addr, ENODEV), 2)
            raise OSError(ENODEV)

        dev.write(parts)
        return nbytes

    def scl_rising(self):
        # bus recovery clocks SCL by hand while SDA is stuck
        if self.sda_stuck > 0:
            self.sda_stuck -= 1
            if self.sda_stuck == 0:
                self.sim.log("I2C", "I2C%d SDA released" % self.id)

    def sda_level(self):
        return 0 if self.sda_stuck else 1


class I2cDevice:
    def __init__(self, sim, addr, name):
        self.sim, self.addr, self.name = sim, addr, name
        self.offline = False

    def set_offline(self, offline=True):
        self.offline = offline
        self.sim.log("FAULT", "%s 0x%02x %s" % (self.name, self.addr,
                     "offline" if offline else "back online"))


class MotorController(I2cDevice):
    # PicoBricks motor driver: [0x26, motor, speed, dir, xor] per write
    def __init__(self, sim, addr=0x22):
        super().__init__(sim, addr, "MotorCtl")
        self.motors = {1: (0, 0), 2: (0, 0)} # motor: (speed, dir)
        self.bad_packets = 0

    def write(self, parts):
        data = b"".join(bytes(p) for p in parts)
        if len(data) != 5 or data[0] != 0x26 or data[4] != data[1] ^ data[2] ^ data[3]:
            self.bad_packets += 1
            self.sim.log("MOTOR", "bad packet %s" % data.hex())
            return
        mid, speed, dir = data[1], data[2], data[3]
        if mid in self.motors and self.motors[mid] != (speed, dir):
            self.motors[mid] = (speed, dir)
            self.sim.car.motors_changed(self.motors)

    def wheels(self):
        # signed speed of the left (1) and right (2) wheel
        return [s if d == 0 else -s for s, d in (self.motors[1], self.motors[2])]


class OledDevice(I2cDevice):
    # SSD1306: 0x80 = command byte follows, 0x40 = display data follows.
    # Text drawn into the framebuf stub is shown when a data write succeeds.
    def __init__(self, sim, addr=0x3c):
        super().__init__(sim, addr, "OLED")
        self.on    = False
        self.rows  = []
        self.shows = 0

    def write(self, parts):
        ctrl = parts[0][0]
        if ctrl == 0x80:
            cmd = parts[0][1]
            if cmd in (0xAE, 0xAF):
                self.on = cmd == 0xAF
        elif ctrl == 0x40 and len(parts) > 1:
            import framebuf
            fb = framebuf.lookup(parts[1])
            rows = fb.rows() if fb else ["?"]
            self.shows += 1
            if rows != self.rows:
                self.rows = rows
                self.sim.log("OLED", " | ".join(rows) if self.on else "(display off)")


#############################################################################
# Car physics
#############################################################################
class Car:
    # Differential drive in a rectangular room, units are inches and degrees.
    # At MOTOR speed REF_SPEED the car drives speed_ips and pivots turn_dps.
    REF_SPEED = 80

    def __init__(self, sim):
        self.sim = sim
        self.room = (120.0, 120.0)
        self.obstacles = []       # (x, y, radius)
        self.x, self.y, self.heading = 60.0, 20.0, 90.0
        self.speed_ips = 12.0
        self.turn_dps  = 180.0
        self.lag_ms    = 0        # motor spin up before the car moves
        self._wheels   = [0, 0]   # speeds in effect
        self._pending  = None     # (t_us, wheels) waiting for lag
        self.bumps     = 0
        self._touching = False
        self.odometer  = 0.0

    def place(self, x, y, heading):
        self.x, self.y, self.heading = float(x), float(y), float(heading)

    def motors_changed(self, motors):
        w = [s if d == 0 else -s for s, d in (motors[1], motors[2])]
        self.sim.log("MOTOR", "L %+4d  R %+4d   %s" % (w[0], w[1], self.pose()))
        if self.lag_ms:
            self._pending = (self.sim.now_us + self.lag_ms * 1000, w)
        else:
            self._wheels = w

    def pose(self):
        return "@ (%.1f, %.1f) %3.0f deg" % (self.x, self.y, self.heading % 360)

    def step(self, t0_us, t1_us):
        if self._pending and self._pending[0] <= t1_us:
            self._move((self._pending[0] - t0_us) / 1e6)
            t0_us = self._pending[0]
            self._wheels = self._pending[1]
            self._pending = None
        self._move((t1_us - t0_us) / 1e6)

    def _move(self, dt):
        if dt <= 0 or self._wheels == [0, 0]:
            return
        k  = self.speed_ips / self.REF_SPEED
        vl, vr = self._wheels[0] * k, self._wheels[1] * k
        v  = (vl + vr) / 2
        w  = (vr - vl) / (2 * self.speed_ips) * self.turn_dps # deg/s, + is left
        while dt > 0:
            h  = min(dt, 0.01)
            dt -= h
            self.heading += w * h
            r = math.radians(self.heading)
            nx = self.x + v * h * math.cos(r)
            ny = self.y + v * h * math.sin(r)
            if self._blocked(nx, ny):
                if not self._touching:
                    self._touching = True
                    self.bumps += 1
                    self.sim.log("BUMP", "car hit something %s" % self.pose())
            else:
                self.odometer += abs(v * h)
                self.x, self.y = nx, ny
                if self._touching and not self._blocked(nx, ny, 3.5):
                    self._touching = False # clear of the surface again

    def _blocked(self, x, y, radius=3.0):
        w, h = self.room
        if x < radius or y < radius or x > w - radius or y > h - radius:
            return True
        return any(math.hypot(x - ox, y - oy) < r + radius for ox, oy, r in self.obstacles)

    def range_ahead(self):
        # distance from the sensor along the heading to the nearest surface
        r  = math.radians(self.heading)
        dx, dy = math.cos(r), math.sin(r)
        w, h = self.room
        best = math.inf
        for t in ((0 - self.x) / dx if dx else -1, (w - self.x) / dx if dx else -1,
                  (0 - self.y) / dy if dy else -1, (h - self.y) / dy if dy else -1):
            if t > 0:
                best = min(best, t)
        for ox, oy, rad in self.obstacles:
            fx, fy = ox - self.x, oy - self.y
            proj = fx * dx + fy * dy
            d2 = fx * fx + fy * fy - proj * proj
            if proj > 0 and d2 < rad * rad:
                best = min(best, proj - math.sqrt(rad * rad - d2))
        return best


#############################################################################
# Simulator
#############################################################################
class Sim:
    CPU_US = 50  # simulated cost of a ticks/pin/adc call, keeps time moving

    def __init__(self):
        self.now_us   = 0
        self.t0_us    = 0      # scenario times are relative to this
        self._events  = []
        self._seq     = 0
        self._busy    = False  # inside advance_us()
        self.irq_off  = 0
        self._pending_irqs = []
        self.end_us   = None
        self.stopped  = False
        self.verbose  = 1
        self.app_log  = True
        self.app      = None
        self.results  = []     # (passed, t_ms, msg)
        self.pins     = {}

        self.car   = Car(self)
        self.i2c   = {0: I2cWorld(self, 0, sda_pin=4, scl_pin=5)}
        self.motor = self.i2c[0].add(MotorController(self))
        self.oled  = self.i2c[0].add(OledDevice(self))

        self.pot_raw = 15 << 5        # Pot.get_value() -> 16 ms
        self.distance_override = None # None = use the car model, "timeout" = no echo, or inches
        self.pings = 0

    # ---------------------------------------------------------------- time
    def now_ms(self):
        # ms since the scenario started
        return (self.now_us - self.t0_us) / 1000

    def advance_us(self, us):
        if self.stopped:
            raise SimStop()
        target = self.now_us + max(0, int(us))
        if self._busy:
            # called from inside an event, the outer loop handles events
            self.car.step(self.now_us, target)
            self.now_us = target
            return
        self._busy = True
        try:
            while self._events and self._events[0].t <= target:
                ev = heapq.heappop(self._events)
                if ev.cancelled:
                    continue
                self.car.step(self.now_us, max(self.now_us, ev.t))
                self.now_us = max(self.now_us, ev.t)
                if ev.irq:
                    self.irq(ev.fn, *ev.args)
                else:
                    ev.fn(*ev.args)
            self.car.step(self.now_us, target)
            self.now_us = max(self.now_us, target)
        finally:
            self._busy = False
        if self.end_us is not None and self.now_us >= self.end_us:
            self.stopped = True
            raise SimStop()

    def cpu(self, us=None):
        self.advance_us(self.CPU_US if us is None else us)

    def ticks_ms(self):
        self.cpu()
        return (self.now_us // 1000) & TICKS_MAX

    def ticks_us(self):
        self.cpu()
        return self.now_us & TICKS_MAX

    # ---------------------------------------------------------------- events
    def _schedule(self, t_us, fn, args, irq):
        self._seq += 1
        ev = _Event(int(t_us), self._seq, fn, args, irq)
        heapq.heappush(self._events, ev)
        return ev

    def at(self, ms, fn, *args, **kw):
        # run fn(*args, **kw) at scenario time ms
        if kw:
            fn = functools.partial(fn, **kw)
        return self._schedule(self.t0_us + ms * 1000, fn, args, False)

    def after_us(self, us, fn, *args, irq=False):
        return self._schedule(self.now_us + us, fn, args, irq)

    def end(self, ms):
        self.end_us = self.t0_us + ms * 1000

    # ---------------------------------------------------------------- irqs
    def irq(self, fn, *args):
        # run an interrupt handler now, or when interrupts are re-enabled
        if self.irq_off:
            self._pending_irqs.append((fn, args))
            return
        self.irq_off = 1
        try:
            fn(*args)
        finally:
            self.irq_off = 0
        self._drain_irqs()

    def disable_irq(self):
        self.cpu(2)
        prev, self.irq_off = self.irq_off, 1
        return prev

    def enable_irq(self, state=0):
        self.irq_off = state
        if not state:
            self._drain_irqs()

    def _drain_irqs(self):
        while self._pending_irqs and not self.irq_off:
            fn, args = self._pending_irqs.pop(0)
            self.irq(fn, *args)

    # ---------------------------------------------------------------- logging
    def stamp(self):
        return "%9.3f" % ((self.now_us - self.t0_us) / 1e6)

    def log(self, tag, msg, level=1):
        if self.verbose >= level:
            _print("%s SIM %-6s %s" % (self.stamp(), tag, msg))

    def app_print(self, *args, **kw):
        if self.app_log:
            _print(self.stamp(), "app   ", *args, **kw)

    # ---------------------------------------------------------------- checks
    def expect(self, ms, cond, msg):
        # evaluate cond() at time ms, record pass/fail
        def check():
            try:
                ok = bool(cond())
            except Exception as e:
                ok, msg2 = False, "%s (raised %r)" % (msg, e)
            else:
                msg2 = msg
            self.results.append((ok, ms, msg2))
            self.log("CHECK", "%s  %s" % ("PASS" if ok else "FAIL", msg2))
        self.at(ms, check)

    # ---------------------------------------------------------------- pins
    def pin(self, num):
        st = self.pins.get(num)
        if st is None:
            st = self.pins[num] = PinState(self, num)
        return st

    # ---------------------------------------------------------------- inputs
    def press_button(self, hold_ms=150, bounces=0):
        # rising edge on the button pin, optional contact bounce
        p = self.pin(10)
        self.log("INPUT", "button press%s" % (", %d bounces" % bounces if bounces else ""))
        p.drive(1)
        for i in range(bounces):
            self.after_us((i * 2 + 1) * 1000, p.drive, 0)
            self.after_us((i * 2 + 2) * 1000, p.drive, 1)
        self.after_us(hold_ms * 1000, p.drive, 0)

    def set_pot_ms(self, ms):
        # Pot.get_value() = 1 + (read_u16 >> 5)
        self.pot_raw = max(0, min(65535, (int(ms) - 1) << 5))
        self.log("INPUT", "pot -> %d ms" % ms)

    def set_distance(self, inches):
        # inches, "timeout", or None to go back to the car model
        self.distance_override = inches
        self.log("INPUT", "distance -> %s" % ("car model" if inches is None else inches))

    def echo_us(self):
        self.pings += 1
        d = self.distance_override
        if d is None:
            d = self.car.range_ahead()
        if d == "timeout" or d > 400:
            return None
        return 2 * d / 0.01359876

    def ir_send(self, cmd, addr=0x00, fault=None, repeat=False):
        # NEC frame as pin edges on GPIO 0. fault: "data", "addr", "short", "start"
        p = self.pin(0)
        if repeat:
            widths = [9000, 2250, 562]
        else:
            lead = 3000 if fault == "start" else 9000
            ncmd = (~cmd & 0xff) ^ (0x01 if fault == "data" else 0)
            naddr = (~addr & 0xff) ^ (0x01 if fault == "addr" else 0)
            val = addr | naddr << 8 | cmd << 16 | ncmd << 24
            widths = [lead, 4500]
            for i in range(32):
                widths += [562, 1687 if (val >> i) & 1 else 562]
            widths.append(562)
            if fault == "short":
                widths = widths[:40]
        self.log("INPUT", "IR %s 0x%02x%s" % ("repeat" if repeat else "cmd", cmd,
                 ", fault " + fault if fault else ""))
        t = 1000
        p.drive_toggle_at(t)
        for w in widths:
            t += w
            p.drive_toggle_at(t)

    # ---------------------------------------------------------------- summary
    def summary(self):
        _print("")
        _print("=" * 70)
        _print("t = %.3f s   car %s   odometer %.1f in   bumps %d" % (
               self.now_ms() / 1e3, self.car.pose(), self.car.odometer, self.car.bumps))
        _print("motors L %+d R %+d   bad packets %d" % (
               *self.motor.wheels(), self.motor.bad_packets))
        b = self.i2c[0]
        _print("I2C0 writes %d  errors %d  bus objects created %d (resets %d)" % (
               b.writes, b.errors, b.created, max(0, b.created - 1)))
        _print("OLED %s" % (" | ".join(self.oled.rows) or "(nothing shown)"))
        if self.app is not None:
            _print("app motor state %s" % self.app.motors.state)
        passed = sum(1 for r in self.results if r[0])
        _print("checks: %d passed, %d failed" % (passed, len(self.results) - passed))
        for ok, ms, msg in self.results:
            if not ok:
                _print("   FAIL @ %d ms: %s" % (ms, msg))
        _print("=" * 70)
        return all(r[0] for r in self.results)


class PinState:
    # shared state for every machine.Pin object on the same GPIO number
    def __init__(self, sim, num):
        self.sim, self.num = sim, num
        self.level   = 0
        self.mode    = None
        self.handler = None
        self.trigger = 0

    def drive(self, level):
        # the outside world drives an input pin
        old, self.level = self.level, level
        if self.handler and old != level:
            from machine import Pin
            edge = Pin.IRQ_RISING if level else Pin.IRQ_FALLING
            if self.trigger & edge:
                self.sim.irq(self.handler, self.sim._pin_obj(self.num))

    def drive_toggle_at(self, us):
        self.sim.after_us(us, lambda: self.drive(1 - self.level))


def _pin_obj(num):
    from machine import Pin
    return Pin(num)


SIM = Sim()
SIM._pin_obj = _pin_obj
