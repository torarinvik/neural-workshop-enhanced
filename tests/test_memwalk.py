#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Walks from memory: the deals, the floor, and the boundary.

That the screen holds nothing about the goal once it is hidden is
counted over deals, and checked on the screen itself; what players
without memory earn is counted against the module's table.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import Counter

from neural_workshop import memwalk

SIDE = 7


def apart(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def play(p, chooser, rng):
    run = memwalk.Run(p)
    run.t = p.open_at
    while run.result is None:
        run.press(chooser(run, rng))
    return run.result[0]


def at_random(run, rng):
    return rng.randrange(4)


def to_middle(run, rng):
    (x, y), _reached = run.state
    ways = [w for w, ok in ((3, x < 3), (2, x > 3), (0, y < 3), (1, y > 3))
            if ok]
    return rng.choice(ways) if ways else rng.randrange(4)


def share(kind, rung, chooser, n=1500, seed=3):
    rng = random.Random(seed)
    return sum(play(memwalk.deal(kind, rung, rng), chooser, rng)
               for _d in range(n)) / n


class TheDeals(unittest.TestCase):

    def test_rung_k_is_k_presses_and_k_plus_one_for_two(self):
        for rung in range(1, 12):
            for seed in range(20):
                p = memwalk.deal('one', rung, random.Random(seed))
                start = p.start[0]
                self.assertEqual(apart(start, p.goals[0]), rung)
                self.assertEqual(p.par, rung)
                q = memwalk.deal('two', rung, random.Random(seed))
                s, (a, b) = q.start[0], q.goals
                self.assertNotEqual(s, a)
                self.assertNotEqual(a, b)
                self.assertEqual(apart(s, a) + apart(a, b), rung + 1)
                self.assertEqual(q.par, rung + 1)

    def test_the_board_is_the_same_on_every_rung(self):
        for rung in (1, 4, 9):
            p = memwalk.deal('one', rung, random.Random(rung))
            self.assertEqual(p.data['side'], SIDE)
            self.assertEqual(p.ports, 4)
            self.assertEqual(p.limit, p.par + max(2, p.par // 2))


class TheWalk(unittest.TestCase):

    def test_presses_while_the_goals_show_are_ignored(self):
        p = memwalk.deal('one', 3, random.Random(1))
        run = memwalk.Run(p)
        self.assertIsNone(run.press(0))
        self.assertEqual(run.presses, 0)
        run.step(p.open_at)
        self.assertIsNotNone(run.press(0))

    def test_the_second_place_first_does_nothing(self):
        for seed in range(200):
            p = memwalk.deal('two', 4, random.Random(seed))
            (a, b), start = p.goals, p.start[0]
            beside = [w for w, (dx, dy) in enumerate(memwalk.STEPS)
                      if (start[0] + dx, start[1] + dy) == b]
            if not beside or apart(start, a) == 0:
                continue
            state = memwalk.move(p, p.start, beside[0])
            self.assertEqual(state, (b, 0))
            return
        self.fail('no deal put the second place beside the start')

    def test_a_wrong_press_costs_a_step(self):
        p = memwalk.deal('one', 4, random.Random(2))
        run = memwalk.Run(p)
        run.t = p.open_at
        run.press(next(w for w in range(4) if w not in run.good()))
        self.assertIsNone(run.result)
        while run.result is None:
            run.press(run.good()[0])
        self.assertTrue(run.result[0])
        self.assertLessEqual(run.presses, p.limit)


class TheFloor(unittest.TestCase):

    def test_where_the_goal_is_given_the_start_is_drawn_evenly(self):
        rng = random.Random(9)
        for rung in (1, 2, 4):
            seen = Counter()
            for _d in range(150000):
                p = memwalk.deal('one', rung, rng)
                if p.start[0] == (3, 3):
                    seen[p.goals[0]] += 1
            ring = memwalk.ring((3, 3), rung)
            self.assertEqual(set(seen), set(ring))
            total = sum(seen.values())
            for cell in ring:
                self.assertAlmostEqual(seen[cell] / total, 1 / len(ring),
                                       delta=0.2 / len(ring))

    def test_players_without_memory_earn_what_the_table_says(self):
        table = {
            ('one', at_random): (0.36, 0.07, 0.02),
            ('one', to_middle): (0.31, 0.15, 0.06),
            ('two', at_random): (0.13, 0.02, 0.01),
            ('two', to_middle): (0.09, 0.04, 0.01),
        }
        for (kind, chooser), shares in table.items():
            for rung, wanted in zip((1, 3, 5), shares):
                self.assertAlmostEqual(share(kind, rung, chooser), wanted,
                                       delta=0.035, msg=(kind, rung))
        for kind, shares in (('one', (0.26, 0.09, 0.04)),
                             ('two', (0.06, 0.02, 0.01))):
            for rung, wanted in zip((1, 3, 5), shares):
                best = max(share(kind, rung, lambda r, g, w=w: w)
                           for w in range(4))
                self.assertAlmostEqual(best, wanted, delta=0.035,
                                       msg=(kind, rung))


class TheScreen(unittest.TestCase):

    def drive(self, name, policy, rung=3, frame_hz=60.0, early=None,
              steps=3000):
        from nwenv import catalog
        from uisupport import close_overlays, reset_window
        env = catalog.env_class(name)(seed=2, rung=rung, trials=1,
                                      adaptive=False, frame_hz=frame_hz)
        scalars = []
        try:
            for _step in range(steps):
                task = env.task
                port = None
                if task.phase == 'playing' and task.run is not None:
                    port = policy(task) if task.run.open else early
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
            close_overlays()
            reset_window()
        return scalars

    def test_right_wrong_early_and_none(self):
        for name in ('gone_from_view', 'in_that_order'):
            self.assertEqual(self.drive(name, lambda t: t.run.good()[0]),
                             [1.0], name)
            self.assertEqual(self.drive(name, lambda t: next(
                w for w in range(4) if w not in t.run.good())), [-1.0])
            self.assertEqual(self.drive(name, lambda t: t.run.good()[0],
                                        early=0), [1.0], name)
            self.assertEqual(self.drive(name, lambda t: None), [-1.0])

    def test_judged_the_same_a_step_a_frame(self):
        for name in ('gone_from_view', 'in_that_order'):
            for pick in (lambda t: t.run.good()[0], lambda t: 0):
                self.assertEqual(self.drive(name, pick, frame_hz=2.0,
                                            steps=300),
                                 self.drive(name, pick, frame_hz=10.0))

    def test_the_goal_is_not_drawn_once_hidden(self):
        from nwenv import catalog
        env = catalog.env_class('gone_from_view')(seed=1, rung=2,
                                                  trials=1, adaptive=False,
                                                  frame_hz=2.0)
        try:
            task = env.task
            drawn = []
            real = task._goal
            task._goal = lambda *a: (drawn.append(a), real(*a))
            for _step in range(6):
                drawn.clear()
                task._redraw()
                self.assertEqual(bool(drawn), not task.run.open)
                env.step(None)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()
