#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Card Sort: the rule, its changes, the reference, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import cardsort as M

RUNGS = (1, 4, 7, 10, 13, 16, 25)


class TheSorter(unittest.TestCase):

    def play(self, rung, pick, n=120, seed=1):
        s = M.Sorter(seed)
        right = 0
        reader = M.Reader()
        for _k in range(n):
            p = s.next(rung)
            k = pick(p, reader)
            ok = k == p.answer
            s.judged(ok)
            reader.heard(p, k, ok)
            right += ok
        return right / float(n)

    def test_the_reference_keeps_up(self):
        for rung in (1, 4, 7, 10, 13, 16, 25):
            self.assertGreater(self.play(rung, lambda p, r: r.pick(p)), 0.55,
                               rung)

    def test_guessing_and_sticking_fall_short(self):
        draw = random.Random(3)
        for rung in (4, 10, 16):
            self.assertLess(self.play(rung, lambda p, r: draw.randrange(
                len(p.keys))), 0.45, rung)
            self.assertLess(self.play(rung, lambda p, r: M.key_for(
                p.keys, p.card, 'colour')), 0.5, rung)

    def test_the_rule_changes(self):
        s = M.Sorter(2)
        rules = set()
        for _k in range(60):
            p = s.next(7)
            rules.add(p.rule)
            s.judged(True)
        self.assertGreater(len(rules), 1)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        self.assertEqual(drive('card_sort', 1, right, seed=2), [1.0])
        self.assertEqual(drive('card_sort', 1, wrong, seed=2), [-1.0])


if __name__ == '__main__':
    unittest.main()
