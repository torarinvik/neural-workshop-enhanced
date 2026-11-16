#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Air Hockey: the puck, the goals, the keeper, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, settle, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import hand as H
from neural_workshop import airhockey as M

RUNGS = (1, 4, 7, 10, 13, 16, 22, 35)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertLessEqual(len(rand), 1)

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 20, 40)}
        self.assertEqual([g[r].need for r in (1, 4, 10)], [1, 2, 3])
        self.assertEqual([g[r].allow for r in (1, 10, 20)], [3, 2, 1])
        self.assertGreater(g[7].rival, g[4].rival)
        self.assertTrue(g[13].swing and not g[10].swing)
        self.assertTrue(g[16].flips and not g[13].flips)
        self.assertGreater(g[40].pace, g[20].pace)


class TheTable(unittest.TestCase):

    def loose(self, rung=1):
        run = M.Run(M.deal(rung, seed=1))
        run.wait = 0.0
        return run

    def test_a_puck_in_their_goal_is_yours(self):
        run = self.loose()
        run.theirs = (0.8, 1.2)
        run.puck, run.v = (0.0, 1.9), (0.0, 2.0)
        settle(run, 0.2)
        self.assertEqual(run.score, [1, 0])
        self.assertTrue(run.result[0])

    def test_a_puck_past_the_bar_is_theirs(self):
        run = self.loose()
        run.keeper = -0.15
        run.mine = (-0.8, 0.8)
        run.puck, run.v = (0.25, 0.3), (0.0, -2.0)
        settle(run, 0.3, M.LEFT)
        self.assertEqual(run.score, [0, 1])

    def test_the_bar_turns_the_puck_back(self):
        run = self.loose()
        run.keeper = 0.25
        run.mine = (-0.8, 0.8)
        run.puck, run.v = (0.25, 0.3), (0.0, -2.0)
        for _k in range(12):
            run.keeper = 0.25
            run.step(1 / 60.0)
        self.assertEqual(run.score, [0, 0])
        self.assertGreater(run.v[1], 0.0)

    def test_the_keys_slide_the_bar_inside_the_mouth(self):
        run = self.loose()
        settle(run, 0.1, M.RIGHT)
        self.assertGreater(run.keeper, 0.0)
        settle(run, 2.0, M.RIGHT)
        self.assertAlmostEqual(run.keeper, run.level.mouth)

    def test_the_mallet_follows_the_pointer_on_your_half_only(self):
        run = self.loose()
        q = run.see((0.5, 1.6))
        run.hand.to(q[0], q[1])
        settle(run, 0.5)
        self.assertAlmostEqual(run.mine[0], 0.5, places=1)
        self.assertLessEqual(run.mine[1], 0.95)

    def test_a_still_mallet_deadens_the_puck(self):
        run = self.loose()
        run.puck, run.v = (run.mine[0], run.mine[1] + 0.3), (0.0, -1.5)
        q = run.see(run.mine)
        run.hand.to(q[0], q[1])
        settle(run, 0.3)
        self.assertLess(abs(run.v[1]), 0.6)

    def test_from_the_far_end_right_is_still_right_on_the_screen(self):
        game = M.deal(16, seed=1)
        run = M.Run(game)
        run.t = game.flips[0][0] + 0.1
        self.assertTrue(run.far_end())
        before = run.see((run.keeper, 0.05))[0]
        run.step(1 / 60.0, M.RIGHT)
        self.assertGreater(run.see((run.keeper, 0.05))[0], before)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('air_hockey', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('air_hockey', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('air_hockey', M), 0)


if __name__ == '__main__':
    unittest.main()
