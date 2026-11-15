#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Lander: the physics, the landing rules, the autopilot, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import lander as M


class ThePhysics(unittest.TestCase):

    def test_coasting_falls_at_gravity(self):
        f = M.deal(2, seed=1)
        c = M.Craft(f)
        vy = c.vy
        for _k in range(60):
            c.step(1 / 60.0, None)
        self.assertAlmostEqual(c.vy - vy, -f.gravity, places=6)

    def test_firing_upright_pushes_up_and_burns_fuel(self):
        f = M.deal(5, seed=1)
        c = M.Craft(f)
        for _k in range(60):
            c.step(1 / 60.0, M.THRUST)
        self.assertAlmostEqual(c.vy - f.start[3],
                               f.gravity * (f.ratio - 1), places=4)
        self.assertAlmostEqual(c.fuel, f.level.fuel - 1.0, places=6)

    def test_an_empty_tank_does_not_fire(self):
        c = M.Craft(M.deal(5, seed=1))
        c.fuel = 0.0
        c.step(0.1, M.THRUST)
        self.assertFalse(c.firing)

    def test_turning_tilts_the_push(self):
        c = M.Craft(M.deal(2, seed=1))
        for _k in range(20):
            c.step(1 / 60.0, M.LEFT)
        self.assertGreater(c.angle, 0)
        vx = c.vx
        c.step(0.1, M.THRUST)
        self.assertLess(c.vx, vx)


class TheLanding(unittest.TestCase):

    def land(self, rung, **change):
        f = M.deal(rung, seed=2)
        c = M.Craft(f)
        c.x = M.pad_centre(f, 0.0)
        c.y = f.pad_y
        c.vx, c.vy, c.angle = 0.0, -1.0, 0.0
        for name, value in change.items():
            setattr(c, name, value)
        c._check()
        return c.result

    def test_the_limits(self):
        self.assertTrue(self.land(5)[0])
        self.assertFalse(self.land(5, vy=-4.0)[0])
        self.assertFalse(self.land(5, vx=2.0)[0])
        self.assertFalse(self.land(5, angle=math.radians(20))[0])

    def test_off_the_pad_is_lost(self):
        f = M.deal(5, seed=2)
        x = M.pad_centre(f, 0) + f.level.pad
        self.assertFalse(self.land(5, x=x, y=M.ground_at(f, x))[0])

    def test_speed_across_a_moving_pad_is_measured_against_it(self):
        f = M.deal(22, seed=2)
        speed = M.pad_speed(f, 3.0)
        self.assertNotEqual(speed, 0.0)
        c = M.Craft(f)
        c.t = 3.0
        c.x = M.pad_centre(f, 3.0)
        c.y = f.pad_y
        c.vx, c.vy, c.angle = speed, -1.0, 0.0
        c._check()
        self.assertTrue(c.result[0], c.result)


class TheAutopilot(unittest.TestCase):

    def test_every_rung_can_be_landed(self):
        for rung in (1, 5, 9, 12, 15, 18, 21, 26):
            landed = sum(M.fly(M.deal(rung, seed=s), M.autopilot)[0]
                         for s in range(12))
            self.assertGreater(landed, 0, rung)
            if rung < 20:
                self.assertGreaterEqual(landed, 9, rung)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_autopilot_lands_and_coasting_crashes(self):
        for rung in (2, 11):
            self.assertEqual(drive('lander', rung,
                                   lambda t: M.autopilot(t.craft),
                                   seed=1, steps=4000), [1.0])
            self.assertEqual(drive('lander', rung, lambda t: None,
                                   seed=1, steps=4000), [-1.0])


if __name__ == '__main__':
    unittest.main()
