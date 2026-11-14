#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dispatch: the town's rules, the fairness of par, and the boundary.

Par means something only if the reference plays the round the player
plays, so the schedule is held to depending on the clock alone and the
simulation to stepping the same however it is driven. The rules are
checked on hand-made rounds, where what should happen can be worked
out on paper. And the boundary is held to paying the reference's own
orders through the seventeen ports, refusing a town nobody dispatched,
and paying each incident once when it pays per event.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import dispatch as D


def round_of(reports, rung=1):
    """A hand-made round on *rung*'s rules."""
    return D.Deal(D.grade(rung), tuple(reports))


def report(at=0.0, x=0.5, y=0.5, need=3.0, growth=0.2, false=False,
           factor=1.0):
    return D.Report(at, x, y, need, growth, false, factor)


def run(world, seconds):
    for _step in range(int(round(seconds / D.SIM_DT))):
        world.step(D.SIM_DT)


class TheLadder(unittest.TestCase):

    def test_the_load_outgrows_the_hands(self):
        last = D.grade(1)
        for rung in range(2, 80):
            level = D.grade(rung)
            self.assertGreaterEqual(level.growth[0], last.growth[0])
            self.assertGreaterEqual(level.false_rate, last.false_rate)
            self.assertGreaterEqual(level.error, last.error)
            self.assertGreaterEqual(level.burst, last.burst)
            self.assertLessEqual(level.factor, last.factor)
            self.assertLessEqual(level.crews, 3)
            last = level

    def test_uncertainty_arrives_in_two_steps(self):
        self.assertFalse(D.grade(3).scout)
        self.assertTrue(D.grade(4).scout)
        self.assertEqual(D.grade(5).error, 0.0)
        self.assertGreater(D.grade(6).error, 0.0)

    def test_past_twenty_par_is_below_the_reference(self):
        self.assertGreaterEqual(D.grade(20).factor, 1.0)
        self.assertLess(D.grade(21).factor, 1.0)
        self.assertLess(D.grade(40).factor, D.grade(30).factor)


class TheSchedule(unittest.TestCase):

    def test_a_round_is_fixed_by_its_seed(self):
        self.assertEqual(D.deal(9, seed=5), D.deal(9, seed=5))
        self.assertNotEqual(D.deal(9, seed=5), D.deal(9, seed=6))

    def test_the_board_can_never_fill_for_a_crew_that_finishes_its_jobs(self):
        """No window as long as an incident can live holds more reports
        than there are slots."""
        for rung in (1, 5, 10, 16, 25, 40):
            for seed in range(4):
                dealt = D.deal(rung, seed=seed)
                window = D.longest_life(dealt.level)
                times = [r.at for r in dealt.reports]
                for index, at in enumerate(times):
                    inside = [u for u in times[:index + 1] if u > at - window]
                    self.assertLessEqual(len(inside), D.SLOTS, (rung, seed))

    def test_reports_stay_on_the_map_and_off_the_stations(self):
        dealt = D.deal(12, seed=1)
        for r in dealt.reports:
            self.assertTrue(0.0 < r.x < 1.0 and 0.0 < r.y < 1.0)
            self.assertLessEqual(r.at, dealt.level.length)
            for sx, sy in D.STATIONS:
                self.assertGreater(math.hypot(r.x - sx, r.y - sy), 0.08)


