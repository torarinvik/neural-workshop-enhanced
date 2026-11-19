#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Own presses: the deals, the floors, and the boundary.

Runs are dealt trial by trial with a ledger, as the screen deals them,
and the answers checked against a record of the presses kept here.
What players without memory of their own presses, and the cheap
partial strategies, earn is counted over whole runs.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from memorysupport import best_from_view

from neural_workshop import framed, ownpress

IDS = {('cycle', 0): 'next_in_turn', ('cycle', 1): 'round_again',
       ('stay', 0): 'stay_or_shift', ('stay', 1): 'moving_prize'}
#: The cycle kept here: the port after each port, by look.
AFTER = {0: {0: 1, 1: 2, 2: 3, 3: 0}, 1: {0: 2, 2: 3, 3: 1, 1: 0}}


def play(kind, rung, player, trials=4000, look=0, seed=3):
    """Deal a run of *trials*, pressing *player(history, rng)* each time
    (None for no press); the run's puzzles, presses and payments."""
    rng, mine = random.Random(seed), random.Random(seed + 100)
    ledger = ownpress.Ledger()
    log = []
    for _t in range(trials):
        p = ownpress.deal(kind, rung, rng, look=look, ledger=ledger)
        press = player(log, mine)
        ledger.record(press)
        log.append((p, press, press == p.answer))
    return log


def share(log, skip=50):
    paid = [ok for _p, _press, ok in log[skip:]]
    return sum(paid) / len(paid)


def at_random(log, rng):
    return rng.randrange(ownpress.PORTS)


def cycler(log, rng):
    return (0 if not log else AFTER[0][log[-1][1]])


def win_stay(log, rng):
    if not log:
        return 0
    _p, press, ok = log[-1]
    return press if ok else (press + 1 + rng.randrange(3)) % 4


class TheDeals(unittest.TestCase):

    def test_the_answer_follows_the_press_k_trials_back(self):
        for look in framed.LOOKS:
            for rung in (1, 2, 3, 6):
                log = play('cycle', rung, lambda log, rng: rng.choice(
                    (0, 1, 2, 3, None)), trials=300, look=look)
                checked = 0
                for t, (p, _press, _ok) in enumerate(log):
                    if t >= rung and log[t - rung][1] is not None:
                        self.assertEqual(
                            p.answer, AFTER[look][log[t - rung][1]])
                        checked += 1
                self.assertGreater(checked, 150)

    def test_the_hidden_port_stays_for_a_block_then_moves(self):
        for rung in (1, 2, 4):
            ledger, rng = ownpress.Ledger(), random.Random(rung)
            for _t in range(600):
                p = ownpress.deal('stay', rung, rng, ledger=ledger)
                self.assertEqual(p.answer, ledger.hidden[-1].port)
                ledger.record(None)
            hidden = ledger.hidden
            for t in range(rung, len(hidden)):
                before, now = hidden[t - rung], hidden[t]
                self.assertTrue(ownpress.BLOCK[0] <= now.length
                                <= ownpress.BLOCK[1])
                if before.age < before.length:
                    self.assertEqual(now.port, before.port)
                    self.assertEqual(now.age, before.age + 1)
                else:
                    self.assertNotEqual(now.port, before.port)
                    self.assertEqual(now.age, 1)

    def test_the_question_waits_a_blank_frame(self):
        p = ownpress.deal('cycle', 1, random.Random(1))
        self.assertEqual(p.frames, (-1, 0))
        self.assertAlmostEqual(p.open_at, framed.FRAME)


