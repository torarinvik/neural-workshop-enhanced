#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Juggler: the tray, the tosses, the reference, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import juggler as M


class TheTray(unittest.TestCase):

    def test_pushing_moves_the_tray_and_it_brakes_when_let_go(self):
        run = M.Run(M.deal(1, seed=1))
        for _k in range(10):
            run.step(1 / 60.0, M.RIGHT)
        self.assertGreater(run.v, 0.0)
        for _k in range(60):
            run.step(1 / 60.0, None)
        self.assertEqual(run.v, 0.0)

    def test_every_toss_flies_the_same_time(self):
        run = M.Run(M.deal(10, seed=2))
        for b in run.balls:
            self.assertAlmostEqual(2 * run.toss_speed(b) / b.g, M.FLIGHT,
                                   places=6)


class TheReference(unittest.TestCase):

    def test_the_reference_juggles_and_idling_drops(self):
        for rung in (1, 4):
            for s in range(3):
                self.assertTrue(M.play(M.deal(rung, seed=s))[0], (rung, s))
        self.assertFalse(M.play(M.deal(1, seed=1), lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('juggler', 1, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('juggler', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])


if __name__ == '__main__':
    unittest.main()
