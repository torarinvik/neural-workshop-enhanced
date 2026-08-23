#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Two Hands: the commitments, the clock, the sky, and what splitting costs.

Four things here are worth testing hard, and the last of them is why
the task exists.

The **road** must have a clean line through it. A road that cannot be
driven scores as a failure the player could not have avoided, and it
looks exactly like a player who was not good enough. Donkey could keep
that true as it laid the road; this one cannot, because the step is the
car's own speed and the verdict has a clock on it, so what survives is
a property of the whole road. So every deal on every rung is solved,
and the ports the solver hands back are driven down the road and
required to come out the far end clean and in time.

The **commitments** are three rules and each gets a test on a road
written out by hand rather than dealt, because a claim about a rule
should not depend on what the dice did. A swerve takes the rung's
ticks, cannot be called off and covers both lanes for all of them. A
jump clears anything flat and only if the car is off the ground for the
*whole* overlap, which is what makes speed buy jump margin. And while
either runs down the wheel is deaf.

The **clock** is what makes the throttle a decision. Without it the
safe policy is to crawl, so the test that matters is that crawling
loses — and loses to the clock rather than to a truck, which is a
different failure and is checked as one.

And the **cost of the second channel** is measured rather than
asserted. The same driver is run three ways: not looking at the sky,
taking it only on the ticks the wheel had no use for, and taking it the
moment anything is up there. The first two clear identically and the
third collapses — *and gets fewer targets while it does it*. That pair
is the finding, and it is kept here where it can go stale rather than
in prose where it cannot.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import (TASKS, Twohands, close_overlays, key, needs_ui,
                       reset_window, state, taskoptions)

from neural_workshop import twohands as H

#: Deals per rung for the sweeps that have to visit every rung. The
#: solver is a dynamic program over some tens of thousands of states,
#: so a deal costs about thirty milliseconds at the top of the ladder
#: and this is what fits in a suite that is run on every change.
DEALS = 16

#: Deals per rung for the measurements. Enough that a 3% and a 70%
#: cannot be confused for one another.
MEASURE = 40

#: The rung the screen tests are pinned at: tall hazards only and a
#: two-tick swerve, so a road can be driven by hand without the test
#: having to plan.
SCREEN_RUNG = 2

#: What one character means in a road written out by hand.
MARKS = {'D': H.DONKEY, 'T': H.TRUCK, 'B': H.BARRIER, 'L': H.LOG,
         'R': H.RUBBLE, 'C': H.CONE, '^': H.RAMP, '>': H.PAD, 'o': H.COIN}


def grade_of(rows, swerve=2, hang=3, top=2, kinds=(H.DONKEY,), slack=2.0):
    return H.Grade('by hand', rows, 0.0, 0.0, swerve, hang, top, slack,
                   kinds, 0.0)


def road_of(rows, start=1, clock=400, **dials):
    """A road written out rather than dealt.

    *rows* is one string a **drawn** row, one character a lane: ``.``
    for clear road and a letter from :data:`MARKS` for something
    standing in it. The body is put on the row it is written on; the
    sub-rows it *blocks* start a car's length earlier, which is where
    the two would first overlap.

    The clock is enormous by default, so a road written to test a rule
    about the wheel is never also a road about running out of time.
    """
    grade = grade_of(len(rows), **dials)
    hazards = [H.Hazard(row * H.SUB - H.CAR + 1, lane, MARKS[mark])
               for row, line in enumerate(rows)
               for lane, mark in enumerate(line) if mark != '.']
    return H.build(grade, hazards, (), start=start, clock=clock)


def run(road, ports):
    """Drive *ports* down *road*, stopping when the road is over."""
    return H.drive(road, ports)


class TheLadder(unittest.TestCase):
    """Ten rungs, and each one adds a single thing."""

    def test_the_first_rungs_are_donkey_in_three_dimensions(self):
        """Nothing flat, nothing that pays, nothing two abreast."""
        for grade in H.GRADES[:2]:
            self.assertEqual(grade.pairs, 0.0)
            for kind in grade.kinds:
                self.assertTrue(H.KINDS[kind].tall, kind)
                self.assertEqual(H.KINDS[kind].toll, 'fatal')

    def test_each_rung_deals_everything_the_one_below_it_did(self):
        for below, above in zip(H.GRADES, H.GRADES[1:]):
            self.assertTrue(set(below.kinds) <= set(above.kinds),
                            (below.name, above.name))

    def test_the_clock_only_ever_tightens(self):
        for below, above in zip(H.GRADES, H.GRADES[1:]):
            self.assertLessEqual(above.slack, below.slack,
                                 (below.name, above.name))

    def test_the_commitments_only_ever_widen(self):
        for below, above in zip(H.GRADES, H.GRADES[1:]):
            self.assertGreaterEqual(above.swerve, below.swerve)
            self.assertGreaterEqual(above.hang, below.hang)
            self.assertGreaterEqual(above.top, below.top)

    def test_something_flat_arrives_before_a_jump_would_be_useless(self):
        """A rung that deals a log must be able to clear one.

        The jump covers ``speed * hang`` sub-rows and the overlap is
        :data:`SPAN` long, so a rung whose top gear cannot span it has
        dealt an obstacle with no answer but the swerve — which is a
        fine obstacle and a broken jump, and the two would be hard to
        tell apart from a learning curve.
        """
        for level, grade in enumerate(H.GRADES, start=1):
            if not any(not H.KINDS[kind].tall for kind in grade.kinds):
                continue
            self.assertGreaterEqual(grade.top * grade.hang, H.SPAN, level)

    def test_the_ports_are_one_flat_list(self):
        """Six for the wheel and five for the sights, out of one budget."""
        self.assertEqual(H.PORTS, len(H.WHEEL) + len(H.SIGHTS))
        self.assertEqual(sorted(H.WHEEL + H.SIGHTS), list(range(H.PORTS)))


