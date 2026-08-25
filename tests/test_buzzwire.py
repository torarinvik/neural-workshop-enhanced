#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Buzz Wire: the contact geometry, the ladder, and the coach's promise.

Four things are worth holding hard here and the rest follows from them.

The **contact test** is the task. It is an exact statement about a
circle and a tube in three dimensions, and the one consequence that
makes the top of the ladder what it is — that a wire crossing the loop
at an angle needs a hole wider than its own thickness by one over the
cosine of that angle — is checked against the closed form rather than
against a screenshot. Everything a player experiences as "you have to
turn the loop into a bend" is that one line of arithmetic.

The **ladder** makes three quantitative promises, and each is the sort
that fails silently. Every rung must be flyable in principle: one tick
of thrust has to be worth less than the clearance, or no controller at
any speed could hold the wire. Every wire must be threadable: no bend
may be tighter than the loop that has to go round it. And the hand's
tremor has to stay inside what the arm can answer. All three were got
wrong in the first version of the table, all three were invisible until
something was measured, and so all three are arithmetic here rather
than a sweep — a sweep would only ever fail to find the case that
breaks them.

The **coach's promise** is that one action changes the count of beads
still ahead by one at most. Under that, and under the potential
reading only what is drawn, the sign of the change is exactly the
potential-based shaping term of Ng et al. and the best policy is
unchanged. It is guaranteed by geometry — the beads are spaced against
the furthest a tick could ever carry the loop — so it is checked
against the geometry *and* driven, because a promise this load-bearing
is worth two arguments.

And the **screen** is held to the workshop's one rule about the band,
and to the thing that makes this task drawable at all: that the wire's
mesh is built once a level and the loop's is not.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from uisupport import (TASKS, BuzzWire, close_overlays, key, needs_ui,
                       reset_window, taskoptions)

from neural_workshop import buzzwire as B

def straight_wire(length=20.0, radius=B.WIRE_RADIUS, along=(1.0, 0.0, 0.0)):
    """A wire with no bends at all, for arithmetic that can be done by hand."""
    steps = 200
    along = B.unit(along)
    points = tuple(B.scale(along, -length / 2.0 + length * i / steps)
                   for i in range(steps + 1))
    return B.Wire(points=points, tangents=tuple([along] * (steps + 1)),
                  arcs=tuple(length * i / steps for i in range(steps + 1)),
                  span=length, length=length, radius=radius, beads=20)


def touching(wire, centre, axis, hole):
    """The worst contact between *wire* and a loop there, or None."""
    worst = None
    for crossing in B.crossings(wire, centre, axis, wire.length / 2.0,
                                hole + B.RIM):
        hit = B.crossing_contact(crossing, centre, axis, hole, wire.radius)
        if hit is not None and (worst is None or hit.depth > worst.depth):
            worst = hit
    return worst


