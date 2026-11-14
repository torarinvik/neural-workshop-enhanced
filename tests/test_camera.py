#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Camera: the ladder, the photographs, the moves, and the screen.

The claims worth holding the task to are the ones its difficulty rests
on. The ladder must keep getting harder for ever and never stop being
dealable. Every photograph must have something in it to line up on.
And every rung, however tight, must be reachable through the agent's
ports by a policy that knows where to go — otherwise the top of the
ladder measures the port table rather than the player. The last is
tested by driving exactly such a policy to a paid match at rung 25,
where the eye has to land within about a millimetre.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import camera as C


class TheLadderHasNoTop(unittest.TestCase):

    def test_tolerances_shrink_at_every_rung_for_ever(self):
        last = C.grade(1)
        for rung in range(2, 400):
            level = C.grade(rung)
            self.assertLess(level.reach, last.reach, rung)
            self.assertLess(level.aim, last.aim, rung)
            last = level
        self.assertGreater(C.grade(399).reach, 0.0)

    def test_the_world_only_ever_grows_and_stays_drawable(self):
        last = C.grade(1)
        for rung in range(2, 200):
            level = C.grade(rung)
            self.assertGreaterEqual(level.objects, last.objects)
            self.assertGreaterEqual(level.field, last.field)
            # Every object is unique at first, so kinds grows with them;
            # what never rises is the share of objects that look unique.
            self.assertLessEqual(level.kinds / level.objects,
                                 last.kinds / last.objects + 1e-12, rung)
            self.assertLessEqual(level.objects, C.MOST_OBJECTS)
            self.assertLessEqual(level.field, C.LARGEST_FIELD)
            last = level

    def test_the_bottom_is_laughably_easy(self):
        level = C.grade(1)
        self.assertGreaterEqual(level.reach, 3.0)
        self.assertGreaterEqual(level.aim, 30.0)
        self.assertTrue(level.meter)
        self.assertEqual(level.lift, 0.0)

    def test_twenty_is_already_past_a_steady_hand(self):
        level = C.grade(20)
        self.assertLess(level.reach, 0.01)       # under a centimetre
        self.assertLess(level.aim, 0.2)
        self.assertFalse(level.meter)

    def test_a_rung_below_one_is_rung_one(self):
        self.assertEqual(C.grade(0), C.grade(1))
        self.assertEqual(C.grade(-5), C.grade(1))


class EveryDealIsFair(unittest.TestCase):

    RUNGS = (1, 2, 3, 5, 8, 12, 20, 30, 50, 100)

    def test_every_rung_deals(self):
        for rung in self.RUNGS:
            for seed in range(4):
                scene = C.deal(rung, seed=seed)
                self.assertEqual(scene.level.rung, rung)

    def test_a_deal_is_repeatable_from_its_seed(self):
        self.assertEqual(C.deal(9, seed=42), C.deal(9, seed=42))

    def test_every_photograph_has_things_to_line_up_on(self):
        for rung in self.RUNGS:
            for seed in range(4):
                scene = C.deal(rung, seed=seed)
                self.assertGreaterEqual(
                    C.anchors(scene.target, scene.things, scene.level.field),
                    scene.level.anchors, (rung, seed))

    def test_no_eye_starts_or_ends_inside_a_thing(self):
        for rung in self.RUNGS:
            scene = C.deal(rung, seed=rung)
            for pose in (scene.target, scene.start):
                for thing in scene.things:
                    self.assertGreater(
                        math.hypot(pose.x - thing.x, pose.z - thing.z),
                        thing.radius, (rung, thing))

    def test_nobody_starts_on_the_answer(self):
        for rung in self.RUNGS:
            for seed in range(4):
                scene = C.deal(rung, seed=seed)
                self.assertFalse(C.matches(scene.start, scene.target,
                                           scene.level), (rung, seed))

    def test_objects_get_harder_to_tell_apart(self):
        def kinds(rung):
            scene = C.deal(rung, seed=1)
            return len({(t.shape, t.colour) for t in scene.things
                        if not t.occluder})

        low = C.deal(3, seed=1)
        self.assertEqual(kinds(3), len([t for t in low.things
                                        if not t.occluder]))
        self.assertLessEqual(kinds(60), 3)


