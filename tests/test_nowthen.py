#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Now and earlier: the deals, the floors, and the boundary.

The answers are checked against what a board kept here makes of the
two showings, not against the code that dealt them; what the frame the
question is put on says about the answer, and what the cheap partial
strategies earn, are counted.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import Counter

from memorysupport import best_from_view, drive, per_port, rate

from neural_workshop import framed, nowthen

IDS = {('moved', 0): 'which_moved', ('moved', 1): 'moved_bead',
       ('new', 0): 'which_is_new', ('new', 1): 'new_bead',
       ('gone', 0): 'which_is_gone', ('gone', 1): 'gone_bead',
       ('traded', 0): 'traded_places', ('traded', 1): 'traded_beads'}


def dealer(kind, rung=2, look=0):
    return lambda rng: nowthen.deal(kind, rung, rng, look=look)


def cards(p):
    """The thing on each port's card, read through the look's order."""
    order = framed.port_order(p.data['look'], len(p.choices))
    return [p.data['cards'][order[port]] for port in range(len(p.choices))]


def truth(p):
    """The port a board kept here says is right."""
    d = p.data
    if p.kind == 'traded':
        differ = [i for i in range(nowthen.ROW)
                  if d['first'][i] != d['second'][i]]
        assert len(differ) == 2 and d['marked'] in differ
        place = differ[0] if differ[1] == d['marked'] else differ[1]
        order = framed.port_order(d['look'], nowthen.ROW)
        return order.index(place)
    before, after = dict(d['first']), dict(d['second'])
    if p.kind == 'moved':
        (key,) = [t for t in before if before[t] != after[t]]
    elif p.kind == 'new':
        (key,) = set(after) - set(before)
    else:
        (key,) = set(before) - set(after)
    return cards(p).index(key)


class TheDeals(unittest.TestCase):

    def test_the_answer_is_what_a_board_kept_here_finds(self):
        for kind in nowthen.KINDS:
            for look in framed.LOOKS:
                for rung in (1, 2, 5, 9):
                    for seed in range(30):
                        p = nowthen.deal(kind, rung, random.Random(seed),
                                         look=look)
                        self.assertEqual(p.answer, truth(p), (kind, look))

    def test_rung_k_puts_k_frames_between_the_showings(self):
        for kind in nowthen.KINDS:
            for rung in range(1, 9):
                p = nowthen.deal(kind, rung, random.Random(rung))
                self.assertEqual(p.frames,
                                 (0,) + (-1,) * (rung - 1) + (1,))
                self.assertAlmostEqual(p.open_at, rung * framed.FRAME)

    def test_the_moved_thing_lands_on_an_empty_place(self):
        for seed in range(200):
            p = nowthen.deal('moved', 1, random.Random(seed))
            spots = [s for _t, s in p.data['second']]
            self.assertEqual(len(set(spots)), 4)

    def test_the_cards_of_gone_never_show_what_is_still_there(self):
        for seed in range(200):
            p = nowthen.deal('gone', 1, random.Random(seed))
            still = {t for t, _s in p.data['second']}
            self.assertFalse(still & set(p.data['cards']))
            shown = {t for t, _s in p.data['first']}
            self.assertEqual(len(shown & set(p.data['cards'])), 1)

    def test_the_twin_has_its_ports_the_other_way_round(self):
        a = nowthen.deal('moved', 2, random.Random(4), look=0)
        b = nowthen.deal('moved', 2, random.Random(4), look=1)
        self.assertEqual(cards(a), cards(b)[::-1])

    def test_layout_and_colour_change_from_trial_to_trial(self):
        rng = random.Random(1)
        looks = {(p.data['hue'], p.data['turn'], p.data['place'])
                 for p in (nowthen.deal('moved', 1, rng) for _i in range(40))}
        self.assertGreater(len(looks), 30)


