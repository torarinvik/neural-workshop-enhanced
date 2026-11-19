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
    """Presses on the shortest way from the start to done, searched over
    (square, holding the key)."""
    doors, goal = p.data['doors'], p.data['goal']
    key = p.data.get('key')
    start = p.start
    seen = {start: 0}
    queue = deque([start])
    while queue:
        (x, y), held = state = queue.popleft()
        if (x, y) == goal and held:
            return seen[state]
        for dx, dy in ministeps.STEPS:
            to = (x + dx, y + dy)
            if frozenset(((x, y), to)) not in doors:
                continue
            if to == goal and not held:
                continue
            nxt = (to, held or to == key)
            if nxt not in seen:
                seen[nxt] = seen[state] + 1
                queue.append(nxt)
    return None


class TheDeals(unittest.TestCase):

    def test_rung_k_is_k_presses_on_the_shortest_way(self):
        for rung in range(1, 21):
            for seed in range(5):
                p = longwalk.deal('walk', rung, random.Random(seed))
                self.assertEqual(p.par, rung)
                self.assertEqual(shortest(p), rung)
                self.assertEqual(longwalk.far(p, p.start), rung)

    def test_the_key_walk_is_one_press_longer_and_goes_by_the_key(self):
        for rung in range(1, 16):
            for seed in range(5):
                p = longwalk.deal('key', rung, random.Random(seed))
                self.assertEqual(p.par, rung + 1)
                self.assertEqual(shortest(p), rung + 1)
                self.assertNotEqual(p.start[0], p.data['key'])
                self.assertNotEqual(p.data['key'], p.data['goal'])

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

    def test_the_door_is_a_wall_until_the_key_is_held(self):
        for seed in range(60):
            p = longwalk.deal('key', 2, random.Random(seed))
            goal = p.data['goal']
            for square in p.data['to_goal']:
                for port, (dx, dy) in enumerate(ministeps.STEPS):
                    if (square[0] + dx, square[1] + dy) == goal and \
                            frozenset((square, goal)) in p.data['doors']:
                        self.assertEqual(
                            longwalk.move(p, (square, False), port),
                            (square, False))
                        self.assertEqual(
                            longwalk.move(p, (square, True), port),
                            (goal, True))

    def test_random_presses_at_rung_one(self):
        for kind, share in (('walk', 0.45), ('key', 0.17)):
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
        for name in ('long_way_round', 'key_and_door'):
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
