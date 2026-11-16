#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Reading People: the ladder, the questions, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from feelingsupport import boundary, outcomes

from neural_workshop import readingpeople as M


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for r, seed, ref, wins in outcomes(M, (1, 4, 7, 10, 20)):
            self.assertTrue(ref, (r, seed))
            self.assertEqual(wins, [], (r, seed))

    def test_the_questions_by_rung(self):
        self.assertEqual([M.grade(r).kinds for r in (1, 4, 7)],
                         [('feel',), ('why',), ('act',)])
        self.assertEqual(len(M.grade(10).kinds), 3)
        for it in M.deal(4, seed=1).items:
            self.assertEqual(len(it.steps), 2)
        for it in M.deal(7, seed=1).items:
            self.assertEqual(len(it.steps), 1)


class TheBoundary(unittest.TestCase):

    def test_reference_idle_and_sound(self):
        boundary(self, 'reading_people', M)


if __name__ == '__main__':
    unittest.main()
