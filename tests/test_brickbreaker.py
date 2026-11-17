#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""3D Brick Breaker: the paddle, the ball, each kind of brick, the
deal, the pilot, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import brickbreaker as M

DT = 1 / 120.0


def board(rung=1, bricks=()):
    return M.deal(rung, seed=1)._replace(bricks=tuple(bricks))


def brick(i=1, j=0, k=0, kind=M.PLAIN, hits=1, colour=0, order=-1):
    return M.Brick(i, j, k, kind, hits, colour, order)


def fly(run, seconds, control=None):
    for _k in range(int(seconds / DT)):
        run.step(DT, control)
        if run.result is not None:
            break


def shot(run, at, velocity):
    """Puts the ball in flight from *at*."""
    ball = run.balls[0]
    ball.held = 0.0
    ball.p, ball.v = list(at), list(velocity)
    run.touched = True
    return ball


class ThePaddle(unittest.TestCase):

    def test_the_ports_slide_it_and_the_box_stops_it(self):
        run = M.Run(board())
        fly(run, 0.25, M.RIGHT)
        self.assertAlmostEqual(run.px, 0.25 * M.PADDLE_SPEED, places=2)
        fly(run, 3.0, M.UP_RIGHT)
        pw, ph = run.level.paddle
        self.assertAlmostEqual(run.px, M.WIDE - pw)
        self.assertAlmostEqual(run.py, M.HIGH - ph)

    def test_the_mouse_is_followed(self):
        run = M.Run(board())
        run.point(-0.4, 0.2)
        fly(run, 0.5)
        self.assertAlmostEqual(run.px, -0.4, places=3)
        self.assertAlmostEqual(run.py, 0.2, places=3)

    def test_it_tilts_to_face_the_way_it_is_told_and_no_further(self):
        run = M.Run(board())
        fly(run, 0.2, M.FACE_RIGHT)
        self.assertGreater(run.normal()[0], 0.1)
        fly(run, 0.2, M.FACE_UP)
        self.assertGreater(run.normal()[1], 0.1)
        fly(run, 3.0, M.FACE_LEFT)
        self.assertAlmostEqual(run.yaw, -M.TILT_MOST)
        run.press(M.LEVEL)
        self.assertEqual(run.normal(), (0.0, 0.0, -1.0))

    def test_a_tilted_paddle_is_a_mirror(self):
        run = M.Run(board())
        run.yaw = 0.3
        ball = shot(run, (0.0, 0.0, -0.5), (0.0, 0.0, 1.5))
        fly(run, 0.5)
        self.assertGreater(ball.v[0], 0.5)       # sent off to the right
        self.assertLess(ball.v[2], 0)
        self.assertAlmostEqual(math.sqrt(sum(c * c for c in ball.v)),
                               run.speed, places=5)

    def test_nothing_is_served_until_the_paddle_is_touched(self):
        run = M.Run(board())
        fly(run, 5.0)
        self.assertGreater(run.balls[0].held, 0)
        self.assertEqual(run.lives, run.level.lives)
        fly(run, 0.05, M.LEFT)
        fly(run, M.HOLD + 0.1)
        self.assertLessEqual(run.balls[0].held, 0)
        self.assertLess(run.balls[0].v[2], 0)