class PosesAndMoves(unittest.TestCase):

    LEVEL = C.grade(8)

    def test_yaw_nought_looks_down_minus_z(self):
        fwd = C.Pose(0, 1.6, 0, 0, 0).forward()
        self.assertAlmostEqual(fwd[2], -1.0)

    def test_forward_follows_the_heading_and_turning_left_is_positive(self):
        pose = C.Pose(0, 1.6, 0, 90, 0)
        ahead = C.moved(pose, 'forward', 1.0, self.LEVEL)
        self.assertAlmostEqual(ahead.x, -1.0)
        self.assertAlmostEqual(ahead.z, 0.0)
        self.assertAlmostEqual(
            C.moved(pose, 'turn_left', 1.0, self.LEVEL).yaw, 105.0)

    def test_walking_is_level_whatever_the_pitch(self):
        pose = C.Pose(0, 1.6, 0, 0, 60)
        self.assertAlmostEqual(
            C.moved(pose, 'forward', 1.0, self.LEVEL).y, 1.6)

    def test_rising_is_only_allowed_where_photos_leave_the_ground(self):
        pose = C.Pose(0, 1.6, 0, 0, 0)
        self.assertEqual(C.moved(pose, 'rise', 1.0, C.grade(1)).y, 1.6)
        self.assertGreater(C.moved(pose, 'rise', 1.0, self.LEVEL).y, 1.6)

    def test_the_eye_stays_inside_the_fence(self):
        pose = C.Pose(0, 1.6, 0, 0, 0)
        for _step in range(500):
            pose = C.moved(pose, 'forward', 1.0, self.LEVEL)
        self.assertLessEqual(abs(pose.z), self.LEVEL.field + 2.0)

    def test_errors_are_plain_metres_and_degrees(self):
        one = C.Pose(0, 1.6, 0, 0, 0)
        two = C.Pose(3, 1.6, 4, 90, 0)
        self.assertAlmostEqual(C.distance(one, two), 5.0)
        self.assertAlmostEqual(C.angle(one, two), 90.0)

    def test_the_meter_is_full_at_a_match_and_falls_off(self):
        level = C.grade(1)
        target = C.Pose(0, 1.6, 0, 0, 0)
        self.assertEqual(C.closeness(target, target, level), 1.0)
        far = C.Pose(30, 1.6, 0, 180, 0)
        self.assertLess(C.closeness(far, target, level), 0.3)


def homing(task):
    """A policy that knows the answer, through the boundary's ports.

    Turn to the photographer's heading, walk to their spot, tilt to
    their pitch and rise to their height, each with the largest step
    that does not overshoot, then submit. The finest step is half the
    rung's tolerance, so what is left over on each axis is under half of
    it and the sum is inside it.
    """
    from nwenv.camera import SUBMIT
    pose, target = task.pose, task.scene.target
    level = task.scene.level
    if C.matches(pose, target, level):
        return SUBMIT

    def pick(move_pos, move_neg, remaining, unit, finest_move):
        sizes = (1.0, 0.125, task._finest(finest_move))
        for index, size in enumerate(sizes):
            if size * unit <= abs(remaining) + 1e-12:
                move = move_pos if remaining > 0 else move_neg
                return C.MOVES.index(move) * 3 + index
        return None

    turn = (target.yaw - pose.yaw + 180.0) % 360.0 - 180.0
    port = pick('turn_left', 'turn_right', turn, C.STEP_DEGREES,
                'turn_left')
    if port is not None:
        return port
    rad = math.radians(pose.yaw)
    dx, dz = target.x - pose.x, target.z - pose.z
    ahead = -math.sin(rad) * dx - math.cos(rad) * dz
    aside = math.cos(rad) * dx - math.sin(rad) * dz
    for remaining, pos, neg in ((ahead, 'forward', 'back'),
                                (aside, 'right', 'left')):
        port = pick(pos, neg, remaining, C.STEP_METRES, pos)
        if port is not None:
            return port
    port = pick('look_up', 'look_down', target.pitch - pose.pitch,
                C.STEP_DEGREES, 'look_up')
    if port is not None:
        return port
    port = pick('rise', 'sink', target.y - pose.y, C.STEP_RISE, 'rise')
    if port is not None:
        return port
    return SUBMIT


