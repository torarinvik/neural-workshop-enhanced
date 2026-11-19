#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""More forgiving walks: the deals, the steps, and the boundary.

The shortest ways are found here by a search forwards from the start
under rules written out again in this file, not by the dealer's own
distances.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import deque

from neural_workshop import morewalks

#: Up, down, left, right.
WAYS = ((0, 1), (0, -1), (-1, 0), (1, 0))
SIDE = 7


def inside(c):
    return 0 <= c[0] < SIDE and 0 <= c[1] < SIDE


def step(p, state, way):
    """The rules again, from the module's docstring."""
    dx, dy = WAYS[way]
    d = p.data
    if p.kind == 'pushpull':
        me, box = state
        to = (me[0] + dx, me[1] + dy)
        free = lambda c: inside(c) and c not in d['blocks']  # noqa: E731
        if not free(to):
            return state
        if to == box:
            on = (box[0] + dx, box[1] + dy)
            return (to, on) if free(on) else state
        behind = (me[0] - dx, me[1] - dy)
        return (to, me) if box == behind else (to, box)
    (me,) = state
    if p.kind == 'oneway':
        to = (me[0] + dx, me[1] + dy)
        ok = frozenset((me, to)) in d['doors'] or (me, to) in d['oneway']
        return (to,) if ok else state
    while inside((me[0] + dx, me[1] + dy)) and \
            (me[0] + dx, me[1] + dy) not in d['blocks']:
        me = (me[0] + dx, me[1] + dy)
    return (me,)


def finished(p, state):
    return state[-1 if p.kind == 'pushpull' else 0] == p.data['goal']


def shortest(p):
    seen = {p.start: 0}
    queue = deque([p.start])
    while queue:
        s = queue.popleft()
        if finished(p, s):
            return seen[s]
        for way in range(4):
            t = step(p, s, way)
            if t not in seen:
                seen[t] = seen[s] + 1
                queue.append(t)
    return None


class TheDeals(unittest.TestCase):

    def test_rung_k_is_k_presses_on_the_shortest_way(self):
        for kind in morewalks.KINDS:
            top = 10 if kind == 'ice' else 16
            for rung in range(1, top + 1):
                for seed in range(3):
                    p = morewalks.deal(kind, rung, random.Random(seed))
                    self.assertEqual(p.par, rung, (kind, rung))
                    self.assertEqual(shortest(p), rung, (kind, rung))

    def test_ice_tops_out_at_rung_ten(self):
        p = morewalks.deal('ice', 14, random.Random(1))
        self.assertEqual(p.par, 10)
        self.assertEqual(shortest(p), 10)

    def test_the_board_and_ports_are_the_same_on_every_rung(self):
        for kind in morewalks.KINDS:
            for rung in (1, 5, 9):
                p = morewalks.deal(kind, rung, random.Random(rung))
                self.assertEqual(p.data['side'], SIDE)
                self.assertEqual(p.ports, 4)
                self.assertEqual(p.limit, rung + max(2, rung // 2))

    def test_the_moves_follow_the_rules_written_here(self):
        for kind in morewalks.KINDS:
            rng = random.Random(4)
            for _d in range(20):
                p = morewalks.deal(kind, 4, rng)
                state = p.start
                for _press in range(30):
                    way = rng.randrange(4)
                    self.assertEqual(morewalks.move(p, state, way),
                                     step(p, state, way))
                    state = step(p, state, way)


class TheSteps(unittest.TestCase):

    def test_a_push_is_undone_by_a_pull(self):
        undone = 0
        for seed in range(80):
            p = morewalks.deal('pushpull', 5, random.Random(seed))
            me, box = p.start
            for way, (dx, dy) in enumerate(WAYS):
                if (me[0] + dx, me[1] + dy) != box:
                    continue
                pushed = morewalks.move(p, p.start, way)
                if pushed == p.start:
                    continue
                back = way ^ 1
                self.assertEqual(morewalks.move(p, pushed, back), p.start)
                undone += 1
        self.assertGreater(undone, 5)

    def test_a_one_way_opening_lets_one_way_through(self):
        for seed in range(20):
            p = morewalks.deal('oneway', 3, random.Random(seed))
            for a, b in p.data['oneway']:
                way = WAYS.index((b[0] - a[0], b[1] - a[1]))
                self.assertEqual(morewalks.move(p, (a,), way), (b,))
                self.assertEqual(morewalks.move(p, (b,), way ^ 1), (b,))

    def test_a_wrong_press_costs_a_step_and_the_walk_goes_on(self):
        for kind in morewalks.KINDS:
            for seed in range(20):
                p = morewalks.deal(kind, 3, random.Random(seed))
                walk = morewalks.Walk(p)
                bad = [w for w in range(4) if w not in walk.good()]
                walk.press(bad[0])
                self.assertIsNone(walk.result)
                while walk.result is None:
                    walk.press(walk.good()[0])
                self.assertTrue(walk.result[0] or walk.presses == p.limit)

    def test_the_last_step_ends_it(self):
        for kind in morewalks.KINDS:
            p = morewalks.deal(kind, 3, random.Random(2))
            walk = morewalks.Walk(p)
            while walk.result is None:
                walk.press([w for w in range(4)
                            if w not in walk.good()][0])
            self.assertFalse(walk.result[0])
            self.assertEqual(walk.presses, p.limit)

    def test_random_presses_are_paid_as_the_docstring_says(self):
        table = {'pushpull': (0.37, 0.04, 0.01),
                 'oneway': (0.44, 0.06, 0.01),
                 'ice': (0.44, 0.08, 0.01)}
        for kind, shares in table.items():
            for rung, share in zip((1, 3, 5), shares):
                rng, wins = random.Random(11), 0
                for _d in range(400):
                    walk = morewalks.Walk(morewalks.deal(kind, rung, rng))
                    while walk.result is None:
                        walk.press(rng.randrange(4))
                    wins += walk.result[0]
                self.assertAlmostEqual(wins / 400, share, delta=0.06,
                                       msg=(kind, rung))


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
        for name in ('push_and_pull', 'one_way_doors', 'ice_floor'):
            self.assertEqual(self.drive(name, lambda t: t.walk.good()[0]),
                             [1.0], name)
            self.assertEqual(self.drive(name, lambda t: next(
                p for p in range(4) if p not in t.walk.good())), [-1.0])

            def waste_one(task):
                if task.walk.presses == 0:
                    return next(p for p in range(4)
                                if p not in task.walk.good())
                return task.walk.good()[0]
            # Par 3 allows five: a wasted press can cost two to undo.
            self.assertEqual(self.drive(name, waste_one), [1.0], name)
            self.assertEqual(self.drive(name, lambda t: None), [], name)

    def test_the_board_keeps_its_size_from_rung_to_rung(self):
        from neural_workshop.ui.morewalks import PushAndPull
        from uisupport import close_overlays, reset_window
        close_overlays()
        task = PushAndPull()
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
