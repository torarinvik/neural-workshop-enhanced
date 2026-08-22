#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The 3D Maze: the view, the par, and the map that must not move.

Three things are worth testing hard and the rest follows from them.

The ray casting is held to a corridor whose distances can be worked
out on paper, because a view that is subtly wrong is a view that lies
to the player about which junction they are in, and nothing downstream
would catch it.

The par is held to the route it claims: walking the moves it hands
back must reach the way out in exactly that many steps. A minimum that
cannot be walked is not a minimum.

And the map is held to the pixels under it. That the map never moves
is the entire task rather than a nicety, so it is checked by
digesting the panel before and after a walk rather than by trusting
that nothing in the movement path happens to touch it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import (TASKS, YouAreHere, close_overlays, key, needs_ui,
                       reset_window, state, taskoptions)

from neural_workshop import maze as M
from neural_workshop import youarehere as Y
from neural_workshop.i18n import _
from nwenv.frames import capture_rgba, digest_rgba

#: The rungs the slow sweeps visit. The ladder is the 2D Maze's own,
#: fifteen rungs of it, and solving the top one over facings as well
#: as cells is not something to do in a loop.
SPREAD = (1, 3, 6)

#: A hand-made maze: a five wide grid whose only corridor is the middle
#: row, running from x=1 to x=3.
WIDE = 5


