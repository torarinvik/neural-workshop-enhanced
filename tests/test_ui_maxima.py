#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Every task must survive every option pushed to its maximum.

The options screens now offer far larger numbers than they used to,
on the promise that the caps sit exactly where the program stops
being able to deliver — the exact solver's cost for the salesman,
tile size for the jigsaw, and so on. That promise is only worth
something if the maxima are exercised: each test here sets every
numeric dial of one task to the top of its range, starts a run,
draws a trial, and cleans up.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from uisupport import (Concentration, Counting, GraphMapping, JigsawPuzzle,
                       Lookout, MatrixReasoning, MazeTask, MonkeyLadder,
                       MovingTargets, OutOfSight, Pursuit, SokobanTask,
                       NCupMonte, Recognition, Reflex, TowerOfHanoi,
                       TravelingSalesman, close_overlays, needs_ui,
                       reset_window, state, taskoptions)

from neural_workshop import datasets, media


def maxed(spec):
    """Every numeric option of *spec* at its largest value.

    Booleans and word choices keep their defaults — the point is the
    size dials, not the flavour switches.
    """
    chosen = {}
    for option in spec.options:
        if option.values and all(isinstance(v, (int, float))
                                 for v in option.values):
            chosen[option.key] = max(option.values)
    return chosen


def push(task_id):
    """Write the maxima for *task_id* into the live config."""
    spec = taskoptions.TASK_SPECS[task_id]
    written = maxed(spec)
    for key, value in written.items():
        state.cfg[key] = value
    return written


class StubLibrary:
    """A folder of stub image files, mostly hard links to one PNG.

    Recognition at its maximum plans five hundred trials, but only
    the shown trial ever loads its file, so the library only needs
    the *names* to exist — one real image and hard links is cheap.
    """

    STUB = datasets.Dataset(
        key='maxima-test', repo='x/y', split='train', column='image',
        kind='image', suffix='.png', rows=512, approx_bytes=1)

    def __enter__(self):
        import pyglet
        self.tmp = tempfile.mkdtemp()
        self.saved = datasets.datasets_dir
        datasets.datasets_dir = lambda: self.tmp
        folder = os.path.join(self.tmp, self.STUB.key)
        os.makedirs(folder, exist_ok=True)
        first = os.path.join(folder, '%07d.png' % 0)
        image = pyglet.image.SolidColorImagePattern(
            (90, 120, 200, 255)).create_image(96, 96)
        with open(first, 'wb') as handle:
            image.save(first, file=handle)
        for index in range(1, 512):
            os.link(first, os.path.join(folder, '%07d.png' % index))
        return self.STUB

    def __exit__(self, *ignored):
        datasets.datasets_dir = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)


