#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Hidden Rule: the rules, the fairness of par, the reference, the screen.

The rule space is held to being what its docstring says: every rule a
distinct set of objects, none lighting for everything or nothing, and
the bit table the reference counts with agreeing with the rules it was
turned from. Par is held to the same fairness Sonar's is -- the lamp's
lies fixed by test number, the exam fixed by the deal -- and the
reference to never ruling out the truth on an honest lamp, to learning
the rule rather than the notebook, and to beating players who test at
random. The boundary is held to paying the reference's own play through
the ten ports, and refusing it past rung twenty.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import hiddenrule as H


class TheLadder(unittest.TestCase):

    def test_every_rung_allows_at_least_what_the_last_did(self):
        last = H.grade(1)
        for rung in range(2, 80):
            level = H.grade(rung)
            self.assertGreaterEqual(len(level.values), len(last.values))
            self.assertTrue(set(last.forms) <= set(level.forms), rung)
            self.assertGreaterEqual(level.nots, last.nots)
            self.assertGreaterEqual(level.noise, last.noise)
            self.assertGreaterEqual(level.penalty, last.penalty)
            self.assertLessEqual(level.factor, last.factor)
            self.assertGreaterEqual(len(H.space(level).rules),
                                    len(H.space(last).rules), rung)
            last = level

    def test_the_lamp_is_honest_until_rung_twelve(self):
        self.assertEqual(H.grade(11).noise, 0.0)
        self.assertGreater(H.grade(12).noise, 0.0)
        self.assertLessEqual(H.grade(90).noise, H.NOISIEST)

    def test_the_allowance_never_buys_a_wrong_answer(self):
        for rung in range(1, 40):
            level = H.grade(rung)
            self.assertLess(level.slack, level.penalty, rung)

    def test_past_twenty_par_is_below_the_reference(self):
        self.assertGreaterEqual(H.grade(20).factor, 1.0)
        self.assertLess(H.grade(21).factor, 1.0)
        self.assertLess(H.grade(40).factor, H.grade(30).factor)


class TheRules(unittest.TestCase):

    def test_every_rule_is_its_own_set_of_objects(self):
        for rung in (1, 4, 8, 13, 16, 19):
            world = H.space(H.grade(rung))
            full = (1 << len(world.items)) - 1
            masks = [rule.mask for rule in world.rules]
            self.assertEqual(len(masks), len(set(masks)), rung)
            self.assertNotIn(0, masks)
            self.assertNotIn(full, masks)

    def test_the_bit_table_agrees_with_the_rules(self):
        world = H.space(H.grade(16))
        rng = random.Random(1)
        for _check in range(300):
            r = rng.randrange(len(world.rules))
            i = rng.randrange(len(world.items))
            self.assertEqual(bool((world.lights[i] >> r) & 1),
                             H.lit(world.rules[r], i))

    def test_a_rule_lights_for_exactly_what_it_says(self):
        world = H.space(H.grade(16))
        checks = {
            'is': lambda h: h[0],
            'both': lambda h: h[0] and h[1],
            'either': lambda h: h[0] or h[1],
            'one_of': lambda h: h[0] != h[1],
            'all': lambda h: all(h),
            'any': lambda h: any(h),
            'two_of': lambda h: sum(h) >= 2,
            'both_or': lambda h: (h[0] and h[1]) or h[2],
            'either_and': lambda h: (h[0] or h[1]) and h[2],
        }
        for rule in world.rules[::37]:
            for index, item in enumerate(world.items):
                holds = [(item[f] == v) == positive
                         for f, v, positive in rule.atoms]
                self.assertEqual(checks[rule.form](holds),
                                 H.lit(rule, index), rule.form)

    def test_negation_only_where_it_means_something(self):
        for rule in H.space(H.grade(19)).rules:
            for feature, _value, positive in rule.atoms:
                if not positive:
                    self.assertGreaterEqual(H.grade(19).values[feature], 3)