class EveryRoadHasACleanLineThroughIt(unittest.TestCase):
    """The generator's promise, checked on every rung by driving it."""

    def deals(self, level, count=DEALS):
        dice = random.Random(level * 7 + 1)
        return [H.generate(level, seed=dice.randrange(1 << 30))
                for _deal in range(count)]

    def test_every_deal_solves(self):
        for level in range(1, len(H.GRADES) + 1):
            for road in self.deals(level):
                self.assertIsNotNone(H.line(road), (level, road.start))

    def test_the_line_it_finds_drives_clean_and_in_time(self):
        for level in range(1, len(H.GRADES) + 1):
            for road in self.deals(level):
                ride = run(road, H.line(road))
                self.assertTrue(H.cleared(ride, road), level)
                self.assertEqual(ride.clipped, 0, level)
                self.assertLessEqual(ride.ticks, road.clock, level)

    def test_the_clock_is_the_rung_s_slack_on_the_road_s_own_par(self):
        for level in range(1, len(H.GRADES) + 1):
            grade = H.GRADES[level - 1]
            for road in self.deals(level, 4):
                self.assertEqual(road.par, len(H.line(road)))
                self.assertGreaterEqual(road.clock, road.par)
                self.assertLessEqual(road.clock, road.par * grade.slack + 1)

    def test_an_impossible_road_is_reported_as_one(self):
        """Or the promise above is a promise about nothing."""
        wall = road_of(['...', '...', '...', '...', 'DDD', '...'])
        self.assertIsNone(H.line(wall))
        self.assertFalse(H.drivable(wall))

    def test_a_road_that_cannot_be_driven_in_time_is_one_too(self):
        clear = road_of(['...'] * 12, clock=3)
        self.assertIsNone(H.line(clear))

    def test_the_first_rows_are_clear(self):
        """The first thing a road asks is whether you were looking."""
        for level in range(1, len(H.GRADES) + 1):
            for road in self.deals(level, 6):
                for haz in road.hazards:
                    self.assertGreaterEqual(haz.at, H.RUN_IN * H.SUB)

    def test_never_more_than_two_abreast(self):
        """Three across three lanes is a wall, not a hazard."""
        for level in range(1, len(H.GRADES) + 1):
            for road in self.deals(level, 6):
                for marks in road.marks:
                    self.assertLessEqual(len(marks), LANES_CAP)

    def test_a_road_always_has_something_on_it_that_can_end_you(self):
        for level in range(1, len(H.GRADES) + 1):
            for road in self.deals(level, 6):
                self.assertGreater(road.deadly, 0, level)

    def test_the_same_seed_deals_the_same_road(self):
        for level in (1, 5, 10):
            one, two = H.generate(level, seed=99), H.generate(level, seed=99)
            self.assertEqual(one.hazards, two.hazards)
            self.assertEqual(one.sky, two.sky)
            self.assertEqual((one.start, one.clock), (two.start, two.clock))


LANES_CAP = 2


class TheSwerve(unittest.TestCase):
    """Donkey's one rule, in three lanes and at a speed you chose."""

    def clear(self, swerve=2, rows=16, start=1, top=2):
        return road_of(['...'] * rows, start=start, swerve=swerve, top=top)

    def test_it_takes_the_rung_s_ticks(self):
        road = self.clear(swerve=3)
        ride = H.start_ride(road)
        ride = H.roll(ride, H.LEFT, road)
        for owed in (2, 1, 0):
            self.assertEqual(ride.cross, owed)
            if owed:
                self.assertEqual(ride.lane, 1)
                ride = H.roll(ride, H.HOLD, road)
        self.assertEqual(ride.lane, 0)
        self.assertTrue(ride.settled)

    def test_the_wheel_is_deaf_until_it_is_done(self):
        """Every port, not only the one that would undo it."""
        road = self.clear(swerve=3, top=3)
        ride = H.roll(H.start_ride(road), H.LEFT, road)
        for port in (H.RIGHT, H.LEFT, H.JUMP, H.FASTER, H.SLOWER):
            self.assertEqual(H.press(ride, port, road.grade), ride, port)

    def test_it_is_drawn_across_by_degrees_rather_than_in_one_go(self):
        road = self.clear(swerve=3)
        ride = H.press(H.start_ride(road), H.RIGHT, road.grade)
        seen = []
        while ride.cross:
            seen.append(round(H.drawn_lane(ride, road.grade), 3))
            ride = H.roll(ride, H.HOLD, road)
        self.assertEqual(len(seen), road.grade.swerve)
        self.assertEqual(seen, sorted(seen))
        self.assertGreater(seen[0], 1.0)
        self.assertLess(seen[-1], 2.0)
        self.assertEqual(H.drawn_lane(ride, road.grade), 2.0)

    def test_a_car_across_the_middle_is_in_both_lanes(self):
        road = road_of(['...'] * 5 + ['D..'] + ['...'] * 6, start=1)
        ride = H.start_ride(road)
        # Swerve away from lane 0 into lane 2: the donkey is in the lane
        # being left, and leaving is not being gone.
        ride = H.roll(ride, H.LEFT, road)
        while not H.over(ride, road):
            ride = H.roll(ride, H.HOLD, road)
        self.assertTrue(ride.hit)

    def test_and_a_car_that_finished_crossing_is_not(self):
        road = road_of(['...'] * 8 + ['D..'] + ['...'] * 4, start=1)
        ride = H.start_ride(road)
        ride = H.roll(ride, H.RIGHT, road)
        while not H.over(ride, road):
            ride = H.roll(ride, H.HOLD, road)
        self.assertFalse(ride.hit)
        self.assertEqual(ride.passed, 1)

    def test_a_swerve_off_the_edge_is_refused(self):
        road = self.clear(start=0)
        ride = H.start_ride(road)
        self.assertEqual(H.press(ride, H.LEFT, road.grade), ride)
        self.assertNotEqual(H.press(ride, H.RIGHT, road.grade), ride)

    def test_going_faster_is_more_road_across_the_middle(self):
        """The whole of what the throttle costs, in one comparison."""
        road = self.clear(swerve=2, top=3)
        spans = []
        for speed in (1, 3):
            ride = H.start_ride(road)._replace(speed=speed)
            began = ride.at
            ride = H.roll(ride, H.LEFT, road)
            while ride.cross:
                ride = H.roll(ride, H.HOLD, road)
            spans.append(ride.at - began)
        self.assertEqual(spans, [2, 6])


