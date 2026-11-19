#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Heard back: the deals, the floors, and the boundary.

The answers are checked against the notes as they will sound, read
back from their pitches and voices, not against the dealer's own
record.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from memorysupport import best_from_view, drive, per_port, rate

from neural_workshop import framed, heardback

IDS = ('changed_note', 'changed_chime', 'marked_tone', 'other_voice')


def dealer(kind, rung=1, look=0):
    return lambda rng: heardback.deal(kind, rung, rng, look=look)


def port_for(p, place):
    return framed.port_order(p.data['look'], 4).index(place)


def truth(p):
    notes = sorted(p.notes, key=lambda n: n.t)
    if p.kind == 'melody':
        heard = [rank_bent(p, n) for n in notes]
        first, second = heard[:4], heard[4:]
        (where,) = [i for i in range(4) if first[i] != second[i]]
        return port_for(p, where)
    marked = [n for n in notes if n.voice == 1]
    assert len(marked) == 1 and marked[0].t == 0
    return port_for(p, rank_bent(p, marked[0]))


def rank_bent(p, note):
    """The pitch's rank among the four, read from its frequency: the
    four are nearly three or more semitones apart and move together by
    at most a semitone, so only its own lies that close."""
    base = heardback.PITCHES[p.data['look']]
    near = [i for i, b in enumerate(base)
            if abs(12 * math.log2(note.freq / b)) <= 1.0 + 1e-9]
    assert len(near) == 1, (note.freq, base)
    return near[0]


class TheDeals(unittest.TestCase):

    def test_the_answer_is_what_the_notes_say(self):
        for kind in heardback.KINDS:
            for look in framed.LOOKS:
                for rung in (1, 2, 4, 6):
                    for seed in range(25):
                        p = heardback.deal(kind, rung, random.Random(seed),
                                           look=look)
                        self.assertEqual(p.answer, truth(p), (kind, rung))

    def test_a_tone_a_frame(self):
        p = heardback.deal('melody', 3, random.Random(1))
        self.assertEqual([round(n.t / framed.FRAME) for n in p.notes],
                         [0, 1, 2, 3, 6, 7, 8, 9])
        self.assertAlmostEqual(p.open_at, 9 * framed.FRAME)
        p = heardback.deal('mark', 2, random.Random(1))
        self.assertEqual([round(n.t / framed.FRAME) for n in p.notes],
                         list(range(5)))
        self.assertAlmostEqual(p.open_at, 5 * framed.FRAME)

    def test_only_the_marked_tone_has_the_other_voice(self):
        for seed in range(30):
            p = heardback.deal('mark', 3, random.Random(seed))
            voices = [n.voice for n in sorted(p.notes, key=lambda n: n.t)]
            self.assertEqual(voices, [1] + [0] * 8)
            self.assertEqual(len(p.patches), 2)


class TheFloors(unittest.TestCase):

    def test_the_tone_heard_when_asked_says_nothing(self):
        for look in framed.LOOKS:
            def last(p):
                return rank_bent(p, max(p.notes, key=lambda n: n.t))
            self.assertLess(best_from_view(dealer('melody', look=look),
                                           last), 0.28)
            per_port(self, dealer('melody', look=look),
                     lambda p, port: last(p), 4)
            self.assertLess(best_from_view(dealer('mark', look=look),
                                           last), 0.28)

    def test_keeping_the_last_tone_of_the_first_four(self):
        def player(p, rng):
            notes = sorted(p.notes, key=lambda n: n.t)
            if rank_bent(p, notes[3]) != rank_bent(p, notes[-1]):
                return port_for(p, 3)
            return port_for(p, rng.randrange(3))
        self.assertAlmostEqual(rate(dealer('melody'), player, 3000), 0.5,
                               delta=0.035)

    def test_pressing_the_pitch_last_heard(self):
        def player(p, rng):
            return port_for(p, rank_bent(p, max(p.notes,
                                                 key=lambda n: n.t)))
        self.assertAlmostEqual(rate(dealer('mark', 2), player, 3000), 0.25,
                               delta=0.035)


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
