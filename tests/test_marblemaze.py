#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Marble Maze's trays and its physics, without a GL context.

Everything here is arithmetic, which is the point of keeping
:mod:`neural_workshop.marblemaze` free of pyglet: the parts of this task
that can be wrong quietly — a tray that cannot be won, a shaping
potential that jumps two steps in a tick, a marble accelerating as
though it were sliding rather than rolling — are all testable without
opening a window.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neural_workshop import marblemaze as M


class TheLadderIsBuildable(unittest.TestCase):
    """Every rung deals, and deals the rung it was asked for."""

    def test_every_rung_deals_its_own_rung(self):
        for rung in range(1, len(M.GRADES) + 1):
            tray = M.deal(rung, seed=4000 + rung)
            self.assertEqual(tray.rung, rung, M.GRADES[rung - 1].name)

    def test_a_corridor_always_fits_the_marble_and_a_hole_beside_it(self):
        """``2·slack > hole_scale + margin_scale + 1``, for every rung.

        This is the inequality that decides whether a hole can sit in a
        corridor with the marble still able to squeeze past on the far
        side. Where it fails, hole placement does not fail — it shoves
        the holes out under the walls, where they are a notch bitten
        out of a corridor edge rather than a hazard in the road, and
        the rung quietly stops being the rung it claims to be.
        """
        for rung, grade in enumerate(M.GRADES, start=1):
            needed = (grade.hole_scale + grade.margin_scale + 1.0) / 2.0
            self.assertGreater(grade.slack, needed,
                               'rung %d (%s) has no room for its holes'
                               % (rung, grade.name))

    def test_the_marble_fits_down_every_corridor(self):
        for rung in range(1, len(M.GRADES) + 1):
            tray = M.deal(rung, seed=7100 + rung)
            self.assertGreater(tray.corridor, 2.0 * M.MARBLE_RADIUS,
                               'rung %d' % rung)

    def test_a_tray_is_certified_before_it_is_dealt(self):
        """Every marble can actually reach the cup, on every rung.

        The strict lookup rather than the widening one: a start point
        one grid cell inside a sealed pocket would borrow a neighbour's
        answer, and the one question a certificate exists to settle is
        exactly that one.
        """
        for rung in range(1, len(M.GRADES) + 1):
            for run in range(3):
                tray = M.deal(rung, seed=200 + run * 97 + rung)
                for (x, y) in tray.starts:
                    self.assertIsNotNone(
                        tray.field.strict(x, y),
                        'rung %d: a marble cannot reach the cup' % rung)

    def test_the_rung_deals_the_marbles_it_promises(self):
        for rung, grade in enumerate(M.GRADES, start=1):
            tray = M.deal(rung, seed=880 + rung)
            self.assertEqual(len(tray.starts), grade.marbles,
                             'rung %d (%s)' % (rung, grade.name))

    def test_marbles_do_not_start_on_top_of_each_other(self):
        for rung, grade in enumerate(M.GRADES, start=1):
            if grade.marbles < 2:
                continue
            tray = M.deal(rung, seed=1500 + rung)
            for a in range(len(tray.starts)):
                for b in range(a + 1, len(tray.starts)):
                    gap = math.dist(tray.starts[a], tray.starts[b])
                    self.assertGreater(gap, 2.0 * M.MARBLE_RADIUS,
                                       'rung %d' % rung)

    def test_no_marble_starts_on_the_rim_of_a_hole(self):
        """Clear of the rim by a real margin, not merely outside it.

        Merely-outside was the first version and it cost a trial: the
        free grid rules out points inside a hole, so the furthest legal
        point on the tray is often *exactly on a rim*, and random play
        at rung four then resolved at a median of 59 ticks because half
        the trays dropped their marble down the hole it was standing on
        inside the first second. The tray has to be losable rather than
        already lost.
        """
        for rung in range(1, len(M.GRADES) + 1):
            for run in range(3):
                tray = M.deal(rung, seed=2600 + run * 41 + rung)
                for (x, y) in tray.starts:
                    for hole in tray.holes:
                        if hole.home:
                            continue
                        room = (hole.radius
                                + M.MARBLE_RADIUS * M.START_CLEARANCE)
                        self.assertGreaterEqual(
                            math.hypot(x - hole.x, y - hole.y), room,
                            'rung %d starts a marble on a rim' % rung)

    def test_the_route_is_worth_walking(self):
        """A high rung must not deal an easier tray than a low one.

        Holes cut the tray up, and a tray cut into pockets still
        certifies — the marble is placed in the pocket the cup is in,
        and everything passes while "inhuman" deals a marble twelve
        centimetres from home. The route bar in ``_build`` is what
        stops that, and this is the test that would catch it going
        away.
        """
        for rung in range(1, len(M.GRADES) + 1):
            worst = min(M.deal(rung, seed=3300 + run * 31 + rung).route
                        for run in range(4))
            self.assertGreater(worst, 0.10,
                               'rung %d deals a marble next to the cup'
                               % rung)