class TheBall(unittest.TestCase):

    def test_the_box_keeps_it_in(self):
        run = M.Run(board())
        ball = shot(run, (0.0, 0.0, -1.5), (1.2, 0.8, -0.5))
        for _k in range(600):
            run.step(DT)
            if run.result is not None or ball.held > 0:
                break
            self.assertLessEqual(abs(ball.p[0]), M.WIDE)
            self.assertLessEqual(abs(ball.p[1]), M.HIGH)
            self.assertGreaterEqual(ball.p[2], -M.DEEP)

    def test_a_ball_that_gets_past_costs_a_life(self):
        run = M.Run(board())
        run.px = 0.6
        shot(run, (-0.6, 0.0, -0.3), (0.0, 0.0, 1.5))
        fly(run, 1.0)
        self.assertEqual(run.lives, run.level.lives - 1)
        self.assertGreater(run.balls[0].held, 0)

    def test_the_last_life_ends_it(self):
        run = M.Run(board(bricks=[brick()]))
        run.lives = 1
        run.px = 0.6
        shot(run, (-0.6, 0.0, -0.3), (0.0, 0.0, 1.5))
        fly(run, 1.0)
        self.assertEqual(run.result[0], False)

    def test_time_runs_out(self):
        run = M.Run(board(bricks=[brick()]))
        fly(run, run.level.seconds + 1.0)
        self.assertEqual(run.result[0], False)

    def test_gravity_and_wind_bend_it_where_they_are_in_play(self):
        run = M.Run(board(16))
        ball = shot(run, (0.0, 0.3, -0.2), (0.0, 0.0, -2.0))
        fly(run, 0.4)
        self.assertLess(ball.v[1], -0.3)
        calm = M.Run(board(1))
        ball = shot(calm, (0.0, 0.3, -0.2), (0.0, 0.0, -1.5))
        fly(calm, 0.4)
        self.assertEqual(ball.v[1], 0.0)


def strike(run, target, colour=1):
    """Sends the ball straight into a brick's front."""
    c, _h = run.box(target)
    ball = shot(run, (c[0], c[1], c[2] + 0.5), (0.0, 0.0, -1.5))
    ball.colour = colour
    fly(run, 0.4)
    return ball


class TheBricks(unittest.TestCase):

    def test_a_plain_brick_breaks_and_the_last_one_clears_the_board(self):
        run = M.Run(board(bricks=[brick(0), brick(2)]))
        ball = strike(run, run.bricks[0])
        self.assertEqual(run.left(), 1)
        self.assertGreater(ball.v[2], 0)             # it came back
        strike(run, run.bricks[0])
        self.assertEqual(run.result, (True, 'Cleared'))

    def test_a_tough_brick_takes_its_hits(self):
        run = M.Run(board(bricks=[brick(kind=M.TOUGH, hits=3), brick(2)]))
        for left in (2, 1):
            strike(run, run.bricks[0])
            self.assertEqual(run.bricks[0].hits, left)
        strike(run, run.bricks[0])
        self.assertEqual(run.left(), 1)

    def test_steel_never_breaks_and_need_not(self):
        run = M.Run(board(bricks=[brick(kind=M.STEEL), brick(2)]))
        for _k in range(3):
            strike(run, run.bricks[0])
        self.assertEqual(len(run.bricks), 2)
        strike(run, run.bricks[1])
        self.assertEqual(run.result[0], True)

    def test_a_mine_costs_a_life(self):
        run = M.Run(board(bricks=[brick(kind=M.MINE), brick(2)]))
        strike(run, run.bricks[0])
        self.assertEqual(run.lives, run.level.lives - 1)
        self.assertEqual(len(run.bricks), 1)
        self.assertIsNone(run.result)

    def test_numbered_bricks_break_only_in_order(self):
        run = M.Run(board(bricks=[brick(0, order=1), brick(2, order=0)]))
        strike(run, run.bricks[0])
        self.assertEqual(run.left(), 2)              # not its turn
        strike(run, run.bricks[1])
        self.assertEqual(run.left(), 1)
        strike(run, run.bricks[0])
        self.assertEqual(run.result[0], True)

    def test_a_coloured_brick_wants_a_ball_of_its_colour(self):
        run = M.Run(board(13, bricks=[brick(0, colour=2), brick(2)]))
        strike(run, run.bricks[0], colour=1)
        self.assertEqual(run.left(), 2)
        strike(run, run.bricks[0], colour=2)
        self.assertEqual(run.left(), 1)

    def test_the_ball_takes_the_paddle_s_colour(self):
        run = M.Run(board(13, bricks=[brick()]))
        run.press(M.COLOUR)
        self.assertEqual(run.colour, 2)
        ball = shot(run, (0.0, 0.0, -0.5), (0.0, 0.0, 1.5))
        ball.colour = 1
        fly(run, 0.5)
        self.assertEqual(ball.colour, 2)
        run.press(M.COLOUR)
        self.assertEqual(run.colour, 1)              # two colours here
        plain = M.Run(board(1, bricks=[brick()]))
        plain.press(M.COLOUR)
        self.assertEqual(plain.colour, 1)

    def test_a_bomb_takes_its_neighbours_and_mines_safely(self):
        run = M.Run(board(13, bricks=[
            brick(1, 1, kind=M.BOMB), brick(0, 1, kind=M.MINE),
            brick(2, 1), brick(1, 0, kind=M.STEEL), brick(3, 2)]))
        strike(run, run.bricks[0])
        self.assertEqual(run.lives, run.level.lives)
        self.assertEqual(sorted(b.kind for b in run.bricks),
                         [M.PLAIN, M.STEEL])
        self.assertEqual(run.bricks[-1].i, 3)        # out of reach


