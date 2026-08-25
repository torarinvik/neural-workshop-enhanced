#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Marble Maze screen, its 3D stage, and its pixel-only boundary.

The physics and the trays are tested next door in
:mod:`tests.test_marblemaze`, without a GL context. What is left for
here is everything the frame is responsible for: that the stage builds
at all, that it stops above the strip the boundary reads, that a port
changes what is drawn, that a verdict goes up only once the action
window has shut — and that a policy which knows the route can win a
tray through the same four ports a learner has, with the outcome still
read off the pixels.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import os
import random
import unittest

from uisupport import (UI_IMPORT_ERROR, close_overlays, geometry, key,
                       reset_window, needs_ui)

if UI_IMPORT_ERROR is None:
    from neural_workshop import marblemaze as M
    from neural_workshop import state
    from neural_workshop.ui import render3d
    from neural_workshop.ui.marblemaze import MarbleMaze
    from neural_workshop.ui.verdict import BAND_TOP, band_rows
    from nwenv.marblemaze import MarbleMazeEnv
    from nwenv.frames import capture_rgba, digest_rgba

#: Ports, in the order :class:`MarbleMazeEnv` declares them.
NORTH, SOUTH, WEST, EAST = 0, 1, 2, 3


def downhill(tray, x, y):
    """A unit vector towards the cup, read off the certified field."""
    step = tray.field.pitch * 2.0
    here = tray.field.at(x, y)
    if here is None:
        return None
    best, where = here, None
    for dx, dy in ((step, 0.), (-step, 0.), (0., step), (0., -step),
                   (step, step), (step, -step), (-step, step),
                   (-step, -step)):
        near = tray.field.at(x + dx, y + dy)
        if near is not None and near < best:
            best, where = near, (dx, dy)
    if where is None:
        return None
    length = math.hypot(*where)
    return (where[0] / length, where[1] / length)


def pilot(task, pace=0.11):
    """One port, steering the laggard marble down the certified route.

    A *velocity* controller, and it has to be: a port sets an
    acceleration and the marble carries momentum through it, so a
    policy that simply tips towards the cup and holds the tilt sends
    the marble straight past the cup and down whatever is beyond it.
    This one asks what velocity would be right and nudges the knob that
    closes the gap, which is roughly what a person does.
    """
    sim = task.sim
    if sim is None:
        return NORTH
    live = [m for m in sim.marbles if m.state == 'rolling']
    if not live:
        return NORTH
    tray = sim.tray
    target = max(live, key=lambda m: tray.field.at(m.x, m.y) or 0.0)
    heading = downhill(tray, target.x, target.y)
    if heading is None:
        return NORTH
    error_x = heading[0] * pace - target.vx
    error_y = heading[1] * pace - target.vy
    if abs(error_x) >= abs(error_y):
        return EAST if error_x > 0 else WEST
    return SOUTH if error_y > 0 else NORTH


def dealt(rung, trials=2, seed=1234, coach=False):
    """A task with a tray already dealt, from a *seeded* deal.

    ``MarbleMaze.__init__`` seeds its generator from the clock, which is
    right for a person and wrong for a test: every case below would
    otherwise be run against whatever tray came up. Measured before this
    existed, ``test_one_marble_and_a_coach_pays_per_action`` failed
    about one run in six — on the trays where the marble starts hard
    against the corner the test tilts towards, nothing moves, the
    potential never changes, and the coach has nothing to say. That is
    a true observation about that tray, not a defect in the coach.
    """
    task = MarbleMaze()
    task.rng = random.Random(seed)
    task.coach = coach
    task.start_rung = task.rung = rung
    task.total_trials = trials
    task.start_run()
    return task


def driven(env, moves, steps=6000):
    """Play *env* by *moves*, a callable handed the task each step."""
    scalars = []
    try:
        for _step in range(steps):
            _obs, events, done = env.step(moves(env.task))
            scalars += [e['scalar'] for e in events
                        if e.get('type') == 'outcome']
            if done or scalars:
                break
    finally:
        env.close()
    return scalars


