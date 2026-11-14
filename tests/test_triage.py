#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Triage: the deals, the rules, the reference, the boundary, the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import triage as T


def random_round(dealt, seed):
    rng = random.Random(seed)
    play = T.Round(dealt)
    while not play.over:
        if play.open is None or rng.random() < 0.1:
            play.open_card(rng.randrange(len(play.rows)))
        else:
            play.swap(rng.randrange(len(play.rows[play.open]) - 1))
    return play


class TheLadder(unittest.TestCase):

    def test_every_rung_asks_at_least_what_the_last_did(self):
        last = T.grade(1)
        for rung in range(2, 50):
            level = T.grade(rung)
            self.assertGreaterEqual(level.cards, last.cards)
            self.assertGreaterEqual(level.longest, last.longest)
            self.assertLessEqual(level.tight, last.tight)
            self.assertGreaterEqual(level.traps, last.traps)
            self.assertGreaterEqual(level.hidden, last.hidden)
            last = level

    def test_the_parts_come_in_on_their_rungs(self):
        self.assertEqual((T.grade(7).traps, T.grade(8).traps),
                         (False, True))
        self.assertEqual((T.grade(11).hidden, T.grade(12).hidden),
                         (False, True))
        self.assertGreaterEqual(T.grade(1).tight, 1.0)


class FairDeals(unittest.TestCase):

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(T.deal(9, seed=4), T.deal(9, seed=4))

    def test_the_cost_is_the_fewest_swaps(self):
        """Inversions against a breadth-first search, rows of up to 5."""
        for length in range(2, 6):
            for row in itertools.permutations(range(length)):
                seen, frontier, steps = {row}, [row], 0
                while sorted(row) not in [list(r) for r in frontier]:
                    grown = []
                    for r in frontier:
                        for j in range(length - 1):
                            s = list(r)
                            s[j], s[j + 1] = s[j + 1], s[j]
                            s = tuple(s)
                            if s not in seen:
                                seen.add(s)
                                grown.append(s)
                    frontier, steps = grown, steps + 1
                self.assertEqual(T.inversions(row), steps, row)

    def test_no_row_comes_sorted_and_something_is_affordable(self):
        for rung in (1, 6, 12, 25):
            for seed in range(30):
                dealt = T.deal(rung, seed=seed)
                for card in dealt.cards:
                    self.assertGreater(card.cost, 0)
                self.assertTrue(any(dealt.price(i) <= dealt.budget
                                    for i in range(len(dealt.cards))))

    def test_at_rung_one_everything_can_be_had(self):
        for seed in range(20):
            dealt = T.deal(1, seed=seed)
            self.assertEqual(T.best(dealt),
                             sum(c.pays for c in dealt.cards))

    def test_moves_and_pay(self):
        dealt = T.deal(3, seed=1)
        play = T.Round(dealt)
        self.assertFalse(play.swap(0))          # nothing open
        play.open_card(0)
        while 0 not in play.solved:
            row = play.rows[0]
            play.swap(next(j for j in range(len(row) - 1)
                           if row[j] > row[j + 1]))
        self.assertEqual(play.used, dealt.cards[0].cost)
        self.assertEqual(play.value, dealt.cards[0].pays)
        self.assertIsNone(play.open)
        self.assertFalse(play.open_card(0))     # solved stays solved

    def test_turning_a_card_over_costs_one_move_once(self):
        dealt = T.deal(14, seed=2)
        play = T.Round(dealt)
        play.open_card(1)
        play.open_card(0)
        play.open_card(1)
        self.assertEqual(play.used, 2)

    def test_the_budget_ends_the_round(self):
        dealt = T.deal(20, seed=3)
        play = random_round(dealt, 0)
        self.assertTrue(play.over)
        self.assertLessEqual(play.used, dealt.budget)


