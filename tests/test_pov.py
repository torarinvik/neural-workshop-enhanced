#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Point of View: the pictures, the deals, the boundary, the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import unittest

from spatialsupport import draws, drive, right, wrong
from uisupport import needs_ui

from neural_workshop import pov as P


class TheDeals(unittest.TestCase):

    def test_every_picture_shows_a_different_order(self):
        for rung in (1, 5, 8, 11, 14, 17, 21, 28):
            colours = P.grade(rung).colours
            for seed in range(25):
                p = P.deal(rung, seed=seed)
                sigs = [P._signature(p.solids, v, colours) for v in p.views]
                self.assertEqual(len(set(sigs)), len(sigs), (rung, seed))
                self.assertEqual(p.views[p.answer],
                                 (p.angle, p.eye, False))

    def test_a_camera_looks_at_the_table(self):
        cam = P.camera(0.0, 2.6)
        self.assertGreater(cam.view(P.LOOK_AT)[2], 0)

    def test_a_mirrored_picture_reverses_the_order(self):
        p = P.deal(8, seed=1)
        self.assertEqual(P.order(p.solids, p.angle, p.eye, True),
                         tuple(reversed(P.order(p.solids, p.angle,
                                                p.eye))))

    def test_solids_stand_on_the_table_apart(self):
        for seed in range(20):
            p = P.deal(24, seed=seed)
            for a in p.solids:
                self.assertLessEqual(abs(a.centre[0]), P.TABLE)
                self.assertLessEqual(abs(a.centre[2]), P.TABLE)
                for b in p.solids:
                    if a is not b:
                        self.assertGreater(math.hypot(
                            a.centre[0] - b.centre[0],
                            a.centre[2] - b.centre[2]), 1.0)

    def test_sides_only_until_rung_thirteen(self):
        for seed in range(20):
            angle = P.deal(12, seed=seed).angle
            self.assertAlmostEqual(angle % (math.pi / 2), 0.0)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (2, 18):
            self.assertEqual(drive('point_of_view', rung, right), [1.0])
            self.assertEqual(drive('point_of_view', rung, wrong), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def test_every_rung_draws(self):
        from neural_workshop.ui.pov import PointOfView
        draws(self, PointOfView, (1, 8, 14, 18, 24))


if __name__ == '__main__':
    unittest.main()
