#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Several kept, one asked for: the deals, the floors and the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from cuesupport import FRAME, drive, port_for
from memorysupport import best_from_view, per_port, rate

from neural_workshop import severalcues


def deal(rung=1, look=0):
    return lambda rng: severalcues.deal('several', rung, rng, look=look)


class TheDeals(unittest.TestCase):

    def test_the_answer_is_where_the_colour_asked_for_lit(self):
        for look in (0, 1):
            for rung in range(1, 7):
                for seed in range(20):
                    p = severalcues.deal('several', rung, random.Random(seed),
                                         look=look)
                    lit = {colour: place
                           for _f, place, colour in p.data['cues']}
                    self.assertEqual(p.answer,
                                     port_for(look, lit[p.data['asked']]))

    def test_the_rung_is_how_many_cues_one_a_frame(self):
        for rung, n in ((1, 2), (2, 3), (3, 4), (4, 4), (8, 4)):
            p = severalcues.deal('several', rung, random.Random(rung))
            cues = p.data['cues']
            self.assertEqual([f for f, _p, _c in cues], list(range(n)))
            self.assertEqual(len({place for _f, place, _c in cues}), n)
            self.assertEqual(len({c for _f, _p, c in cues}), n)
            self.assertAlmostEqual(p.open_at, (n + 2) * FRAME)


class TheFloors(unittest.TestCase):

    def test_the_question_frame_is_at_chance(self):
        for look in (0, 1):
            for rung in (1, 3):
                self.assertLess(best_from_view(
                    deal(rung, look),
                    lambda p: (p.data['layout'], p.data['asked'])), 0.28)
            per_port(self, deal(2, look),
                     lambda p, port: p.data['asked'], 4)

    def test_answering_with_the_last_cue_shown(self):
        def last(p, rng):
            _f, place, _c = p.data['cues'][-1]
            return port_for(p.data['look'], place)
        for rung, n in ((1, 2), (2, 3), (3, 4)):
            self.assertAlmostEqual(rate(deal(rung), last), 1 / n,
                                   delta=0.03)


class TheBoundary(unittest.TestCase):

    def test_right_wrong_early_and_none(self):
        for hz in (2.0, 10.0):
            for rung in (1, 3):
                self.assertEqual(drive('which_was_where',
                                       lambda t: t.puzzle.answer, rung,
                                       frame_hz=hz), [1.0])
                self.assertEqual(drive('which_was_where',
                                       lambda t: t.puzzle.answer, rung,
                                       wait=lambda t: 1, frame_hz=hz),
                                 [-1.0])
            self.assertEqual(drive('which_was_where',
                                   lambda t: (t.puzzle.answer + 1) % 4,
                                   frame_hz=hz), [-1.0])
            self.assertEqual(drive('which_was_where', lambda t: None,
                                   frame_hz=hz), [-1.0])


if __name__ == '__main__':
    unittest.main()
