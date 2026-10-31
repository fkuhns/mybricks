# Tests for common.RingBuffer. Run from anywhere:  python3 tests/ringbuff_tests.py
# Uses the sim/ stubs for machine/utime so common.py imports on plain CPython.
import builtins
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "sim"), os.path.join(ROOT, "common")]
import micropython
builtins.const = micropython.const
from common import RingBuffer, RING_DEF_SIZE


class RingBufferBase(unittest.TestCase):
    def fill(self, rb, n, start=1):
        for k in range(n):
            self.assertTrue(rb.put(start + k))


class TestInit(RingBufferBase):
    def test_defaults(self):
        rb = RingBuffer()
        self.assertEqual(rb.width, 1)
        self.assertEqual(rb.slots, RING_DEF_SIZE + 1)
        self.assertEqual(len(rb.buf), RING_DEF_SIZE + 1)
        self.assertEqual((rb.head, rb.tail), (0, 0))
        self.assertTrue(rb.is_empty())

    def test_int_init_fills_buffer(self):
        rb = RingBuffer(4, 7)
        self.assertEqual(list(rb.buf), [7] * 5)

    def test_tuple_init_sets_width(self):
        rb = RingBuffer(4, (1, 2, 3))
        self.assertEqual(rb.width, 3)
        self.assertEqual(len(rb.buf), 5 * 3)
        self.assertEqual(list(rb.buf), [1, 2, 3] * 5)

    def test_capacity_is_size(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        self.assertTrue(rb.is_full())
        self.assertEqual(len(rb), 3)


class TestPut(RingBufferBase):
    def test_put_returns_true_and_stores(self):
        rb = RingBuffer(3)
        self.assertTrue(rb.put(5))
        self.assertEqual(len(rb), 1)
        self.assertEqual(rb.head, 1)

    def test_put_full_returns_false_without_overwrite(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        self.assertFalse(rb.put(99))
        self.assertEqual([rb.get() for _ in range(3)], [1, 2, 3])

    def test_put_tuple(self):
        rb = RingBuffer(3, (0, 0))
        self.assertTrue(rb.put((4, 5)))
        self.assertEqual(rb.get(), (4, 5))

    def test_put_tuple_full(self):
        rb = RingBuffer(2, (0, 0))
        rb.put((1, 1)); rb.put((2, 2))
        self.assertFalse(rb.put((3, 3)))
        self.assertEqual(rb.get(), (1, 1))

    def test_put_wraps_head(self):
        rb = RingBuffer(3)
        for _ in range(3):
            self.fill(rb, 3)
            for _ in range(3):
                rb.get()
        self.assertTrue(0 <= rb.head < rb.slots)
        self.assertTrue(rb.is_empty())

    def test_put_negative_values(self):
        rb = RingBuffer(2)
        rb.put(-5)
        self.assertEqual(rb.get(), -5)


class TestGet(RingBufferBase):
    def test_get_empty_returns_none(self):
        self.assertIsNone(RingBuffer(3).get())

    def test_get_is_fifo(self):
        rb = RingBuffer(5)
        self.fill(rb, 5)
        self.assertEqual([rb.get() for _ in range(5)], [1, 2, 3, 4, 5])
        self.assertIsNone(rb.get())

    def test_get_tuple(self):
        rb = RingBuffer(3, (0, 0, 0))
        rb.put((1, 2, 3)); rb.put((4, 5, 6))
        self.assertEqual(rb.get(), (1, 2, 3))
        self.assertEqual(rb.get(), (4, 5, 6))

    def test_get_removes_item(self):
        rb = RingBuffer(3)
        rb.put(1)
        rb.get()
        self.assertEqual(len(rb), 0)

    def test_get_wraps_tail_and_preserves_order(self):
        rb = RingBuffer(3)
        n = 1
        for _ in range(10):
            rb.put(n); rb.put(n + 1)
            self.assertEqual(rb.get(), n)
            self.assertEqual(rb.get(), n + 1)
            n += 2
        self.assertTrue(0 <= rb.tail < rb.slots)

    def test_get_after_full_frees_space(self):
        rb = RingBuffer(2)
        self.fill(rb, 2)
        rb.get()
        self.assertTrue(rb.put(3))
        self.assertEqual([rb.get(), rb.get()], [2, 3])


class TestPeek(RingBufferBase):
    def test_peek_empty_returns_none(self):
        self.assertIsNone(RingBuffer(3).peek())

    def test_peek_does_not_consume(self):
        rb = RingBuffer(3)
        self.fill(rb, 2)
        self.assertEqual(rb.peek(), 1)
        self.assertEqual(rb.peek(), 1)
        self.assertEqual(len(rb), 2)

    def test_peek_matches_next_get(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        self.assertEqual(rb.peek(), rb.get())
        self.assertEqual(rb.peek(), rb.get())

    def test_peek_tuple(self):
        rb = RingBuffer(3, (0, 0))
        rb.put((8, 9))
        self.assertEqual(rb.peek(), (8, 9))
        self.assertEqual(len(rb), 1)

    def test_peek_after_wrap(self):
        rb = RingBuffer(2)
        for v in range(1, 6):
            rb.put(v)
            self.assertEqual(rb.peek(), v)
            rb.get()


class TestAdvanceTail(RingBufferBase):
    def test_advance_empty_is_noop(self):
        rb = RingBuffer(3)
        rb.advance_tail()
        self.assertEqual((rb.head, rb.tail), (0, 0))
        self.assertTrue(rb.is_empty())

    def test_advance_drops_head_item(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        rb.advance_tail()
        self.assertEqual(len(rb), 2)
        self.assertEqual(rb.peek(), 2)

    def test_peek_advance_equals_get(self):
        a, b = RingBuffer(4), RingBuffer(4)
        self.fill(a, 4); self.fill(b, 4)
        seen = []
        for _ in range(4):
            seen.append(a.peek())
            a.advance_tail()
        self.assertEqual(seen, [b.get() for _ in range(4)])
        self.assertTrue(a.is_empty())

    def test_advance_wraps_tail(self):
        rb = RingBuffer(2)
        for v in range(10):
            rb.put(v)
            rb.advance_tail()
            self.assertTrue(0 <= rb.tail < rb.slots)
        self.assertTrue(rb.is_empty())

    def test_advance_tuple(self):
        rb = RingBuffer(3, (0, 0))
        rb.put((1, 2)); rb.put((3, 4))
        rb.advance_tail()
        self.assertEqual(rb.get(), (3, 4))


class TestUpdateTail(RingBufferBase):
    def test_update_empty_is_noop(self):
        rb = RingBuffer(3)
        rb.update_tail(5)
        self.assertTrue(rb.is_empty())
        self.assertIsNone(rb.get())

    def test_update_replaces_tail_item_only(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        rb.update_tail(42)
        self.assertEqual([rb.get() for _ in range(3)], [42, 2, 3])

    def test_update_does_not_change_length(self):
        rb = RingBuffer(3)
        self.fill(rb, 2)
        rb.update_tail(9)
        self.assertEqual(len(rb), 2)

    def test_update_tuple(self):
        rb = RingBuffer(3, (0, 0, 0))
        rb.put((1, 2, 3)); rb.put((4, 5, 6))
        rb.update_tail((7, 8, 9))
        self.assertEqual(rb.peek(), (7, 8, 9))
        rb.advance_tail()
        self.assertEqual(rb.peek(), (4, 5, 6))

    def test_update_after_wrap(self):
        rb = RingBuffer(2, (0, 0))
        for k in range(5):
            rb.put((k, k))
            rb.get()
        rb.put((1, 2)); rb.put((3, 4))
        rb.update_tail((9, 9))
        self.assertEqual(rb.get(), (9, 9))
        self.assertEqual(rb.get(), (3, 4))

    def test_update_scalar_after_wrap(self):
        rb = RingBuffer(2)
        for k in range(5):
            rb.put(k); rb.get()
        rb.put(1); rb.put(2)
        rb.update_tail(9)
        self.assertEqual([rb.get(), rb.get()], [9, 2])


class TestClear(RingBufferBase):
    def test_clear_empties(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        rb.clear()
        self.assertTrue(rb.is_empty())
        self.assertEqual(len(rb), 0)
        self.assertIsNone(rb.get())

    def test_clear_empty_is_noop(self):
        rb = RingBuffer(3)
        rb.clear()
        self.assertTrue(rb.is_empty())

    def test_usable_after_clear(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        rb.clear()
        self.fill(rb, 3, start=10)
        self.assertEqual([rb.get() for _ in range(3)], [10, 11, 12])


class TestIsEmpty(RingBufferBase):
    def test_new_is_empty(self):
        self.assertTrue(RingBuffer(3).is_empty())

    def test_not_empty_after_put(self):
        rb = RingBuffer(3)
        rb.put(1)
        self.assertFalse(rb.is_empty())

    def test_empty_after_drain(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        for _ in range(3):
            rb.get()
        self.assertTrue(rb.is_empty())

    def test_full_is_not_empty(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        self.assertFalse(rb.is_empty())


class TestIsFull(RingBufferBase):
    def test_new_is_not_full(self):
        self.assertFalse(RingBuffer(3).is_full())

    def test_full_at_capacity(self):
        rb = RingBuffer(3)
        self.fill(rb, 2)
        self.assertFalse(rb.is_full())
        self.fill(rb, 1)
        self.assertTrue(rb.is_full())

    def test_not_full_after_get(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        rb.get()
        self.assertFalse(rb.is_full())

    def test_full_when_wrapped(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        rb.get(); rb.get()
        self.fill(rb, 2, start=10)
        self.assertTrue(rb.is_full())
        self.assertGreater(rb.tail, rb.head)

    def test_size_one(self):
        rb = RingBuffer(1)
        self.assertFalse(rb.is_full())
        rb.put(1)
        self.assertTrue(rb.is_full())


class TestLen(RingBufferBase):
    def test_len_tracks_puts_and_gets(self):
        rb = RingBuffer(4)
        self.assertEqual(len(rb), 0)
        for n in range(1, 5):
            rb.put(n)
            self.assertEqual(len(rb), n)
        for n in range(3, -1, -1):
            rb.get()
            self.assertEqual(len(rb), n)

    def test_len_when_wrapped(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        rb.get(); rb.get()
        rb.put(4); rb.put(5)
        self.assertLess(rb.head, rb.tail)
        self.assertEqual(len(rb), 3)

    def test_len_unchanged_by_failed_put(self):
        rb = RingBuffer(2)
        self.fill(rb, 2)
        rb.put(3)
        self.assertEqual(len(rb), 2)


class TestFree(RingBufferBase):
    def test_free_new_is_size(self):
        self.assertEqual(RingBuffer(5).free(), 5)

    def test_free_decreases_with_put(self):
        rb = RingBuffer(5)
        for n in range(5):
            self.assertEqual(rb.free(), 5 - n)
            rb.put(n)
        self.assertEqual(rb.free(), 0)

    def test_free_plus_len_is_size(self):
        rb = RingBuffer(4)
        for k in range(12):
            rb.put(k)
            if k % 3 == 0:
                rb.get()
            self.assertEqual(rb.free() + len(rb), 4)

    def test_free_after_clear(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        rb.clear()
        self.assertEqual(rb.free(), 3)


class TestUnput(RingBufferBase):
    def test_unput_empty_returns_false(self):
        rb = RingBuffer(3)
        self.assertFalse(rb.unput())
        self.assertEqual((rb.head, rb.tail), (0, 0))
        self.assertTrue(rb.is_empty())

    def test_unput_removes_newest_item(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        self.assertTrue(rb.unput())
        self.assertEqual(len(rb), 2)
        self.assertEqual([rb.get(), rb.get()], [1, 2])
        self.assertIsNone(rb.get())

    def test_unput_undoes_put(self):
        rb = RingBuffer(3)
        self.fill(rb, 2)
        rb.put(99)
        rb.unput()
        self.assertEqual(len(rb), 2)
        self.assertEqual(rb.peek(), 1)

    def test_unput_leaves_oldest_item_alone(self):
        rb = RingBuffer(3)
        rb.put(7)
        self.assertTrue(rb.unput())
        self.assertTrue(rb.is_empty())
        self.assertFalse(rb.unput())

    def test_unput_all_items(self):
        rb = RingBuffer(4)
        self.fill(rb, 4)
        for n in range(4):
            self.assertTrue(rb.unput())
        self.assertTrue(rb.is_empty())
        self.assertFalse(rb.unput())

    def test_unput_from_full_makes_room(self):
        rb = RingBuffer(2)
        self.fill(rb, 2)
        self.assertTrue(rb.is_full())
        rb.unput()
        self.assertFalse(rb.is_full())
        self.assertEqual(rb.free(), 1)
        self.assertTrue(rb.put(9))
        self.assertEqual([rb.get(), rb.get()], [1, 9])

    def test_unput_wraps_head_backwards(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        rb.get(); rb.get(); rb.get() # head == tail == 3
        rb.put(10); rb.put(11)       # head wraps to 1
        self.assertEqual(rb.head, 1)
        rb.unput()                   # head back to 0
        rb.unput()                   # head back to 3 (slots - 1)
        self.assertEqual(rb.head, rb.slots - 1)
        self.assertTrue(rb.is_empty())

    def test_unput_at_head_zero(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        rb.get(); rb.get(); rb.get()
        rb.put(5); rb.put(6); rb.put(7) # head wraps to 2
        rb.get()
        rb.put(8)                       # head wraps to 3 -> 0 cases
        for _ in range(4):
            if rb.head == 0:
                break
            rb.get(); rb.put(0)
        self.assertEqual(rb.head, 0)
        self.assertTrue(rb.unput())
        self.assertEqual(rb.head, rb.slots - 1)
        self.assertEqual(len(rb), 2)

    def test_unput_tuple(self):
        rb = RingBuffer(3, (0, 0))
        rb.put((1, 2)); rb.put((3, 4))
        self.assertTrue(rb.unput())
        self.assertEqual(rb.get(), (1, 2))
        self.assertIsNone(rb.get())

    def test_put_after_unput_overwrites_removed_slot(self):
        rb = RingBuffer(3, (0, 0))
        rb.put((1, 2)); rb.put((3, 4))
        rb.unput()
        rb.put((5, 6))
        self.assertEqual([rb.get(), rb.get()], [(1, 2), (5, 6)])

    def test_unput_does_not_move_tail(self):
        rb = RingBuffer(3)
        self.fill(rb, 3)
        rb.get()
        tail = rb.tail
        rb.unput()
        self.assertEqual(rb.tail, tail)


class TestModel(RingBufferBase):
    """Randomized comparison against a plain list used as a FIFO."""
    def run_model(self, width):
        import random
        rnd = random.Random(1234 + width)
        init = 0 if width == 1 else (0,) * width
        rb = RingBuffer(5, init)
        ref = []
        for _ in range(2000):
            op = rnd.random()
            if op < 0.45:
                item = rnd.randint(-1000, 1000) if width == 1 else tuple(rnd.randint(-1000, 1000) for _ in range(width))
                ok = rb.put(item)
                self.assertEqual(ok, len(ref) < 5)
                if ok:
                    ref.append(item)
            elif op < 0.85:
                self.assertEqual(rb.get(), ref.pop(0) if ref else None)
            elif op < 0.93:
                self.assertEqual(rb.peek(), ref[0] if ref else None)
            elif op < 0.95:
                rb.advance_tail()
                if ref:
                    ref.pop(0)
            elif op < 0.97:
                self.assertEqual(rb.unput(), bool(ref))
                if ref:
                    ref.pop()
            else:
                rb.clear()
                ref.clear()
            self.assertEqual(len(rb), len(ref))
            self.assertEqual(rb.is_empty(), not ref)
            self.assertEqual(rb.is_full(), len(ref) == 5)
            self.assertEqual(rb.free(), 5 - len(ref))

    def test_model_scalar(self):
        self.run_model(1)

    def test_model_tuple(self):
        self.run_model(3)


if __name__ == "__main__":
    unittest.main()