class TheRules(unittest.TestCase):

    def test_a_crew_arrives_when_the_distance_says_and_clears_the_job(self):
        sx, sy = D.STATIONS[0]
        world = D.World(round_of([report(x=sx + 0.24, y=sy, growth=0.1)]))
        run(world, 0.1)
        self.assertTrue(world.send(0, 'incident', 0))
        run(world, 0.24 / D.CREW_SPEED - 0.2)
        self.assertFalse(world.units[0].working)
        run(world, 0.3)
        self.assertTrue(world.units[0].working)
        run(world, 4.0)
        self.assertEqual((world.saved, world.lost), (1, 0))
        self.assertTrue(world.over)
        self.assertTrue(world.units[0].idle)

    def test_an_incident_left_alone_burns_and_costs_the_loss(self):
        world = D.World(round_of([report(need=3.0, growth=0.5)]))
        run(world, (D.BURN - 3.0) / 0.5 + 0.3)
        self.assertEqual(world.lost, 1)
        self.assertAlmostEqual(world.damage, D.LOSS + 14.0, delta=0.5)
        self.assertTrue(world.over)

    def test_damage_is_the_seconds_real_incidents_wait(self):
        world = D.World(round_of([report(growth=0.01),
                                  report(x=0.3, growth=0.01, false=True)]))
        run(world, 5.0)
        self.assertAlmostEqual(world.damage, 5.0, delta=0.11)

    def test_a_false_alarm_ends_when_someone_gets_there(self):
        sx, sy = D.STATIONS[0]
        world = D.World(round_of([report(x=sx + 0.06, y=sy, false=True)]))
        run(world, 0.1)
        world.send(0, 'incident', 0)
        run(world, 1.0)
        self.assertEqual((world.saved, world.lost, world.false_alarms),
                         (0, 0, 1))
        self.assertEqual(world.damage, 0.0)

    def test_the_scout_confirms_but_does_not_clear(self):
        world = D.World(round_of([report(growth=0.05, factor=1.5)], rung=6))
        scout = next(u for u in world.units if u.scout)
        run(world, 0.1)
        incident = world.incident_in(0)
        self.assertAlmostEqual(incident.shown, incident.need * 1.5)
        world.send(scout.index, 'incident', 0)
        run(world, 3.0)
        self.assertTrue(incident.confirmed)
        self.assertAlmostEqual(incident.shown, incident.need)
        self.assertGreater(incident.need, 3.0)
        self.assertTrue(scout.idle)

    def test_a_crew_called_away_leaves_the_job_growing_again(self):
        sx, sy = D.STATIONS[0]
        world = D.World(round_of([report(x=sx + 0.05, y=sy, need=4.0,
                                         growth=0.3)]))
        run(world, 0.1)
        world.send(0, 'incident', 0)
        run(world, 2.0)
        incident = world.incident_in(0)
        shrinking = incident.need
        self.assertLess(shrinking, 4.0)
        world.send(0, 'station', 2)
        run(world, 1.0)
        self.assertGreater(incident.need, shrinking)

    def test_two_crews_clear_a_job_twice_as_fast(self):
        def seconds(crews):
            world = D.World(round_of([report(x=0.5, y=0.5, need=4.0,
                                             growth=0.0)]))
            for unit in world.units[:crews]:
                unit.x, unit.y = 0.5, 0.5
            run(world, 0.05)
            for unit in world.units[:crews]:
                world.send(unit.index, 'incident', 0)
            while not world.over:
                world.step(D.SIM_DT)
            return world.time

        self.assertAlmostEqual(seconds(1) / seconds(2), 2.0, delta=0.15)

    def test_an_order_to_an_empty_slot_is_refused(self):
        world = D.World(round_of([report(at=5.0)]))
        self.assertFalse(world.send(0, 'incident', 0))
        self.assertFalse(world.send(9, 'station', 0))

    def test_the_town_steps_the_same_however_it_is_driven(self):
        dealt = D.deal(8, seed=2)
        damages = []
        for chunk in (D.SIM_DT, 1 / 60., 0.25):
            world = D.World(dealt)
            while not world.over:
                world.step(chunk)
            damages.append(round(world.damage, 6))
        self.assertEqual(len(set(damages)), 1, damages)


class TheReference(unittest.TestCase):

    RUNGS = (1, 3, 5, 8, 12, 16, 20, 30)

    def test_it_plays_the_same_round_twice(self):
        dealt = D.deal(12, seed=3)
        self.assertEqual(D.reference_round(dealt).damage,
                         D.reference_round(dealt).damage)

    def test_dispatching_beats_not_dispatching_at_every_rung(self):
        for rung in self.RUNGS:
            for seed in range(3):
                dealt = D.deal(rung, seed=seed)
                self.assertLess(D.reference_round(dealt).damage * 1.5,
                                D.idle_round(dealt).damage, (rung, seed))

    def test_it_loses_nothing_while_the_town_is_quiet(self):
        for seed in range(4):
            self.assertEqual(D.reference_round(D.deal(1, seed=seed)).lost, 0)

    def test_and_cannot_save_everything_at_the_top(self):
        lost = sum(D.reference_round(D.deal(30, seed=seed)).lost
                   for seed in range(4))
        self.assertGreater(lost, 0)

    def test_par_is_its_damage_scaled_by_the_rung(self):
        dealt = D.deal(25, seed=1)
        self.assertLess(D.par(dealt), D.reference_round(dealt).damage)
        dealt = D.deal(2, seed=1)
        self.assertGreater(D.par(dealt), D.reference_round(dealt).damage)


