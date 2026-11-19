#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The newest counts and the first counts: the deals, the floors and
the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import Counter

from cuesupport import FRAME, drive, port_for
from memorysupport import best_from_view, per_port, rate

from neural_workshop import newestfirst


def deal(kind, rung=1, look=0):
    return lambda rng: newestfirst.deal(kind, rung, rng, look=look)


def other_rule(kind):
    """The player that keeps the other cue: the first on the newest,
    the last on the first."""
    def player(p, rng):
        cues = p.data['cues']
        _f, place, _c = cues[0] if kind == 'newest' else cues[-1]
        return port_for(p.data['look'], place)
    return player


#: What the other rule earns, by rung: counted here.
OTHER = {1: 0.5, 2: 0.45, 3: 0.39}


class TheDeals(unittest.TestCase):

    def test_the_answer_is_the_newest_or_the_first(self):
        for kind in newestfirst.KINDS:
            for look in (0, 1):
                for rung in range(1, 7):
                    for seed in range(20):
                        p = newestfirst.deal(kind, rung, random.Random(seed),
                                             look=look)
                        cues = p.data['cues']
                        _f, place, _c = cues[-1] if kind == 'newest' \
                            else cues[0]
                        self.assertEqual(p.answer, port_for(look, place))

    def test_later_cues_come_elsewhere_in_slots_every_other_frame(self):
        for rung in range(1, 7):
            seen = Counter()
            for seed in range(400):
                p = newestfirst.deal('first', rung, random.Random(seed))
                cues = p.data['cues']
                self.assertEqual(cues[0][0], 0)
                for (f0, a, _c), (f1, b, _c2) in zip(cues, cues[1:]):
                    self.assertNotEqual(a, b)
                    self.assertGreater(f1, f0)
                for f, _p, _c in cues[1:]:
                    self.assertIn(f, range(2, 2 * rung + 1, 2))
                self.assertAlmostEqual(p.open_at, (2 * rung + 2) * FRAME)
                seen[len(cues) - 1] += 1
            self.assertEqual(sorted(seen), list(range(rung + 1)))
            for count in seen.values():
                self.assertAlmostEqual(count / 400, 1 / (rung + 1),
                                       delta=0.08)


class TheFloors(unittest.TestCase):

    def test_the_question_frame_is_at_chance(self):
        for kind in newestfirst.KINDS:
            for look in (0, 1):
                self.assertLess(best_from_view(
                    deal(kind, 2, look), lambda p: p.data['layout']), 0.28)
                per_port(self, deal(kind, 2, look),
                         lambda p, port: p.data['layout'], 4)

    def test_answering_by_the_other_rule(self):
        for kind in newestfirst.KINDS:
            for rung, level in OTHER.items():
                self.assertAlmostEqual(rate(deal(kind, rung),
                                            other_rule(kind)),
                                       level, delta=0.03, msg=(kind, rung))


class TheBoundary(unittest.TestCase):

    def test_right_wrong_early_and_none(self):
        for task_id in ('newest_counts', 'first_counts'):
            for hz in (2.0, 10.0):
                for rung in (1, 3):
                    for seed in (1, 2, 3):
                        self.assertEqual(drive(task_id,
                                               lambda t: t.puzzle.answer,
                                               rung, seed=seed,
                                               frame_hz=hz), [1.0])
                    self.assertEqual(drive(task_id, lambda t: t.puzzle.answer,
                                           rung, wait=lambda t: 2,
                                           frame_hz=hz), [-1.0])
                self.assertEqual(drive(task_id,
                                       lambda t: (t.puzzle.answer + 1) % 4,
                                       frame_hz=hz), [-1.0])
                self.assertEqual(drive(task_id, lambda t: None,
                                       frame_hz=hz), [-1.0])


if __name__ == '__main__':
    unittest.main()