@needs_ui
class TheStageIsReal3D(unittest.TestCase):

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_the_stage_builds(self):
        task = MarbleMaze()
        self.assertTrue(task.stage.ok,
                        'the 3D stage did not build: %s' % task.stage.trouble)

    def test_a_tray_becomes_meshes(self):
        task = dealt(6, trials=2)
        for name in ('body', 'frame', 'walls', 'pits', 'cup', 'collar'):
            self.assertIn(name, task.meshes, name)
        self.assertIsNotNone(task.marble_mesh)

    def test_the_marble_wears_its_baked_maps(self):
        """The maps bake out of an asset, so a checkout can lack them.

        Which is why this asserts the *pair* of facts rather than one:
        that they are found and uploaded when they are on disk, and
        that the stage is still usable when they are not. A missing
        texture has to give a plainer marble, not a black one — the
        shader keeps procedural mottling for exactly that case and
        ``marble_maps`` is the uniform that chooses.
        """
        from neural_workshop.paths import get_res_dir
        folder = os.path.join(get_res_dir(), 'marblemaze')
        names = ('marble_colour.png', 'marble_rough.png',
                 'marble_normal.png')
        here = [os.path.join(folder, name) for name in names]
        task = MarbleMaze()
        if all(os.path.exists(path) for path in here):
            self.assertTrue(task.textured, 'the baked maps did not upload')
        else:
            self.assertFalse(task.textured)
        task.close()
        # Either way the stage runs and a tray draws.
        task = dealt(2, trials=2)
        self.assertTrue(task.stage.ok)
        state.window.clear()
        task.on_draw()

    def test_a_stage_with_no_maps_still_draws(self):
        task = dealt(2, trials=2)
        task.stage._marble_tex = ()
        task.textured = False
        state.window.clear()
        task.on_draw()
        self.assertTrue(task.stage.ok)

    def test_no_rung_asks_for_more_holes_than_the_floor_will_cut(self):
        """The shader's hole array is a fixed size, and overflowing it
        is silent: the surplus holes stay solid board on screen while
        the physics goes on swallowing marbles into them. A guard on
        the *ladder* rather than on a sample, because which trays hit it
        would depend on the roll.
        """
        for grade in M.GRADES:
            self.assertLess(grade.holes + 1, render3d.MAX_HOLES, grade.name)


@needs_ui
class TheArtStopsAboveTheBand(unittest.TestCase):
    """Where the tray is allowed to be drawn, argued from the geometry.

    ``check_band.py`` sweeps what a run happens to paint, and for this
    task that is not enough on its own: the tray is lit pine, and a
    wooden midtone like ``(196, 128, 74)`` is a *negative verdict* as
    far as the outcome reader is concerned — red over 180 with the
    other two under 140. Whether any given frame lands there depends on
    the grain seed, the tilt and where the shadows fall, so a clean
    sweep proves the roll rather than the rule. The rule is that the
    viewport stops above the band, and that is what is asserted here.
    """

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_the_viewport_clears_the_band_at_every_window_size(self):
        task = MarbleMaze()
        for width, height in ((640, 480), (800, 600), (1024, 768),
                              (1280, 720), (1600, 900), (1920, 1080)):
            geometry.set_window_size(width, height)
            task.relayout()
            _left, bottom, _wide, _high = task._stage_rect()
            pixels_high = geometry.pixel_size()[1]
            fb_high = geometry.framebuffer_size(state.window)[1]
            scale = fb_high / float(pixels_high) if pixels_high else 1.0
            # band_rows counts image rows from the *top*, which is how
            # the frame arrives at the reader; a viewport's bottom edge
            # is a pyglet y, counted from the bottom. Turn one into the
            # other rather than comparing them as though they were the
            # same number.
            band_starts_at = band_rows(pixels_high)[0]
            ceiling = (pixels_high - band_starts_at) * scale
            self.assertGreaterEqual(
                bottom, ceiling,
                'at %dx%d the tray reaches into the band' % (width, height))

    def test_the_band_is_where_the_reader_thinks_it_is(self):
        """A sanity check on the arithmetic the test above leans on."""
        self.assertEqual(band_rows(1000), (int(1000 * BAND_TOP), 1000))


