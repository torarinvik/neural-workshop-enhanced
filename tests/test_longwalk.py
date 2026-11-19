#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forgiving walks: the deals, the steps, and the boundary.

The shortest ways are found here by a search of the maze's own doors,
not by the dealer's distances.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import deque

from neural_workshop import longwalk, ministeps


def shortest(p):
    """Presses on the shortest way from the start to the goal."""
    doors, goal = p.data['doors'], p.data['goal']
    start = p.start[0]
    seen = {start: 0}
    queue = deque([start])
    while queue:
        x, y = here = queue.popleft()
        if here == goal:
            return seen[here]
        for dx, dy in ministeps.STEPS:
            to = (x + dx, y + dy)
            if frozenset((here, to)) in doors and to not in seen:
                seen[to] = seen[here] + 1
                queue.append(to)
    return None


class TheDeals(unittest.TestCase):

    def test_rung_k_is_k_presses_on_the_shortest_way(self):
        for rung in range(1, 21):
            for seed in range(5):
                p = longwalk.deal('walk', rung, random.Random(seed))
                self.assertEqual(p.par, rung)
                self.assertEqual(shortest(p), rung)
                self.assertEqual(longwalk.far(p, p.start), rung)

    def test_the_board_and_ports_are_the_same_on_every_rung(self):
        for kind in longwalk.KINDS:
            for rung in (1, 5, 12):
                p = longwalk.deal(kind, rung, random.Random(rung))
                self.assertEqual(p.data['side'], 7)
                self.assertEqual(p.ports, 4)

    def test_the_steps_allowed_are_a_little_above_par(self):
        self.assertEqual([longwalk.allowed(k) for k in (1, 2, 4, 5, 10)],
                         [3, 4, 6, 7, 15])


class TheSteps(unittest.TestCase):

    def test_a_bump_wastes_a_step_and_the_walk_goes_on(self):
        for seed in range(30):
            p = longwalk.deal('walk', 4, random.Random(seed))
            walk = longwalk.Walk(p)
            bumps = [port for port in range(4)
                     if longwalk.move(p, walk.state, port) == walk.state]
            if not bumps:
                continue
            self.assertFalse(walk.press(bumps[0]))
            self.assertIsNone(walk.result)
            while walk.result is None:
                walk.press(walk.good()[0])
            self.assertTrue(walk.result[0])
            self.assertEqual(walk.presses, 5)

    def test_a_dead_end_can_be_walked_into(self):
        found = 0
        for seed in range(40):
            p = longwalk.deal('walk', 6, random.Random(seed))
            walk = longwalk.Walk(p)
            away = [port for port in range(4)
                    if port not in walk.good()
                    and longwalk.move(p, walk.state, port) != walk.state]
            if away:
                walk.press(away[0])
                self.assertIsNone(walk.result)
                self.assertEqual(longwalk.far(p, walk.state), 7)
                found += 1
        self.assertGreater(found, 10)

    def test_the_last_step_ends_it(self):
        p = longwalk.deal('walk', 3, random.Random(2))
        walk = longwalk.Walk(p)
        presses = 0
        while walk.result is None:
            bump = [port for port in range(4)
                    if port not in walk.good()][0]
            walk.press(bump)
            presses += 1
        self.assertEqual(presses, p.limit)
        self.assertFalse(walk.result[0])

    def test_random_presses_at_rung_one(self):
        for kind, share in (('walk', 0.45),):
            rng, wins = random.Random(1), 0
            for _d in range(3000):
                walk = longwalk.Walk(longwalk.deal(kind, 1, rng))
                while walk.result is None:
                    walk.press(rng.randrange(4))
                wins += walk.result[0]
            self.assertAlmostEqual(wins / 3000, share, delta=0.03)


class TheBoundary(unittest.TestCase):

    def drive(self, name, policy, rung=3):
        from nwenv import catalog
        from uisupport import close_overlays, reset_window
        env = catalog.env_class(name)(seed=2, rung=rung, trials=1,
                                      adaptive=False)
        scalars = []
        try:
            for _step in range(200):
                task = env.task
                port = policy(task) if task.phase == 'playing' else None
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

    def test_right_wrong_wasted_and_none(self):
        for name in ('long_way_round',):
            self.assertEqual(self.drive(name, lambda t: t.walk.good()[0]),
                             [1.0], name)
            self.assertEqual(self.drive(name, lambda t: next(
                p for p in range(4) if p not in t.walk.good())), [-1.0])

            def waste_one(task):
                if task.walk.presses == 0:
                    bumps = [p for p in range(4) if longwalk.move(
                        task.puzzle, task.walk.state, p) == task.walk.state]
                    if bumps:
                        return bumps[0]
                return task.walk.good()[0]
            self.assertEqual(self.drive(name, waste_one), [1.0], name)
            self.assertEqual(self.drive(name, lambda t: None), [], name)

    def test_the_board_keeps_its_size_from_rung_to_rung(self):
        from neural_workshop.ui.longwalk import LongWayRound
        from uisupport import close_overlays, reset_window
        close_overlays()
        task = LongWayRound()
        sizes = set()
        try:
            for rung in (1, 6, 14):
                task.rng = random.Random(rung)
                task.start_rung, task.total_trials = rung, 1
                task.adaptive = False
                task.start_run()
                sizes.add(round(task._board(0, 0, 800, 600)[2], 6))
        finally:
            task.close()
            close_overlays()
            reset_window()
        self.assertEqual(len(sizes), 1)


if __name__ == '__main__':
    unittest.main()
