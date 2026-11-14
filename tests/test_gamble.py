#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gamble: the machines, the fairness of par, the reference, the screen.

Deals are held to being fixed by their seed and to meaning what the
ladder says: a clear best machine to find, drift, bites that lose on
average, jumps, and a price that makes stopping matter. Scoring is held
to counting what pulls were worth rather than what luck paid. The
reference is held to beating random pulling and to walking away from a
table that only loses; the boundary to paying its own play through the
nine ports and refusing it past rung twenty.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import gamble as G


def random_round(dealt, seed):
    rng = random.Random(seed)
    play = G.Round(dealt)
    while not play.over:
        play.pull(rng.randrange(dealt.level.arms))
    return play


class TheLadder(unittest.TestCase):

    def test_every_rung_asks_at_least_what_the_last_did(self):
        last = G.grade(1)
        for rung in range(2, 60):
            level = G.grade(rung)
            self.assertGreaterEqual(level.arms, last.arms)
            self.assertLessEqual(level.spread, last.spread)
            self.assertGreaterEqual(level.drift, last.drift)
            self.assertGreaterEqual(level.biters, last.biters)
            self.assertGreaterEqual(level.jumps, last.jumps)
            self.assertLessEqual(level.allow, last.allow)
            last = level

    def test_the_parts_come_in_on_their_rungs(self):
        self.assertEqual(G.grade(5).drift, 0.0)
        self.assertGreater(G.grade(6).drift, 0.0)
        self.assertEqual((G.grade(9).biters, G.grade(10).biters), (0, 1))
        self.assertEqual((G.grade(13).jumps, G.grade(14).jumps), (0, 1))
        self.assertEqual((G.grade(17).price, G.grade(18).price), (0, 1))
        self.assertGreater(G.grade(18).bankroll, 0)

    def test_past_twenty_par_is_above_the_reference(self):
        self.assertGreaterEqual(G.grade(20).allow, 0.0)
        self.assertLess(G.grade(21).allow, 0.0)


class FairDeals(unittest.TestCase):

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(G.deal(14, seed=3), G.deal(14, seed=3))

    def test_a_pull_pays_by_its_number_not_by_what_came_before(self):
        dealt = G.deal(8, seed=1)
        one, other = G.Round(dealt), G.Round(dealt)
        one.pull(0)
        other.pull(1)
        self.assertEqual(one.pull(1), other.pull(1))

    def test_one_machine_is_best_at_the_start(self):
        for seed in range(20):
            dealt = G.deal(4, seed=seed)
            worths = sorted(G.worth(dealt, 0, a)
                            for a in range(dealt.level.arms))
            self.assertGreater(worths[-1], worths[-2], seed)

    def test_a_biter_wins_more_often_and_pays_less(self):
        for seed in range(20):
            dealt = G.deal(12, seed=seed)
            biters = [a for a, m in enumerate(dealt.machines)
                      if m.bite_rate]
            self.assertEqual(len(biters), 1)
            a = biters[0]
            best = max(range(dealt.level.arms),
                       key=lambda b: G.worth(dealt, 0, b))
            self.assertNotEqual(a, best, seed)
            self.assertGreater(dealt.odds[0][a],
                               max(dealt.odds[0][b] for b in
                                   range(dealt.level.arms) if b != a)
                               - 1e-9, seed)

    def test_the_odds_drift_from_rung_six(self):
        dealt = G.deal(8, seed=0)
        self.assertNotEqual(dealt.odds[0], dealt.odds[-1])
        steady = G.deal(4, seed=0)
        self.assertEqual(steady.odds[0], steady.odds[-1])

    def test_the_score_is_what_pulls_were_worth(self):
        dealt = G.deal(6, seed=2)
        play = G.Round(dealt)
        play.pull(0)
        play.pull(1)
        self.assertAlmostEqual(play.value, G.worth(dealt, 0, 0)
                               + G.worth(dealt, 1, 1))

    def test_stop_ends_the_round_only_where_pulls_cost(self):
        free = G.Round(G.deal(10, seed=0))
        self.assertFalse(free.stop())
        paid = G.Round(G.deal(18, seed=0))
        self.assertTrue(paid.stop())
        self.assertTrue(paid.over)
        self.assertIsNone(paid.pull(0))

    def test_running_the_bankroll_dry_is_bust(self):
        dealt = G.deal(18, seed=0)
        worst = min(range(dealt.level.arms),
                    key=lambda a: G.worth(dealt, 0, a))
        play = G.Round(dealt)
        play.history = [(worst, -1)] * dealt.level.bankroll
        self.assertTrue(play.bust)
        self.assertTrue(play.over)


