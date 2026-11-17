#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Second Thoughts: the right answers are right, and the lure is there.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from feelingsupport import boundary, outcomes

from neural_workshop import secondthoughts as M


class ThePuzzles(unittest.TestCase):

    def test_every_puzzle_offers_its_lure_and_a_different_answer(self):
        d = random.Random(1)
        for kind, make in M.KINDS.items():
            for _k in range(40):
                p = make(d)
                if p is None:
                    continue
                self.assertNotEqual(p.options[p.answer], p.options[p.lure])
                self.assertEqual(len(set(p.options)), len(p.options), kind)

    def test_the_price(self):
        d = random.Random(2)
        for _k in range(20):
            p = M.price(d)
            low = float(p.options[p.answer])
            nums = [float(x) for x in
                    p.text.replace('.', ' ', 0).split() if
                    x.replace('.', '', 1).isdigit()]
            total, diff = nums
            self.assertAlmostEqual(low + (low + diff), total)

    def test_the_test(self):
        self.assertAlmostEqual(M._posterior(0.01, 0.8, 0.1, 1),
                               0.008 / (0.008 + 0.099))
        d = random.Random(3)
        for _k in range(20):
            p = M.test_counts(d)
            if p is None:
                continue
            found, of = (int(x) for x in p.options[p.answer].split(' of '))
            self.assertIn('%d of those' % found, p.text)
            self.assertIn('also for %d of' % (of - found), p.text)

    def test_the_kinds_by_rung(self):
        self.assertEqual(M.grade(1).kinds, ('race', 'pond', 'coin', 'counts'))
        self.assertIn('price', M.grade(4).kinds)
        self.assertIn('percent', M.grade(7).kinds)
        self.assertIn('two_tests', M.grade(13).kinds)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for r, seed, ref, wins in outcomes(M, (1, 4, 7, 10, 13, 20)):
            self.assertTrue(ref, (r, seed))
            self.assertEqual(wins, [], (r, seed))


class TheBoundary(unittest.TestCase):

    def test_reference_idle_and_sound(self):
        boundary(self, 'second_thoughts', M, idle_steps=16000)


if __name__ == '__main__':
    unittest.main()
