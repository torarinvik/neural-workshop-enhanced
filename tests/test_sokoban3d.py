#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""3D Sokoban: the par, the view, and the plan that must not move.

Four things are worth testing hard and the rest follows from them.

The **par** is held to two independent things, because a par is the
only number the task reports and a wrong one would be invisible. It is
held to the route it hands back — walking those moves must finish the
warehouse in exactly that many steps — and, on every rung small enough
to afford it, to a plain breadth-first search over ``(boxes, cell,
facing)`` that knows nothing about the contraction the real solver
uses. The two agreeing is what says the contraction is a shortcut and
not a different answer.

The **view** is held to a corridor whose distances can be worked out on
paper, and to the one thing that makes this task different from the 3D
Maze: a box stops a ray, and moving the box moves where the ray stops.

The **plan** is held to the pixels under it. That the plan never moves
is the entire task rather than a nicety, and here it is a stronger
promise than the 3D Maze's, because the world moves too: the panel is
digested before a push and after it, with a box somewhere it was not.

And the **foils** are measured rather than asserted. What one dropped
update costs in a maze is steps; what it costs here is the warehouse,
and that difference is the reason the task exists, so it is a
measurement and not a remark.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest
from collections import deque

from uisupport import (TASKS, Sokoban3D, close_overlays, key, needs_ui,
                       reset_window, state, taskoptions)

from neural_workshop import sokoban as S
from neural_workshop import sokoban3d as S3
from nwenv.frames import capture_rgba, digest_rgba

#: The rungs the slow sweeps visit. The ladder is the 2D Sokoban's own,
#: sixteen rungs of it, and solving one over facings as well as box
#: positions is not something to do in a loop.
SPREAD = (1, 3, 5)

#: The rung the exactness claim is pinned at. Measured: the step search
#: certifies a minimum on every deal up to and including this one and
#: falls back to its frontier above it.
LAST_EXACT = 8

#: A hand-made warehouse: seven wide, whose only floor is the middle
#: row running from x=1 to x=5.
WIDE = 7


def corridor(boxes, goals, player, width=WIDE):
    """The little east-west corridor the ray tests are measured against."""
    walls = frozenset(cell for cell in range(width * 5)
                      if not (cell // width == 2
                              and 1 <= cell % width <= width - 2))
    return S.Level(width=width, height=5, walls=walls,
                   goals=frozenset(goals), boxes=frozenset(boxes),
                   player=player, minimum=None, at_least=0, bound=0)


def at(x, y=2, width=WIDE):
    return y * width + x


def brute(level, cap=300000):
    """The minimum in steps, found the slow and obvious way.

    Breadth-first over every ``(boxes, cell, facing)`` a player can
    reach by pressing keys, with the task's own :func:`move` and
    :func:`costs` deciding what a key does. It knows nothing about
    pushes, contraction or dead squares, which is the point: it is a
    second opinion rather than the same opinion written twice.
    """
    start = (level.boxes, S3.Pose(level.player, S3.facing_at(level)))
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        (boxes, pose), spent = queue.popleft()
        if S3.solved(level, boxes):
            return spent
        if len(seen) > cap:
            return None
        for doing in S3.MOVES:
            went, shifted, moved, _pushed = S3.move(level, boxes, pose,
                                                    doing)
            if not S3.costs(doing, moved):
                continue
            below = (shifted, went)
            if below not in seen:
                seen.add(below)
                queue.append((below, spent + 1))
    return -1


