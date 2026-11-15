#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Time It: the motions, the hidden mark, the window, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import timeit as M


class TheShot(unittest.TestCase):

    def test_the_ball_is_at_the_mark_when_it_says(self):
        for rung in (1, 7, 10, 13, 16, 22):
            for s in range(8):
                shot = M.deal(rung, seed=s)
                x, _y = M.where(shot, shot.when)
                self.assertAlmostEqual(x, shot.mark, places=6)

    def test_the_ball_is_hidden_when_it_matters(self):
        for rung in (1, 7, 10, 13, 16):
            for s in range(8):
                shot = M.deal(rung, seed=s)
                x, _y = M.where(shot, shot.when)
                self.assertTrue(shot.screen[0] < x < shot.screen[1])
                hidden_for = shot.when - next(
                    t / 100 for t in range(1000)
                    if M.where(shot, t / 100)[0] >= shot.screen[0])
                self.assertGreaterEqual(hidden_for, shot.level.hidden[0] - 0.02)

    def test_a_thrown_ball_lands_on_the_mark(self):
        shot = M.deal(14, seed=1)
        self.assertEqual(shot.kind, 'throw')
        self.assertAlmostEqual(M.where(shot, shot.when)[1], M.GROUND,
                               places=6)

    def test_a_bounce_comes_back(self):
        shot = M.deal(11, seed=1)
        self.assertEqual(shot.kind, 'bounce')
        self.assertLess(shot.mark, shot.wall)

    def test_the_window(self):
        shot = M.deal(4, seed=1)
        for off, ok in ((0.0, True), (0.08, True), (-0.08, True),
                        (0.12, False), (-0.12, False)):
            run = M.Run(shot)
            run.t = shot.when + off
            run.press()
            self.assertEqual(run.result[0], ok, off)

    def test_the_reference_passes_and_waiting_fails(self):
        for rung in (1, 7, 10, 13, 16, 22):
            for s in range(4):
                shot = M.deal(rung, seed=s)
                self.assertTrue(M.play(shot)[0])
                self.assertFalse(M.play(shot, lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('time_it', 1, pilot, seed=1, steps=1200),
                         [1.0])
        self.assertEqual(drive('time_it', 1, lambda t: None, seed=1,
                               steps=1200), [-1.0])


if __name__ == '__main__':
    unittest.main()
