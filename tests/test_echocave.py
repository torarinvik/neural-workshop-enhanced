#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Echo Cave: the cave, the echoes, the moths, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import echocave as M


class TheEchoes(unittest.TestCase):

    def test_a_near_wall_answers_sooner_and_louder(self):
        run = M.Run(M.deal(1, seed=1))
        cx, cy = M.axis(run.cave, run.z + M.AHEAD)
        run.x = cx + M.radius(run.cave, run.z + M.AHEAD) * 0.6
        run.y = cy
        run.click()
        echoes = [n for n in run.notes if n.voice == M.P_ECHO]
        right = min(echoes, key=lambda n: -n.pan)
        left = min(echoes, key=lambda n: n.pan)
        self.assertLess(right.t, left.t)
        self.assertGreater(right.gain, left.gain)

    def test_above_is_higher_than_below(self):
        run = M.Run(M.deal(1, seed=1))
        run.click()
        echoes = [n for n in run.notes if n.voice == M.P_ECHO]
        up = max(echoes, key=lambda n: n.freq)
        down = min(echoes, key=lambda n: n.freq)
        self.assertGreater(up.freq, down.freq * 1.5)

    def test_the_long_echo_points_down_the_cave(self):
        run = M.Run(M.deal(4, seed=2))
        run.z = 60.0
        run.x, run.y = M.axis(run.cave, run.z)
        fx, _fy = M.axis(run.cave, run.z + M.FAR)
        run.click()
        far = [n for n in run.notes if n.voice == M.P_FAR][0]
        self.assertEqual(far.pan > 0, fx > run.x)

    def test_clicks_light_the_cave_only_on_the_flash_rungs(self):
        dark = M.Run(M.deal(8, seed=1))
        self.assertEqual(dark.lit(), 0.0)
        dark.click()
        self.assertGreater(dark.lit(), 0.0)
        black = M.Run(M.deal(17, seed=1))
        black.click()
        self.assertEqual(black.lit(), 0.0)


class TheFlight(unittest.TestCase):

    def test_moths_buzz_and_flying_through_one_catches_it(self):
        cave = M.deal(1, seed=3)
        run = M.Run(cave)
        mz = cave.moths[0][0]
        run.z = mz - 20
        run.step(1 / 60.0)
        self.assertTrue(any(n.voice == M.P_MOTH for n in run.notes))
        run = M.Run(cave)
        run.z = mz - 0.05
        mx, my, _z = run.moth(0, run.t + 1 / 60.0)
        run.x, run.y = mx, my
        run.step(1 / 60.0)
        self.assertTrue(run.caught[0])

    def test_the_reference_passes_and_idle_and_random_fail(self):
        for rung in (1, 4, 7, 10, 13, 16, 22):
            for s in range(3):
                cave = M.deal(rung, seed=s)
                self.assertTrue(M.play(cave)[0], (rung, s))
                self.assertFalse(M.play(cave, lambda run: [])[0])
                draw = random.Random(s)
                self.assertFalse(M.play(cave, lambda run: [
                    draw.randrange(M.PORTS)])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('echo_cave', 1, pilot, seed=1, steps=2500),
                         [1.0])
        self.assertEqual(drive('echo_cave', 1, lambda t: None, seed=1,
                               steps=2500), [-1.0])


if __name__ == '__main__':
    unittest.main()
