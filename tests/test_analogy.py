#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analogies: the change, the deal, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import random
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import analogy as M

RUNGS = (1, 4, 7, 10, 13, 16, 25, 40)


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


class TheChange(unittest.TestCase):

    def test_steps_and_becomes(self):
        lk = M.G.look(random.Random(1), oriented=True)
        a = M.G.Glyph(0, 0, 0, 1, 0, 0, -1)
        b = a._replace(size=1, colour=2)
        change = M.infer(lk, a, b)
        self.assertEqual(change, {'colour': ('becomes', 2),
                                  'size': ('steps', 1)})
        c = M.G.Glyph(1, 1, 1, 2, 3, 1, -1)
        self.assertEqual(M.apply(change, c), c._replace(size=2, colour=2))

    def test_a_step_off_the_end_is_refused(self):
        g = M.G.Glyph(0, 0, 2, 1, 0, 0, -1)
        self.assertIsNone(M.apply({'size': ('steps', 1)}, g))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 10):
            self.assertEqual(drive('analogies', rung, right, seed=2,
                                   steps=600), [1.0], rung)
            self.assertEqual(drive('analogies', rung, wrong, seed=2,
                                   steps=600), [-1.0], rung)


if __name__ == '__main__':
    unittest.main()