class StandingTests(unittest.TestCase):
    """Where a player is, and what one action does to it."""

    def setUp(self):
        # Player at x=1, box at x=2, goal at x=5: room to push it three
        # ways along and to reverse into it from the other side.
        self.level = corridor(boxes=(at(2),), goals=(at(5),),
                              player=at(1))
        self.pose = S3.Pose(at(1), S3.facing_at(self.level))

    def test_it_starts_facing_the_only_way_out_of_the_cell(self):
        self.assertEqual(S3.FACINGS[S3.facing_at(self.level)], (1, 0))

    def test_turning_never_moves_you_and_always_costs(self):
        pose, boxes, moved, pushed = S3.move(self.level, self.level.boxes,
                                             self.pose, S3.LEFT)
        self.assertEqual(pose.cell, self.pose.cell)
        self.assertFalse(moved or pushed)
        self.assertEqual(S3.costs(S3.LEFT, moved), 1)

    def test_walking_forward_takes_one_cell(self):
        level = corridor(boxes=(at(4),), goals=(at(5),), player=at(1))
        pose, _boxes, moved, pushed = S3.move(level, level.boxes,
                                              S3.Pose(at(1), 1), S3.AHEAD)
        self.assertEqual((pose.cell, moved, pushed), (at(2), True, False))

    def test_walking_into_a_box_pushes_it(self):
        pose, boxes, moved, pushed = S3.move(self.level, self.level.boxes,
                                             self.pose, S3.AHEAD)
        self.assertEqual(pose.cell, at(2))
        self.assertEqual(boxes, frozenset({at(3)}))
        self.assertTrue(moved and pushed)

    def test_reversing_into_a_box_pushes_it_too(self):
        """The key that makes the par a par of what the keys can do."""
        pose, boxes, moved, pushed = S3.move(
            self.level, self.level.boxes,
            S3.Pose(at(1), 3), S3.BACK)      # facing west, reversing east
        self.assertEqual(pose.cell, at(2))
        self.assertEqual(boxes, frozenset({at(3)}))
        self.assertTrue(moved and pushed)

    def test_a_push_leaves_you_facing_the_way_you_already_were(self):
        pose, _b, _m, _p = S3.move(self.level, self.level.boxes,
                                   S3.Pose(at(1), 3), S3.BACK)
        self.assertEqual(pose.facing, 3)

    def test_a_box_against_a_wall_does_not_go(self):
        level = corridor(boxes=(at(5),), goals=(at(1),), player=at(4))
        pose, boxes, moved, pushed = S3.move(level, level.boxes,
                                             S3.Pose(at(4), 1), S3.AHEAD)
        self.assertEqual((pose.cell, moved, pushed), (at(4), False, False))
        self.assertEqual(boxes, level.boxes)

    def test_a_box_against_a_box_does_not_go(self):
        level = corridor(boxes=(at(2), at(3)), goals=(at(4), at(5)),
                         player=at(1))
        _p, boxes, moved, _pushed = S3.move(level, level.boxes,
                                            S3.Pose(at(1), 1), S3.AHEAD)
        self.assertFalse(moved)
        self.assertEqual(boxes, level.boxes)

    def test_a_wall_stops_you_and_costs_nothing(self):
        level = corridor(boxes=(at(4),), goals=(at(5),), player=at(1))
        _p, _b, moved, _pushed = S3.move(level, level.boxes,
                                         S3.Pose(at(1), 3), S3.AHEAD)
        self.assertFalse(moved)
        self.assertEqual(S3.costs(S3.AHEAD, moved), 0)

    def test_a_shove_that_does_not_shift_costs_nothing_either(self):
        """A bump is a bump whether it is rock or a box that stopped it."""
        level = corridor(boxes=(at(5),), goals=(at(1),), player=at(4))
        _p, _b, moved, _pushed = S3.move(level, level.boxes,
                                         S3.Pose(at(4), 1), S3.AHEAD)
        self.assertEqual(S3.costs(S3.AHEAD, moved), 0)

    def test_a_walk_costs_one(self):
        self.assertEqual(S3.costs(S3.AHEAD, True), 1)

    def test_every_box_home_is_solved(self):
        self.assertTrue(S3.solved(self.level, frozenset({at(5)})))
        self.assertFalse(S3.solved(self.level, frozenset({at(4)})))


