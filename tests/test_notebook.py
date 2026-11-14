#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Notebook: the cards, the notebook, the boundary, the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import notebook as N


def play_out(dealt, head=False):
    play, memory = N.Round(dealt), {'head': head}
    while not play.over:
        N.act(play, N.reference_move(play, memory))
    return play


class TheLadder(unittest.TestCase):

    def test_every_rung_asks_at_least_what_the_last_did(self):
        last = N.grade(1)
        for rung in range(2, 40):
            level = N.grade(rung)
            for field in ('facts', 'hold', 'gap', 'choices', 'noise',
                          'updates'):
                self.assertGreaterEqual(getattr(level, field),
                                        getattr(last, field), field)
            if rung > 6:
                self.assertLessEqual(level.lines - level.hold,
                                     last.lines - last.hold)
            last = level

    def test_the_notebook_holds_everything_until_sixteen(self):
        for rung in range(1, 16):
            self.assertGreaterEqual(N.grade(rung).lines, N.grade(rung).hold)
        self.assertLess(N.grade(16).lines, N.grade(16).hold)
        self.assertEqual(N.grade(40).lines, 1)


class TheCards(unittest.TestCase):

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(N.deal(11, seed=3), N.deal(11, seed=3))

    def test_every_fact_is_asked_once_and_after_its_gap(self):
        for rung in (1, 4, 9, 14, 22):
            for seed in range(20):
                dealt = N.deal(rung, seed=seed)
                shown, asked = {}, []
                for at, card in enumerate(dealt.cards):
                    if card.kind in ('fact', 'update'):
                        shown[card.key] = at
                    if card.kind == 'question':
                        self.assertGreater(at - shown[card.key],
                                           dealt.level.gap)
                        asked.append(card.key)
                facts = [c.key for c in dealt.cards if c.kind == 'fact']
                self.assertEqual(sorted(asked), sorted(facts))
                self.assertLessEqual(N.peak(dealt), dealt.level.hold)

    def test_the_right_answer_is_the_latest_code(self):
        for seed in range(30):
            dealt = N.deal(14, seed=seed)
            latest = {}
            for card in dealt.cards:
                if card.kind in ('fact', 'update'):
                    latest[card.key] = card.code
                if card.kind == 'question':
                    self.assertEqual(card.offered[card.answer],
                                     latest[card.key])
                    self.assertEqual(len(set(card.offered)),
                                     dealt.level.choices)

    def test_an_updated_code_offers_the_stale_one(self):
        seen = 0
        for seed in range(30):
            dealt = N.deal(12, seed=seed)
            codes = {}
            for card in dealt.cards:
                if card.kind in ('fact', 'update'):
                    codes.setdefault(card.key, []).append(card.code)
                if card.kind == 'question' and len(codes[card.key]) > 1:
                    self.assertIn(codes[card.key][0], card.offered)
                    seen += 1
        self.assertGreater(seen, 10)

    def test_noise_is_never_asked_about(self):
        dealt = N.deal(20, seed=1)
        noise = {c.key for c in dealt.cards if c.kind == 'noise'}
        asked = {c.key for c in dealt.cards if c.kind == 'question'}
        self.assertTrue(noise)
        self.assertFalse(noise & asked)

    def test_writing_and_moving_on(self):
        dealt = N.deal(4, seed=2)
        play = N.Round(dealt)
        first = play.card
        self.assertTrue(play.write(0))
        self.assertEqual(play.lines[0], first.note())
        self.assertFalse(play.answer(0))     # not a question
        self.assertTrue(play.next())
        self.assertFalse(play.write(99))


class TheReference(unittest.TestCase):

    def test_the_notebook_alone_is_enough_up_to_fifteen(self):
        for rung in (1, 5, 9, 15):
            for seed in range(15):
                dealt = N.deal(rung, seed=seed)
                self.assertEqual(play_out(dealt).right, dealt.questions,
                                 (rung, seed))

    def test_past_it_the_notebook_alone_is_not(self):
        fails = sum(play_out(N.deal(22, seed=s)).right
                    < N.deal(22, seed=s).questions for s in range(15))
        self.assertGreater(fails, 12)

    def test_with_a_head_as_well_it_is(self):
        for seed in range(10):
            dealt = N.deal(26, seed=seed)
            self.assertEqual(play_out(dealt, head=True).right,
                             dealt.questions)

    def test_guessing_fails(self):
        rng = random.Random(0)
        passes = 0
        for seed in range(40):
            dealt = N.deal(8, seed=seed)
            play = N.Round(dealt)
            while not play.over:
                if play.card.kind == 'question':
                    play.answer(rng.randrange(dealt.level.choices))
                else:
                    play.next()
            passes += play.right == dealt.questions
        self.assertEqual(passes, 0)


def reference_ports(task, memory):
    from nwenv.notebook import NEXT, WRITE
    kind, at = N.reference_move(task.round, memory)
    return at if kind == 'answer' else WRITE + at if kind == 'write' \
        else NEXT


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, policy, seed=0):
        from nwenv import catalog
        env = catalog.env_class('notebook')(seed=seed, rung=rung, trials=1,
                                            adaptive=False)
        memory, scalars = {}, []
        try:
            for _step in range(500):
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

    def test_a_careful_keeper_passes(self):
        self.assertEqual(self.drive(10, reference_ports), [1.0])

    def test_never_writing_fails(self):
        from nwenv.notebook import NEXT

        def lazy(task, _memory):
            return 0 if task.round.card.kind == 'question' else NEXT
        self.assertEqual(self.drive(10, lazy), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.notebook import Notebook
        close_overlays()
        self.task = Notebook()
        self.task.rng = random.Random(4)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def click(self, hit):
        from pyglet.window import mouse
        x, y, w, h, _action = hit
        self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                 mouse.LEFT, 0)

    def test_write_buttons_copy_the_card_and_next_moves_on(self):
        self.task.start_rung = 6
        self.task.start_run()
        card = self.task.round.card
        writes = self.task.hits[1:]
        self.click(writes[1])
        self.assertEqual(self.task.round.lines[1], card.note())
        self.click(self.task.hits[0])               # Next
        self.assertEqual(self.task.round.at, 1)
        self.task.on_draw()

    def test_keys_write_answer_and_move_on(self):
        from pyglet.window import key
        self.task.start_rung = 3
        self.task.start_run()
        card = self.task.round.card
        self.task.on_key_press(key._2, key.MOD_SHIFT)
        self.assertEqual(self.task.round.lines[1], card.note())
        self.task.on_key_press(key.RETURN, 0)
        self.assertEqual(self.task.round.at, 1)

    def test_the_keeper_is_green_and_climbs(self):
        self.task.start_rung = 7
        self.task.start_run()
        memory = {}
        while self.task.phase == 'playing':
            self.task.steer(reference_ports(self.task, memory))
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 8)
        self.task.on_draw()

    def test_everything_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        self.task.start_rung = 14
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
        from neural_workshop.ui.notebook import Notebook
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Notebook.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_long_term_memory(self):
        self.assertIn('notebook', [t for t, _l in TASKS['long_term_memory']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.notebook import Notebook
        launch_task('notebook')
        self.assertIsNotNone(Notebook.instance)
        Notebook.instance.close()

    def test_the_options_note_says_when_the_head_is_needed(self):
        note = taskoptions.notebook_note({'NOTEBOOK_RUNG': 20})
        self.assertIn('head', note)


if __name__ == '__main__':
    unittest.main()
