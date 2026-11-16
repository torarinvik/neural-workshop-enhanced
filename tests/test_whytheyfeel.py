#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Why They Feel: the stories, the answers offered, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from feelingsupport import boundary, outcomes

from neural_workshop import whytheyfeel as M


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for r, seed, ref, wins in outcomes(M, (1, 3, 5, 7, 9, 12, 15, 25)):
            self.assertTrue(ref, (r, seed))
            self.assertEqual(wins, [], (r, seed))

    def test_kinds_come_in_at_their_rungs(self):
        self.assertEqual(M.grade(1).kinds, ('happened',))
        self.assertIn('fortune', M.grade(9).kinds)
        self.assertTrue(M.grade(12).twist and not M.grade(11).twist)
        self.assertEqual([M.grade(r).depth for r in (14, 15, 20, 30, 99)],
                         [0, 1, 2, 4, 4])


class TheStories(unittest.TestCase):

    def test_every_kind_gives_its_own_emotions(self):
        level = M.grade(12)
        draw = random.Random(1)
        for kind, _at, emotions in M.KINDS:
            for _k in range(20):
                _text, _who, e = M.story(kind, level, draw)
                self.assertIn(e, emotions)

    def test_a_fair_second_answer_is_never_offered(self):
        for r in (5, 9, 13, 20):
            for it in M.deal(r, seed=2).items:
                st = it.steps[0]
                truth = [e for e, w in M.WORD.items()
                         if w == st.options[st.answer]][0]
                for o in st.options:
                    e = [e for e, w in M.WORD.items() if w == o][0]
                    self.assertNotIn(e, M.COMPAT[truth])

    def test_what_one_thinks_another_thinks_is_the_longest_chain(self):
        level = M.grade(25)
        draw = random.Random(4)
        for _k in range(20):
            text, question, e = M.believed(level, draw)
            last = text.split('. ')[-1]
            self.assertEqual(e == 'joy', any(
                good in last for good in
                [g.won.format(P='') for g in M.GOALS]))
            self.assertTrue(question.startswith('What does '))


class TheBoundary(unittest.TestCase):

    def test_reference_idle_and_sound(self):
        boundary(self, 'why_they_feel', M)


if __name__ == '__main__':
    unittest.main()
