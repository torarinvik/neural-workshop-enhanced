#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The maze: carving, locking, and the exact way out.

The generator's promises are what is tested hardest, because they are
what the par on screen rests on: every door really separates the start
from the way out, every key can really be had before its own door, and
the minimum really is one. Small mazes are written out as pictures so
the expected answer can be counted by hand.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import (MazeTask, TASKS, close_overlays, needs_ui,
                       reset_window, taskoptions)

from neural_workshop import maze as M

#: A rung with a planning floor, and one without.
PLANNING_RUNG = 12
PLAIN_RUNG = 3


def picture(rows, doors='', keys=''):
    """A maze written out: ``#`` wall, ``@`` start, ``X`` way out.

    Doors and keys are named by the characters in *doors* and *keys*,
    in colour order, so ``doors='0'`` and ``keys='a'`` reads straight
    off the picture.
    """
    height, width = len(rows), len(rows[0])
    walls, start, way_out = set(), 0, 0
    door_at, key_at = {}, {}
    for y, row in enumerate(rows):
        assert len(row) == width, 'ragged picture'
        for x, mark in enumerate(row):
            cell = y * width + x
            if mark == '#':
                walls.add(cell)
            elif mark == '@':
                start = cell
            elif mark == 'X':
                way_out = cell
            elif mark in doors:
                door_at[doors.index(mark)] = cell
            elif mark in keys:
                key_at[keys.index(mark)] = cell
    made = M.Maze(
        width=width, height=height, walls=frozenset(walls), start=start,
        way_out=way_out,
        doors=tuple(door_at[i] for i in range(len(door_at))),
        keys=tuple(key_at[i] for i in range(len(key_at))),
        minimum=0, greedy=0)
    made = made._replace(minimum=M.solve(made))
    return made._replace(greedy=M.greedy_walk(made))


def links_of(maze):
    return M.adjacency(maze.width, maze.height, maze.open_cells())


class CarveTests(unittest.TestCase):
    """A perfect maze: every room reached, exactly once each."""

    def test_the_grid_is_twice_the_rooms_plus_one(self):
        for rooms in (2, 4, 7):
            width, height, _open = M.carve(rooms, random.Random(1))
            self.assertEqual((width, height),
                             (2 * rooms + 1, 2 * rooms + 1))

    def test_a_perfect_maze_is_a_tree(self):
        """Rooms plus the walls knocked between them, and no more.

        A spanning tree over r*r rooms has exactly r*r - 1 edges, so
        an open count of anything else means a room was joined twice
        or missed.
        """
        for rooms in (2, 3, 5, 8):
            width, height, open_cells = M.carve(rooms, random.Random(rooms))
            self.assertEqual(len(open_cells), 2 * rooms * rooms - 1)

    def test_every_room_is_reachable(self):
        width, height, open_cells = M.carve(6, random.Random(4))
        links = M.adjacency(width, height, frozenset(open_cells))
        walked = M.reachable(links, min(open_cells))
        self.assertEqual(len(walked), len(open_cells))

    def test_the_border_is_never_carved(self):
        width, height, open_cells = M.carve(5, random.Random(9))
        for cell in open_cells:
            x, y = cell % width, cell // width
            self.assertTrue(0 < x < width - 1)
            self.assertTrue(0 < y < height - 1)


class BraidTests(unittest.TestCase):
    """Opening dead ends is what gives the walk a choice."""

    def test_a_perfect_maze_is_all_dead_ends_and_corridor(self):
        rows = ['#####',
                '#...#',
                '#.###',
                '#...#',
                '#####']
        walls = {y * 5 + x for y, row in enumerate(rows)
                 for x, mark in enumerate(row) if mark == '#'}
        open_cells = {cell for cell in range(25) if cell not in walls}
        ends = M.dead_ends(5, 5, open_cells)
        self.assertEqual(sorted(ends), [8, 18])   # (3,1) and (3,3)

    def test_braiding_opens_walls_and_never_shuts_any(self):
        width, height, open_cells = M.carve(6, random.Random(2))
        was = set(open_cells)
        M.braid(width, height, open_cells, 0.5, random.Random(2))
        self.assertGreater(len(open_cells), len(was))
        self.assertTrue(was <= open_cells)

    def test_braiding_nothing_changes_nothing(self):
        width, height, open_cells = M.carve(5, random.Random(3))
        was = set(open_cells)
        M.braid(width, height, open_cells, 0.0, random.Random(3))
        self.assertEqual(open_cells, was)

    def test_braiding_leaves_the_maze_in_one_piece(self):
        width, height, open_cells = M.carve(7, random.Random(6))
        M.braid(width, height, open_cells, 0.7, random.Random(6))
        links = M.adjacency(width, height, frozenset(open_cells))
        self.assertEqual(len(M.reachable(links, min(open_cells))),
                         len(open_cells))

    def test_braiding_removes_dead_ends(self):
        width, height, open_cells = M.carve(8, random.Random(11))
        before = len(M.dead_ends(width, height, open_cells))
        M.braid(width, height, open_cells, 0.6, random.Random(11))
        self.assertLess(len(M.dead_ends(width, height, open_cells)), before)