class ParTests(unittest.TestCase):
    """The minimum, and the route it claims."""

    def walked(self, level, moves):
        boxes = level.boxes
        pose = S3.Pose(level.player, S3.facing_at(level))
        spent = 0
        for doing in moves:
            pose, boxes, moved, _pushed = S3.move(level, boxes, pose, doing)
            spent += S3.costs(doing, moved)
        return spent, S3.solved(level, boxes)

    def test_a_box_one_push_from_home_costs_one_step(self):
        level = corridor(boxes=(at(2),), goals=(at(3),), player=at(1))
        self.assertEqual(S3.par(level), 1)

    def test_pushing_it_further_costs_a_step_a_cell(self):
        level = corridor(boxes=(at(2),), goals=(at(5),), player=at(1))
        self.assertEqual(S3.par(level), 3)

    def test_the_route_is_as_long_as_the_par_says(self):
        for rung in SPREAD:
            for seed in range(3):
                level = S3.deal(rung, seed=seed)
                found, _bound, moves = S3.solve_bounded(level)
                spent, done = self.walked(level, moves)
                self.assertTrue(done, 'rung %d seed %d' % (rung, seed))
                self.assertEqual(spent, found, 'rung %d seed %d'
                                 % (rung, seed))

    def test_the_contraction_agrees_with_the_plain_search(self):
        """The claim that the walk contracts away, checked rather than said."""
        for rung in (1, 2, 3, 4):
            for seed in range(3):
                level = S3.deal(rung, seed=seed)
                self.assertEqual(S3.par(level), brute(level),
                                 'rung %d seed %d' % (rung, seed))

    def test_turning_makes_a_warehouse_dearer_than_its_pushes(self):
        """Where the par being in steps rather than pushes shows up."""
        for rung in SPREAD:
            level = S3.deal(rung, seed=1)
            pushes = (level.minimum if level.minimum is not None
                      else level.at_least)
            self.assertGreater(S3.par(level), pushes, 'rung %d' % rung)

    def test_it_is_the_same_room_the_flat_ladder_deals(self):
        for rung in SPREAD:
            self.assertEqual(S3.deal(rung, seed=3),
                             S.generate(rung, seed=3))

    def test_the_search_certifies_a_minimum_low_down(self):
        for seed in range(3):
            level = S3.deal(LAST_EXACT, seed=seed)
            self.assertTrue(S3.certified(level), 'seed %d' % seed)

    def test_a_bound_is_never_a_guess(self):
        """Past the budget the par must still be a *proven* floor.

        The frontier says every remaining line costs at least this, and
        the flat game's certified push count says the same thing from
        the other side, since every push is a step. Neither may exceed
        what a real route costs, so a route the search does find has to
        clear the bound.
        """
        for rung in SPREAD:
            level = S3.deal(rung, seed=5)
            found, bound, _moves = S3.solve_bounded(level)
            pushes = (level.minimum if level.minimum is not None
                      else level.at_least)
            self.assertGreaterEqual(bound, 0)
            if found is not None:
                self.assertEqual(found, bound)
                self.assertGreaterEqual(found, pushes)

    def test_a_short_budget_still_answers_and_does_not_lie(self):
        level = S3.deal(5, seed=2)
        exact = S3.par(level)
        found, bound, _moves = S3.solve_bounded(level, budget=3)
        self.assertIsNone(found)
        self.assertLessEqual(bound, exact)


