#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A wait of uneven length: the deals, the floors and the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import Counter

from cuesupport import FRAME, drive, port_for
from memorysupport import best_from_view, per_port

from neural_workshop import unevenwait


def cue_place(p):
    (_frame, place, _colour), = p.data['cues']
    return place


def wait_of(p):
    """Frames from the cue's frame to the question's, less one."""
    return round(p.open_at / FRAME) - 1


class TheDeals(unittest.TestCase):

    def test_the_answer_is_the_port_of_the_place_that_lit(self):
        for look in (0, 1):
            for rung in range(1, 8):
                for seed in range(20):
                    p = unevenwait.deal('uneven', rung, random.Random(seed),
                                        look=look)
                    self.assertEqual(p.answer, port_for(look, cue_place(p)))

    def test_the_wait_is_drawn_evenly_from_n_to_three_n(self):
        for rung in (1, 2, 3, 5):
            rng, seen = random.Random(rung), Counter()
            n = 6000
            for _d in range(n):
                p = unevenwait.deal('uneven', rung, rng)
                seen[wait_of(p)] += 1
                self.assertEqual(p.data['wait'], wait_of(p))
            self.assertEqual(sorted(seen), list(range(rung, 3 * rung + 1)))
            share = 1 / (2 * rung + 1)
            for count in seen.values():
                self.assertAlmostEqual(count / n, share, delta=0.025)

    def test_no_fixed_distance_back_is_right_more_often(self):
        # The cue's frame, counted back from the question, is the wait
        # plus one; at rung 3 the likeliest distance holds one trial in
        # seven.
        rng, seen = random.Random(9), Counter()
        for _d in range(7000):
            seen[wait_of(unevenwait.deal('uneven', 3, rng)) + 1] += 1
        self.assertLess(max(seen.values()) / 7000, 0.17)


class TheFloors(unittest.TestCase):

    def test_the_question_frame_and_the_trial_length_are_at_chance(self):
        for look in (0, 1):
            for rung in (1, 3):
                deal = lambda rng: unevenwait.deal('uneven', rung, rng,  # noqa
                                                   look=look)
                self.assertLess(best_from_view(
                    deal, lambda p: (wait_of(p), p.data['layout'])), 0.28)
            per_port(self, lambda rng: unevenwait.deal('uneven', 2, rng,
                                                       look=look),
                     lambda p, port: wait_of(p), 4)


class TheBoundary(unittest.TestCase):

    def test_right_wrong_early_and_none(self):
        for hz in (2.0, 10.0):
            for rung in (1, 3):
                for seed in (1, 2):
                    self.assertEqual(drive('uneven_wait',
                                           lambda t: t.puzzle.answer, rung,
                                           seed=seed, frame_hz=hz), [1.0])
                self.assertEqual(drive('uneven_wait',
                                       lambda t: t.puzzle.answer, rung,
                                       wait=lambda t: 0, frame_hz=hz),
                                 [-1.0])
            self.assertEqual(drive('uneven_wait',
                                   lambda t: (t.puzzle.answer + 1) % 4,
                                   frame_hz=hz), [-1.0])
            self.assertEqual(drive('uneven_wait', lambda t: None,
                                   frame_hz=hz), [-1.0])


if __name__ == '__main__':
    unittest.main()
