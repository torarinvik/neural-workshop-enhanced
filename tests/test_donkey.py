#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Donkey: the swerve, the road that always has a line through it, and the band.

Three things here are worth testing hard.

The **road** must be passable. A road that cannot be driven scores as a
failure the player could not have avoided, and it would look exactly
like a player who was not good enough — so every deal on every rung is
put through the exact solver, and the presses it hands back are driven
down the road and required to come out the far end.

The **swerve** is the whole of the task and it is three rules: it takes
the rung's number of rows, it cannot be called off, and while it is
running a donkey in either lane hits the car. Each gets a test on a
road written by hand rather than dealt, because a claim about a rule
should not depend on what the dice did.

And the **gap between two shallow policies** is measured rather than
asserted. Swerving on sight of the donkey is perfect play while the
crossing is one row wide and nearly worthless once it is two, and that
number is what the upper half of the ladder is for. The opposite
finding is recorded too, because it is the one that surprised: aiming
the press at the swerve is enough on *every* road this deals, so the
task has no planning depth and the tests say so out loud rather than
leaving a rung name to imply otherwise.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import (TASKS, Donkey, close_overlays, key, needs_ui,
                       reset_window, state, taskoptions)

from neural_workshop import donkey as D

#: Deals per rung for the sweeps that have to visit every rung.
DEALS = 60

#: Deals per rung for the two measurements. Enough that a 9% and a 100%
#: cannot be confused for one another, and small enough to run every time.
MEASURE = 200

#: The rung the screen tests are pinned at: a one-row swerve, so a road
#: can be driven by hand without the test having to plan.
SCREEN_RUNG = 3


def road_of(blocked, swerve=1, start=0, rows=None):
    """A road written out rather than dealt.

    *blocked* is one character a row: ``.`` clear, ``L`` a donkey in
    lane 0, ``R`` a donkey in lane 1.
    """
    lanes = {'.': None, 'L': 0, 'R': 1}
    grade = D.Grade('by hand', rows or len(blocked), 0.0, swerve)
    return D.Road(grade=grade, start=start,
                  blocked=tuple(lanes[mark] for mark in blocked))


def blend(front, back, part):
    return tuple(int(round(a + (b - a) * part)) for a, b in zip(front, back))


def verdictish(colour):
    """What the outcome reader counts: one channel up, the other two down."""
    from neural_workshop.ui.verdict import BRIGHT, DIM
    return any(colour[i] >= BRIGHT
               and all(colour[j] <= DIM for j in range(3) if j != i)
               for i in range(3))


class TheLadder(unittest.TestCase):
    """Ten rungs, and each one has to add something."""

    def test_the_first_rung_is_the_original_game(self):
        first = D.GRADES[0]
        self.assertEqual(first.swerve, 1)
        self.assertLess(first.density, 0.15)

    def test_the_swerve_only_ever_widens(self):
        widths = [grade.swerve for grade in D.GRADES]
        self.assertEqual(widths, sorted(widths))
        self.assertGreater(widths[-1], widths[0])

    def test_each_rung_differs_from_the_one_below_it(self):
        for below, above in zip(D.GRADES, D.GRADES[1:]):
            self.assertNotEqual(
                (below.rows, below.density, below.swerve),
                (above.rows, above.density, above.swerve), above.name)

    def test_the_road_is_long_enough_to_hold_on_over(self):
        for grade in D.GRADES:
            self.assertGreater(grade.rows, D.RUN_IN * 4, grade.name)


