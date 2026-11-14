#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Hidden Wiring: the wirings, the fairness of par, the reference, the screen.

The wiring space is held to holding distinct, non-constant truth tables
and to agreeing with the gates they came from. Deals are held to being
fixed by their seed, to asking questions a blind guess cannot answer
for certain, and to lies fixed by look number. The reference is held to
never ruling out the truth on an honest panel, to answering right once
it says it is ready, and to beating looks taken at random; the boundary
to paying its own play through the eleven ports and refusing it past
rung twenty.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import wiring as W


class TheLadder(unittest.TestCase):

    def test_every_rung_allows_at_least_what_the_last_did(self):
        last = W.grade(1)
        for rung in range(2, 60):
            level = W.grade(rung)
            self.assertGreaterEqual(level.switches, last.switches)
            self.assertGreaterEqual(level.lamps, last.lamps)
            self.assertTrue(set(last.gates) <= set(level.gates))
            self.assertGreaterEqual(level.noise, last.noise)
            self.assertLessEqual(level.factor, last.factor)
            self.assertGreaterEqual(len(W.space(level)),
                                    len(W.space(last)))
            last = level

    def test_the_panel_is_honest_until_rung_sixteen(self):
        self.assertEqual(W.grade(15).noise, 0.0)
        self.assertGreater(W.grade(16).noise, 0.0)
        self.assertLessEqual(W.grade(90).noise, W.NOISIEST)

    def test_it_stays_within_eight_switches(self):
        self.assertEqual(W.grade(90).switches, W.MOST_SWITCHES)


class TheWirings(unittest.TestCase):

    def test_every_wiring_is_distinct_and_not_constant(self):
        level = W.grade(14)
        tables = [bits for _gate, bits in W.space(level)]
        self.assertEqual(len(tables), len(set(tables)))
        full = (1 << (1 << level.switches)) - 1
        self.assertNotIn(0, tables)
        self.assertNotIn(full, tables)

    def test_a_table_agrees_with_its_gate(self):
        level = W.grade(14)
        for gate, bits in W.space(level)[::17]:
            for setting in range(1 << level.switches):
                self.assertEqual(bool(bits >> setting & 1),
                                 W.evaluate(gate, setting))

    def test_the_gates_mean_what_they_say(self):
        and_ = W.Gate('and', (0, 1), (False, True))
        self.assertTrue(W.evaluate(and_, 0b01))
        self.assertFalse(W.evaluate(and_, 0b11))
        majority = W.Gate('majority', (0, 1, 2), (False,) * 3)
        self.assertTrue(W.evaluate(majority, 0b101))
        self.assertFalse(W.evaluate(majority, 0b100))


class FairDeals(unittest.TestCase):

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(W.deal(14, seed=3), W.deal(14, seed=3))

    def test_every_question_can_be_made(self):
        for seed in range(10):
            dealt = W.deal(12, seed=seed)
            made = {W.lamps_for(dealt, s)
                    for s in range(1 << dealt.level.switches)}
            for pattern in dealt.exam:
                self.assertIn(pattern, made)

    def test_a_question_needs_a_look_first(self):
        for rung in (1, 4, 9, 14):
            dealt = W.deal(rung, seed=0)
            blind = W.Belief(dealt.level)
            self.assertFalse(W.ready(blind, dealt.exam), rung)

    def test_the_lamps_lie_by_look_number_not_by_setting(self):
        dealt = W.deal(22, seed=4)
        liar = next(k for k, l in enumerate(dealt.lies) if l >= 0)
        for setting in (0, 5):
            play = W.Round(dealt)
            for _k in range(liar):
                play.look(1)
            shown = play.look(setting)
            self.assertNotEqual(shown, W.lamps_for(dealt, setting))

    def test_cost_is_looks_plus_penalties(self):
        dealt = W.deal(6, seed=1)
        play = W.Round(dealt)
        play.look(0)
        play.start_exam()
        while not play.over:
            play.answer(0)
        self.assertEqual(play.cost, 1 + dealt.level.penalty * play.wrong)


