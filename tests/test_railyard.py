#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Rail Yard: the track, the rules, the dispatcher, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import railyard as M


class TheTrack(unittest.TestCase):

    def test_stations_double_with_depth(self):
        for rung in (1, 4, 10, 20):
            yard = M.deal(rung, seed=1)
            self.assertEqual(len(yard.layout.switch_nodes),
                             2 ** yard.level.depth - 1, rung)

    def test_every_train_has_a_route_home(self):
        yard = M.deal(13, seed=2)
        for plan in yard.plans:
            self.assertTrue(M.route(yard.layout, plan.portal, plan.station))

    def test_points_take_time_from_rung_seven(self):
        run = M.Run(M.deal(4, seed=1))
        run.throw(0)
        self.assertEqual(run.points[0].way, 1)
        run = M.Run(M.deal(7, seed=1))
        run.throw(0)
        self.assertEqual(run.points[0].way, 0)
        self.assertGreater(run.points[0].moving, 0)
        for _k in range(60):
            run.step(1 / 30.0)
        self.assertEqual(run.points[0].way, 1)


class TheDispatcher(unittest.TestCase):

    def test_the_reference_clears_every_rung(self):
        for rung in (1, 7, 13, 20, 26):
            ok = sum(M.play(M.deal(rung, seed=s))[0] for s in range(4))
            self.assertEqual(ok, 4, rung)

    def test_doing_nothing_fails(self):
        for rung in (4, 13):
            self.assertFalse(M.play(M.deal(rung, seed=3),
                                    lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('rail_yard', 2, pilot, seed=1, steps=5000),
                         [1.0])
        self.assertEqual(drive('rail_yard', 4, lambda t: None, seed=1,
                               steps=5000), [-1.0])


if __name__ == '__main__':
    unittest.main()
