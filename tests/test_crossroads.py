#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Crossroads: the lights, the traffic, the reference, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import crossroads as M


class TheLights(unittest.TestCase):

    def test_a_switch_runs_through_amber_and_all_red(self):
        light = M.Light('EW')
        light.changing = 0.0
        self.assertEqual(light.state('EW', 0.5), 'amber')
        self.assertEqual(light.state('NS', 0.5), 'red')
        self.assertEqual(light.state('EW', M.AMBER + 0.1), 'red')
        self.assertEqual(light.state('NS', M.AMBER + 0.1), 'red')

    def test_the_switch_completes_after_all_red(self):
        run = M.Run(M.deal(1, seed=1))
        first = run.lights[0].green
        M.act(run, 0)
        while run.t < M.AMBER + M.ALL_RED + 0.1:
            run.step(1 / 30.0)
        self.assertNotEqual(run.lights[0].green, first)

    def test_ports_past_the_junctions_do_nothing(self):
        run = M.Run(M.deal(1, seed=1))
        M.act(run, 3)
        self.assertTrue(all(l.changing is None for l in run.lights))

    def test_layouts_grow(self):
        self.assertEqual(len(M.deal(1, seed=1).junctions), 1)
        self.assertEqual(len(M.deal(7, seed=1).junctions), 2)
        self.assertEqual(len(M.deal(13, seed=1).junctions), 4)


class TheReference(unittest.TestCase):

    def test_the_reference_keeps_town_moving_and_idling_jams(self):
        for rung in (1, 10):
            for s in range(3):
                self.assertTrue(M.play(M.deal(rung, seed=s))[0], (rung, s))
            self.assertFalse(M.play(M.deal(rung, seed=1),
                                    lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('crossroads', 1, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('crossroads', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])


if __name__ == '__main__':
    unittest.main()
