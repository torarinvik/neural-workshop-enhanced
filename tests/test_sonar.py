#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sonar: the ladder, the fairness of par, the reference, and the screen.

Par is only meaningful if the reference plays the deal the player
plays, so the first thing held here is that noise and drift are fixed
by action number and not by which action was taken. The reference is
held to never ruling out the truth and to finding the target on every
rung. And the boundary is held to paying the reference's own play
through the six ports below rung twenty, and refusing it above, where
par asks for better than the reference.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import sonar as S


class TheLadder(unittest.TestCase):

    def test_every_decision_only_gets_harder(self):
        last = S.grade(1)
        for rung in range(2, 120):
            level = S.grade(rung)
            self.assertGreaterEqual(level.side, last.side)
            self.assertGreaterEqual(level.noise, last.noise)
            self.assertGreaterEqual(level.drift, last.drift)
            self.assertGreaterEqual(level.penalty, last.penalty)
            self.assertLessEqual(level.slack, last.slack)
            last = level

    def test_the_decisions_arrive_one_at_a_time(self):
        self.assertEqual((S.grade(4).noise, S.grade(4).drift), (0.0, 0.0))
        self.assertGreater(S.grade(5).noise, 0.0)
        self.assertEqual(S.grade(7).drift, 0.0)
        self.assertGreater(S.grade(8).drift, 0.0)

    def test_past_twenty_par_is_below_the_reference(self):
        self.assertGreaterEqual(S.grade(20).slack, 0.0)
        self.assertLess(S.grade(21).slack, 0.0)
        self.assertLess(S.grade(60).slack, S.grade(30).slack)


class FairDeals(unittest.TestCase):

    def test_noise_and_drift_follow_the_action_count_not_the_action(self):
        dealt = S.deal(12, seed=3)
        one, two = S.Round(dealt), S.Round(dealt)
        for _step in range(6):
            one.ping((0, 0))
            two.dig((5, 5)) if two.target != (5, 5) else two.ping((1, 1))
        self.assertEqual(one.target, two.target)
        self.assertEqual(one.actions, two.actions)

    def test_a_reading_is_off_by_at_most_one_band(self):
        dealt = S.deal(12, seed=4)
        play = S.Round(dealt)
        for _step in range(40):
            cell = (random.randrange(dealt.level.side),
                    random.randrange(dealt.level.side))
            true = S.band(dealt.level, S.chebyshev(cell, play.target))
            reading = play.ping(cell)
            if reading is None:
                break
            self.assertLessEqual(abs(reading - true), 1)

    def test_likelihoods_are_distributions(self):
        for rung in (1, 5, 9, 15):
            level = S.grade(rung)
            for true in range(level.bands):
                total = sum(S.likelihood(level, reading, true)
                            for reading in range(level.bands))
                self.assertAlmostEqual(total, 1.0, msg=(rung, true))

    def test_costs_are_pings_and_penalties(self):
        dealt = S.deal(6, seed=1)
        play = S.Round(dealt)
        play.ping((0, 0))
        wrong = next(c for c in ((0, 0), (1, 0)) if c != play.target)
        play.dig(wrong)
        self.assertEqual(play.cost, S.PING + dealt.level.penalty)
        self.assertEqual(play.log, ['ping', 'dig'])

    def test_the_budget_ends_a_round(self):
        dealt = S.deal(1, seed=0)
        play = S.Round(dealt)
        while not play.over:
            play.ping((0, 0))
        self.assertFalse(play.found)
        self.assertEqual(play.actions, dealt.budget)


class TheReference(unittest.TestCase):

    def test_it_never_rules_out_the_truth(self):
        for rung in (1, 5, 8, 12, 16):
            for seed in range(3):
                dealt = S.deal(rung, seed=seed)
                play, belief = S.Round(dealt), S.Belief(dealt.level)
                rng = random.Random(0)
                while not play.over:
                    self.assertGreater(belief.p.get(play.target, 0.0), 0.0,
                                       (rung, seed, play.actions))
                    kind, cell = S.reference_move(belief, rng)
                    if kind == 'dig':
                        if not play.dig(cell):
                            belief.missed(cell)
                    else:
                        belief.heard(cell, play.ping(cell))

    def test_it_finds_the_target_on_every_rung(self):
        for rung in (1, 3, 5, 7, 8, 10, 13, 16, 20):
            for seed in range(3):
                cost, found = S.reference_cost(S.deal(rung, seed=seed))
                self.assertTrue(found, (rung, seed))

    def test_it_asks_rather_than_guesses_when_guessing_is_dear(self):
        cost, found = S.reference_cost(S.deal(3, seed=0))
        self.assertTrue(found)
        self.assertLess(cost, 10)