class TheContactTestIsExact(unittest.TestCase):
    """A circle and a tube, and nothing rounded off between them."""

    def test_a_wire_down_the_middle_is_not_touching(self):
        wire = straight_wire()
        self.assertIsNone(touching(wire, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                                   1.0))

    def test_the_gap_is_the_hole_less_the_wire(self):
        """Square on, a loop may be off centre by exactly the clearance."""
        wire = straight_wire()
        hole = 1.0
        room = hole - B.WIRE_RADIUS
        inside = touching(wire, (0.0, room * 0.98, 0.0), (1.0, 0.0, 0.0), hole)
        outside = touching(wire, (0.0, room * 1.02, 0.0), (1.0, 0.0, 0.0),
                           hole)
        self.assertIsNone(inside)
        self.assertIsNotNone(outside)
        self.assertFalse(outside.outside)
        self.assertAlmostEqual(outside.depth, room * 0.02, places=3)

    def test_a_tilted_wire_needs_a_wider_hole(self):
        """The one over cosine law, against the closed form.

        This is the whole reason the loop has to be turned, so it is
        checked as arithmetic rather than as behaviour. A tube of radius
        *r* crossing a plane at *theta* to its normal cuts an ellipse
        with semi-axes *r* and *r/cos(theta)*, so a centred loop is
        clear exactly while ``hole > r / cos(theta)``.
        """
        for degrees in (0, 15, 30, 45, 55, 60):
            angle = math.radians(degrees)
            along = (math.cos(angle), math.sin(angle), 0.0)
            wire = straight_wire(along=along)
            needs = B.WIRE_RADIUS / math.cos(angle)
            # The loop still faces down the x axis; the wire leans away.
            axis = (1.0, 0.0, 0.0)
            self.assertIsNone(
                touching(wire, (0.0, 0.0, 0.0), axis, needs * 1.04),
                'a hole 4%% over the ellipse should pass at %d deg'
                % degrees)
            self.assertIsNotNone(
                touching(wire, (0.0, 0.0, 0.0), axis, needs * 0.96),
                'a hole 4%% under the ellipse must not, at %d deg' % degrees)

    def test_a_hole_too_small_for_the_tilt_is_a_jam(self):
        """No move of the loop can clear it, and the contact says so."""
        angle = math.radians(70.0)
        wire = straight_wire(along=(math.cos(angle), math.sin(angle), 0.0))
        hit = touching(wire, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                       B.WIRE_RADIUS / math.cos(angle) * 0.8)
        self.assertIsNotNone(hit)
        self.assertTrue(hit.jammed)

    def test_a_wire_that_misses_the_loop_entirely_is_not_touching(self):
        wire = straight_wire()
        self.assertIsNone(touching(wire, (0.0, 4.0, 0.0), (1.0, 0.0, 0.0),
                                   1.0))

    def test_a_wire_against_the_outside_of_the_loop_is_touching(self):
        """The loop is metal, not a hole in the air, and can be hit."""
        wire = straight_wire()
        hole = 1.0
        just_outside = hole + B.RIM - B.WIRE_RADIUS * 0.5
        hit = touching(wire, (0.0, just_outside, 0.0), (1.0, 0.0, 0.0), hole)
        self.assertIsNotNone(hit)
        self.assertTrue(hit.outside)

    def test_the_escape_points_out_of_the_contact(self):
        """Moving the loop by the depth along the escape ends the touch."""
        wire = straight_wire()
        hole = 1.0
        centre = (0.0, (hole - B.WIRE_RADIUS) * 1.30, 0.0)
        hit = touching(wire, centre, (1.0, 0.0, 0.0), hole)
        self.assertIsNotNone(hit)
        moved = B.add(centre, B.scale(hit.escape, hit.depth * 1.02))
        self.assertIsNone(touching(wire, moved, (1.0, 0.0, 0.0), hole))


