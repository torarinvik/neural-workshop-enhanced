#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Captcha: the characters, the rules, the clutter, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import captcha as M

RUNGS = (1, 4, 7, 10, 13, 16, 20, 24, 30)


class TheCharacters(unittest.TestCase):

    def test_the_answer_is_the_real_ones_left_to_right(self):
        for rung in RUNGS:
            for s in range(6):
                p = M.deal(rung, seed=s)
                real = sorted((g for g in p.glyphs if g.real),
                              key=lambda g: g.x)
                self.assertEqual(''.join(g.char for g in real), p.answer)
                self.assertEqual(len(p.answer), p.level.length)
                self.assertTrue(set(p.answer) <= set(M.ALPHABET))

    def test_no_confusable_characters(self):
        for c in '0O1IL2Z5S8B69':
            self.assertNotIn(c, M.ALPHABET)

    def test_every_decoy_breaks_a_rule_in_words(self):
        for rung in (10, 13, 16, 24, 28):
            for s in range(6):
                p = M.deal(rung, seed=s)
                decoys = [g for g in p.glyphs if not g.real]
                self.assertEqual(len(decoys), p.level.decoys)
                real = [g for g in p.glyphs if g.real]
                for g in decoys:
                    colour = 'only the' in p.rule and \
                        all(r.colour != g.colour for r in real)
                    small = 'small' in p.rule and \
                        g.size < 0.6 * min(r.size for r in real)
                    upside = 'upside-down' in p.rule and \
                        abs(g.angle - 180) <= 15 and \
                        g.char not in M.TURN_ALIKE
                    self.assertTrue(colour or small or upside, (rung, s, g))

    def test_real_ones_keep_every_rule(self):
        for rung in (10, 13, 16, 24, 28):
            for s in range(6):
                p = M.deal(rung, seed=s)
                real = [g for g in p.glyphs if g.real]
                if 'only the' in p.rule:
                    self.assertEqual(len({g.colour for g in real}), 1)
                if 'upside-down' in p.rule:
                    self.assertTrue(all(abs(g.angle) <= 40 for g in real))

    def test_clutter_grows_up_the_ladder(self):
        counts = [len(M.deal(r, seed=1).marks) for r in (1, 7, 13, 20, 30)]
        self.assertEqual(counts, sorted(counts))
        self.assertEqual(counts[0], 0)
        self.assertGreater(counts[-1], 150)

    def test_marks_stay_on_the_card(self):
        for s in range(5):
            for m in M.deal(28, seed=s).marks:
                if m.kind in ('blob', 'stray', 'arc'):
                    self.assertTrue(0 <= m.points[0] <= M.W)
                    self.assertTrue(0 <= m.points[1] <= M.H)

    def test_checking(self):
        p = M.deal(5, seed=2)
        self.assertTrue(M.check(p, p.answer)[0])
        self.assertFalse(M.check(p, p.answer[:-1])[0])
        self.assertFalse(M.check(p, p.answer + 'A')[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_typing_it_passes(self):
        def typist(task):
            typed = task.typed
            want = task.puzzle.answer
            if typed == want:
                return M.SUBMIT
            if not want.startswith(typed):
                return M.BACKSPACE
            return M.ALPHABET.index(want[len(typed)])
        self.assertEqual(drive('captcha', 11, typist, seed=1, steps=60),
                         [1.0])

    def test_typing_the_decoys_too_fails(self):
        def everything(task):
            every = ''.join(g.char for g in sorted(task.puzzle.glyphs,
                                                   key=lambda g: g.x))
            if task.typed == every:
                return M.SUBMIT
            return M.ALPHABET.index(every[len(task.typed)])
        self.assertEqual(drive('captcha', 11, everything, seed=1,
                               steps=60), [-1.0])

    def test_typing_nothing_fails(self):
        self.assertEqual(drive('captcha', 1, lambda t: M.SUBMIT, seed=1,
                               steps=5), [-1.0])


if __name__ == '__main__':
    unittest.main()
