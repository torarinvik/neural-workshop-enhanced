#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A cue far back: the deals, the floors, and the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from memorysupport import best_from_view, drive, per_port, rate

from neural_workshop import farcue, framed

IDS = ('the_marked_one', 'flagged_bead')


def dealer(rung=1, look=0):
    return lambda rng: farcue.deal('marked', rung, rng, look=look)


def cards(p):
    order = framed.port_order(p.data['look'], farcue.CARDS)
    return [p.data['cards'][order[port]] for port in range(farcue.CARDS)]


class TheDeals(unittest.TestCase):

    def test_the_answer_is_the_card_of_the_marked_thing(self):
        for look in framed.LOOKS:
            for rung in range(1, 7):
                for seed in range(30):
                    p = farcue.deal('marked', rung, random.Random(seed),
                                    look=look)
                    marked = p.data['first'][p.data['marked']]
                    self.assertEqual(cards(p)[p.answer], marked)
                    self.assertEqual(sorted(p.data['cards']),
                                     sorted(p.data['first']))

    def test_the_gap_doubles_each_rung_up_to_thirty_two(self):
        for rung, wanted in ((1, 2), (2, 4), (3, 8), (4, 16), (5, 32),
                             (6, 32), (9, 32)):
            p = farcue.deal('marked', rung, random.Random(rung))
            self.assertEqual(p.frames, (0,) + (1,) * wanted + (2,))
            self.assertEqual(len(p.data['fillers']), wanted)
            self.assertAlmostEqual(p.open_at, (wanted + 1) * framed.FRAME)

    def test_the_look_alikes_are_the_same_kind_of_thing_unmarked(self):
        p = farcue.deal('marked', 5, random.Random(2))
        first = set(p.data['first'])
        shared = sum(bool(first & set(f)) for f in p.data['fillers'])
        self.assertEqual(shared, len(p.data['fillers']))
        for filler in p.data['fillers']:
            self.assertEqual(len(set(filler)), farcue.PANELS)


class TheFloors(unittest.TestCase):

    def test_the_question_frame_is_at_chance(self):
        for look in framed.LOOKS:
            self.assertLess(best_from_view(dealer(look=look),
                                           lambda p: tuple(cards(p))), 0.28)
            per_port(self, dealer(look=look),
                     lambda p, port: cards(p)[port], 4)

    def test_keeping_the_first_frame_without_the_mark(self):
        def player(p, rng):
            return cards(p).index(rng.choice(p.data['first']))
        self.assertAlmostEqual(rate(dealer(), player), 0.25, delta=0.03)

    def test_keeping_where_the_mark_was_without_what(self):
        def player(p, rng):
            return p.data['marked']          # the panel, read as a port
        self.assertAlmostEqual(rate(dealer(), player), 0.25, delta=0.03)

    def test_keeping_only_the_last_frames(self):
        def player(p, rng):
            seen = set(p.data['fillers'][-1])
            return rng.choice([i for i, t in enumerate(cards(p))
                               if t in seen] or [0])
        self.assertAlmostEqual(rate(dealer(3), player), 0.25, delta=0.03)


class TheBoundary(unittest.TestCase):

    def test_right_wrong_early_and_none(self):
        for task_id in IDS:
            for rung in (1, 3):
                self.assertEqual(drive(task_id, lambda t: t.puzzle.answer,
                                       rung), [1.0], (task_id, rung))
            self.assertEqual(drive(task_id, lambda t: (t.puzzle.answer + 1)
                                   % 4), [-1.0], task_id)
            self.assertEqual(drive(task_id, lambda t: t.puzzle.answer,
                                   early=0), [1.0], task_id)
            self.assertEqual(drive(task_id, lambda t: None), [-1.0],
                             task_id)


if __name__ == '__main__':
    unittest.main()
