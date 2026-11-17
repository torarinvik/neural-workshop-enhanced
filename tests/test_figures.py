#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Figures of Speech: the ladder, the parsing, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from feelingsupport import boundary, outcomes

from neural_workshop import figures as M
from neural_workshop import socialdata as D


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for r, seed, ref, wins in outcomes(M, (1, 4, 7, 10, 20)):
            self.assertTrue(ref, (r, seed))
            self.assertEqual(wins, [], (r, seed))

    def test_more_figures_to_choose_from_higher_up(self):
        self.assertEqual([M.grade(r).figures for r in (4, 7, 10)],
                         [4, 6, 8])
        self.assertEqual(M.grade(10).kinds,
                         ('metaphor', 'figure', 'fable', 'odd_metaphor'))

    def test_a_metaphor_row_becomes_its_differing_words(self):
        row = {'inputs': 'paraphrase: \nQ: He sat like a carved image. '
               'option: He sat completely still. option: He sat for a '
               'long time.\nA:',
               'multiple_choice_targets': ['He sat completely still.',
                                           'He sat for a long time.'],
               'multiple_choice_scores': [1, 0]}
        q = D.parse_big('metaphor', row)
        self.assertEqual(q.options, ('completely still.', 'for a long time.'))
        self.assertIn('He sat ___', q.prompt)
        self.assertEqual(q.answer, 0)

    def test_the_right_answer_survives_the_cut(self):
        for it in M.deal(4, seed=2).items:
            st = it.steps[0]
            self.assertLessEqual(len(st.options), 5)
            self.assertIn(it.truth, st.options)


class TheBoundary(unittest.TestCase):

    def test_reference_idle_and_sound(self):
        boundary(self, 'figures_of_speech', M, idle_steps=16000)


if __name__ == '__main__':
    unittest.main()
