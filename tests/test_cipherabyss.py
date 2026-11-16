#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Cipher Abyss: the language, the laboratory, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import cipherabyss as M

RUNGS = (1, 4, 7, 10, 13, 16, 20, 25, 33)
ZERO = (0, None, None)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertEqual(rand, [])

    def test_each_stage_comes_in_at_its_rung(self):
        stages = [M.grade(r).stage for r in (1, 4, 7, 10, 13, 16, 20, 25)]
        self.assertEqual(stages, list(range(1, 9)))
        self.assertLess(M.grade(40).budget, M.grade(25).budget)
        self.assertGreater(M.grade(40).length, M.grade(25).length)

    def test_the_language_grows_up_the_ladder(self):
        sizes = [len(M.family(M.grade(r))) for r in (1, 4, 7)]
        self.assertLess(sizes[0], sizes[1])
        self.assertLess(sizes[1], sizes[2])


class TheLanguage(unittest.TestCase):

    def test_the_primitives(self):
        x = (0, 1, 2, 2)
        self.assertEqual(M.apply(('seq', (('rev',),)), x, 3, ZERO),
                         (2, 2, 1, 0))
        self.assertEqual(M.apply(('seq', (('rot', 1),)), x, 3, ZERO),
                         (2, 0, 1, 2))
        self.assertEqual(M.apply(('seq', (('shift', 1),)), x, 3, ZERO),
                         (1, 2, 0, 0))
        self.assertEqual(M.apply(('seq', (('prefix',),)), x, 3, ZERO),
                         (0, 1, 0, 2))
        self.assertEqual(M.apply(('seq', (('swap',),)), x, 3, ZERO),
                         (1, 0, 2, 2))

    def test_composition_runs_left_to_right(self):
        rule = ('seq', (('rev',), ('shift', 1)))
        self.assertEqual(M.apply(rule, (0, 1, 2), 3, ZERO), (0, 2, 1))

    def test_a_condition_picks_the_branch(self):
        rule = ('if', ('first', 0), ('seq', (('rev',),)),
                ('seq', (('shift', 1),)))
        self.assertEqual(M.apply(rule, (0, 1), 2, ZERO), (1, 0))
        self.assertEqual(M.apply(rule, (1, 1), 2, ZERO), (0, 0))

    def test_state_changes_the_answer(self):
        rule = ('seq', (('tshift', 1),))
        self.assertEqual(M.apply(rule, (0, 0), 3, (0, None, None)), (0, 0))
        self.assertEqual(M.apply(rule, (0, 0), 3, (2, None, None)), (2, 2))

    def test_the_exception_fires_only_on_one_symbol(self):
        rule = ('except', ('seq', (('rev',),)), ('seq', (('shift', 1),)))
        self.assertEqual(M.apply(rule, (0, 1), 2, ZERO), (1, 0))
        self.assertEqual(M.apply(rule, (1, 1), 2, ZERO), (0, 0))

    def test_every_rule_can_be_said(self):
        for r in RUNGS:
            for rule in M.family(M.grade(r))[:50]:
                self.assertTrue(M.describe(rule))


class TheLaboratory(unittest.TestCase):

    def test_an_experiment_is_logged_and_spends_one(self):
        run = M.Run(M.deal(1, seed=1))
        for v in (0, 1, 0, 0):
            M.act(run, M.SYM + v)
        M.act(run, M.RUN)
        self.assertEqual(len(run.log), 1)
        self.assertEqual(run.left(), run.level.budget - 1)

    def test_a_short_input_does_not_run(self):
        run = M.Run(M.deal(1, seed=1))
        M.act(run, M.SYM)
        M.act(run, M.RUN)
        self.assertEqual(run.log, [])

    def test_a_wrong_answer_fails_and_says_the_rule(self):
        machine = M.deal(1, seed=1)
        run = M.Run(machine)
        M.act(run, M.TEST)
        q = run.question()
        truth = M.apply(machine.rule, q, machine.level.k, ZERO)
        wrong = tuple(1 - v for v in truth)
        for v in wrong:
            M.act(run, M.SYM + v)
        M.act(run, M.RUN)
        self.assertFalse(run.result[0])
        self.assertIn(M.describe(machine.rule), run.result[1])

    def test_the_adversarial_test_asks_about_the_exception(self):
        machine = M.deal(25, seed=2)
        self.assertTrue(any(len(set(t)) == 1 for t in machine.tests))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('cipher_abyss', 4, pilot, seed=1,
                               steps=12000), [1.0])
        self.assertEqual(drive('cipher_abyss', 1, lambda t: None, seed=1,
                               steps=40000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('cipher_abyss', M), 0)


if __name__ == '__main__':
    unittest.main()
