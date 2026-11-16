#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Night Watch: the torch, the thieves, the others, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, settle, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import hand as H
from neural_workshop import nightwatch as M

RUNGS = (1, 4, 7, 10, 13, 16, 22, 35)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertLessEqual(len(rand), 1)

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 20, 40)}
        self.assertEqual((g[1].thieves, g[1].others), (2, 0))
        self.assertTrue(g[4].others)
        self.assertGreater(g[7].half, g[4].half)
        self.assertTrue(g[7].fixed and not g[10].fixed)
        self.assertTrue(g[10].telling and not g[13].telling)
        self.assertTrue(g[16].weave and not g[13].weave)
        self.assertEqual([g[r].strikes for r in (1, 10, 20)], [3, 2, 1])
        self.assertLess(g[40].beam, g[20].beam)


class TheWarehouse(unittest.TestCase):

    def inside(self, rung, kind):
        """A run with a walker of *kind* in the building and in view."""
        night = M.deal(rung, seed=1)
        k = next(i for i, w in enumerate(night.walkers) if w.kind == kind)
        run = M.Run(night)
        run.t = night.walkers[k].enters + 1.0
        at = run.where(k)
        run.cam = max(-run.room(), min(run.room(), at[0]))
        return run, k

    def on(self, run, k):
        x, y, _unit = run.spot(k)
        run.hand.to(x, y)

    def test_a_click_on_a_thief_catches_them(self):
        run, k = self.inside(1, M.THIEF)
        self.on(run, k)
        self.assertTrue(run.lit(k))
        run.press()
        self.assertEqual((run.caught, run.strikes), (1, 0))
        self.assertIsNone(run.where(k))

    def test_a_click_on_the_guard_or_the_cat_is_a_strike(self):
        for kind in (M.GUARD, M.CAT):
            run, k = self.inside(4, kind)
            self.on(run, k)
            run.press()
            self.assertEqual((run.caught, run.strikes), (0, 1), kind)

    def test_a_click_on_nobody_wastes_a_blast(self):
        run = M.Run(M.deal(1, seed=1))
        have = run.blasts
        self.assertEqual(have, run.level.thieves + 3)
        run.hand.to(500.0, 600.0)
        for _k in range(have):
            self.assertIsNone(run.result)
            run.press()
            run.release()
        self.assertFalse(run.result[0])

    def test_a_thief_at_the_safe_ends_the_night(self):
        night = M.deal(1, seed=1)
        run = M.Run(night)
        while run.result is None:
            run.step(1 / 60.0)
        self.assertFalse(run.result[0])
        first = min(w.enters for w in night.walkers)
        self.assertAlmostEqual(run.t, first + night.level.cross, delta=0.2)

    def test_only_what_the_torch_is_on_is_lit(self):
        run, k = self.inside(1, M.THIEF)
        x, y, _unit = run.spot(k)
        run.hand.to(x, y)
        self.assertTrue(run.lit(k))
        run.hand.to((x + 500.0) % 1000.0, y)
        self.assertFalse(run.lit(k))

    def test_the_keys_turn_the_view_only_where_there_is_floor(self):
        run = M.Run(M.deal(1, seed=1))
        settle(run, 0.5, M.RIGHT)
        self.assertEqual(run.cam, 0.0)
        run = M.Run(M.deal(7, seed=1))
        settle(run, 0.5, M.RIGHT)
        self.assertGreater(run.cam, 0.0)
        settle(run, 5.0, M.RIGHT)
        self.assertAlmostEqual(run.cam, run.room())

    def test_steps_sound_from_the_side_they_fall_on(self):
        night = M.deal(1, seed=1)
        run = M.Run(night)
        w = night.walkers[0]
        settle(run, w.enters + 1.0)
        steps = [n for n in run.notes if n.voice == M.STEP]
        self.assertTrue(steps)
        self.assertEqual(steps[0].pan > 0, w.start[0] > 0)

    def test_the_orders_name_tonights_colours(self):
        night = M.deal(10, seed=1)
        run = M.Run(night)
        self.assertIn(night.thief, run.orders())
        self.assertNotEqual(night.thief, night.guard)
        self.assertTrue(all(w.colour == night.thief for w in night.walkers
                            if w.kind == M.THIEF))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('night_watch', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('night_watch', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('night_watch', M), 0)


if __name__ == '__main__':
    unittest.main()