class TheJump(unittest.TestCase):
    """Flat things only, and only if you are off the ground for all of it."""

    def test_it_clears_something_flat(self):
        road = road_of(['...'] * 6 + ['L..'] + ['...'] * 5, start=0,
                       hang=3, top=3)
        ride = H.start_ride(road)._replace(speed=3)
        home = None
        for _tick in range(40):
            if H.over(ride, road):
                break
            ahead = road.marks[min(road.length - 1, ride.at + 3)]
            port = H.JUMP if ahead and ride.settled else H.HOLD
            ride = H.roll(ride, port, road)
            home = ride
        self.assertFalse(home.hit)
        self.assertEqual(home.passed, 1)

    def test_it_does_not_clear_something_tall(self):
        road = road_of(['...'] * 6 + ['D..'] + ['...'] * 5, start=0,
                       hang=6, top=3)
        ride = H.start_ride(road)._replace(speed=3)
        ride = H.roll(ride, H.JUMP, road)
        while not H.over(ride, road):
            ride = H.roll(ride, H.HOLD, road)
        self.assertTrue(ride.hit)

    def _one_jump(self, speed, hang):
        """Jump once, at the last tick before the log, and see what happens."""
        road = road_of(['...'] * 6 + ['L..'] + ['...'] * 6, start=0,
                       hang=hang, top=3)
        first = road.hazards[0].at
        ride = H.start_ride(road)._replace(speed=speed)
        jumped = False
        while not H.over(ride, road):
            port = H.HOLD
            if not jumped and ride.at + speed > first:
                port, jumped = H.JUMP, True
            ride = H.roll(ride, port, road)
        return ride

    def test_landing_half_way_over_it_is_a_crash(self):
        """The reason a crash is checked on every swept sub-row.

        One tick of hang at one sub-row a tick covers one sub-row of an
        overlap that is :data:`SPAN` long, so the car comes down inside
        the log. Resolved once, at the moment of meeting, this would
        have been a clean jump — which is why it is not resolved that
        way.
        """
        self.assertTrue(self._one_jump(speed=1, hang=1).hit)

    def test_speed_is_what_buys_the_jump(self):
        """One jump, one rung, two gears: the slow one comes down inside it.

        The slow car is not shut out of the log — it can hop over one a
        piece at a time, and the test below says so. What it cannot do
        is get over it for *one* tick, and a tick is what the clock and
        the sky are both charging in.
        """
        self.assertTrue(self._one_jump(speed=1, hang=2).hit)
        self.assertFalse(self._one_jump(speed=3, hang=2).hit)

    def test_a_slow_car_can_still_hop_it_a_piece_at_a_time(self):
        """And pays a tick for every hop, which is the whole cost of it."""
        road = road_of(['...'] * 6 + ['L..'] + ['...'] * 6, start=0,
                       hang=2, top=1)
        ride, hops = H.start_ride(road), 0
        while not H.over(ride, road):
            reach = min(road.length - 1, ride.at)
            port = H.HOLD
            if ride.settled and road.marks[reach]:
                port, hops = H.JUMP, hops + 1
            ride = H.roll(ride, port, road)
        self.assertFalse(ride.hit)
        self.assertGreater(hops, 1)

    def test_a_jump_cannot_be_started_mid_swerve_or_the_other_way_round(self):
        road = road_of(['...'] * 10, start=1, swerve=2, hang=3)
        crossing = H.roll(H.start_ride(road), H.LEFT, road)
        self.assertEqual(H.press(crossing, H.JUMP, road.grade), crossing)
        flying = H.roll(H.start_ride(road), H.JUMP, road)
        self.assertEqual(H.press(flying, H.LEFT, road.grade), flying)


