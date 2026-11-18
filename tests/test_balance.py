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
        run = M.Run(M.deal(9, seed=1))
        while run.result is None:
            run.step(1 / 60.0, None)
        self.assertFalse(run.result[0])
        self.assertLess(run.t, 10.0)

    def test_pushing_the_cart_tips_the_pole_the_other_way(self):
        for port, axis, sign in ((M.RIGHT, 'theta', -1), (M.LEFT, 'theta', 1),
                                 (M.AWAY, 'phi', -1), (M.NEAR, 'phi', 1)):
            run = M.Run(M.deal(1, seed=1))
            run.theta = run.omega = run.phi = run.psi = 0.0
            for _k in range(10):
                run.step(1 / 60.0, port)
            self.assertGreater(sign * getattr(run, axis), 0.0, port)

    def test_only_the_lantern_on_the_ground_is_a_fall(self):
        run = M.Run(M.deal(1, seed=1))
        run.theta = 1.2           # far past the old 35 degrees
        run.step(1 / 60.0, None)
        self.assertIsNone(run.result)
        run.theta = run.phi = 0.0
        run.x = 0.0
        run.v = -5.0              # into the fence: it only stops the cart
        run.step(1 / 60.0, M.LEFT)
        self.assertIsNone(run.result)
        self.assertEqual(run.v, 0.0)
        run.phi = 1.6
        run.step(1 / 60.0, None)
        self.assertFalse(run.result[0])

    def test_the_bottom_rungs_are_much_gentler(self):
        one, nine = M.grade(1), M.grade(9)
        self.assertLess(one.gravity, 0.15 * nine.gravity)
        self.assertLess(one.push, 0.3 * nine.push)
        self.assertEqual((nine.gravity, nine.push), (M.G, M.PUSH))
        for r in range(1, 9):
            self.assertLess(M.grade(r).gravity, M.grade(r + 1).gravity)

        def alone(rung):
            run = M.Run(M.deal(rung, seed=1))
            while run.result is None:
                run.step(1 / 60.0, None)
            return run.t
        self.assertGreater(alone(3), 3 * alone(9))

    def test_training_wheels_at_the_bottom(self):
        """Rungs 1 and 2: the pole stands itself up, and a beginner who
        only drives at the flags gets them all; from rung 3 they must
        balance."""
        import math

        def naive(run):
            fx, fz = run.course.flags[run.flag]
            dx, dz = fx - run.x, fz - run.z
            speed = math.hypot(run.v, run.w)
            if math.hypot(dx, dz) < 0.5 and speed < 0.3:
                return []
            if math.hypot(dx, dz) < 2.0 and speed > 0.8:
                if abs(run.v) > abs(run.w):
                    return [M.LEFT if run.v > 0 else M.RIGHT]
                return [M.NEAR if run.w > 0 else M.AWAY]
            if abs(dx) > abs(dz):
                return [M.RIGHT if dx > 0 else M.LEFT]
            return [M.AWAY if dz > 0 else M.NEAR]
        for rung, passes in ((1, True), (2, True), (3, False), (5, False)):
            for s in range(3):
                course = M.deal(rung, seed=s)
                self.assertEqual(M.play(course, naive)[0], passes,
                                 (rung, s))
                run = M.Run(course)
                while run.result is None:
                    run.step(1 / 60.0, None)
                self.assertEqual(run.result[1] == M._('Out of time'),
                                 rung < 3, (rung, s))

    def test_idling_and_random_pushes_fail(self):
        import random
        for rung in (1, 10):
            for s in range(3):
                course = M.deal(rung, seed=s)
                self.assertFalse(M.play(course, lambda run: [])[0])
                draw = random.Random(s)
                self.assertFalse(M.play(course, lambda run: [
                    draw.randrange(M.PORTS)])[0])


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
