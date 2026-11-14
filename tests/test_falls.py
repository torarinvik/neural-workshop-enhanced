#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Will It Fall?: the physics, the deals, the boundary, the screen.

The answers are checked against independent sums and a stepped
simulation, not against the code that dealt them.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import Counter

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import falls as F


def simulate(height, edge, speed, bounces, step=1e-4):
    """Step a ball off a table edge and return where it lands."""
    x, y, up, left = edge, height, 0.0, bounces
    while True:
        x += speed * step
        up -= F.G * step
        y += up * step
        if y <= 0:
            if left == 0:
                return x
            left -= 1
            y, up = 0.0, -up * F.BOUNCE


class TheLadder(unittest.TestCase):

    def test_every_rung_asks_at_least_what_the_last_did(self):
        last = F.grade(1)
        for rung in range(2, 40):
            level = F.grade(rung)
            self.assertTrue(set(last.kinds) <= set(level.kinds))
            self.assertGreaterEqual(level.blocks, last.blocks)
            self.assertLessEqual(level.margin, last.margin)
            self.assertGreaterEqual(level.bins, last.bins)
            self.assertLessEqual(level.dots, last.dots)
            last = level

    def test_the_kinds_come_in_on_their_rungs(self):
        self.assertEqual(F.grade(3).kinds, ('stand',))
        self.assertIn('lever', F.grade(4).kinds)
        self.assertIn('land', F.grade(8).kinds)
        self.assertIn('first', F.grade(12).kinds)
        self.assertIn('bounce', F.grade(16).kinds)


class ThePhysics(unittest.TestCase):

    def test_landing_matches_a_stepped_simulation(self):
        rng = random.Random(1)
        for _case in range(20):
            h, e, v = rng.uniform(1, 3), rng.uniform(1, 3), rng.uniform(1, 6)
            for bounces in (0, 1):
                self.assertAlmostEqual(F.landing(h, v, e, bounces),
                                       simulate(h, e, v, bounces), places=2)

    def test_a_tower_answer_agrees_with_summing_moments(self):
        for rung in (2, 9, 14, 24):
            for seed in range(30):
                puzzle = F.deal(rung, seed=seed)
                if not puzzle.blocks:
                    continue
                blocks = list(puzzle.blocks)
                topples = None
                for level in range(1, len(blocks)):
                    above = blocks[level:]
                    com = sum(b.middle * b.mass for b in above) / \
                        sum(b.mass for b in above)
                    under, me = blocks[level - 1], blocks[level]
                    lo = max(under.x, me.x)
                    hi = min(under.x + under.w, me.x + me.w)
                    if not lo < com < hi:
                        topples = level
                        break
                if puzzle.kind == 'stand':
                    self.assertEqual(puzzle.answer,
                                     0 if topples is None else 1)
                else:
                    n = len(blocks)
                    self.assertEqual(puzzle.answer, n - 1 if topples is None
                                     else topples - 1)

    def test_every_level_keeps_the_rung_s_margin(self):
        for seed in range(30):
            puzzle = F.deal(14, seed=seed)
            for level in range(1, len(puzzle.blocks)):
                self.assertGreaterEqual(
                    abs(F.lean(list(puzzle.blocks), level)),
                    F.grade(14).margin - 1e-9)

    def test_a_lever_answer_agrees_with_its_moments(self):
        for seed in range(60):
            puzzle = F.deal(12, seed=seed)
            if not puzzle.lever:
                continue
            _length, pivot, plank, piles = puzzle.lever
            moment = sum(n * (at - pivot) for at, n in piles) - plank * pivot
            self.assertEqual(puzzle.answer,
                             2 if moment == 0 else 0 if moment < 0 else 1)

    def test_a_ball_lands_inside_its_bin_by_the_margin(self):
        for rung in (9, 18, 28):
            level = F.grade(rung)
            for seed in range(40):
                puzzle = F.deal(rung, seed=seed)
                if not puzzle.flight:
                    continue
                h, e, v, lo, hi, dots, bounces = puzzle.flight
                place = (F.landing(h, v, e, bounces) - lo) / \
                    ((hi - lo) / len(puzzle.choices))
                self.assertEqual(int(place), puzzle.answer)
                self.assertGreaterEqual(min(place % 1, 1 - place % 1),
                                        level.margin - 1e-6)
                self.assertEqual(len(dots), level.dots)

    def test_answers_are_spread(self):
        for rung in (2, 5, 9):
            seen = Counter((p.kind, p.answer) for p in
                           (F.deal(rung, seed=s) for s in range(120)))
            for kind in F.grade(rung).kinds:
                answers = {a for (k, a) in seen if k == kind}
                self.assertGreater(len(answers), 1, (rung, kind))

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(F.deal(17, seed=4), F.deal(17, seed=4))


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, pick, rung=10):
        from nwenv import catalog
        env = catalog.env_class('will_it_fall')(seed=1, rung=rung, trials=1,
                                                adaptive=False)
        scalars = []
        try:
            for _step in range(50):
                task = env.task
                port = pick(task) if task.phase == 'playing' else None
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_the_right_answer_is_paid(self):
        self.assertEqual(self.drive(lambda t: t.puzzle.answer), [1.0])

    def test_a_wrong_one_is_not(self):
        self.assertEqual(self.drive(
            lambda t: (t.puzzle.answer + 1) % len(t.puzzle.choices)),
            [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.falls import WillItFall
        close_overlays()
        self.task = WillItFall()
        self.task.rng = random.Random(2)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def test_a_click_on_the_answer_is_green_and_climbs(self):
        from pyglet.window import mouse
        self.task.start_rung = 5
        self.task.start_run()
        x, y, w, h, _a = self.task.hits[self.task.puzzle.answer]
        self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                 mouse.LEFT, 0)
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 6)
        self.task.on_draw()

    def test_every_kind_draws_before_and_after(self):
        for rung in (2, 5, 9, 13, 17, 26):
            for seed in range(6):
                self.task.rung = rung
                self.task.rng = random.Random(seed)
                self.task.phase = 'ready'
                self.task._next_trial()
                self.task.on_draw()
                self.task.choose(0)
                self.task.on_draw()

    def test_keys_answer(self):
        from pyglet.window import key
        self.task.start_run()
        self.task.on_key_press(key._1 + self.task.puzzle.answer, 0)
        self.assertTrue(self.task.verdict_shown[0])

    def test_everything_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        self.task.start_rung = 24
        self.task.start_run()
        for size in ((1824, 1368), (1280, 720), (2560, 1080)):
            state.window.set_size(*size)
            display.ensure_laid_out()
            self.task.relayout()
            floor = above_the_band(from_bottom_edge(58)) - 0.5
            for x, y, w, h, _action in self.task.hits:
                self.assertGreaterEqual(y, floor, size)

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.falls import WillItFall
        self.task.start_run()
        self.task.close()
        self.assertIsNone(WillItFall.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_perception(self):
        self.assertIn('will_it_fall', [t for t, _l in TASKS['perception']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.falls import WillItFall
        launch_task('will_it_fall')
        self.assertIsNotNone(WillItFall.instance)
        WillItFall.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.will_it_fall_note({'WILL_IT_FALL_RUNG': 16})
        self.assertIn('bounce', note)


if __name__ == '__main__':
    unittest.main()
