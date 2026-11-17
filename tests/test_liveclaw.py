#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Live Claw Machine: the rope, the fingers, the machine's cycle, the
deal, the pilot, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import liveclaw as M

DT = 1 / 60.0


def run_for(run, seconds, control=None):
    for _k in range(int(seconds / DT)):
        run.step(DT, control)


def empty(rung=1):
    """A cabinet with its one prize parked in a far corner."""
    cab = M.deal(rung, seed=1)
    far = cab.prizes[0]._replace(pos=(0.22, 0.22, cab.prizes[0].size[2]))
    return cab._replace(prizes=(far,))


class TheRope(unittest.TestCase):

    def test_the_claw_hangs_under_the_winch(self):
        run = M.Run(empty())
        run_for(run, 3.5)                    # the deal's own sway dies
        x, y, z = run.claw()
        self.assertAlmostEqual(z, M.TOP - M.ROPE0 - M.EYE, delta=0.004)
        self.assertLess(math.hypot(x - run.x, y - run.y), 0.003)

    def test_it_swings_when_the_gantry_stops_and_longer_higher_up(self):
        def swing(rung):
            """How wide it still swings a second after the stop."""
            run = M.Run(empty()._replace(level=M.grade(rung)))
            run_for(run, 3.0)
            run_for(run, 1.2, M.RIGHT)
            run_for(run, 1.0)
            widest = 0.0
            for _k in range(60):
                run.step(DT, None)
                x, y, _z = run.claw()
                widest = max(widest, math.hypot(x - run.x, y - run.y))
            return widest
        calm, loose = swing(1), swing(10)
        self.assertGreater(calm, 0.004)
        self.assertGreater(loose, calm * 2)

    def test_the_gantry_stays_inside_the_cabinet(self):
        run = M.Run(empty())
        run_for(run, 5.0, M.RIGHT)
        self.assertAlmostEqual(run.x, M.REACH)
        run_for(run, 5.0, M.AWAY)
        self.assertAlmostEqual(run.y, M.REACH)


class TheFingers(unittest.TestCase):

    def test_they_close_under_the_grip_and_spring_open_again(self):
        run = M.Run(empty())
        run_for(run, 0.5)
        self.assertLess(run.closed(), 0.3)
        for _k in range(400):
            run._grip(0.3)
            run.step(M.STEP, None)
        # Empty, the blades meet each other well short of the stop.
        self.assertGreater(run.closed(), 0.5)
        for _k in range(400):
            run._grip(0.0)
            run.step(M.STEP, None)
        self.assertLess(run.closed(), 0.3)


class TheMachine(unittest.TestCase):

    def test_a_play_runs_through_the_machine_s_cycle(self):
        run = M.Run(empty())
        run_for(run, 0.5)
        run.press()
        seen = []
        while run.result is None:
            if not seen or seen[-1] != run.phase:
                seen.append(run.phase)
            run.step(DT, None)
        self.assertEqual(seen, ['lower', 'grip', 'raise', 'carry', 'release'])
        self.assertEqual(run.result[0], False)

    def test_the_claw_comes_down_until_it_rests_and_no_further(self):
        run = M.Run(empty())
        run_for(run, 2.0, M.RIGHT)
        run_for(run, 1.5)
        run.press()
        while run.phase == 'lower':
            run.step(DT, None)
        # On the bare floor: the fingertips are on it, the hub a
        # finger's length above.
        self.assertAlmostEqual(run.claw()[2], M.TIP, delta=0.02)

    def test_time_running_out_presses_the_button(self):
        run = M.Run(empty())
        run_for(run, run.level.seconds + 0.5)
        self.assertNotEqual(run.phase, 'aim')

    def test_the_stick_does_nothing_once_the_button_is_pressed(self):
        run = M.Run(empty())
        run.press()
        x = run.x
        run_for(run, 0.5, M.RIGHT)
        self.assertAlmostEqual(run.x, x)

    def test_a_ball_under_the_claw_is_carried_to_the_chute(self):
        run = M.play(M.deal(1, seed=0))
        self.assertEqual(run.result[0], True)
        self.assertEqual(run.won, [0])
        self.assertLess(run.prize(0)[2], -0.06)