def reference_port(task):
    """The reference's next order, as the port that carries it out."""
    from nwenv.dispatch import FIRST_SLOT, FIRST_STATION
    orders = D.reference_orders(task.world)
    if not orders:
        return None
    unit, kind, index = orders[0]
    if task.selected != unit:
        return unit
    return (FIRST_SLOT if kind == 'incident' else FIRST_STATION) + index


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def play(self, rung, policy, seed=0, **extra):
        from nwenv import catalog
        env = catalog.env_class('dispatch')(
            seed=seed, rung=rung, trials=1, adaptive=False, frame_hz=20,
            **extra)
        scalars, final = [], None
        try:
            for _step in range(6000):
                task = env.task
                port = policy(task) if task.phase == 'running' else None
                if port is None and extra.get('neutral_outcomes'):
                    port = type(env).ports      # the do-nothing port
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                # Read while the finished round is still on the board;
                # the run clears it when it moves on.
                if task.results and task.world is not None:
                    final = (task.results[-1], task.world.saved,
                             task.world.lost)
                if done:
                    break
        finally:
            env.close()
        return scalars, final

    def test_the_reference_s_orders_pass_a_quiet_town(self):
        scalars, _final = self.play(3, reference_port)
        self.assertEqual(scalars, [1.0])

    def test_and_a_busy_one_with_false_alarms(self):
        scalars, _final = self.play(9, reference_port)
        self.assertEqual(scalars, [1.0])

    def test_a_town_nobody_dispatched_is_a_paid_loss(self):
        scalars, _final = self.play(1, lambda task: None)
        self.assertEqual(scalars, [-1.0])

    def test_past_twenty_the_reference_s_orders_are_not_enough(self):
        scalars, _final = self.play(24, reference_port)
        self.assertEqual(scalars, [-1.0])

    def test_paid_per_event_each_incident_is_paid_exactly_once(self):
        from nwenv import catalog
        ports = catalog.env_class('dispatch').ports
        scalars, final = self.play(5, reference_port, neutral_outcomes=True,
                                   runtime_ports=ports + 1)
        (_rung, passed, _damage, _par), saved, lost = final
        self.assertEqual(scalars.count(1.0), saved + (1 if passed else 0))
        self.assertEqual(scalars.count(-1.0), lost + (0 if passed else 1))
        self.assertGreater(saved, 0)

    def test_it_refuses_the_think_clock_because_it_has_its_own(self):
        from nwenv import catalog
        with self.assertRaises(ValueError):
            catalog.env_class('dispatch')(seed=0, think_seconds=1.0)


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.dispatch import Dispatch
        close_overlays()
        self.task = Dispatch()
        self.task.rng = random.Random(3)
        self.task.total_trials = 1
        self.now = 10.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def tick(self, seconds):
        for _step in range(int(seconds * 20)):
            self.now += 0.05
            self.task.update(0.05)

    def test_a_click_on_a_crew_then_an_incident_sends_it(self):
        from pyglet.window import mouse
        self.task.start_run()
        self.tick(5.0)
        world = self.task.world
        incident = world.incident_in(0)
        self.assertIsNotNone(incident)
        x, y = self.task._unit_at(world.units[0])
        self.task.on_mouse_press(int(x), int(y), mouse.LEFT, 0)
        self.assertEqual(self.task.selected, 0)
        x, y = self.task._at(incident.x, incident.y)
        self.task.on_mouse_press(int(x), int(y), mouse.LEFT, 0)
        self.assertEqual(world.units[0].target, ('incident', incident.ident))
        self.assertIsNone(self.task.selected)
        self.task.on_draw()

    def test_keys_do_the_same(self):
        from pyglet.window import key
        self.task.start_run()
        self.tick(5.0)
        self.task.on_key_press(key._2, 0)
        self.assertEqual(self.task.selected, 1)
        self.task.on_key_press(key.L, 0)
        self.assertEqual(self.task.world.units[1].target, ('station', 2))

    def test_a_round_ends_in_a_verdict_and_a_tally(self):
        self.task.start_run()
        while self.task.phase == 'running':
            for unit, kind, index in D.reference_orders(self.task.world):
                self.task.world.send(unit, kind, index)
            self.tick(0.25)
        self.assertEqual(self.task.phase, 'judged')
        self.assertTrue(self.task.verdict_shown[0])
        self.now = self.task.feedback_until
        self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['passed'], 1)

    def test_nothing_is_painted_for_people_until_the_round_is_over(self):
        self.task.start_run()
        while self.task.phase == 'running':
            for unit, kind, index in D.reference_orders(self.task.world):
                self.task.world.send(unit, kind, index)
            self.tick(0.25)
            if self.task.phase == 'running':
                self.assertIsNone(self.task.verdict_shown)

    def test_the_map_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        for size in ((1824, 1368), (1280, 720), (2560, 1080)):
            state.window.set_size(*size)
            display.ensure_laid_out()
            _left, bottom, _size = self.task._map()
            self.assertGreaterEqual(
                bottom, above_the_band(from_bottom_edge(58)) - 0.5, size)

    def test_resizing_mid_round_keeps_the_town(self):
        self.task.start_run()
        self.tick(4.0)
        world = self.task.world
        state.window.set_size(1280, 720)
        display.ensure_laid_out()
        self.task.relayout()
        self.assertIs(self.task.world, world)
        self.task.on_draw()

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.dispatch import Dispatch
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Dispatch.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_decision_making(self):
        self.assertIn('dispatch', [t for t, _l in TASKS['decisions']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.dispatch import Dispatch
        launch_task('dispatch')
        self.assertIsNotNone(Dispatch.instance)
        Dispatch.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.dispatch_note({'DISPATCH_RUNG': 25})
        self.assertIn('false alarms', note)
        self.assertIn('better than the reference', note)


if __name__ == '__main__':
    unittest.main()