class TheWireIsShapedTheWayItSaysItIs(unittest.TestCase):
    """What the generator promises about every wire it deals."""

    #: Wires per rung for the geometry sweeps. Every one of these
    #: properties has to hold for *every* wire the ladder will ever
    #: deal, and a single seed would only ever fail to find the one
    #: that breaks it.
    SEEDS = 8

    def wires(self):
        for rung in range(1, len(B.GRADES) + 1):
            for seed in range(self.SEEDS):
                yield rung, seed, B.deal(rung, seed=seed)

    def test_dealing_is_deterministic(self):
        self.assertEqual(B.deal(6, seed=11).points,
                         B.deal(6, seed=11).points)
        self.assertNotEqual(B.deal(6, seed=11).points,
                            B.deal(6, seed=12).points)

    def test_it_never_doubles_back_along_its_own_run(self):
        """Which is what makes "how far along" a number, not an argument."""
        for rung, seed, wire in self.wires():
            for before, after in zip(wire.points, wire.points[1:]):
                self.assertGreater(after[0], before[0] - 1e-9,
                                   'rung %d seed %d' % (rung, seed))

    def test_both_ends_run_straight(self):
        """The lead-in a loop is threaded onto, and the lead-out.

        Grown as straight segments tangent to the curve rather than
        windowed down to nothing, and the difference is the whole point:
        a window forces the entire swing to happen inside a tenth of the
        span, so the piece meant to be gentle comes out as the steepest
        part of the wire.
        """
        for rung, seed, wire in self.wires():
            for tangent in list(wire.tangents[:3]) + list(wire.tangents[-3:]):
                self.assertGreater(
                    abs(tangent[0]), 0.999,
                    'rung %d seed %d ends at %s, not along its axis'
                    % (rung, seed, tangent))

    def test_the_samples_are_evenly_spaced_along_it(self):
        for rung, seed, wire in self.wires():
            gaps = [B.length(B.sub(after, before))
                    for before, after in zip(wire.points, wire.points[1:])]
            self.assertLess(max(gaps) - min(gaps), 0.02 * wire.spacing() + 1e-3,
                            'rung %d seed %d' % (rung, seed))

    def test_every_bend_is_wider_than_the_loop_going_round_it(self):
        """Or the wire is impossible rather than hard.

        A loop cannot be threaded round a bend tighter than itself, and
        the failure would look exactly like a very difficult rung. So
        the margin is arithmetic: the tightest radius of curvature on
        any wire the ladder deals stays clear of the loop's own outside
        by a factor of two.
        """
        for rung, seed, wire in self.wires():
            grade = B.grade_of(rung)
            outer = grade.hole + B.RIM
            worst = float('inf')
            for one, two in zip(wire.tangents, wire.tangents[2:]):
                turn = math.acos(max(-1.0, min(1.0, B.dot(one, two))))
                if turn > 1e-9:
                    worst = min(worst, 2.0 * wire.spacing() / turn)
            self.assertGreater(
                worst, 2.0 * outer,
                'rung %d seed %d bends to %.2f cm against a loop %.2f across'
                % (rung, seed, worst, outer))


