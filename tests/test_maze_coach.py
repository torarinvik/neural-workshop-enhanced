#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Coach mode on the 2D Maze: the same shaping, a simpler task.

You Are Here walks in first person, so two of its four ports turn rather
than move.  The Maze steps in absolute directions, so *every* port that
does anything moves exactly one cell, and the shaping term is always
+1 or -1.  What is left to protect is the other half: the three ways a
step can refuse -- the edge of the grid, a wall, a locked door -- each
leave the walker where it was, and each must clear the label rather than
leave the last move's verdict up to be paid a second time.

That is the whole safety argument for the shaping.  A move that changes
nothing is owed nothing, so no closed loop of moves has positive return
and grinding on a wall pays exactly as much as standing still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import UI_IMPORT_ERROR

if UI_IMPORT_ERROR is None:
    from neural_workshop import state
    from neural_workshop.ui.maze import MazeTask
    from nwenv.frames import capture_rgba
    from nwenv.outcome import derive_public_outcome

#: The four steps, as the wrapper's action table orders them.
STEPS = ((0, -1), (0, 1), (-1, 0), (1, 0))


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class CoachPaintsConsequences(unittest.TestCase):

    def setUp(self):
        self.task = MazeTask()
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

    def test_every_real_step_pays_its_own_sign(self):
        """Walk until something moves, and check the sign each time.

        Distance is Manhattan, a step is one cell, so a move that lands
        closer is exactly +1 and one that lands farther exactly -1. There
        is no third case: a step either moves a cell or it does not move
        at all.
        """
        moved = 0
        for turn in range(60):
            before = self.task._distance_out()
            where = self.task.walker
            self.task.step(*STEPS[turn % len(STEPS)])
            if self.task.phase != 'walking':
                break
            if self.task.walker == where:
                continue
            now = self.task._distance_out()
            self.assertEqual(abs(now - before), 1,
                             'a step moved by other than one cell')
            self.assertEqual(self.scalar(), 1.0 if now < before else -1.0)
            moved += 1
            if moved >= 3:
                return
        self.assertTrue(moved, 'never moved; widen the walk')

    def test_a_refused_step_clears_the_verdict(self):
        """Walls, edges and locked doors all read as nothing.

        One direction pressed over and over is what makes this
        deterministic: the maze is bounded, so a straight line has to
        run into something. Cycling the four steps does not -- two open
        cells side by side shuttle a walker between them forever, and
        the refusal never comes.
        """
        for step in STEPS:
            reach = self.task.maze.width + self.task.maze.height
            for _ in range(reach):
                where = self.task.walker
                self.task.step(*step)
                if self.task.phase != 'walking':
                    self.skipTest('walked out before anything refused')
                if self.task.walker != where:
                    self.assertIsNotNone(self.scalar(),
                                         'a real move painted nothing')
                    continue
                self.assertIsNone(self.scalar(),
                                  'a refused step left a verdict on screen')
                return
        self.fail('nothing ever refused; widen the walk')


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class CoachOffIsThePlainGame(unittest.TestCase):

    def test_no_verdict_while_walking(self):
        task = MazeTask()
        task.start_run()
        try:
            self.assertFalse(task.coach)
            window = state.window
            for turn in range(40):
                task.step(*STEPS[turn % len(STEPS)])
                if task.phase != 'walking':
                    return          # solved: the solve verdict is allowed
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
