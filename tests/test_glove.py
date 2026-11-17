#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Glove: the reference, the shortcuts, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import glove as M


def fixed(port):
    """A player that sends one port every step."""
    return lambda run: [port]


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for rung in (1, 2, 4, 7, 10, 13, 30):
            for s in range(2):
                dealt = M.deal(rung, seed=s)
                self.assertTrue(M.play(dealt)[0], (rung, s))
                self.assertFalse(M.play(dealt, lambda run: [])[0],
                                 ('idle', rung, s))
                draw = random.Random(s)
                self.assertFalse(M.play(dealt, lambda run: [
                    draw.randrange(M.PORTS)])[0], ('random', rung, s))
                for port in range(M.PORTS):
                    self.assertFalse(M.play(dealt, fixed(port))[0],
                                     ('fixed', port, rung, s))

    def test_the_grade_grows_without_end(self):
        self.assertEqual(M.grade(500).rung, 500)
        self.assertEqual(M.grade(0), M.grade(1))

    def test_in_every_view_the_controls_move_the_picture_their_way(self):
        for view in range(len(M.VIEWS)):
            for at in ((0.0, 1.2), (0.7, 0.5), (-0.8, 1.9)):
                right, up = M.axes(view, at)
                p0 = M._project(view, (at[0], at[1], 0.0))
                pr = M._project(view, (at[0] + 0.05 * right[0],
                                       at[1] + 0.05 * right[1], 0.0))
                pu = M._project(view, (at[0] + 0.05 * up[0],
                                       at[1] + 0.05 * up[1], 0.0))
                self.assertGreater(pr[0], p0[0], (view, at))
                self.assertGreater(pu[1], p0[1], (view, at))

    def test_from_rung_two_the_camera_cuts(self):
        self.assertEqual(len(M.deal(1, seed=1).cuts), 1)
        self.assertGreater(len(M.deal(2, seed=1).cuts), 1)
        self.assertGreater(len(M.deal(13, seed=1).cuts),
                           len(M.deal(4, seed=1).cuts))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('glove', 1, pilot, seed=1, steps=24000),
                         [1.0])
        self.assertEqual(drive('glove', 1, lambda t: None, seed=1,
                               steps=24000), [-1.0])


if __name__ == '__main__':
    unittest.main()
