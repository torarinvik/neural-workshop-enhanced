#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""More or Less: the counts, the ink, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import moreorless as M

RUNGS = (1, 4, 7, 10, 13, 25)


class TheLadder(unittest.TestCase):

    def test_every_rung_deals(self):
        for rung in RUNGS:
            for seed in range(8):
                p = M.deal(rung, seed=seed)
                self.assertLess(p.answer, len(p.choices))
                self.assertLess(p.open_at, p.limit)

    def test_no_one_answer_is_a_safe_bet(self):
        for rung in (RUNGS[0], RUNGS[len(RUNGS) // 2], RUNGS[-1]):
            seen = collections.Counter(M.deal(rung, seed=s).answer
                                       for s in range(80))
            n = len(M.deal(rung, seed=0).choices)
            self.assertLessEqual(max(seen.values()) / 80.0,
                                 0.68 if n <= 3 else 2.6 / n, (rung, seen))


class TheDots(unittest.TestCase):

    def test_the_counts_are_what_the_answer_says(self):
        for rung in (1, 10, 25):
            for seed in range(30):
                p = M.deal(rung, seed=seed)
                if p.kind == 'flash':
                    n = [sum(1 for d in p.dots if d.side == s) for s in (0, 1)]
                    self.assertEqual(n.index(max(n)), p.answer)
                    self.assertGreaterEqual(max(n) / min(n),
                                            p.level.ratio * 0.9)
                elif p.answer == M.SAME:
                    self.assertEqual(p.rows[0], p.rows[1])

    def test_the_more_numerous_have_less_ink(self):
        p = next(q for q in (M.deal(4, seed=s) for s in range(50))
                 if q.kind == 'flash')
        ink = [sum(d.r ** 2 for d in p.dots if d.side == s) for s in (0, 1)]
        self.assertLessEqual(ink[p.answer], ink[1 - p.answer] * 1.3)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 10):
            self.assertEqual(drive('more_or_less', rung, right, seed=2,
                                   steps=1200), [1.0], rung)
            self.assertEqual(drive('more_or_less', rung, wrong, seed=2,
                                   steps=1200), [-1.0], rung)


if __name__ == '__main__':
    unittest.main()
