#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Coach mode is potential-based shaping, painted in pixels.

The claim being protected: with ``coach`` on, every *move* paints a verdict
the public deriver reads as the shaping term d - d' (green +1 closer, red -1
farther), and everything that is not a move -- a turn, a bump -- clears the
label and reads as nothing.  If turns paid, spinning would farm reward; if
bumps paid, walking into walls would.  And with ``coach`` off the task must
be pixel-for-pixel the game people play.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import UI_IMPORT_ERROR

if UI_IMPORT_ERROR is None:
    from neural_workshop import state
    from neural_workshop.ui.youarehere import YouAreHere
    from neural_workshop.youarehere import route
    from nwenv.frames import capture_rgba
    from nwenv.outcome import derive_public_outcome


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class CoachPaintsConsequences(unittest.TestCase):

    def setUp(self):
        self.task = YouAreHere()
        self.task.coach = True
        self.task.start_run()

    def tearDown(self):
        self.task.close()

    def scalar(self):
        window = state.window
        window.switch_to()
        window.dispatch_events()
        self.task.on_draw()
        width, height, rgba = capture_rgba(window)
        outcome = derive_public_outcome(rgba, width, height, ['x'], 1)
        return None if outcome is None else outcome['scalar']

    def first_move(self):
        """Walk the optimal route up to and including its first real move."""
        for doing in route(self.task.maze):
            cell_before = self.task.pose.cell
            self.task.walk(doing)
            if self.task.pose.cell != cell_before:
                return
            self.assertIsNone(self.scalar(),
                              'a turn on the optimal route painted a verdict')
        self.fail('the optimal route never moved')

    def test_a_closing_move_reads_plus_one(self):
        """The route's first move is toward the exit and must pay +1.

        Not guaranteed for *every* optimal move -- shortest paths detour
        around walls -- but the distance the whole route covers telescopes,
        so somewhere it closes; asserting on the first closing move keeps
        the test independent of maze layout.
        """
        before = self.task._distance_out()
        for doing in route(self.task.maze):
            cell_before = self.task.pose.cell
            self.task.walk(doing)
            if self.task.phase != 'walking':
                break
            if self.task.pose.cell == cell_before:
                continue
            now = self.task._distance_out()
            expected = 1.0 if now < before else -1.0
            self.assertEqual(self.scalar(), expected)
            before = now

    def test_a_turn_clears_the_verdict(self):
        self.first_move()
        self.assertIsNotNone(self.scalar())
        self.task.walk('left')
        self.assertIsNone(self.scalar(),
                          'a turn left the previous move\'s verdict up')

    def test_a_bump_clears_the_verdict(self):
        self.first_move()
        # Face and walk until something refuses to move; bumps must not pay.
        for _ in range(8):
            steps = self.task.steps
            self.task.walk('ahead')
            if self.task.phase != 'walking':
                return              # walked clean out; nothing to assert
            if self.task.steps == steps and self.task.bumps:
                self.assertIsNone(self.scalar(),
                                  'a bump left a verdict on screen')
                return
            self.task.walk('left')
        self.fail('never bumped; widen the walk')


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class CoachOffIsThePlainGame(unittest.TestCase):

    def test_no_verdict_before_solving(self):
        task = YouAreHere()
        task.start_run()
        try:
            self.assertFalse(task.coach)
            window = state.window
            for doing in route(task.maze)[:-1]:
                task.walk(doing)
                window.switch_to()
                window.dispatch_events()
                task.on_draw()
                width, height, rgba = capture_rgba(window)
                outcome = derive_public_outcome(rgba, width, height, ['x'], 1)
                self.assertIsNone(outcome,
                                  'coach off, yet a verdict mid-maze')
        finally:
            task.close()


if __name__ == '__main__':
    unittest.main()