@needs_ui
class MaximaTests(unittest.TestCase):

    def setUp(self):
        close_overlays()
        self.saved = {}

    def tearDown(self):
        for key, value in self.saved.items():
            state.cfg[key] = value
        close_overlays()
        reset_window()

    def _push(self, task_id):
        spec = taskoptions.TASK_SPECS[task_id]
        for option in spec.options:
            self.saved[option.key] = state.cfg[option.key]
        return push(task_id)

    def test_monkey_ladder_ten_by_ten_length_fifty(self):
        self._push('monkey_ladder')
        task = MonkeyLadder()
        try:
            self.assertEqual(task.grid, 10)
            task.start_round()
            self.assertEqual(len(task.sequence), 50)
            self.assertEqual(len(set(task.sequence)), 50)
            task.on_draw()
        finally:
            task.close()

    def test_ncup_monte_sixteen_cups(self):
        self._push('ncup_monte')
        task = NCupMonte()
        try:
            self.assertEqual(task.cups, 16)
            task.on_draw()
        finally:
            task.close()

    def test_concentration_fifty_pairs(self):
        self._push('concentration')
        with StubLibrary() as stub:
            task = Concentration()
            try:
                task.pool = media.MediaPool(stub, task.rng)
                self.assertTrue(task.deal())
                self.assertEqual(len(task.cards), 100)
                columns, rows = task._grid_shape()
                self.assertGreaterEqual(columns * rows, 100)
                task.on_draw()
            finally:
                task.close()

    def test_recognition_five_hundred_trials(self):
        self._push('recognition')
        with StubLibrary() as stub:
            task = Recognition()
            try:
                task.pool = media.MediaPool(stub, task.rng)
                self.assertTrue(task.start_run())
                self.assertEqual(len(task.trials), 500)
                task.on_draw()
            finally:
                task.close()

    def test_reflex_twelve_at_once(self):
        self._push('reflex')
        task = Reflex()
        try:
            self.assertEqual(task.max_active, 12)
            task.on_draw()
        finally:
            task.close()

    def test_count_sixty_shapes(self):
        self._push('count')
        task = Counting()
        try:
            self.assertEqual(task.count, 60)
            task.start_run()
            self.assertEqual(len(task.shapes_data), 60)
            task.on_draw()
        finally:
            task.close()

    def test_graph_mapping_sixteen_dots(self):
        self._push('graph_mapping')
        task = GraphMapping()
        try:
            task.start_run()
            self.assertEqual(task.graphs[0].size, 16)
            self.assertEqual(task.graphs[1].size, 16)
            task.on_draw()
        finally:
            task.close()

    def test_matrix_reasoning_hundred_puzzles(self):
        self._push('matrix_reasoning')
        task = MatrixReasoning()
        try:
            self.assertEqual(task.total_trials, 100)
            task.start_run()
            task.on_draw()
        finally:
            task.close()

    def test_jigsaw_ten_by_ten(self):
        self._push('jigsaw')
        with StubLibrary() as stub:
            task = JigsawPuzzle()
            try:
                task.pool = media.MediaPool(stub, task.rng)
                task.start_run()
                self.assertEqual(task.trial_side, 10)
                self.assertEqual(len(task.order), 100)
                task.on_draw()
            finally:
                task.close()

    def test_hanoi_twelve_disks(self):
        self._push('tower_of_hanoi')
        task = TowerOfHanoi()
        try:
            task.start_run()
            self.assertEqual(task.trial_disks, 12)
            self.assertEqual(task.par, 4095)
            task.on_draw()
        finally:
            task.close()

    def test_moving_targets_thirty_balls(self):
        self._push('moving_targets')
        task = MovingTargets()
        try:
            task.start_run()
            self.assertEqual(len(task.balls), 30)
            # Fifteen targets fits under the thirty-ball flock whole.
            self.assertEqual(task.tracked_now(), 15)
            for _frame in range(120):
                task._move(1 / 60.)
            task.on_draw()
        finally:
            task.close()

    def test_lookout_thirty_shapes(self):
        self._push('lookout')
        task = Lookout()
        try:
            task.watching = 'both'
            task.start_run()
            self.assertEqual(len(task.shapes), 30)
            for channel in task.channels():
                self.assertFalse(task.channel_on_screen(channel))
            for _frame in range(120):
                task._move(1 / 60.)
            task._sync_shapes()
            task.on_draw()
        finally:
            task.close()

    def test_pursuit_every_screw_tightened(self):
        self._push('pursuit')
        task = Pursuit()
        try:
            task.start_run()
            self.assertEqual(task.seconds, 120)
            self.assertEqual(task.total_rounds, 20)
            quarry = task.quarry
            for _frame in range(600):
                if _frame % 10 == 0:
                    task._swerve(quarry, 0.0)
                    task._lurch(quarry, 0.0)
                    task._swell(quarry, 0.0)
                    task._shift(quarry, 0.0)
                task._move(1 / 60.)
                task._sample(1 / 60.)
            low_x, high_x, low_y, high_y = task._bounds()
            self.assertTrue(low_x <= quarry.x <= high_x)
            self.assertTrue(low_y <= quarry.y <= high_y)
            task.on_draw()
        finally:
            task.close()

    def test_out_of_sight_a_field_full_of_slabs(self):
        """Thirty dots, fifteen of them yours, behind the widest slabs.

        The slabs are the maximum that matters here: eight of them at
        their widest is more than the field can take, so the test is
        that the field still comes out playable — every dot spawned
        in the open, the slabs short of half the field between them,
        and a question that finds something to point at.
        """
        from neural_workshop.ui.outofsight import area_in, hidden
        self._push('out_of_sight')
        task = OutOfSight()
        try:
            task.start_run()
            self.assertEqual(len(task.dots), 30)
            self.assertEqual(task.held_now(), 15)
            self.assertEqual(task.probes_per_round, 20)
            field = task._bounds()
            low_x, high_x, low_y, high_y = field
            taken = sum(area_in(slab, field) for slab in task.blinds)
            self.assertLess(taken, (high_x - low_x) * (high_y - low_y) * 0.5)
            for dot in task.dots:
                self.assertFalse(hidden(task.blinds, dot.x, dot.y))
            task.until = 0.0
            task.update(1 / 60.)
            for _frame in range(600):
                task._move(1 / 60.)
            for dot in task.dots:
                self.assertTrue(low_x <= dot.x <= high_x)
                self.assertTrue(low_y <= dot.y <= high_y)
            task.next_probe = 0.0
            task.update(1 / 60.)
            self.assertIsNotNone(task.probe)
            task.on_draw()
        finally:
            task.close()

    def test_sokoban_at_the_superhuman_rung(self):
        self._push('sokoban')
        task = SokobanTask()
        try:
            task.total_trials = 1
            task.start_run()
            self.assertEqual(task.rung, 16)
            self.assertEqual(len(task.level.boxes), 13)
            certified = (task.level.minimum
                         if task.level.minimum is not None
                         else task.level.at_least)
            from neural_workshop.sokoban import GRADES
            self.assertGreaterEqual(certified, GRADES[15].floor)
            task.on_draw()
        finally:
            task.close()

    def test_maze_at_the_superhuman_rung(self):
        """The biggest maze the ladder offers, solved exactly.

        Unlike Sokoban there is no budget to run out of here: the
        search over (cell, keys held) is affordable at every size the
        ladder deals, so the top rung still hands back a real minimum
        rather than a bound.
        """
        from neural_workshop.maze import GRADES, planning_share, route
        self._push('maze')
        task = MazeTask()
        try:
            task.total_trials = 1
            task.start_run()
            self.assertEqual(task.rung, len(GRADES))
            grade = GRADES[-1]
            maze = task.maze
            self.assertEqual(maze.width, 2 * grade.rooms + 1)
            self.assertEqual(len(maze.doors), grade.doors)
            self.assertGreaterEqual(maze.minimum, grade.floor)
            self.assertGreaterEqual(planning_share(maze), grade.planning)
            self.assertEqual(len(route(maze)) - 1, maze.minimum)
            task.on_draw()
        finally:
            task.close()

    def test_salesman_eighteen_cities(self):
        self._push('salesman')
        task = TravelingSalesman()
        try:
            task.start_run()
            self.assertEqual(task.trial_cities, 18)
            self.assertEqual(len(task.cities), 18)
            self.assertEqual(len(set(task.best_order)), 18)
            task.on_draw()
        finally:
            task.close()
