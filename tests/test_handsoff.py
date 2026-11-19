#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Hands off: the deals, the closed wait, the floors and the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import Counter

from cuesupport import FRAME, drive, job_now, jobs_due, port_for
from memorysupport import best_from_view, per_port, rate

from neural_workshop import handsoff, keptcue

IDS = ('hands_off', 'busy_wait')


def cue_place(p):
    (frame, place, _colour), = p.data['cues']
    return place


def finish(p, presses):
    """The verdict of a run fed *presses* as (seconds, port)."""
    run = keptcue.Run(p)
    for t, port in sorted(presses):
        while run.result is None and run.t + 1e-9 < t:
            run.step(min(0.05, t - run.t))
        run.answer(port)
    while run.result is None:
        run.step(0.05)
    return run.result[0]


def by_the_jobs(p):
    return [((start + end) / 2, port) for start, end, port in jobs_due(p)]


class TheDeals(unittest.TestCase):

    def test_the_answer_is_the_port_of_the_place_that_lit(self):
        for kind in handsoff.KINDS:
            for look in (0, 1):
                for rung in range(1, 8):
                    for seed in range(20):
                        p = handsoff.deal(kind, rung, random.Random(seed),
                                          look=look)
                        self.assertEqual(p.answer,
                                         port_for(look, cue_place(p)))
                        self.assertEqual(p.data['cues'][0][0], 0)

    def test_the_wait_grows_with_the_rung(self):
        for rung in range(1, 9):
            p = handsoff.deal('still', rung, random.Random(rung))
            self.assertAlmostEqual(p.open_at, (rung + 1) * FRAME)
            self.assertEqual(p.data['jobs'], ())
            p = handsoff.deal('busy', rung, random.Random(rung))
            self.assertAlmostEqual(p.open_at, (2 * rung + 1) * FRAME)
            self.assertEqual([j[0] for j in p.data['jobs']],
                             [1 + 2 * j for j in range(rung)])

    def test_the_jobs_say_nothing_of_the_cue(self):
        rng, same, n = random.Random(3), Counter(), 8000
        for _d in range(n):
            p = handsoff.deal('busy', 2, rng)
            for _first, place in p.data['jobs']:
                same[place == cue_place(p)] += 1
        self.assertAlmostEqual(same[True] / (same[True] + same[False]),
                               0.25, delta=0.02)
        # Every press a trial can be played with, read back at the
        # question, and the question frame: still one in four.
        for look in (0, 1):
            deal = lambda rng: handsoff.deal('busy', 3, rng, look=look)  # noqa
            self.assertLess(best_from_view(
                deal, lambda p: (tuple(port for _s, _e, port in
                                       jobs_due(p)), p.data['layout'])),
                0.28)


class TheClosedWait(unittest.TestCase):

    def test_any_press_before_the_question_ends_hands_off(self):
        for seed in range(20):
            p = handsoff.deal('still', 3, random.Random(seed))
            for t in (0.0, 0.3, FRAME, p.open_at - 0.1):
                self.assertFalse(finish(p, [(t, p.answer),
                                            (p.open_at, p.answer)]))
            self.assertTrue(finish(p, [(p.open_at, p.answer)]))
            self.assertFalse(finish(p, [(p.open_at, (p.answer + 1) % 4)]))
            self.assertFalse(finish(p, []))

    def test_the_jobs_done_right_and_the_answer_pay(self):
        for seed in range(20):
            p = handsoff.deal('busy', 3, random.Random(seed))
            self.assertTrue(finish(p, by_the_jobs(p) +
                                   [(p.open_at, p.answer)]))

    def test_every_other_press_in_the_wait_ends_the_trial(self):
        for seed in range(20):
            p = handsoff.deal('busy', 3, random.Random(seed))
            good = by_the_jobs(p)
            end = [(p.open_at, p.answer)]
            self.assertFalse(finish(p, good[1:] + end), 'a job undone')
            t, port = good[1]
            wrong = good[:1] + [(t, (port + 1) % 4)] + good[2:]
            self.assertFalse(finish(p, wrong + end), 'a wrong press')
            self.assertFalse(finish(p, good + [(t + 0.1, port)] + end),
                             'a second press')
            self.assertFalse(finish(p, good + [(0.1, p.answer)] + end),
                             'a press on the cue frame')

    def test_a_job_may_be_pressed_on_either_of_its_frames(self):
        p = handsoff.deal('busy', 2, random.Random(4))
        for late in (0.0, FRAME):
            presses = [(start + late, port)
                       for start, _end, port in jobs_due(p)]
            self.assertTrue(finish(p, presses + [(p.open_at, p.answer)]))


class TheFloors(unittest.TestCase):

    def test_the_question_frame_is_at_chance(self):
        for kind in handsoff.KINDS:
            for look in (0, 1):
                deal = lambda rng: handsoff.deal(kind, 1, rng, look=look)  # noqa
                self.assertLess(best_from_view(
                    deal, lambda p: (p.data['layout'], p.data['hue'])),
                    0.28)
                per_port(self, deal, lambda p, port: p.data['layout'], 4)

    def test_presses_at_random(self):
        def player(p, rng):
            for _job in p.data['jobs']:
                if rng.randrange(4) != _job_port(p, _job):
                    return -1
            return rng.randrange(4)
        for rung in (1, 3):
            self.assertAlmostEqual(
                rate(lambda rng: handsoff.deal('still', rung, rng), player),
                0.25, delta=0.02)
            self.assertAlmostEqual(
                rate(lambda rng: handsoff.deal('busy', rung, rng), player),
                0.25 ** (rung + 1), delta=0.02)


def _job_port(p, job):
    return port_for(p.data['look'], job[1])


class TheBoundary(unittest.TestCase):

    def test_hands_off(self):
        for hz in (2.0, 10.0):
            for rung in (1, 3):
                self.assertEqual(drive('hands_off', lambda t: t.puzzle.answer,
                                       rung, frame_hz=hz), [1.0])
                self.assertEqual(drive('hands_off', lambda t: t.puzzle.answer,
                                       rung, wait=lambda t: 0,
                                       frame_hz=hz), [-1.0])
            self.assertEqual(drive('hands_off', lambda t: (t.puzzle.answer
                                                           + 1) % 4,
                                   frame_hz=hz), [-1.0])
            self.assertEqual(drive('hands_off', lambda t: None,
                                   frame_hz=hz), [-1.0])

    def test_busy_wait(self):
        for hz in (2.0, 10.0):
            for rung in (1, 3):
                self.assertEqual(drive('busy_wait', lambda t: t.puzzle.answer,
                                       rung, wait=job_now, frame_hz=hz),
                                 [1.0], (hz, rung))
                self.assertEqual(drive('busy_wait', lambda t: t.puzzle.answer,
                                       rung, frame_hz=hz), [-1.0])

                self.assertEqual(drive('busy_wait', lambda t: t.puzzle.answer,
                                       rung, wait=lambda t: (
                                           job_now(t) + 1) % 4
                                       if job_now(t) is not None else None,
                                       frame_hz=hz), [-1.0])


if __name__ == '__main__':
    unittest.main()