class TheTolls(unittest.TestCase):
    """Nine kinds, five tolls, and each one resolved exactly once."""

    def meet(self, mark, start=0, speed=1, top=3, rows_before=6):
        road = road_of(['...'] * rows_before + [mark + '..']
                       + ['...'] * 6, start=start, top=top)
        ride = H.start_ride(road)._replace(speed=speed)
        while not H.over(ride, road):
            ride = H.roll(ride, H.HOLD, road)
        return road, ride

    def test_a_donkey_ends_the_road_where_the_bodies_meet(self):
        road, ride = self.meet('D')
        self.assertTrue(ride.hit)
        self.assertEqual(ride.passed, 0)
        self.assertEqual(ride.at, road.hazards[0].at + 1)

    def test_a_cone_costs_a_point_and_the_gearbox_but_not_the_road(self):
        _road, ride = self.meet('C', speed=3)
        self.assertFalse(ride.hit)
        self.assertEqual(ride.clipped, 1)
        self.assertEqual(ride.points, -1)
        self.assertEqual(ride.speed, 1)

    def test_and_it_only_costs_them_once(self):
        """Every sub-row is swept exactly once, whatever gear you are in."""
        for speed in (1, 2, 3):
            _road, ride = self.meet('R', speed=speed)
            self.assertEqual(ride.clipped, 1, speed)

    def test_a_coin_is_worth_the_speed_it_was_taken_at(self):
        for speed in (1, 3):
            _road, ride = self.meet('o', speed=speed)
            self.assertEqual(ride.points, speed)
            self.assertFalse(ride.hit)

    def test_a_pad_is_a_gear_you_did_not_ask_for(self):
        _road, ride = self.meet('>', speed=1, top=3)
        self.assertEqual(ride.points, 1)
        self.assertGreater(ride.speed, 1)

    def test_and_it_will_not_push_past_the_rung_s_top_gear(self):
        _road, ride = self.meet('>', speed=2, top=2)
        self.assertEqual(ride.speed, 2)

    def test_a_ramp_is_a_jump_nobody_spent_a_tick_on(self):
        road = road_of(['...'] * 6 + ['^..'] + ['...'] * 6, start=0, hang=3)
        ride = H.start_ride(road)
        flew = False
        while not H.over(ride, road):
            ride = H.roll(ride, H.HOLD, road)
            flew = flew or bool(ride.air)
        self.assertTrue(flew)
        self.assertFalse(ride.hit)

    def test_a_ramp_taken_mid_swerve_does_nothing(self):
        """Or a ride could be across the middle and in the air at once."""
        road = road_of(['...'] * 6 + ['^..'] + ['...'] * 6, start=0,
                       swerve=8, hang=3)
        ride = H.roll(H.start_ride(road), H.RIGHT, road)
        while not H.over(ride, road):
            ride = H.roll(ride, H.HOLD, road)
            self.assertFalse(ride.cross and ride.air)

    def test_a_prize_in_another_lane_is_not_collected(self):
        road = road_of(['...'] * 6 + ['..o'] + ['...'] * 6, start=0)
        ride = run(road, [H.HOLD] * 60)
        self.assertEqual(ride.points, 0)

    def test_nothing_flat_touches_a_car_that_is_over_it(self):
        for mark in ('C', 'o', '>'):
            road = road_of(['...'] * 6 + [mark + '..'] + ['...'] * 6,
                           start=0, hang=9, top=1)
            first = road.hazards[0].at
            ride, jumped = H.start_ride(road), False
            while not H.over(ride, road):
                port = H.HOLD
                if not jumped and ride.at + 1 > first:
                    port, jumped = H.JUMP, True
                ride = H.roll(ride, port, road)
            self.assertEqual((ride.clipped, ride.points), (0, 0), mark)

    def test_a_hazard_is_counted_past_when_it_is_past(self):
        road = road_of(['...'] * 6 + ['D..'] + ['...'] * 6, start=2)
        ride = H.start_ride(road)
        seen = []
        while not H.over(ride, road):
            ride = H.roll(ride, H.HOLD, road)
            seen.append((ride.at, ride.passed))
        first = next(at for at, passed in seen if passed)
        self.assertGreater(first, road.hazards[0].at)
        self.assertEqual(ride.passed, 1)


class TheClock(unittest.TestCase):
    """The thing that makes the throttle a decision rather than a slider."""

    def test_crawling_is_safe_and_loses_anyway(self):
        for level in (1, 5, 10):
            share = H.rehearse(level, MEASURE, policy='crawl')
            self.assertEqual(share, 0.0, level)

    def test_and_it_loses_to_the_clock_rather_than_to_a_truck(self):
        """A different failure, and the ladder rests on which one it is."""
        dice = random.Random(3)
        ran_out = 0
        for _deal in range(30):
            road = H.generate(1, seed=dice.randrange(1 << 30))
            done = H.play(road, want=1)
            ran_out += 1 if H.late(done.ride, road) else 0
        self.assertEqual(ran_out, 30)

    def test_a_road_is_over_when_the_clock_is(self):
        road = road_of(['...'] * 20, clock=5)
        ride = run(road, [H.HOLD] * 40)
        self.assertEqual(ride.ticks, 5)
        self.assertFalse(H.cleared(ride, road))
        self.assertTrue(H.late(ride, road))

    def test_a_road_with_no_clock_on_it_has_no_deadline(self):
        """Which is the state :func:`timed` solves it in."""
        road = road_of(['...'] * 6, clock=0)
        ride = run(road, [H.HOLD] * 60)
        self.assertTrue(H.cleared(ride, road))
        self.assertFalse(H.late(ride, road))