class TheFloors(unittest.TestCase):

    def test_the_screen_says_nothing(self):
        for kind in ownpress.KINDS:
            ledger = ownpress.Ledger()

            def deal(rng, kind=kind, ledger=ledger):
                p = ownpress.deal(kind, 1, rng, ledger=ledger)
                ledger.record(rng.randrange(4))
                return p
            self.assertLess(best_from_view(deal, lambda p: (
                p.data['layout'], p.data['hue'])), 0.28, kind)

    def test_pressing_at_random_is_right_one_time_in_four(self):
        for kind in ownpress.KINDS:
            for rung in (1, 3):
                self.assertAlmostEqual(share(play(kind, rung, at_random)),
                                       0.25, delta=0.03, msg=kind)

    def test_one_port_all_run(self):
        same = lambda log, rng: 2  # noqa: E731
        self.assertEqual(share(play('cycle', 2, same)), 0.0)
        self.assertAlmostEqual(share(play('stay', 2, same)), 0.25,
                               delta=0.03)

    def test_pressing_round_the_cycle_without_looking_back(self):
        for rung in range(1, 10):
            expected = 1.0 if rung % 4 == 1 else 0.0
            self.assertEqual(share(play('cycle', rung, cycler, 400)),
                             expected, rung)

    def test_win_stay_lose_shift_on_the_trial_before(self):
        self.assertAlmostEqual(share(play('stay', 1, win_stay)), 0.5,
                               delta=0.04)
        self.assertAlmostEqual(share(play('stay', 2, win_stay, 20000)),
                               0.29, delta=0.02)
        for rung in (3, 5):
            self.assertAlmostEqual(share(play('stay', rung, win_stay,
                                              20000)), 0.25, delta=0.02)

    def test_win_stay_lose_shift_k_back_earns_half(self):
        def k_back(k):
            def player(log, rng):
                if len(log) < k:
                    return rng.randrange(4)
                _p, press, ok = log[-k]
                return press if ok else (press + 1 + rng.randrange(3)) % 4
            return player
        for rung in (2, 3):
            self.assertAlmostEqual(share(play('stay', rung,
                                              k_back(rung))), 0.5,
                                   delta=0.04)


class TheBoundary(unittest.TestCase):

    def run_of(self, name, policy, trials=6, rung=2, early=None):
        from nwenv import catalog
        from uisupport import close_overlays, reset_window
        env = catalog.env_class(name)(seed=4, rung=rung, trials=trials,
                                      adaptive=False)
        scalars, words = [], set()
        try:
            for _step in range(20000):
                task = env.task
                port = None
                if task.phase == 'playing' and task.run is not None:
                    port = policy(task) if task.run.open else early
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if task.phase == 'judged':
                    words.add(task.message)
                if done:
                    break
        finally:
            env.close()
            close_overlays()
            reset_window()
        return scalars, words

    def test_right_wrong_early_and_none(self):
        for name in IDS.values():
            scalars, words = self.run_of(name, lambda t: t.puzzle.answer)
            self.assertEqual(scalars, [1.0] * 6, name)
            self.assertEqual(words, {'Right'})
            scalars, words = self.run_of(
                name, lambda t: (t.puzzle.answer + 1) % 4)
            self.assertEqual(scalars, [-1.0] * 6, name)
            self.assertEqual(words, {'Wrong'})
            scalars, _w = self.run_of(name, lambda t: t.puzzle.answer,
                                      early=0)
            self.assertEqual(scalars, [1.0] * 6, name)
            scalars, _w = self.run_of(name, lambda t: None, trials=2)
            self.assertEqual(scalars, [-1.0] * 2, name)

    def test_the_screen_keeps_the_ledger_and_the_cycle(self):
        from nwenv import catalog
        env = catalog.env_class('next_in_turn')(seed=5, rung=1, trials=8,
                                                adaptive=False)
        presses, answers = [], []
        try:
            for _step in range(20000):
                task = env.task
                port = None
                if task.phase == 'playing' and task.run.open:
                    if len(answers) < len(task.ledger.presses) + 1:
                        answers.append(task.puzzle.answer)
                    port = (len(presses) * 3) % 4
                    presses.append(port)
                _obs, _events, done = env.step(port)
                if done:
                    break
            self.assertEqual(task.ledger.presses, presses)
            for t in range(1, len(presses)):
                self.assertEqual(answers[t], AFTER[0][presses[t - 1]])
        finally:
            env.close()

    def test_no_panel_is_marked_after_a_press(self):
        from neural_workshop.ui.ownpress import NextInTurn
        task = NextInTurn.__new__(NextInTurn)
        task.ink = (0, 0, 0)
        self.assertEqual({task._mark(i) for i in range(4)},
                         {((0, 0, 0), 2)})


if __name__ == '__main__':
    unittest.main()
