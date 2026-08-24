#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The N-in-a-row generator, board, screen, and agent boundary."""
from __future__ import annotations

import unittest

from uisupport import (NInARow, TASKS, close_overlays, key, needs_ui,
                       reset_window)

from neural_workshop import ninarow as N


class GeneratorTests(unittest.TestCase):
    def test_every_grade_has_one_and_only_one_winning_cell(self):
        for rung in range(1, len(N.GRADES) + 1):
            puzzle = N.generate(rung, seed=17)
            self.assertIsNotNone(puzzle, rung)
            self.assertEqual(puzzle.length, N.GRADES[rung - 1].length)
            self.assertEqual(puzzle.winning_moves, (puzzle.answer,), rung)
            self.assertFalse(N.winner(puzzle.cells, puzzle.size, N.PLAYER,
                                       puzzle.length))
            self.assertFalse(N.winner(puzzle.cells, puzzle.size, N.OPPONENT,
                                       puzzle.length))
            self.assertEqual(sum(value != N.EMPTY for value in puzzle.cells),
                             puzzle.pellets)

    def test_same_seed_repeats_the_same_scenario(self):
        self.assertEqual(N.generate(8, seed=4), N.generate(8, seed=4))

    def test_different_seed_changes_the_scenario(self):
        self.assertNotEqual(N.generate(5, seed=4), N.generate(5, seed=5))

    def test_custom_grid_and_pellet_dials(self):
        puzzle = N.generate(1, seed=4, size=9, pellets=30)
        self.assertEqual(puzzle.size, 9)
        self.assertEqual(puzzle.pellets, 30)
        self.assertEqual(puzzle.winning_moves, (puzzle.answer,))

    def test_custom_length_and_machine_rung(self):
        puzzle = N.generate(9, seed=4)
        self.assertEqual((puzzle.size, puzzle.length), (128, 100))
        self.assertEqual(puzzle.winning_moves, (puzzle.answer,))
        custom = N.generate(1, seed=4, size=12, pellets=60, length=7)
        self.assertEqual((custom.size, custom.length), (12, 7))
        self.assertEqual(custom.winning_moves, (custom.answer,))

    def test_line_and_cell_coordinates_agree(self):
        line = N.line_cells(7, 1, 1, 1, 1)
        self.assertEqual(line, (8, 16, 24, 32, 40))
        for cell in line:
            row, col = N.cell_row_col(cell, 7)
            self.assertEqual(N.cell_index(row, col, 7), cell)

    def test_ascii_board_has_the_expected_shape(self):
        puzzle = N.generate(1, seed=2)
        rows = N.board_text(puzzle).splitlines()
        self.assertEqual(len(rows), puzzle.size)
        self.assertTrue(all(len(row) == puzzle.size for row in rows))
        self.assertIn('X', N.board_text(puzzle))
        self.assertIn('O', N.board_text(puzzle))


