#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Walker: the figure of lights; the ladder, the scene, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import walker as M

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

    def test_turning_the_walker_round_turns_the_answer(self):
        for seed in range(10):
            p = M.deal(8, seed=seed)
            self.assertNotEqual(M.solve(p._replace(facing=-p.facing)), M.solve(p))

    def test_the_strays_face_both_ways_alike(self):
        p = M.deal(13, seed=1)
        self.assertEqual(sum(s.facing for s in p.strays), 0)
        self.assertEqual(len(M.joints(0.0, 1)), 11)


class TheScene(unittest.TestCase):

    def test_it_is_made_of_plain_shapes(self):
        for rung in RUNGS:
            p = M.deal(rung, seed=1)
            for t, judged in ((0.0, False), (1.0, False), (0.0, True)):
                for prim in M.scene(p, t, judged):
                    self.assertIn(prim[0], KINDS, rung)
                    if prim[0] == 'hit':
                        self.assertLess(prim[5], len(p.choices), rung)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 10):
            self.assertEqual(drive('walker', rung, right, seed=2,
                                   steps=1500), [1.0], rung)
            self.assertEqual(drive('walker', rung, wrong, seed=2,
                                   steps=1500), [-1.0], rung)


if __name__ == '__main__':
    unittest.main()
