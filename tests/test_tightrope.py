#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tightrope: the lean, the pole, the birds, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, settle, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import hand as H
from neural_workshop import tightrope as M

RUNGS = (1, 4, 7, 10, 13, 16, 20, 22, 28, 35)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertLessEqual(len(rand), 1)

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 22, 40)}
        self.assertEqual((g[1].steps, g[4].steps), (6, 10))
        self.assertFalse(g[1].sway or g[1].gusts or g[1].birds)
        self.assertTrue(g[4].sway and not g[4].gusts)
        self.assertTrue(g[7].gusts and not g[7].birds)
        self.assertTrue(g[10].birds)
        self.assertGreater(g[40].steps, g[13].steps)
        self.assertTrue(g[13].breeze and not g[13].spring)
        self.assertTrue(g[16].spring and not g[16].bounce)
        self.assertTrue(g[22].bounce)


class TheWire(unittest.TestCase):

    def test_the_pole_out_to_the_right_tips_you_left(self):
        run = M.Run(M.deal(1, seed=1))
        run.hand.to(990.0, 300.0)
        self.assertEqual(run.aim(), 1.0)
        self.assertEqual(run.pole(), 0.0)    # the pole is heavy
        settle(run, 0.5)
        self.assertGreater(run.pole(), 0.9)
        self.assertLess(run.lean, 0.0)

    def test_steps_cannot_be_run(self):
        run = M.Run(M.deal(1, seed=1))
        M.act(run, M.STEP)
        M.act(run, M.STEP)
        self.assertEqual(run.taken, 1)
        settle(run, 0.4)
        M.act(run, M.STEP)
        self.assertEqual(run.taken, 2)

    def test_leaning_too_far_is_a_fall(self):
        run = M.Run(M.deal(1, seed=1))
        run.lean = M.FALL - 0.01
        run.rate = 1.0
        settle(run, 0.2)
        self.assertEqual(run.result[0], False)

    def test_a_bird_weighs_its_end_down_until_it_is_clicked_off(self):
        run = M.Run(M.deal(10, seed=1))
        run.perched.append(1)
        for _k in range(40):                # the pole moves with the hand
            x, y = run.bird_spot(1)
            run.hand.to(x, y)
        run.press()
        self.assertEqual(run.perched, [])

    def test_a_gust_is_heard_a_second_before_it_blows(self):
        walk = M.deal(7, seed=1)
        run = M.Run(walk)
        gust = walk.gusts[0]
        while run.t < gust.t - 0.5 and run.result is None:
            run.step(1 / 60.0)
            run.lean = run.rate = 0.0
        self.assertTrue(any(n.voice == M.WIND for n in run.notes))
        self.assertEqual(run.wind(), 0.0)

    def test_a_springy_wire_swings_when_you_step(self):
        run = M.Run(M.deal(16, seed=1))
        M.act(run, M.STEP)
        settle(run, 0.2)
        self.assertNotEqual(run.swing, 0.0)
        flat = M.Run(M.deal(4, seed=1))
        M.act(flat, M.STEP)
        settle(flat, 0.2)
        self.assertEqual(flat.swing, 0.0)

    def test_a_bounce_makes_a_lean_grow_faster(self):
        run = M.Run(M.deal(22, seed=1))
        calm = run.tip()
        M.act(run, M.STEP)
        settle(run, 0.1)
        self.assertGreater(run.tip(), calm)

@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('tightrope', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('tightrope', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('tightrope', M), 0)


if __name__ == '__main__':
    unittest.main()
