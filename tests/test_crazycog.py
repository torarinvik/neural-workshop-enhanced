#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Crazy Cog: the snapping, the gearing, the motor, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, settle, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import crazycog as M

RUNGS = (1, 4, 7, 10, 13, 16, 20, 28)


def bare(rung=1, seed=1):
    """A dealt machine, its board empty."""
    return M.Run(M.deal(rung, seed=seed))


def open_board(rung=1):
    """A machine with the motor and the winch far apart."""
    return M.Run(M.deal(rung, seed=1)._replace(motor=(300.0, 350.0),
                                               winch=(800.0, 500.0),
                                               walls=(), fan=None))


def put(run, x, y, r):
    """Carry a cog of radius *r* from nowhere and drop it at (x, y)."""
    run.carry = r
    run.hand.down = True
    run.hand.to(x, y)
    run.release()


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertEqual(rand, [])

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 20, 40)}
        self.assertEqual(g[1].links, 1)
        self.assertTrue(g[4].links >= 3 and g[4].load < 0.5)
        self.assertGreater(g[7].load, 0.5)
        self.assertTrue(g[4].chains and not g[1].chains)
        self.assertTrue(g[7].layers == 1 and g[10].walls)
        self.assertEqual((g[10].layers, g[13].fan), (2, 0))
        self.assertEqual([M.grade(r).layers for r in (9, 10, 16, 24, 32)],
                         [1, 2, 3, 4, 5])
        self.assertEqual((g[16].fan, g[20].fan), (1, 2))
        self.assertLess(g[16].slack, g[13].slack)
        self.assertGreater(g[20].load, 3.0)          # past any two cogs
        self.assertGreaterEqual(g[40].load, g[20].load)


