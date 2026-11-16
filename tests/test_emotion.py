#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Emotion: the ladder, the faces, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from feelingsupport import boundary, outcomes

from neural_workshop import emotion as M
from neural_workshop import emotiondata as D


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for r, seed, ref, wins in outcomes(M, (1, 3, 6, 10, 14, 25)):
            self.assertTrue(ref, (r, seed))
            self.assertEqual(wins, [], (r, seed))

    def test_the_ladder_adds_what_it_says(self):
        self.assertEqual(M.grade(1).options, ('happiness', 'sadness'))
        self.assertEqual(len(M.grade(6).options), 8)
        self.assertTrue(M.grade(8).flash and not M.grade(7).flash)
        self.assertTrue(M.grade(10).crop and not M.grade(9).crop)
        self.assertTrue(M.grade(14).two and not M.grade(13).two)
        self.assertLess(M.grade(30).flash, M.grade(8).flash)
        self.assertGreaterEqual(M.grade(1).agree[0], 0.9)

    def test_the_first_faces_are_plain_and_the_answer_is_the_majority(self):
        rnd = M.deal(1, seed=4)
        for it in rnd.items:
            f = it.face
            self.assertGreaterEqual(f.agreement(), 0.9)
            st = it.steps[0]
            self.assertEqual(M.NAMES[D.EMOTIONS[f.top()]],
                             st.options[st.answer])

    def test_two_emotions_name_the_strongest_then_the_next(self):
        rnd = M.deal(14, seed=2)
        for it in rnd.items:
            r = it.face.ranked()
            a, b = it.steps
            self.assertEqual(a.options[a.answer], M.NAMES[D.EMOTIONS[r[0]]])
            self.assertEqual(b.options[b.answer], M.NAMES[D.EMOTIONS[r[1]]])


class TheFaces(unittest.TestCase):

    def test_drawn_faces_cover_every_emotion(self):
        drawn = D._drawn_faces()
        tops = {D.EMOTIONS[f.top()] for f in drawn}
        self.assertEqual(tops, set(D.EMOTIONS))
        self.assertTrue(all(f.total() == 10 for f in drawn))


class TheBoundary(unittest.TestCase):

    def test_reference_idle_and_sound(self):
        boundary(self, 'emotion', M)


if __name__ == '__main__':
    unittest.main()