class EveryRoadHasALineThroughIt(unittest.TestCase):
    """The claim the whole task rests on, checked on every rung.

    Not "the generator tries to". :func:`neural_workshop.donkey.line` is
    an exact search over the same states the generator maintains, and
    what it hands back is *driven* — the presses go down the road and
    the car has to come out the far end. A solver agreeing with itself
    would prove nothing.
    """

    def test_every_deal_is_survivable(self):
        rng = random.Random(0)
        for level in range(1, len(D.GRADES) + 1):
            for _deal in range(DEALS):
                road = D.generate(level, seed=rng.randrange(1 << 30))
                self.assertTrue(D.survivable(road), road.grade.name)

    def test_the_line_it_finds_actually_drives(self):
        rng = random.Random(1)
        for level in range(1, len(D.GRADES) + 1):
            for _deal in range(DEALS):
                road = D.generate(level, seed=rng.randrange(1 << 30))
                presses = D.line(road)
                self.assertIsNotNone(presses, road.grade.name)
                car = D.drive(road, presses)
                self.assertTrue(D.cleared(car, road), road.grade.name)
                self.assertEqual(car.passed, road.donkeys)

    def test_an_impossible_road_is_reported_as_one(self):
        """A road nobody could drive, so ``line`` has to say so.

        Donkeys on adjacent rows in opposite lanes: the first pins the
        car in the far lane and the second stands in it, and the one row
        between them is not enough to cross in. The generator will never
        lay this — that is what makes it the right thing to hand the
        solver by hand.
        """
        road = road_of('...LR...')
        self.assertFalse(D.survivable(road))
        self.assertIsNone(D.line(road))

    def test_the_first_rows_are_clear(self):
        for level in range(1, len(D.GRADES) + 1):
            road = D.generate(level, seed=level)
            for row in range(D.RUN_IN):
                self.assertIsNone(road.blocked[row])

    def test_a_road_is_never_empty(self):
        rng = random.Random(2)
        for level in range(1, len(D.GRADES) + 1):
            for _deal in range(DEALS):
                road = D.generate(level, seed=rng.randrange(1 << 30))
                self.assertGreater(road.donkeys, 0, road.grade.name)

    def test_the_same_seed_deals_the_same_road(self):
        self.assertEqual(D.generate(6, seed=99), D.generate(6, seed=99))


class TheSwerve(unittest.TestCase):
    """Three rules, on roads written out rather than dealt."""

    def test_it_takes_the_rung_s_rows(self):
        road = road_of('.........', swerve=2)
        car = D.Car(road.start, 2)
        D.steer(car, D.SWITCH)
        self.assertEqual(car.lane, 0)
        D.beat(car, road)
        self.assertEqual(car.lane, 0)      # still across the middle
        self.assertTrue(car.across)
        D.beat(car, road)
        self.assertEqual(car.lane, 1)
        self.assertFalse(car.across)

    def test_a_second_press_cannot_call_it_off(self):
        road = road_of('.........', swerve=2)
        car = D.Car(road.start, 2)
        self.assertTrue(D.steer(car, D.SWITCH))
        self.assertFalse(D.steer(car, D.SWITCH))
        D.beat(car, road)
        self.assertFalse(D.steer(car, D.SWITCH))
        D.beat(car, road)
        self.assertEqual(car.lane, 1)

    def test_a_car_across_the_middle_is_in_both_lanes(self):
        """The rule that makes the dodge-on-sight a crash.

        The donkey is in the lane the car is *leaving*, and it still
        hits: while the crossing runs, both lanes are the car's lane.
        """
        road = road_of('...R.....', swerve=1, start=1)
        car = D.Car(road.start, 1)
        for _row in range(3):
            D.beat(car, road)
        D.steer(car, D.SWITCH)              # too late, and into it
        D.beat(car, road)
        self.assertTrue(car.hit)

    def test_the_same_press_one_row_earlier_gets_by(self):
        road = road_of('...R.....', swerve=1, start=1)
        car = D.Car(road.start, 1)
        for _row in range(2):
            D.beat(car, road)
        D.steer(car, D.SWITCH)
        D.beat(car, road)                   # crossing, over a clear row
        self.assertFalse(car.hit)
        D.beat(car, road)                   # the donkey, in the other lane
        self.assertFalse(car.hit)
        self.assertEqual(car.passed, 1)

    def test_holding_costs_nothing_and_changes_nothing(self):
        road = road_of('.........')
        car = D.Car(road.start, 1)
        self.assertFalse(D.steer(car, D.HOLD))
        D.beat(car, road)
        self.assertEqual(car.lane, road.start)
        self.assertFalse(car.across)

    def test_a_hit_ends_the_road_there(self):
        road = road_of('...L.....', swerve=1, start=0)
        car = D.drive(road, [D.HOLD] * road.length)
        self.assertTrue(car.hit)
        self.assertTrue(D.over(car, road))
        self.assertFalse(D.cleared(car, road))
        self.assertEqual(car.row, 4)