class TheLadderIsFlyableAllTheWayUp(unittest.TestCase):
    """Three promises that fail silently, so all three are arithmetic."""

    def test_one_tick_of_thrust_is_worth_less_than_the_gap(self):
        """Under one it is not a hard rung, it is an impossible one.

        The quantity is ``thrust / drag / hz`` — how far one frame's
        press eventually carries the loop — against the clearance. The
        first version of this table had it at seven *times* the
        clearance on the top rungs, so nothing could have held those
        wires, and the ladder had no upper half at all.
        """
        for rung, grade in enumerate(B.GRADES, start=1):
            ticks = B.ticks_per_clearance(grade)
            self.assertGreater(ticks, 3.5,
                               'rung %d gives %.1f ticks of grace'
                               % (rung, ticks))

    def grip(self, grade):
        """The arm's authority against the tremor, over the tremor's own
        correlation time.

        The right comparison, and not the obvious one. Comparing the
        tremor to what a *single* tick of thrust can take back says the
        top four rungs are impossible, and they are not: the tremor
        turns over in about a tenth of a second and the arm gets six
        ticks inside that. So the quantity is ``thrust x tau`` against
        the speed the tremor holds, and it is the number that says how
        much of the arm the shaking is eating.
        """
        wander = B.tremor_wander(grade)
        if wander <= 0.0:
            return float('inf')
        return grade.thrust * grade.tremor_tau / wander

    def test_the_grip_only_gets_harder(self):
        shaking = [self.grip(grade) for grade in B.GRADES
                   if grade.tremor]
        self.assertEqual(shaking, sorted(shaking, reverse=True))

    def test_the_tremor_never_beats_the_arm_outright(self):
        """It may beat a person's reaction. It may not beat the arm.

        Under about two the loop is being carried faster than the whole
        stroke could bring it back, and the rung stops being hard and
        becomes a coin. Above it the rung is merely past what anybody
        could hold, which is the thing this ladder is for.
        """
        for rung, grade in enumerate(B.GRADES, start=1):
            if not grade.tremor:
                continue
            self.assertGreater(self.grip(grade), 2.0,
                               'rung %d shakes harder than the arm can '
                               'answer' % rung)

    def test_the_gap_and_the_clock_only_get_harder(self):
        holes = [grade.hole for grade in B.GRADES]
        self.assertEqual(holes, sorted(holes, reverse=True))
        ticks = [B.ticks_per_clearance(grade) for grade in B.GRADES]
        self.assertEqual(ticks, sorted(ticks, reverse=True))

    def test_the_clock_allows_the_wire_to_be_flown(self):
        """Twice over, at the pace the hand can actually manage."""
        for rung, grade in enumerate(B.GRADES, start=1):
            wire = B.deal(rung, seed=0)
            flat_out = wire.length / B.hand_speed(grade)
            self.assertGreater(grade.seconds, flat_out * 2.0,
                               'rung %d allows %ds for %.0fs of wire'
                               % (rung, grade.seconds, flat_out))

    def worst_turn(self, rung, grade, seeds=6):
        """Fastest the tangent swings on this rung, at a cruising pace."""
        pace = B.hand_speed(grade) * 0.72
        worst = 0.0
        for seed in range(seeds):
            wire = B.deal(rung, seed=seed)
            for one, two in zip(wire.tangents, wire.tangents[4:]):
                turn = math.acos(max(-1.0, min(1.0, B.dot(one, two))))
                worst = max(worst, turn / (4.0 * wire.spacing()) * pace)
        return worst

    def test_a_bend_the_wrist_cannot_follow_can_still_be_crawled(self):
        """The top rungs turn faster than the wrist, and that is allowed.

        What is not allowed is for that to make the wire impossible. The
        tangent's turn rate is proportional to how fast the loop is
        travelling, so a bend the wrist cannot follow at a cruise can
        always be followed by *slowing down* — and the price of slowing
        down is the clock. So the promise is not "the wrist keeps up"
        but the one that matters: crawl the whole wire at the pace the
        sharpest bend on it dictates, and the clock still allows it.
        """
        for rung, grade in enumerate(B.GRADES, start=1):
            if grade.twist <= 0.0:
                continue
            worst = self.worst_turn(rung, grade)
            pace = B.hand_speed(grade) * 0.72
            crawl = pace * min(1.0, grade.top_twist / worst)
            wire = B.deal(rung, seed=0)
            self.assertGreater(
                grade.seconds, wire.length / crawl,
                'rung %d needs %.0fs at the pace its wrist allows and is '
                'given %ds' % (rung, wire.length / crawl, grade.seconds))

    def test_the_wrist_is_not_furniture_at_the_top(self):
        """From the ninth rung it has to be a real constraint."""
        for rung, grade in enumerate(B.GRADES, start=1):
            if rung < 9 or grade.twist <= 0.0:
                continue
            self.assertLess(grade.top_twist,
                            self.worst_turn(rung, grade) * 2.0,
                            'rung %d gives the wrist nothing to do' % rung)

    def test_the_lower_rungs_aim_the_loop_for_you(self):
        """And say so by offering no twist at all, rather than a slow one."""
        for rung, grade in enumerate(B.GRADES, start=1):
            self.assertEqual(grade.twist > 0.0, rung >= 7, 'rung %d' % rung)


