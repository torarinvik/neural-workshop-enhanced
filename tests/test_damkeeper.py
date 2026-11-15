#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dam Keeper: the gates, the delay, the reference, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import damkeeper as M


class TheGates(unittest.TestCase):

    def test_gates_start_shut_and_move_a_notch_a_press(self):
        run = M.Run(M.deal(1, seed=1))
        self.assertEqual(run.gate, [0, 0])
        M.act(run, 0)
        M.act(run, 0)
        self.assertEqual(run.gate[0], 2)
        M.act(run, 1)
        self.assertEqual(run.gate[0], 1)
        for _k in range(10):
            M.act(run, 1)
        self.assertEqual(run.gate[0], 0)

    def test_water_let_out_arrives_downstream_later(self):
        run = M.Run(M.deal(1, seed=1))
        for _k in range(M.NOTCHES):
            M.act(run, 0)
        below = run.water[1]
        run.step(0.5)
        self.assertAlmostEqual(run.water[1], below, places=6)
        self.assertGreater(run.in_pipe(1), 0.0)
        while run.t < run.level.delay + 0.6:
            run.step(0.1)
        self.assertGreater(run.arriving[1], 0.0)

    def test_stiff_gates_take_time(self):
        run = M.Run(M.deal(13, seed=1))
        M.act(run, 0)
        self.assertEqual(run.opening[0], 0.0)
        run.step(run.level.stiff / 2)
        self.assertGreater(run.opening[0], 0.0)
        self.assertLess(run.opening[0], 1.0)


class TheReference(unittest.TestCase):

    def test_the_reference_keeps_the_town_dry_and_idling_fails(self):
        for rung in (1, 7):
            for s in range(3):
                self.assertTrue(M.play(M.deal(rung, seed=s))[0], (rung, s))
        self.assertFalse(M.play(M.deal(1, seed=1), lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('dam_keeper', 1, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('dam_keeper', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])


if __name__ == '__main__':
    unittest.main()
