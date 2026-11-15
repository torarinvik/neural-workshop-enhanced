#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Where Was It?: the rooms, the change, picking, the boundary, the
screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive
from uisupport import close_overlays, needs_ui, reset_window

from neural_workshop import rooms as R


def where(room):
    return {t.cell: (t.kind, t.colour) for t in room.things}


class TheLadder(unittest.TestCase):

    def test_the_parts_come_in_on_their_rungs(self):
        self.assertEqual([R.grade(r).rooms for r in (3, 4, 7, 13, 20)],
                         [1, 2, 3, 4, 5])
        self.assertFalse(R.grade(9).shared)
        self.assertTrue(R.grade(10).shared)
        self.assertEqual(R.grade(15).turn, (0.0, 0.0))
        self.assertGreater(R.grade(16).turn[0], 0)


class TheChange(unittest.TestCase):

    def test_the_answer_is_exactly_what_changed(self):
        for rung in (2, 6, 9, 12, 18, 24):
            for seed in range(30):
                p = R.deal(rung, seed=seed)
                before = where(p.rooms[p.tested])
                after = where(p.changed)
                differ = {c for c in set(before) | set(after)
                          if before.get(c) != after.get(c)}
                if p.change == 'moved':
                    self.assertEqual(len(differ), 2)
                    self.assertEqual(set(p.answer) & set(before), set())
                    self.assertTrue(set(p.answer) <= differ)
                else:
                    self.assertEqual(differ, set(p.answer), (rung, seed))

    def test_shared_rooms_hold_the_same_things(self):
        p = R.deal(11, seed=3)
        sets = [sorted((t.kind, t.colour) for t in room.things)
                for room in p.rooms]
        self.assertTrue(all(s == sets[0] for s in sets))
        self.assertGreater(len({tuple(t.cell for t in room.things)
                                for room in p.rooms}), 1)

    def test_near_moves_from_rung_twenty(self):
        for seed in range(30):
            p = R.deal(22, seed=seed)
            if p.change != 'moved':
                continue
            to = p.answer[0]
            moved = next(t for t in p.changed.things if t.cell == to)
            was = next(t.cell for t in p.rooms[p.tested].things
                       if t.colour == moved.colour)
            self.assertIn(to, R._neighbours(was, p.cols, p.rows))


class Picking(unittest.TestCase):

    def test_a_bare_square_is_picked_at_its_middle(self):
        p = R.deal(17, seed=4)
        room = p.changed._replace(things=())
        painted = R.scene(p.cols, p.rows, room, p.angle)
        cam = R.camera(p.cols, p.rows, p.angle)
        for cell in range(p.cols * p.rows):
            x, y = cam.project((cell % p.cols + 0.5, 0.0,
                                cell // p.cols + 0.5))
            self.assertEqual(R.pick(painted, x, y), cell)

    def test_a_thing_is_picked_as_its_square(self):
        p = R.deal(5, seed=1)
        painted = R.scene(p.cols, p.rows, p.changed)
        cam = R.camera(p.cols, p.rows)
        thing = p.changed.things[0]
        top = (thing.cell % p.cols + 0.5, thing.size * 0.5,
               thing.cell // p.cols + 0.5)
        self.assertEqual(R.pick(painted, *cam.project(top)), thing.cell)


def answer(task):
    from nwenv.rooms import NEXT
    return NEXT if not task.testing else task.puzzle.answer[0]


def off(task):
    from nwenv.rooms import NEXT
    if not task.testing:
        return NEXT
    p = task.puzzle
    return next(c for c in range(p.cols * p.rows) if c not in p.answer)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (2, 14, 22):
            self.assertEqual(drive('where_was_it', rung, answer), [1.0])
            self.assertEqual(drive('where_was_it', rung, off), [-1.0])

    def test_a_square_cannot_be_clicked_while_studying(self):
        from neural_workshop.ui.rooms import WhereWasIt
        close_overlays()
        task = WhereWasIt()
        try:
            task.rng = random.Random(2)
            task.start_rung, task.total_trials = 8, 1
            task.adaptive = False
            task.start_run()
            task.steer(task.puzzle.answer[0])
            self.assertEqual(task.phase, 'playing')
        finally:
            task.close()
            close_overlays()
            reset_window()


@needs_ui
class TheScreen(unittest.TestCase):

    def test_a_click_on_the_changed_square_passes(self):
        from neural_workshop.ui.rooms import WhereWasIt
        close_overlays()
        task = WhereWasIt()
        try:
            for seed in range(12):
                task.rng = random.Random(seed)
                task.start_rung, task.total_trials = 6, 1
                task.adaptive = False
                task.start_run()
                for _k in range(len(task.puzzle.rooms)):
                    task.on_draw()
                    task.next_room()
                task.on_draw()
                p = task.puzzle
                cam = R.camera(p.cols, p.rows, p.angle)
                cell = p.answer[0]
                mid = cam.project((cell % p.cols + 0.5, 0.05,
                                   cell // p.cols + 0.5))
                if R.pick(task.painted, *mid) != cell:
                    continue         # hidden behind something; try another
                task._click(*task.place(*mid), button=1)
                self.assertTrue(task.verdict_shown[0])
                return
            self.fail('no seed left the square in view')
        finally:
            task.close()
            close_overlays()
            reset_window()


if __name__ == '__main__':
    unittest.main()
