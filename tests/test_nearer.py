#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Which Is Nearer?: the cues, the deals, the boundary, the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import unittest

from spatialsupport import draws, drive, right, wrong
from uisupport import needs_ui

from neural_workshop import nearer as N


class TheLadder(unittest.TestCase):

    def test_one_cue_goes_every_few_rungs(self):
        self.assertEqual([N.grade(r).cue for r in (1, 7, 10, 13, 16)],
                         ['size', 'floor', 'shadow', 'hiding', 'motion'])
        self.assertFalse(N.grade(19).order)
        self.assertTrue(N.grade(20).order)
        self.assertGreater(N.grade(1).ratio, N.grade(19).ratio)
        self.assertGreater(N.grade(19).ratio, N.grade(30).ratio)


class TheDeals(unittest.TestCase):

    def test_the_nearest_is_nearer_by_the_rung_s_ratio(self):
        for rung in (1, 8, 11, 14, 17, 22, 29):
            level = N.grade(rung)
            for seed in range(25):
                p = N.deal(rung, seed=seed)
                zs = [p.solids[i].centre[2] for i in p.order]
                self.assertEqual(p.answer, p.order[0])
                self.assertGreaterEqual(zs[1] / zs[0], level.ratio - 1e-9)
                if level.order:
                    for a, b in zip(zs, zs[1:]):
                        self.assertGreaterEqual(b / a, level.ratio - 1e-9)

    def test_ports_count_left_to_right(self):
        p = N.deal(9, seed=2)
        cam = N.camera(p.cue)
        xs = [cam.project(s.centre)[0] for s in p.solids]
        self.assertEqual(xs, sorted(xs))

    def test_past_the_floor_page_size_says_nothing(self):
        """From rung 10 a solid's size on the page is drawn apart from
        its depth: across many deals the two barely correlate."""
        sizes, depths = [], []
        for seed in range(150):
            p = N.deal(17, seed=seed)
            for s in p.solids:
                sizes.append(s.size / s.centre[2])
                depths.append(s.centre[2])
        n = len(sizes)
        ms, md = sum(sizes) / n, sum(depths) / n
        cov = sum((a - ms) * (b - md) for a, b in zip(sizes, depths))
        sd = math.sqrt(sum((a - ms) ** 2 for a in sizes)
                       * sum((b - md) ** 2 for b in depths))
        self.assertLess(abs(cov / sd), 0.2)

    def test_crowded_solids_hide_one_another(self):
        p = N.deal(14, seed=3)
        boxes = dict(N.boxes(N.scene(p)))
        nearest = boxes[p.answer]
        overlaps = 0
        for tag, (x0, y0, x1, y1) in boxes.items():
            if tag != p.answer and x0 < nearest[2] and nearest[0] < x1 \
                    and y0 < nearest[3] and nearest[1] < y1:
                overlaps += 1
        self.assertGreater(overlaps, 0)

    def test_the_eye_sways_only_where_motion_is_the_cue(self):
        still = N.deal(8, seed=1)
        self.assertEqual(N.scene(still, 0.0), N.scene(still, 0.6))
        moving = N.deal(17, seed=1)
        self.assertNotEqual(N.scene(moving, 0.0), N.scene(moving, 0.6))


def in_order(task):
    return task.puzzle.order[len(task.picked)]


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (3, 17):
            self.assertEqual(drive('which_is_nearer', rung, right), [1.0])
            self.assertEqual(drive('which_is_nearer', rung, wrong), [-1.0])

    def test_ordering_all_of_them(self):
        self.assertEqual(drive('which_is_nearer', 24, in_order), [1.0])

        def backwards(task):
            return task.puzzle.order[-1 - len(task.picked)]
        self.assertEqual(drive('which_is_nearer', 24, backwards), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def test_every_cue_draws(self):
        from neural_workshop.ui.nearer import WhichIsNearer
        draws(self, WhichIsNearer, (2, 8, 11, 14, 17))


if __name__ == '__main__':
    unittest.main()
