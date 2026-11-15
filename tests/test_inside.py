#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inside or Out?: the region, the line, the dots, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import inside as M

RUNGS = (1, 4, 7, 10, 13, 16, 20, 25)


class TheLine(unittest.TestCase):

    def test_one_closed_line_round_one_region(self):
        for rung in RUNGS:
            for seed in range(5):
                p = M.deal(rung, seed=seed)
                self.assertEqual(len(p.loops), 1)
                self.assertTrue(M._connected(p.region))

    def test_the_line_agrees_with_the_region(self):
        for rung in (1, 7, 13):
            p = M.deal(rung, seed=2)
            for x, y in list(p.region)[:40]:
                self.assertTrue(M.contains(p.loops[0], (x + 0.5, y + 0.5)))

    def test_the_answer_is_what_the_line_says(self):
        for rung in RUNGS:
            for seed in range(12):
                p = M.deal(rung, seed=seed)
                inside = [M.contains(p.loops[0], d) for d in p.dots]
                if len(p.dots) == 2:
                    self.assertEqual(inside[0] == inside[1], p.answer == 0)
                else:
                    self.assertEqual(inside[0], p.answer == M.IN)

    def test_both_answers_come_up(self):
        for rung in (1, 10, 14):
            self.assertEqual({M.deal(rung, seed=s).answer
                              for s in range(20)}, {0, 1})

    def test_the_ladder(self):
        self.assertEqual(M.grade(1).kind, 'blob')
        self.assertEqual(M.grade(7).kind, 'maze')
        self.assertTrue(M.grade(13).pair)
        self.assertGreater(M.grade(16).decoys, 0)
        self.assertGreater(M.grade(25).size, M.grade(10).size)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        self.assertEqual(drive('inside_or_out', 7,
                               lambda t: t.puzzle.answer, seed=1), [1.0])
        self.assertEqual(drive('inside_or_out', 7,
                               lambda t: 1 - t.puzzle.answer, seed=1),
                         [-1.0])


if __name__ == '__main__':
    unittest.main()