class ViewTests(unittest.TestCase):
    """What the rays find, and what a box does to them."""

    def setUp(self):
        self.level = corridor(boxes=(at(4),), goals=(at(5),), player=at(1))

    def test_a_box_stops_a_ray_where_rock_would_not(self):
        pose = S3.Pose(at(1), 1)
        with_box = S3.look_around(self.level, self.level.boxes, pose)
        empty = S3.look_around(self.level, frozenset(), pose)
        middle = len(with_box) // 2
        self.assertLess(with_box[middle].distance, empty[middle].distance)

    def test_the_ray_stops_at_the_box_and_names_its_cell(self):
        sights = S3.look_around(self.level, self.level.boxes,
                                S3.Pose(at(1), 1))
        middle = sights[len(sights) // 2]
        self.assertEqual(middle.cell, at(4))
        self.assertAlmostEqual(middle.distance, 2.5, places=6)

    def test_moving_the_box_moves_where_the_ray_stops(self):
        near = S3.look_around(self.level, frozenset({at(3)}),
                              S3.Pose(at(1), 1))
        far = S3.look_around(self.level, frozenset({at(5)}),
                             S3.Pose(at(1), 1))
        middle = len(near) // 2
        self.assertLess(near[middle].distance, far[middle].distance)

    def test_the_far_wall_is_where_it_ought_to_be(self):
        # Standing in the middle of x=1, the rock at x=6 has its near
        # face four and a half cells off.
        sights = S3.look_around(self.level, frozenset(), S3.Pose(at(1), 1))
        middle = sights[len(sights) // 2]
        self.assertAlmostEqual(middle.distance, 4.5, places=6)

    def test_a_flat_wall_ahead_is_flat_and_not_bowed(self):
        """Distances are square on, so the end wall reads as one plane."""
        sights = S3.look_around(self.level, frozenset(), S3.Pose(at(1), 1))
        straight = [s for s in sights if s.side == 0 and s.distance < S3.FAR]
        self.assertTrue(straight)
        for sight in straight:
            self.assertAlmostEqual(sight.distance, 4.5, places=6)

    def test_it_casts_the_columns_it_is_asked_for(self):
        self.assertEqual(len(S3.look_around(self.level, self.level.boxes,
                                            S3.Pose(at(1), 1), columns=24)),
                         24)

    def test_a_real_warehouse_casts_from_every_cell_it_has(self):
        level = S3.deal(3, seed=0)
        floor_ok = S3.floor_of(level)
        for cell in range(level.width * level.height):
            if not floor_ok[cell] or cell in level.boxes:
                continue
            for facing in range(4):
                sights = S3.look_around(level, level.boxes,
                                        S3.Pose(cell, facing), columns=16)
                self.assertEqual(len(sights), 16)


class MarkTests(unittest.TestCase):
    """The rings hanging where a goal still wants a box."""

    def setUp(self):
        self.level = corridor(boxes=(at(2),), goals=(at(5),), player=at(1))

    def test_a_goal_down_the_corridor_is_seen(self):
        seen = S3.marks(self.level, frozenset(), S3.Pose(at(1), 1))
        self.assertEqual([mote.cell for mote in seen], [at(5)])

    def test_nothing_behind_you_is_seen(self):
        self.assertEqual(S3.marks(self.level, frozenset(),
                                  S3.Pose(at(1), 3)), ())

    def test_a_goal_with_a_box_on_it_stops_being_a_mark(self):
        self.assertEqual(S3.marks(self.level, frozenset({at(5)}),
                                  S3.Pose(at(1), 1)), ())

    def test_a_goal_behind_a_box_is_out_of_sight(self):
        """One of the ways a player learns the plan has gone stale."""
        self.assertEqual(S3.marks(self.level, self.level.boxes,
                                  S3.Pose(at(1), 1)), ())

    def test_the_far_ones_come_first_so_the_near_ones_draw_over_them(self):
        level = corridor(boxes=(), goals=(at(4), at(5)), player=at(1))
        seen = S3.marks(level, frozenset(), S3.Pose(at(1), 1))
        self.assertEqual([mote.cell for mote in seen], [at(5), at(4)])


class TheStuckTest(unittest.TestCase):
    """The flat game's own verdict, reached from inside."""

    def test_a_box_shoved_into_a_corner_is_provably_lost(self):
        # The goal is behind the player; every push takes the box
        # further from it, and the last cell of the corridor is one
        # nothing can be pushed out of.
        level = corridor(boxes=(at(3),), goals=(at(2),), player=at(2))
        boxes, pose = level.boxes, S3.Pose(at(2), 1)
        while True:
            pose, shifted, moved, _p = S3.move(level, boxes, pose, S3.AHEAD)
            if not moved:
                break
            boxes = shifted
        self.assertTrue(S3.stuck(level, boxes))

    def test_a_warehouse_as_dealt_is_never_already_lost(self):
        for rung in SPREAD:
            for seed in range(4):
                level = S3.deal(rung, seed=seed)
                self.assertFalse(S3.stuck(level, level.boxes),
                                 'rung %d seed %d' % (rung, seed))


class PlayerTests(unittest.TestCase):
    """The foils, and what losing your place costs in a game that does
    not forgive.

    Both numbers below are floors on a measurement, not the measurement:
    the sweeps that produced them are in the Readme, over thirty
    warehouses a rung rather than the handful a unit test can afford.
    What is held here is the shape — that forgetting the load costs
    steps, that dropping the whole update costs the warehouse, and that
    a player which does neither walks the minimum exactly.
    """

    def test_a_player_that_never_slips_walks_the_minimum(self):
        rng = random.Random(0)
        for rung in (1, 2, 3):
            for seed in range(3):
                level = S3.deal(rung, seed=seed)
                out = S3.push_slipping(level, 0.0, rng)
                self.assertEqual(out.ending, 'solved')
                self.assertEqual(out.steps, S3.par(level))

    def test_forgetting_the_load_costs_steps(self):
        rng = random.Random(3)
        clean, muddled = [], []
        for seed in range(8):
            level = S3.deal(3, seed=seed)
            best = S3.par(level)
            clean.append(S3.push_forgetful(level, 0.0, rng).steps / best)
            out = S3.push_forgetful(level, 0.5, rng)
            if out.ending == 'solved':
                muddled.append(out.steps / best)
        self.assertEqual(max(clean), 1.0)
        self.assertGreater(sum(muddled) / len(muddled), 1.0)

    def test_dropping_the_whole_update_costs_the_warehouse(self):
        """The difference from the 3D Maze, stated as a number.

        There, a player that loses its place walks further. Here it
        finishes far fewer of them at all — and the endings say why: it
        is provably stuck, or standing among boxes believing it has
        finished.
        """
        rng = random.Random(5)
        finished = 0
        for seed in range(12):
            level = S3.deal(5, seed=seed)
            if S3.push_slipping(level, 0.15, rng).ending == 'solved':
                finished += 1
        self.assertLess(finished, 6)

    def test_slipping_more_never_helps(self):
        rng = random.Random(9)
        got = []
        for slip in (0.0, 0.1, 0.3):
            done = 0
            for seed in range(6):
                level = S3.deal(3, seed=seed)
                done += S3.push_slipping(level, slip, rng).ending == 'solved'
            got.append(done)
        self.assertEqual(got, sorted(got, reverse=True))

    def test_every_ending_is_one_of_the_four(self):
        rng = random.Random(11)
        endings = set()
        for seed in range(10):
            level = S3.deal(3, seed=seed)
            endings.add(S3.push_slipping(level, 0.2, rng).ending)
            endings.add(S3.push_forgetful(level, 0.5, rng).ending)
        self.assertTrue(endings <= {'solved', 'stuck', 'thinks it is done',
                                    'adrift'}, endings)


def blend(one, other, part):
    """One colour *part* of the way to another, as a screen blends them."""
    return tuple(int(round(a + (b - a) * part))
                 for a, b in zip(one, other))


def verdictish(pixel):
    """Whether the outcome reader would count this pixel as a verdict."""
    from neural_workshop.ui.verdict import BRIGHT, DIM
    return any(pixel[one] >= BRIGHT
               and all(pixel[other] <= DIM
                       for other in range(3) if other != one)
               for one in range(3))


class WhyTheStageStopsAboveTheBand(unittest.TestCase):
    """The reason for the layout, kept beside the layout.

    ``tests/check_band.py`` sweeps this task and reports it clean. That
    is not evidence, and the lesson is already written down in this
    repository: a violation that depends on *what* got drawn rather
    than on *where* it got drawn is exactly the kind a sample reports
    clean two runs in three. Reflex was reported clean about two runs
    in three while it was painting photographs into the band.

    So the palette is enumerated instead of sampled, and what the
    enumeration found is the reason this stage stops where it does. A
    box is Okabe-Ito sky blue, which is not a verdict colour; drawn
    against the dark room's near-black ceiling its anti-aliased edge
    passes straight through the reader's window on the way. The defence
    is geometry — see the two screen tests below — and this class
    exists so that the geometry keeps its reason. If a future palette
    made the finding below false, this fails and says the reason has
    gone stale, rather than leaving a layout nobody can account for.

    Writing this down is what turned up the same fault, worse, in the
    3D Maze next door, which had been shipping it: a map palette with
    an outright verdict colour in it, over a stage that reached into
    the band. That one hid from the sweep along a third axis again —
    not content, but the *shape of the window* — and
    :mod:`tests.test_youarehere` now carries the argument for it.
    """

    STEPS = 256

    def test_the_reader_would_know_a_verdict_if_it_saw_one(self):
        """Or everything else here is checking nothing at all."""
        self.assertTrue(verdictish((213, 94, 0)))
        self.assertFalse(verdictish((0, 158, 115)))
        self.assertFalse(verdictish((170, 170, 170)))

    def test_a_box_is_not_a_verdict_colour(self):
        from neural_workshop.ui.sokoban import BOX, BOX_HOME
        self.assertFalse(verdictish(BOX))
        self.assertFalse(verdictish(BOX_HOME))

    def test_but_its_edge_against_a_dark_ceiling_is_one(self):
        from neural_workshop.ui.sokoban import BOX
        from neural_workshop.ui.youarehere import DARK_ROOM
        ceiling = DARK_ROOM[0]
        caught = [blend(BOX, ceiling, part / float(self.STEPS))
                  for part in range(self.STEPS + 1)
                  if verdictish(blend(BOX, ceiling, part / float(self.STEPS)))]
        self.assertTrue(caught, 'the reason for the layout has gone stale')


@needs_ui
class Sokoban3DScreenTests(unittest.TestCase):
    """The screen: a corridor that moves, and a plan that does not."""

    RUNG = 2

    def setUp(self):
        close_overlays()
        self.task = Sokoban3D()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.start_rung = self.task.rung = self.RUNG

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _finish(self):
        for doing in S3.solve_bounded(self.task.level,
                                      boxes=self.task.boxes,
                                      pose=self.task.pose)[2]:
            self.task.walk(doing)

    def test_it_is_in_the_planning_category(self):
        self.assertIn('sokoban_3d',
                      [task for task, _n in TASKS['planning']])

    def test_a_trial_deals_a_warehouse_and_stands_you_in_it(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'pushing')
        self.assertEqual(self.task.pose.cell, self.task.level.player)
        self.assertEqual(self.task.boxes, self.task.level.boxes)
        self.assertEqual(self.task.steps, 0)
        self.task.on_draw()

    def test_the_arrows_turn_walk_and_push(self):
        self.task.start_run()
        was = self.task.pose.facing
        self.task.on_key_press(key.RIGHT, 0)
        self.assertEqual(self.task.pose.facing, (was + 1) % 4)
        self.assertEqual(self.task.steps, 1)

    def _stand_in(self, level, facing):
        """Put the run in a warehouse chosen rather than dealt.

        A dealt room is a fine thing to walk but a poor thing to make a
        claim about: whether it has rock to the west, or a pocket three
        pushes away, is up to the generator. These two tests are about
        what the screen does in a named position, so the position is
        named.
        """
        self.task.start_run()
        self.task.level = level
        self.task.par = S3.par(level)
        self.task.certified = True
        self.task._restart_run()
        self.task.pose = S3.Pose(level.player, facing)

    def test_walking_into_rock_costs_nothing(self):
        self._stand_in(corridor(boxes=(at(3),), goals=(at(4),),
                                player=at(1)), 3)
        self.task.walk(S3.AHEAD)
        self.assertEqual(self.task.steps, 0)
        self.assertEqual(self.task.bumps, 1)

    def test_finishing_ends_the_warehouse(self):
        self.task.start_run()
        self._finish()
        self.assertEqual(self.task.phase, 'solved')
        self.assertEqual(self.task.steps, self.task.par)
        self.assertEqual(self.task.verdict_shown[0], True)

    def test_a_provably_lost_position_says_so_and_pays(self):
        """The goal is behind you and the corridor ends: shove on."""
        self._stand_in(corridor(boxes=(at(3),), goals=(at(2),),
                                player=at(2)), 1)
        for _push in range(4):
            self.task.walk(S3.AHEAD)
        self.assertEqual(self.task.phase, 'lost')
        self.assertEqual(self.task.verdict_shown[0], False)
        self.assertEqual(self.task.score()['lost'], 1)

    def test_undo_puts_the_box_back(self):
        self.task.start_run()
        before = (self.task.boxes, self.task.pose, self.task.steps)
        self.task.walk(S3.AHEAD)
        self.task.walk(S3.RIGHT)
        self.task.undo()
        self.task.undo()
        self.assertEqual((self.task.boxes, self.task.pose, self.task.steps),
                         before)

    def test_restart_puts_you_back_and_zeroes_the_count(self):
        self.task.start_run()
        self.task.walk(S3.RIGHT)
        self.task.walk(S3.AHEAD)
        self.task.restart()
        self.assertEqual(self.task.boxes, self.task.level.boxes)
        self.assertEqual(self.task.pose.cell, self.task.level.player)
        self.assertEqual(self.task.steps, 0)

    def test_the_run_finishes_after_its_warehouses(self):
        self.task.start_run()
        for _trial in range(self.task.total_trials):
            self._finish()
            self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['solved'],
                         self.task.total_trials)

    def test_adaptive_climbs_after_a_tidy_run(self):
        self.task.adaptive = True
        self.task.start_run()
        self._finish()
        self.assertEqual(self.task.rung, self.RUNG + 1)

    def test_it_draws_in_every_phase(self):
        self.task.on_draw()
        self.task.start_run()
        self.task.on_draw()
        self._finish()
        self.task.on_draw()
        self.task.on_key_press(key.SPACE, 0)
        self.task.on_draw()

    def test_it_draws_with_the_traps_and_the_rings_off(self):
        self.task.show_traps = True
        self.task.show_marks = False
        self.task.start_run()
        self.task.on_draw()

    def test_neither_panel_reaches_into_the_band(self):
        """Both halves, by geometry, whatever the deal put in them.

        A panel centres its grid inside itself, so whether anything is
        drawn along its bottom edge depends on the aspect of the window
        and on how tall the warehouse is. That makes a pixel sweep the
        wrong instrument, and the bottom edge of the stage the right
        one: nothing this screen paints starts below it.
        """
        from neural_workshop.ui.verdict import band_rows
        self.task.start_run()
        first, _past = band_rows(state.window.height)
        ceiling = state.window.height - first
        for rect in (self.task._view_rect(), self.task._plan_rect(),
                     self.task._stage()):
            self.assertGreaterEqual(rect[1], ceiling)

    def test_the_view_and_the_plan_do_not_overlap(self):
        self.task.start_run()
        view_left, _vb, view_wide, _vh = self.task._view_rect()
        plan_left, _pb, _pw, _ph = self.task._plan_rect()
        self.assertLess(view_left + view_wide, plan_left)

    def test_every_cell_of_the_plan_lands_inside_its_panel(self):
        self.task.start_run()
        left, bottom, wide, tall = self.task._plan_rect()
        level = self.task.level
        for cell in range(level.width * level.height):
            x, y, side = self.task._cell_rect(cell)
            self.assertGreaterEqual(x, left - 1)
            self.assertGreaterEqual(y, bottom - 1)
            self.assertLessEqual(x + side, left + wide + 1)
            self.assertLessEqual(y + side, bottom + tall + 1)

    def _plan_pixels(self):
        """Digest only the pixels under the plan panel.

        Cut to the panel's own band rather than to the whole width,
        because the status line above it changes on every action and
        would otherwise drown the very thing being measured. Trimmed by
        the same amount at both ends so it is the right band whichever
        way round the capture stores its rows.
        """
        wide, tall, rgba = capture_rgba(state.window)
        scale = wide / float(state.window.width)
        left, bottom, _panel_wide, panel_tall = self.task._plan_rect()
        first = int(bottom * scale) + 2
        last = int((bottom + panel_tall) * scale) - 2
        first, last = max(first, tall - last), min(last, tall - first)
        start_x = int(left * scale)
        rows = [rgba[(row * wide + start_x) * 4:(row * wide + wide) * 4]
                for row in range(first, last)]
        return digest_rgba(b''.join(rows))

    def test_the_plan_does_not_move_when_a_box_does(self):
        """The task's one promise, read off the pixels themselves.

        Not "the plan is rebuilt from the same data" and not "nothing in
        the movement path calls the plan builder" — the actual pixels
        under the panel, before a push and after it, with a box standing
        where the plan does not show one and the player somewhere else
        entirely. If anything about the state of the room ever reached
        the plan, this is where it would show.
        """
        self.task.rng.seed(7)
        self.task.start_run()
        self.task.on_draw()
        before = self._plan_pixels()
        moves = S3.solve_bounded(self.task.level)[2]
        for doing in moves:
            self.task.walk(doing)
            if self.task.boxes != self.task.level.boxes:
                break
        self.task.on_draw()
        self.assertNotEqual(self.task.boxes, self.task.level.boxes)
        self.assertNotEqual(self.task.pose.cell, self.task.level.player)
        self.assertEqual(self._plan_pixels(), before)

    def test_the_view_does_move_when_the_player_does(self):
        """The other half, so the test above cannot pass by drawing nothing."""
        self.task.start_run()
        self.task.on_draw()
        before = digest_rgba(capture_rgba(state.window)[2])
        self.task.walk(S3.RIGHT)
        self.task.on_draw()
        self.assertNotEqual(digest_rgba(capture_rgba(state.window)[2]),
                            before)

    def test_the_plan_is_not_even_rebuilt_while_pushing(self):
        """Belt to the pixel test's braces: the shapes are the same objects."""
        self.task.start_run()
        was = [id(shape) for shape in self.task.plan_drawn]
        self.assertTrue(was)
        for doing in S3.solve_bounded(self.task.level)[2][:4]:
            self.task.walk(doing)
        self.assertEqual([id(shape) for shape in self.task.plan_drawn], was)

    def test_a_new_warehouse_does_get_a_new_plan(self):
        self.task.start_run()
        was = [id(shape) for shape in self.task.plan_drawn]
        self._finish()
        self.task.on_key_press(key.SPACE, 0)
        self.assertNotEqual([id(shape) for shape in self.task.plan_drawn],
                            was)

    def test_it_has_an_options_screen(self):
        spec = taskoptions.TASK_SPECS['sokoban_3d']
        chosen = dict(taskoptions.settings(spec))
        self.assertIn('SOKO3D_LEVEL', chosen)
        self.assertTrue(spec.note(chosen))

    def test_the_note_says_the_plan_will_go_stale(self):
        spec = taskoptions.TASK_SPECS['sokoban_3d']
        chosen = dict(taskoptions.settings(spec))
        chosen['SOKO3D_LEVEL'] = 4
        said = spec.note(chosen)
        self.assertIn('never says where the boxes are now', said)

    def test_the_note_admits_when_the_par_is_a_bound(self):
        spec = taskoptions.TASK_SPECS['sokoban_3d']
        chosen = dict(taskoptions.settings(spec))
        chosen['SOKO3D_LEVEL'] = LAST_EXACT + 1
        self.assertIn('proven lower bound', spec.note(chosen))


if __name__ == '__main__':
    unittest.main()