class TheCoachCannotPayTwiceForOneTick(unittest.TestCase):
    """The potential moves by one at most, and that is geometry."""

    def test_the_beads_are_spaced_against_the_furthest_a_tick_goes(self):
        for rung, grade in enumerate(B.GRADES, start=1):
            wire = B.deal(rung, seed=0)
            furthest = 2.0 * grade.top_speed / B.SLOWEST_HZ
            spacing = wire.length / wire.beads
            self.assertGreater(
                spacing, 2.0 * furthest,
                'rung %d: beads %.2f cm apart, a tick worth %.2f cm'
                % (rung, spacing, furthest))

    def test_driven_hard_it_still_never_moves_two(self):
        """The argument is geometric; this is the second opinion."""
        rng = random.Random(4)
        for rung in (1, 6, 12):
            grade = B.grade_of(rung)
            wire = B.deal(rung, seed=rung)
            hand = B.Hand(wire, grade, rng=random.Random(rung))
            before = hand.beads_left()
            for tick in range(1200):
                name = B.PORTS[rng.randrange(len(B.PORTS))
                               if tick % 3 else B.PORTS.index('right')]
                push = (B.push_vector(grade, name) if name in B.PUSHES
                        else None)
                twist = {'tilt up': (1.0, 0.0), 'tilt down': (-1.0, 0.0),
                         'tilt left': (0.0, 1.0), 'tilt right': (0.0, -1.0)
                         }.get(name, (0.0, 0.0))
                step = hand.advance(1.0 / B.SLOWEST_HZ, push=push,
                                    twist=twist, grip=(name == B.GRIP))
                now = hand.beads_left()
                self.assertLessEqual(abs(now - before), 1,
                                     'rung %d tick %d moved %d beads'
                                     % (rung, tick, abs(now - before)))
                before = now
                if step.home:
                    break

    def test_the_potential_is_nought_at_the_far_post(self):
        wire = B.deal(1, seed=0)
        self.assertEqual(wire.bead_at(wire.length), wire.beads)
        self.assertEqual(wire.bead_at(0.0), 0)


class TheLoopCannotPassThroughTheWire(unittest.TestCase):
    """A hard constraint, held under the worst thing a player can do."""

    def flown(self, rung, port, ticks=900, seed=0):
        grade = B.grade_of(rung)
        wire = B.deal(rung, seed=seed)
        hand = B.Hand(wire, grade, rng=random.Random(seed))
        name = B.PORTS[port]
        push = B.push_vector(grade, name) if name in B.PUSHES else None
        deepest = 0.0
        for _tick in range(ticks):
            hand.advance(1.0 / 60.0, push=push)
            worst = hand._deepest()
            if worst is not None:
                deepest = max(deepest, worst.depth)
        return hand, deepest

    def test_shoved_flat_at_the_wire_it_stays_threaded(self):
        """Held against the wire for fifteen seconds, it never gets out.

        The interesting failure is not the loop going *through* the wire
        but the wire slipping out of the hole, which would end the run
        as a win. So what is asserted is that the wire is still crossing
        the loop's plane inside the metal at the end of it.
        """
        for rung in (1, 5, 9, 12):
            for port, name in enumerate(B.PORTS):
                if name not in ('up', 'down', 'in', 'out'):
                    continue
                hand, deepest = self.flown(rung, port)
                self.assertFalse(hand.home,
                                 'rung %d: shoving %s took the loop home'
                                 % (rung, name))
                self.assertLess(deepest, 0.02,
                                'rung %d: shoving %s buried the wire %.3f cm '
                                'into the loop' % (rung, name, deepest))

    def test_a_tick_cannot_carry_the_loop_through_its_own_rim(self):
        """Which is what makes a false win impossible rather than rare.

        The contact test is evaluated once a tick, so a loop moving far
        enough in one tick could pass clean through the wire between two
        evaluations — and a loop on the wrong side of the wire has no
        crossing, which :meth:`Hand._locate` would have to interpret.
        It cannot happen, and the reason is arithmetic rather than luck:
        the furthest a tick can carry the loop, at the slowest rate the
        physics allows, is less than the thickness of the metal it would
        have to pass through.
        """
        for rung, grade in enumerate(B.GRADES, start=1):
            step = grade.top_speed / B.SLOWEST_HZ
            self.assertLess(step, B.RIM,
                            'rung %d moves %.3f cm a tick through %.3f cm '
                            'of rim' % (rung, step, B.RIM))

    def test_a_long_scrape_is_one_buzz_and_not_sixty(self):
        """What the real buzzer does, and what stops a graze reading as
        a run's worth of faults."""
        grade = B.grade_of(1)
        wire = B.deal(1, seed=0)
        hand = B.Hand(wire, grade, rng=random.Random(0))
        up = B.push_vector(grade, 'up')
        fresh = 0
        for _tick in range(600):
            step = hand.advance(1.0 / 60.0, push=up)
            fresh += int(step.buzzed)
        self.assertTrue(hand.scraping)
        self.assertEqual(hand.touches, fresh)
        self.assertLessEqual(hand.touches, 3)
        self.assertGreaterEqual(hand.touches, 1)


