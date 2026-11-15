#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Ferry: the helm, the current, the reference, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import ferry as M


class TheHelm(unittest.TestCase):

    def test_ahead_gathers_way_and_rudder_turns(self):
        run = M.Run(M.deal(1, seed=1))
        h0 = run.heading
        for _k in range(30):
            run.step(1 / 30.0, M.AHEAD)
        self.assertGreater(run.speed, 0.5)
        for _k in range(15):
            run.step(1 / 30.0, M.LEFT)
        self.assertNotAlmostEqual(run.heading, h0, places=1)

    def test_the_current_carries_a_drifting_ferry(self):
        run = M.Run(M.deal(4, seed=1))
        vx, _vy = run.ground_velocity()
        self.assertNotEqual(vx, 0.0)


class TheReference(unittest.TestCase):

    def test_the_reference_crosses_and_idling_fails(self):
        for rung in (1, 7):
            for s in range(3):
                self.assertTrue(M.play(M.deal(rung, seed=s))[0], (rung, s))
        self.assertFalse(M.play(M.deal(1, seed=1), lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('ferry', 1, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('ferry', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])


if __name__ == '__main__':
    unittest.main()