class WhatTheTwoShallowPoliciesAreWorth(unittest.TestCase):
    """The measurement the upper half of the ladder exists for.

    Both numbers are measured here rather than quoted from the
    docstrings, so a change to the generator that quietly flattened the
    ladder would fail this rather than leave the prose lying.
    """

    def test_swerving_on_sight_is_perfect_while_the_crossing_is_one_row(self):
        for level in range(1, 6):
            self.assertEqual(D.GRADES[level - 1].swerve, 1)
            self.assertEqual(D.rehearse(level, MEASURE, policy='reactive'),
                             1.0, 'rung %d' % level)

    def test_and_nearly_worthless_once_it_is_wider(self):
        for level in range(6, len(D.GRADES) + 1):
            self.assertGreater(D.GRADES[level - 1].swerve, 1)
            share = D.rehearse(level, MEASURE, policy='reactive')
            self.assertLess(share, 0.2, 'rung %d cleared %.2f' % (level, share))

    def test_aiming_at_the_swerve_clears_every_road_on_every_rung(self):
        """The finding that was not expected, kept where it can go stale.

        The task was built expecting the wide-swerve rungs to need a
        line chosen several rows out. They do not: :func:`generate`
        refuses any donkey that would empty the surviving states, and
        with a two-row crossing that refusal leaves nothing standing
        that a press aimed at the swerve cannot handle. If a future
        generator did leave something harder, this fails and says the
        docstrings have gone out of date rather than letting them claim
        a depth the task never had.
        """
        for level in range(1, len(D.GRADES) + 1):
            self.assertEqual(D.rehearse(level, MEASURE, policy='aimed'), 1.0,
                             'rung %d' % level)

    def test_guessing_is_worth_much_less_than_either(self):
        for level in range(1, len(D.GRADES) + 1):
            self.assertLess(D.rehearse(level, MEASURE), 0.25,
                            'rung %d' % level)

    def test_the_exact_line_is_the_ceiling_the_others_are_measured_against(self):
        for level in (1, 6, 10):
            self.assertEqual(D.rehearse(level, DEALS, policy='exact'), 1.0)


class WhyTheStageStopsAboveTheBand(unittest.TestCase):
    """The reason for the layout, kept beside the layout.

    ``tests/check_band.py`` sweeps this task and reports it clean. That
    is not the guard and it never is: a sweep runs one window size and
    whatever the deal happened to lay, and both of those have hidden a
    violation in this repository before. The guard is the geometry test
    below.

    What this class is for is the *reason* the geometry is what it is,
    so that it cannot go quietly stale. It is a shorter argument here
    than in the two 3D tasks next door: the donkey is not a colour that
    blends its way into the reader's window on its way to a background,
    it is a colour the reader counts outright.
    """

    def test_the_reader_would_know_a_verdict_if_it_saw_one(self):
        """Or everything else here is checking nothing at all."""
        self.assertTrue(verdictish((213, 94, 0)))
        self.assertFalse(verdictish((0, 158, 115)))
        self.assertFalse(verdictish((170, 170, 170)))

    def test_a_donkey_is_a_negative_verdict_on_its_own(self):
        from neural_workshop.ui.donkey import DONKEY
        self.assertTrue(verdictish(DONKEY))

    def test_and_its_edge_against_either_page_is_one_too(self):
        """It does not even need a lucky blend, unlike the 3D tasks.

        There the reason for the layout was a colour that is safe on its
        own and becomes a verdict only somewhere along its
        anti-aliased edge, which is a fiddly argument. Here it is a
        verdict at full strength and stays one a sixth of the way to a
        black page and a third of the way to a white one — so it is not
        the edge that has to be kept out of the band, it is the donkey.
        """
        from neural_workshop.ui.donkey import DONKEY
        for page in ((255, 255, 255), (0, 0, 0)):
            caught = [part for part in range(33)
                      if verdictish(blend(DONKEY, page, part / 32.0))]
            self.assertGreaterEqual(len(caught), 5, page)


