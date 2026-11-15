#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Firebreak: the land, the fire, the crew, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import firebreak as M


class TheFire(unittest.TestCase):

    def test_wind_speeds_the_fire_downwind(self):
        blaze = M.Blaze(M.deal(4, seed=1))
        wx, wy = blaze.wind()
        if abs(wx) >= abs(wy):
            dc, dr = (1 if wx > 0 else -1), 0
        else:
            dc, dr = 0, (1 if wy > 0 else -1)
        c, r = M.COLS // 2, M.ROWS // 2
        here = M.cell(c, r)
        ahead, behind = M.cell(c + dc, r + dr), M.cell(c - dc, r - dr)
        blaze.terrain[ahead] = blaze.terrain[behind] = M.GRASS
        rough = blaze.land.rough
        self.assertLess(blaze.cross_time(here, ahead, 1.0) / rough[ahead],
                        blaze.cross_time(here, behind, 1.0) / rough[behind])

    def test_a_break_does_not_burn(self):
        land = M.deal(1, seed=2)
        blaze = M.Blaze(land)
        for _k in range(30 * 20):
            blaze.step(1 / 30.0)
            if blaze.result:
                break
        for i, t in enumerate(blaze.terrain):
            if t in (M.WATER, M.ROCK, M.BREAK):
                self.assertEqual(blaze.state[i], M.UNBURNT)

    def test_digging_spends_a_shovel_and_rests_the_crew(self):
        blaze = M.Blaze(M.deal(1, seed=3))
        for i, t in enumerate(blaze.terrain):
            if t in (M.FOREST, M.GRASS) and blaze.state[i] == M.UNBURNT:
                blaze.put(*M.colrow(i))
                break
        shovels = blaze.shovels
        self.assertTrue(blaze.dig())
        self.assertEqual(blaze.shovels, shovels - 1)
        self.assertEqual(blaze.terrain[M.cell(*blaze.cursor)], M.BREAK)
        blaze.move(1, 0)
        self.assertFalse(blaze.can_dig())


class TheCrew(unittest.TestCase):

    def test_the_reference_saves_the_town(self):
        for rung in (1, 7, 13):
            ok = sum(M.play(M.deal(rung, seed=s))[1] for s in range(4))
            self.assertGreaterEqual(ok, 3, rung)

    def test_doing_nothing_loses_the_town(self):
        for rung in (1, 10):
            self.assertFalse(M.play(M.deal(rung, seed=4),
                                    lambda blaze: [])[1])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.blaze)
        self.assertEqual(drive('firebreak', 1, pilot, seed=1, steps=4000),
                         [1.0])
        self.assertEqual(drive('firebreak', 1, lambda t: None, seed=1,
                               steps=4000), [-1.0])


if __name__ == '__main__':
    unittest.main()