class TheHandIsTheSameHandAtAnyFrameRate(unittest.TestCase):
    """A run driven faster is not a run with a different disturbance."""

    def wander(self, hz, ticks):
        """Standard deviation of the loop's speed under tremor alone."""
        grade = B.grade_of(12)
        wire = B.deal(12, seed=0)
        hand = B.Hand(wire, grade, rng=random.Random(99))
        seen = []
        for _tick in range(ticks):
            hand.advance(1.0 / hz)
            seen.append(B.length(hand.velocity))
        half = len(seen) // 2
        return sum(seen[half:]) / float(len(seen) - half)

    def test_the_tremor_does_not_depend_on_the_tick(self):
        slow = self.wander(30.0, 900)
        fast = self.wander(240.0, 7200)
        self.assertLess(abs(slow - fast) / max(slow, fast, 1e-9), 0.35,
                        'tremor moves the loop at %.3f cm/s at 30 Hz and '
                        '%.3f at 240' % (slow, fast))

    def test_a_frame_longer_than_the_physics_allows_is_slowed_not_skipped(self):
        """A stuttering machine gets slow motion, not a loop through a wire."""
        grade = B.grade_of(1)
        wire = B.deal(1, seed=0)
        one = B.Hand(wire, grade, rng=random.Random(1))
        two = B.Hand(wire, grade, rng=random.Random(1))
        push = B.push_vector(grade, 'right')
        one.advance(1.0 / B.SLOWEST_HZ, push=push)
        two.advance(5.0, push=push)
        self.assertAlmostEqual(one.arc, two.arc, places=6)

    def test_the_same_seed_flies_the_same_wire(self):
        def run(seed):
            grade = B.grade_of(9)
            wire = B.deal(9, seed=seed)
            hand = B.Hand(wire, grade, rng=random.Random(seed))
            for _tick in range(400):
                hand.advance(1.0 / 60.0,
                             push=B.push_vector(grade,
                                                B.PORTS[B.pilot_port(hand)])
                             if B.PORTS[B.pilot_port(hand)] in B.PUSHES
                             else None)
            return hand.centre, hand.arc, hand.touches
        self.assertEqual(run(3), run(3))


class ThePilotIsAYardstickAndItWorks(unittest.TestCase):
    """The reference controller, which the ladder was measured with."""

    def fly(self, rung, seed):
        grade = B.grade_of(rung)
        wire = B.deal(rung, seed=seed)
        hand = B.Hand(wire, grade, rng=random.Random(seed ^ 0x5eed))
        for _tick in range(int(grade.seconds * 60)):
            name = B.PORTS[B.pilot_port(hand)]
            push = B.push_vector(grade, name) if name in B.PUSHES else None
            twist = {'tilt up': (1.0, 0.0), 'tilt down': (-1.0, 0.0),
                     'tilt left': (0.0, 1.0), 'tilt right': (0.0, -1.0)
                     }.get(name, (0.0, 0.0))
            step = hand.advance(1.0 / 60.0, push=push, twist=twist,
                                grip=(name == B.GRIP))
            if hand.touches > grade.touches or step.home:
                break
        return hand

    def test_it_flies_the_bottom_of_the_ladder_clean(self):
        for rung in (1, 3, 5):
            hand = self.fly(rung, seed=rung)
            self.assertTrue(hand.home, 'the pilot did not finish rung %d'
                                       % rung)
            self.assertEqual(hand.touches, 0, 'rung %d' % rung)

    def test_the_top_of_the_ladder_beats_it(self):
        """Which is what the word "superhuman" is doing up there.

        The pilot is a fixed-gain controller reading the true state at
        sixty ticks a second, and a person is neither of those things.
        A rung it cannot hold is a long way past one anybody could.
        """
        home = sum(int(self.fly(12, seed=seed).home) for seed in range(4))
        self.assertLessEqual(home, 1)

    def test_it_reads_no_more_than_a_learner_could(self):
        """It must not consult the tremor, which nothing on screen carries.

        Not a style point: subtracting ``hand.drift`` cancels the
        disturbance exactly, and with it the whole top of the ladder
        came out flyable — a measurement of the cheat rather than of the
        wire.
        """
        import inspect
        source = inspect.getsource(B.pilot_port)
        self.assertNotIn('hand.drift', source.split('# ')[0])


