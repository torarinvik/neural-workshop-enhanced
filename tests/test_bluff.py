#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Bluff: the game, the opponents, the fairness of par, the screen.

The rules are held to paying what they say. The opponents are held to
their habits -- the station calls, the rock folds, the maniac bets, the
adaptive one calls more against a bluffer -- and deals to being fixed by
their seed. Scoring is held to counting what choices were worth over
the opponent's possible cards rather than what the cards paid. The
reference is held to beating one-note and random play; the boundary to
paying its play through the two ports and refusing it past rung twenty.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import bluff as B


def one_note(dealt, choice):
    return B.play_with(dealt, lambda _m, _model: choice)


class TheLadder(unittest.TestCase):

    def test_the_opponents_come_in_order(self):
        self.assertEqual(B.grade(1).kinds, (B.STATION,))
        self.assertEqual(B.grade(3).kinds, (B.ROCK,))
        self.assertEqual(B.grade(5).kinds, (B.MANIAC,))
        self.assertIn(B.SOUND, B.grade(10).kinds)
        self.assertEqual(B.grade(14).kinds, (B.ADAPTIVE,))
        self.assertTrue(B.grade(18).changes)

    def test_the_deck_grows(self):
        self.assertEqual([B.grade(r).cards for r in (1, 7, 14, 18)],
                         [3, 5, 7, 9])

    def test_past_twenty_par_is_above_the_reference(self):
        self.assertGreaterEqual(B.grade(20).allow, 0.0)
        self.assertLess(B.grade(21).allow, 0.0)


class TheRules(unittest.TestCase):

    def hand(self, actions, player_first=True, mine=2, theirs=0):
        return B._payoff(actions, player_first, mine, theirs)

    def test_a_showdown_pays_the_higher_card(self):
        self.assertEqual(self.hand('cc'), 1)
        self.assertEqual(self.hand('bk'), 2)
        self.assertEqual(self.hand('cbk', mine=0, theirs=2), -2)

    def test_a_fold_gives_the_bettor_the_antes(self):
        self.assertEqual(self.hand('bf'), 1)
        self.assertEqual(self.hand('cbf'), -1)
        self.assertEqual(self.hand('cbf', player_first=False), 1)

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(B.deal(12, seed=3), B.deal(12, seed=3))

    def test_turns_alternate_and_the_opponent_moves_itself(self):
        match = B.Match(B.deal(1, seed=0))
        self.assertTrue(match.player_to_act())
        match.act(B.PASSIVE)
        if match.index == 1:
            self.assertFalse(match.hand.player_first)
            self.assertEqual(len(match.actions), 1)


class TheOpponents(unittest.TestCase):

    def test_the_station_calls_anything_and_the_rock_folds(self):
        station, rock = B.Habits(B.STATION), B.Habits(B.ROCK)
        self.assertEqual(station.aggression(0.0, 'b'), 1.0)
        self.assertEqual(rock.aggression(0.5, 'b'), 0.0)
        self.assertEqual(rock.aggression(1.0, 'b'), 1.0)

    def test_the_maniac_bets_most_hands(self):
        self.assertGreater(B.Habits(B.MANIAC).aggression(0.0, ''), 0.8)

    def test_the_adaptive_player_calls_a_bluffer_more(self):
        habits = B.Habits(B.ADAPTIVE)
        before = habits.aggression(0.3, 'b')
        for _hand in range(4):
            habits.notice(0, 7, True, None)
        self.assertGreater(habits.aggression(0.3, 'b'), before)

    def test_the_opponent_changes_partway_from_rung_eighteen(self):
        dealt = B.deal(19, seed=1)
        start, later = dealt.kinds[1]
        self.assertNotEqual(B.kind_at(dealt, start - 1),
                            B.kind_at(dealt, start))


