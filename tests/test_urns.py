#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Which Urn?: Bayes, the margin, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import urns as M

RUNGS = (1, 4, 7, 10, 13, 16, 25)


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


class TheOdds(unittest.TestCase):

    def test_bayes(self):
        urns = ((9, 1), (1, 9))
        self.assertGreater(M.odds(urns, (1, 1), [0], True), 2.0)
        # Three to one for the right kind beats a single left-leaning draw
        # from urns only a little apart.
        self.assertLess(M.odds(((6, 4), (4, 6)), (1, 3), [0], True), 0)

    def test_without_putting_back(self):
        self.assertEqual(M.likelihood((1, 1), [0, 0], False), 0.0)
        self.assertGreater(M.likelihood((1, 1), [0, 0], True), 0.0)

    def test_the_margin_holds(self):
        for rung in (1, 10, 25):
            for seed in range(20):
                p = M.deal(rung, seed=seed)
                self.assertGreaterEqual(abs(p.log_odds), p.level.margin)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 10):
            self.assertEqual(drive('which_urn', rung, right, seed=2,
                                   steps=600), [1.0], rung)
            self.assertEqual(drive('which_urn', rung, wrong, seed=2,
                                   steps=600), [-1.0], rung)


if __name__ == '__main__':
    unittest.main()