class TheDeal(unittest.TestCase):

    def test_the_ladder_grows(self):
        self.assertEqual(M.grade(1).mines, 0)
        self.assertGreater(M.grade(7).mines, 0)
        self.assertGreater(M.grade(10).order, 0)
        self.assertGreater(M.grade(13).colours, 0)
        self.assertGreater(M.grade(13).bombs, 0)
        self.assertTrue(M.grade(16).gravity)
        self.assertGreater(M.grade(16).slide, 0)
        self.assertGreater(M.grade(19).wind, 0)
        self.assertEqual(M.grade(22).balls, 2)
        self.assertGreater(M.grade(30).speed, M.grade(1).speed * 1.8)
        self.assertLess(M.grade(30).paddle[0], M.grade(1).paddle[0])

    def test_a_board_has_what_its_rung_says(self):
        for rung in (1, 5, 8, 11, 14, 17, 20, 23, 40):
            for seed in range(25):
                b = M.deal(rung, seed=seed)
                lv = b.level
                kinds = [x.kind for x in b.bricks]
                self.assertEqual(sum(M.must(x) for x in b.bricks), lv.bricks)
                self.assertEqual(kinds.count(M.MINE), lv.mines)
                self.assertEqual(kinds.count(M.STEEL), lv.steel)
                self.assertEqual(kinds.count(M.BOMB), lv.bombs)
                self.assertEqual(len({(x.i, x.j, x.k) for x in b.bricks}),
                                 len(b.bricks))
                for x in b.bricks:
                    self.assertTrue(0 <= x.i < lv.across and 0 <= x.j < lv.up
                                    and 0 <= x.k < lv.layers)
                    self.assertLessEqual(x.colour, lv.colours)

    def test_nothing_that_must_go_is_shut_in(self):
        for rung in (11, 14, 20, 30):
            for seed in range(40):
                b = M.deal(rung, seed=seed)
                at = {(x.i, x.j, x.k): x for x in b.bricks}
                for x in b.bricks:
                    if not M.must(x):
                        continue
                    for k in range(x.k + 1, b.level.layers):
                        front = at.get((x.i, x.j, k))
                        if front is None:
                            continue
                        self.assertNotIn(front.kind, (M.MINE, M.STEEL))
                        # A numbered brick in front goes no later.
                        self.assertLessEqual(front.order, x.order)

    def test_a_seed_deals_the_same_board(self):
        self.assertEqual(M.deal(14, seed=3), M.deal(14, seed=3))
        self.assertNotEqual(M.deal(14, seed=3).bricks,
                            M.deal(14, seed=4).bricks)

    def test_the_sliding_wall_stays_in_the_box(self):
        run = M.Run(M.deal(17, seed=2))
        for k in range(200):
            for b in run.bricks:
                c, h = run.box(b, t=k * 0.05)
                self.assertLessEqual(abs(c[0]) + h[0], M.WIDE + 1e-9)


