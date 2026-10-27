# Stub of the MicroPython machine module, backed by the simulator
from simcore import SIM, SimReset

_I2C_PINS = {0: (4, 5)}   # bus id: (SDA, SCL)
_LED_PIN  = 7


class Pin:
    IN, OUT, OPEN_DRAIN = 0, 1, 2
    PULL_UP, PULL_DOWN  = 1, 2
    IRQ_FALLING, IRQ_RISING = 4, 8

    def __init__(self, id, mode=None, pull=None, value=None):
        self.id = id
        self._st = SIM.pin(id)
        if mode is not None:
            self._st.mode = mode
        if value is not None:
            self.value(value)

    def __repr__(self):
        return "Pin(%d)" % self.id

    def _i2c_world(self):
        for bid, (sda, scl) in _I2C_PINS.items():
            if self.id in (sda, scl):
                return SIM.i2c[bid], self.id == sda
        return None, False

    def value(self, v=None):
        SIM.cpu(2)
        world, is_sda = self._i2c_world()
        if v is None:
            if world and is_sda:
                return world.sda_level() & self._st.level
            return self._st.level
        v = 1 if v else 0
        if world and not is_sda and v and not self._st.level:
            world.scl_rising()
        if self.id == _LED_PIN and v != self._st.level:
            SIM.log("LED", "on" if v else "off")
        self._st.level = v

    def on(self):   self.value(1)
    def off(self):  self.value(0)
    def high(self): self.value(1)
    def low(self):  self.value(0)
    __call__ = value

    def irq(self, handler=None, trigger=IRQ_FALLING | IRQ_RISING):
        self._st.handler = handler
        self._st.trigger = trigger


class I2C:
    def __init__(self, id, scl=None, sda=None, freq=400_000, timeout=50_000):
        self.id, self.freq = id, freq
        self._world = SIM.i2c[id]
        self._world.created += 1
        if self._world.created > 1:
            SIM.log("I2C", "I2C%d new bus object (reset #%d)" % (id, self._world.created - 1))

    def __repr__(self):
        return "I2C(%d, freq=%d) [sim]" % (self.id, self.freq)

    def scan(self):
        return [a for a, d in sorted(self._world.devices.items()) if not d.offline]

    def writeto(self, addr, buf, stop=True):
        return self._world.write(addr, [buf], self.freq)

    def writevto(self, addr, bufs, stop=True):
        return self._world.write(addr, list(bufs), self.freq)


class ADC:
    def __init__(self, pin):
        self.pin = pin

    def read_u16(self):
        SIM.cpu(5)
        return SIM.pot_raw


class PWM:
    def __init__(self, pin, freq=None, duty_u16=None):
        self.pin = pin
        self._duty = 0
        self._last_on = -10**9

    def freq(self, f=None):
        return 500 if f is None else None

    def duty_u16(self, d=None):
        if d is None:
            return self._duty
        if bool(d) != bool(self._duty):
            if d and SIM.now_us - self._last_on > 1_200_000:
                SIM.log("BUZZ", "beeping")
            SIM.log("BUZZ", "on" if d else "off", 2)
            if d:
                self._last_on = SIM.now_us
        self._duty = d

    def deinit(self):
        self._duty = 0


class Timer:
    ONE_SHOT, PERIODIC = 0, 1

    def __init__(self, id=-1, **kw):
        self._ev = None
        if kw:
            self.init(**kw)

    def init(self, mode=PERIODIC, period=-1, freq=-1, callback=None):
        self.deinit()
        if freq > 0:
            period = 1000 / freq
        self._mode, self._period, self._cb = mode, period, callback
        self._arm()

    def _arm(self):
        self._ev = SIM.after_us(int(self._period * 1000), self._fire, irq=True)

    def _fire(self):
        if self._mode == Timer.PERIODIC:
            self._arm()
        else:
            self._ev = None
        if self._cb:
            self._cb(self)

    def deinit(self):
        if self._ev:
            self._ev.cancelled = True
            self._ev = None


def disable_irq():
    return SIM.disable_irq()


def enable_irq(state=0):
    SIM.enable_irq(state)


def time_pulse_us(pin, level, timeout_us=1_000_000):
    # ultrasonic echo: the pulse width is the round trip time
    echo = SIM.echo_us()
    if echo is None or echo > timeout_us:
        SIM.advance_us(timeout_us)
        return -1
    SIM.advance_us(echo)
    return int(echo)


def reset():
    SIM.log("RESET", "machine.reset() called")
    raise SimReset()


def soft_reset():
    reset()


def freq(hz=None):
    return 125_000_000
