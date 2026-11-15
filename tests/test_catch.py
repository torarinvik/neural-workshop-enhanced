#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Catch: the flights, the catching, the sounds, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import catch as M


class TheFlight(unittest.TestCase):

    def test_every_ball_comes_down_where_it_says(self):
        for rung in (1, 7, 10, 20):
            court = M.deal(rung, seed=3)
            for ball in court.balls:
                x, y, z = M.where(ball, ball.t0 + ball.flight,
                                  court.level.walls)
                self.assertAlmostEqual(x, ball.land[0], places=6)
                self.assertAlmostEqual(z, ball.land[1], places=6)
                self.assertAlmostEqual(y, M.RIM, places=6)

    def test_walls_turn_balls_back(self):
        self.assertAlmostEqual(M.fold(M.HALF + 2), M.HALF - 2)
        self.assertAlmostEqual(M.fold(-M.HALF - 3), -M.HALF + 3)
        court = M.deal(11, seed=1)
        bounced = [b for b in court.balls
                   if abs(b.x0 + b.v[0] * b.flight + 0.5 * b.ax *
                          b.flight ** 2) > M.HALF]
        self.assertTrue(bounced)

    def test_every_landing_is_in_reach(self):
        x0, x1, z0, z1 = M.ZONE
        for rung in (1, 13, 25):
            for ball in M.deal(rung, seed=2).balls:
                self.assertTrue(x0 <= ball.land[0] <= x1)
                self.assertTrue(z0 <= ball.land[1] <= z1)


class TheCatching(unittest.TestCase):

    def test_under_it_catches_beside_it_drops(self):
        court = M.deal(1, seed=4)
        ball = court.balls[0]
        run = M.Run(court)
        run.baskets[0] = list(ball.land)
        while run.fate[0] is None and run.result is None:
            run.step(1 / 60.0)
        self.assertTrue(run.fate[0])
        run = M.Run(court)
        run.baskets[0] = [ball.land[0] + court.level.radius * 1.2,
                          ball.land[1]]
        while run.fate[0] is None and run.result is None:
            run.step(1 / 60.0)
        self.assertFalse(run.fate[0])

    def test_a_basket_only_catches_its_own_colour(self):
        court = M.deal(14, seed=2)
        ball = court.balls[0]
        own, other = ball.colour, 1 - ball.colour
        run = M.Run(court)
        run.baskets[other] = list(ball.land)
        run.baskets[own] = [8.0 if ball.land[0] < 0 else -8.0, 15.0]
        while run.fate[0] is None and run.result is None:
            run.step(1 / 60.0)
        self.assertFalse(run.fate[0])

    def test_the_mouse_runs_the_basket_to_the_spot(self):
        run = M.Run(M.deal(1, seed=1))
        run.aim[0] = (5.0, 10.0)
        for _k in range(120):
            run.step(1 / 60.0)
        self.assertAlmostEqual(run.baskets[0][0], 5.0, places=3)
        self.assertAlmostEqual(run.baskets[0][1], 10.0, places=3)

    def test_the_reference_passes_and_idle_and_random_fail(self):
        for rung in (1, 7, 10, 13, 16, 20, 25):
            for s in range(3):
                court = M.deal(rung, seed=s)
                self.assertTrue(M.play(court)[0], (rung, s))
                self.assertFalse(M.play(court, lambda run: [])[0])
                draw = random.Random(s)
                self.assertFalse(M.play(court, lambda run: [
                    draw.randrange(M.PORTS)])[0])

    def test_every_ball_is_heard(self):
        court = M.deal(16, seed=1)
        notes = M.sounds(court)
        self.assertEqual([n.t for n in notes], sorted(n.t for n in notes))
        for ball in court.balls:
            self.assertTrue(any(abs(n.t - ball.t0) < 1e-9 for n in notes))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('catch', 1, pilot, seed=1, steps=1500),
                         [1.0])
        self.assertEqual(drive('catch', 1, lambda t: None, seed=1,
                               steps=1500), [-1.0])


if __name__ == '__main__':
    unittest.main()
