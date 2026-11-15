#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Explore or Exploit: the machines, the reference, par, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import bandit as M


class TheMachines(unittest.TestCase):

    def test_a_run_is_fixed_by_its_seed(self):
        self.assertEqual(M.deal(12, seed=2), M.deal(12, seed=2))

    def test_means_hold_drift_or_jump_by_rung(self):
        still = M.deal(5, seed=1)
        self.assertEqual(len(set(still.means)), 1)
        drift = M.deal(8, seed=1)
        self.assertGreater(len(set(drift.means)), 30)
        jumps = M.deal(11, seed=1)
        a, b = jumps.means[17], jumps.means[18]
        self.assertGreater(max(abs(x - y) for x, y in zip(a, b)), 1.0)

    def test_batched_payouts_show_in_fives(self):
        run = M.deal(17, seed=1)
        self.assertEqual([M.seen_after(run, t) for t in (4, 5, 9, 10)],
                         [0, 5, 5, 10])


class TheReference(unittest.TestCase):

    def test_it_beats_chance_and_meets_par_below_twenty(self):
        draw = random.Random(1)
        for rung in (2, 8, 11, 14, 17):
            ref = luck = 0
            for seed in range(20):
                run = M.deal(rung, seed=seed)
                self.assertGreaterEqual(M.reference(run), M.par(run) - 1e-9)
                ref += M.reference(run)
                luck += M.play(run, lambda h, t, c, run=run:
                               draw.randrange(run.level.arms))
            self.assertGreater(ref, luck * 1.05, rung)

    def test_past_twenty_par_asks_for_more(self):
        run = M.deal(26, seed=3)
        self.assertGreater(M.par(run), M.reference(run))


def reference(task):
    run = task.run
    n = len(task.chosen)
    history = [[] for _k in range(run.level.arms)]
    for s in range(M.seen_after(run, n)):
        history[task.chosen[s]].append((s, run.pays[s][task.chosen[s]]))
    return M.reference_policy(run)(history, n, task.chosen)


def worst(task):
    run = task.run
    t = len(task.chosen)
    return min(range(run.level.arms), key=lambda k: run.means[t][k])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_the_worst_machine_fails(self):
        for rung in (3, 12):
            self.assertEqual(drive('explore_exploit', rung, reference),
                             [1.0])
            self.assertEqual(drive('explore_exploit', rung, worst), [-1.0])


if __name__ == '__main__':
    unittest.main()