class TheFloors(unittest.TestCase):
    """What a player without the earlier showing, and the cheap partial
    strategies, earn: the numbers in the module's docstring."""

    def test_the_second_showing_alone_is_at_chance(self):
        for kind in nowthen.KINDS:
            for look in framed.LOOKS:
                def view(p):
                    if p.kind == 'traded':
                        return (p.data['second'], p.data['marked'])
                    return (tuple(sorted(p.data['second'])),
                            tuple(cards(p)))
                self.assertLess(best_from_view(dealer(kind, look=look),
                                               view), 0.28, (kind, look))

    def test_no_card_leans_towards_the_answer(self):
        for look in framed.LOOKS:
            def spot_of(p, port):
                return dict(p.data['second']).get(cards(p)[port])
            per_port(self, dealer('moved', look=look), spot_of, 4)
            per_port(self, dealer('new', look=look), spot_of, 4)
            per_port(self, dealer('gone', look=look),
                     lambda p, port: cards(p)[port], 4)

    def test_traded_never_asks_for_the_marked_place_and_no_other_leans(self):
        rng = random.Random(3)
        seen, hit = Counter(), Counter()
        for _d in range(8000):
            p = nowthen.deal('traded', 2, rng)
            marked_port = framed.port_order(0, nowthen.ROW).index(
                p.data['marked'])
            self.assertNotEqual(p.answer, marked_port)
            for port in range(nowthen.ROW):
                if port != marked_port:
                    seen[port] += 1
                    hit[port] += p.answer == port
        for port, count in seen.items():
            self.assertAlmostEqual(hit[port] / count, 0.25, delta=0.03)

    def test_keeping_where_one_thing_was(self):
        def moved(p, rng):
            thing, spot = rng.choice(p.data['first'])
            mine = cards(p)
            if dict(p.data['second'])[thing] != spot:
                return mine.index(thing)
            return rng.choice([i for i in range(4) if mine[i] != thing])
        self.assertAlmostEqual(rate(dealer('moved'), moved), 0.5,
                               delta=0.03)

        def traded(p, rng):
            first, second = p.data['first'], p.data['second']
            place = rng.randrange(nowthen.ROW)
            thing = first[place]
            now = second.index(thing)
            if now == place:
                left = [i for i in range(nowthen.ROW)
                        if i not in (place, p.data['marked'])]
                return rng.choice(left)
            return place if now == p.data['marked'] else now
        self.assertAlmostEqual(rate(dealer('traded'), traded), 0.6,
                               delta=0.03)

    def test_keeping_one_or_two_of_the_old_things(self):
        def keeping(n):
            def player(p, rng):
                kept = [t for t, _s in rng.sample(p.data['first'], n)]
                return rng.choice([i for i, t in enumerate(cards(p))
                                   if t not in kept])
            return player
        self.assertAlmostEqual(rate(dealer('new'), keeping(1)), 1 / 3,
                               delta=0.03)
        self.assertAlmostEqual(rate(dealer('new'), keeping(2)), 1 / 2,
                               delta=0.03)

    def test_keeping_one_thing_from_before_it_went(self):
        def player(p, rng):
            thing, _spot = rng.choice(p.data['first'])
            if thing not in dict(p.data['second']):
                return cards(p).index(thing)
            return rng.randrange(4)
        self.assertAlmostEqual(rate(dealer('gone'), player), 7 / 16,
                               delta=0.03)


class TheBoundary(unittest.TestCase):

    def test_right_wrong_early_and_none(self):
        for task_id in IDS.values():
            for rung in (1, 3):
                self.assertEqual(drive(task_id, lambda t: t.puzzle.answer,
                                       rung), [1.0], (task_id, rung))
            n = len(nowthen.deal('traded' if 'traded' in task_id
                                 else 'moved', 1).choices)
            self.assertEqual(drive(task_id, lambda t: (t.puzzle.answer + 1)
                                   % n), [-1.0], task_id)
            self.assertEqual(drive(task_id, lambda t: t.puzzle.answer,
                                   early=0), [1.0], task_id)
            self.assertEqual(drive(task_id, lambda t: None), [-1.0],
                             task_id)

    def test_the_cards_are_blank_until_the_question_is_put(self):
        from nwenv import catalog
        env = catalog.env_class('which_is_new')(seed=2, rung=2, trials=1,
                                                adaptive=False)
        try:
            task = env.task
            env.step(None)
            self.assertFalse(task.run.open)
            calls = []
            real = task._thing
            task._thing = lambda *a, **k: (calls.append(a), real(*a, **k))
            task._draw_at(0, 0, 800, 600, 0.1)
            on_board = len(calls)
            calls.clear()
            task.run.t = task.puzzle.open_at
            task._draw_at(0, 0, 800, 600, task.run.t)
            self.assertEqual(on_board, 3)
            self.assertEqual(len(calls), 4 + 4)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()
