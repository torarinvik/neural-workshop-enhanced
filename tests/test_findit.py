#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Find It: present or not, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import findit as M

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


class TheSearch(unittest.TestCase):

    def test_present_means_present(self):
        for rung in (1, 10, 25):
            for seed in range(20):
                p = M.deal(rung, seed=seed)
                self.assertEqual(M.solve(p), p.answer)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 10):
            self.assertEqual(drive('find_it', rung, right, seed=2,
                                   steps=1200), [1.0], rung)
            self.assertEqual(drive('find_it', rung, wrong, seed=2,
                                   steps=1200), [-1.0], rung)


if __name__ == '__main__':
    unittest.main()
