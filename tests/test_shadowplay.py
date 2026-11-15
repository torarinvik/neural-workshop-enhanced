#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shadow Play: the rod, the shadows, the fit, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import shadowplay as M


class TheRod(unittest.TestCase):

    def test_rods_use_all_three_directions_at_right_angles(self):
        draw = random.Random(1)
        for bends in (3, 5, 8):
            rod = M.make_rod(bends, draw)
            self.assertEqual(len(rod), bends + 1)
            dirs = set()
            for (a, b), (c, d) in zip(rod, rod[1:]):
                u = [b[i] - a[i] for i in range(3)]
                v = [d[i] - c[i] for i in range(3)]
                self.assertAlmostEqual(sum(u[i] * v[i] for i in range(3)), 0)
            for a, b in rod:
                dirs.add(max(range(3), key=lambda i: abs(b[i] - a[i])))
            self.assertEqual(dirs, {0, 1, 2})

    def test_turns_are_rotations(self):
        m = M.mul(M.mat(0, 0.3), M.mul(M.mat(1, 1.1), M.mat(2, -0.7)))
        i = M.mul(m, M.tr(m))
        for r in range(3):
            for c in range(3):
                self.assertAlmostEqual(i[r][c], 1.0 if r == c else 0.0)

    def test_the_plan_rebuilds_the_turn(self):
        draw = random.Random(4)
        for _k in range(20):
            q = M.random_turn(draw)
            a, b, c = M.plan(q)
            back = M.mul(M.mat(1, a), M.mul(M.mat(0, b), M.mat(1, c)))
            self.assertLess(M.angle_between(back, q), 1e-6)


class TheFit(unittest.TestCase):

    def test_the_target_fits_and_the_start_does_not(self):
        for rung in (1, 4, 7, 10, 16):
            setup = M.deal(rung, seed=2)
            self.assertLess(M.misfit(setup, setup.target, 0.0), 1e-9)
            self.assertGreater(M.misfit(setup, setup.start, 0.0),
                               3 * setup.level.tol)

    def test_one_axis_rungs_turn_only_about_the_upright(self):
        run = M.Run(M.deal(1, seed=1))
        before = run.turn
        run.step(0.5, M.PITCH_U)
        run.step(0.5, M.ROLL_L)
        self.assertEqual(run.turn, before)
        run.step(0.5, M.YAW_R)
        self.assertAlmostEqual(M.angle_between(run.turn, before),
                               M.SPIN * 0.5, places=6)

    def test_holding_the_fit_passes(self):
        setup = M.deal(4, seed=3)
        run = M.Run(setup)
        run.turn = setup.target
        while run.result is None:
            run.step(1 / 60.0)
        self.assertTrue(run.result[0])
        self.assertLess(run.t, setup.level.hold + 0.2)

    def test_the_hum_rises_as_the_fit_closes(self):
        setup = M.deal(1, seed=3)
        far = M.Run(setup)
        near = M.Run(setup)
        near.turn = M.mul(M.mat(1, 0.05), setup.target)
        for run in (far, near):
            for _k in range(30):
                run.step(1 / 60.0)
        self.assertGreater(near.notes[0].freq, far.notes[0].freq)

    def test_the_reference_passes_and_idle_and_random_fail(self):
        for rung in (1, 4, 7, 10, 13, 16, 22):
            for s in range(3):
                setup = M.deal(rung, seed=s)
                self.assertTrue(M.play(setup)[0], (rung, s))
                self.assertFalse(M.play(setup, lambda run: [])[0])
                draw = random.Random(s)
                self.assertFalse(M.play(setup, lambda run: [
                    draw.randrange(M.PORTS)])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('shadow_play', 1, pilot, seed=1, steps=1500),
                         [1.0])
        self.assertEqual(drive('shadow_play', 1, lambda t: None, seed=1,
                               steps=2500), [-1.0])


if __name__ == '__main__':
    unittest.main()
