#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Delay: the waits, the rules, par, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import delay as M


class TheWaits(unittest.TestCase):

    def test_each_kind_of_wait(self):
        uniform = [o.wait for o in M.deal(5, seed=1).offers]
        self.assertTrue(all(2.0 <= w <= 6.0 for w in uniform))
        heavy = [o.wait for o in M.deal(8, seed=1).offers]
        self.assertTrue(any(w > 30 for w in heavy))
        never = [o.wait for o in M.deal(17, seed=1).offers]
        self.assertTrue(any(w == M.NEVER for w in never))
        self.assertTrue(all(w <= 4.0 or w == M.NEVER for w in never))

    def test_patience_pays_only_up_to_a_point(self):
        """Fair waits reward waiting them out; heavy-tailed ones punish
        it, and giving up after a few seconds is what pays."""
        fair = [M.deal(5, seed=s) for s in range(10)]
        heavy = [M.deal(8, seed=s) for s in range(10)]
        always = lambda o: M.NEVER    # noqa: E731
        never_wait = lambda o: 0      # noqa: E731
        self.assertGreater(sum(M.play(r, always) for r in fair),
                           sum(M.play(r, never_wait) for r in fair))
        self.assertLess(sum(M.play(r, always) for r in heavy),
                        sum(M.play(r, never_wait) for r in heavy))
        self.assertGreater(sum(M.play(r, lambda o: 3.0) for r in heavy),
                           sum(M.play(r, never_wait) for r in heavy))

    def test_par_sits_between_the_floor_and_the_reference(self):
        for rung in (2, 8, 14, 18):
            for seed in range(5):
                run = M.deal(rung, seed=seed)
                self.assertLessEqual(M.floor(run), M.par(run) + 1e-9)
                self.assertLessEqual(M.par(run), M.reference(run) + 1e-9)


def patient(seconds):
    def policy(task):
        if task.mode == 'offer':
            return 1
        if task.mode == 'waiting' and \
                task.clock() - task.since > seconds:
            return 0
        return None
    return policy


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_waiting_well_passes_and_grabbing_fails(self):
        self.assertEqual(drive('delay', 5, patient(M.NEVER), seed=3,
                               steps=5000), [1.0])
        self.assertEqual(drive('delay', 5, lambda t: 0 if t.mode == 'offer'
                               else None, seed=3, steps=5000), [-1.0])


if __name__ == '__main__':
    unittest.main()
