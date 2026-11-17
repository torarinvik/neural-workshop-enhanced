#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gaze: where the eyes point; the ladder, the scene, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import math
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import gaze as M

RUNGS = (1, 4, 7, 10, 13, 19, 30)
KINDS = {'rect', 'disc', 'ring', 'poly', 'line', 'text', 'hit'}


class TheLadder(unittest.TestCase):

    def test_every_rung_deals_and_the_reference_agrees(self):
        for rung in RUNGS:
            for seed in range(12):
                p = M.deal(rung, seed=seed)
                self.assertEqual(M.solve(p), p.answer, (rung, seed))
                self.assertLess(p.answer, len(p.choices))

    def test_no_one_answer_is_a_safe_bet(self):
        for rung in (RUNGS[0], RUNGS[3], RUNGS[-1]):
            seen = collections.Counter(M.deal(rung, seed=s).answer
                                       for s in range(80))
            n = len(M.deal(rung, seed=0).choices)
            self.assertLessEqual(max(seen.values()) / 80.0,
                                 0.68 if n <= 3 else max(2.6 / n, 0.45),
                                 (rung, seen))

    def test_the_same_seed_deals_the_same(self):
        self.assertEqual(repr(M.deal(RUNGS[-1], seed=7)),
                         repr(M.deal(RUNGS[-1], seed=7)))

    def test_the_rungs_get_no_easier(self):
        self.assertEqual(M.grade(0), M.grade(1))
        self.assertEqual(M.grade(300).rung, 300)


class TheTask(unittest.TestCase):

    def test_each_pupil_points_at_the_thing(self):
        for rung in RUNGS:
            p = M.deal(rung, seed=2)
            tx, ty = p.things[p.answer]
            for (ex, ey), (px, py) in zip(M.eyes(p.face), p.pupils):
                self.assertLess(math.hypot(px - ex, py - ey) + M.PUPIL_R, M.EYE_R)
                a = math.atan2(py - ey, px - ex)
                b = math.atan2(ty - ey, tx - ex)
                self.assertAlmostEqual(math.cos(a - b), 1.0)

    def test_the_things_keep_clear_of_the_face(self):
        p = M.deal(13, seed=1)
        for x, y in p.things:
            self.assertGreater(math.hypot(x - p.face[0], y - p.face[1]), M.HEAD)


class TheScene(unittest.TestCase):

    def test_it_is_made_of_plain_shapes(self):
        for rung in RUNGS:
            p = M.deal(rung, seed=1)
            for t, judged in ((0.0, False), (0.0, False), (0.0, True)):
                for prim in M.scene(p, t, judged):
                    self.assertIn(prim[0], KINDS, rung)
                    if prim[0] == 'hit':
                        self.assertLess(prim[5], len(p.choices), rung)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 10):
            self.assertEqual(drive('gaze', rung, right, seed=2,
                                   steps=600), [1.0], rung)
            self.assertEqual(drive('gaze', rung, wrong, seed=2,
                                   steps=600), [-1.0], rung)


if __name__ == '__main__':
    unittest.main()
