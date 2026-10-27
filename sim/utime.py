# Stub of MicroPython utime/time, every sleep advances the simulated clock
from simcore import SIM, TICKS_MAX, TICKS_HALF


def ticks_ms():
    return SIM.ticks_ms()


def ticks_us():
    return SIM.ticks_us()


def ticks_diff(a, b):
    return ((a - b + TICKS_HALF) & TICKS_MAX) - TICKS_HALF


def ticks_add(t, delta):
    return (t + delta) & TICKS_MAX


def sleep(s):
    SIM.advance_us(s * 1_000_000)


def sleep_ms(ms):
    SIM.advance_us(ms * 1000)


def sleep_us(us):
    SIM.advance_us(us)


def time():
    return SIM.now_us // 1_000_000