@needs_ui
class DonkeyScreenTests(unittest.TestCase):
    """The road on the screen, driven by hand on a clock that does not tick."""

    def setUp(self):
        close_overlays()
        self.saved = {option.key: state.cfg[option.key]
                      for option in taskoptions.DONKEY.options}
        state.cfg.DONKEY_LEVEL = SCREEN_RUNG
        state.cfg.DONKEY_TRIALS = 2
        state.cfg.DONKEY_ADAPTIVE = False
        state.cfg.DONKEY_SET_SECONDS = 0.0
        self.now = 1000.0
        self.task = Donkey()
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        state.cfg.update(self.saved)
        reset_window()

    def _rows(self, count=1):
        """Let *count* rows of road arrive."""
        for _row in range(count):
            self.now += self.task.beat_seconds
            self.task.update(0.016)

    def _running(self):
        self.task.start_run()
        self._rows(0)
        self.now += self.task.set_seconds + 0.001
        self.task.update(0.016)
        return self.task.road

    # --- the task in the workshop ----------------------------------------

    def test_it_is_in_the_attention_category(self):
        self.assertIn('donkey', [task for task, _n in TASKS['attention']])

    def test_it_has_an_options_screen(self):
        self.assertTrue(taskoptions.has_options('donkey'))

    def test_a_trial_deals_a_road_and_puts_the_car_on_it(self):
        road = self._running()
        self.assertEqual(self.task.phase, 'running')
        self.assertEqual(self.task.car.lane, road.start)
        self.assertEqual(self.task.car.row, 0)
        self.assertGreater(road.donkeys, 0)
        self.task.on_draw()

    # --- the key ----------------------------------------------------------

    def test_space_starts_the_run_and_then_swerves(self):
        self.task.on_key_press(key.SPACE, 0)
        self.assertIn(self.task.phase, ('setting', 'running'))
        self.now += self.task.set_seconds + 0.001
        self.task.update(0.016)
        self.assertFalse(self.task.car.across)
        self.task.on_key_press(key.SPACE, 0)
        self.assertTrue(self.task.car.across)

    def test_a_press_mid_swerve_is_swallowed(self):
        self._running()
        self.assertTrue(self.task.act(D.SWITCH))
        self.assertFalse(self.task.act(D.SWITCH))

    def test_holding_is_a_port_that_does_nothing_and_says_so(self):
        self._running()
        self.assertFalse(self.task.act(D.HOLD))
        self.assertFalse(self.task.car.across)

    def test_a_press_outside_the_running_phase_does_nothing(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'setting')
        self.assertFalse(self.task.act(D.SWITCH))

    # --- how a road ends --------------------------------------------------

    def test_driving_the_line_clears_the_road_and_pays_green(self):
        road = self._running()
        for port in D.line(road):
            if self.task.phase != 'running':
                break
            self.task.act(port)
            self._rows(1)
        self.assertEqual(self.task.phase, 'scored')
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.results[-1][1], True)

    def test_holding_into_a_donkey_pays_red(self):
        road = self._running()
        for _row in range(road.length):
            if self.task.phase != 'running':
                break
            self._rows(1)
        self.assertEqual(self.task.phase, 'scored')
        self.assertFalse(self.task.verdict_shown[0])
        self.assertTrue(self.task.car.hit)

    def test_the_run_ends_after_the_roads_it_was_asked_for(self):
        self._running()
        for _trial in range(2):
            for _row in range(self.task.road.length + 2):
                if self.task.phase != 'running':
                    break
                self._rows(1)
            self.assertEqual(self.task.phase, 'scored')
            self.now += 2.0
            self.task.on_key_press(key.SPACE, 0)   # deal the next road
            self.now += self.task.set_seconds + 0.001
            self.task.update(0.016)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['roads'], 2)

    # --- the layout -------------------------------------------------------

    def test_the_stage_and_the_road_clear_the_band(self):
        """By geometry, whatever the deal put on the road.

        A sweep is the wrong instrument here for the reason written at
        the top of :class:`WhyTheStageStopsAboveTheBand`, and the right
        one is the bottom edge of the stage: nothing this screen paints
        starts below it.
        """
        from neural_workshop.ui.verdict import band_rows
        self._running()
        first, _past = band_rows(state.window.height)
        ceiling = state.window.height - first
        for rect in (self.task._stage(), self.task._road_rect()):
            self.assertGreaterEqual(rect[1], ceiling)

    def test_nothing_the_road_draws_starts_below_it_either(self):
        """The stage is only a promise until the drawing keeps it.

        Every shape the road puts down is walked, at several window
        shapes, because a panel that letterboxes its contents can be
        clear on a tall window and into the band on a wide one — which
        is exactly how the 3D Maze shipped a violation past a sweep.
        """
        import pyglet
        from neural_workshop.ui.verdict import band_rows
        from neural_workshop import geometry
        from neural_workshop import display as disp
        for width, height in ((1280, 720), (1600, 900), (1920, 1080),
                              (2560, 1080), (1824, 1368)):
            geometry.set_window_size(width, height)
            disp.relayout()
            self._running()
            self._rows(4)
            first, _past = band_rows(state.window.height)
            ceiling = state.window.height - first
            shapes = [shape for shape in self.task.drawn
                      if isinstance(shape, pyglet.shapes.Rectangle)]
            self.assertTrue(shapes, '%dx%d drew nothing' % (width, height))
            for shape in shapes:
                self.assertGreaterEqual(
                    shape.y, ceiling,
                    '%dx%d: a shape starts at %.0f, ceiling %d'
                    % (width, height, shape.y, ceiling))

    def test_the_road_is_still_wide_enough_to_read_at_every_shape(self):
        """Giving up the bottom quarter must not squeeze the lanes shut.

        Checked rather than hoped: the road is a column down the middle
        of the stage and its width is capped by the stage's *height*, so
        the height the band takes is the dimension that could have cost
        something here.
        """
        from neural_workshop import geometry
        from neural_workshop import display as disp
        for width, height in ((1280, 720), (1920, 1080), (2560, 1080)):
            geometry.set_window_size(width, height)
            disp.relayout()
            self._running()
            _left, _bottom, wide, tall = self.task._road_rect()
            self.assertGreater(wide / 2.0, 40, '%dx%d' % (width, height))
            self.assertGreater(self.task._row_height(), 12,
                               '%dx%d' % (width, height))
            self.assertGreater(tall, wide * 0.9, '%dx%d' % (width, height))

    def test_the_two_lanes_stay_inside_the_tarmac(self):
        self._running()
        left, _bottom, wide, _tall = self.task._road_rect()
        for lane in (0.0, 0.5, 1.0):
            self.assertGreater(self.task._lane_x(lane), left)
            self.assertLess(self.task._lane_x(lane), left + wide)

    # --- the crash has to look like one -----------------------------------

    def _painted(self, colour):
        """The rectangles drawn in *colour*, as (left, bottom, right, top)."""
        import pyglet
        return [(shape.x, shape.y, shape.x + shape.width,
                 shape.y + shape.height)
                for shape in self.task.drawn
                if isinstance(shape, pyglet.shapes.Rectangle)
                and tuple(shape.color)[:3] == colour]

    @staticmethod
    def _overlap(one, two):
        return (one[0] < two[2] and two[0] < one[2]
                and one[1] < two[3] and two[1] < one[3])

    def _hold_until_hit(self):
        self._running()
        while self.task.phase == 'running':
            self._rows(1)
        self.assertTrue(self.task.car.hit)
        return self.task.road.blocked[self.task.car.row - 1]

    def test_the_row_the_car_has_met_is_drawn_on_the_car(self):
        """The bug this is here for made every collision look like none.

        :func:`~neural_workshop.donkey.beat` checks the arriving row
        against the car, so once the beat has run the two are in the
        same place. The first version of the screen drew only the road
        *ahead* — so the donkey the car had just hit vanished from a
        position a full row-height in front of the bumper, and the
        round ended over a gap.
        """
        self._running()
        self._rows(2)
        _left, bottom, _wide, _tall = self.task._road_rect()
        step = self.task._row_height()
        self.assertAlmostEqual(self.task._row_y(-1), bottom + step * 0.5)
        self.assertAlmostEqual(self.task._row_y(0), bottom + step * 1.5)

    def test_a_donkey_the_car_hit_is_drawn_over_the_bonnet(self):
        from neural_workshop.ui.donkey import CAR, DONKEY
        self._hold_until_hit()
        cars = self._painted(CAR)
        self.assertEqual(len(cars), 1)
        touching = [box for box in self._painted(DONKEY)
                    if self._overlap(box, cars[0])]
        self.assertTrue(touching,
                        'the car hit a donkey and nothing was drawn on it')

    def test_a_donkey_it_got_by_is_drawn_beside_the_bonnet_instead(self):
        """The same row in the same place; only the lane is different.

        Which is the whole of the rule, so it should be the whole of the
        difference on the screen too. Driven on a road written out
        rather than dealt, because whether a deal offers a donkey in the
        far lane at a convenient moment is up to the dice, and a test
        that skips itself when they go the other way is not a test.
        """
        from neural_workshop.ui.donkey import CAR, DONKEY
        self._running()
        self.task.road = road_of('....R' + '.' * 8, start=0)
        self.task.car = D.Car(0, 1)
        self._rows(5)
        self.assertEqual(self.task.car.passed, 1)
        self.assertFalse(self.task.car.hit)
        cars = self._painted(CAR)
        self.assertEqual(len(cars), 1)
        level = [box for box in self._painted(DONKEY)
                 if box[1] < cars[0][3] and cars[0][1] < box[3]]
        self.assertTrue(level, 'the donkey it passed was not drawn level')
        for box in level:
            self.assertFalse(self._overlap(box, cars[0]))

    def test_the_car_is_drawn_between_the_lanes_while_it_crosses(self):
        """The screen must not claim the car is somewhere it is not safe."""
        self._running()
        settled = self.task._lane_x(float(self.task.car.lane))
        self.task.act(D.SWITCH)
        crossing = self.task._lane_x(
            self.task.car.lane
            + (1 - 2 * self.task.car.lane)
            * (self.task.car.swerve - self.task.car.crossing + 1)
            / float(self.task.car.swerve + 1))
        self.assertNotAlmostEqual(settled, crossing, places=1)


if __name__ == '__main__':
    unittest.main()
