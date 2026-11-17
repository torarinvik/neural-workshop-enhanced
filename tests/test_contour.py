#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Contour: the chain in the field; the ladder, the scene, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import contour as M

RUNGS = (1, 4, 7, 10, 13, 19, 30)
KINDS = {'rect', 'disc', 'ring', 'poly', 'line', 'text', 'hit'}


class TheLadder(unittest.TestCase):

    def test_every_rung_deals_and_the_reference_agrees(self):
        for rung in RUNGS:
            for seed in range(6):
                p = M.deal(rung, seed=seed)
                self.assertEqual(M.solve(p), p.answer, (rung, seed))
                self.assertLess(p.answer, len(p.choices))

    def test_no_one_answer_is_a_safe_bet(self):
        for rung in (RUNGS[0], RUNGS[3], RUNGS[-1]):
            seen = collections.Counter(M.deal(rung, seed=s).answer
                                       for s in range(60))
            n = len(M.deal(rung, seed=0).choices)
            self.assertLessEqual(max(seen.values()) / 60.0,
                                 0.68 if n <= 3 else max(2.6 / n, 0.45),
                                 (rung, seen))

    def test_the_same_seed_deals_the_same(self):
        self.assertEqual(repr(M.deal(RUNGS[-1], seed=7)),
                         repr(M.deal(RUNGS[-1], seed=7)))

    def test_the_rungs_get_no_easier(self):
        self.assertEqual(M.grade(0), M.grade(1))
        self.assertEqual(M.grade(300).rung, 300)


class TheTask(unittest.TestCase):

    def test_the_path_lies_in_the_answer_s_part(self):
        for rung in RUNGS:
            for seed in range(5):
                p = M.deal(rung, seed=seed)
                for k in p.path:
                    s = p.strokes[k]
                    self.assertEqual(M.region(p.level, s.x, s.y), p.answer)

    def test_the_reference_finds_the_path_itself(self):
        p = M.deal(7, seed=2)
        run = M.chain(p.strokes)
        self.assertGreaterEqual(len(set(run) & set(p.path)), len(p.path) - 1)


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
            self.assertEqual(drive('contour', rung, right, seed=2,
                                   steps=600), [1.0], rung)
            self.assertEqual(drive('contour', rung, wrong, seed=2,
                                   steps=600), [-1.0], rung)


if __name__ == '__main__':
    unittest.main()
