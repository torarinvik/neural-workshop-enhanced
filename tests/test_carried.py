#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Carried through: the deals, the floors, and the boundary.

The answers are checked against a counter and a board kept here; what
the frame the question is put on says about the answer, and what
keeping only the start earns, are counted.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import Counter

from memorysupport import best_from_view, drive, per_port, rate

from neural_workshop import carried, framed

IDS = ('running_count', 'bead_pile', 'arrow_walk', 'chevron_walk')
#: Row and column steps for each arrow, rows counted from the top.
TURNS = {0: (-1, 0), 1: (1, 0), 2: (0, -1), 3: (0, 1),
         4: (-1, -1), 5: (-1, 1), 6: (1, -1), 7: (1, 1)}


def dealer(kind, rung=1, look=0):
    return lambda rng: carried.deal(kind, rung, rng, look=look)


def port_for(p, place):
    return framed.port_order(p.data['look'], carried.CARDS).index(place)


def truth(p):
    d = p.data
    if p.kind == 'count':
        total = d['start'] + sum(d['steps'])
        return port_for(p, d['cards'].index(total))
    row, col = divmod(d['start'], 2)
    for arrow in d['arrows']:
        dr, dc = TURNS[arrow]
        row, col = (row + dr) % 2, (col + dc) % 2
    return port_for(p, row * 2 + col)


class TheDeals(unittest.TestCase):

    def test_the_answer_is_what_a_counter_and_board_kept_here_say(self):
        for kind in carried.KINDS:
            for look in framed.LOOKS:
                for rung in (1, 2, 5, 12):
                    for seed in range(40):
                        p = carried.deal(kind, rung, random.Random(seed),
                                         look=look)
                        self.assertEqual(p.answer, truth(p), (kind, rung))

    def test_rung_k_has_k_events_and_asks_on_the_last(self):
        for kind in carried.KINDS:
            for rung in range(1, 10):
                p = carried.deal(kind, rung, random.Random(rung))
                events = p.data['steps' if kind == 'count' else 'arrows']
                self.assertEqual(len(events), rung)
                self.assertEqual(len(p.frames), rung + 1)
                self.assertAlmostEqual(p.open_at, rung * framed.FRAME)

    def test_the_pile_never_goes_below_nothing(self):
        for rung in range(1, 13):
            for seed in range(60):
                d = carried.deal('count', rung, random.Random(seed),
                                 look=1).data
                value = d['start']
                self.assertGreaterEqual(value, 0)
                for step in d['steps']:
                    value += step
                    self.assertGreaterEqual(value, 0)

    def test_each_kind_of_move_is_drawn_as_often(self):
        rng, seen = random.Random(9), Counter()
        for _d in range(4000):
            p = carried.deal('arrows', 1, rng)
            dr, dc = TURNS[p.data['arrows'][0]]
            seen[bool(dr), bool(dc)] += 1
        for key in ((True, False), (False, True), (True, True)):
            self.assertAlmostEqual(seen[key] / 4000, 1 / 3, delta=0.03)

    def test_the_twin_has_its_ports_the_other_way_round(self):
        a = carried.deal('count', 3, random.Random(2), look=0)
        b = carried.deal('count', 3, random.Random(2), look=1)
        self.assertEqual(a.data['cards'], b.data['cards'])
        self.assertEqual(a.answer, 3 - b.answer)


class TheFloors(unittest.TestCase):

    def test_the_last_event_and_the_cards_say_nothing(self):
        for rung in (1, 2, 4):
            for look in framed.LOOKS:
                count = dealer('count', rung, look)
                self.assertLess(best_from_view(
                    count, lambda p: (p.data['steps'][-1],
                                      p.data['cards'])), 0.28)
                per_port(self, count,
                         lambda p, port: p.data['steps'][-1], 4)
                arrows = dealer('arrows', rung, look)
                self.assertLess(best_from_view(
                    arrows, lambda p: p.data['arrows'][-1]), 0.28)
                per_port(self, arrows,
                         lambda p, port: p.data['arrows'][-1], 4)

    def best_from_start(self, p):
        """The card a player who kept only the start would press: the
        total the most step sequences reach from it."""
        reach = Counter({0: 1})
        for _step in p.data['steps']:
            nxt = Counter()
            for value, ways in reach.items():
                for step in carried.STEPS:
                    nxt[value + step] += ways
            reach = nxt
        start = p.data['start']
        best = max(p.data['cards'], key=lambda v: reach[v - start])
        return port_for(p, p.data['cards'].index(best))

    def test_keeping_only_the_start(self):
        counter = lambda p, rng: self.best_from_start(p)  # noqa: E731
        self.assertAlmostEqual(rate(dealer('count'), counter), 0.5,
                               delta=0.03)
        self.assertAlmostEqual(rate(dealer('count', 3), counter), 0.37,
                               delta=0.03)

        def marker(p, rng):
            # Anywhere but the start at rung 1; the start at rung 2.
            if len(p.data['arrows']) % 2:
                return port_for(p, rng.choice(
                    [c for c in range(4) if c != p.data['start']]))
            return port_for(p, p.data['start'])
        self.assertAlmostEqual(rate(dealer('arrows'), marker), 1 / 3,
                               delta=0.03)
        self.assertAlmostEqual(rate(dealer('arrows', 2), marker), 1 / 3,
                               delta=0.03)
        self.assertAlmostEqual(rate(dealer('arrows', 4), marker),
                               0.25 + 0.75 / 81, delta=0.03)


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
