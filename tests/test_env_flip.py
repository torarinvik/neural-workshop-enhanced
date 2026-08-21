#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Turning a bottom-up readback top-down.

:func:`nwenv.frames.flip_rgba` had no test of its own and sits under
every frame the agent environment captures, so it gained one when it
gained a faster path. The point of these is not the speed — it is that
the fast path and the old one agree, byte for byte, including on the
ragged inputs that send it down the old one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from nwenv.frames import flip_rgba


def rows(raw, width):
    """*raw* cut back into its rows, for saying what went where."""
    row = width * 4
    return [raw[at:at + row] for at in range(0, len(raw), row)]


def frame(width, height):
    """A frame whose every row is plainly distinguishable from the rest."""
    return b''.join(bytes([y % 256]) * (width * 4) for y in range(height))


class FlipTests(unittest.TestCase):
    """The rows come back in the other order and nothing else moves."""

    def test_the_rows_come_back_reversed(self):
        flipped = flip_rgba(frame(3, 4), 3, 4)
        self.assertEqual(rows(flipped, 3), list(reversed(rows(frame(3, 4), 3))))

    def test_a_row_is_not_itself_reversed(self):
        """Only the order of rows changes — the pixels within one do not."""
        raw = bytes(range(8)) + bytes(range(8, 16))
        self.assertEqual(flip_rgba(raw, 2, 2), bytes(range(8, 16))
                         + bytes(range(8)))

    def test_flipping_twice_is_doing_nothing(self):
        raw = frame(7, 5)
        self.assertEqual(flip_rgba(flip_rgba(raw, 7, 5), 7, 5), raw)

    def test_one_row_is_left_alone(self):
        raw = frame(4, 1)
        self.assertEqual(flip_rgba(raw, 4, 1), raw)

    def test_nothing_at_all_is_handled(self):
        self.assertEqual(flip_rgba(b'', 0, 0), b'')
        self.assertEqual(flip_rgba(b'', 4, 0), b'')
        self.assertEqual(flip_rgba(b'abc', 0, 3), b'abc')

    def test_the_length_is_kept(self):
        for width, height in ((1, 1), (3, 4), (16, 9), (64, 64)):
            raw = frame(width, height)
            self.assertEqual(len(flip_rgba(raw, width, height)), len(raw))

    def test_the_fast_path_and_the_old_one_agree(self):
        """The whole reason the fast path is allowed to exist.

        The join only runs when the buffer is exactly the size the
        geometry implies; this walks the same frames through the older
        bytearray form written out longhand and requires the same
        bytes back.
        """
        for width, height in ((1, 1), (2, 3), (5, 5), (17, 11), (64, 48)):
            raw = frame(width, height)
            row = width * 4
            out = bytearray(len(raw))
            for y in range(height):
                src = (height - 1 - y) * row
                out[y * row:y * row + row] = raw[src:src + row]
            self.assertEqual(flip_rgba(raw, width, height), bytes(out),
                             '%dx%d' % (width, height))

    def test_a_ragged_buffer_keeps_the_older_behaviour(self):
        """Short readbacks go down the slow path and are unchanged by this."""
        raw = frame(4, 3)[:-5]
        row = 16
        out = bytearray(len(raw))
        for y in range(3):
            src = (3 - 1 - y) * row
            out[y * row:y * row + row] = raw[src:src + row]
        self.assertEqual(flip_rgba(raw, 4, 3), bytes(out))


if __name__ == '__main__':
    unittest.main()