class ThePilot(unittest.TestCase):

    def wins(self, rung, n, pilot=M.autopilot):
        return sum(M.play(M.deal(rung, seed=s), pilot).result[0]
                   for s in range(n))

    def test_it_clears_the_lower_rungs(self):
        for rung in (1, 4, 7, 10):
            self.assertGreaterEqual(self.wins(rung, 12), 11, rung)

    def test_the_top_is_hard_but_not_closed(self):
        self.assertGreaterEqual(self.wins(16, 12), 8)
        top = self.wins(24, 16)
        self.assertGreaterEqual(top, 1)
        self.assertLessEqual(top, 13)

    def test_doing_nothing_is_never_paid(self):
        for rung in (1, 2, 3, 7):
            self.assertEqual(self.wins(rung, 25, lambda run: []), 0, rung)

    def test_flailing_seldom_is(self):
        rng = random.Random(2)
        for rung, most in ((1, 6), (4, 1), (10, 0)):
            wins = self.wins(rung, 40,
                             lambda run: [rng.randrange(M.PORTS)])
            self.assertLessEqual(wins, most, rung)

    def test_mines_punish_a_paddle_that_never_tilts(self):
        def follow(run):
            ball = run.balls[0]
            ex, ey = ball.p[0] - run.px, ball.p[1] - run.py
            return [M._way(ex, ey)] if abs(ex) + abs(ey) > 0.05 else \
                ([] if run.touched else [M.LEVEL])
        self.assertLess(self.wins(19, 20, follow),
                        self.wins(19, 20) - 4)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_pilot_clears_a_board_through_the_ports(self):
        for rung, seed in ((1, 3), (8, 3)):
            pilot = queued(M.autopilot, lambda task: task.run)
            self.assertEqual(drive('brick_breaker_3d', rung, pilot,
                                   seed=seed, steps=9000), [1.0], rung)

    def test_idle_fails_when_the_time_is_up(self):
        self.assertEqual(drive('brick_breaker_3d', 1, lambda task: None,
                               seed=3, steps=4000), [-1.0])

    def test_the_mouse_lands_where_it_points(self):
        from neural_workshop.ui.brickbreaker import BrickBreaker
        from uisupport import close_overlays, reset_window
        close_overlays()
        task = BrickBreaker()
        try:
            self.assertTrue(task.stage.ok, task.stage.trouble)
            task.rng = random.Random(2)
            task.start_rung = 20
            task.total_trials = 1
            task.adaptive = False
            task.start_run()
            task.on_draw()
            for want in ((0.0, 0.0), (0.5, -0.3), (-0.6, 0.35)):
                at = task._see((want[0], want[1], 0.0))
                task.on_mouse_motion(at[0], at[1], 0, 0)
                self.assertAlmostEqual(task.run.aim[0], want[0], places=3)
                self.assertAlmostEqual(task.run.aim[1], want[1], places=3)
            # Right on the screen is right in the box.
            self.assertGreater(task._see((0.5, 0.0, 0.0))[0],
                               task._see((-0.5, 0.0, 0.0))[0])
            self.assertTrue(task.run.touched)
        finally:
            task.close()
            close_overlays()
            reset_window()

    def test_the_agent_hears_the_ball(self):
        from nwenv import catalog
        env = catalog.env_class('brick_breaker_3d')(seed=1, rung=1, trials=1,
                                                    adaptive=False)
        most = 0
        try:
            for k in range(240):
                env.step(M.LEFT if k < 3 else None)
                chunk = env._public_audio
                if chunk:
                    most = max([most] + [abs(v) for v in memoryview(
                        chunk['audio_pcm']).cast('h')])
        finally:
            env.close()
        self.assertGreater(most, 500)


if __name__ == '__main__':
    unittest.main()
