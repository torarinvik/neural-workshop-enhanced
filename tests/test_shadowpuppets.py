#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shadow Puppets: the figure, the shadow, the turning, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, settle, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import hand as H
from neural_workshop import shadowpuppets as M

RUNGS = (1, 4, 7, 10, 13, 16, 22, 35)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertLessEqual(len(rand), 1)

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 20, 40)}
        self.assertTrue(g[1].flat and not g[4].flat)
        self.assertEqual([g[r].shown for r in (1, 7, 13)],
                         ['wall', 'card', 'named'])
        self.assertEqual([g[r].shadows for r in (1, 10, 20)], [1, 2, 3])
        self.assertTrue(g[7].tone and not g[10].tone)
        self.assertTrue(g[16].hidden and not g[13].hidden)
        self.assertLess(g[40].near, g[20].near)


class TheFigure(unittest.TestCase):

    def test_a_cube_sits_twenty_four_ways(self):
        self.assertEqual(len(M.SQUARE), 24)
        self.assertAlmostEqual(M.apart(M.EYE, M.turn(1, 90.0)), 90.0)
        self.assertAlmostEqual(M.apart(M.turn(0, 30.0), M.turn(0, 50.0)),
                               20.0)

    def test_from_the_front_and_the_side_it_is_its_two_shapes(self):
        cubes = M.blocks('T', 'L')
        self.assertEqual(M.shadow(cubes, M.EYE), M.cells('T'))
        side = M.shadow(cubes, M.turn(1, 90.0))
        mirror = frozenset((-x, y) for x, y in M.cells('L'))
        self.assertIn(side, (M.cells('L'), mirror))

    def test_a_dealt_figure_starts_well_away_from_every_shadow(self):
        for rung in (1, 7, 13, 25):
            for s in range(4):
                run = M.Run(M.deal(rung, seed=s))
                self.assertGreater(run.off(), 50.0)
                for fit in run.fits:
                    self.assertTrue(fit)

    def test_a_named_shadow_is_one_of_the_figures_own_shapes(self):
        puppet = M.deal(13, seed=1)
        for name, want in zip(puppet.names, puppet.wanted):
            self.assertIn(name, (puppet.front, puppet.side))
            self.assertEqual(want, M.cells(name))


class TheTurning(unittest.TestCase):

    def test_a_drag_turns_the_figure_and_a_bare_move_does_not(self):
        run = M.Run(M.deal(1, seed=1))
        start = run.m
        run.hand.to(520.0, 320.0)
        run.step(1 / 60.0)
        self.assertEqual(run.m, start)
        run.press()
        run.hand.to(540.0, 320.0)
        run.step(1 / 60.0)
        self.assertAlmostEqual(M.apart(run.m, start), 20 * M.GAIN, places=3)

    def test_the_keys_roll_it(self):
        run = M.Run(M.deal(1, seed=1))
        start = run.m
        M.act(run, M.ROLL_LEFT)
        self.assertAlmostEqual(M.apart(run.m, start), M.ROLL, places=3)
        M.act(run, M.ROLL_RIGHT)
        self.assertAlmostEqual(M.apart(run.m, start), 0.0, places=3)

    def test_the_shadow_has_to_be_held(self):
        run = M.Run(M.deal(1, seed=1))
        run.m = run.fits[0][0]
        settle(run, M.STAY - 0.1)
        self.assertIsNone(run.result)
        settle(run, 0.2)
        self.assertTrue(run.result[0])

    def test_the_tone_rises_as_the_shadow_nears(self):
        run = M.Run(M.deal(1, seed=1))
        settle(run, 1.0)
        far = [n.freq for n in run.notes if n.voice == M.WARM][-1]
        run.m = M.mul(M.turn(1, 25.0), run.fits[0][0])
        settle(run, 0.5)
        near = [n.freq for n in run.notes if n.voice == M.WARM][-1]
        self.assertGreater(near, far)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('shadow_puppets', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('shadow_puppets', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('shadow_puppets', M), 0)


if __name__ == '__main__':
    unittest.main()
