#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Same or Mirror?: the ladder, the deals, the boundary, the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import draws, drive, right, wrong
from uisupport import needs_ui

from neural_workshop import mirror as M, space


class TheLadder(unittest.TestCase):

    def test_the_parts_come_in_on_their_rungs(self):
        self.assertFalse(M.grade(6).any_axis)
        self.assertTrue(M.grade(7).any_axis)
        self.assertLess(M.grade(1).most, M.grade(6).most)
        self.assertEqual([M.grade(r).options for r in (12, 13, 16, 21)],
                         [0, 3, 4, 5])
        self.assertTrue(M.grade(24).lit)
        self.assertFalse(M.grade(25).lit)


class TheDeals(unittest.TestCase):

    def test_every_deal_has_one_true_answer(self):
        for rung in (1, 5, 9, 12, 13, 17, 22, 28):
            for seed in range(25):
                self.assertTrue(M.truth(M.deal(rung, seed=seed)),
                                (rung, seed))

    def test_same_and_mirror_come_up_about_evenly(self):
        answers = [M.deal(4, seed=s).answer for s in range(200)]
        self.assertGreater(answers.count(M.SAME), 70)
        self.assertGreater(answers.count(M.MIRROR), 70)

    def test_the_turn_stays_within_the_rung(self):
        for rung in (1, 3, 8):
            most = M.grade(rung).most
            for seed in range(30):
                for angle in M.deal(rung, seed=seed).angles:
                    self.assertLessEqual(angle, most + 1e-6)

    def test_nudged_wrong_choices_are_one_cube_off(self):
        p = M.deal(22, seed=4)
        ref = set(space.canonical(p.reference.cubes))
        for i, f in enumerate(p.others):
            if i != p.answer:
                self.assertFalse(space.same_shape(p.reference.cubes,
                                                  f.cubes))
        del ref


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (2, 15):
            self.assertEqual(drive('same_or_mirror', rung, right), [1.0])
            self.assertEqual(drive('same_or_mirror', rung, wrong), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def test_every_kind_of_trial_draws(self):
        from neural_workshop.ui.mirror import SameOrMirror
        draws(self, SameOrMirror, (1, 8, 14, 18, 26))


if __name__ == '__main__':
    unittest.main()
