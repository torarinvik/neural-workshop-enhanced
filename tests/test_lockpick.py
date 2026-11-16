#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Lock Pick: the tension, the pins, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, settle, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import hand as H
from neural_workshop import lockpick as M

RUNGS = (1, 4, 7, 10, 13, 16, 22, 35)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertLessEqual(len(rand), 1)

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 40)}
        self.assertEqual((g[1].pins, g[4].pins, g[7].pins), (3, 4, 5))
        self.assertTrue(g[1].ordered and g[1].glow and g[1].tone)
        self.assertFalse(g[4].ordered or g[4].glow)
        self.assertFalse(g[7].tone)
        self.assertTrue(g[10].false and not g[7].false)
        self.assertTrue(g[13].hidden and not g[10].hidden)
        self.assertLess(g[40].fine, g[1].fine)


class TheLock(unittest.TestCase):

    def test_tension_builds_while_held_and_eases_when_let_go(self):
        run = M.Run(M.deal(1, seed=1))
        settle(run, 0.4, M.TENSION)
        high = run.tension
        self.assertGreater(high, 0.2)
        settle(run, 1.0)
        self.assertLess(run.tension, high)

    def test_too_much_tension_slips_and_three_slips_fail(self):
        run = M.Run(M.deal(1, seed=1))
        while run.result is None:
            run.step(1 / 60.0, M.TENSION)
        self.assertEqual(run.slips, 3)
        self.assertFalse(run.result[0])

    def test_the_binding_pin_sets_at_its_height_in_the_band(self):
        lock = M.deal(1, seed=1)
        run = M.Run(lock)
        run.tension = sum(run.level.band) / 2
        k = run.binding
        run.hand.to(M.pin_x(k), M.FLOOR + M.LIFT * lock.heights[k])
        run.press()
        for _k in range(12):
            run.tension = sum(run.level.band) / 2
            run.step(1 / 60.0)
        self.assertEqual(run.set, 1)
        self.assertTrue(run.is_set(k))

    def test_shoving_a_pin_past_its_height_jams_the_lock(self):
        lock = M.deal(4, seed=1)
        run = M.Run(lock)
        run.set = 1
        k = run.binding
        run.tension = sum(run.level.band) / 2
        run.hand.to(M.pin_x(k), M.FLOOR + M.LIFT * min(
            1.0, lock.heights[k] + 3 * run.level.fine))
        run.press()
        run.step(1 / 60.0)
        if lock.heights[k] + 3 * run.level.fine <= 1.0:
            self.assertEqual(run.set, 0)

    def test_set_pins_drop_when_the_tension_goes(self):
        run = M.Run(M.deal(1, seed=1))
        run.set = 2
        settle(run, 1.2)
        self.assertLess(run.set, 2)

@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('lock_pick', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('lock_pick', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('lock_pick', M), 0)


if __name__ == '__main__':
    unittest.main()