class TheSky(unittest.TestCase):
    """A second task rather than a second hazard."""

    def deal(self, level=8):
        dice = random.Random(5)
        while True:
            road = H.generate(level, seed=dice.randrange(1 << 30))
            if road.sky:
                return road

    def test_targets_are_pinned_to_the_road_rather_than_to_the_clock(self):
        road = self.deal()
        target = road.sky[0]
        self.assertFalse(target.aloft(target.at - 1))
        self.assertTrue(target.aloft(target.at))
        self.assertTrue(target.aloft(target.at + H.ALOFT - 1))
        self.assertFalse(target.aloft(target.at + H.ALOFT))

    def test_one_drifts_and_stays_on_the_screen_while_it_does(self):
        road = self.deal()
        for target in road.sky:
            for step in range(0, H.ALOFT, 3):
                across, up = target.where(target.at + step)
                self.assertTrue(0.0 <= across <= 1.0)
                self.assertTrue(0.0 <= up <= 1.0)

    def test_the_crosshair_takes_the_nearest_thing_under_it(self):
        road = self.deal()
        target = road.sky[0]
        across, up = target.where(target.at)
        self.assertEqual(H.sighted(road, target.at, across, up), 0)

    def test_and_nothing_at_all_when_it_is_pointed_at_nothing(self):
        road = self.deal()
        target = road.sky[0]
        across, up = target.where(target.at)
        away = 0.0 if across > 0.5 else 1.0
        self.assertIsNone(H.sighted(road, target.at, away,
                                    1.0 - up if abs(up - 0.5) > 0.2 else 0.0))

    def test_one_already_down_cannot_be_shot_again(self):
        road = self.deal()
        target = road.sky[0]
        across, up = target.where(target.at)
        self.assertIsNone(H.sighted(road, target.at, across, up, {0}))

    def test_nothing_in_the_sky_can_touch_the_car(self):
        """Which is what makes the cost of it attention and nothing else."""
        thick = H.GRADES[9]._replace(density=0.0, sky=2.0)
        dice = random.Random(1)
        road = H.build(thick, [], H._fly(thick, dice), start=1, clock=400)
        self.assertGreater(len(road.sky), 20)
        ride = run(road, [H.HOLD] * (road.length + 5))
        self.assertTrue(H.cleared(ride, road))
        self.assertEqual((ride.hit, ride.clipped), (False, 0))


class WhatSplittingCosts(unittest.TestCase):
    """The measurement the task exists to produce.

    Three runs of the same driver. The first never looks up. The second
    takes the sky only on ticks the wheel had no use for — a tick that
    would have been a hold, and every tick of a swerve or a jump, which
    the wheel is deaf for anyway. The third takes it the moment
    anything is up there.
    """

    RUNGS = (1, 5, 8, 10)

    def test_spare_ticks_are_free(self):
        for level in self.RUNGS:
            self.assertEqual(H.rehearse(level, MEASURE, policy='gunner'),
                             H.rehearse(level, MEASURE, policy='aimed'),
                             level)

    def test_and_they_are_enough_to_get_a_useful_share_of_the_sky(self):
        for level in (7, 8, 9, 10):
            _share, shots = H.sky_toll(level, MEASURE, policy='gunner')
            self.assertGreaterEqual(shots, 2.0, level)

    def test_taking_it_at_the_wrong_moment_loses_the_road(self):
        for level in (3, 5, 8, 10):
            greedy = H.rehearse(level, MEASURE, policy='sniper')
            spare = H.rehearse(level, MEASURE, policy='gunner')
            self.assertLess(greedy, spare * 0.75, level)

    def test_and_gets_less_of_the_sky_while_it_does_it(self):
        """The half of the finding that is not obvious.

        A driver that shoots on sight does not merely trade road for
        sky. It gets *fewer* targets as well, because the roads it is
        on end early — so there is no read of this in which the greedy
        policy is buying anything.
        """
        for level in (5, 8, 10):
            _spare, spare_shots = H.sky_toll(level, MEASURE, policy='gunner')
            _greedy, greedy_shots = H.sky_toll(level, MEASURE,
                                               policy='sniper')
            self.assertLess(greedy_shots, spare_shots, level)

    def test_swerving_on_sight_is_not_enough_once_the_road_is_busy(self):
        for level in (5, 8, 10):
            self.assertLess(H.rehearse(level, MEASURE, policy='reactive'),
                            H.rehearse(level, MEASURE, policy='aimed') * 0.6,
                            level)

    def test_the_floor_is_real_at_the_bottom_and_gone_by_the_middle(self):
        """Five ports in eleven do not touch the wheel, so a coin holds.

        Which is a floor worth knowing the shape of rather than
        quoting: anything read off the first rung is read against a
        fifth, and anything read off the fourth is read against zero.
        """
        self.assertGreater(H.rehearse(1, MEASURE, policy='random'), 0.05)
        for level in (4, 7, 10):
            self.assertLess(H.rehearse(level, MEASURE, policy='random'), 0.05,
                            level)

    def test_the_exact_line_is_the_ceiling_the_rest_are_shares_of(self):
        for level in (1, 5, 10):
            self.assertEqual(H.rehearse(level, DEALS, policy='exact'), 1.0,
                             level)