class WalkTests(unittest.TestCase):
    """Reaching, measuring and separating, on pictures."""

    CORRIDOR = ['###########',
                '#@..a.0..X#',
                '###########']

    def test_distances_count_steps(self):
        maze = picture(self.CORRIDOR, doors='0', keys='a')
        apart = M.distances(links_of(maze), maze.start)
        self.assertEqual(apart[maze.start], 0)
        self.assertEqual(apart[maze.way_out], 8)

    def test_a_blocked_cell_stops_the_walk(self):
        maze = picture(self.CORRIDOR, doors='0', keys='a')
        shut = frozenset(maze.doors)
        self.assertNotIn(maze.way_out,
                         M.reachable(links_of(maze), maze.start, shut))

    def test_every_inner_cell_of_a_corridor_separates_it(self):
        maze = picture(self.CORRIDOR, doors='0', keys='a')
        beads = M.separators(links_of(maze), maze.start, maze.way_out)
        self.assertEqual(len(beads), 7)      # every cell between the ends

    def test_the_separators_come_out_in_order(self):
        maze = picture(self.CORRIDOR, doors='0', keys='a')
        links = links_of(maze)
        beads = M.separators(links, maze.start, maze.way_out)
        apart = M.distances(links, maze.start)
        self.assertEqual([apart[cell] for cell in beads],
                         sorted(apart[cell] for cell in beads))

    def test_a_loop_has_no_separators_at_all(self):
        """Two ways round means no single cell is on both."""
        maze = picture(['#####',
                        '#@..#',
                        '#.#.#',
                        '#..X#',
                        '#####'])
        self.assertEqual(M.separators(links_of(maze), maze.start,
                                      maze.way_out), [])


class SolveTests(unittest.TestCase):
    """The minimum, counted by hand and then by the solver."""

    def test_a_plain_corridor_is_its_own_length(self):
        maze = picture(['#######',
                        '#@...X#',
                        '#######'])
        self.assertEqual(maze.minimum, 4)

    def test_a_key_on_the_way_costs_nothing_extra(self):
        maze = picture(['###########',
                        '#@..a.0..X#',
                        '###########'], doors='0', keys='a')
        self.assertEqual(maze.minimum, 8)

    def test_a_key_off_the_way_costs_the_detour_twice(self):
        """Down the branch and back again, then on to the way out."""
        maze = picture(['#######',
                        '#@.0.X#',
                        '#.#####',
                        '#a#####',
                        '#######'], doors='0', keys='a')
        self.assertEqual(maze.minimum, 4 + 4)

    def test_a_maze_with_no_key_has_no_way_out(self):
        maze = picture(['#######',
                        '#@.0.X#',
                        '#######'], doors='0')
        self.assertEqual(maze.minimum, -1)

    def test_the_same_corridor_twice_is_not_going_in_circles(self):
        """The key is the wrong way down the corridor, so the walk
        doubles back through cells it has already used, carrying more.
        Two steps out to the key, then six all the way across."""
        maze = picture(['#########',
                        '#a.@.0.X#',
                        '#########'], doors='0', keys='a')
        self.assertEqual(maze.minimum, 2 + 6)


class RouteTests(unittest.TestCase):
    """The walk the solver found, and that it really is one."""

    def test_a_route_starts_at_the_start_and_ends_at_the_way_out(self):
        for rung in (1, 6, PLANNING_RUNG):
            maze = M.generate(rung, seed=55)
            walk = M.route(maze)
            self.assertEqual(walk[0], maze.start)
            self.assertEqual(walk[-1], maze.way_out)

    def test_a_route_is_exactly_the_minimum_long(self):
        for rung in (1, 6, PLANNING_RUNG):
            maze = M.generate(rung, seed=56)
            self.assertEqual(len(M.route(maze)) - 1, maze.minimum)

    def test_every_step_of_a_route_is_legal(self):
        """Neighbouring cells, never a wall, never a door unopened."""
        maze = M.generate(PLANNING_RUNG, seed=57)
        held = 0
        key_at = {cell: i for i, cell in enumerate(maze.keys)}
        door_at = {cell: i for i, cell in enumerate(maze.doors)}
        walk = M.route(maze)
        for was, now in zip(walk, walk[1:]):
            self.assertIn(now, M.neighbours(maze.width, maze.height, was))
            self.assertNotIn(now, maze.walls)
            colour = door_at.get(now)
            if colour is not None:
                self.assertTrue(held >> colour & 1)
            if now in key_at:
                held |= 1 << key_at[now]

    def test_a_maze_with_no_way_out_has_no_route(self):
        maze = picture(['#######',
                        '#@.0.X#',
                        '#######'], doors='0')
        self.assertEqual(M.route(maze), [])


