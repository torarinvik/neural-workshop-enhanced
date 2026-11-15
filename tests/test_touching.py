#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Touching?: the gap measure, the pairs, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import touching as M


def circle(x, y, r):
    return M.Shape('circle', x, y, r, 0.0, False)


class TheGap(unittest.TestCase):

    def test_circles(self):
        self.assertAlmostEqual(M.gap(circle(0, 0, 5), circle(12, 0, 5)), 2.0)
        self.assertAlmostEqual(M.gap(circle(0, 0, 5), circle(10, 0, 5)), 0.0)
        self.assertLess(M.gap(circle(0, 0, 5), circle(8, 0, 5)), 0)

    def test_a_square_turned_into_a_star_overlaps(self):
        a = M.Shape('square', 50, 30, 10, 0.0, False)
        self.assertLess(M.gap(a, a._replace(turn=0.785)), 0)

    def test_circle_and_square(self):
        sq = M.Shape('square', 0, 0, 5, 0.0, False)
        self.assertAlmostEqual(M.gap(sq, circle(10, 0, 5)), 0.0)
        self.assertAlmostEqual(M.gap(sq, circle(12, 0, 5)), 2.0)


class TheDeal(unittest.TestCase):

    def test_pairs_are_what_they_say_and_clear_of_the_margin(self):
        for rung in (1, 4, 7):
            for seed in range(15):
                p = M.deal(rung, seed=seed)
                g = M.gap(*p.shapes)
                if p.answer == M.TOUCHING:
                    self.assertLess(abs(g), 1e-3)
                elif p.answer == M.APART:
                    self.assertGreaterEqual(g, p.level.margin * 0.99)
                else:
                    self.assertLessEqual(g, -p.level.margin * 0.99)

    def test_counts_are_the_touching_pairs(self):
        for rung in (10, 16, 22):
            for seed in range(8):
                p = M.deal(rung, seed=seed)
                n = sum(1 for i in range(len(p.shapes)) for j in range(i)
                        if abs(M.gap(p.shapes[i], p.shapes[j])) < 1e-3)
                self.assertEqual(n, p.answer)

    def test_every_answer_comes_up(self):
        self.assertEqual({M.deal(1, seed=s).answer for s in range(30)},
                         {0, 1, 2})


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        self.assertEqual(drive('touching', 4, lambda t: t.puzzle.answer,
                               seed=1), [1.0])
        self.assertEqual(drive('touching', 4,
                               lambda t: (t.puzzle.answer + 1) % 3, seed=1),
                         [-1.0])


if __name__ == '__main__':
    unittest.main()
