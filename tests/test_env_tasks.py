#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The tasks wrapped on TaskEnv, and the one thing that has to be true of each.

A wrapper is worth very little on its own. What matters is that a run
through it produces outcomes a third party could check, so each of these
plays its task and requires that it was actually paid — and that the scalar
it was paid came off the pixels rather than out of the task's own state.

Sokoban gets more than that, because wrapping it turned up something the
task had been quietly doing to people all along: a box pushed into a pocket
can never come out, and until now the screen said nothing. A learner could
sit in a position it could not win and could not leave, and be paid nothing
for the rest of the episode. The deadlock tests are about that.

These bind shared-memory segments, so they run one environment at a time.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import UI_IMPORT_ERROR, close_overlays, key, reset_window

if UI_IMPORT_ERROR is None:
    from neural_workshop import sokoban as S
    from neural_workshop import state
    from neural_workshop.ui.sokoban import SokobanTask
    from nwenv.crossedwires import CrossedWiresEnv
    from nwenv.frames import capture_rgba
    from nwenv.inthedark import InTheDarkEnv
    from nwenv.maze import MazeEnv
    from nwenv.outcome import derive_public_outcome
    from nwenv.removals import RemovalsEnv
    from nwenv.sokoban import SokobanEnv

needs_ui = unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))

#: A level that can be killed, and a walk that kills it. Found by
#: tests/find_dead_seed.py rather than guessed at.
LEVEL_SEED, WALK_SEED = 4, 0


def played(env, steps, seed=0):
    """Play *env* at random and collect what it paid."""
    rng = random.Random(seed)
    scalars = []
    try:
        for _step in range(steps):
            _obs, events, done = env.step(rng.randrange(env.n_actions))
            scalars += [e['scalar'] for e in events
                        if e.get('type') == 'outcome']
            if done:
                break
    finally:
        env.close()
    return scalars


@needs_ui
class EachWrappedTaskPays(unittest.TestCase):
    """A run through the boundary produces outcomes, and they are +1/-1."""

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def check(self, env, steps):
        scalars = played(env, steps)
        self.assertTrue(scalars, 'nothing was ever paid')
        for scalar in scalars:
            self.assertIn(scalar, (1.0, -1.0))

    def test_removals_pays(self):
        self.check(RemovalsEnv(seed=0, rung=1, trials=2, seconds=0.2), 2000)

    def test_in_the_dark_pays(self):
        self.check(InTheDarkEnv(seed=0, rung=1, trials=2, seconds=0.2), 2000)

    def test_crossed_wires_pays(self):
        self.check(CrossedWiresEnv(seed=0, rung=1, rounds=3), 700)

    def test_sokoban_pays(self):
        self.check(SokobanEnv(seed=0, rung=1, trials=3), 2500)

    def test_a_turn_based_task_is_not_ticked_on_a_clock(self):
        """Ticking a task with no clock would be inventing one."""
        self.assertFalse(CrossedWiresEnv.clocked)
        self.assertFalse(MazeEnv.clocked)
        self.assertFalse(SokobanEnv.clocked)
        self.assertTrue(RemovalsEnv.clocked)
        self.assertTrue(InTheDarkEnv.clocked)

    def test_the_ports_are_the_ones_the_task_has(self):
        self.assertEqual(MazeEnv.ports, 4)
        self.assertEqual(SokobanEnv.ports, 4)
        self.assertEqual(RemovalsEnv.ports, 5)
        self.assertEqual(InTheDarkEnv.ports, 5)
        self.assertEqual(CrossedWiresEnv.ports, 8)


@needs_ui
class SokobanSaysWhenALevelIsDead(unittest.TestCase):
    """The thing wrapping it turned up, which was a bug for people too."""

    def setUp(self):
        # Hermetic, like every other UI class here: an overlay left
        # registered by an earlier test draws its batch over this
        # one's, and a stale verdict on top of a fresh level is
        # exactly the failure these tests are about.
        close_overlays()
        self.task = SokobanTask()
        self.task.total_trials = 3
        self.task.adaptive = False
        self.task.start_rung = self.task.rung = 3
        # Pinned, because the task deals from an unseeded generator and
        # only some levels can be pushed into a pocket at all. Under
        # this pair the walk below kills it in fourteen actions; left
        # random, half these tests would pass on the luck of the deal.
        self.task.rng.seed(LEVEL_SEED)
        self.task.start_run()

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def scalar(self):
        """What a third party holding only the frame would derive."""
        window = state.window
        window.switch_to()
        window.dispatch_events()
        self.task.on_draw()
        width, height, rgba = capture_rgba(window)
        outcome = derive_public_outcome(rgba, width, height, ['x'], 1)
        return None if outcome is None else outcome['scalar']

    def kill_it(self):
        """Push at random until the level is provably lost."""
        rng = random.Random(WALK_SEED)
        for _try in range(4000):
            if self.task.phase == 'lost':
                return True
            if self.task.phase != 'pushing':
                return False
            self.task.step(*((0, -1), (0, 1), (-1, 0),
                             (1, 0))[rng.randrange(4)])
        return False

    def test_a_fresh_level_is_not_called_dead(self):
        level = self.task.level
        self.assertFalse(S.deadlocked(level.width, level.height, level.walls,
                                      level.goals, level.boxes))
        self.assertEqual(self.task.phase, 'pushing')

    def test_a_level_pushed_into_a_pocket_says_so(self):
        self.assertTrue(self.kill_it(), 'no seed reached a dead position')
        self.assertEqual(self.task.phase, 'lost')
        level = self.task.level
        self.assertTrue(S.deadlocked(level.width, level.height, level.walls,
                                     level.goals, self.task.boxes))

    def test_a_dead_level_reads_as_a_loss_off_the_pixels(self):
        """Which is the whole point: the scalar comes from the frame."""
        self.assertTrue(self.kill_it())
        self.assertEqual(self.scalar(), -1.0)

    def test_a_dead_level_is_not_counted_as_solved(self):
        self.assertTrue(self.kill_it())
        tally = self.task.score()
        self.assertEqual(tally['solved'], 0)
        self.assertEqual(tally['lost'], 1)

    def test_space_deals_on_from_a_dead_level(self):
        """Otherwise it is an absorbing state, which is what it was."""
        self.assertTrue(self.kill_it())
        was = self.task.level
        self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.phase, 'pushing')
        self.assertIsNot(self.task.level, was)

    def test_the_verdict_goes_down_when_the_next_level_opens(self):
        self.assertTrue(self.kill_it())
        self.assertEqual(self.scalar(), -1.0)
        self.task.on_key_press(key.SPACE, 0)
        self.assertIsNone(self.scalar())


if __name__ == '__main__':
    unittest.main()
