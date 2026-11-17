#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Same or Different?: every guise, the shrinking difference, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import samediff as M

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


class TheGuises(unittest.TestCase):

    def test_every_guise_deals(self):
        for guise in M.GUISES:
            for rung in (1, 10, 30):
                p = M.deal(rung, seed=3, guise=guise)
                self.assertEqual(p.guise, guise)
                if guise in M.SOUND:
                    self.assertTrue(p.notes)

    def test_same_means_same(self):
        for guise in ('shape', 'orientation', 'size'):
            for seed in range(20):
                p = M.deal(5, seed=seed, guise=guise)
                if p.answer == M.SAME:
                    if guise == 'orientation':
                        self.assertEqual(p.a.turn, p.b.turn)
                    if guise == 'size':
                        self.assertEqual(p.a.scale, p.b.scale)

    def test_the_difference_shrinks(self):
        self.assertGreater(M.grade(1).ease, M.grade(20).ease * 10)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 10):
            self.assertEqual(drive('same_or_different', rung, right, seed=2,
                                   steps=1200), [1.0], rung)
            self.assertEqual(drive('same_or_different', rung, wrong, seed=2,
                                   steps=1200), [-1.0], rung)


@needs_ui
class TheSound(unittest.TestCase):

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('same_or_different', rung=1, guise='pitch'), 0)


if __name__ == '__main__':
    unittest.main()
