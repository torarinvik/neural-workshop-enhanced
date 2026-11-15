#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The 3D kit the spatial tasks share: turns, cube figures, the camera.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

import uisupport  # noqa: F401  (puts the package on the path)
from neural_workshop import space as S


class Turns(unittest.TestCase):

    def test_there_are_24_grid_turns_and_all_differ(self):
        self.assertEqual(len(set(S.GRID_TURNS)), 24)

    def test_a_turn_keeps_lengths_and_handedness(self):
        m = S.rotation((1, 2, 3), 1.1)
        for v in ((1, 0, 0), (0.3, -2, 5)):
            self.assertAlmostEqual(S.length(S.apply(m, v)), S.length(v))
        x, y, z = (S.apply(m, e) for e in ((1, 0, 0), (0, 1, 0),
                                          (0, 0, 1)))
        for a, b in zip(S.cross(x, y), z):
            self.assertAlmostEqual(a, b)

    def test_angle_between_reads_back_the_angle(self):
        m = S.rotation((0, 1, 0), 0.7)
        self.assertAlmostEqual(S.angle_between(S.IDENTITY, m), 0.7)


class Figures(unittest.TestCase):

    def test_arms_are_chiral_and_connected(self):
        draw = random.Random(3)
        for count in (7, 9, 11):
            for _k in range(10):
                f = S.arms(draw, count)
                self.assertEqual(len(set(f)), count)
                self.assertTrue(S.connected(f))
                self.assertTrue(S.chiral(f))

    def test_a_turned_figure_is_the_same_and_a_mirror_is_not(self):
        f = S.arms(random.Random(1), 8)
        for m in S.GRID_TURNS:
            turned = [tuple(sum(m[r][k] * c[k] for k in range(3))
                            for r in range(3)) for c in f]
            self.assertTrue(S.same_shape(f, turned))
        self.assertFalse(S.same_shape(f, S.mirrored(f)))

    def test_a_nudged_figure_is_neither(self):
        draw = random.Random(2)
        f = S.arms(draw, 9)
        g = S.nudged(draw, f)
        self.assertFalse(S.same_shape(f, g))
        self.assertFalse(S.same_shape(S.mirrored(f), g))
        self.assertEqual(len(set(g) & set(f)), 8)


class Camera(unittest.TestCase):

    def test_perspective_shrinks_with_distance(self):
        cam = S.Camera((0, 0, 0), (0, 0, 10), focal=1.0)
        near = cam.project((1, 0, 2))[0]
        far = cam.project((1, 0, 4))[0]
        self.assertAlmostEqual(near, 2 * far)

    def test_looking_down_with_x_right_puts_minus_z_up(self):
        cam = S.Camera((0, 10, 0), (0, 0, 0), up=(0, 0, -1))
        self.assertGreater(cam.project((0, 0, -1))[1], 0)
        self.assertGreater(cam.project((1, 0, 0))[0], 0)

    def test_a_cube_shows_three_faces_from_a_corner(self):
        cam = S.Camera((5, 5, 5), (0, 0, 0))
        painted = S.render(S.cube_faces([(0, 0, 0)]), cam)
        self.assertEqual(len(painted), 3)

    def test_nearer_faces_are_drawn_last(self):
        cam = S.Camera((0, 0, -10), (0, 0, 0), focal=1.0)
        faces = S.box_faces((0, 0, 0), (1, 1, 1), (1, 1, 1), 'far') + \
            S.box_faces((0, 0, -3), (1, 1, 1), (1, 1, 1), 'near')
        tags = [p.tag for p in S.render(faces, cam)]
        self.assertEqual(tags[-1], 'near')
        self.assertEqual(tags[0], 'far')

    def test_clipping_keeps_inside_and_cuts_outside(self):
        square = [(-2, -2), (2, -2), (2, 2), (-2, 2)]
        cut = S.clip(square, -1, -1, 1, 1)
        self.assertEqual(sorted(cut), sorted([(-1, -1), (1, -1), (1, 1),
                                              (-1, 1)]))
        self.assertEqual(S.clip([(5, 5), (6, 5), (6, 6)], -1, -1, 1, 1),
                         [])


if __name__ == '__main__':
    unittest.main()
