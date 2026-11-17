#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tone of Voice: the ladder, the voice on the audio channel.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest
from array import array

from feelingsupport import boundary, outcomes

from neural_workshop import toneofvoice as M


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for r, seed, ref, wins in outcomes(M, (1, 2, 4, 7, 10, 13, 16)):
            self.assertTrue(ref, (r, seed))
            self.assertEqual([w for w in wins if w != 'random'], [],
                             (r, seed))

    def test_guessing_passes_rarely(self):
        from neural_workshop import feelings as F
        wins = sum(F.play(M.deal(1, seed=s), F.at_random(s + 500))[0]
                   for s in range(100))
        self.assertLessEqual(wins, 3)

    def test_the_choices_by_rung(self):
        self.assertEqual([M.grade(r).choices for r in (1, 2, 4, 7)],
                         [2, 3, 4, 6])
        self.assertFalse(M.grade(6).plain)
        self.assertTrue(M.grade(7).plain)
        self.assertEqual(M.grade(9).hiss, 0)
        self.assertGreater(M.grade(10).hiss, 0)
        self.assertGreater(M.grade(13).cut, 0)

    def test_the_hum_differs_by_emotion(self):
        sad = M._samples(M.Heard('', M.EMOTIONS.index('sadness'), 1), 0)
        fear = M._samples(M.Heard('', M.EMOTIONS.index('fear'), 1), 0)
        self.assertGreater(len(sad), len(fear))      # slower

    def test_each_item_is_heard(self):
        run = M.Run(M.deal(4, seed=1))
        it = run.item()
        n = M.length(it.face, run.level.cut)
        pcm = array('h', M.mix(run, 0.0, M.LEAD + n))
        self.assertGreater(max(abs(v) for v in pcm), 3000)
        quiet = array('h', M.mix(run, 0.0, M.LEAD * 0.5))
        self.assertLess(max(abs(v) for v in quiet), 200)


class TheBoundary(unittest.TestCase):

    def test_reference_idle_and_sound(self):
        boundary(self, 'tone_of_voice', M, idle_steps=16000)


if __name__ == '__main__':
    unittest.main()
