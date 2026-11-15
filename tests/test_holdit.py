#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Hold It: the asks, the hold, the reference, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import holdit as M


def hold_for(ask, seconds, dt=1 / 60.0):
    run = M.Run(ask)
    while run.result is None:
        on = run.your_turn() and (run.down is None or
                                  run.t - run.down < seconds - 1e-9)
        run.step(dt, M.HOLD if on else None)
    return run


class TheAsk(unittest.TestCase):

    def test_targets(self):
        a = M.deal(1, seed=1)
        self.assertAlmostEqual(a.target, a.lamps[0][1] - a.lamps[0][0])
        b = M.deal(8, seed=1)
        shown = b.lamps[0][1] - b.lamps[0][0]
        self.assertIn(b.factor, (0.5, 2.0))
        self.assertAlmostEqual(b.target, shown * b.factor, places=3)
        c = M.deal(11, seed=1)
        self.assertEqual(len(c.lamps), 2)
        self.assertAlmostEqual(c.target, sum(y - x for x, y in c.lamps),
                               places=3)

    def test_the_turn_comes_after_the_lamps(self):
        a = M.deal(11, seed=2)
        self.assertGreater(a.turn, a.lamps[-1][1])

    def test_holding_before_the_turn_does_not_count(self):
        ask = M.deal(1, seed=1)
        run = M.Run(ask)
        for _k in range(30):
            run.step(1 / 60.0, M.HOLD)
        self.assertIsNone(run.down)


class TheHold(unittest.TestCase):

    def test_close_passes_far_fails(self):
        ask = M.deal(4, seed=3)
        m = ask.level.margin
        self.assertTrue(hold_for(ask, ask.target).result[0])
        self.assertTrue(hold_for(ask, ask.target * (1 + m * 0.8)).result[0])
        self.assertFalse(hold_for(ask, ask.target * (1 + m * 1.4)).result[0])
        self.assertFalse(hold_for(ask, ask.target * (1 - m * 1.4)).result[0])

    def test_never_holding_fails(self):
        self.assertFalse(M.play(M.deal(1, seed=1), lambda run: [])[0])

    def test_the_reference_passes_every_kind(self):
        for rung in (1, 7, 10, 13, 20):
            for s in range(4):
                self.assertTrue(M.play(M.deal(rung, seed=s))[0], (rung, s))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('hold_it', 1, pilot, seed=1, steps=1500),
                         [1.0])
        self.assertEqual(drive('hold_it', 1, lambda t: None, seed=1,
                               steps=1500), [-1.0])


if __name__ == '__main__':
    unittest.main()
