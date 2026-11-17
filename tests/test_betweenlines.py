#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Between the Lines: the ladder, the questions, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from feelingsupport import boundary, outcomes

from neural_workshop import betweenlines as M


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for r, seed, ref, wins in outcomes(M, (1, 4, 7, 10, 20)):
            self.assertTrue(ref, (r, seed))
            self.assertEqual(wins, [], (r, seed))

    def test_the_kinds_by_rung(self):
        self.assertEqual([M.grade(r).kinds for r in (1, 4, 7)],
                         [('implicature',), ('implicature', 'sarcasm'),
                          ('implicature', 'sarcasm', 'irony')])

    def test_less_time_to_read_higher_up(self):
        low = sum(i.seconds for i in M.deal(10, seed=1).items)
        high = sum(i.seconds for i in M.deal(24, seed=1).items)
        self.assertLess(high, low)

    def test_a_guesser_passes_one_round_in_thirty_at_most(self):
        rnd = M.deal(1, seed=3)
        from math import comb
        n = len(rnd.items)
        p = sum(comb(n, j) for j in range(rnd.need, n + 1)) / 2.0 ** n
        self.assertLessEqual(p, 0.03)
        self.assertEqual((n, rnd.need), (20, 15))


class TheBoundary(unittest.TestCase):

    def test_reference_idle_and_sound(self):
        boundary(self, 'between_the_lines', M, idle_steps=16000)


if __name__ == '__main__':
    unittest.main()
