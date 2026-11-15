#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sokoban Live: the warehouse, the guards, the worker, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import sokobanlive as M


class TheWarehouse(unittest.TestCase):

    def test_the_worker_rests_between_steps(self):
        run = M.Run(M.deal(1, seed=1))
        start = run.player
        for d in range(4):
            to = start + run.delta(d)
            if not run.solid(to) and to not in run.boxes:
                break
        run.press(d)
        run.step(1 / 60.0)
        self.assertEqual(run.player, to)
        run.press((d ^ 1))
        run.step(1 / 60.0)
        self.assertEqual(run.player, to)
        for _k in range(20):
            run.step(1 / 60.0)
        self.assertEqual(run.player, start)

    def test_a_guard_turns_at_a_crate(self):
        cells = (10, 11, 12, 13)
        g = M.Guard(M.Patrol(cells, 2, 1, 0.0))
        g.beat(lambda c: c == 13)
        self.assertEqual(g.cell, 11)
        self.assertEqual(g.heading, -1)

    def test_meeting_a_guard_ends_the_trial(self):
        run = M.Run(M.deal(4, seed=2))
        run.player = run.guards[0].cell
        run.step(1 / 60.0)
        self.assertFalse(run.result[0])

    def test_the_plan_covers_every_pad(self):
        floor = M.deal(10, seed=3)
        room = floor.room
        plan = M.solve(room, room.boxes, room.player)
        boxes, at = set(room.boxes), room.player
        for d in plan:
            step = (-room.width, room.width, -1, 1)[d]
            if at + step in boxes:
                boxes.remove(at + step)
                boxes.add(at + 2 * step)
            at += step
        self.assertTrue(boxes >= set(room.goals))


class TheWorker(unittest.TestCase):

    def test_every_dealt_warehouse_is_cleared(self):
        for rung in (1, 4, 10, 13):
            for s in range(2):
                self.assertTrue(M.play(M.deal(rung, seed=s))[0], (rung, s))

    def test_doing_nothing_fails(self):
        self.assertFalse(M.play(M.deal(4, seed=1), lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = M.Pilot()
        self.assertEqual(drive('sokoban_live', 4,
                               lambda t: (pilot(t.run) or [None])[0],
                               seed=1, steps=4000), [1.0])
        self.assertEqual(drive('sokoban_live', 1, lambda t: None, seed=1,
                               steps=4000), [-1.0])


if __name__ == '__main__':
    unittest.main()
