#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Which Block?: trying beats watching, the reference, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import blicket as M

RUNGS = (1, 4, 7, 10, 13, 16, 22)


class TheMachine(unittest.TestCase):

    def test_the_reference_finds_it(self):
        for rung in RUNGS:
            for seed in range(15):
                m = M.deal(rung, seed=seed)
                run = M.play(m)
                self.assertTrue(run.result[0], (rung, seed))

    def test_watching_alone_cannot_tell(self):
        for rung in (4, 7, 10, 13):
            for seed in range(15):
                m = M.deal(rung, seed=seed)
                self.assertIsNone(M.settled(m.level, m.seen), (rung, seed))

    def test_naming_without_trying_falls_short(self):
        for rung in (7, 13, 22):
            won = 0
            for seed in range(60):
                m = M.deal(rung, seed=seed)
                run = M.Run(m)
                for k in range(len(m.rule)):
                    run.act(M.NAME + k)
                won += bool(run.result and run.result[0])
            self.assertLess(won / 60.0, 0.3, rung)

    def test_two_needed_means_both_named(self):
        m = M.deal(10, seed=1)
        run = M.Run(m)
        run.act(M.NAME + min(m.rule))
        self.assertIsNone(run.result)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_a_guess_fails(self):
        pilots = {}

        def pilot(task):
            key = id(task.run)
            if key not in pilots:
                pilots[key] = M.Pilot()
            return pilots[key].next(task.run)
        for rung in (1, 10):
            self.assertEqual(drive('which_block', rung, pilot, seed=2,
                                   steps=400), [1.0])

        def guess(task):
            bad = [k for k in range(task.run.m.level.blocks)
                   if k not in task.run.m.rule]
            return M.NAME + bad[len(task.run.named) % len(bad)]
        self.assertEqual(drive('which_block', 4, guess, seed=2), [-1.0])


if __name__ == '__main__':
    unittest.main()