class TheReference(unittest.TestCase):

    def test_on_an_honest_panel_it_never_rules_out_the_truth(self):
        dealt = W.deal(12, seed=2)
        play = W.Round(dealt)
        belief = W.Belief(dealt.level)
        rng = random.Random(0)
        truth = [W.table(g, dealt.level.switches) for g in dealt.lamps]
        for _k in range(10):
            setting = rng.randrange(1 << dealt.level.switches)
            belief.saw(setting, play.look(setting))
            for lamp, bits in enumerate(truth):
                self.assertIn(bits, belief.alive(lamp))

    def test_when_it_is_ready_its_answers_are_right(self):
        for rung in (5, 10, 14):
            for seed in range(5):
                play = W.reference_round(W.deal(rung, seed=seed))
                self.assertEqual(play.wrong, 0, (rung, seed))

    def test_it_looks_less_than_a_player_looking_at_random(self):
        for rung in (10, 14):
            ref = rnd = 0
            for seed in range(6):
                dealt = W.deal(rung, seed=seed)
                ref += len(W.reference_round(dealt).looks)
                belief = W.Belief(dealt.level)
                play = W.Round(dealt)
                rng = random.Random(seed)
                while not W.ready(belief, dealt.exam) and play.looks_left:
                    s = rng.randrange(1 << dealt.level.switches)
                    belief.saw(s, play.look(s))
                rnd += len(play.looks)
            self.assertLess(ref, rnd, rung)

    def test_par_is_its_cost_scaled_by_the_rung(self):
        dealt = W.deal(8, seed=1)
        self.assertGreater(W.par(dealt), W.reference_round(dealt).cost)
        dealt = W.deal(26, seed=1)
        self.assertLess(W.par(dealt), W.reference_round(dealt).cost)


def reference_ports(task, memory):
    """The reference's next step, through the ports."""
    from nwenv.wiring import ANSWER, EXAM, LOOK
    play = task.round
    if memory.get('round') is not play:
        memory.update(round=play, seen=0, belief=W.Belief(play.level))
    belief = memory['belief']
    while memory['seen'] < len(play.looks):
        belief.saw(*play.looks[memory['seen']])
        memory['seen'] += 1
    if task.phase == 'looking':
        target = W.reference_look(belief, play.deal.exam, play.looks_left)
        if target is None:
            return EXAM
    else:
        target = belief.best_guess(play.question)
    for i, on in enumerate(task.switches):
        if on != bool(target >> i & 1):
            return i
    return LOOK if task.phase == 'looking' else ANSWER


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, seed=0, policy=reference_ports):
        from nwenv import catalog
        env = catalog.env_class('wiring')(seed=seed, rung=rung, trials=1,
                                          adaptive=False)
        memory, scalars = {}, []
        try:
            for _step in range(4000):
                task = env.task
                port = (policy(task, memory)
                        if task.phase in ('looking', 'examining') else None)
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_the_reference_s_play_passes(self):
        self.assertEqual(self.drive(5), [1.0])

    def test_and_with_xor_gates(self):
        self.assertEqual(self.drive(10), [1.0])

    def test_past_twenty_matching_the_reference_is_not_enough(self):
        self.assertEqual(self.drive(24), [-1.0])

    def test_answering_blind_is_a_paid_loss(self):
        from nwenv.wiring import ANSWER, EXAM

        def blind(task, _memory):
            return EXAM if task.phase == 'looking' else ANSWER

        self.assertEqual(self.drive(8, policy=blind), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.wiring import Wiring
        close_overlays()
        self.task = Wiring()
        self.task.rng = random.Random(7)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def test_a_click_flips_a_switch_and_look_records_it(self):
        from pyglet.window import key, mouse
        self.task.start_rung = 8
        self.task.start_run()
        switch = next(h for h in self.task.hits
                      if h[4].__name__ == '<lambda>')
        x, y, w, h, _action = switch
        self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                 mouse.LEFT, 0)
        self.assertTrue(self.task.switches[0])
        self.task.on_key_press(key.L, 0)
        self.assertEqual(self.task.round.looks[0][0], 1)
        self.task.on_draw()

    def test_right_answers_on_par_are_green_and_climb(self):
        self.task.start_rung = 3
        self.task.start_run()
        play = self.task.round
        self.task.look()
        self.task.start_exam()
        while self.task.phase == 'examining':
            want = play.question
            setting = next(s for s in range(1 << play.level.switches)
                           if W.lamps_for(play.deal, s) == want)
            self.task.switches = [bool(setting >> i & 1)
                                  for i in range(play.level.switches)]
            self.task.answer()
        self.assertTrue(self.task.verdict_shown[0])
        self.assertIn('=', self.task.reveal)
        self.assertEqual(self.task.rung, 4)
        self.task.on_draw()

    def test_a_run_ends_with_a_tally(self):
        self.task.start_run()
        for _round in range(2):
            self.task.start_exam()
            while self.task.phase == 'examining':
                self.task.answer()
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
        from neural_workshop.ui.wiring import Wiring
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Wiring.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_reasoning(self):
        self.assertIn('wiring', [t for t, _l in TASKS['reasoning']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.wiring import Wiring
        launch_task('wiring')
        self.assertIsNotNone(Wiring.instance)
        Wiring.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.wiring_note({'WIRING_RUNG': 25})
        self.assertIn('lies', note)
        self.assertIn('beat the reference', note)


if __name__ == '__main__':
    unittest.main()
