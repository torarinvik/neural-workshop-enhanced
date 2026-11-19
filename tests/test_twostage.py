#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Forgiving walks in two stages: the boards, the rules, random presses
and the boundary.

The rules are worked out here, apart from the model: a search over
(square, stage) that knows only the blocks, the half-way point and the
end.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import deque

from neural_workshop import twostage

try:
    from uisupport import needs_ui
    from spatialsupport import drive
except Exception:                                      # pragma: no cover
    needs_ui = unittest.skip('no UI')
    drive = None

WAYS = ((0, 1), (0, -1), (-1, 0), (1, 0))      # up, down, left, right


def step(p, state, way):
    (x, y), stage = state
    d = p.data
    to = (x + way[0], y + way[1])
    if not (0 <= to[0] < 7 and 0 <= to[1] < 7) or to in d['blocks']:
        return state
    if p.kind == 'fetch':
        return (to, stage or to == d['thing'])
    if to == d['goal'] and not stage:
        return state
    return (to, stage or to == d['plate'])


def finished(p, state):
    end = p.data['mark'] if p.kind == 'fetch' else p.data['goal']
    return state[0] == end and state[1]


def shortest(p, start=None):
    start = start or p.start
    seen = {start: 0}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        if finished(p, state):
            return seen[state]
        for way in WAYS:
            nxt = step(p, state, way)
            if nxt not in seen:
                seen[nxt] = seen[state] + 1
                queue.append(nxt)
    return None


def reachable(p):
    seen, queue = {p.start}, deque([p.start])
    while queue:
        state = queue.popleft()
        for way in WAYS:
            nxt = step(p, state, way)
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


class TheBoards(unittest.TestCase):

    def test_rung_n_is_n_plus_one_presses_and_two_stages(self):
        for kind in twostage.KINDS:
            for rung in range(1, 16):
                for seed in range(4):
                    p = twostage.deal(kind, rung, random.Random(seed))
                    self.assertEqual(p.par, rung + 1)
                    self.assertEqual(shortest(p), rung + 1, (kind, rung))
                    self.assertEqual(twostage.far(p, p.start), rung + 1)
                    self.assertFalse(p.start[1])
                    self.assertEqual(p.limit,
                                     p.par + max(2, p.par // 2))

    def test_no_press_can_spoil_the_trial(self):
        for kind in twostage.KINDS:
            for seed in range(30):
                p = twostage.deal(kind, 4, random.Random(seed))
                for state in reachable(p):
                    self.assertIsNotNone(shortest(p, state), (kind, seed))
                    self.assertEqual(twostage.far(p, state),
                                     shortest(p, state))

    def test_the_end_without_the_half_way_point(self):
        for seed in range(30):
            p = twostage.deal('fetch', 3, random.Random(seed))
            self.assertFalse(finished(p, (p.data['mark'], False)))
            p = twostage.deal('plate', 3, random.Random(seed))
            goal = p.data['goal']
            for square in [(goal[0] - w[0], goal[1] - w[1]) for w in WAYS]:
                for port, way in enumerate(WAYS):
                    if (square[0] + way[0], square[1] + way[1]) == goal \
                            and square not in p.data['blocks'] \
                            and 0 <= square[0] < 7 and 0 <= square[1] < 7:
                        self.assertEqual(square, p.data['gate'])
                        self.assertEqual(
                            twostage.move(p, (square, False), port),
                            (square, False))
                        self.assertEqual(
                            twostage.move(p, (square, True), port),
                            (goal, True))

    def test_the_model_moves_as_worked_out_here(self):
        for kind in twostage.KINDS:
            rng = random.Random(5)
            for seed in range(20):
                p = twostage.deal(kind, 3, random.Random(seed))
                walk = twostage.Walk(p)
                state = p.start
                while walk.result is None:
                    port = rng.randrange(4)
                    state = step(p, state, WAYS[port])
                    walk.press(port)
                    self.assertEqual(walk.state, state)
                self.assertEqual(walk.result[0], finished(p, state))

    def test_a_port_order_turns_the_ports(self):
        p = twostage.deal('plate', 3, random.Random(1), order=(2, 3, 0, 1))
        q = twostage.deal('plate', 3, random.Random(1))
        self.assertEqual(p.data['blocks'], q.data['blocks'])
        for state in reachable(q):
            for port in range(4):
                self.assertEqual(twostage.move(p, state, port),
                                 twostage.move(q, state, (2, 3, 0, 1)[port]))


class RandomPresses(unittest.TestCase):

    def test_the_levels(self):
        for kind in twostage.KINDS:
            for rung, level in ((1, 0.125), (3, 0.02), (5, 0.004)):
                rng, wins, n = random.Random(1), 0, 3000
                for _d in range(n):
                    walk = twostage.Walk(twostage.deal(kind, rung, rng))
                    while walk.result is None:
                        walk.press(rng.randrange(4))
                    wins += walk.result[0]
                self.assertAlmostEqual(wins / n, level, delta=0.02,
                                       msg=(kind, rung))


def _good(task):
    return task.walk.good()[0]


def _bad(task):
    ok = task.walk.good()
    return next(p for p in range(4) if p not in ok)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_and_wrong(self):
        for task_id in ('fetch_and_carry', 'plate_and_gate'):
            for rung in (1, 6):
                self.assertEqual(drive(task_id, rung, _good, seed=2,
                                       steps=200), [1.0], (task_id, rung))
                self.assertEqual(drive(task_id, rung, _bad, seed=2,
                                       steps=200), [-1.0], (task_id, rung))


if __name__ == '__main__':
    unittest.main()
