#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Longer or Sooner?: durations and onsets, the tones, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import howlong as M

def heard(task_id, steps=400, seed=3, **dials):
    """Bytes of sound the agent is given over *steps* idle steps."""
    from nwenv import catalog
    env = catalog.env_class(task_id)(seed=seed, trials=5, adaptive=False,
                                     **dials)
    total = 0
    try:
        for _k in range(steps):
            env.step(None)
            chunk = env._public_audio
            if chunk:
                total += len(chunk['audio_pcm'])
    finally:
        env.close()
    return total


RUNGS = (1, 4, 7, 10, 13, 25)


class TheLadder(unittest.TestCase):

    def test_every_rung_deals(self):
        for rung in RUNGS:
            for seed in range(8):
                p = M.deal(rung, seed=seed)
                self.assertLess(p.answer, len(p.choices))
                self.assertLess(p.open_at, p.limit)

    def test_no_one_answer_is_a_safe_bet(self):
        for rung in (RUNGS[0], RUNGS[len(RUNGS) // 2], RUNGS[-1]):
            seen = collections.Counter(M.deal(rung, seed=s).answer
                                       for s in range(80))
            n = len(M.deal(rung, seed=0).choices)
            self.assertLessEqual(max(seen.values()) / 80.0,
                                 0.68 if n <= 3 else 2.6 / n, (rung, seen))


class TheTimes(unittest.TestCase):

    def test_the_answer_is_the_longer_or_the_first(self):
        for rung in (1, 7, 25):
            for seed in range(30):
                p = M.deal(rung, seed=seed)
                a, b = p.events
                if p.kind == 'longer':
                    d = [e.t1 - e.t0 for e in p.events]
                    self.assertEqual(d.index(max(d)), p.answer)
                else:
                    first = min(p.events, key=lambda e: e.t0)
                    self.assertEqual(first.side, p.answer)

    def test_tones_sound(self):
        p = next(q for q in (M.deal(1, seed=s) for s in range(40))
                 if q.guise == 'tone')
        self.assertEqual(len(p.notes), 2)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 10):
            self.assertEqual(drive('longer_or_sooner', rung, right, seed=2,
                                   steps=1200), [1.0], rung)
            self.assertEqual(drive('longer_or_sooner', rung, wrong, seed=2,
                                   steps=1200), [-1.0], rung)


@needs_ui
class TheSound(unittest.TestCase):

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('longer_or_sooner', rung=1), 0)


if __name__ == '__main__':
    unittest.main()
