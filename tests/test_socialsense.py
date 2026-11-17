#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Social Sense: the ladder, the pairs, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from feelingsupport import boundary, outcomes

from neural_workshop import socialdata as D
from neural_workshop import socialsense as M


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for r, seed, ref, wins in outcomes(M, (1, 4, 7, 10, 13, 20)):
            self.assertTrue(ref, (r, seed))
            self.assertEqual(wins, [], (r, seed))

    def test_the_questions_by_rung(self):
        self.assertEqual(M.grade(1).kinds, ('feel', 'describe'))
        self.assertIn('need', M.grade(4).kinds)
        self.assertIn('why', M.grade(7).kinds)
        self.assertFalse(M.grade(12).pairs)
        self.assertTrue(M.grade(13).pairs)

    def test_a_pair_asks_two_things_of_one_situation(self):
        for it in M.deal(13, seed=1).items:
            self.assertEqual(len(it.steps), 2)
            self.assertNotEqual(it.steps[0].ask, it.steps[1].ask)
            asked = {q.ask for q in D.of('social') if q.prompt == it.prompt}
            self.assertTrue({s.ask for s in it.steps} <= asked)

    def test_the_question_kinds_are_told_apart(self):
        self.assertEqual(D.social_kind('Why did Sam do this?'), 'why')
        self.assertEqual(D.social_kind('How would others feel as a result?'),
                         'others_feel')
        self.assertEqual(D.social_kind('How would Sam feel afterwards?'),
                         'feel')
        self.assertEqual(D.social_kind('What will Sam want to do next?'),
                         'want')


class TheBoundary(unittest.TestCase):

    def test_reference_idle_and_sound(self):
        boundary(self, 'social_sense', M, idle_steps=16000)


if __name__ == '__main__':
    unittest.main()
