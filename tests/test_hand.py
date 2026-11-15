#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The drawn pointer that the mouse-and-keyboard tasks share.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from neural_workshop import hand as H


class ThePointer(unittest.TestCase):

    def test_ports_move_it_by_three_sizes_and_it_stays_on_the_screen(self):
        h = H.Hand(500, 320)
        h.move(0)
        self.assertEqual((h.x, h.y), (500, 400))
        h.move(1 * 3 + 1)
        self.assertEqual((h.x, h.y), (500, 380))
        h.move(2 * 3 + 2)
        self.assertEqual((h.x, h.y), (495, 380))
        h.move(3 * 3)
        self.assertEqual((h.x, h.y), (575, 380))
        for _k in range(40):
            h.move(3 * 3)
            h.move(0)
        self.assertEqual((h.x, h.y), (H.W, H.H))

    def test_toward_reaches_any_spot_in_a_few_moves(self):
        for goal in ((123, 607), (998, 3), (500, 320), (37, 451)):
            h = H.Hand()
            for n in range(60):
                port = H.toward(h, *goal)
                if port is None:
                    break
                h.move(port)
            self.assertLess(n, 30)
            self.assertLessEqual(abs(h.x - goal[0]), 3)
            self.assertLessEqual(abs(h.y - goal[1]), 3)

    def test_a_key_counts_as_held_for_a_moment(self):
        run = H.HandRun(10.0)
        run.controls(20)
        self.assertTrue(run.holding(20))
        run.t += H.HandRun.LATCH + 0.01
        self.assertFalse(run.holding(20))

    def test_notes_stay_in_time_order(self):
        run = H.HandRun(10.0)
        run.note(0.1, 440.0, 0, at=0.5)
        run.note(0.1, 440.0, 0)
        run.note(0.1, 440.0, 0, at=0.2)
        self.assertEqual([n.t for n in run.notes], [0.0, 0.2, 0.5])

    def test_a_screen_point_goes_back_onto_a_plane(self):
        view = H.lens((0.0, 0.0, 9.0), (0.0, 0.0, 0.0))
        q = view.see((1.5, -2.0, 0.0))
        p = H.on_plane(view, q[0], q[1], (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        self.assertAlmostEqual(p[0], 1.5, places=5)
        self.assertAlmostEqual(p[1], -2.0, places=5)


if __name__ == '__main__':
    unittest.main()
