#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The 3D Maze paints a verdict the agent boundary can read.

The task is the first to use the shared path: it paints
:class:`neural_workshop.ui.verdict.VerdictLabel` when a maze is solved and
therefore needs no deriver and no verifier of its own. These tests check the
three things that path can get wrong -- a verdict that is not derivable, one
that appears before the run is over, and one that survives into the next maze.

The fourth is subtler and cost a debugging session: ``on_draw`` calls
``ensure_laid_out`` before it draws, and a relayout rebuilds the chrome batch.
A verdict set and then rebuilt away is only *sometimes* derivable, which is
worse than never, because it looks like it works.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import UI_IMPORT_ERROR

if UI_IMPORT_ERROR is None:
    from neural_workshop import state
    from neural_workshop.ui.youarehere import YouAreHere
    from neural_workshop.youarehere import route, route_from
    from nwenv.frames import capture_rgba
    from nwenv.outcome import derive_public_outcome


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class VerdictIsReadable(unittest.TestCase):

    def setUp(self):
        self.task = YouAreHere()
        self.task.start_run()

    def tearDown(self):
        self.task.close()

    def scalar(self):
        """What a third party holding only the frame would derive."""
        window = state.window
        window.switch_to()
        window.dispatch_events()
        self.task.on_draw()
        width, height, rgba = capture_rgba(window)
        outcome = derive_public_outcome(rgba, width, height, ['x'], 1)
        return None if outcome is None else outcome['scalar']

    def solve_optimally(self):
        for doing in route(self.task.maze):
            self.task.walk(doing)

    def solve_wastefully(self, wasted=40):
        for _ in range(wasted):
            self.task.walk('left')
        for doing in route_from(self.task.maze, self.task.pose,
                                self.task.held):
            self.task.walk(doing)

    def test_an_unsolved_maze_has_no_scalar_at_all(self):
        """None is not zero: nothing has been earned or lost yet."""
        self.assertIsNone(self.scalar())

    def test_nothing_is_painted_while_the_learner_can_still_act(self):
        """A verdict visible mid-maze would be an answer key."""
        for doing in route(self.task.maze)[:-1]:
            self.task.walk(doing)
            self.assertIsNone(self.scalar())

    def test_out_within_par_derives_positive(self):
        self.solve_optimally()
        self.assertEqual(self.task.phase, 'solved')
        self.assertLessEqual(self.task.steps, self.task.par)
        self.assertEqual(self.scalar(), 1.0)

    def test_out_over_par_derives_negative(self):
        self.solve_wastefully()
        self.assertEqual(self.task.phase, 'solved')
        self.assertGreater(self.task.steps, self.task.par)
        self.assertEqual(self.scalar(), -1.0)

    def test_the_next_maze_does_not_inherit_the_last_verdict(self):
        self.solve_optimally()
        self.assertEqual(self.scalar(), 1.0)
        self.task.trial = 0
        self.task._next_trial()
        self.assertIsNone(self.scalar())

    def test_a_verdict_survives_a_relayout(self):
        """The bug this test exists for: rebuilt chrome dropped the verdict."""
        self.solve_optimally()
        self.assertEqual(self.scalar(), 1.0)
        self.task.relayout()
        self.assertEqual(self.scalar(), 1.0)

    def test_the_band_stays_clear_of_the_task_s_own_art(self):
        """Coloured doors must not be read as verdicts."""
        for rung in range(1, self.task.clamped(99) + 1):
            with self.subTest(rung=rung):
                self.task.rung = rung
                self.task.trial = 0
                self.task._next_trial()
                self.assertIsNone(self.scalar())


if __name__ == '__main__':
    unittest.main()
