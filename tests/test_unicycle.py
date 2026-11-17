#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Unicycle: the reference, the shortcuts, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import unicycle as M


def fixed(port):
    """A player that sends one port every step."""
    return lambda run: [port]


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for rung in (1, 2, 4, 7, 10, 13, 20):
            for s in range(2):
                dealt = M.deal(rung, seed=s)
                self.assertTrue(M.play(dealt)[0], (rung, s))
                self.assertFalse(M.play(dealt, lambda run: [])[0],
                                 ('idle', rung, s))
                draw = random.Random(s)
                self.assertFalse(M.play(dealt, lambda run: [
                    draw.randrange(M.PORTS)])[0], ('random', rung, s))
                for port in range(M.PORTS):
                    self.assertFalse(M.play(dealt, fixed(port))[0],
                                     ('fixed', port, rung, s))

    def test_the_grade_grows_without_end(self):
        self.assertEqual(M.grade(500).rung, 500)
        self.assertEqual(M.grade(0), M.grade(1))

    def test_letting_go_falls_over(self):
        run = M.Run(M.deal(1, seed=1))
        while run.result is None:
            run.step(1 / 30.0, None)
        self.assertFalse(run.result[0])
        self.assertLess(run.t, 30.0)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('unicycle', 1, pilot, seed=1, steps=24000),
                         [1.0])
        self.assertEqual(drive('unicycle', 1, lambda t: None, seed=1,
                               steps=24000), [-1.0])


if __name__ == '__main__':
    unittest.main()