class TheMarbleRollsLikeASphere(unittest.TestCase):

    @staticmethod
    def _bare_tray():
        """One rung-1 tray with the walls and holes taken out of it."""
        tray = M.deal(1, seed=17)
        return tray._replace(walls=(), holes=())

    def _lone_marble(self, roll=0.0, pitch=0.0):
        tray = self._bare_tray()
        sim = M.Simulation(tray)
        sim.marbles = [M.Marble(tray.width / 2.0, tray.depth / 2.0)]
        sim.roll, sim.pitch = roll, pitch
        return sim

    def test_it_accelerates_at_five_sevenths_of_gravity(self):
        """The rolling factor, measured off one substep from rest.

        Two sevenths of gravity goes into spin. Drop the factor and the
        marble is 40% too eager, which reads to a player as a board
        twice as steep as it looks rather than as wrong physics.
        """
        angle = 0.10
        sim = self._lone_marble(roll=angle)
        dt = 1 / 240.0
        sim._substep(dt)
        got = sim.marbles[0].vx / dt

        rolling = M.ROLL_FACTOR * M.GRAVITY * math.sin(angle)
        # Resistance is taken off inside the same substep, so what comes
        # out is the *net* acceleration and the whole of it is
        # predictable: the rolling term, less a constant
        # ``Crr·g·cosθ`` that does not depend on speed, less a viscous
        # term that at this point still does.
        resistance = M.ROLLING_RESISTANCE * M.GRAVITY * math.cos(angle)
        viscous = M.VISCOUS_DRAG * rolling * dt
        self.assertAlmostEqual(got, rolling - resistance - viscous,
                               places=6)

        # And the qualitative half, which is the one that would catch
        # the factor going away: a *sliding* sphere would be a full
        # seven fifths of this, and the gap has to be unmistakable.
        sliding = M.GRAVITY * math.sin(angle)
        self.assertLess(got, sliding * 0.80)

    def test_a_shallow_enough_slope_does_not_start_it_at_all(self):
        """Rolling resistance sets a slope below which nothing happens.

        Real, and worth having: it is why a marble does not creep
        across a tray a player believes is level, and it is what makes
        levelling the tray a usable move rather than an approximate
        one.
        """
        stalls = M.ROLLING_RESISTANCE / M.ROLL_FACTOR
        sim = self._lone_marble(roll=stalls * 0.5)
        for _ in range(60 * 5):
            sim.step(1 / 60.0)
        self.assertEqual(sim.marbles[0].speed, 0.0)

    def test_a_level_tray_leaves_it_where_it_is(self):
        sim = self._lone_marble()
        before = (sim.marbles[0].x, sim.marbles[0].y)
        for _ in range(120):
            sim.step(1 / 60.0)
        self.assertAlmostEqual(sim.marbles[0].x, before[0], places=9)
        self.assertAlmostEqual(sim.marbles[0].y, before[1], places=9)

    def test_it_rolls_downhill_the_way_the_knob_says(self):
        east = self._lone_marble(roll=0.10)
        for _ in range(30):
            east.step(1 / 60.0)
        self.assertGreater(east.marbles[0].vx, 0.0)
        north = self._lone_marble(pitch=-0.10)
        for _ in range(30):
            north.step(1 / 60.0)
        self.assertGreater(north.marbles[0].vy, 0.0)

    def test_it_comes_to_rest_once_the_tray_is_levelled(self):
        sim = self._lone_marble(roll=0.12)
        for _ in range(60):
            sim.step(1 / 60.0)
        self.assertGreater(sim.marbles[0].speed, 0.05)
        sim.level()
        for _ in range(60 * 12):
            sim.step(1 / 60.0)
        self.assertLess(sim.marbles[0].speed, 0.005)

    def test_it_never_passes_the_speed_cap(self):
        sim = self._lone_marble(roll=M.MAX_TILT)
        for _ in range(60 * 20):
            sim.step(1 / 60.0)
            self.assertLessEqual(sim.marbles[0].speed, M.SPEED_CAP + 1e-9)

    def test_a_wall_stops_it_and_takes_some_of_the_bounce(self):
        tray = M.deal(1, seed=17)._replace(holes=())
        sim = M.Simulation(tray)
        sim.marbles = [M.Marble(tray.width / 2.0, tray.depth / 2.0)]
        sim.roll = M.MAX_TILT
        for _ in range(60 * 8):
            sim.step(1 / 60.0)
        marble = sim.marbles[0]
        # Inside the tray, wherever the walls left it.
        self.assertGreater(marble.x, 0.0)
        self.assertLess(marble.x, tray.width)
        self.assertGreater(marble.y, 0.0)
        self.assertLess(marble.y, tray.depth)

    def test_it_never_ends_a_step_inside_a_wall(self):
        tray = M.deal(8, seed=64)
        sim = M.Simulation(tray)
        rng = random.Random(3)
        for _ in range(60 * 20):
            for _ in range(3):
                sim.tilt(rng.choice((M.TILT_NORTH, M.TILT_SOUTH,
                                     M.TILT_WEST, M.TILT_EAST)))
            sim.step(1 / 60.0)
            for marble in sim.marbles:
                if not marble.live:
                    continue
                for wall in tray.walls:
                    near_x = min(max(marble.x, wall.x0), wall.x1)
                    near_y = min(max(marble.y, wall.y0), wall.y1)
                    gap = math.hypot(marble.x - near_x, marble.y - near_y)
                    self.assertGreater(gap, M.MARBLE_RADIUS * 0.75)
            if sim.settled:
                break


