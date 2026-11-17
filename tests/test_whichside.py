#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Which Side?: the rule settles the side, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import whichside as M

RUNGS = (1, 4, 7, 10, 13, 16, 22)


class TheLadder(unittest.TestCase):

    def test_every_rung_deals_and_the_reference_agrees(self):
        for rung in RUNGS:
            for seed in range(8):
                p = M.deal(rung, seed=seed)
                self.assertEqual(M.solve(p), p.answer, (rung, seed))

    def test_no_one_answer_is_a_safe_bet(self):
        for rung in (RUNGS[0], RUNGS[len(RUNGS) // 2], RUNGS[-1]):
            seen = collections.Counter(M.deal(rung, seed=s).answer
                                       for s in range(80))
            n = len(M.deal(rung, seed=0).choices)
            self.assertLessEqual(max(seen.values()) / 80.0,
                                 0.68 if n <= 2 else 2.2 / n, (rung, seen))

    def test_the_same_seed_deals_the_same(self):
        self.assertEqual(repr(M.deal(RUNGS[-1], seed=7)),
                         repr(M.deal(RUNGS[-1], seed=7)))


class TheRule(unittest.TestCase):

    def test_the_examples_follow_the_dealt_rule(self):
        for rung in (1, 7, 13):
            for seed in range(10):
                p = M.deal(rung, seed=seed)
                for panel in p.left:
                    self.assertTrue(M.F.holds(p.rule, M.F.features(
                        p.look, panel)))
                for panel in p.right:
                    self.assertFalse(M.F.holds(p.rule, M.F.features(
                        p.look, panel)))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 10):
            self.assertEqual(drive('which_side', rung, right, seed=2,
                                   steps=600), [1.0], rung)
            self.assertEqual(drive('which_side', rung, wrong, seed=2,
                                   steps=600), [-1.0], rung)


if __name__ == '__main__':
    unittest.main()
