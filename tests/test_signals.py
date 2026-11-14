#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Signals: the games, the partner, the reference, the boundary, the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import signals as S


class TheLadder(unittest.TestCase):

    def test_the_parts_come_in_on_their_rungs(self):
        self.assertEqual(S.grade(3).roles, 'listen')
        self.assertEqual(S.grade(4).roles, 'speak')
        self.assertEqual(S.grade(8).roles, 'both')
        self.assertFalse(S.grade(7).shapes)
        self.assertTrue(S.grade(8).shapes)
        self.assertEqual((S.grade(11).length, S.grade(12).length), (1, 2))
        self.assertEqual((S.grade(15).swaps, S.grade(16).swaps,
                          S.grade(20).swaps), (0, 2, 3))
        self.assertLess(S.grade(25).exchanges, S.grade(20).exchanges)


class TheGames(unittest.TestCase):

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(S.deal(14, seed=3), S.deal(14, seed=3))

    def test_the_code_is_a_one_to_one_naming(self):
        for rung in (2, 9, 17):
            dealt = S.deal(rung, seed=1)
            named = [v for v in dealt.meaning if v is not None]
            self.assertEqual(len(named), len(set(named)))
            changed = [v for v in dealt.changed if v is not None]
            self.assertEqual(sorted(named), sorted(changed))

    def test_the_code_changes_only_where_it_should(self):
        self.assertEqual(S.deal(12, seed=2).meaning,
                         S.deal(12, seed=2).changed)
        dealt = S.deal(18, seed=2)
        moved = sum(a != b for a, b in zip(dealt.meaning, dealt.changed))
        self.assertEqual(moved, 2)
        self.assertLess(dealt.change_at, len(dealt.exchanges))

    def test_every_scene_can_be_said(self):
        """One glyph picks the target out from rung 8; two are needed,
        and enough, from rung 12."""
        for rung, length in ((9, 1), (14, 2)):
            for seed in range(20):
                dealt = S.deal(rung, seed=seed)
                for at, ex in enumerate(dealt.exchanges):
                    signal = S.partner_says(dealt, at)
                    self.assertEqual(len(signal), length)
                    code = dealt.code(at)
                    fits = [i for i, t in enumerate(ex.objects)
                            if all(S.value_of(t, code[g]) for g in signal)]
                    self.assertEqual(fits, [ex.target])
                    if length == 2:
                        for g in signal:
                            alone = [i for i, t in enumerate(ex.objects)
                                     if S.value_of(t, code[g])]
                            self.assertGreater(len(alone), 1)

    def test_a_partner_reads_a_good_signal_right(self):
        dealt = S.deal(10, seed=4)
        for at, ex in enumerate(dealt.exchanges):
            self.assertEqual(S.partner_picks(dealt, at,
                                             S.partner_says(dealt, at)),
                             ex.target)

    def test_turns_and_scoring(self):
        dealt = S.deal(9, seed=5)
        game = S.Game(dealt)
        self.assertEqual(game.exchange.role, 'partner')
        self.assertIsNone(game.say(0))            # not the player's turn
        game.pick(game.exchange.target)
        self.assertEqual(game.score, 1)
        self.assertEqual(game.exchange.role, 'player')
        self.assertIsNone(game.pick(0))


class TheReference(unittest.TestCase):

    def test_it_learns_well_beyond_guessing(self):
        for rung in (3, 7, 11, 15, 18):
            ahead = 0
            for seed in range(12):
                dealt = S.deal(rung, seed=seed)
                ahead += S.reference_game(dealt).score > S.guessing(dealt)
            self.assertGreaterEqual(ahead, 10, rung)

    def test_par_gives_ground_below_twenty_and_takes_it_after(self):
        for seed in range(10):
            low = S.deal(9, seed=seed)
            self.assertLessEqual(S.par(low), S.reference_game(low).score)
            high = S.deal(26, seed=seed)
            self.assertGreaterEqual(S.par(high),
                                    S.reference_game(high).score)


def reference_ports(task, memory):
    from nwenv.signals import GLYPH
    game = task.game
    if memory.get('game') is not game:
        memory.update(game=game, learner=S.Learner(game.deal), seen=0,
                      plan=[])
    learner = memory['learner']
    while memory['seen'] < len(game.history):
        learner.saw(*game.history[memory['seen']][:3])
        memory['seen'] += 1
    ex = game.exchange
    if ex.role == 'partner':
        return learner.listen(ex, game.heard())
    if not memory['plan']:
        memory['plan'] = list(learner.speak(ex))
    return GLYPH + memory['plan'].pop(0)


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, policy, seed=0):
        from nwenv import catalog
        env = catalog.env_class('signals')(seed=seed, rung=rung, trials=1,
                                           adaptive=False)
        memory, scalars = {}, []
        try:
            for _step in range(200):
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

    def test_the_reference_passes_listening(self):
        self.assertEqual(self.drive(2, reference_ports), [1.0])

    def test_and_taking_turns_with_two_glyphs(self):
        self.assertEqual(self.drive(13, reference_ports), [1.0])

    def test_always_the_first_object_fails(self):
        def lazy(task, _memory):
            return 0
        self.assertEqual(self.drive(3, lazy), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.signals import Signals
        close_overlays()
        self.task = Signals()
        self.task.rng = random.Random(3)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def test_clicks_pick_and_glyph_keys_speak(self):
        from pyglet.window import key, mouse
        self.task.start_rung = 9
        self.task.start_run()
        ex = self.task.game.exchange
        self.assertEqual(ex.role, 'partner')
        x, y, w, h, _a = self.task.hits[ex.target]
        self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                 mouse.LEFT, 0)
        self.assertEqual(self.task.game.score, 1)
        self.assertEqual(self.task.game.exchange.role, 'player')
        self.task.on_key_press(key.Q, 0)
        self.assertEqual(self.task.game.at, 2)
        self.task.on_draw()

    def test_two_glyph_signals_wait_for_the_second(self):
        self.task.start_rung = 13
        self.task.start_run()
        self.task.pick(0)
        self.task.say(1)
        self.assertEqual(self.task.game.drafted, [1])
        self.task.on_draw()
        self.task.say(2)
        self.assertEqual(self.task.game.at, 2)

    def test_the_reference_is_green_and_climbs(self):
        self.task.start_rung = 10
        self.task.start_run()
        memory = {}
        while self.task.phase == 'playing':
            self.task.steer(reference_ports(self.task, memory))
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 11)
        self.task.on_draw()

    def test_everything_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        self.task.start_rung = 24
        self.task.start_run()
        for _n in range(7):
            self.task.steer(0 if self.task.game.exchange.role == 'partner'
                            else 8)
        for size in ((1824, 1368), (1280, 720), (2560, 1080)):
            state.window.set_size(*size)
            display.ensure_laid_out()
            self.task.relayout()
            floor = above_the_band(from_bottom_edge(58)) - 0.5
            for x, y, w, h, _action in self.task.hits:
                self.assertGreaterEqual(y, floor, size)
            for line in (self.task.facts, self.task.footnote,
                         self.task.status):
                self.assertLessEqual(line.content_width,
                                     state.window.width - 16, size)

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.signals import Signals
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Signals.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_reasoning(self):
        self.assertIn('signals', [t for t, _l in TASKS['reasoning']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.signals import Signals
        launch_task('signals')
        self.assertIsNotNone(Signals.instance)
        Signals.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.signals_note({'SIGNALS_RUNG': 17})
        self.assertIn('changes its code', note)


if __name__ == '__main__':
    unittest.main()
