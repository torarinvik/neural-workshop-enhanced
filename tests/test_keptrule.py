#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A rule that holds across trials: the blocks, the floors and the
boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import Counter

from cuesupport import FRAME, drive, port_for

from neural_workshop import keptrule


def place_of(p):
    (_f, place, _c), = p.data['cues']
    return place


def by_rule(rule, look, place):
    """The place to press, worked out here: the same, or across."""
    if rule == 'same':
        return place
    return {0: {0: 3, 1: 2, 2: 1, 3: 0},
            1: {0: 2, 1: 3, 2: 0, 3: 1}}[look][place]


def run_of(rung, n, seed, look=0):
    rng, ledger = random.Random(seed), keptrule.Ledger()
    return [keptrule.deal('rule', rung, rng, look=look, ledger=ledger)
            for _t in range(n)]


class Keeper:
    """A player that keeps the last sign it saw."""

    def __init__(self):
        self.rule = None

    def see(self, p):
        if p.data['sign'] is not None:
            self.rule = p.data['sign']

    def press(self, p):
        return port_for(p.data['look'],
                        by_rule(self.rule, p.data['look'], place_of(p)))


class TheBlocks(unittest.TestCase):

    def test_a_sign_starts_every_block_of_n_and_only_those(self):
        for rung in range(1, 7):
            run = run_of(rung, 6 * rung, rung)
            signs = [i for i, p in enumerate(run)
                     if p.data['sign'] is not None]
            self.assertEqual(signs, list(range(0, 6 * rung, rung)))

    def test_the_answer_follows_the_rule_signed(self):
        for look in (0, 1):
            for rung in (1, 2, 5):
                keeper = Keeper()
                for p in run_of(rung, 60, 7, look):
                    keeper.see(p)
                    self.assertEqual(p.answer, keeper.press(p))

    def test_the_sign_shows_a_frame_before_the_question(self):
        for p in run_of(3, 9, 2):
            self.assertAlmostEqual(p.open_at, FRAME)
            self.assertEqual(p.data['cues'][0][0], 1)

    def test_the_rule_of_a_block_is_drawn_evenly(self):
        rules = Counter(p.data['sign'] for p in run_of(1, 4000, 3))
        self.assertAlmostEqual(rules['same'] / 4000, 0.5, delta=0.03)

    def test_a_block_keeps_its_length_when_the_rung_changes(self):
        rng, ledger = random.Random(1), keptrule.Ledger()
        firsts = []
        for i, rung in enumerate([3, 1, 1, 4, 4, 4, 4, 2]):
            p = keptrule.deal('rule', rung, rng, ledger=ledger)
            if p.data['sign'] is not None:
                firsts.append(i)
        self.assertEqual(firsts, [0, 3, 7])


class TheFloors(unittest.TestCase):

    def test_without_the_sign(self):
        for rung in (1, 3):
            run = run_of(rung, 6000, 5)
            # The best player that sees the question frame -- the place
            # filled, and the layout -- and nothing kept: one half.
            seen = {}
            for p in run[:3000]:
                key = (place_of(p), p.data['layout'])
                seen.setdefault(key, Counter())[p.answer] += 1
            right = sum(seen[(place_of(p), p.data['layout'])]
                        .most_common(1)[0][0] == p.answer
                        for p in run[3000:])
            self.assertAlmostEqual(right / 3000, 0.5, delta=0.03)
            same = sum(port_for(0, place_of(p)) == p.answer for p in run)
            self.assertAlmostEqual(same / 6000, 0.5, delta=0.03)
            rng = random.Random(4)
            guess = sum(rng.randrange(4) == p.answer for p in run)
            self.assertAlmostEqual(guess / 6000, 0.25, delta=0.03)


class TheBoundary(unittest.TestCase):

    def test_a_block_played_by_the_sign_kept(self):
        for hz in (2.0, 10.0):
            for rung in (1, 3):
                keeper = Keeper()

                def pick(task):
                    keeper.see(task.puzzle)
                    return keeper.press(task.puzzle)

                def wait(task):
                    keeper.see(task.puzzle)
                    return None
                self.assertEqual(drive('same_or_opposite', pick, rung,
                                       wait=wait, frame_hz=hz,
                                       trials=2 * rung, steps=20000),
                                 [1.0] * (2 * rung), (hz, rung))

    def test_wrong_early_and_none(self):
        for hz in (2.0, 10.0):
            self.assertEqual(drive('same_or_opposite',
                                   lambda t: (t.puzzle.answer + 1) % 4,
                                   frame_hz=hz), [-1.0])
            self.assertEqual(drive('same_or_opposite',
                                   lambda t: t.puzzle.answer,
                                   wait=lambda t: 0, frame_hz=hz), [-1.0])
            self.assertEqual(drive('same_or_opposite', lambda t: None,
                                   frame_hz=hz), [-1.0])


if __name__ == '__main__':
    unittest.main()