class TheReference(unittest.TestCase):

    def test_it_beats_pulling_at_random(self):
        for rung in (3, 8, 12, 16):
            ahead = 0.0
            for seed in range(20):
                dealt = G.deal(rung, seed=seed)
                ahead += (G.reference_round(dealt).value
                          - random_round(dealt, seed).value)
            self.assertGreater(ahead / 20, 1.0, rung)

    def test_it_walks_away_from_a_table_that_only_loses(self):
        dealt = G.deal(18, seed=0)
        hopeless = dealt._replace(odds=tuple(
            tuple(0.0 for _a in row) for row in dealt.odds))
        play = G.reference_round(hopeless)
        self.assertTrue(play.stopped)
        self.assertLess(play.t, dealt.level.pulls // 2)

    def test_random_play_rarely_reaches_par(self):
        for rung in (6, 14, 20):
            passed = 0
            for seed in range(30):
                dealt = G.deal(rung, seed=seed)
                play = random_round(dealt, seed)
                passed += (not play.bust
                           and play.value >= G.par(dealt) - 1e-9)
            self.assertLessEqual(passed, 15, rung)

    def test_par_gives_ground_below_twenty_and_takes_it_after(self):
        dealt = G.deal(8, seed=1)
        self.assertLess(G.par(dealt), G.reference_round(dealt).value)
        dealt = G.deal(24, seed=1)
        self.assertGreater(G.par(dealt), G.reference_round(dealt).value)


def reference_ports(task, memory):
    """The reference's next pull, through the ports."""
    from nwenv.gamble import STOP
    play = task.round
    if memory.get('round') is not play:
        memory.update(round=play, seen=0, belief=G.Belief(play.deal),
                      rng=random.Random(play.deal.seed))
    belief = memory['belief']
    while memory['seen'] < len(play.history):
        belief.saw(*play.history[memory['seen']])
        memory['seen'] += 1
    arm = G.reference_move(belief, memory['rng'])
    return STOP if arm is None else arm


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, seed=0, policy=reference_ports):
        from nwenv import catalog
        env = catalog.env_class('gamble')(seed=seed, rung=rung, trials=1,
                                          adaptive=False)
        memory, scalars = {}, []
        try:
            for _step in range(4000):
                task = env.task
                port = (policy(task, memory)
                        if task.phase == 'pulling' else None)
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_the_reference_s_play_passes(self):
        self.assertEqual(self.drive(4), [1.0])

    def test_and_where_the_odds_move(self):
        self.assertEqual(self.drive(15), [1.0])

    def test_past_twenty_matching_the_reference_is_not_enough(self):
        self.assertEqual(self.drive(24), [-1.0])

    def test_pulling_the_worst_machine_is_a_loss(self):
        def worst(task, _memory):
            dealt = task.round.deal
            return min(range(dealt.level.arms),
                       key=lambda a: G.worth(dealt, task.round.t, a))

        self.assertEqual(self.drive(8, policy=worst), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.gamble import Gamble
        close_overlays()
        self.task = Gamble()
        self.task.rng = random.Random(7)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def test_a_click_on_a_machine_pulls_it(self):
        from pyglet.window import mouse
        self.task.start_run()
        x, y, w, h, _action = self.task.hits[1]
        self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                 mouse.LEFT, 0)
        self.assertEqual(self.task.round.history[0][0], 1)
        self.task.on_draw()

    def test_keys_pull_and_stop(self):
        from pyglet.window import key
        self.task.start_rung = 18
        self.task.start_run()
        self.task.on_key_press(key._2, 0)
        self.assertEqual(self.task.round.history[0][0], 1)
        self.task.on_key_press(key.S, 0)
        self.assertEqual(self.task.phase, 'judged')
        self.task.on_draw()

    def test_the_best_pulls_are_green_and_climb(self):
        self.task.start_rung = 3
        self.task.start_run()
        while self.task.phase == 'pulling':
            play = self.task.round
            dealt = play.deal
            self.task.pull(max(range(dealt.level.arms),
                               key=lambda a: G.worth(dealt, play.t, a)))
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 4)
        self.task.on_draw()

    def test_a_run_ends_with_a_tally(self):
        self.task.start_run()
        for _round in range(2):
            while self.task.phase == 'pulling':
                self.task.pull(0)
            self.now = self.task.feedback_until
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['trials'], 2)

    def test_everything_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        self.task.start_rung = 22
        self.task.start_run()
        for size in ((1824, 1368), (1280, 720), (2560, 1080)):
            state.window.set_size(*size)
            display.ensure_laid_out()
            self.task.relayout()
            floor = above_the_band(from_bottom_edge(58)) - 0.5
            for x, y, w, h, _action in self.task.hits:
                self.assertGreaterEqual(y, floor, size)
            for line in (self.task.facts, self.task.footnote):
                self.assertLessEqual(line.content_width,
                                     state.window.width - 16, size)

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.gamble import Gamble
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Gamble.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_decision_making(self):
        self.assertIn('gamble', [t for t, _l in TASKS['decisions']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.gamble import Gamble
        launch_task('gamble')
        self.assertIsNotNone(Gamble.instance)
        Gamble.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.gamble_note({'GAMBLE_RUNG': 25})
        self.assertIn('bite', note)
        self.assertIn('beat the reference', note)


if __name__ == '__main__':
    unittest.main()
