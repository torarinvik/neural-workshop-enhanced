#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sokoban: the generator's guarantees and the solver's word.

The module promises three things — every level solvable, difficulty
certified rather than asserted, and the C kernel agreeing with the
Python search to the push. Each promise gets held here.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import time
import unittest

from uisupport import (SokobanTask, TASKS, close_overlays, key, needs_ui,
                       reset_window, state, taskoptions)

from neural_workshop import sokoban
from neural_workshop.sokoban import (GRADES, Level, generate, live_cells,
                                     solve, solve_bounded, _solve_py)


def tiny_level():
    """A hand-built 5x4: one box, two pushes, no tricks.

        #####
        #@$.#      -> the box rolls right onto the goal in one push;
        #...#         the second row keeps the player region honest.
        #####
    """
    width, height = 5, 4
    walls = frozenset(
        cell for cell in range(width * height)
        if cell % width in (0, width - 1) or cell // width in (0, height - 1))
    return Level(width, height, walls, goals=frozenset({8}),
                 boxes=frozenset({7}), player=6, minimum=None,
                 at_least=0, bound=1)


class SolverTests(unittest.TestCase):

    def test_the_tiny_level_needs_exactly_one_push(self):
        self.assertEqual(solve(tiny_level()), 1)

    def test_a_solved_level_needs_zero(self):
        level = tiny_level()._replace(boxes=frozenset({8}))
        self.assertEqual(solve(level), 0)

    def test_a_dead_corner_is_recognised(self):
        # Box pushed into the top-left floor corner, goal elsewhere.
        level = tiny_level()._replace(boxes=frozenset({6}), player=7)
        alive = live_cells(level.width, level.height, level.walls,
                           level.goals)
        self.assertNotIn(6, alive)
        self.assertIsNone(solve(level))

    def test_the_budget_returns_a_proven_lower_bound(self):
        level = generate(8, seed=3)
        minimum, proven = solve_bounded(level, budget=200)
        self.assertIsNone(minimum)
        self.assertGreater(proven, 0)
        exact = solve(level)
        self.assertIsNotNone(exact)
        self.assertLessEqual(proven, exact)

    def test_c_and_python_agree_to_the_push(self):
        if sokoban._native is None:
            self.skipTest('C kernel not built')
        for rung in (1, 3, 5, 7):
            for seed in range(3):
                level = generate(rung, seed=seed)
                py = _solve_py(level, 300000)
                native = sokoban._solve_native(level, 300000)
                self.assertEqual(py[0], native[0], (rung, seed))


class GeneratorTests(unittest.TestCase):

    def test_every_rung_generates_and_clears_its_floor(self):
        for rung, grade in enumerate(GRADES, start=1):
            level = generate(rung, seed=11)
            certified = (level.minimum if level.minimum is not None
                         else level.at_least)
            self.assertGreaterEqual(certified, grade.floor,
                                    'rung %d below its floor' % rung)
            self.assertEqual(len(level.boxes), grade.boxes)
            self.assertLessEqual(certified, level.bound)

    def test_generated_levels_are_actually_solvable(self):
        for rung in (2, 5, 8):
            level = generate(rung, seed=7)
            self.assertIsNotNone(solve(level))

    def test_boxes_start_off_their_goals_enough_to_matter(self):
        level = generate(6, seed=5)
        off = sum(1 for box in level.boxes if box not in level.goals)
        self.assertGreaterEqual(off, len(level.goals) // 2)

    def test_the_same_seed_deals_the_same_level(self):
        self.assertEqual(generate(4, seed=42), generate(4, seed=42))

    def test_the_superhuman_rung_carries_a_certificate(self):
        level = generate(16, seed=1)
        certified = (level.minimum if level.minimum is not None
                     else level.at_least)
        self.assertGreaterEqual(certified, GRADES[15].floor)

    def test_every_trap_rung_delivers_its_landmines(self):
        from neural_workshop.sokoban import _floor_flags
        for rung in (6, 10, 14):
            grade = GRADES[rung - 1]
            level = generate(rung, seed=17)
            flags = _floor_flags(level.width, level.height, level.walls)
            share = len(level.traps) / sum(flags)
            self.assertGreaterEqual(share, grade.trap_share - 0.02,
                                    'rung %d short on traps' % rung)

    def test_traps_really_are_deadly(self):
        """A box parked on any reported trap makes the level lost."""
        level = generate(6, seed=17)
        self.assertTrue(level.traps)
        trap = min(level.traps)
        doomed = level._replace(
            boxes=frozenset(list(level.boxes - {min(level.boxes)})
                            + [trap]))
        self.assertIsNone(solve(doomed))

    def test_a_dug_pocket_has_one_entrance(self):
        """The trap digger only ever carves single-door pockets."""
        from neural_workshop.sokoban import (_blob_goals, _carve_room,
                                             _dig_traps, _floor_flags,
                                             _steps)
        import random
        rng = random.Random(5)
        grade = GRADES[13]
        walls = _carve_room(grade, rng)
        goals = _blob_goals(grade.width, grade.height, walls,
                            grade.boxes, rng)
        self.assertIsNotNone(goals)
        dug = _dig_traps(grade.width, grade.height, walls, goals,
                         grade.trap_share, rng)
        flags = _floor_flags(grade.width, grade.height, dug)
        for cell in walls - dug:          # every newly carved pocket
            doors = sum(1 for step in _steps(grade.width)
                        if flags[cell + step])
            self.assertEqual(doors, 1)

    def test_the_matching_bound_never_exceeds_the_minimum(self):
        from neural_workshop.sokoban import matching_bound
        for rung in (3, 6, 9):
            level = generate(rung, seed=13)
            if level.minimum is not None:
                self.assertLessEqual(matching_bound(level),
                                     level.minimum)


@needs_ui
class SokobanScreenTests(unittest.TestCase):

    def setUp(self):
        close_overlays()
        self.task = SokobanTask()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.start_rung = 1
        self.task.rung = 1

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _solve_by_search(self):
        """Follow the solver's answer by replaying pushes greedily."""
        from neural_workshop.sokoban import _floor_flags, _reachable, _steps
        level = self.task.level
        # Breadth-first once more, remembering the first move of the
        # winning line, then walking the player there push by push.
        while not (self.task.boxes <= level.goals):
            width = level.width
            flags = _floor_flags(width, level.height, level.walls)
            best = None
            for box in self.task.boxes:
                for step in _steps(width):
                    behind, ahead = box - step, box + step
                    region = _reachable(width, flags, self.task.boxes,
                                        self.task.player)
                    if behind not in region or not flags[ahead] \
                            or ahead in self.task.boxes:
                        continue
                    trial = Level(width, level.height, level.walls,
                                  level.goals,
                                  (self.task.boxes - {box}) | {ahead},
                                  box, None, 0, 0)
                    after = solve(trial)
                    if after is not None and (best is None
                                              or after < best[0]):
                        best = (after, box, step, behind)
            self.assertIsNotNone(best, 'no improving push found')
            _after, box, step, behind = best
            self._walk_to(behind)
            dx = {1: (1, 0), -1: (-1, 0)}.get(step)
            if dx is None:
                dx = (0, 1) if step > 0 else (0, -1)
            self.task.step(*dx)

    def _walk_to(self, cell):
        """Teleport the walk: legality is the solver's business, and
        these tests only need the player standing somewhere reachable."""
        from neural_workshop.sokoban import _floor_flags, _reachable
        level = self.task.level
        flags = _floor_flags(level.width, level.height, level.walls)
        region = _reachable(level.width, flags, self.task.boxes,
                            self.task.player)
        self.assertIn(cell, region)
        self.task.player = cell

    def test_it_is_in_the_planning_category(self):
        self.assertIn('sokoban',
                      [task for task, _name in TASKS['planning']])

    def test_starting_deals_a_level_with_a_par_line(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'pushing')
        self.assertIn('pushes', self.task.message)
        self.task.on_draw()

    def test_a_wall_refuses_the_step(self):
        self.task.start_run()
        level = self.task.level
        # March into the nearest wall; position must survive.
        for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)):
            before = self.task.player
            for _step in range(level.width):
                self.task.step(dx, dy)
            self.assertNotIn(self.task.player, level.walls)

    def test_undo_takes_back_a_push(self):
        self.task.start_run()
        before_boxes = self.task.boxes
        before_player = self.task.player
        moved = False
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            self.task.step(dx, dy)
            if (self.task.player, self.task.boxes) != (before_player,
                                                       before_boxes):
                moved = True
                break
        self.assertTrue(moved)
        self.task.undo()
        self.assertEqual(self.task.boxes, before_boxes)
        self.assertEqual(self.task.player, before_player)

    def test_restart_rewinds_the_level_whole(self):
        self.task.start_run()
        for dx, dy in ((1, 0), (0, 1), (1, 0), (0, 1)):
            self.task.step(dx, dy)
        self.task.restart()
        self.assertEqual(self.task.boxes, self.task.level.boxes)
        self.assertEqual(self.task.player, self.task.level.player)
        self.assertEqual(self.task.pushes, 0)

    def test_solving_scores_and_space_deals_the_next(self):
        self.task.start_run()
        self._solve_by_search()
        self.assertEqual(self.task.phase, 'solved')
        rung, pushes, par, certified = self.task.results[-1]
        self.assertTrue(certified)
        self.assertGreaterEqual(pushes, par)
        self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.phase, 'pushing')
        self.assertEqual(self.task.trial, 2)

    def test_the_run_ends_with_a_tally(self):
        self.task.start_run()
        for _trial in range(2):
            self._solve_by_search()
            self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.phase, 'done')
        tally = self.task.score()
        self.assertEqual(tally['solved'], 2)
        self.assertGreaterEqual(tally['efficiency'], 50)
        self.task.on_draw()

    def test_adaptive_climbs_on_a_near_minimum_solve(self):
        self.task.adaptive = True
        self.task.start_run()
        was = self.task.rung
        self._solve_by_search()
        if self.task.pushes <= self.task.par() * 1.4:
            self.assertEqual(self.task.rung, was + 1)

    def test_it_has_an_options_screen(self):
        self.assertTrue(taskoptions.has_options('sokoban'))
        note = taskoptions.SOKOBAN.note(
            {'SOKOBAN_LEVEL': 16, 'SOKOBAN_ADAPTIVE': True})
        self.assertIn('lower bound', note)