class AHoleIsNotAWall(unittest.TestCase):
    """A marble can outrun a hole, and that is the whole of going fast."""

    @staticmethod
    def _one_hole(radius_scale=1.6):
        tray = M.deal(1, seed=11)
        hole = M.Hole(tray.width / 2.0, tray.depth / 2.0,
                      M.MARBLE_RADIUS * radius_scale, False)
        return tray._replace(holes=(hole,), walls=())

    def _cross_at(self, speed, radius_scale=1.6):
        tray = self._one_hole(radius_scale)
        sim = M.Simulation(tray)
        sim.marbles = [M.Marble(tray.width / 2.0 - 0.05, tray.depth / 2.0)]
        sim.marbles[0].vx = speed
        for _ in range(240):
            sim.step(1 / 60.0)
            if not sim.marbles[0].live:
                break
        return sim.marbles[0].state

    def test_a_slow_marble_falls_in(self):
        self.assertEqual(self._cross_at(0.15), 'lost')
        self.assertEqual(self._cross_at(0.40), 'lost')

    def test_a_fast_one_clears_the_far_rim(self):
        self.assertEqual(self._cross_at(0.95), 'rolling')

    def test_a_wide_enough_hole_cannot_be_outrun(self):
        """There is a size past which speed stops helping.

        Which is what keeps the trick honest: if every hole could be
        jumped, the whole task would be "go flat out", and the ladder's
        hole sizes are chosen against the marble rather than against a
        look.
        """
        self.assertEqual(self._cross_at(M.SPEED_CAP, radius_scale=3.2),
                         'lost')

    def test_the_cup_takes_a_marble_home(self):
        tray = M.deal(1, seed=11)
        cup = M.Hole(tray.width / 2.0, tray.depth / 2.0,
                     M.MARBLE_RADIUS * 1.8, True)
        tray = tray._replace(holes=(cup,), walls=())
        sim = M.Simulation(tray)
        sim.marbles = [M.Marble(tray.width / 2.0 - 0.03, tray.depth / 2.0)]
        sim.marbles[0].vx = 0.20
        for _ in range(240):
            sim.step(1 / 60.0)
            if sim.settled:
                break
        self.assertEqual(sim.marbles[0].state, 'home')
        self.assertTrue(sim.won)


class MarblesShareOneTray(unittest.TestCase):

    def test_they_bounce_off_each_other_rather_than_through(self):
        tray = M.deal(1, seed=23)._replace(holes=(), walls=())
        sim = M.Simulation(tray)
        middle = tray.depth / 2.0
        sim.marbles = [M.Marble(tray.width / 2.0 - 0.04, middle),
                       M.Marble(tray.width / 2.0 + 0.04, middle)]
        sim.marbles[0].vx = 0.5
        for _ in range(120):
            sim.step(1 / 60.0)
            gap = abs(sim.marbles[1].x - sim.marbles[0].x)
            self.assertGreater(gap, 2.0 * M.MARBLE_RADIUS - 1e-6)
        # The struck one has been sent on its way.
        self.assertGreater(sim.marbles[1].vx, 0.05)

    def test_the_tray_is_lost_if_any_marble_is(self):
        tray = M.deal(5, seed=31)
        sim = M.Simulation(tray)
        sim.marbles[0].state = 'lost'
        for marble in sim.marbles[1:]:
            marble.state = 'home'
        self.assertTrue(sim.settled)
        self.assertFalse(sim.won)


