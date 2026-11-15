#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shape from Motion: the dots, the deals, the boundary, the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import draws, drive, right, wrong
from uisupport import needs_ui

from neural_workshop import sfm as M


class TheLadder(unittest.TestCase):

    def test_the_parts_come_in_on_their_rungs(self):
        self.assertIsNone(M.grade(6).life)
        self.assertIsNotNone(M.grade(7).life)
        self.assertEqual(M.grade(9).spin_share, 0.0)
        self.assertGreater(M.grade(10).spin_share, 0.0)
        self.assertEqual(M.grade(11).noise, 0.0)
        self.assertGreater(M.grade(12).noise, 0.0)
        self.assertGreater(M.grade(1).dots, M.grade(30).dots)


class TheDots(unittest.TestCase):

    def test_every_solid_s_dots_lie_within_reach(self):
        draw = random.Random(1)
        for solid in M.SOLIDS:
            for _k in range(300):
                x, y, z = M.surface(solid, draw)
                self.assertLess(max(abs(x), abs(y), abs(z)), 1.2, solid)

    def test_dots_are_the_same_at_the_same_moment(self):
        p = M.deal(9, seed=5)
        self.assertEqual(M.dots(p, 1.3), M.dots(p, 1.3))
        self.assertNotEqual(M.dots(p, 1.3), M.dots(p, 1.4))

    def test_the_near_side_moves_the_way_asked(self):
        for way in (1, -1):
            p = M.deal(11, seed=3)._replace(kind='spin', way=way,
                                            solid='sphere')
            a, b = M.dots(p, 0.0), M.dots(p, 0.02)
            near = [i for i, (_x, _y, s) in enumerate(a) if s > 1.15]
            drift = sum(b[i][0] - a[i][0] for i in near) / len(near)
            self.assertGreater(drift * way, 0)

    def test_the_right_solid_is_on_offer_once(self):
        for rung in (2, 8, 14, 24):
            for seed in range(30):
                p = M.deal(rung, seed=seed)
                if p.kind == 'shape':
                    self.assertEqual(p.options.count(p.solid), 1)
                    self.assertEqual(p.options[p.answer], p.solid)
                    self.assertEqual(len(p.options), M.grade(rung).choices)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (2, 14):
            self.assertEqual(drive('shape_from_motion', rung, right),
                             [1.0])
            self.assertEqual(drive('shape_from_motion', rung, wrong),
                             [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def test_every_rung_draws_its_dots(self):
        from neural_workshop.ui.sfm import ShapeFromMotion
        draws(self, ShapeFromMotion, (1, 9, 13, 26))


if __name__ == '__main__':
    unittest.main()