@needs_ui
class ScreenTests(unittest.TestCase):
    def setUp(self):
        close_overlays()
        self.task = NInARow()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.start_rung = self.task.rung = 1

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def open_one(self, rung=1):
        self.task.start_rung = self.task.rung = rung
        self.task.start_run()
        self.assertEqual(self.task.phase, 'asking')
        self.assertIsNotNone(self.task.puzzle)

    def test_it_is_in_the_planning_category_and_has_options(self):
        self.assertIn('n_in_a_row',
                      [task for task, _name in TASKS['planning']])
        from neural_workshop.ui import taskoptions
        self.assertTrue(taskoptions.has_options('n_in_a_row'))

    def test_a_position_opens_and_draws(self):
        self.open_one()
        self.task.on_draw()
        self.assertEqual(len(self.task.puzzle.cells),
                         self.task.puzzle.size ** 2)

    def test_the_superhuman_position_opens_and_draws(self):
        self.open_one(9)
        self.task.on_draw()
        self.assertEqual((self.task.puzzle.size, self.task.puzzle.length),
                         (128, 100))

    def test_arrows_move_the_highlight_without_leaving_the_board(self):
        self.open_one()
        self.task.choice = 0
        self.task.move(-1, 0)
        self.assertEqual(self.task.choice, 0)
        self.task.move(0, -1)
        self.assertEqual(self.task.choice, 0)
        self.task.move(1, 0)
        self.assertEqual(self.task.choice, self.task.puzzle.size)

    def test_enter_answers_the_highlighted_cell(self):
        self.open_one()
        self.task.choice = self.task.puzzle.answer
        self.task.on_key_press(key.ENTER, 0)
        self.assertEqual(self.task.phase, 'judged')
        self.assertTrue(self.task.verdict_shown[0])

    def test_wrong_cell_is_red_and_answer_is_marked_afterwards(self):
        self.open_one()
        wrong = next(cell for cell, value in enumerate(self.task.puzzle.cells)
                     if value == N.EMPTY and cell != self.task.puzzle.answer)
        self.task.choose(wrong)
        self.assertEqual(self.task.phase, 'judged')
        self.assertFalse(self.task.verdict_shown[0])

    def test_a_pellet_is_not_a_move(self):
        self.open_one()
        occupied = next(cell for cell, value in enumerate(self.task.puzzle.cells)
                        if value != N.EMPTY)
        self.task.choose(occupied)
        self.assertEqual(self.task.phase, 'asking')

    def test_next_position_clears_the_verdict(self):
        self.open_one()
        self.task.choose(self.task.puzzle.answer)
        self.task.advance()
        self.assertEqual(self.task.phase, 'asking')
        self.assertIsNone(self.task.verdict_shown)

    def test_clock_is_swappable(self):
        self.task.clock = lambda: 100.0
        self.open_one()
        self.task.clock = lambda: 106.5
        self.task.choose(self.task.puzzle.answer)
        self.assertAlmostEqual(self.task.results[-1][2], 6.5)

    def test_board_stays_above_the_verdict_band(self):
        from neural_workshop import geometry, state
        for width, height in ((800, 600), (1280, 720), (1024, 768)):
            state.window.set_size(width, height)
            geometry._size_changed()
            self.open_one(8)
            left, bottom, side = self.task._board_box()
            self.assertGreaterEqual(bottom, self.task._floor())
            self.assertLessEqual(left + side, state.window.width)
            self.assertGreaterEqual(left, 0)


@needs_ui
class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_the_agent_can_answer_a_position_through_its_ports(self):
        from nwenv import catalog
        env = catalog.env_class('n_in_a_row')(
            seed=0, rung=1, trials=1, grid=5, pellets=8, adaptive=False)
        try:
            _obs, _events, _done = env.step(None)
            answer = env.task.puzzle.answer
            _obs, events, done = env.step(answer)
            self.assertIn(1.0, [event['scalar'] for event in events
                                if event.get('type') == 'outcome'])
            self.assertFalse(done)
        finally:
            env.close()

    def test_a_port_outside_the_current_board_is_silent(self):
        from nwenv import catalog
        env = catalog.env_class('n_in_a_row')(
            seed=0, rung=1, trials=1, grid=5, pellets=8, adaptive=False)
        try:
            _obs, _events, _done = env.step(None)
            _obs, events, _done = env.step(360)
            self.assertFalse([event for event in events
                              if event.get('type') == 'outcome'])
            self.assertEqual(env.task.phase, 'asking')
        finally:
            env.close()

    def test_an_occupied_cell_is_silent_at_the_agent_boundary(self):
        from nwenv import catalog
        env = catalog.env_class('n_in_a_row')(
            seed=0, rung=1, trials=1, grid=5, pellets=8, adaptive=False)
        try:
            _obs, _events, _done = env.step(None)
            occupied = next(cell for cell, value in
                            enumerate(env.task.puzzle.cells)
                            if value != N.EMPTY)
            _obs, events, _done = env.step(occupied)
            self.assertFalse([event for event in events
                              if event.get('type') == 'outcome'])
            self.assertEqual(env.task.phase, 'asking')
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