class TheCoachTellsNoTales(unittest.TestCase):
    """The shaping potential, and the rule that makes it safe."""

    def test_one_tick_cannot_move_the_potential_by_more_than_one(self):
        """The geometric guarantee, stated as arithmetic.

        A geodesic distance is 1-Lipschitz, so it cannot change by more
        than the distance travelled; a tick travels at most
        ``SPEED_CAP/60``; so a quantum wider than that leaves the floor
        of the ratio moving by one step or none. The margin is a third
        rather than a hair because the field is a *grid* geodesic and an
        eight-connected grid metric overstates a diagonal by a few
        percent.
        """
        per_tick = M.SPEED_CAP / 60.0
        self.assertLess(per_tick, M.POTENTIAL_QUANTUM)
        self.assertLess(per_tick, M.POTENTIAL_QUANTUM * 0.75)

    def test_it_holds_when_the_tray_is_actually_played(self):
        for rung in (1, 2, 4, 6, 8, 10, 12, 14):
            if M.GRADES[rung - 1].marbles != 1:
                continue
            tray = M.deal(rung, seed=770 + rung)
            sim = M.Simulation(tray)
            rng = random.Random(rung)
            before = sim.potential()
            for _ in range(60 * 25):
                for _ in range(3):
                    sim.tilt(rng.choice((M.TILT_NORTH, M.TILT_SOUTH,
                                         M.TILT_WEST, M.TILT_EAST)))
                sim.step(1 / 60.0)
                now = sim.potential()
                if before is not None and now is not None:
                    self.assertLessEqual(abs(now - before), 1,
                                         'rung %d jumped the potential'
                                         % rung)
                before = now
                if sim.settled:
                    break

    def test_the_potential_falls_to_nothing_at_the_cup(self):
        tray = M.deal(3, seed=52)
        home_x, home_y, _radius = tray.home
        near = M.potential_at(tray, home_x, home_y)
        self.assertIsNotNone(near)
        self.assertLessEqual(near, 1)
        start = M.potential_at(tray, *tray.starts[0])
        self.assertIsNotNone(start)
        self.assertGreater(start, near)

    def test_it_says_nothing_rather_than_something_wrong_off_the_tray(self):
        tray = M.deal(2, seed=61)
        self.assertIsNone(M.potential_at(tray, -1.0, -1.0))

    def test_a_falling_marble_has_no_potential(self):
        """Mid-drop is not a place, so there is no honest distance to it."""
        tray = M.deal(2, seed=61)
        sim = M.Simulation(tray)
        sim.marbles[0].state = 'falling'
        self.assertIsNone(sim.potential())


class TheSimulationIsDeterministic(unittest.TestCase):

    def test_the_same_seed_deals_the_same_tray(self):
        first = M.deal(9, seed=1234)
        second = M.deal(9, seed=1234)
        self.assertEqual(first.walls, second.walls)
        self.assertEqual(first.holes, second.holes)
        self.assertEqual(first.starts, second.starts)

    def test_the_same_actions_give_the_same_run(self):
        def play():
            sim = M.Simulation(M.deal(6, seed=99))
            rng = random.Random(5)
            for _ in range(600):
                sim.tilt(rng.choice((M.TILT_NORTH, M.TILT_SOUTH,
                                     M.TILT_WEST, M.TILT_EAST)))
                sim.step(1 / 60.0)
            return [(m.x, m.y, m.vx, m.vy, m.state) for m in sim.marbles]
        self.assertEqual(play(), play())

    def test_nothing_in_the_model_reads_the_wall_clock(self):
        """The driver owns the clock, so this module may not have one."""
        import inspect
        source = inspect.getsource(M)
        self.assertNotIn('time.time', source)
        self.assertNotIn('import time', source)


class TheKnobsHaveStops(unittest.TestCase):

    def test_tilt_never_passes_the_limit(self):
        sim = M.Simulation(M.deal(1, seed=8))
        for _ in range(500):
            sim.tilt(M.TILT_NORTH)
            sim.tilt(M.TILT_EAST)
        self.assertAlmostEqual(sim.pitch, M.MAX_TILT, places=9)
        self.assertAlmostEqual(sim.roll, M.MAX_TILT, places=9)
        for _ in range(500):
            sim.tilt(M.TILT_SOUTH)
            sim.tilt(M.TILT_WEST)
        self.assertAlmostEqual(sim.pitch, -M.MAX_TILT, places=9)
        self.assertAlmostEqual(sim.roll, -M.MAX_TILT, places=9)

    def test_levelling_puts_both_knobs_back(self):
        sim = M.Simulation(M.deal(1, seed=8))
        for _ in range(9):
            sim.tilt(M.TILT_NORTH)
            sim.tilt(M.TILT_WEST)
        sim.level()
        self.assertEqual((sim.pitch, sim.roll), (0.0, 0.0))


if __name__ == '__main__':
    unittest.main()