def reference_ports(task, state_):
    """The reference's own play, steered through the six ports."""
    from nwenv.sonar import DIG, PING
    play = task.round
    if state_.get('round') is not play:
        state_.update(round=play, belief=S.Belief(play.level),
                      rng=random.Random(0), seen=0, plan=None)
    belief = state_['belief']
    # Fold in whatever the last action told us.
    while state_['seen'] < len(play.log):
        index = state_['seen']
        kind = play.log[index]
        cell = state_['plan'][1]
        if kind == 'ping':
            belief.heard(cell, play.pings[-1][1])
        else:
            belief.missed(cell)
        state_['seen'] += 1
        state_['plan'] = None
    if state_['plan'] is None:
        state_['plan'] = S.reference_move(belief, state_['rng'])
    kind, (x, y) = state_['plan']
    ax, ay = task.at
    if ay > y:
        return 0
    if ay < y:
        return 1
    if ax > x:
        return 2
    if ax < x:
        return 3
    return DIG if kind == 'dig' else PING


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, seed=0, steps=20000):
        from nwenv import catalog
        env = catalog.env_class('sonar')(seed=seed, rung=rung, trials=1,
                                         adaptive=False)
        memory, scalars = {}, []
        try:
            for _step in range(steps):
                task = env.task
                port = (reference_ports(task, memory)
                        if task.phase == 'searching' else None)
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_the_reference_s_own_play_passes_on_a_still_target(self):
        self.assertEqual(self.drive(3), [1.0])

    def test_and_with_noise_and_drift(self):
        self.assertEqual(self.drive(10), [1.0])

    def test_past_twenty_matching_the_reference_is_not_enough(self):
        self.assertEqual(self.drive(22), [-1.0])

    def test_digging_blind_is_a_paid_miss(self):
        from nwenv import catalog
        from nwenv.sonar import DIG
        env = catalog.env_class('sonar')(seed=0, rung=6, trials=1)
        scalars = []
        try:
            for step in range(400):
                port = DIG if step % 2 == 0 else 3
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if scalars or done:
                    break
        finally:
            env.close()
        self.assertEqual(scalars, [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.sonar import Sonar
        close_overlays()
        self.task = Sonar()
        self.task.rng = random.Random(7)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def centre(self, cell):
        left, bottom, span = self.task._cell_rect(cell)
        return int(left + span / 2), int(bottom + span / 2)

    def test_a_click_pings_and_a_shift_click_digs(self):
        from pyglet.window import key, mouse
        self.task.start_run()
        x, y = self.centre((1, 2))
        self.task.on_mouse_press(x, y, mouse.LEFT, 0)
        self.assertEqual(self.task.round.pings[-1][0], (1, 2))
        target = self.task.round.target
        wrong = (0, 0) if target != (0, 0) else (1, 1)
        x, y = self.centre(wrong)
        self.task.on_mouse_press(x, y, mouse.LEFT, key.MOD_SHIFT)
        self.assertIn(wrong, self.task.round.misses)
        self.task.on_draw()

    def test_digging_the_target_under_par_is_green_and_climbs(self):
        self.task.start_rung = 3
        self.task.start_run()
        self.task.dig(self.task.round.target)
        self.assertEqual(self.task.phase, 'judged')
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 4)

    def test_a_run_ends_with_a_tally(self):
        self.task.start_run()
        for _round in range(2):
            self.task.dig(self.task.round.target)
            self.now = self.task.feedback_until
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['passed'], 2)

    def test_the_board_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        for size in ((1824, 1368), (1280, 720), (2560, 1080)):
            state.window.set_size(*size)
            display.ensure_laid_out()
            _left, bottom, _size = self.task._board()
            self.assertGreaterEqual(
                bottom, above_the_band(from_bottom_edge(58)) - 0.5, size)

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.sonar import Sonar
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Sonar.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_has_a_decision_making_tab(self):
        self.assertIn('sonar', [t for t, _l in TASKS['decisions']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.sonar import Sonar
        launch_task('sonar')
        self.assertIsNotNone(Sonar.instance)
        Sonar.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.sonar_note({'SONAR_RUNG': 25})
        self.assertIn('drifts', note)
        self.assertIn('beat the reference', note)


if __name__ == '__main__':
    unittest.main()
