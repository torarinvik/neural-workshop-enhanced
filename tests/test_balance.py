#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Balance: the cart and pole, the flags, the reference, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import balance as M


class ThePole(unittest.TestCase):

    def test_left_alone_the_pole_falls(self):
        run = M.Run(M.deal(1, seed=1))
        while run.result is None:
            run.step(1 / 60.0, None)
        self.assertFalse(run.result[0])
        self.assertLess(run.t, 10.0)

    def test_pushing_the_cart_tips_the_pole_the_other_way(self):
        run = M.Run(M.deal(1, seed=1))
        run.theta = run.omega = 0.0
        for _k in range(10):
            run.step(1 / 60.0, M.RIGHT)
        self.assertLess(run.theta, 0.0)


class TheReference(unittest.TestCase):

    def test_the_reference_collects_every_flag(self):
        for rung in (1, 10, 20):
            for s in range(3):
                self.assertTrue(M.play(M.deal(rung, seed=s))[0], (rung, s))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('balance', 1, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('balance', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])


if __name__ == '__main__':
    unittest.main()