class TheScore(unittest.TestCase):

    def test_worth_is_close_to_chips_over_many_hands(self):
        dealt = B.deal(8, seed=0)
        dealt = dealt._replace(hands=dealt.hands * 20)
        match = B.reference_round(dealt)
        self.assertLess(abs(match.value - match.chips),
                        0.35 * len(match.records))

    def test_the_reference_beats_one_note_and_random_play(self):
        for rung in (1, 3, 5, 8, 15):
            ahead = 0
            for seed in range(10):
                dealt = B.deal(rung, seed=seed)
                ref = B.reference_round(dealt).value
                rng = random.Random(seed)
                others = (one_note(dealt, 0).value,
                          one_note(dealt, 1).value,
                          B.play_with(dealt, lambda _m, _mo:
                                      rng.randrange(2)).value)
                ahead += all(ref > other for other in others)
            self.assertGreaterEqual(ahead, 7, rung)

    def test_par_gives_ground_below_twenty_and_takes_it_after(self):
        dealt = B.deal(8, seed=1)
        self.assertLessEqual(B.par(dealt), B.reference_round(dealt).value)
        dealt = B.deal(24, seed=1)
        self.assertGreater(B.par(dealt), B.reference_round(dealt).value)


def reference_ports(task, memory):
    match = task.match
    if memory.get('match') is not match:
        memory.update(match=match, seen=0,
                      model=B.Model(match.level.cards))
    model = memory['model']
    while memory['seen'] < len(match.records):
        model.saw(match.records[memory['seen']])
        memory['seen'] += 1
    return B.reference_move(model, match)


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, seed=0, policy=reference_ports):
        from nwenv import catalog
        env = catalog.env_class('bluff')(seed=seed, rung=rung, trials=1,
                                         adaptive=False)
        memory, scalars = {}, []
        try:
            for _step in range(4000):
                task = env.task
                port = (policy(task, memory)
                        if task.phase == 'playing' else None)
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_the_reference_s_play_passes(self):
        self.assertEqual(self.drive(3), [1.0])

    def test_and_against_the_adaptive_player(self):
        self.assertEqual(self.drive(15), [1.0])

    def test_past_twenty_matching_the_reference_is_not_enough(self):
        self.assertEqual(self.drive(24), [-1.0])

    def test_folding_everything_is_a_loss(self):
        self.assertEqual(self.drive(5, policy=lambda t, m: 0), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.bluff import Bluff
        close_overlays()
        self.task = Bluff()
        self.task.rng = random.Random(7)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def test_a_click_on_a_button_acts(self):
        from pyglet.window import mouse
        self.task.start_run()
        x, y, w, h, _action = self.task.hits[1]
        before = (len(self.task.match.records), self.task.match.actions)
        self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                 mouse.LEFT, 0)
        self.assertNotEqual((len(self.task.match.records),
                             self.task.match.actions), before)
        self.task.on_draw()

    def test_keys_act(self):
        from pyglet.window import key
        self.task.start_run()
        for _press in range(6):
            self.task.on_key_press(key.B, 0)
        self.assertGreaterEqual(len(self.task.match.records), 2)
        self.task.on_draw()

    def test_a_run_ends_with_a_tally(self):
        self.task.start_run()
        for _round in range(2):
            while self.task.phase == 'playing':
                self.task.act(B.AGGRESSIVE)
            self.now = self.task.feedback_until
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['trials'], 2)

    def test_everything_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        self.task.start_rung = 19
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
        from neural_workshop.ui.bluff import Bluff
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Bluff.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_decision_making(self):
        self.assertIn('bluff', [t for t, _l in TASKS['decisions']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.bluff import Bluff
        launch_task('bluff')
        self.assertIsNotNone(Bluff.instance)
        Bluff.instance.close()

    def test_the_options_note_names_the_opponent(self):
        note = taskoptions.bluff_note({'BLUFF_RUNG': 25})
        self.assertIn('changes', note)
        self.assertIn('beat the reference', note)


if __name__ == '__main__':
    unittest.main()
