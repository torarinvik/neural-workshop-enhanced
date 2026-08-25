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

#: Ports, in the order :class:`MarbleMazeEnv` declares them. The names
#: are the marble's heading, which is what the knobs behind them are
#: named for too — see the note on ``TILT_NORTH`` in
#: :mod:`neural_workshop.marblemaze`.
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
    return NORTH if error_y > 0 else SOUTH


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

    def test_the_marble_turns_the_way_the_model_says(self):
        """Two conventions have to meet here and neither is obvious.

        The model keeps the marble's orientation as a quaternion in the
        tray's frame; the stage wants a matrix in the room's, which the
        tray meets at ``(x, z, -y)``. On top of that, pyglet's
        ``Quaternion.to_mat4`` hands back the transpose of what
        ``Mat4.from_rotation`` builds for the same turn, so the
        conjugate is what agrees with the rest of the stage. Get either
        wrong and the marble rolls sideways, or backwards, and nothing
        else in this file would notice.

        A single-axis roll is the case where the old accumulated-angle
        form was right, so it is the case that can be checked against
        it. Both axes, because a sign error shows in one and not the
        other.
        """
        from pyglet.math import Mat4, Vec3
        from neural_workshop.ui.marblemaze import _turned

        tray = M.deal(1, seed=17)._replace(walls=(), holes=())
        for vx, vy in ((0.30, 0.0), (0.0, 0.30)):
            sim = M.Simulation(tray)
            sim.marbles = [M.Marble(tray.width / 2.0, tray.depth / 2.0)]
            marble = sim.marbles[0]
            marble.vx, marble.vy = vx, vy
            marble.roll_with_travel()
            turned = 0.0
            for _ in range(4):
                was = (marble.x, marble.y)
                sim.step(1 / 60.0)
                turned += math.hypot(marble.x - was[0],
                                     marble.y - was[1]) / M.MARBLE_RADIUS
            self.assertGreater(turned, 1.0,
                               'it did not roll far enough to say')
            want = (Mat4.from_rotation(-turned if vy else 0.0,
                                       Vec3(1., 0., 0.))
                    @ Mat4.from_rotation(-turned if vx else 0.0,
                                         Vec3(0., 0., 1.)))
            # Distance over radius is the rolling angle only up to the
            # engine's regularised slip, so the tolerance is a couple
            # of degrees: what this pins is the axis and the sign —
            # the difference between rolling and rolling backwards, or
            # sideways — not the solver's last digit.
            for got, expected in zip(_turned(marble), want):
                self.assertAlmostEqual(got, expected, delta=0.06)

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

    def test_each_port_sends_the_marble_the_way_it_is_named(self):
        """Port order against the compass, end to end.

        The model's own suite pins :meth:`Simulation.tilt` against the
        compass, and this pins the table that sits in front of it, so
        the two cannot drift apart. Worth having as its own case:
        the ports are a tuple whose order is easy to reshuffle while
        every test that plays *through* them goes on passing, because
        a controller written against the table reshuffles with it.
        """
        compass = ((NORTH, 0.0, 1.0), (SOUTH, 0.0, -1.0),
                   (EAST, 1.0, 0.0), (WEST, -1.0, 0.0))
        for port, want_x, want_y in compass:
            tray = M.deal(1, seed=17)._replace(walls=(), holes=())
            sim = M.Simulation(tray)
            sim.marbles = [M.Marble(tray.width / 2.0, tray.depth / 2.0)]
            for _ in range(30):
                sim.tilt(MarbleMazeEnv.action_table[port])
                sim.step(1 / 60.0)
            marble = sim.marbles[0]
            went = (marble.vx * want_x + marble.vy * want_y) / marble.speed
            self.assertGreater(went, 0.99,
                               'port %d sent the marble (%+.3f, %+.3f)'
                               % (port, marble.vx, marble.vy))

    def test_the_boundary_knows_this_one_moves_on_its_own(self):
        self.assertTrue(MarbleMazeEnv.clocked)


