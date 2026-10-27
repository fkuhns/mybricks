# Stub of the MicroPython framebuf module. Pixels are not drawn, text calls
# are recorded so the simulated OLED can show what would be on screen.
MONO_VLSB = 0
MONO_HLSB = 3
MONO_HMSB = 4

_by_buffer = {}


def lookup(buf):
    # the FrameBuffer drawing into buf, used by the simulated OLED
    return _by_buffer.get(id(buf))


class FrameBuffer:
    def __init__(self, buffer, width, height, format, stride=None):
        self._texts = []
        _by_buffer[id(buffer)] = self

    def rows(self):
        return [t for _, _, t in sorted(self._texts, key=lambda r: (r[0], r[1]))]

    def fill(self, c):
        self._texts = []

    def text(self, s, x, y, c=1):
        self._texts = [r for r in self._texts if r[0] != y]
        self._texts.append((y, x, s))

    def fill_rect(self, x, y, w, h, c):
        if not c:
            self._texts = [r for r in self._texts if not (y <= r[0] < y + h)]

    def pixel(self, x, y, c=None): return 0
    def hline(self, *a): pass
    def vline(self, *a): pass
    def line(self, *a): pass
    def rect(self, *a, **k): pass
    def ellipse(self, *a, **k): pass
    def scroll(self, *a): pass
    def blit(self, *a): pass