@needs_ui
class TheBoundaryPaysAMatch(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, steps=3000):
        from nwenv import catalog
        env = catalog.env_class('camera')(seed=rung, rung=rung, trials=1,
                                          adaptive=False)
        scalars = []
        try:
            for _step in range(steps):
                if env.task.phase != 'searching':
                    port = None
                else:
                    port = homing(env.task)
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_rung_one(self):
        self.assertEqual(self.drive(1), [1.0])

    def test_rung_ten(self):
        self.assertEqual(self.drive(10), [1.0])

    def test_rung_twenty_five_is_reachable_through_the_ports(self):
        """About a millimetre and four hundredths of a degree."""
        self.assertLess(C.grade(25).reach, 0.0015)
        self.assertEqual(self.drive(25), [1.0])

    def test_saying_so_from_the_start_is_a_paid_miss(self):
        from nwenv import catalog
        from nwenv.camera import SUBMIT
        env = catalog.env_class('camera')(seed=0, rung=1, trials=1)
        scalars = []
        try:
            for _step in range(10):
                _obs, events, done = env.step(SUBMIT)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if scalars:
                    break
        finally:
            env.close()
        self.assertEqual(scalars, [-1.0])

    def test_it_is_turn_based_so_it_takes_the_think_clock(self):
        from nwenv import catalog
        cls = catalog.env_class('camera')
        self.assertFalse(cls.clocked)
        env = cls(seed=0, rung=1, trials=1, think_seconds=0.1)
        try:
            for _step in range(40):
                _obs, _events, done = env.step(None)
                if done:
                    break
            self.assertEqual(env.forfeits, 1)
            self.assertTrue(done)
        finally:
            env.close()


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.camera import CameraTask
        close_overlays()
        self.task = CameraTask()
        self.task.rng = random.Random(5)
        self.task.total_trials = 2
        self.task.adaptive = True
        self.now = 100.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def test_starting_deals_a_field_and_draws_both_views(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'searching')
        self.assertTrue(self.task.scene.things)
        self.task.on_draw()

    def test_held_keys_walk_and_shift_slows_them(self):
        self.task.start_run()
        before = self.task.pose
        self.task.held = {'forward'}
        self.task.update(0.1)
        walked = math.hypot(self.task.pose.x - before.x,
                            self.task.pose.z - before.z)
        self.task.slow = True
        before = self.task.pose
        self.task.update(0.1)
        crept = math.hypot(self.task.pose.x - before.x,
                           self.task.pose.z - before.z)
        self.assertGreater(walked, 0.2)
        self.assertLess(crept, walked * 0.2)

    def test_dragging_turns_the_view(self):
        self.task.start_run()
        yaw = self.task.pose.yaw
        self.task.on_mouse_drag(0, 0, -40, 0, 1, 0)
        self.assertNotAlmostEqual(self.task.pose.yaw, yaw)

    def test_a_match_climbs_and_a_miss_drops(self):
        self.task.start_rung = 4
        self.task.start_run()
        self.task.pose = self.task.scene.target
        self.task.submit()
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 5)
        self.now = self.task.feedback_until
        self.task.update(0)
        self.task.submit()                      # from the start: a miss
        self.assertFalse(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 4)

    def test_a_run_ends_with_a_tally(self):
        self.task.start_run()
        for _trial in range(2):
            self.task.pose = self.task.scene.target
            self.task.submit()
            self.now = self.task.feedback_until
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['matched'], 2)

    def test_the_views_stay_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        for size in ((1824, 1368), (1280, 720), (900, 900), (2560, 1080)):
            state.window.set_size(*size)
            display.ensure_laid_out()
            floor = above_the_band(from_bottom_edge(58))
            for rect in (self.task._view_rect(), self.task._photo_rect()):
                self.assertGreaterEqual(rect[1], floor - 0.5, size)

    def test_holding_t_shows_the_photograph_full_size(self):
        from pyglet.window import key
        self.task.start_run()
        self.task.on_key_press(key.T, 0)
        self.assertTrue(self.task.peek)
        self.task.on_draw()
        self.task.on_key_release(key.T, 0)
        self.assertFalse(self.task.peek)

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.camera import CameraTask
        self.task.start_run()
        self.task.close()
        self.assertIsNone(CameraTask.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_perception(self):
        self.assertIn('camera',
                      [task_id for task_id, _l in TASKS['perception']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.camera import CameraTask
        launch_task('camera')
        self.assertIsNotNone(CameraTask.instance)
        CameraTask.instance.close()

    def test_the_options_note_names_the_rung(self):
        note = taskoptions.camera_note({'CAMERA_RUNG': 20,
                                        'CAMERA_ADAPTIVE': True})
        self.assertIn('Rung 20', note)
        self.assertIn('mm', note)


if __name__ == '__main__':
    unittest.main()