class WhyTheStageStopsAboveTheBand(unittest.TestCase):
    """Two of the nine kinds are verdict colours outright.

    The donkey is Okabe-Ito vermillion, which is the reader's pattern
    for a negative verdict with nothing blended about it, and the coin
    and the pad are the workshop's green. A road drawn into the band
    would pay itself a scalar for having scenery on it, which is why
    the stage is held above it by geometry rather than by palette.
    """

    def verdictish(self, colour):
        from neural_workshop.ui.verdict import BRIGHT, DIM
        return any(colour[i] >= BRIGHT
                   and all(colour[j] <= DIM for j in range(3) if j != i)
                   for i in range(3))

    def test_the_reader_would_know_a_verdict_if_it_saw_one(self):
        """Or everything else here is checking nothing at all."""
        self.assertTrue(self.verdictish((0, 200, 0)))
        self.assertFalse(self.verdictish((200, 200, 200)))

    def test_at_least_one_thing_on_the_road_is_a_verdict_on_its_own(self):
        from neural_workshop.ui.twohands import PAINT
        caught = [name for name, colour in PAINT.items()
                  if self.verdictish(colour)]
        self.assertTrue(caught)


@needs_ui
class ThroughTheBoundary(unittest.TestCase):
    """What a learner is actually handed, driven through the real wrapper.

    Everything above this is the rules or the screen. This is the one
    that puts the two together: the *same* driver, once with the sights
    off and once with them on, stepped through
    :class:`nwenv.twohands.TwoHandsEnv` and paid by the shared deriver
    reading the frames it published.

    It is here rather than in ``tests/test_env_tasks.py`` because what
    it checks is a claim about this task and not about the boundary.
    The claim is that the second channel is *payable* — a shot reaches
    the learner as a scalar at all — and that on spare ticks it is
    free, which is the whole task in one comparison.
    """

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, shoot, steps=1400):
        from nwenv import catalog
        env = catalog.env_class('two_hands')(seed=3, neutral_outcomes=True,
                                             rung=7, trials=2)
        task = env.task
        cross, paid = [0.5, 0.5], []
        try:
            for _step in range(steps):
                road, ride = task.road, task.ride
                port = H.HOLD
                if road is not None and task.phase == 'running':
                    if ride.settled:
                        port = H._wheel_port(road, ride, road.grade.top, 1.0)
                    if shoot and (port == H.HOLD or not ride.settled):
                        port = (H._sky_port(road, ride, cross, task.downed)
                                or H.HOLD)
                _obs, events, done = env.step(port)
                if port in H.SIGHTS:
                    cross[0], cross[1] = task.cross_x, task.cross_y
                paid.extend(event['scalar'] for event in events
                            if event.get('scalar'))
                if done:
                    break
        finally:
            env.close()
        return paid

    def test_driving_is_paid_through_the_frames(self):
        paid = self.drive(shoot=False)
        self.assertGreater(len(paid), 8)
        self.assertTrue(all(value > 0 for value in paid), paid)

    def test_and_the_sky_on_spare_ticks_is_paid_on_top_of_it(self):
        """Free, and it is the frames that say so rather than the model."""
        alone = self.drive(shoot=False)
        armed = self.drive(shoot=True)
        self.assertGreater(len(armed), len(alone))
        self.assertTrue(all(value > 0 for value in armed), armed)


