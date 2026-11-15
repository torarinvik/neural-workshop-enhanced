#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Glider: lift and sink, the walls, the reference, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import glider as M


class TheFlight(unittest.TestCase):

    def test_holding_climbs_letting_go_sinks(self):
        run = M.Run(M.deal(1, seed=1))
        y0 = run.y
        for _k in range(20):
            run.step(1 / 60.0, M.UP)
        self.assertGreater(run.y, y0)
        y1 = run.y
        for _k in range(40):
            run.step(1 / 60.0, None)
        self.assertLess(run.y, y1)

    def test_idling_hits_the_floor(self):
        result = M.play(M.deal(1, seed=1), lambda run: [])
        self.assertFalse(result[0])

    def test_gaps_slide_from_rung_10(self):
        run = M.Run(M.deal(10, seed=1))
        self.assertNotEqual(run.wall(0, 0.0)[1], run.wall(0, 1.0)[1])

    def test_the_reference_flies_through_and_a_coin_does_not(self):
        for rung in (1, 7, 10, 13, 16, 22):
            for s in range(3):
                course = M.deal(rung, seed=s)
                self.assertTrue(M.play(course)[0], (rung, s))
                draw = random.Random(s)
                self.assertFalse(M.play(course, lambda run: [M.UP]
                                        if draw.random() < 0.5 else [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('glider', 1, pilot, seed=1, steps=3000),
                         [1.0])
        self.assertEqual(drive('glider', 1, lambda t: None, seed=1,
                               steps=3000), [-1.0])


if __name__ == '__main__':
    unittest.main()