class GreedyTests(unittest.TestCase):
    """The foil: nearest key first, which is not always the plan."""

    def test_it_never_beats_the_minimum(self):
        rng = random.Random(5)
        for rung in (4, 8, 12):
            for _deal in range(6):
                maze = M._deal(M.GRADES[rung - 1], rng)
                if maze is None:
                    continue
                self.assertGreaterEqual(maze.greedy, maze.minimum)

    def test_one_key_can_never_be_the_wrong_one_to_fetch(self):
        maze = picture(['#######',
                        '#@.0.X#',
                        '#.#####',
                        '#a#####',
                        '#######'], doors='0', keys='a')
        self.assertEqual(maze.greedy, maze.minimum)
        self.assertEqual(M.planning_share(maze), 0.0)

    def test_the_share_is_what_the_detour_wasted(self):
        maze = picture(['#######',
                        '#@...X#',
                        '#######'])._replace(minimum=10, greedy=13)
        self.assertAlmostEqual(M.planning_share(maze), 0.3)


class LadderTests(unittest.TestCase):
    """What the rungs promise, kept."""

    def test_the_ladder_climbs(self):
        for lower, upper in zip(M.GRADES, M.GRADES[1:]):
            self.assertLessEqual(lower.rooms, upper.rooms)
            self.assertLessEqual(lower.doors, upper.doors)
            self.assertLess(lower.floor, upper.floor)

    def test_no_rung_asks_for_more_doors_than_there_are_colours(self):
        for grade in M.GRADES:
            self.assertLessEqual(grade.doors, M.MOST_DOORS)

    def test_a_planning_floor_only_comes_with_doors_to_order(self):
        for grade in M.GRADES:
            if grade.planning:
                self.assertGreaterEqual(grade.doors, 4)


class GenerateTests(unittest.TestCase):
    """Every promise the generator makes, on real mazes."""

    def mazes(self, rung, count=4, seed=400):
        return [M.generate(rung, seed=seed + index)
                for index in range(count)]

    def test_the_same_seed_deals_the_same_maze(self):
        self.assertEqual(M.generate(6, seed=99), M.generate(6, seed=99))

    def test_another_seed_deals_another_maze(self):
        self.assertNotEqual(M.generate(6, seed=99), M.generate(6, seed=100))

    def test_a_level_past_the_ladder_is_the_last_rung(self):
        far = M.generate(len(M.GRADES) + 40, seed=3)
        last = M.generate(len(M.GRADES), seed=3)
        self.assertEqual(far, last)

    def test_every_maze_can_be_walked_out_of(self):
        for maze in self.mazes(PLANNING_RUNG):
            self.assertGreater(maze.minimum, 0)
            self.assertEqual(M.solve(maze), maze.minimum)

    def test_every_door_really_locks_the_way_out(self):
        """A door that can be walked round is scenery, not a lock."""
        for maze in self.mazes(PLANNING_RUNG, count=3):
            links = links_of(maze)
            for door in maze.doors:
                walked = M.reachable(links, maze.start, frozenset((door,)))
                self.assertNotIn(maze.way_out, walked)

    def test_every_key_can_be_had_before_its_own_door(self):
        for maze in self.mazes(PLANNING_RUNG, count=3):
            links = links_of(maze)
            for colour, door in enumerate(maze.doors):
                near = M.reachable(links, maze.start, frozenset((door,)))
                self.assertIn(maze.keys[colour], near)

    def test_nothing_shares_a_cell_with_anything_else(self):
        for maze in self.mazes(PLANNING_RUNG, count=3):
            placed = list(maze.doors) + list(maze.keys) + [maze.start,
                                                           maze.way_out]
            self.assertEqual(len(placed), len(set(placed)))
            for cell in placed:
                self.assertNotIn(cell, maze.walls)

    def test_a_rung_clears_its_own_floor(self):
        for rung in (1, 4, 8, PLANNING_RUNG, len(M.GRADES)):
            grade = M.GRADES[rung - 1]
            for maze in self.mazes(rung, count=3, seed=900):
                self.assertGreaterEqual(maze.minimum, grade.floor)

    def test_a_rung_with_a_planning_floor_clears_that_too(self):
        grade = M.GRADES[PLANNING_RUNG - 1]
        self.assertGreater(grade.planning, 0)
        for maze in self.mazes(PLANNING_RUNG, count=4, seed=1200):
            self.assertGreaterEqual(M.planning_share(maze), grade.planning)

    def test_a_rung_without_one_is_not_asked_for_it(self):
        self.assertEqual(M.GRADES[PLAIN_RUNG - 1].planning, 0.0)
        for maze in self.mazes(PLAIN_RUNG, count=3):
            self.assertGreaterEqual(maze.minimum,
                                    M.GRADES[PLAIN_RUNG - 1].floor)

    def test_the_first_rung_has_no_doors_to_open(self):
        maze = M.generate(1, seed=8)
        self.assertEqual(maze.doors, ())
        self.assertEqual(maze.keys, ())

    def test_held_after_reads_a_walk_back(self):
        maze = M.generate(6, seed=21)
        self.assertEqual(M.held_after(maze, []), 0)
        self.assertEqual(M.held_after(maze, list(maze.keys)),
                         (1 << len(maze.keys)) - 1)