@needs_ui
class TwoHandsScreenTests(unittest.TestCase):
    """The road on the screen, driven by hand on a clock that does not tick."""

    def setUp(self):
        close_overlays()
        self.saved = {option.key: state.cfg[option.key]
                      for option in taskoptions.TWO_HANDS.options}
        state.cfg.TWOHANDS_LEVEL = SCREEN_RUNG
        state.cfg.TWOHANDS_TRIALS = 2
        state.cfg.TWOHANDS_ADAPTIVE = False
        state.cfg.TWOHANDS_SET_SECONDS = 0.0
        self.now = 1000.0
        self.task = Twohands()
        self.task.clock = lambda: self.now
        # Seeded, because a screen test that deals its own road is a
        # screen test whose subject is up to the dice.
        self.task.rng = random.Random(11)

    def tearDown(self):
        self.task.close()
        close_overlays()
        state.cfg.update(self.saved)
        reset_window()

    def _ticks(self, count=1):
        for _tick in range(count):
            self.now += self.task.tick_seconds()
            self.task.update(0.016)

    def _running(self):
        self.task.start_run()
        self.now += self.task.set_seconds + 0.001
        self.task.update(0.016)
        return self.task.road

    # --- the task in the workshop ----------------------------------------

    def test_it_is_in_the_attention_category(self):
        self.assertIn('two_hands', [task for task, _n in TASKS['attention']])

    def test_it_has_an_options_screen(self):
        self.assertTrue(taskoptions.has_options('two_hands'))

    def test_a_trial_deals_a_road_and_puts_the_car_on_it(self):
        road = self._running()
        self.assertEqual(self.task.phase, 'running')
        self.assertEqual(self.task.ride.lane, road.start)
        self.assertEqual(self.task.ride.at, 0)
        self.assertEqual(road.length, road.rows * H.SUB)
        self.assertGreater(road.deadly, 0)
        self.assertGreater(road.clock, 0)
        self.task.on_draw()

    # --- the wheel --------------------------------------------------------

    def test_the_arrow_keys_steer_and_shift(self):
        self._running()
        self.task.ride = self.task.ride._replace(lane=1, to=1)
        self.task.on_key_press(key.LEFT, 0)
        self.assertEqual(self.task.ride.to, 0)
        self.assertTrue(self.task.ride.cross)
        self.task.ride = self.task.ride._replace(cross=0, to=1, lane=1)
        self.task.on_key_press(key.UP, 0)
        self.assertEqual(self.task.ride.speed, 2)
        self.task.on_key_press(key.DOWN, 0)
        self.assertEqual(self.task.ride.speed, 1)

    def test_space_starts_the_run_and_then_jumps(self):
        self.task.on_key_press(key.SPACE, 0)
        self.assertIn(self.task.phase, ('setting', 'running'))
        self.now += self.task.set_seconds + 0.001
        self.task.update(0.016)
        self.assertFalse(self.task.ride.air)
        self.task.on_key_press(key.SPACE, 0)
        self.assertTrue(self.task.ride.air)

    def test_a_port_mid_commitment_is_swallowed(self):
        self._running()
        self.assertTrue(self.task.act(H.JUMP))
        self.assertFalse(self.task.act(H.LEFT))
        self.assertFalse(self.task.act(H.FASTER))

    def test_holding_is_a_port_that_does_nothing_and_says_so(self):
        self._running()
        self.assertFalse(self.task.act(H.HOLD))
        self.assertTrue(self.task.ride.settled)

    def test_a_port_outside_the_running_phase_does_nothing(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'setting')
        self.assertFalse(self.task.act(H.LEFT))

    # --- the sights -------------------------------------------------------

    def test_the_aim_ports_move_the_crosshair(self):
        self._running()
        self.task.cross_x = self.task.cross_y = 0.5
        self.assertTrue(self.task.act(H.AIM_LEFT))
        self.assertAlmostEqual(self.task.cross_x, 0.5 - H.NUDGE)
        self.assertTrue(self.task.act(H.AIM_UP))
        self.assertAlmostEqual(self.task.cross_y, 0.5 + H.NUDGE)

    def test_and_they_stop_at_the_edge_of_the_sky(self):
        self._running()
        for _step in range(40):
            self.task.act(H.AIM_LEFT)
            self.task.act(H.AIM_DOWN)
        self.assertEqual((self.task.cross_x, self.task.cross_y), (0.0, 0.0))

    def test_the_mouse_and_the_ports_write_the_same_two_numbers(self):
        """Or a person and a learner are pointing different instruments."""
        self._running()
        left, bottom, width, height = self.task._sky_rect()
        self.task.on_mouse_motion(int(left + width * 0.25),
                                  int(bottom + height * 0.75), 0, 0)
        self.assertAlmostEqual(self.task.cross_x, 0.25, places=1)
        self.assertAlmostEqual(self.task.cross_y, 0.75, places=1)

    def test_firing_at_a_target_takes_it_down_and_pays(self):
        road = self._running()
        target = H.Target(at=self.task.ride.at, across=0.4, up=0.6, drift=0.0)
        self.task.road = road._replace(sky=(target,))
        self.task.cross_x, self.task.cross_y = 0.4, 0.6
        self.assertTrue(self.task.act(H.FIRE))
        self.assertEqual(self.task.shot, 1)
        self.assertEqual(self.task.points, 1)
        self.assertFalse(self.task.act(H.FIRE))

    def test_a_shot_is_paid_on_the_tick_and_not_on_the_press(self):
        """A boundary step is the port and then the tick, in that order.

        The frame the learner is handed is drawn after the tick, so a
        label put up by the press is a label the tick takes down again
        — and the shot is paid nothing at all. This is the shape of
        the bug that finding cost, kept where it would come back.
        """
        self.task.coach = True
        road = self._running()
        target = H.Target(at=self.task.ride.at, across=0.4, up=0.6,
                          drift=0.0)
        self.task.road = road._replace(sky=(target,))
        self.task.cross_x, self.task.cross_y = 0.4, 0.6
        self.task.act(H.FIRE)
        self.assertIsNone(self.task.verdict_shown)
        self._ticks(1)
        self.assertIsNotNone(self.task.verdict_shown)
        self.assertTrue(self.task.verdict_shown[0])
        # And it is paid once rather than for the rest of the road.
        self._ticks(1)
        self.assertIsNone(self.task.verdict_shown)

    def test_firing_at_nothing_costs_the_tick_and_gets_nothing(self):
        self._running()
        self.task.road = self.task.road._replace(sky=())
        self.assertFalse(self.task.act(H.FIRE))
        self.assertEqual(self.task.shot, 0)

    def test_the_sights_never_touch_the_car(self):
        self._running()
        was = self.task.ride
        for port in H.SIGHTS:
            self.task.act(port)
        self.assertEqual(self.task.ride, was)

    # --- how a road ends --------------------------------------------------

    def test_driving_the_line_clears_the_road_and_pays_green(self):
        road = self._running()
        for port in H.line(road):
            if self.task.phase != 'running':
                break
            self.task.act(port)
            self._ticks(1)
        self.assertEqual(self.task.phase, 'scored')
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.results[-1][1], True)

    def test_holding_into_a_donkey_pays_red(self):
        self._running()
        self.task.road = road_of(['...'] * 5 + ['.D.'] + ['...'] * 8,
                                 start=1)
        self.task.ride = H.start_ride(self.task.road)
        for _tick in range(self.task.road.length):
            if self.task.phase != 'running':
                break
            self._ticks(1)
        self.assertEqual(self.task.phase, 'scored')
        self.assertFalse(self.task.verdict_shown[0])
        self.assertTrue(self.task.ride.hit)

    def test_running_out_of_time_pays_red_and_says_which_it_was(self):
        self._running()
        self.task.road = road_of(['...'] * 14, start=1, clock=4)
        self.task.ride = H.start_ride(self.task.road)
        for _tick in range(8):
            if self.task.phase != 'running':
                break
            self._ticks(1)
        self.assertEqual(self.task.phase, 'scored')
        self.assertFalse(self.task.verdict_shown[0])
        self.assertFalse(self.task.ride.hit)
        self.assertIn('time', self.task.verdict_shown[1].lower())

    def test_the_run_ends_after_the_roads_it_was_asked_for(self):
        self._running()
        for _trial in range(2):
            for _tick in range(self.task.road.clock + 2):
                if self.task.phase != 'running':
                    break
                self._ticks(1)
            self.assertEqual(self.task.phase, 'scored')
            self.now += 4.0
            self.task.on_key_press(key.SPACE, 0)
            self.now += self.task.set_seconds + 0.001
            self.task.update(0.016)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['roads'], 2)

    def test_the_coach_stays_off_for_a_person(self):
        """The human game has to stay pixel-identical to what it was."""
        self.assertFalse(self.task.coach)
        self._running()
        self._ticks(6)
        self.assertIsNone(self.task.verdict_shown)

    def test_and_pays_per_tick_when_it_is_on(self):
        self.task.coach = True
        self._running()
        self.task.road = road_of(['...'] * 5 + ['.D.'] + ['...'] * 8,
                                 start=0)
        self.task.ride = H.start_ride(self.task.road)
        seen = []
        for _tick in range(self.task.road.length):
            if self.task.phase != 'running':
                break
            self._ticks(1)
            if self.task.verdict_shown is not None:
                seen.append(self.task.verdict_shown[0])
        self.assertIn(True, seen)

    # --- the layout -------------------------------------------------------

    def test_the_stage_and_the_sky_clear_the_band(self):
        from neural_workshop.ui.verdict import band_rows
        self._running()
        first, _past = band_rows(state.window.height)
        ceiling = state.window.height - first
        for rect in (self.task._stage(), self.task._sky_rect()):
            self.assertGreaterEqual(rect[1], ceiling)
        self.assertGreaterEqual(self.task._horizon(), ceiling)

    def test_nothing_the_road_draws_starts_below_it_either(self):
        """The stage is only a promise until the drawing keeps it.

        Every shape is walked at several window shapes, because a
        playfield that letterboxes its contents can be clear on a tall
        window and into the band on a wide one — which is exactly how
        the 3D Maze shipped a violation past a sweep.
        """
        import pyglet
        from neural_workshop import geometry
        from neural_workshop.ui.verdict import band_rows
        for width, height in ((800, 600), (1280, 720), (1024, 1200)):
            geometry.set_window_size(width, height)
            self.task.relayout()
            self._running()
            self._ticks(H.SUB * 3)
            self.task._redraw()
            first, _past = band_rows(state.window.height)
            ceiling = state.window.height - first
            for shape in self.task.drawn:
                if isinstance(shape, pyglet.shapes.Rectangle):
                    low = shape.y
                elif isinstance(shape, pyglet.shapes.Circle):
                    low = shape.y - shape.radius
                elif isinstance(shape, pyglet.shapes.Polygon):
                    low = min(point[1] for point
                              in getattr(shape, '_coordinates', ((0, 1e9),)))
                else:
                    continue
                self.assertGreaterEqual(low + 1, ceiling,
                                        (width, height, type(shape)))

    def test_the_road_converges_and_stays_inside_the_playfield(self):
        from neural_workshop.ui.twohands import SIGHT
        left, _bottom, width, _height = self.task._stage()
        near = self.task.far(0.0)[1]
        far = self.task.far(float(SIGHT))[1]
        self.assertGreater(near, far)
        self.assertLess(near * 2.0, width)
        for lane in range(H.LANES):
            for ahead in (0.0, 4.0, float(SIGHT)):
                x = self.task.lane_x(ahead, lane)
                self.assertGreater(x, left)
                self.assertLess(x, left + width)

    def test_the_three_lanes_stay_apart_at_every_distance(self):
        """Or the road is drawn in a way the rules do not agree with."""
        for ahead in (0.0, 2.0, 6.0):
            xs = [self.task.lane_x(ahead, lane) for lane in range(H.LANES)]
            self.assertEqual(xs, sorted(xs))
            self.assertGreater(min(b - a for a, b in zip(xs, xs[1:])), 1.0)


if __name__ == '__main__':
    unittest.main()