class FairDeals(unittest.TestCase):

    def test_a_round_is_fixed_by_its_seed(self):
        self.assertEqual(H.deal(14, seed=5), H.deal(14, seed=5))
        self.assertNotEqual(H.deal(14, seed=5), H.deal(14, seed=6))

    def test_the_lamp_lies_by_test_number_not_by_what_is_tested(self):
        dealt = H.deal(16, seed=2)
        one, two = H.Round(dealt), H.Round(dealt)
        for k in range(12):
            a, b = one.test(k), two.test(100 + k)
            self.assertEqual(a != H.lit(dealt.rule, k),
                             b != H.lit(dealt.rule, 100 + k), k)

    def test_the_free_examples_are_one_of_each_and_true(self):
        for seed in range(20):
            dealt = H.deal(13, seed=seed)
            (bright, yes), (dim, no) = dealt.seeds
            self.assertEqual((yes, no), (True, False))
            self.assertTrue(H.lit(dealt.rule, bright))
            self.assertFalse(H.lit(dealt.rule, dim))

    def test_the_exam_is_half_lit(self):
        for rung in (1, 8, 16):
            dealt = H.deal(rung, seed=4)
            bright = sum(H.lit(dealt.rule, i) for i in dealt.exam)
            self.assertEqual(bright, dealt.level.exam // 2)

    def test_cost_is_tests_plus_penalties(self):
        dealt = H.deal(6, seed=0)
        play = H.Round(dealt)
        play.test(0)
        play.test(1)
        play.start_exam()
        self.assertIsNone(play.test(2))
        calls = []
        while not play.over:
            truth = H.lit(dealt.rule, play.question)
            call = truth if calls else not truth
            calls.append(call)
            play.answer(call)
        self.assertEqual(play.wrong, 1)
        self.assertEqual(play.cost, 2 * H.TEST + dealt.level.penalty)

    def test_the_notebook_has_a_last_page(self):
        play = H.Round(H.deal(3, seed=0))
        while play.test(0) is not None:
            pass
        self.assertEqual(len(play.tests), H.BUDGET)


class TheReference(unittest.TestCase):

    def test_on_an_honest_lamp_it_never_rules_out_the_truth(self):
        for rung in (3, 8, 11):
            for seed in range(4):
                dealt = H.deal(rung, seed=seed)
                world = H.space(dealt.level)
                truth = world.rules.index(dealt.rule)
                play = H.Round(dealt)
                belief = H.Belief(dealt.level, dealt.seeds)
                while True:
                    self.assertTrue((belief.tiers[0] >> truth) & 1)
                    index = H.reference_move(belief, play.tests_left)
                    if index is None:
                        break
                    belief.saw(index, play.test(index))

    def test_it_learns_the_rule_and_not_the_notebook(self):
        """No mistakes on an honest lamp, on objects it never tested."""
        for rung in (1, 4, 8, 11):
            for seed in range(5):
                play = H.reference_round(H.deal(rung, seed=seed))
                self.assertEqual(play.wrong, 0, (rung, seed))

    def test_it_asks_the_question_its_rules_split_on(self):
        dealt = H.deal(8, seed=3)
        belief = H.Belief(dealt.level, dealt.seeds)
        chances = belief.chances()
        index = H.reference_move(belief, H.BUDGET)
        best = min(abs(c - 0.5) for c in chances)
        self.assertAlmostEqual(abs(chances[index] - 0.5), best)

    def test_it_beats_testing_at_random(self):
        def random_round(dealt, tests, seed):
            rng = random.Random(seed)
            play = H.Round(dealt)
            belief = H.Belief(dealt.level, dealt.seeds)
            count = len(H.space(dealt.level).items)
            for _test in range(tests):
                index = rng.randrange(count)
                belief.saw(index, play.test(index))
            play.start_exam()
            chances = belief.chances()
            while not play.over:
                play.answer(chances[play.question] >= 0.5)
            return play.cost

        for rung in (10, 13, 16):
            deals = [H.deal(rung, seed=seed) for seed in range(12)]
            reference = sum(H.reference_round(d).cost for d in deals)
            for tests in (4, 12):
                guessed = sum(random_round(d, tests, s)
                              for s, d in enumerate(deals))
                self.assertLess(reference * 1.3, guessed, (rung, tests))

    def test_par_is_its_cost_scaled_by_the_rung(self):
        dealt = H.deal(25, seed=1)
        self.assertLess(H.par(dealt), H.reference_round(dealt).cost)
        dealt = H.deal(2, seed=1)
        self.assertGreater(H.par(dealt), H.reference_round(dealt).cost)


def reference_ports(task, memory):
    """The reference's own play, steered through the ten ports."""
    from nwenv.hiddenrule import DARK, EXAM, LIT, TEST
    play = task.round
    if memory.get('round') is not play:
        memory.update(round=play, seen=0, done=False,
                      belief=H.Belief(play.level, play.deal.seeds))
    belief = memory['belief']
    while memory['seen'] < len(play.tests):
        belief.saw(*play.tests[memory['seen']])
        memory['seen'] += 1
    if task.phase == 'examining':
        return LIT if belief.chance(play.question) >= 0.5 else DARK
    index = H.reference_move(belief, play.tests_left)
    if index is None:
        return EXAM
    target = H.space(play.level).items[index]
    for feature, value in enumerate(target):
        if task.item[feature] != value:
            return feature
    return TEST


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, seed=0, policy=reference_ports):
        from nwenv import catalog
        env = catalog.env_class('hidden_rule')(seed=seed, rung=rung,
                                               trials=1, adaptive=False)
        memory, scalars = {}, []
        try:
            for _step in range(4000):
                task = env.task
                port = (policy(task, memory)
                        if task.phase in ('testing', 'examining') else None)
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_the_reference_s_play_passes_a_simple_rule(self):
        self.assertEqual(self.drive(4), [1.0])

    def test_and_a_compound_one(self):
        self.assertEqual(self.drive(10), [1.0])

    def test_past_twenty_matching_the_reference_is_not_enough(self):
        self.assertEqual(self.drive(24), [-1.0])

    def test_guessing_the_exam_blind_is_a_paid_loss(self):
        from nwenv.hiddenrule import EXAM, LIT

        def blind(task, _memory):
            return EXAM if task.phase == 'testing' else LIT

        self.assertEqual(self.drive(8, policy=blind), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.hiddenrule import HiddenRule
        close_overlays()
        self.task = HiddenRule()
        self.task.rng = random.Random(7)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def click_on(self, words):
        """Click the button or swatch whose action is *words*."""
        for x, y, w, h, action in self.task.hits:
            if getattr(action, '__name__', '') == words:
                from pyglet.window import mouse
                self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                         mouse.LEFT, 0)
                return
        self.fail('nothing to click for %s' % words)

    def test_a_swatch_click_changes_the_object_and_test_records_it(self):
        from pyglet.window import mouse
        self.task.start_rung = 8
        self.task.start_run()
        x, y, w, h, _action = self.task.hits[1]     # colour, second value
        self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                 mouse.LEFT, 0)
        self.assertEqual(self.task.item[0], 1)
        self.click_on('test')
        self.assertEqual(len(self.task.round.tests), 1)
        self.assertEqual(self.task.round.tests[0][0],
                         self.task.index_of(self.task.item))
        self.assertEqual(len(self.task.notebook), 3)
        self.task.on_draw()

    def test_keys_step_test_and_answer(self):
        from pyglet.window import key
        self.task.start_run()
        self.task.on_key_press(key._2, 0)
        self.assertEqual(self.task.item[1], 1)
        self.task.on_key_press(key.T, 0)
        self.task.on_key_press(key.E, 0)
        self.assertEqual(self.task.phase, 'examining')
        self.task.on_key_press(key.T, 0)
        self.assertEqual(len(self.task.round.tests), 1)
        self.task.on_key_press(key.Y, 0)
        self.assertEqual(self.task.round.answers, [True])
        self.task.on_draw()

    def test_a_perfect_exam_on_par_is_green_names_the_rule_and_climbs(self):
        self.task.start_rung = 3
        self.task.start_run()
        play = self.task.round
        self.task.start_exam()
        while self.task.phase == 'examining':
            self.task.answer(H.lit(play.deal.rule, play.question))
        self.assertEqual(self.task.phase, 'judged')
        self.assertTrue(self.task.verdict_shown[0])
        self.assertIn('The rule was', self.task.reveal)
        self.assertEqual(self.task.rung, 4)
        self.task.on_draw()

    def test_a_run_ends_with_a_tally(self):
        self.task.start_run()
        for _round in range(2):
            play = self.task.round
            self.task.start_exam()
            while self.task.phase == 'examining':
                self.task.answer(H.lit(play.deal.rule, play.question))
            self.now = self.task.feedback_until
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['passed'], 2)

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
        from neural_workshop.ui.hiddenrule import HiddenRule
        self.task.start_run()
        self.task.close()
        self.assertIsNone(HiddenRule.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_reasoning(self):
        self.assertIn('hidden_rule', [t for t, _l in TASKS['reasoning']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.hiddenrule import HiddenRule
        launch_task('hidden_rule')
        self.assertIsNotNone(HiddenRule.instance)
        HiddenRule.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.hidden_rule_note({'HIDDEN_RULE_RUNG': 25})
        self.assertIn('lies', note)
        self.assertIn('beat the reference', note)


if __name__ == '__main__':
    unittest.main()
