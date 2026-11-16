#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Bartender: the pour, the slide, the orders, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, settle, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import hand as H
from neural_workshop import bartender as M

RUNGS = (1, 4, 7, 10, 13, 16, 22, 35)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertLessEqual(len(rand), 1)

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 40)}
        self.assertEqual((g[1].customers, g[4].customers, g[7].customers),
                         (1, 2, 3))
        self.assertFalse(g[1].doubles or g[1].ice or g[1].pewter)
        self.assertTrue(g[4].doubles and g[7].ice and g[10].pewter)
        self.assertTrue(g[13].usual and not g[10].usual)
        self.assertEqual((g[1].strikes, g[10].strikes), (3, 2))
        self.assertGreater(g[40].customers, g[16].customers)


class TheBar(unittest.TestCase):

    def take(self, run, point):
        q = M.VIEW.see(point)
        run.hand.to(q[0], q[1])
        run.press()

    def over_the_glass(self, run):
        q = M.VIEW.see(run.glass())
        run.hand.to(q[0], q[1])

    def test_a_bottle_held_over_the_glass_pours(self):
        run = M.Run(M.deal(1, seed=1))
        self.take(run, M.bottle_at(1))
        self.assertEqual(run.held, ('bottle', 1))
        self.over_the_glass(run)
        settle(run, 1.0)
        self.assertAlmostEqual(run.level_in, M.POUR, places=2)
        self.assertEqual(run.drink, 1)
        pitches = [n.freq for n in run.notes if n.voice == M.POURING]
        self.assertGreater(pitches[-1], pitches[0])

    def test_pouring_over_the_brim_is_a_spill(self):
        run = M.Run(M.deal(1, seed=1))
        self.take(run, M.bottle_at(0))
        self.over_the_glass(run)
        settle(run, 2.8)
        self.assertEqual(run.strikes, 1)
        self.assertLess(run.level_in, 0.5)

    def test_two_bottles_in_one_glass_is_a_mix(self):
        run = M.Run(M.deal(1, seed=1))
        for k in (0, 1):
            self.take(run, M.bottle_at(k))
            self.over_the_glass(run)
            settle(run, 0.3)
            run.release()
        self.assertEqual(run.drink, -2)

    def test_the_glass_slides_four_times_its_push(self):
        run = M.Run(M.deal(1, seed=1))
        self.take(run, run.glass())
        self.assertEqual(run.held, ('glass', 0))
        for x in (-1.0, 0.0):
            q = M.VIEW.see((x, M.TOP + 0.3, 0.4))
            run.hand.to(q[0], q[1])
            run.step(1 / 60.0)
        self.assertAlmostEqual(run.glass_x, 0.0, places=1)
        run.release()
        self.assertAlmostEqual(run.sliding[0], M.SLIDE * 1.0, places=1)

    def test_ice_goes_in_and_comes_out(self):
        run = M.Run(M.deal(7, seed=1))
        M.act(run, M.ICE)
        self.assertTrue(run.ice)
        M.act(run, M.ICE)
        self.assertFalse(run.ice)

    def test_a_customer_kept_waiting_walks_out(self):
        night = M.deal(1, seed=1)
        run = M.Run(night)
        settle(run, night.orders[0].leave + 0.2)
        self.assertEqual(run.result[0], False)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('bartender', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('bartender', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('bartender', M), 0)


if __name__ == '__main__':
    unittest.main()