@needs_ui
class NothingIsPaintedInTheBandOnAnyPhase(unittest.TestCase):
    """The band, swept through every phase this task actually has.

    ``tests/check_band.py`` sweeps the catalogue and reports this task
    clean, and on this one task that is worth less than it sounds: the
    sweep plays seven hundred steps of a task whose own clock runs to
    twelve hundred, so it never sees a wire settle and never sees a
    verdict, and the phases it does not reach are the ones with a label
    up. So the sweep is asked the same question here with a clock short
    enough to answer it, in a build that turns the per-tick coach on,
    and at three window shapes — the stage is laid out from the window
    and a violation that only appears on a wide one is exactly the kind
    that survives a single sweep.
    """

    def setUp(self):
        close_overlays()
        reset_window()

    def tearDown(self):
        close_overlays()
        reset_window()

    def band(self, obs):
        import bwaccel
        return bwaccel.count_feedback_label_runs(obs['rgba'], obs['width'],
                                                obs['height'])

    def sweep(self, rung, coach, size, steps=260):
        from nwenv import catalog
        from neural_workshop.geometry import set_window_size
        set_window_size(*size)
        env = catalog.env_class('buzz_wire')(
            seed=rung, rung=rung, trials=3, seconds=1.2,
            neutral_outcomes=coach, coach=coach)
        rng = random.Random(rung)
        seen = set()
        try:
            for step in range(steps):
                obs, _events, done = env.step(rng.randrange(env.n_actions))
                seen.add(env.task.phase)
                if step % 5:
                    continue
                runs = self.band(obs)
                # A verdict standing is the one run the reader is meant
                # to find. Any second run, anywhere, is the task's own
                # art being read as a score.
                self.assertLessEqual(
                    sum(runs), 1,
                    'rung %d, coach %s, %dx%d, phase %s: %s'
                    % (rung, coach, size[0], size[1], env.task.phase, runs))
                if done:
                    break
        finally:
            env.close()
        return seen

    #: Four sweeps rather than the cross product of every rung, hand
    #: and window: what is being covered is the *phases* and the shapes
    #: the layout can take, and a wire is a wire. Kept small enough to
    #: run on every pass of the suite, which is the only kind of guard
    #: that goes on being run.
    SWEEPS = ((1, False, (640, 480)), (7, True, (912, 684)),
              (12, True, (1400, 700)), (12, False, (800, 900)))

    def test_every_phase_is_visited_and_none_of_them_paints(self):
        seen = set()
        for rung, coach, size in self.SWEEPS:
            seen |= self.sweep(rung, coach, size)
        # The point of the class: the phases the catalogue sweep never
        # reaches are reached here.
        self.assertTrue({'flying', 'lost'} <= seen, sorted(seen))