@needs_ui
class TheScreenAnswersItsPorts(unittest.TestCase):

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    @staticmethod
    def _frame():
        window = state.window
        window.switch_to()
        window.dispatch_events()
        window.clear()
        MarbleMaze.instance.on_draw()
        return digest_rgba(capture_rgba(window)[2])

    def test_a_port_changes_the_picture(self):
        task = dealt(3, trials=2)
        before = self._frame()
        for _ in range(12):
            task.tilt(M.TILT_EAST)
            task.update(1 / 60.)
        self.assertNotEqual(before, self._frame())

    def test_the_tray_tips_the_way_the_knob_says(self):
        task = dealt(1, trials=2)
        for _ in range(5):
            task.tilt(M.TILT_EAST)
        self.assertGreater(task.sim.roll, 0.0)
        for _ in range(20):
            task.tilt(M.TILT_WEST)
        self.assertLess(task.sim.roll, 0.0)

    def test_a_port_does_nothing_once_the_tray_has_settled(self):
        task = dealt(1, trials=2)
        task.phase = 'lost'
        held = task.sim.roll
        task.tilt(M.TILT_EAST)
        self.assertEqual(task.sim.roll, held)


@needs_ui
class TheVerdictIsPaintedWhenItShould(unittest.TestCase):

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def _rolling_task(self, rung=2):
        return dealt(rung, trials=2)

    def test_nothing_is_painted_while_the_tray_is_still_in_play(self):
        task = self._rolling_task()
        for _ in range(120):
            task.tilt(M.TILT_EAST)
            task.update(1 / 60.)
            if task.phase != 'rolling':
                break
        else:
            self.assertIsNone(task.verdict_shown)
            self.assertFalse(task.verdict.label.visible)

    def test_a_marble_down_a_hole_is_a_red(self):
        task = self._rolling_task()
        task.sim.marbles[0].state = 'lost'
        task.update(1 / 60.)
        self.assertEqual(task.phase, 'lost')
        self.assertIsNotNone(task.verdict_shown)
        self.assertFalse(task.verdict_shown[0])

    def test_every_marble_home_is_a_green(self):
        task = self._rolling_task()
        for marble in task.sim.marbles:
            marble.state = 'home'
        task.update(1 / 60.)
        self.assertEqual(task.phase, 'won')
        self.assertTrue(task.verdict_shown[0])

    def test_running_out_of_time_is_a_red(self):
        task = self._rolling_task()
        task.sim.elapsed = task.tray.seconds + 1.0
        task.update(1 / 60.)
        self.assertEqual(task.phase, 'lost')
        self.assertFalse(task.verdict_shown[0])

    def test_it_survives_a_resize_on_the_frame_it_goes_up(self):
        """A relayout drops the label unless the chrome puts it back.

        Which is exactly the frame it matters on: the first frame after
        a tray settles is when a window resize would otherwise take the
        verdict away, and an outcome that is only sometimes derivable is
        worse than one that never is.
        """
        task = self._rolling_task()
        for marble in task.sim.marbles:
            marble.state = 'home'
        task.update(1 / 60.)
        self.assertTrue(task.verdict.label.visible)
        task.relayout()
        self.assertTrue(task.verdict.label.visible)
        self.assertEqual(task.verdict_shown[0], True)

    def test_the_next_tray_takes_it_down(self):
        task = self._rolling_task()
        for marble in task.sim.marbles:
            marble.state = 'home'
        task.update(1 / 60.)
        self.assertTrue(task.verdict.label.visible)
        task._next_trial()
        self.assertIsNone(task.verdict_shown)
        self.assertFalse(task.verdict.label.visible)


