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

    def test_a_wall_always_stands_at_least_as_tall_as_the_centre(self):
        """Which is what lets a wall hit the marble level with its centre.

        The wall boxes handed to the engine stand ``tray.height``
        tall, and the blow they deal is horizontal only while that
        height reaches the marble's middle. A shorter wall would catch
        it below the equator, tilt the contact normal upward, and let
        a fast marble ride over — which the certified maze never
        priced in.

        Wall height is ``max(8mm, 0.30·cell)``, so the floor of it is
        the constant rather than the ladder. This is here because a
        change to that constant or to :data:`MARBLE_RADIUS` would break
        an assumption a hundred lines away from either.
        """
        for rung in range(1, len(M.GRADES) + 1):
            tray = M.deal(rung, seed=7200 + rung)
            self.assertGreaterEqual(tray.height, M.MARBLE_RADIUS,
                                    'rung %d walls are below the marble\'s '
                                    'centre' % rung)

    def test_every_hole_is_wider_than_the_marble(self):
        """A marble stops being supported once its contact patch is over
        a hole, and from there it goes in. That is only right while the
        hole is big enough to swallow it: a narrower one would catch
        the ball on its rim and hold it there, which is a thing the
        model cannot draw and cannot resolve.
        """
        for rung in range(1, len(M.GRADES) + 1):
            tray = M.deal(rung, seed=7300 + rung)
            for hole in tray.holes:
                self.assertGreater(hole.radius, M.MARBLE_RADIUS,
                                   'rung %d has a hole that would only jam'
                                   % rung)

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

        Nothing in the model multiplies by five sevenths — the contact
        solve produces it — so this measures rather than restates. Two
        sevenths of gravity goes into spin. Drop the factor and the
        marble is 40% too eager, which reads to a player as a board
        twice as steep as it looks rather than as wrong physics.
        """
        angle = 0.10
        sim = self._lone_marble(roll=angle)
        sim.step(1 / 60.0)
        got = sim.marbles[0].vx * 60.0

        # From rest the first frame is the rolling term less the dry
        # rolling resistance, which the noslip solver applies from the
        # very first substep — both at five sevenths, like everything
        # a contact delivers. Three percent, because a contact solver
        # is an approximation and the claim under test is the factor,
        # not the solver's last digit.
        want = M.ROLL_FACTOR * M.GRAVITY * (
            math.sin(angle) - M.ROLLING_RESISTANCE * math.cos(angle))
        self.assertAlmostEqual(got, want, delta=want * 0.03)

        # And the qualitative half, which is the one that would catch
        # the factor going away: a *sliding* sphere would be a full
        # seven fifths of this, and the gap has to be unmistakable.
        sliding = M.GRAVITY * math.sin(angle)
        self.assertLess(got, sliding * 0.80)

        # The other side of the same coin: the spin it picked up is
        # the spin that rolling at that speed calls for, so the contact
        # patch is barely sliding. The bound is absolute rather than
        # proportional because a regularised solver keeps a small
        # constant slip at any speed; a marble actually skidding would
        # read a hundred times this.
        self.assertLess(sim.marbles[0].slipping, 0.003)

    def test_the_contact_patch_takes_two_sevenths_and_no_more(self):
        """The friction that holds a roll is real friction, and Coulomb-capped.

        It matters that the cap is nowhere near binding under gravity
        alone: if it were, the marble would skid down the tray instead
        of rolling down it, and every number on this page would be a
        different number.
        """
        asked = M.SLIP_SHARE * M.GRAVITY * math.sin(M.MAX_TILT)
        held = M.FRICTION_STATIC * M.GRAVITY * math.cos(M.MAX_TILT)
        self.assertLess(asked, held * 0.2,
                        'gravity alone is close to breaking the roll')

    def test_a_shallow_enough_slope_does_not_start_it_at_all(self):
        """Rolling resistance sets a slope below which nothing happens.

        Real, and worth having: it is why a marble does not creep
        across a tray a player believes is level, and it is what makes
        levelling the tray a usable move rather than an approximate
        one. The angle is ``atan(Crr)`` and both sides of it are worth
        pinning, because a threshold that never lets go is as wrong as
        one that never holds.
        """
        stalls = math.atan(M.ROLLING_RESISTANCE)
        sim = self._lone_marble(roll=stalls * 0.9)
        for _ in range(60 * 5):
            sim.step(1 / 60.0)
        self.assertEqual(sim.marbles[0].speed, 0.0)

        sim = self._lone_marble(roll=stalls * 1.6)
        for _ in range(60 * 5):
            sim.step(1 / 60.0)
        self.assertGreater(sim.marbles[0].speed, 0.001)

    def test_rolling_resistance_costs_five_sevenths_of_itself(self):
        """On the flat it decelerates at ``5/7·Crr·g``, and linearly.

        Rolling resistance is a torque about the contact point, so the
        travel only feels it through the same solve everything else
        goes through — which is why it is five sevenths and not the
        whole of it. Getting this wrong by that factor moves the stall
        angle by 40% and is invisible in play until a player starts
        trusting a levelled tray.
        """
        sim = self._lone_marble()
        marble = sim.marbles[0]
        marble.vx = 0.30
        marble.roll_with_travel()
        dt = 1 / 60.0
        # The wrapper's viscous drag is muted so what is measured is
        # the engine's rolling friction alone, which is the claim.
        real = M.VISCOUS_DRAG
        M.VISCOUS_DRAG = 0.0
        try:
            for _ in range(30):
                sim.step(dt)
            fast = marble.vx
            for _ in range(30):
                sim.step(dt)
            got = (fast - marble.vx) / (30 * dt)
        finally:
            M.VISCOUS_DRAG = real
        rolling = M.ROLL_FACTOR * M.ROLLING_RESISTANCE * M.GRAVITY
        self.assertAlmostEqual(got, rolling, delta=rolling * 0.10)

    def test_a_level_tray_leaves_it_where_it_is(self):
        sim = self._lone_marble()
        before = (sim.marbles[0].x, sim.marbles[0].y)
        for _ in range(120):
            sim.step(1 / 60.0)
        self.assertAlmostEqual(sim.marbles[0].x, before[0], places=9)
        self.assertAlmostEqual(sim.marbles[0].y, before[1], places=9)

    def test_a_settled_marble_stops_turning_as_well_as_moving(self):
        """All the way to nought, in every channel the eye has.

        The marble wears a photograph, so a spin about the tray's own
        normal is visible even when nothing is moving. Decay it
        exponentially and it only ever *approaches* nought: a marble
        parked in a corner would go on rotating its picture for the
        rest of the trial, which is the same lie as a levelled tray
        that still creeps.
        """
        sim = self._lone_marble()
        marble = sim.marbles[0]
        marble.wz = 40.0                  # spinning like a top
        for _ in range(60 * 4):
            sim.step(1 / 60.0)
        self.assertEqual(marble.wz, 0.0)
        was = (marble.qw, marble.qx, marble.qy, marble.qz)
        for _ in range(60):
            sim.step(1 / 60.0)
        # Still, to any eye: the engine renormalises the quaternion
        # each step, which can move the last bits, and nothing else.
        for got, prior in zip((marble.qw, marble.qx, marble.qy,
                               marble.qz), was):
            self.assertAlmostEqual(got, prior, places=12)

    def test_it_rolls_downhill_the_way_the_knob_says(self):
        """All four knobs, turned by name, checked against the compass.

        This drives :meth:`Simulation.tilt` rather than setting pitch
        and roll behind it, and that is the whole point of it. The
        version that set the angles directly could only ever restate
        the sign convention it had just written down, and it let north
        and south sit backwards — named for the edge that lifts while
        east and west were named for the marble — for as long as
        nobody read the two side by side.
        """
        compass = ((M.TILT_NORTH, 0.0, 1.0), (M.TILT_SOUTH, 0.0, -1.0),
                   (M.TILT_EAST, 1.0, 0.0), (M.TILT_WEST, -1.0, 0.0))
        for knob, want_x, want_y in compass:
            sim = self._lone_marble()
            for _ in range(30):
                sim.tilt(knob)
                sim.step(1 / 60.0)
            marble = sim.marbles[0]
            went = (marble.vx * want_x + marble.vy * want_y) / marble.speed
            self.assertGreater(
                went, 0.99,
                'knob %r sent the marble (%+.3f, %+.3f)'
                % (knob, marble.vx, marble.vy))

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


class SpinIsARealDegreeOfFreedom(unittest.TestCase):
    """The marble's spin is integrated, not read off its velocity.

    Which only shows up where the two disagree — and they disagree
    every time something breaks the roll. These are the tests that a
    slaved spin could not pass.
    """

    @staticmethod
    def _flat(walls=()):
        tray = M.deal(1, seed=17)._replace(walls=tuple(walls), holes=())
        sim = M.Simulation(tray)
        sim.marbles = [M.Marble(tray.width / 2.0, tray.depth / 2.0)]
        return sim, sim.marbles[0], tray

    def test_a_bounce_leaves_the_contact_patch_sliding(self):
        """It comes off the wall still spinning the way it was going.

        Nothing touched the spin: the wall hit the marble level with
        its centre, so the blow had no leverage on the roll at all.
        The patch is left sliding at very nearly ``(1 + e)`` times the
        approach, which is the whole reason the next test is true.
        """
        sim, marble, tray = self._flat(
            walls=(M.Wall(0.30, 0.02, 0.31, 0.40),))
        marble.x, marble.y = 0.20, tray.depth / 2.0
        marble.vx = 0.5
        marble.roll_with_travel()
        self.assertAlmostEqual(marble.slipping, 0.0, places=12)
        for _ in range(120):
            sim.step(1 / 60.0)
            if marble.vx < 0.0:
                break
        self.assertLess(marble.vx, 0.0, 'it never met the wall')
        # The spin carried through — the patch is sliding hard, where
        # a spin slaved to the velocity would read nearly none. The
        # engine's stiff-but-finite contact spends some of the spin an
        # instantaneous impact would keep, so the bound is a floor and
        # not the impulsive figure; the test that the surviving spin
        # then *does* something is the wall-hug test next door.
        self.assertGreater(marble.slipping, 0.20,
                           'the spin did not carry through the bounce')

    def test_a_square_hit_leaves_it_hugging_the_wall(self):
        """And not crossing the corridor, which is what a real one does.

        The rebound is real — about a quarter of the approach — but the
        marble is spinning the wrong way for it, and the tray drags it
        straight back. A model that slaves spin to velocity keeps the
        whole quarter and sends the marble back across the corridor,
        which is the single most obviously wrong thing a labyrinth can
        do.
        """
        sim, marble, tray = self._flat(
            walls=(M.Wall(0.30, 0.02, 0.31, 0.40),))
        marble.x, marble.y = 0.20, tray.depth / 2.0
        marble.vx = 0.5
        marble.roll_with_travel()
        deepest = 0.0
        for _ in range(60 * 5):
            sim.step(1 / 60.0)
            deepest = min(deepest, marble.vx)
        face = 0.30 - M.MARBLE_RADIUS
        # The rebound is real but small — the noslip contact spends
        # more of the blow in the impact itself than the regularised
        # one did, and the marble arrives slower on a slick board.
        self.assertLess(deepest, -0.02, 'no rebound at all')
        self.assertLess(face - marble.x, M.MARBLE_RADIUS,
                        'it crossed the corridor instead of settling')
        self.assertAlmostEqual(marble.speed, 0.0, places=9)

    def test_a_skid_comes_back_to_a_roll(self):
        """Kinetic friction, and it converges rather than ringing.

        A ball dropped travelling but not turning ends up rolling at
        five sevenths of what it started with, and that number comes
        from angular momentum about the contact line rather than from
        anywhere in the code: the skid is friction acting *at* that
        line, so it has no moment about it. Same two sevenths as ever,
        arrived at from the other direction.
        """
        sim, marble, _tray = self._flat()
        marble.vx = 0.6           # travelling, and not turning at all
        self.assertAlmostEqual(marble.slipping, 0.6, places=9)
        for tick in range(60):
            sim.step(1 / 60.0)
            if marble.slipping < 0.005:
                break
        self.assertLess(marble.slipping, 0.005)
        self.assertLess(tick, 10, 'the skid took longer than it should')
        # Five sevenths of what it had, less what the tray took off
        # both of them while it was skidding.
        self.assertLess(marble.vx, 0.6 * M.ROLL_FACTOR)
        self.assertGreater(marble.vx, 0.6 * M.ROLL_FACTOR - 0.03)

    def test_a_skid_never_overshoots_into_a_skid_the_other_way(self):
        """The slip decays and keeps decaying; it never rings.

        With the hand-rolled solver this was an inequality between two
        constants. With an engine it is a property to *measure*: from
        the hardest skid the tray can be asked for — a marble at the
        speed cap, not turning at all — the slip must fall every tick
        until it is gone, because a solver that overshoots sets the
        marble ringing between two skids instead of settling into a
        roll, and that reads as a buzz.
        """
        sim, marble, _tray = self._flat()
        marble.vx = M.SPEED_CAP
        was = marble.slipping
        for _ in range(60):
            sim.step(1 / 60.0)
            now = marble.slipping
            # Monotone down to the solver's noise floor; below two
            # centimetres a second the residual wobbles in a band a
            # tenth of that, which is no skid at all.
            self.assertLessEqual(now, max(was, 0.02) + 1e-9,
                                 'the skid grew')
            was = now
        self.assertLess(marble.slipping, 0.02)

    def test_a_scuff_spins_it_about_the_trays_normal(self):
        """A graze puts a marble into a turn a roll cannot account for."""
        sim, marble, tray = self._flat(
            walls=(M.Wall(0.30, 0.02, 0.31, 0.40),))
        marble.x, marble.y = 0.20, tray.depth / 2.0
        marble.vx, marble.vy = 0.25, 0.43
        marble.roll_with_travel()
        self.assertEqual(marble.wz, 0.0)
        peak = 0.0
        for _ in range(40):
            sim.step(1 / 60.0)
            peak = max(peak, abs(marble.wz))
        # The peak of the turn, because the same contact that starts
        # the spin begins winding it down again the moment the graze
        # ends — the floor's torsional grip is what tops do die of.
        self.assertGreater(peak, 1.0)
        # And it runs on down the corridor rather than stopping in it.
        self.assertGreater(marble.vy, 0.1)

    def test_the_orientation_stays_a_rotation(self):
        """A quaternion that drifts off unit length is a shear, on screen.

        Thirty seconds of the top rung, which is walls, pits, three
        marbles and everything the solve can do to a spin.
        """
        sim = M.Simulation(M.deal(len(M.GRADES), seed=5))
        rng = random.Random(11)
        for _ in range(60 * 30):
            sim.tilt(rng.choice((M.TILT_NORTH, M.TILT_SOUTH,
                                 M.TILT_WEST, M.TILT_EAST)))
            sim.step(1 / 60.0)
            for marble in sim.marbles:
                length = math.sqrt(marble.qw ** 2 + marble.qx ** 2
                                   + marble.qy ** 2 + marble.qz ** 2)
                self.assertAlmostEqual(length, 1.0, places=9)

    def test_the_orientation_turns_the_way_the_marble_rolls(self):
        """One radian of roll for every radius travelled, and about the
        axis across the travel. Get the axis wrong and the marble rolls
        sideways down the tray, which is not subtle."""
        sim, marble, _tray = self._flat()
        marble.vx = 0.30
        marble.roll_with_travel()
        for _ in range(6):
            sim.step(1 / 60.0)
        # Travelling along +x rolls about +y, so the quaternion's y is
        # the only part of the vector that should have grown.
        self.assertGreater(marble.qy, 0.05)
        self.assertAlmostEqual(marble.qx, 0.0, places=9)
        self.assertAlmostEqual(marble.qz, 0.0, places=9)


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

    def test_a_fall_always_ends(self):
        """There is no speed at which a marble is left mid-drop forever.

        This is a regression with a body count. The capture used to be
        decided on height first and position second, which left a
        crossing that ran out of height in the same substep it ran out
        of hole in neither state: not swallowed, not back on the tray,
        and *still falling* — sliding about at nought height under the
        whole of gravity with no friction on it for the rest of the
        trial. The trial could then only end on the clock, and
        :meth:`Simulation.potential` answers ``None`` for a falling
        marble, so the coach went blind at the same moment.

        The band it lived in is narrow and speed-dependent, which is
        why this sweeps rather than samples: two hundred crossings
        across every hole size on the ladder.
        """
        for scale in (1.3, 1.6, 2.0, 2.6):
            for step in range(50):
                speed = 0.20 + step * 0.014        # 0.20 .. 0.89 m/s
                tray = self._one_hole(scale)
                sim = M.Simulation(tray)
                sim.marbles = [M.Marble(tray.width / 2.0 - 0.05,
                                        tray.depth / 2.0)]
                sim.marbles[0].vx = speed
                sim.marbles[0].roll_with_travel()
                for _ in range(60 * 6):
                    sim.step(1 / 60.0)
                    if sim.marbles[0].state != 'falling':
                        break
                self.assertNotEqual(
                    sim.marbles[0].state, 'falling',
                    'a marble crossing a %.1f-radius hole at %.3f m/s was '
                    'left mid-drop' % (scale, speed))

    def test_the_far_lip_charges_for_the_climb(self):
        """And charges by the drop, rather than a flat percentage.

        A marble that barely dipped keeps nearly all of its speed; one
        that nearly went in comes over the lip with hardly any. That
        gradient is the whole of the skill in going fast past a hole —
        a flat toll makes every near miss cost the same, so there is
        nothing to aim at.
        """
        kept = {}
        for speed in (0.70, 0.82, 0.95):
            tray = self._one_hole(1.6)
            sim = M.Simulation(tray)
            sim.marbles = [M.Marble(tray.width / 2.0 - 0.05,
                                    tray.depth / 2.0)]
            marble = sim.marbles[0]
            marble.vx = speed
            marble.roll_with_travel()
            entered = None
            for _ in range(240):
                was = marble.state
                sim.step(1 / 60.0)
                if was == 'rolling' and marble.state == 'falling':
                    entered = marble.speed
                elif was == 'falling' and marble.state != 'falling':
                    break
            self.assertEqual(marble.state, 'rolling',
                             'it went in at %.2f m/s' % speed)
            # Measured across the hole alone, so what the tray took on
            # the way in does not muddle the toll the lip charged.
            kept[speed] = marble.speed / entered
        self.assertLess(kept[0.70], kept[0.82])
        self.assertLess(kept[0.82], kept[0.95])
        self.assertLess(kept[0.70], 0.92, 'a slow crossing paid nothing')
        self.assertGreater(kept[0.95], 0.94, 'a fast crossing paid too much')

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
            # Half a millimetre of squeeze, because the engine's
            # contact is soft during the impact itself — that give is
            # where the restitution comes from. What must never
            # happen is passing through, and that is metres away from
            # this bound.
            self.assertGreater(gap, 2.0 * M.MARBLE_RADIUS - 5e-4)
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
        """Every number a marble carries, not just the ones on the floor.

        The spin and the orientation are read by the renderer rather
        than by the verdict, so a drift in them would not change who
        wins — it would show up as a marble that turns differently on
        a replay, which is the kind of thing nothing else here would
        catch.
        """
        def play():
            sim = M.Simulation(M.deal(6, seed=99))
            rng = random.Random(5)
            for _ in range(600):
                sim.tilt(rng.choice((M.TILT_NORTH, M.TILT_SOUTH,
                                     M.TILT_WEST, M.TILT_EAST)))
                sim.step(1 / 60.0)
            return [(m.x, m.y, m.z, m.vx, m.vy, m.vz, m.wx, m.wy, m.wz,
                     m.qw, m.qx, m.qy, m.qz, m.state) for m in sim.marbles]
        self.assertEqual(play(), play())

    def test_nothing_in_the_model_reads_the_wall_clock(self):
        """The driver owns the clock, so this module may not have one."""
        import inspect
        source = inspect.getsource(M)
        self.assertNotIn('time.time', source)
        self.assertNotIn('import time', source)


class TheKnobsHaveStops(unittest.TestCase):

    def test_tilt_never_passes_the_limit(self):
        """Both stops on both axes, driven from the knobs.

        The pitch stops read the way they do because the knobs are
        named for the marble: north is towards larger y, gravity in
        the tray's frame carries a minus on that axis, so the knob
        called north walks pitch down to its *negative* stop.
        """
        sim = M.Simulation(M.deal(1, seed=8))
        for _ in range(500):
            sim.tilt(M.TILT_NORTH)
            sim.tilt(M.TILT_EAST)
        self.assertAlmostEqual(sim.pitch, -M.MAX_TILT, places=9)
        self.assertAlmostEqual(sim.roll, M.MAX_TILT, places=9)
        for _ in range(500):
            sim.tilt(M.TILT_SOUTH)
            sim.tilt(M.TILT_WEST)
        self.assertAlmostEqual(sim.pitch, M.MAX_TILT, places=9)
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
