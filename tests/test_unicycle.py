#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Unicycle: the reference, the shortcuts, the four-way balance, the
boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import unicycle as M


def fixed(port):
    """A player that sends one port every step."""
    return lambda run: [port]


def left_alone(rung):
    run = M.Run(M.deal(rung, seed=1))
    while run.result is None:
        run.step(1 / 30.0, None)
    return run


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for rung in (1, 2, 4, 7, 10, 13, 20):
            for s in range(2):
                dealt = M.deal(rung, seed=s)
                self.assertTrue(M.play(dealt)[0], (rung, s))
                self.assertFalse(M.play(dealt, lambda run: [])[0],
                                 ('idle', rung, s))
                draw = random.Random(s)
                self.assertFalse(M.play(dealt, lambda run: [
                    draw.randrange(M.PORTS)])[0], ('random', rung, s))
                for port in range(M.PORTS):
                    if rung == 1 and port == M.PEDAL:
                        continue      # rung 1: just pedalling gets there
                    self.assertFalse(M.play(dealt, fixed(port))[0],
                                     ('fixed', port, rung, s))

    def test_the_grade_grows_without_end(self):
        self.assertEqual(M.grade(500).rung, 500)
        self.assertEqual(M.grade(0), M.grade(1))

    def test_letting_go_falls_over(self):
        run = left_alone(9)
        self.assertFalse(run.result[0])
        self.assertLess(run.t, 30.0)

    def test_the_bottom_rungs_are_much_gentler(self):
        one, nine = M.grade(1), M.grade(9)
        self.assertLess(one.gravity, 0.1 * nine.gravity)
        self.assertEqual((nine.gravity, nine.soft), (M.GRAV, 1.0))
        for r in range(1, 9):
            self.assertLess(M.grade(r).gravity, M.grade(r + 1).gravity)
        # left alone, the rung-3 rider stays up far longer
        self.assertGreater(left_alone(3).t, 3 * left_alone(10).t)

    def test_training_wheels_at_the_bottom(self):
        """Rungs 1 and 2: the rider rights themselves, and a beginner who
        only pedals and steers at the flag gets there; from rung 3 they
        must balance."""
        def naive(run):
            b, tr = run.body, run.tr
            fx, fz = tr.flags[run.flag]
            off = M._wrap(math.atan2(fz - b.z, fx - b.x) - b.heading)
            run.k = getattr(run, 'k', 0) + 1
            if abs(off) > 0.15 and run.k % 3 == 0:
                return [M.LEAN_R if off > 0 else M.LEAN_L]
            return [M.PEDAL]
        for rung, passes in ((1, True), (2, True), (3, False)):
            for s in range(3):
                self.assertEqual(M.play(M.deal(rung, seed=s), naive)[0],
                                 passes, (rung, s))
        self.assertTrue(left_alone(1).result[1].startswith('Out of time'))

    def test_later_rungs_have_more_flags_and_turns(self):
        self.assertEqual((M.grade(1).flags, M.grade(1).turn), (1, 0.0))
        self.assertGreater(M.grade(10).flags, M.grade(4).flags)
        tr = M.deal(4, seed=2)
        self.assertEqual(len(tr.flags), 2)
        self.assertGreater(max(abs(z) for _x, z in tr.flags), 1.0)


class TheFourWays(unittest.TestCase):

    def test_the_rider_topples_sideways_and_leaning_rights_it(self):
        tr = M.deal(1, seed=1)
        tr = M.deal(9, seed=1)          # no training wheels from rung 8
        b = M.begin(tr)._replace(roll=0.2, rate=0.0)
        left = b
        for _k in range(10):
            b = M.advance(tr, b, None, 1 / 30.0)
            left = M.advance(tr, left, M.LEAN_L, 1 / 30.0)
        self.assertGreater(b.roll, 0.2)
        self.assertLess(left.roll, b.roll)

    def test_a_lean_to_the_right_turns_right(self):
        """Heading +x, the rider's right is +z: a right lean turns the
        heading towards +z and the head goes that way."""
        tr = M.deal(1, seed=1)
        self.assertEqual(M.frame(M.begin(tr))[1], (-0.0, 0.0, 1.0))
        b = M.begin(tr)._replace(roll=0.0, vx=2.0, ux=2.0)
        for _k in range(15):
            b = M.advance(tr, b, M.LEAN_R, 1 / 30.0)
        self.assertGreater(b.roll, 0.0)
        self.assertGreater(b.heading, 0.0)
        self.assertGreater(M.head(tr, b)[2], 0.0)

    def test_only_the_head_on_the_ground_ends_the_ride(self):
        tr = M.deal(1, seed=1)
        b = M.begin(tr)
        self.assertIsNone(M.crashed(tr, b._replace(roll=0.8)))
        self.assertIsNotNone(M.crashed(tr, b._replace(roll=math.pi / 2)))

    def test_reaching_each_flag_in_turn(self):
        tr = M.deal(4, seed=0)
        run = M.Run(tr)
        seen = []
        while run.result is None:
            run.step(1 / 30.0, (M.autopilot(run) or [None])[0])
            if not seen or seen[-1] != run.flag:
                seen.append(run.flag)
        self.assertTrue(run.result[0])
        self.assertEqual(seen, list(range(len(tr.flags) + 1)))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('unicycle', 1, pilot, seed=1, steps=24000),
                         [1.0])
        self.assertEqual(drive('unicycle', 1, lambda t: None, seed=1,
                               steps=24000), [-1.0])


if __name__ == '__main__':
    unittest.main()