@needs_ui
class TheCoachIsGatedOnTheMarbleCount(unittest.TestCase):
    """Shaping is only paid where the shaping rule actually holds.

    The potential is the summed quantised distance of every live
    marble, and the guarantee that one tick moves it by at most one step
    rests on a marble travelling at most 16.7mm in a tick against a 25mm
    quantum. That argument is about *a* marble; three of them can each
    cross a boundary in the same tick, and measured on the top rung they
    do. So the several-marble rungs are honestly sparse rather than
    dishonestly dense.
    """

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_one_marble_and_a_coach_pays_per_action(self):
        task = dealt(1, trials=2, coach=True)
        self.assertEqual(len(task.sim.marbles), 1)
        self.assertTrue(task.paying)
        seen = set()
        for _ in range(60 * 20):
            task.tilt(M.TILT_EAST)
            task.tilt(M.TILT_SOUTH)
            task.update(1 / 60.)
            if task.verdict_shown is not None and task.phase == 'rolling':
                seen.add(task.verdict_shown[0])
            if task.phase != 'rolling':
                break
        self.assertTrue(seen, 'the coach never said anything')

    def test_several_marbles_and_a_coach_says_nothing_per_action(self):
        task = dealt(5, trials=2, coach=True)
        self.assertGreater(len(task.sim.marbles), 1)
        self.assertFalse(task.paying)
        for _ in range(60 * 10):
            task.tilt(M.TILT_EAST)
            task.update(1 / 60.)
            if task.phase != 'rolling':
                break
            self.assertIsNone(task.verdict_shown)

    def test_a_person_never_gets_a_coach(self):
        """The human game stays pixel-identical, so old runs compare."""
        task = dealt(1, trials=2)
        self.assertFalse(task.coach)
        self.assertFalse(task.paying)

    def test_a_tick_that_changes_nothing_pays_nothing(self):
        """Otherwise standing still against a wall would farm it."""
        task = dealt(1, trials=2, coach=True)
        task.update(1 / 60.)          # level tray, marble at rest
        task.update(1 / 60.)
        self.assertIsNone(task.verdict_shown)


@needs_ui
class PlayedProperlyItIsPaid(unittest.TestCase):
    """A policy that knows the route, through the ports a learner has.

    Random play on this task is paid and paid red — it wanders a marble
    into a hole, or runs the clock out — so the *green* needs a policy
    that knows the answer. This is that test. The boundary is told
    nothing; it still reads the +1 off the pixels.
    """

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_a_steered_tray_is_paid_a_green(self):
        env = MarbleMazeEnv(seed=3, rung=1, trials=2, adaptive=False,
                            coach=False)
        self.assertEqual(driven(env, pilot), [1.0])

    def test_the_ports_are_the_four_a_knob_can_turn(self):
        self.assertEqual(MarbleMazeEnv.ports, 4)
        self.assertEqual(set(MarbleMazeEnv.action_table),
                         {M.TILT_NORTH, M.TILT_SOUTH,
                          M.TILT_WEST, M.TILT_EAST})

    def test_the_boundary_knows_this_one_moves_on_its_own(self):
        self.assertTrue(MarbleMazeEnv.clocked)


@needs_ui
class TheKeysAndTheHubAgree(unittest.TestCase):

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_held_arrows_keep_tipping_the_tray(self):
        task = dealt(1, trials=2)
        task.on_key_press(key.RIGHT, 0)
        for _ in range(10):
            task.update(1 / 60.)
        self.assertGreater(task.sim.roll, 0.0)
        held = task.sim.roll
        task.on_key_release(key.RIGHT, 0)
        for _ in range(10):
            task.update(1 / 60.)
        self.assertAlmostEqual(task.sim.roll, held, places=9)

    def test_l_levels_the_tray(self):
        task = dealt(1, trials=2)
        for _ in range(6):
            task.tilt(M.TILT_EAST)
        task.on_key_press(key.L, 0)
        self.assertEqual((task.sim.pitch, task.sim.roll), (0.0, 0.0))

    def test_the_hub_lists_it_and_can_launch_it(self):
        from neural_workshop.ui.taskhub import TASKS, launch_task
        listed = {task_id for rows in TASKS.values() for task_id, _ in rows}
        self.assertIn('marble_maze', listed)
        launch_task('marble_maze')
        self.assertIsNotNone(MarbleMaze.instance)

    def test_the_catalogue_and_the_hub_name_the_same_task(self):
        from nwenv import catalog
        row = [r for r in catalog.CATALOG if r.task_id == 'marble_maze']
        self.assertEqual(len(row), 1)
        self.assertIs(catalog.env_class('marble_maze'), MarbleMazeEnv)


if __name__ == '__main__':
    unittest.main()
