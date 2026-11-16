#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sign Painter: the strokes, the paint, the board, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, settle, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import hand as H
from neural_workshop import signpainter as M

RUNGS = (1, 4, 7, 10, 13, 16, 22, 35)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertLessEqual(len(rand), 1)

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 40)}
        self.assertFalse(g[1].colour or g[1].load or g[1].swing)
        self.assertTrue(g[4].colour)
        self.assertEqual([g[r].guide for r in (1, 7, 13)],
                         ['outline', 'corners', 'none'])
        self.assertTrue(g[7].load and g[10].swing and g[16].drag)
        self.assertFalse(g[7].swing or g[13].drag)
        self.assertLess(g[40].brush, g[1].brush)


class TheSign(unittest.TestCase):

    def test_a_word_is_laid_out_as_its_letters_strokes(self):
        strokes, _corners = M.lay_out('IT')
        self.assertEqual(len(strokes),
                         len(M.LETTERS['I']) + len(M.LETTERS['T']))
        for line in strokes:
            for (ax, ay), (bx, by) in zip(line, line[1:]):
                self.assertLessEqual(((ax - bx) ** 2 + (ay - by) ** 2)
                                     ** 0.5, M.STEP * 1.5)
            for x, y in line:
                self.assertTrue(0 <= x <= M.BOARD[0] and 0 <= y <= M.BOARD[1])

    def brush_on(self, run, point):
        q = run.see(*point)
        run.hand.to(q[0], q[1])

    def test_the_brush_paints_the_next_point_it_is_put_on(self):
        run = M.Run(M.deal(1, seed=1))
        self.brush_on(run, run.goal)
        run.press()
        run.step(1 / 60.0)
        self.assertEqual((run.stroke, run.point), (0, 1))

    def test_the_wrong_colour_smudges(self):
        sign = M.deal(4, seed=1)
        run = M.Run(sign)
        M.act(run, M.RED + (sign.colour + 1) % 4)
        self.brush_on(run, run.goal)
        run.press()
        run.step(1 / 60.0)
        self.assertEqual(run.smudges, 1)
        self.assertEqual(run.point, 0)

    def test_no_colour_taken_up_paints_nothing(self):
        run = M.Run(M.deal(4, seed=1))
        self.brush_on(run, run.goal)
        run.press()
        run.step(1 / 60.0)
        self.assertEqual((run.point, run.smudges), (0, 0))

    def test_wandering_off_a_started_stroke_smudges(self):
        run = M.Run(M.deal(1, seed=1))
        first = run.goal
        self.brush_on(run, first)
        run.press()
        run.step(1 / 60.0)
        run.release()
        self.brush_on(run, (first[0] + 1.5, first[1] + 1.5)
                      if first[1] < 1.5 else (first[0] + 1.5,
                                              first[1] - 1.5))
        run.press()
        run.step(1 / 60.0)
        self.assertEqual(run.smudges, 1)

    def test_a_dry_brush_has_to_be_dipped(self):
        run = M.Run(M.deal(7, seed=1))
        M.act(run, M.RED + max(0, run.sign.colour))
        run.paint = 0
        self.brush_on(run, run.goal)
        run.press()
        run.step(1 / 60.0)
        self.assertEqual(run.point, 0)
        run.release()
        M.act(run, M.DIP)
        self.assertEqual(run.paint, run.level.load)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('sign_painter', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('sign_painter', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('sign_painter', M), 0)


if __name__ == '__main__':
    unittest.main()
