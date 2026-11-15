#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Kitchen: the stations, the tickets, the cook, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import kitchen as M


def walk(run, kind, index=0):
    run.send(run.station(kind, index).port)
    while run.target is not None:
        run.step(1 / 30.0)


class TheStations(unittest.TestCase):

    def test_crate_board_stove_plate_pass(self):
        shift = M.deal(1, seed=1)
        run = M.Run(shift)
        while not run.open:
            run.step(0.1)
        food = shift.tickets[0].parts[0][0]
        crate = [s for s in shift.stations
                 if s.kind == M.CRATE and s.food == food][0]
        run.send(crate.port)
        while run.target is not None:
            run.step(1 / 30.0)
        self.assertEqual(run.held, (food, M.RAW))
        walk(run, M.BOARD)
        self.assertIsNone(run.held)
        for _k in range(int(M.CHOP * 30) + 2):
            run.step(1 / 30.0)
        walk(run, M.BOARD)
        self.assertEqual(run.held, (food, M.CHOPPED))
        walk(run, M.STOVE)
        for _k in range(int(M.COOK * 30) + 2):
            run.step(1 / 30.0)
        walk(run, M.STOVE)
        self.assertEqual(run.held, (food, M.COOKED))
        walk(run, M.PLATE)
        walk(run, M.PLATE)
        walk(run, M.PASS)
        self.assertEqual(run.served, [0])

    def test_a_pan_left_too_long_burns(self):
        run = M.Run(M.deal(10, seed=1))
        run.stoves[0] = M.Pan('tomato', 0.0)
        run.t = M.COOK + run.level.hold + 0.1
        self.assertEqual(run.pan_stage(0), M.BURNT)

    def test_a_wrong_plate_is_not_served(self):
        run = M.Run(M.deal(1, seed=1))
        while not run.open:
            run.step(0.1)
        run.held = ('plate', (('fish', M.BURNT),))
        walk(run, M.PASS)
        self.assertEqual(run.served, [])


class TheCook(unittest.TestCase):

    def test_the_reference_serves_every_shift(self):
        for rung in (1, 4, 7, 13, 16):
            for s in range(2):
                self.assertTrue(M.play(M.deal(rung, seed=s))[0], (rung, s))

    def test_doing_nothing_fails(self):
        self.assertFalse(M.play(M.deal(1, seed=1), lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('kitchen', 1, pilot, seed=1, steps=6000),
                         [1.0])
        self.assertEqual(drive('kitchen', 1, lambda t: None, seed=1,
                               steps=6000), [-1.0])


if __name__ == '__main__':
    unittest.main()
