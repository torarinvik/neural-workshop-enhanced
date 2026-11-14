#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The think clock: thinking on a turn-based task finally costs something.

Without it a turn-based task waits for ever, and a learner that ponders
for a thousand steps is paid what one that answers in ten is. These
tests hold the clock to what it promises: a bank that drains only while
a trial is open, refills by a set amount per trial, forfeits a trial
with the ordinary red verdict when it runs dry -- a verdict the ordinary
verifier accepts -- and is drawn where the learner can see it and the
verdict reader never looks.

Syllogisms is the task under test because one port answers it, so how
long a policy waits before answering is the only thing that varies.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import close_overlays, needs_ui, reset_window

from nwenv import catalog
from nwenv.taskenv import THINK_BAR_COLOR, THINK_BAR_PX

HZ = 60.0


def waiting(env, waits, steps=4000):
    """Answer each trial right after *waits[trial]* idle steps.

    Returns the scalars paid, in order. A step with no port is the
    think action: the frame advances and nothing is pressed.
    """
    scalars = []
    trial, idle, last = 0, 0, None
    try:
        for _step in range(steps):
            task = env.task
            port = None
            if env._on_move():
                if task.question is not last:
                    last, idle = task.question, 0
                if idle >= waits[min(trial, len(waits) - 1)]:
                    port = task.question.answer
                    trial += 1
                    last = None
                idle += 1
            _obs, events, done = env.step(port)
            scalars += [e['scalar'] for e in events
                        if e.get('type') == 'outcome']
            if done:
                break
    finally:
        env.close()
    return scalars


@needs_ui
class TheBankIsAPrice(unittest.TestCase):

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def env(self, **clock):
        return catalog.env_class('syllogism')(seed=0, rung=6, trials=3,
                                              frame_hz=HZ, **clock)

    def test_no_clock_means_no_change(self):
        env = self.env()
        self.assertEqual(env.think_left, 0.0)
        self.assertEqual(waiting(env, [600]), [1.0, 1.0, 1.0])

    def test_an_answer_inside_the_deadline_is_paid(self):
        env = self.env(think_seconds=0.5)
        self.assertEqual(waiting(env, [10]), [1.0, 1.0, 1.0])

    def test_an_answer_past_the_deadline_is_forfeit(self):
        env = self.env(think_seconds=0.5)
        self.assertEqual(waiting(env, [60]), [-1.0, -1.0, -1.0])
        self.assertEqual(env.forfeits, 3)

    def test_a_deadline_is_per_trial_when_the_refill_is_full(self):
        """Twenty steps of a thirty-step bank, three times over: each
        trial starts with a full bank again."""
        env = self.env(think_seconds=0.5)
        self.assertEqual(waiting(env, [20]), [1.0, 1.0, 1.0])

    def test_one_bank_for_the_run_charges_the_later_trials(self):
        """The same twenty steps against one bank with no refill: the
        first trial spends what the second needed."""
        env = self.env(think_seconds=0.5, refill_seconds=0.0)
        self.assertEqual(waiting(env, [20]), [1.0, -1.0, -1.0])

    def test_time_saved_on_an_easy_trial_buys_a_hard_one(self):
        """A chess clock with an increment. Quick answers keep the bank
        topped up, and the topped-up bank pays for a long think that a
        bare deadline of the same increment would forfeit."""
        clock = dict(think_seconds=1.0, refill_seconds=0.25)
        self.assertEqual(waiting(self.env(**clock), [1, 1, 40]),
                         [1.0, 1.0, 1.0])
        self.assertEqual(waiting(self.env(think_seconds=0.25), [1, 1, 40]),
                         [1.0, 1.0, -1.0])

    def test_the_bank_drains_only_while_on_move(self):
        env = self.env(think_seconds=1.0, refill_seconds=0.0)
        try:
            env.step(None)
            env.step(None)
            self.assertAlmostEqual(env.think_left, 1.0 - 2 / HZ, places=6)
            env.step(env.task.question.answer)
            left = env.think_left
            env.step(None)              # the verdict frame
            self.assertAlmostEqual(env.think_left, left, places=6)
        finally:
            env.close()

    def test_a_forfeit_verifies_like_any_other_loss(self):
        env = self.env(think_seconds=0.1)
        verify = type(env).verifier()
        try:
            for _step in range(200):
                obs, events, _done = env.step(None)
                paid = [e for e in events if e.get('type') == 'outcome']
                if paid:
                    break
            self.assertEqual(paid[0]['scalar'], -1.0)
            self.assertTrue(verify(obs['outcome'], obs['rgba'], obs['width'],
                                   obs['height'], archive=env._archive,
                                   receipt_ledger=env._receipt_ledger))
        finally:
            env.close()

    def test_a_runtime_acting_every_tick_is_paid_the_forfeit(self):
        """A runtime presses something on every tick, a do-nothing port
        when it is thinking. The forfeit is still paid, once per trial,
        and every other tick is a zero."""
        cls = catalog.env_class('syllogism')
        env = cls(seed=0, rung=6, trials=2, frame_hz=HZ,
                  neutral_outcomes=True, runtime_ports=cls.ports + 1,
                  think_seconds=0.1)
        scalars = []
        try:
            for _step in range(400):
                _obs, events, done = env.step(cls.ports)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done:
                    break
        finally:
            env.close()
        self.assertEqual(scalars.count(-1.0), env.forfeits)
        self.assertEqual(env.forfeits, 2)
        self.assertEqual(set(scalars) - {0.0, -1.0}, set())

    def test_the_bank_is_drawn_along_the_top_edge(self):
        env = self.env(think_seconds=1.0, refill_seconds=0.0)
        try:
            for _step in range(30):
                obs, _events, _done = env.step(None)
            width, height = obs['width'], obs['height']
            rgba = obs['rgba']
            row = 1 * width * 4         # frames are top-down: the top edge
            lit = sum(1 for x in range(width)
                      if tuple(rgba[row + 4 * x: row + 4 * x + 3])
                      == THINK_BAR_COLOR)
            self.assertAlmostEqual(lit / width, env.think_left, delta=0.03)
            self.assertLess(THINK_BAR_PX, height // 20)
        finally:
            env.close()


@needs_ui
class OnlyWhereItMeansSomething(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_a_clocked_task_is_refused(self):
        with self.assertRaises(ValueError):
            catalog.env_class('reflex')(seed=0, think_seconds=1.0)

    def test_a_task_that_deals_itself_is_refused(self):
        with self.assertRaises(ValueError):
            catalog.env_class('you_are_here')(seed=0, think_seconds=1.0)

    def test_every_declared_turn_based_task_forfeits_and_ends(self):
        """Never act, and every trial of every run is a paid loss."""
        eligible = []
        for entry in catalog.CATALOG:
            cls = catalog.env_class(entry.task_id)
            if (not getattr(cls, 'clocked', True)
                    and getattr(cls, 'settled_phase', ())):
                eligible.append(entry.task_id)
        self.assertGreaterEqual(len(eligible), 19)
        for task_id in eligible:
            env = catalog.env_class(task_id)(seed=0, think_seconds=0.1)
            scalars, done = [], False
            try:
                for _step in range(3000):
                    _obs, events, done = env.step(None)
                    scalars += [e['scalar'] for e in events
                                if e.get('type') == 'outcome']
                    if done:
                        break
            finally:
                env.close()
            if not env.forfeits:
                continue                # no library, so nothing was dealt
            self.assertTrue(done, task_id)
            self.assertEqual(scalars, [-1.0] * env.forfeits, task_id)


if __name__ == '__main__':
    unittest.main()
