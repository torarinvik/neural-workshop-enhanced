#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Potter's Wheel: the clay, the wheel, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, settle, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import hand as H
from neural_workshop import potter as M

RUNGS = (1, 4, 7, 10, 13, 16, 22, 35)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertLessEqual(len(rand), 1)

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 40)}
        self.assertEqual((g[1].bands, g[4].bands, g[7].bands), (4, 6, 8))
        self.assertFalse(g[1].dry)
        self.assertTrue(g[4].dry and g[4].drag)
        self.assertEqual([g[r].ghost for r in (1, 7, 13)],
                         ['over', 'beside', 'brief'])
        self.assertTrue(g[10].wobble and not g[7].wobble)
        self.assertLess(g[40].near, g[1].near)


class TheClay(unittest.TestCase):

    def test_pressing_in_narrows_the_band_under_the_hand(self):
        run = M.Run(M.deal(1, seed=1))
        n = run.level.bands
        run.hand.to(M.AXIS + 0.3 * M.UNIT, M.band_y(n, 0))
        run.press()
        settle(run, 0.5)
        self.assertLess(run.r[0], M.START)
        self.assertEqual(run.r[2], M.START)
        run.release()
        was = run.r[0]
        settle(run, 0.5)
        self.assertEqual(run.r[0], was)

    def test_clay_pressed_to_nothing_collapses(self):
        run = M.Run(M.deal(1, seed=1))
        run.hand.to(M.AXIS, M.band_y(run.level.bands, 1))
        run.press()
        settle(run, 4.0)
        self.assertFalse(run.result[0])

    def test_dry_clay_will_not_move_until_it_is_wet(self):
        run = M.Run(M.deal(7, seed=1))
        run.wet = 0.0
        run.hand.to(M.AXIS + 0.3 * M.UNIT, M.band_y(run.level.bands, 0))
        run.press()
        settle(run, 0.3)
        self.assertEqual(run.r[0], M.START)
        run.release()
        M.act(run, M.WET)
        run.press()
        settle(run, 0.3)
        self.assertLess(run.r[0], M.START)

    def test_a_faster_wheel_shapes_faster(self):
        moved = []
        for taps in (0, 2):
            run = M.Run(M.deal(1, seed=1))
            for _k in range(taps):
                M.act(run, M.FASTER)
            run.hand.to(M.AXIS + 0.3 * M.UNIT, M.band_y(run.level.bands, 0))
            run.press()
            settle(run, 0.3)
            moved.append(M.START - run.r[0])
        self.assertGreater(moved[1], 2 * moved[0])

@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('potters_wheel', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('potters_wheel', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('potters_wheel', M), 0)


if __name__ == '__main__':
    unittest.main()
