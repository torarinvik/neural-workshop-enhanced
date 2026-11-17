#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Button Box: the reference, random presses, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import buttonbox as M

RUNGS = (1, 4, 7, 10, 13, 20)


class TheBox(unittest.TestCase):

    def test_the_reference_always_matches(self):
        for rung in RUNGS:
            for seed in range(15):
                box = M.deal(rung, seed=seed)
                run = M.play(box)
                self.assertTrue(run.result[0], (rung, seed))
                self.assertLessEqual(run.used, box.budget)

    def test_random_presses_are_paid_at_first_and_not_later(self):
        def rate(rung):
            won = 0
            for seed in range(80):
                box = M.deal(rung, seed=seed)
                draw = random.Random(seed)
                run = M.Run(box)
                while run.result is None:
                    run.act(draw.randrange(13))
                won += run.result[0]
            return won / 80.0
        self.assertGreater(rate(1), 0.4)
        self.assertLess(rate(13), 0.1)

    def test_idle_and_one_button_fail(self):
        box = M.deal(7, seed=4)
        run = M.Run(box)
        for _k in range(40):
            run.act(0)
        self.assertFalse(run.result and run.result[0])

    def test_reset_is_free(self):
        box = M.deal(4, seed=1)
        run = M.Run(box)
        run.act(M.RESET)
        self.assertEqual(run.used, 0)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idle_does_not(self):
        pilots = {}

        def pilot(task):
            key = id(task.run)
            if key not in pilots:
                pilots[key] = M.Pilot(task.run.box)
            return pilots[key].next(task.run)
        for rung in (1, 10):
            self.assertEqual(drive('button_box', rung, pilot, seed=2,
                                   steps=400), [1.0])
        # Doing nothing is never paid; at rung 1 one button pressed over
        # and over may be (a guess paid often is the point of rung 1),
        # but not past it.
        self.assertNotEqual(drive('button_box', 1, lambda t: None, seed=2,
                                  steps=400), [1.0])
        self.assertEqual(drive('button_box', 10, lambda t: 0, seed=2,
                               steps=400), [-1.0])


if __name__ == '__main__':
    unittest.main()
