#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Crossings: counting, clean crossings, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import crossings as M


class TheCount(unittest.TestCase):

    def test_an_x_crosses_once(self):
        hits = M.crossings([(0, 0), (10, 10)], [(0, 10), (10, 0)])
        self.assertEqual(len(hits), 1)
        self.assertAlmostEqual(hits[0][0][0], 5.0)
        self.assertAlmostEqual(hits[0][1], 90.0)

    def test_the_answer_is_the_count_and_every_crossing_is_clean(self):
        for rung in (1, 4, 7, 10, 13, 16):
            for seed in range(4):
                p = M.deal(rung, seed=seed)
                hits = M.crossings(p.red, p.blue)
                self.assertEqual(len(hits), p.answer)
                self.assertTrue(all(a >= p.level.angle for _q, a in hits))
                for i in range(len(hits)):
                    for j in range(i):
                        self.assertGreaterEqual(math.hypot(
                            hits[i][0][0] - hits[j][0][0],
                            hits[i][0][1] - hits[j][0][1]), 7)

    def test_decoys_cross_both(self):
        p = M.deal(12, seed=3)
        self.assertEqual(len(p.decoys), 1)
        self.assertTrue(M.crossings(p.decoys[0], p.red))
        self.assertTrue(M.crossings(p.decoys[0], p.blue))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        self.assertEqual(drive('crossings', 4, lambda t: t.puzzle.answer,
                               seed=1), [1.0])
        self.assertEqual(drive('crossings', 4,
                               lambda t: (t.puzzle.answer + 1) % 4, seed=1),
                         [-1.0])


if __name__ == '__main__':
    unittest.main()