@needs_ui
class TheScreenKeepsTheWorkshopsRules(unittest.TestCase):
    """The band, the verdict, and the one thing a relayout must not lose."""

    def setUp(self):
        close_overlays()
        reset_window()
        self.task = BuzzWire()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_the_stage_stops_above_the_band(self):
        """Both panels, at several window shapes.

        Written against the geometry rather than left to the sweep,
        because everything drawn here is lit metal against a dark sky
        and a lit metal surface passes through every colour on its way
        to the background -- so which of its blends land on the outcome
        reader's pattern is not a thing a palette can be chosen to
        avoid, and one clean sweep would prove nothing.
        """
        from neural_workshop.ui.verdict import band_rows
        from neural_workshop.geometry import pixel_size, set_window_size
        for width, height in ((640, 480), (912, 684), (1400, 700)):
            set_window_size(width, height)
            self.task.relayout()
            ceiling = pixel_size()[1] - band_rows()[0]
            for rect in (self.task._view_rect(), self.task._sight_rect()):
                self.assertGreaterEqual(rect[1], ceiling,
                                        'panel bottom %s at %dx%d'
                                        % (rect[1], width, height))

    def test_the_two_panels_do_not_overlap(self):
        left = self.task._view_rect()
        right = self.task._sight_rect()
        self.assertLessEqual(left[0] + left[2], right[0])

    def test_a_relayout_keeps_the_verdict_and_the_status(self):
        """The frame a wire settles on is exactly when this would drop it."""
        self.task.start_run()
        self.task._lost('a made-up loss')
        said = self.task.status.text
        self.assertTrue(self.task.verdict.label.visible)
        self.task.relayout()
        self.assertTrue(self.task.verdict.label.visible)
        self.assertEqual(self.task.verdict.label.text, 'a made-up loss')
        self.assertEqual(self.task.status.text, said)

    def test_the_wire_is_built_once_a_level_and_the_loop_is_not(self):
        """Which is the whole of why this renderer fits in a frame."""
        self.task.start_run()
        held = list(self.task.solids)
        places = list(self.task.loop.list.position)
        for _tick in range(30):
            self.task.press(B.PORTS.index('right'))
            self.task.update(1.0 / 60.0)
        self.assertEqual([id(solid) for solid in self.task.solids],
                         [id(solid) for solid in held])
        self.assertNotEqual(list(self.task.loop.list.position), places)

    def test_it_is_in_the_hub_and_owns_a_settings_screen(self):
        self.assertIn(('buzz_wire', 'Buzz Wire'), TASKS['attention'])
        self.assertTrue(taskoptions.has_options('buzz_wire'))
        spec = taskoptions.TASK_SPECS['buzz_wire']
        for rung in (1, 7, 12):
            said = spec.note({'BUZZ_LEVEL': rung, 'BUZZ_ADAPTIVE': True})
            self.assertIn('mm', said)

    def test_a_key_held_and_a_port_pressed_buy_the_same_thing(self):
        """Or the person's game and the learner's are different games."""
        self.task.start_run()
        one = self.task
        one.held = {'up'}
        one.update(1.0 / 60.0)
        by_key = one.hand.velocity

        close_overlays()
        two = BuzzWire()
        two.rng = random.Random(0)
        self.task = two
        two.start_run()
        two.press(B.PORTS.index('up'))
        two.update(1.0 / 60.0)
        self.assertAlmostEqual(B.length(B.sub(by_key, two.hand.velocity)),
                               0.0, places=6)

    def test_the_run_ends_on_the_clock(self):
        self.task.start_run()
        self.task.clock = lambda: self.task.deadline + 1.0
        self.task.update(1.0 / 60.0)
        self.assertEqual(self.task.phase, 'lost')
        self.assertTrue(self.task.verdict.label.visible)

    def test_escape_leaves_and_takes_its_handlers_with_it(self):
        self.task.on_key_press(key.ESCAPE, 0)
        self.assertIsNone(BuzzWire.instance)
        from neural_workshop.ui.taskhub import TaskHub
        self.assertIsNotNone(TaskHub.instance)


if __name__ == '__main__':
    unittest.main()