class TheCogs(unittest.TestCase):

    def test_a_drop_beside_a_cog_snaps_into_mesh(self):
        run = bare()
        mx, my = run.machine.motor
        put(run, mx + 2, my - 3, 30.0)                   # onto the axle
        self.assertEqual((run.cogs[0].x, run.cogs[0].y), (mx, my))
        put(run, mx + 30 + 40 + 9, my + 4, 40.0)         # a little off
        self.assertTrue(M.meshed(run.cogs[0], run.cogs[1]))

    def test_a_cog_on_top_of_another_goes_back_to_the_tray(self):
        run = bare()
        mx, my = run.machine.motor
        put(run, mx, my, 40.0)
        n = len([t for t in run.tray if t is not None])
        put(run, mx + 20, my + 10, 40.0)                 # overlaps, no mesh
        self.assertEqual(len(run.cogs), 1)
        self.assertEqual(len([t for t in run.tray if t is not None]), n + 1)

    def test_meshed_cogs_turn_opposite_ways_by_the_ratio(self):
        run = M.Run(M.deal(1, seed=1)._replace(motor=(300.0, 350.0),
                                               winch=(800.0, 500.0)))
        mx, my = run.machine.motor
        put(run, mx, my, 22.0)
        put(run, mx + 88, my, 66.0)
        a, b = run.cogs
        self.assertAlmostEqual(run.ratio[b], -run.ratio[a] * 22 / 66)
        self.assertLess(run.ratio[a] * run.ratio[b], 0)

    def test_a_ring_that_cannot_turn_jams(self):
        run = bare()
        mx, my = run.machine.motor
        put(run, mx, my, 30.0)
        put(run, mx + 60, my, 30.0)
        # a third cog meshing both closes a ring of three: it jams
        put(run, mx + 30, my + 52, 30.0)
        self.assertEqual(len(run.cogs), 3)
        self.assertTrue(run.jammed)

    def test_a_chain_turns_both_cogs_the_same_way(self):
        run = open_board(4)
        put(run, 300, 350, 22.0)
        put(run, 450, 350, 44.0 if 44.0 in M.SIZES else 40.0)
        a, b = run.cogs
        run.chain_from = a
        run.hand.to(b.x, b.y)
        run.press()
        run.release()
        self.assertEqual(run.chains, [(a, b)])
        self.assertAlmostEqual(run.ratio[b], run.ratio[a] * a.r / b.r)

    def test_a_cog_over_another_on_the_back_shares_its_axle(self):
        run = open_board(13)
        put(run, 300, 350, 22.0)
        put(run, 300 + 22 + 66, 350, 66.0)
        M.act(run, M.LAYER)
        self.assertEqual(run.layer, 1)
        put(run, 300 + 88 + 4, 350 - 3, 30.0)       # near its middle
        c = run.cogs[-1]
        self.assertEqual((c.x, c.y, c.z), (388.0, 350.0, 1))
        self.assertEqual(run.ratio[c], run.ratio[run.cogs[1]])

    def test_the_winch_is_on_the_deepest_plane(self):
        for rung in (10, 16, 24, 32):
            m = M.deal(rung, seed=2)
            self.assertEqual(m.winch_z, m.level.layers - 1, rung)
            self.assertEqual(max(c.z for c in m.plan), m.winch_z)
            self.assertTrue(M.play(m)[0], rung)

    def test_a_cog_on_the_winch_axle_but_the_wrong_plane_does_nothing(self):
        run = open_board(16)
        mc = run.machine
        put(run, mc.winch[0], mc.winch[1], 30.0)     # on the front plane
        self.assertIsNone(run.on(mc.winch, mc.winch_z))
        self.assertIsNone(run.gearing())

    def test_planes_go_round_both_ways(self):
        run = open_board(24)
        seen = []
        for _k in range(5):
            M.act(run, M.LAYER)
            seen.append(run.layer)
        self.assertEqual(seen, [1, 2, 3, 0, 1])
        M.act(run, M.NEARER)
        M.act(run, M.NEARER)
        self.assertEqual(run.layer, 3)

    def test_cogs_on_different_layers_pass_each_other(self):
        run = open_board(13)
        put(run, 500, 300, 52.0)
        M.act(run, M.LAYER)
        put(run, 530, 300, 52.0)                     # overlapping, behind
        self.assertEqual(len(run.cogs), 2)
        self.assertFalse(M.meshed(*run.cogs))

    def test_clearing_puts_every_cog_back(self):
        run = bare()
        mx, my = run.machine.motor
        put(run, mx, my, 30.0)
        M.act(run, M.CLEAR)
        self.assertEqual(run.cogs, [])
        self.assertEqual(sorted(t for t in run.tray if t is not None),
                         sorted(run.machine.tray + (30.0,)))


class TheMotor(unittest.TestCase):

    def test_gearing_down_lifts_what_gearing_up_cannot(self):
        self.assertEqual(M.lift_speed(0.5, 1.0), 0.0)    # stalls
        self.assertGreater(M.lift_speed(2.0, 1.0), 0.0)
        self.assertGreater(M.lift_speed(0.5, 0.2), M.lift_speed(2.0, 0.2))

    def test_the_wrong_way_leaves_the_bucket_on_the_floor(self):
        run = bare()
        mc = run.machine
        mx, my = mc.motor
        wx, wy = mc.winch
        put(run, mx, my, mc.plan[0].r)
        put(run, wx, wy, mc.plan[1].r)
        settle(run, 1.0)
        self.assertGreater(run.height, 0.0)              # direct: it lifts
        run2 = bare()
        put(run2, mx, my, mc.plan[0].r)
        # two cogs in a row from the motor turn its own way
        d = mc.plan[0].r + 30.0
        put(run2, mx, my + d, 30.0)
        put(run2, mx, my + d + 30.0 + 30.0, 30.0)
        settle(run2, 1.0)
        self.assertEqual(run2.height, 0.0)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('crazy_cog', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('crazy_cog', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('crazy_cog', M), 0)


if __name__ == '__main__':
    unittest.main()
