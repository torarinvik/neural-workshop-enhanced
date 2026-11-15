#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Air Traffic: the sky, the rules, the controller, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import airtraffic as M


class TheSky(unittest.TestCase):

    def test_the_ladder_adds_runways_storms_and_fuel(self):
        self.assertEqual(M.grade(1).runways, 1)
        self.assertEqual(M.grade(4).runways, 2)
        self.assertEqual(M.grade(4).storms, 0)
        self.assertGreater(M.grade(7).storms, 0)
        self.assertIsNone(M.grade(9).fuel)
        self.assertIsNotNone(M.grade(10).fuel)
        self.assertTrue(M.grade(13).closure)

    def test_orders_need_a_selected_plane(self):
        run = M.Run(M.deal(1, seed=1))
        while not run.planes:
            run.step(0.1)
        p = run.planes[0]
        run.order(M.HOLD)
        self.assertNotEqual(p.mode, 'hold')
        run.select(p.slot)
        run.order(M.HOLD)
        self.assertEqual(p.mode, 'hold')
        run.order(M.LAND)
        self.assertTrue(p.cleared)


class TheController(unittest.TestCase):

    def test_the_reference_lands_the_low_rungs(self):
        for rung in (1, 4):
            ok = sum(M.play(M.deal(rung, seed=s))[0] for s in range(6))
            self.assertGreaterEqual(ok, 5, rung)

    def test_doing_nothing_fails(self):
        self.assertFalse(M.play(M.deal(1, seed=2), lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('air_traffic', 1, pilot, seed=1, steps=8000),
                         [1.0])
        self.assertEqual(drive('air_traffic', 1, lambda t: None, seed=1,
                               steps=8000), [-1.0])


if __name__ == '__main__':
    unittest.main()