class TheDeal(unittest.TestCase):

    def test_prizes_lie_at_rest_in_the_pit_and_out_of_the_chute(self):
        for rung in (1, 4, 10, 16):
            cab = M.deal(rung, seed=2)
            self.assertEqual(len(cab.prizes), cab.level.prizes)
            run = M.Run(cab)
            before = [run.prize(i) for i in range(len(cab.prizes))]
            run_for(run, 1.0)
            for i, was in enumerate(before):
                now = run.prize(i)
                self.assertLess(math.dist(was, now), 0.004, (rung, i))
                self.assertGreater(now[2], 0.0)
                self.assertTrue(abs(now[0]) < M.HALF and abs(now[1]) < M.HALF)
                self.assertFalse(M.in_chute(now[0], now[1]))

    def test_the_same_seed_deals_the_same_cabinet(self):
        self.assertEqual(M.deal(10, seed=5), M.deal(10, seed=5))
        self.assertNotEqual(M.deal(10, seed=5), M.deal(10, seed=6))

    def test_the_machine_gets_meaner_up_the_ladder(self):
        grips = [M.grade(r).grip * M.grade(r).hold for r in (1, 7, 16, 40)]
        self.assertEqual(grips, sorted(grips, reverse=True))
        self.assertTrue(M.grade(13).gold and not M.grade(12).gold)
        self.assertGreaterEqual(M.grade(400).grip, 0.13)


class ThePilot(unittest.TestCase):

    def wins(self, rung, seeds):
        return sum(M.play(M.deal(rung, seed=s)).result[0] for s in seeds)

    def test_a_careful_pilot_wins_the_low_rungs(self):
        self.assertGreaterEqual(self.wins(1, range(8)), 7)
        self.assertGreaterEqual(self.wins(4, range(8)), 7)

    def test_and_most_of_a_heap(self):
        self.assertGreaterEqual(self.wins(10, range(6)), 4)

    def test_doing_nothing_and_pressing_at_random_win_nothing(self):
        rnd = random.Random(5)
        for seed in range(6):
            run = M.Run(M.deal(4, seed=seed))
            while run.result is None:
                run.step(DT, None)
            self.assertFalse(run.result[0])
            run = M.Run(M.deal(4, seed=seed))
            while run.result is None:
                port = rnd.randrange(M.PORTS)
                if port in M.EVENTS:
                    M.act(run, port)
                    port = None
                run.step(DT, port)
            self.assertFalse(run.result[0])

    def test_where_gold_must_be_won_another_prize_is_no_win(self):
        run = M.Run(M.deal(13, seed=1))
        run.won = [3]
        run._judge()
        self.assertFalse(run.result[0])
        run = M.Run(M.deal(13, seed=1))
        run.won = [0]
        run._judge()
        self.assertTrue(run.result[0])


class WhatIsDrawn(unittest.TestCase):

    def test_every_moving_solid_is_listed_where_it_is(self):
        run = M.Run(M.deal(4, seed=1))
        shapes = run.shapes()
        self.assertEqual(sum(1 for s in shapes if s.part == 'gold'), 1)
        self.assertEqual(sum(1 for s in shapes if s.part == 'prize'), 2)
        # Hub, stem, housing, and three pieces to each finger.
        self.assertEqual(sum(1 for s in shapes if s.part == 'claw'),
                         3 + 3 * M.FINGERS)
        for s in shapes:
            self.assertEqual(len(s.mat), 9)
            self.assertTrue(all(v > 0 for v in s.size))
        top, eye = run.rope_ends()
        self.assertAlmostEqual(top[2] - eye[2], M.ROPE0, delta=0.01)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_pilot_is_paid_and_idleness_is_not(self):
        pilot = queued(M.autopilot, lambda task: task.run)
        self.assertEqual(drive('live_claw_machine', 1, pilot, seed=2,
                               steps=3000), [1.0])
        self.assertEqual(drive('live_claw_machine', 1, lambda t: None, seed=2,
                               steps=4000), [-1.0])

    def test_the_other_window_is_a_port_and_the_stage_draws(self):
        from nwenv import catalog
        env = catalog.env_class('live_claw_machine')(seed=1, rung=4, trials=1,
                                                     adaptive=False)
        try:
            env.step(None)
            task = env.task
            self.assertTrue(task.stage.ok, task.stage.trouble)
            self.assertEqual(task.run.view, 0)
            env.step(M.VIEW)
            self.assertEqual(task.run.view, 1)
            task.on_draw()
            self.assertGreater(len(task._draws(1)), 20)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()