@needs_ui
class MazeScreenTests(unittest.TestCase):
    """The screen: walking it, locking it, scoring it."""

    def setUp(self):
        close_overlays()
        self.task = MazeTask()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.start_rung = 4
        self.task.rung = 4

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _walk_to(self, cell):
        """Move the walker onto *cell* without pretending it walked."""
        self.task.walker = cell
        self.task.walked.add(cell)
        self.task._take_key()

    def test_it_is_in_the_planning_category(self):
        self.assertIn('maze', [task for task, _n in TASKS['planning']])

    def test_a_trial_deals_a_maze_and_stands_you_at_its_start(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'walking')
        self.assertEqual(self.task.walker, self.task.maze.start)
        self.assertEqual(self.task.steps, 0)
        self.task.on_draw()

    def test_the_par_is_always_an_exact_minimum(self):
        self.task.start_run()
        self.assertEqual(self.task.par(), self.task.maze.minimum)
        self.assertGreater(self.task.par(), 0)

    def test_a_wall_will_not_be_walked_into(self):
        self.task.start_run()
        maze = self.task.maze
        where = self.task.walker
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            ahead = where + dy * maze.width + dx
            if ahead in maze.walls:
                self.task.step(dx, dy)
                self.assertEqual(self.task.walker, where)
                self.assertEqual(self.task.steps, 0)
                return
        self.skipTest('this start had open air all round it')

    def test_a_locked_door_will_not_be_walked_through(self):
        self.task.start_run()
        maze = self.task.maze
        door = maze.doors[0]
        self._walk_to(door - 1 if door - 1 not in maze.walls
                      else door - maze.width)
        was = self.task.walker
        self.assertIsNotNone(self.task.needs_key(door))
        self.task.step(1 if was == door - 1 else 0,
                       0 if was == door - 1 else 1)
        self.assertEqual(self.task.walker, was)

    def test_picking_the_key_up_opens_its_door(self):
        self.task.start_run()
        maze = self.task.maze
        self.assertIsNotNone(self.task.needs_key(maze.doors[0]))
        self._walk_to(maze.keys[0])
        self.assertIsNone(self.task.needs_key(maze.doors[0]))
        self.assertEqual(self.task.keys_left(), len(maze.keys) - 1)

    def test_walking_counts_steps_and_leaves_a_trail(self):
        self.task.start_run()
        maze = self.task.maze
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            ahead = self.task.walker + dy * maze.width + dx
            if ahead not in maze.walls and self.task.needs_key(ahead) is None:
                self.task.step(dx, dy)
                self.assertEqual(self.task.steps, 1)
                self.assertIn(ahead, self.task.walked)
                return
        self.fail('a maze with nowhere to walk')

    def test_restarting_puts_everything_back(self):
        self.task.start_run()
        maze = self.task.maze
        self._walk_to(maze.keys[0])
        self.task.steps = 30
        self.task.restart()
        self.assertEqual(self.task.walker, maze.start)
        self.assertEqual(self.task.steps, 0)
        self.assertEqual(self.task.keys_left(), len(maze.keys))

    def test_reaching_the_way_out_scores_the_maze(self):
        self.task.start_run()
        maze = self.task.maze
        self.task.held = (1 << len(maze.keys)) - 1
        self.task.steps = maze.minimum - 1
        self._walk_to(maze.way_out)
        self.task.walker = maze.way_out - 1
        self.task.step(1, 0) if maze.way_out - 1 not in maze.walls else None
        if self.task.phase != 'solved':          # the way out was walled
            self.task.walker = maze.way_out
            self.task._solved()
        self.assertEqual(self.task.phase, 'solved')
        self.assertEqual(self.task.results[-1][2], maze.minimum)
        self.task.on_draw()

    def test_a_perfect_walk_says_so(self):
        self.task.start_run()
        self.task.steps = self.task.par()
        self.task.walker = self.task.maze.way_out
        self.task._solved()
        self.assertIn('Perfect', self.task.message)

    def test_adaptive_climbs_on_a_tight_walk_and_drops_on_a_loose_one(self):
        self.task.adaptive = True
        self.task.start_run()
        was = self.task.rung
        self.task.steps = self.task.par()
        self.task.walker = self.task.maze.way_out
        self.task._solved()
        self.assertEqual(self.task.rung, was + 1)
        self.task._next_trial()
        was = self.task.rung
        self.task.steps = self.task.par() * 3
        self.task.walker = self.task.maze.way_out
        self.task._solved()
        self.assertEqual(self.task.rung, was - 1)

    def test_the_run_finishes_after_its_mazes(self):
        self.task.start_run()
        for _trial in range(2):
            self.task.steps = self.task.par()
            self.task.walker = self.task.maze.way_out
            self.task._solved()
            self.task._next_trial()
        self.assertEqual(self.task.phase, 'done')
        tally = self.task.score()
        self.assertEqual(tally['solved'], 2)
        self.assertEqual(tally['efficiency'], 100)
        self.assertEqual(tally['perfect'], 2)
        self.task.on_draw()

    def test_it_draws_in_every_phase(self):
        self.task.on_draw()                      # ready
        self.task.start_run()
        self.task.on_draw()                      # walking
        self.task.held = 1
        self.task._redraw()
        self.task.on_draw()                      # a door opened
        self.task.walker = self.task.maze.way_out
        self.task._solved()
        self.task._redraw()
        self.task.on_draw()                      # solved
        self.task._finish()
        self.task.on_draw()                      # done

    def test_the_trail_can_be_turned_off(self):
        self.task.show_trail = False
        self.task.start_run()
        self.task.on_draw()
        self.assertFalse(self.task.show_trail)

    def test_every_cell_of_the_board_lands_on_screen(self):
        self.task.start_run()
        maze = self.task.maze
        left, bottom, width, height = self.task._canvas()
        for cell in (0, maze.width - 1, maze.width * maze.height - 1):
            x, y, side = self.task._cell_rect(cell)
            self.assertGreaterEqual(x, left - 1)
            self.assertLessEqual(x + side, left + width + 1)
            self.assertGreaterEqual(y, bottom - 1)
            self.assertLessEqual(y + side, bottom + height + 1)

    def test_the_solvers_route_walks_the_screen_in_par(self):
        """The strongest check there is that the two halves agree.

        The model says the maze takes N steps; this drives the screen
        along the walk the model found, one arrow key at a time,
        through the screen's own rules about walls, doors and keys.
        If they disagreed about any of it the walk would stall or the
        count would come out wrong.
        """
        from neural_workshop.maze import route
        self.task.start_rung = self.task.rung = 8
        self.task.start_run()
        maze = self.task.maze
        walk = route(maze)
        for was, now in zip(walk, walk[1:]):
            self.task.step(now % maze.width - was % maze.width,
                           now // maze.width - was // maze.width)
        self.assertEqual(self.task.walker, maze.way_out)
        self.assertEqual(self.task.steps, maze.minimum)
        self.assertEqual(self.task.phase, 'solved')
        self.assertIn('Perfect', self.task.message)
        self.assertEqual(self.task.keys_left(), 0)

    def test_it_has_an_options_screen(self):
        self.assertTrue(taskoptions.has_options('maze'))
        note = taskoptions.MAZE.note({'MAZE_LEVEL': PLANNING_RUNG,
                                      'MAZE_SHOW_TRAIL': True,
                                      'MAZE_ADAPTIVE': False})
        grade = M.GRADES[PLANNING_RUNG - 1]
        self.assertIn(str(grade.floor), note)
        self.assertIn('order', note)             # the planning axis is said

    def test_the_note_warns_when_the_trail_is_off(self):
        note = taskoptions.MAZE.note({'MAZE_LEVEL': 2,
                                      'MAZE_SHOW_TRAIL': False,
                                      'MAZE_ADAPTIVE': False})
        self.assertIn('carry the map', note)


if __name__ == '__main__':
    unittest.main()