@needs_ui
class ThePhysicsRunsOnTheWallClock(unittest.TestCase):
    """Each drawn frame shows exactly the real time that passed.

    The jitter this class guards against was never in the model: the
    task used to schedule its update as a 1/60 *interval* item while
    the redraw is another, and two interval items drift — stretches of
    play where one frame carried two physics steps and the next none,
    which on a gliding sphere reads as the speed pulsing. The cure is
    the every-tick schedule plus a sim stepped by the true dt, and
    these tests pin the properties that make that safe.
    """

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_nothing_is_scheduled_on_the_pyglet_clock(self):
        """Neither schedule form: both were tried, both were wrong.

        A 1/60 interval item drifts against the redraw's own interval
        item — frames alternate between two physics steps and none.
        An every-tick item stops pyglet's loop sleeping at all — the
        update ran forty thousand times a second, measured, a core
        gone. The stepping lives in ``on_draw`` instead.
        """
        import pyglet
        task = dealt(1, trials=2)
        clock = pyglet.clock.get_default()
        every_tick = [item.func for item in clock._schedule_items]
        self.assertNotIn(task.update, every_tick,
                         'an every-tick item busy-spins the event loop')
        intervals = [item.func for item in clock._schedule_interval_items]
        self.assertNotIn(task.update, intervals,
                         'an interval item drifts against the redraw')

    def test_the_draw_steps_a_persons_sim_and_only_a_persons(self):
        """One physics step per drawn frame under a live event loop —
        and none anywhere else. The else matters as much: the driver
        dispatches this same handler to capture frames, and a capture
        that nudged the sim by however long the harness took would put
        wall-clock noise inside the sealed boundary."""
        import pyglet
        task = dealt(1, trials=2)
        loop = pyglet.app.event_loop
        was = loop.is_running
        try:
            loop.is_running = False
            before = task.sim.elapsed
            task.on_draw()
            task.on_draw()
            self.assertEqual(task.sim.elapsed, before,
                             'a draw stepped the sim with no loop running')
            loop.is_running = True
            task.on_draw()          # first draw only starts the clock
            task.on_draw()
            self.assertGreater(task.sim.elapsed, before,
                               'a drawn frame did not step the sim')
        finally:
            loop.is_running = was

    def test_uneven_frames_lose_no_time(self):
        """The sim's clock advances by exactly the dt handed in.

        This is the property that replaces render interpolation: a
        fixed-step engine must blend between states because its clock
        moves in quanta, and ours need not because it does not.
        """
        task = dealt(1, trials=2)
        frames = (1 / 60., 1 / 47., 1 / 144., 1 / 60., 0.031, 1 / 90.)
        before = task.sim.elapsed
        for dt in frames:
            task.update(dt)
        self.assertAlmostEqual(task.sim.elapsed - before, sum(frames),
                               places=9)

    def test_a_long_frame_is_stepped_in_sixtieth_bites(self):
        """A hitch must not stretch the substeps past what the
        tunnelling test certifies: one substep of a 60Hz step moves a
        capped marble 4mm, under a wall's thickness, and a 0.05s frame
        handed over whole would triple that."""
        task = dealt(1, trials=2)
        bites = []
        stepped = task.sim.step
        task.sim.step = lambda dt: (bites.append(dt), stepped(dt))[1]
        task.update(0.05)
        self.assertGreater(len(bites), 1)
        for bite in bites:
            self.assertLessEqual(bite, 1 / 60. + 1e-12)
        self.assertAlmostEqual(sum(bites), 0.05, places=9)

    def test_the_held_tilt_rate_is_a_rate_of_time_not_of_calls(self):
        """Sixty nudges a second held, however often update is called.

        Every-tick scheduling runs once per clock tick, and another
        overlay's timer adds ticks — a naive nudge-per-call would tilt
        faster whenever something else was animating, which is the kind
        of wrong nobody ever traces.
        """
        fine = dealt(1, trials=2)
        fine.held.add(M.TILT_EAST)
        for _ in range(8):
            fine.update(1 / 240.)             # called four times as often
        coarse = dealt(1, trials=2)
        coarse.held.add(M.TILT_EAST)
        for _ in range(2):
            coarse.update(1 / 60.)            # the same span of held time
        self.assertAlmostEqual(fine.sim.roll, coarse.sim.roll, places=12)


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

    def test_every_arrow_sends_the_marble_where_it_points(self):
        """Up is away, down is towards, and the letters agree with them.

        The third layer of the same convention: the model names its
        knobs for the marble's heading and the ports pass that through,
        and this is the keyboard's end of it. Only ``RIGHT`` was
        covered before, which is the axis that was never wrong — north
        and south sat backwards against east and west for as long as
        nothing pressed ``UP`` and looked at the marble.
        """
        arrows = ((key.UP, key.W, 0.0, 1.0), (key.DOWN, key.S, 0.0, -1.0),
                  (key.RIGHT, key.D, 1.0, 0.0), (key.LEFT, key.A, -1.0, 0.0))
        tray = M.deal(1, seed=17)._replace(walls=(), holes=())
        for arrow, letter, want_x, want_y in arrows:
            knob = MarbleMaze._KEYS[arrow]
            self.assertEqual(MarbleMaze._KEYS[letter], knob,
                             'the letter and the arrow disagree')
            sim = M.Simulation(tray)
            sim.marbles = [M.Marble(tray.width / 2.0, tray.depth / 2.0)]
            for _ in range(30):
                sim.tilt(knob)
                sim.step(1 / 60.0)
            marble = sim.marbles[0]
            went = (marble.vx * want_x + marble.vy * want_y) / marble.speed
            self.assertGreater(went, 0.99,
                               'key %r sent the marble (%+.3f, %+.3f)'
                               % (knob, marble.vx, marble.vy))

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
