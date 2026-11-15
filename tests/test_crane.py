#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Crane: the swinging hook, the boxes, the reference, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import crane as M


class TheTrolley(unittest.TestCase):

    def test_pushing_moves_the_trolley_and_swings_the_hook_back(self):
        run = M.Run(M.deal(1, seed=1))
        x0 = run.x
        for _k in range(30):
            run.step(1 / 60.0, M.RIGHT)
        self.assertGreater(run.x, x0)
        self.assertLess(run.theta, 0.0)       # the load lags behind

    def test_the_hoist_shortens_and_lengthens_the_cable(self):
        run = M.Run(M.deal(1, seed=1))
        c0 = run.cable
        for _k in range(30):
            run.step(1 / 60.0, M.UP)
        self.assertLess(run.cable, c0)
        for _k in range(60):
            run.step(1 / 60.0, M.DOWN)
        self.assertGreater(run.cable, c0)

    def test_grab_far_from_any_box_holds_nothing(self):
        run = M.Run(M.deal(1, seed=1))
        M.act(run, M.GRAB)
        self.assertIsNone(run.held)


class TheReference(unittest.TestCase):

    def test_the_reference_unloads_and_idling_fails(self):
        for rung in (1, 7):
            for s in range(3):
                self.assertTrue(M.play(M.deal(rung, seed=s))[0], (rung, s))
        self.assertFalse(M.play(M.deal(1, seed=1), lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('crane', 1, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('crane', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])


if __name__ == '__main__':
    unittest.main()