class TheReference(unittest.TestCase):

    def test_best_is_a_true_knapsack(self):
        for seed in range(15):
            dealt = T.deal(16, seed=seed)
            top = 0
            n = len(dealt.cards)
            for mask in range(1 << n):
                picked = [i for i in range(n) if mask >> i & 1]
                if sum(dealt.price(i) for i in picked) <= dealt.budget:
                    top = max(top, sum(dealt.cards[i].pays for i in picked))
            self.assertEqual(T.best(dealt), top)

    def test_it_never_beats_best_and_beats_random_play(self):
        ahead = 0
        for seed in range(30):
            dealt = T.deal(14, seed=seed)
            ref = T.reference_round(dealt).value
            self.assertLessEqual(ref, T.best(dealt))
            ahead += ref > random_round(dealt, seed).value
        self.assertGreater(ahead, 25)

    def test_random_play_rarely_reaches_par(self):
        passes = sum(random_round(T.deal(10, seed=s), s).value
                     >= T.par(T.deal(10, seed=s)) - 1e-9 for s in range(40))
        self.assertLess(passes, 4)

    def test_par_gives_ground_below_twenty_and_takes_it_after(self):
        for seed in range(30):
            low = T.deal(6, seed=seed)
            self.assertLessEqual(T.par(low),
                                 T.reference_round(low).value)
            high = T.deal(26, seed=seed)
            ref = T.reference_round(high).value
            self.assertGreaterEqual(T.par(high), ref)
            self.assertLessEqual(T.par(high), T.best(high))


def reference_ports(task, _memory):
    from nwenv.triage import DONE, SWAP
    kind, at = T.reference_move(task.round)
    return at if kind == 'open' else SWAP + at if kind == 'swap' else DONE


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, seed=0, policy=reference_ports):
        from nwenv import catalog
        env = catalog.env_class('triage')(seed=seed, rung=rung, trials=1,
                                          adaptive=False)
        memory, scalars = {}, []
        try:
            for _step in range(3000):
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
        self.assertEqual(self.drive(4), [1.0])

    def test_and_with_cards_face_down(self):
        self.assertEqual(self.drive(14), [1.0])

    def test_giving_up_at_once_is_a_loss(self):
        from nwenv.triage import DONE
        self.assertEqual(self.drive(3, policy=lambda t, m: DONE), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.triage import Triage
        close_overlays()
        self.task = Triage()
        self.task.rng = random.Random(7)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def click(self, index):
        from pyglet.window import mouse
        x, y, w, h, _action = self.task.hits[index]
        self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                 mouse.LEFT, 0)

    def test_clicks_open_a_card_and_swap(self):
        self.task.start_rung = 5
        self.task.start_run()
        self.click(1)
        self.assertEqual(self.task.round.open, 1)
        before = list(self.task.round.rows[1])
        swaps = [h for h in self.task.hits if h[2] < h[3]]   # narrow ones
        x, y, w, h, action = swaps[0]
        action()
        self.assertEqual(self.task.round.rows[1][:2], before[1::-1])
        self.task.on_draw()

    def test_keys_open_and_finish(self):
        from pyglet.window import key
        self.task.start_run()
        self.task.on_key_press(key._2, 0)
        self.assertEqual(self.task.round.open, 1)
        self.task.on_key_press(key.RETURN, 0)
        self.assertEqual(self.task.phase, 'judged')
        self.assertFalse(self.task.verdict_shown[0])

    def test_the_reference_is_green_and_climbs(self):
        self.task.start_rung = 3
        self.task.start_run()
        while self.task.phase == 'playing':
            self.task.steer(reference_ports(self.task, {}))
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 4)
        self.task.on_draw()

    def test_a_run_ends_with_a_tally(self):
        self.task.start_run()
        for _round in range(2):
            self.task.done()
            self.now = self.task.feedback_until
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['trials'], 2)

    def test_everything_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        self.task.start_rung = 24
        self.task.start_run()
        self.task.open_card(0)
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
        from neural_workshop.ui.triage import Triage
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Triage.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_decision_making(self):
        self.assertIn('triage', [t for t, _l in TASKS['decisions']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.triage import Triage
        launch_task('triage')
        self.assertIsNotNone(Triage.instance)
        Triage.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.triage_note({'TRIAGE_RUNG': 25})
        self.assertIn('face-down', note)
        self.assertIn('beat the reference', note)


if __name__ == '__main__':
    unittest.main()
