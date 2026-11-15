#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Escort: the temple, the walkers, the levers, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import escort as M


def one(kind, at=5, start=False, lever=0, **jet):
    path = [(c, 3) for c in range(12)]
    dev = M.Device(kind, 0, at, None if kind == M.JET else lever, **jet)
    temple = M.Temple(M.grade(1), [path], [dev],
                      [[0]] if kind != M.JET else [], [start], [0.0], [[]],
                      60.0)
    return M.Run(temple)


class TheTemple(unittest.TestCase):

    def test_a_shut_door_holds_the_walker(self):
        run = one(M.DOOR)
        for _k in range(30 * 8):
            run.step(1 / 30.0)
        self.assertEqual(run.state[0], M.WAITING)
        self.assertAlmostEqual(run.pos[0], 4.5)
        run.pull(0)
        for _k in range(30 * 8):
            run.step(1 / 30.0)
        self.assertEqual(run.result[0], True)

    def test_a_missing_bridge_is_a_fall(self):
        run = one(M.BRIDGE)
        while run.result is None:
            run.step(1 / 30.0)
        self.assertEqual(run.state[0], M.FELL)
        run = one(M.BRIDGE, start=True)
        while run.result is None:
            run.step(1 / 30.0)
        self.assertTrue(run.result[0])

    def test_a_bridge_slides_and_carries_no_one_meanwhile(self):
        run = one(M.BRIDGE, start=True)
        run.pull(0)
        run.step(M.SLIDE / 2)
        self.assertFalse(run.is_open(0))

    def test_jets_keep_their_own_clock(self):
        run = one(M.JET, period=3.0, duty=0.5, phase=0.0)
        self.assertTrue(run.jet_on(0, 0.5))
        self.assertFalse(run.jet_on(0, 2.0))

    def test_coupled_levers_from_rung_ten(self):
        self.assertFalse(M.grade(9).coupled)
        temple = M.deal(10, seed=1)
        self.assertTrue(any(len(g) > 1 for g in temple.levers))


class TheEscort(unittest.TestCase):

    def test_every_dealt_temple_is_crossable(self):
        for rung in (1, 4, 10, 13, 16, 20):
            for s in range(3):
                self.assertTrue(M.play(M.deal(rung, seed=s))[0], (rung, s))

    def test_doing_nothing_fails(self):
        for rung in (1, 10):
            self.assertFalse(M.play(M.deal(rung, seed=2),
                                    lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('escort', 4, pilot, seed=1, steps=4000),
                         [1.0])
        self.assertEqual(drive('escort', 4, lambda t: None, seed=1,
                               steps=9000), [-1.0])


if __name__ == '__main__':
    unittest.main()
