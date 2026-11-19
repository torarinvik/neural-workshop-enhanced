#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Held in mind: the deals, and the boundary.

The answers are checked against a board kept here, not against the
code that dealt them; and that the frame showing when the question is
put says nothing of the answer is checked by counting.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import Counter

from uisupport import close_overlays, reset_window

from neural_workshop import inmind, lookback

DEALS = 4000


class TheDeals(unittest.TestCase):

    def test_one_tile_changes_and_it_is_the_answer(self):
        for rung in range(1, 9):
            for seed in range(40):
                p = inmind.deal('changed', rung, random.Random(seed))
                first, second = p.data['tiles']
                differ = [place for place in range(inmind.PLACES)
                          if first[place] != second[place]]
                self.assertEqual(differ, [p.answer])
                self.assertEqual(p.frames, (0,) + (-1,) * (rung - 1) + (1,))
                self.assertEqual(p.open_at, rung * lookback.FRAME)

    def test_the_light_is_where_a_board_kept_here_has_it(self):
        for rung in range(1, 9):
            for seed in range(40):
                p = inmind.deal('swapped', rung, random.Random(seed))
                board = [place == p.frames[0]
                         for place in range(inmind.PLACES)]
                self.assertEqual(len(p.data['pairs']), rung)
                for a, b in p.data['pairs']:
                    self.assertNotEqual(a, b)
                    board[a], board[b] = board[b], board[a]
                self.assertEqual(board.index(True), p.answer)
                self.assertEqual(len(p.frames), rung + 1)
                self.assertEqual(p.open_at, rung * lookback.FRAME)

    def test_the_tiles_showing_do_not_say_which_changed(self):
        # Whatever hue a tile shows the second time, it is the one that
        # changed a quarter of the time.
        rng, seen, changed = random.Random(7), Counter(), Counter()
        for _deal in range(DEALS):
            p = inmind.deal('changed', 2, rng)
            for place, hue in enumerate(p.data['tiles'][1]):
                seen[place, hue] += 1
                changed[place, hue] += place == p.answer
        for key, count in seen.items():
            self.assertAlmostEqual(changed[key] / count, 0.25, delta=0.09)

    def test_the_boxes_joined_last_do_not_say_where_the_light_is(self):
        # Each box of the last pair, and each box outside it, holds
        # the light a quarter of the time.
        rng = random.Random(7)
        for rung in (1, 3):
            inside = Counter()
            for _deal in range(DEALS):
                p = inmind.deal('swapped', rung, rng)
                last = p.data['pairs'][-1]
                inside[p.answer == last[0], p.answer == last[1]] += 1
            self.assertAlmostEqual(inside[True, False] / DEALS, 0.25,
                                   delta=0.03)
            self.assertAlmostEqual(inside[False, True] / DEALS, 0.25,
                                   delta=0.03)

    def test_the_light_moves_half_the_time_at_the_first_rung(self):
        rng = random.Random(3)
        moved = sum(p.answer != p.frames[0] for p in
                    (inmind.deal('swapped', 1, rng) for _d in range(DEALS)))
        self.assertAlmostEqual(moved / DEALS, 0.5, delta=0.03)


class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, name, pick, rung=1, early=None):
        """Scalars paid for one trial: *early* is pressed before the
        question is put, *pick* chooses once it is."""
        from nwenv import catalog
        env = catalog.env_class(name)(seed=1, rung=rung, trials=1,
                                      adaptive=False)
        scalars = []
        try:
            for _step in range(900):
                task = env.task
                port = None
                if task.phase == 'playing' and task.run is not None:
                    port = pick(task) if task.run.open else early
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_the_right_answer_is_paid(self):
        for name in ('changed_tile', 'swapped_boxes'):
            for rung in (1, 3):
                self.assertEqual(self.drive(
                    name, lambda t: t.puzzle.answer, rung), [1.0])

    def test_a_wrong_one_is_not(self):
        for name in ('changed_tile', 'swapped_boxes'):
            self.assertEqual(self.drive(
                name, lambda t: (t.puzzle.answer + 1) % inmind.PLACES),
                [-1.0])

    def test_a_press_before_the_question_is_ignored(self):
        for name in ('changed_tile', 'swapped_boxes'):
            self.assertEqual(self.drive(
                name, lambda t: t.puzzle.answer, early=0), [1.0])

    def test_no_answer_is_a_loss(self):
        for name in ('changed_tile', 'swapped_boxes'):
            self.assertEqual(self.drive(name, lambda t: None), [-1.0])


if __name__ == '__main__':
    unittest.main()
