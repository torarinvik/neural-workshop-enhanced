#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""How Strongly: the ladder, the scale, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from feelingsupport import boundary, outcomes

from neural_workshop import feelings as F
from neural_workshop import howstrongly as M


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for r, seed, ref, wins in outcomes(M, (1, 4, 6, 8, 11, 20)):
            self.assertTrue(ref, (r, seed))
            self.assertEqual(wins, [], (r, seed))

    def test_the_tolerance_narrows_to_nothing(self):
        tol = [M.grade(r).tolerance for r in (4, 5, 7, 9, 11, 30)]
        self.assertEqual(tol, [8.0, 6.0, 4.0, 2.0, 0.0, 0.0])
        self.assertTrue(M.grade(3).strongest and not M.grade(4).strongest)

    def test_no_single_answer_for_all_four_passes(self):
        rnd = M.deal(6, seed=3)
        for it in rnd.items:
            for c in range(len(M.SCALE)):
                self.assertFalse(F.judge(it, [c] * len(it.steps)))

    def test_the_strongest_stands_out(self):
        rnd = M.deal(1, seed=2)
        for it in rnd.items:
            self.assertEqual(len(it.steps), 1)
            self.assertEqual(len(it.steps[0].options), 4)


class TheBoundary(unittest.TestCase):

    def test_reference_idle_and_sound(self):
        boundary(self, 'how_strongly', M, idle_steps=16000)


if __name__ == '__main__':
    unittest.main()