def corridor(doors=(), keys=()):
    """The little east-west corridor the ray tests are measured against."""
    walls = frozenset(cell for cell in range(WIDE * WIDE)
                      if not (cell // WIDE == 2 and 1 <= cell % WIDE <= 3))
    return M.Maze(width=WIDE, height=WIDE, walls=walls, start=2 * WIDE + 1,
                  way_out=2 * WIDE + 3, doors=doors, keys=keys,
                  minimum=2, greedy=2)


def spot(cell):
    return cell % WIDE, cell // WIDE


class StandingTests(unittest.TestCase):
    """Where a player is, and what one action does to it."""

    def setUp(self):
        self.maze = corridor()

    def test_the_facings_run_clockwise_from_north(self):
        self.assertEqual(Y.FACINGS,
                         ((0, -1), (1, 0), (0, 1), (-1, 0)))

    def test_turning_right_goes_round_the_ring(self):
        pose = Y.Pose(2 * WIDE + 2, 0)
        for expected in (1, 2, 3, 0):
            pose, _held, moved = Y.move(self.maze, pose, 0, Y.RIGHT)
            self.assertEqual(pose.facing, expected)
            self.assertFalse(moved)

    def test_turning_left_goes_the_other_way(self):
        pose, _held, _m = Y.move(self.maze, Y.Pose(2 * WIDE + 2, 0), 0, Y.LEFT)
        self.assertEqual(pose.facing, 3)

    def test_turning_never_moves_you(self):
        for turn in (Y.LEFT, Y.RIGHT):
            pose, _h, _m = Y.move(self.maze, Y.Pose(2 * WIDE + 2, 1), 0, turn)
            self.assertEqual(pose.cell, 2 * WIDE + 2)

    def test_walking_forward_takes_one_cell(self):
        pose, _h, moved = Y.move(self.maze, Y.Pose(2 * WIDE + 1, 1), 0, Y.AHEAD)
        self.assertEqual(pose.cell, 2 * WIDE + 2)
        self.assertEqual(pose.facing, 1)
        self.assertTrue(moved)

    def test_walking_backward_keeps_you_facing_the_same_way(self):
        pose, _h, moved = Y.move(self.maze, Y.Pose(2 * WIDE + 2, 1), 0, Y.BACK)
        self.assertEqual(pose.cell, 2 * WIDE + 1)
        self.assertEqual(pose.facing, 1)
        self.assertTrue(moved)

    def test_a_wall_stops_you_and_says_so(self):
        pose, _h, moved = Y.move(self.maze, Y.Pose(2 * WIDE + 2, 0), 0, Y.AHEAD)
        self.assertEqual(pose.cell, 2 * WIDE + 2)
        self.assertFalse(moved)

    def test_the_edge_of_the_grid_stops_you(self):
        # Cell 2 is on the top row; north of it is off the grid.
        self.assertIsNone(Y.ahead_of(self.maze, 2, 0))

    def test_a_locked_door_stops_you_but_is_not_a_wall(self):
        maze = corridor(doors=(2 * WIDE + 2,), keys=(2 * WIDE + 1,))
        self.assertIsNotNone(Y.ahead_of(maze, 2 * WIDE + 1, 1))
        pose, _h, moved = Y.move(maze, Y.Pose(2 * WIDE + 1, 1), 0, Y.AHEAD)
        self.assertFalse(moved)
        self.assertEqual(Y.locked(maze, 2 * WIDE + 2, 0), 0)

    def test_the_key_opens_it(self):
        maze = corridor(doors=(2 * WIDE + 2,), keys=(2 * WIDE + 1,))
        held = Y.picked_up(maze, 2 * WIDE + 1, 0)
        self.assertEqual(held, 1)
        pose, _h, moved = Y.move(maze, Y.Pose(2 * WIDE + 1, 1), held, Y.AHEAD)
        self.assertTrue(moved)
        self.assertIsNone(Y.locked(maze, 2 * WIDE + 2, held))

    def test_walking_over_a_key_picks_it_up(self):
        maze = corridor(doors=(2 * WIDE + 3,), keys=(2 * WIDE + 2,))
        _pose, held, _m = Y.move(maze, Y.Pose(2 * WIDE + 1, 1), 0, Y.AHEAD)
        self.assertEqual(held, 1)

    def test_a_turn_costs_a_step_and_a_bump_does_not(self):
        self.assertEqual(Y.costs(Y.LEFT, False), 1)
        self.assertEqual(Y.costs(Y.RIGHT, False), 1)
        self.assertEqual(Y.costs(Y.AHEAD, True), 1)
        self.assertEqual(Y.costs(Y.AHEAD, False), 0)
        self.assertEqual(Y.costs(Y.BACK, False), 0)

    def test_a_maze_always_opens_onto_a_corridor(self):
        for rung in SPREAD:
            maze = Y.deal(rung, seed=30 + rung)
            facing = Y.facing_at(maze)
            self.assertIsNotNone(Y.ahead_of(maze, maze.start, facing))


class ParTests(unittest.TestCase):
    """The minimum, and the route that proves it is one."""

    def test_the_route_is_as_long_as_the_par_says(self):
        for rung in SPREAD:
            maze = Y.deal(rung, seed=70 + rung)
            self.assertEqual(len(Y.route(maze)), Y.par(maze))

    def test_walking_the_route_gets_out(self):
        """A minimum that cannot be walked is not a minimum."""
        for rung in SPREAD:
            maze = Y.deal(rung, seed=90 + rung)
            pose = Y.Pose(maze.start, Y.facing_at(maze))
            held = Y.picked_up(maze, maze.start, 0)
            spent = 0
            for doing in Y.route(maze):
                pose, held, moved = Y.move(maze, pose, held, doing)
                spent += Y.costs(doing, moved)
            self.assertEqual(pose.cell, maze.way_out)
            self.assertEqual(spent, Y.par(maze))

    def test_turning_makes_the_way_out_dearer_than_it_is_flat(self):
        """The price of the view, which is the point of counting turns."""
        for rung in SPREAD:
            maze = Y.deal(rung, seed=110 + rung)
            self.assertGreater(Y.par(maze), maze.minimum)

    def test_the_par_is_the_same_maze_the_2d_ladder_deals(self):
        for rung in SPREAD:
            self.assertEqual(Y.deal(rung, seed=7), M.generate(rung, seed=7))

    def test_a_corridor_two_cells_long_costs_two_steps(self):
        self.assertEqual(Y.par(corridor()), 2)

    def test_a_maze_that_needs_turning_round_costs_the_turns(self):
        """Three cells in a row, but starting at the wrong end of them.

        The start faces north into a wall, so the first open way is
        east; the way out is west. Turning about costs two, then two
        cells: four.
        """
        walls = frozenset(cell for cell in range(WIDE * WIDE)
                          if not (cell // WIDE == 2 and 1 <= cell % WIDE <= 3))
        maze = M.Maze(width=WIDE, height=WIDE, walls=walls,
                      start=2 * WIDE + 3, way_out=2 * WIDE + 1,
                      doors=(), keys=(), minimum=2, greedy=2)
        self.assertEqual(Y.facing_at(maze), 3)
        self.assertEqual(Y.par(maze), 2)

    def test_the_flat_sweep_agrees_with_the_plain_one(self):
        """The optimisation has to give the same answer or it is a bug.

        :func:`_sweep` packs a state into one integer and reads the
        maze off precomputed tables, which is about three times the
        speed of the obvious search but is no longer obviously the
        same search. This is the obvious one, written out with
        :func:`move` per edge, held against it.
        """
        for rung in SPREAD:
            maze = Y.deal(rung, seed=1300 + rung)
            first = (maze.start, Y.facing_at(maze),
                     Y.picked_up(maze, maze.start, 0))
            came = {first: None}
            queue, found = [first], -1
            while queue and found < 0:
                nextup = []
                for state in queue:
                    if state[0] == maze.way_out:
                        found = 0
                        while came[state] is not None:
                            state, _doing = came[state]
                            found += 1
                        break
                    pose, keys = Y.Pose(state[0], state[1]), state[2]
                    for doing in Y.MOVES:
                        went, got, _m = Y.move(maze, pose, keys, doing)
                        below = (went.cell, went.facing, got)
                        if below not in came:
                            came[below] = (state, doing)
                            nextup.append(below)
                queue = nextup
            self.assertEqual(Y.par(maze), found, 'rung %d' % rung)

    def test_planning_from_a_belief_plans_from_the_belief(self):
        maze = Y.deal(1, seed=13)
        here = Y.Pose(maze.start, Y.facing_at(maze))
        elsewhere = Y.Pose(maze.way_out, 0)
        self.assertTrue(Y.route_from(maze, here, 0))
        self.assertEqual(Y.route_from(maze, elsewhere, 63), [])


class ViewTests(unittest.TestCase):
    """The ray casting, against a corridor measured by hand."""

    def setUp(self):
        self.maze = corridor()

    def test_a_flat_wall_ahead_is_flat_and_not_bowed(self):
        """The one error that would be invisible and ruinous.

        Measuring along the ray instead of square on to the screen
        bows a straight wall outwards, which reads as a curved
        corridor and quietly misleads about how far away a junction
        is.
        """
        seen = Y.look(self.maze, Y.Pose(2 * WIDE + 1, 1), columns=41)
        faces = {round(sight.distance, 6) for sight in seen
                 if sight.cell % WIDE == 4}
        self.assertEqual(faces, {2.5})

    def test_the_far_wall_is_where_it_ought_to_be(self):
        seen = Y.look(self.maze, Y.Pose(2 * WIDE + 1, 1), columns=9)
        self.assertEqual(spot(seen[4].cell), (4, 2))
        self.assertAlmostEqual(seen[4].distance, 2.5, places=6)

    def test_a_wall_one_cell_off_is_half_a_cell_from_your_eye(self):
        for facing, away in ((0, 0.5), (1, 1.5), (2, 0.5), (3, 1.5)):
            seen = Y.look(self.maze, Y.Pose(2 * WIDE + 2, facing), columns=3)
            self.assertAlmostEqual(seen[1].distance, away, places=6)

    def test_every_column_finds_a_wall_in_a_closed_maze(self):
        for facing in range(4):
            for sight in Y.look(self.maze, Y.Pose(2 * WIDE + 2, facing)):
                self.assertLess(sight.distance, Y.FAR)
                self.assertIn(sight.cell, self.maze.walls)

    def test_it_casts_the_columns_it_is_asked_for(self):
        self.assertEqual(len(Y.look(self.maze, Y.Pose(2 * WIDE + 2, 0),
                                    columns=7)), 7)
        self.assertEqual(len(Y.look(self.maze, Y.Pose(2 * WIDE + 2, 0))),
                         Y.COLUMNS)

    def test_the_two_faces_of_a_corner_are_told_apart(self):
        seen = Y.look(self.maze, Y.Pose(2 * WIDE + 1, 1), columns=41)
        self.assertEqual({sight.side for sight in seen}, {0, 1})

    def test_turning_right_round_shows_a_different_corridor(self):
        ahead = Y.look(self.maze, Y.Pose(2 * WIDE + 1, 1), columns=21)
        behind = Y.look(self.maze, Y.Pose(2 * WIDE + 1, 3), columns=21)
        self.assertNotEqual([s.distance for s in ahead],
                            [s.distance for s in behind])

    def test_a_real_maze_casts_from_every_cell_it_has(self):
        maze = Y.deal(2, seed=5)
        for cell in maze.open_cells():
            for facing in range(4):
                seen = Y.look(maze, Y.Pose(cell, facing), columns=11)
                self.assertTrue(all(sight.distance > 0 for sight in seen))


class MoteTests(unittest.TestCase):
    """The keys and the way out, seen from down a corridor."""

    def setUp(self):
        self.maze = corridor(doors=(2 * WIDE + 3,), keys=(2 * WIDE + 2,))

    def test_a_key_down_the_corridor_is_seen(self):
        found = Y.motes(self.maze, Y.Pose(2 * WIDE + 1, 1), 0)
        keys = [mote for mote in found if mote.what == 'key']
        self.assertEqual(len(keys), 1)
        self.assertAlmostEqual(keys[0].distance, 1.0, places=6)
        self.assertAlmostEqual(keys[0].across, 0.5, places=6)

    def test_the_way_out_is_seen_too(self):
        found = Y.motes(self.maze, Y.Pose(2 * WIDE + 1, 1), 0)
        self.assertIn('way out', [mote.what for mote in found])

    def test_nothing_behind_you_is_seen(self):
        self.assertEqual(Y.motes(self.maze, Y.Pose(2 * WIDE + 3, 1), 0), ())

    def test_a_key_already_held_stops_being_a_mark(self):
        found = Y.motes(self.maze, Y.Pose(2 * WIDE + 1, 1), 1)
        self.assertNotIn('key', [mote.what for mote in found])

    def test_nothing_is_seen_through_a_wall(self):
        walls = frozenset(cell for cell in range(WIDE * WIDE)
                          if not (cell // WIDE == 2 and cell % WIDE in (1, 3)))
        maze = M.Maze(width=WIDE, height=WIDE, walls=walls,
                      start=2 * WIDE + 1, way_out=2 * WIDE + 3, doors=(),
                      keys=(), minimum=2, greedy=2)
        self.assertEqual(Y.motes(maze, Y.Pose(2 * WIDE + 1, 1), 0), ())

    def test_the_far_ones_come_first_so_the_near_ones_draw_over_them(self):
        maze = corridor(doors=(2 * WIDE + 3,), keys=(2 * WIDE + 2,))
        found = Y.motes(maze, Y.Pose(2 * WIDE + 1, 1), 0)
        self.assertEqual([mote.distance for mote in found],
                         sorted((mote.distance for mote in found),
                                reverse=True))


class WalkerTests(unittest.TestCase):
    """The foils, which are what the task's claim rests on."""

    def test_a_perfect_walk_is_the_par(self):
        for rung in SPREAD:
            maze = Y.deal(rung, seed=210 + rung)
            self.assertEqual(Y.walk_perfect(maze), Y.par(maze))

    def test_a_hand_on_the_wall_gets_out_of_a_maze_without_loops(self):
        """Which is the whole reason the ladder braids loops in.

        Rung one is a perfect maze — no loops at all — and one hand on
        one wall solves any of those. Every rung above it opens dead
        ends back into the maze, and that is what this foil cannot
        cope with.
        """
        maze = Y.deal(1, seed=41)
        self.assertGreater(Y.walk_hugging(maze), 0)

    def test_a_hand_on_the_wall_costs_far_more_than_knowing_where_you_are(self):
        maze = Y.deal(1, seed=41)
        self.assertGreater(Y.walk_hugging(maze), Y.par(maze) * 1.5)

    def test_a_player_that_never_slips_walks_the_minimum_exactly(self):
        """Which is what makes the slipping numbers mean anything."""
        for rung in SPREAD:
            maze = Y.deal(rung, seed=250 + rung)
            self.assertEqual(Y.walk_slipping(maze, 0.0, random.Random(1)),
                             Y.par(maze))

    def test_losing_your_place_loses_the_maze(self):
        """The claim the whole task is built on, played out.

        Not "does worse" — a player that drops one update in ten stops
        getting out at all, on a maze a player that drops none walks
        the minimum of.
        """
        got_out = 0
        for trial in range(10):
            maze = Y.deal(3, seed=280 + trial)
            if Y.walk_slipping(maze, 0.10, random.Random(trial)) > 0:
                got_out += 1
        self.assertLess(got_out, 6)

    def test_slipping_more_never_helps(self):
        maze = Y.deal(2, seed=17)
        steady = sum(1 for t in range(12)
                     if Y.walk_slipping(maze, 0.0, random.Random(t)) > 0)
        shaky = sum(1 for t in range(12)
                    if Y.walk_slipping(maze, 0.15, random.Random(t)) > 0)
        self.assertGreater(steady, shaky)


@needs_ui
class YouAreHereScreenTests(unittest.TestCase):
    """The screen: a corridor that moves, and a map that does not."""

    RUNG = 1

    def setUp(self):
        close_overlays()
        self.task = YouAreHere()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.start_rung = self.task.rung = self.RUNG
        self.now = 1000.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _walk_out(self):
        for doing in Y.route(self.task.maze):
            self.task.walk(doing)

    def test_it_is_in_the_planning_category(self):
        self.assertIn('you_are_here',
                      [task for task, _n in TASKS['planning']])

    def test_a_trial_deals_a_maze_and_stands_you_in_it(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'walking')
        self.assertEqual(self.task.pose.cell, self.task.maze.start)
        self.assertEqual(self.task.par, Y.par(self.task.maze))
        self.assertEqual(self.task.steps, 0)
        self.task.on_draw()

    def test_the_arrows_turn_and_walk(self):
        self.task.start_run()
        was = self.task.pose.facing
        self.task.on_key_press(key.RIGHT, 0)
        self.assertEqual(self.task.pose.facing, (was + 1) % 4)
        self.assertEqual(self.task.steps, 1)
        self.task.on_key_press(key.LEFT, 0)
        self.assertEqual(self.task.pose.facing, was)
        self.assertEqual(self.task.steps, 2)

    def test_walking_into_a_wall_costs_nothing(self):
        self.task.start_run()
        # Turn until a wall is dead ahead, then walk into it.
        for _turn in range(4):
            if Y.ahead_of(self.task.maze, self.task.pose.cell,
                          self.task.pose.facing) is None:
                break
            self.task.walk(Y.RIGHT)
        was, bumps = self.task.steps, self.task.bumps
        self.task.walk(Y.AHEAD)
        self.assertEqual(self.task.steps, was)
        self.assertEqual(self.task.bumps, bumps + 1)

    def test_getting_out_ends_the_maze(self):
        self.task.start_run()
        self._walk_out()
        self.assertEqual(self.task.phase, 'solved')
        self.assertEqual(self.task.steps, self.task.par)
        self.assertEqual(self.task.score()['perfect'], 1)
        self.task.on_draw()

    def test_restart_puts_you_back_and_zeroes_the_count(self):
        self.task.start_run()
        self.task.walk(Y.RIGHT)
        self.task.walk(Y.AHEAD)
        self.task.restart()
        self.assertEqual(self.task.pose,
                         Y.Pose(self.task.maze.start,
                                Y.facing_at(self.task.maze)))
        self.assertEqual(self.task.steps, 0)

    def test_the_run_finishes_after_its_mazes(self):
        self.task.start_run()
        for _trial in range(self.task.total_trials):
            self._walk_out()
            self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['solved'],
                         self.task.total_trials)
        self.assertEqual(self.task.score()['efficiency'], 100)

    def test_adaptive_climbs_after_a_tidy_walk(self):
        self.task.adaptive = True
        self.task.start_run()
        was = self.task.rung
        self._walk_out()
        self.assertEqual(self.task.rung, was + 1)

    def test_adaptive_drops_after_a_wandering_one(self):
        self.task.adaptive = True
        # Not from rung one, which has nowhere below it to drop to.
        self.task.start_rung = self.task.rung = 3
        self.task.start_run()
        was = self.task.rung
        # A whole number of full turns, so the route still applies
        # afterwards, and enough of them to spend twice the par.
        for _spin in range(4 * (self.task.par // 2 + 1)):
            self.task.walk(Y.RIGHT)
        self.assertGreater(self.task.steps, self.task.par * 2)
        self._walk_out()
        self.assertEqual(self.task.rung, was - 1)

    def test_it_draws_in_every_phase(self):
        self.task.on_draw()                        # ready
        self.task.start_run()
        self.task.on_draw()                        # walking
        self._walk_out()
        self.task.on_draw()                        # solved
        self.task.total_trials = 1
        self.task.on_key_press(key.SPACE, 0)
        self.task.on_draw()                        # done

    def test_it_draws_a_maze_with_doors_and_keys(self):
        self.task.start_rung = self.task.rung = 4
        self.task.start_run()
        self.assertTrue(self.task.maze.doors)
        self.task.on_draw()
        self.task.show_marks = False
        self.task._redraw()
        self.task.on_draw()

    def test_the_view_and_the_map_do_not_overlap(self):
        self.task.start_run()
        view_left, _vb, view_wide, _vh = self.task._view_rect()
        map_left, _mb, _mw, _mh = self.task._map_rect()
        self.assertLess(view_left + view_wide, map_left)

    def test_every_cell_of_the_map_lands_inside_its_panel(self):
        self.task.start_run()
        left, bottom, wide, tall = self.task._map_rect()
        for cell in range(self.task.maze.width * self.task.maze.height):
            x, y, side = self.task._cell_rect(cell)
            self.assertGreaterEqual(x, left - 1)
            self.assertGreaterEqual(y, bottom - 1)
            self.assertLessEqual(x + side, left + wide + 1)
            self.assertLessEqual(y + side, bottom + tall + 1)

    def _map_pixels(self):
        """Digest only the pixels under the map panel.

        Cut to the panel's own band rather than to the whole width,
        because the status line above it changes on every step and
        would otherwise drown the very thing being measured. The band
        is trimmed by the same amount at both ends so that it is the
        right band whichever way round the capture happens to store
        its rows.
        """
        wide, tall, rgba = capture_rgba(state.window)
        scale = wide / float(state.window.width)
        left, bottom, _panel_wide, panel_tall = self.task._map_rect()
        first = int(bottom * scale) + 2
        last = int((bottom + panel_tall) * scale) - 2
        first, last = max(first, tall - last), min(last, tall - first)
        start_x = int(left * scale)
        rows = [rgba[(row * wide + start_x) * 4:(row * wide + wide) * 4]
                for row in range(first, last)]
        return digest_rgba(b''.join(rows))

    def test_the_map_does_not_move_when_the_player_does(self):
        """The task's one promise, read off the pixels themselves.

        Not "the map is rebuilt from the same data" and not "nothing
        in the movement path calls the map builder" — the actual
        pixels under the panel, before a walk and after it, with the
        player somewhere else entirely and carrying a key it did not
        have. If anything about where the player is ever reached the
        map, this is where it would show.
        """
        self.task.start_rung = self.task.rung = 4
        # Pinned, because the maze is dealt from an unseeded generator
        # and the halfway point of a route can land back on the start
        # cell — on such a deal this test would pass by measuring
        # nothing, or fail on the assertion below, depending on the
        # deal rather than on anything about the map.
        self.task.rng.seed(7)
        self.task.start_run()
        self.task.on_draw()
        before = self._map_pixels()
        walked = Y.route(self.task.maze)
        for doing in walked[:len(walked) // 2]:
            self.task.walk(doing)
        self.task.on_draw()
        self.assertNotEqual(self.task.pose.cell, self.task.maze.start)
        self.assertEqual(self._map_pixels(), before)

    def test_the_view_does_move_when_the_player_does(self):
        """The other half, so the test above cannot pass by drawing nothing."""
        self.task.start_run()
        self.task.on_draw()
        before = digest_rgba(capture_rgba(state.window)[2])
        self.task.walk(Y.RIGHT)
        self.task.on_draw()
        self.assertNotEqual(digest_rgba(capture_rgba(state.window)[2]),
                            before)

    def test_the_map_is_not_even_rebuilt_while_walking(self):
        """Belt to the pixel test's braces: the shapes are the same objects."""
        self.task.start_run()
        was = [id(shape) for shape in self.task.map_drawn]
        self.assertTrue(was)
        for doing in Y.route(self.task.maze)[:4]:
            self.task.walk(doing)
        self.assertEqual([id(shape) for shape in self.task.map_drawn], was)

    def test_a_new_maze_does_get_a_new_map(self):
        self.task.start_run()
        was = [id(shape) for shape in self.task.map_drawn]
        self._walk_out()
        self.task.on_key_press(key.SPACE, 0)
        self.assertNotEqual([id(shape) for shape in self.task.map_drawn], was)

    def test_it_has_an_options_screen(self):
        spec = taskoptions.TASK_SPECS['you_are_here']
        chosen = {opt.key: opt.default for opt in spec.options}
        self.assertIn('HERE_LEVEL', chosen)
        self.assertTrue(spec.note(chosen))

    def test_the_note_says_the_map_will_not_say_where_you_are(self):
        spec = taskoptions.TASK_SPECS['you_are_here']
        chosen = {opt.key: opt.default for opt in spec.options}
        chosen['HERE_LEVEL'] = 6
        said = spec.note(chosen)
        self.assertIn(_(M.GRADES[5].name), said)
        self.assertIn('never says where you are', said)

    def test_the_note_warns_when_the_marks_are_off(self):
        spec = taskoptions.TASK_SPECS['you_are_here']
        chosen = {opt.key: opt.default for opt in spec.options}
        chosen['HERE_MARKS'] = False
        self.assertIn('marks off', spec.note(chosen))


if __name__ == '__main__':
    unittest.main()
