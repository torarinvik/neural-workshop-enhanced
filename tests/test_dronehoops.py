#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Drone Hoops: the courses, the flying, the hoops, the camera, the
sound, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import dronehoops as M


def flown(course, steps, port=None, dt=1 / 30.0):
    run = M.Run(course)
    for _k in range(steps):
        run.step(dt, port)
    return run


class TheCourses(unittest.TestCase):

    def test_the_ladder_adds_what_it_says(self):
        g = [M.grade(r) for r in (1, 4, 7, 10, 13, 16, 20, 24, 30)]
        self.assertEqual([x.camera for x in g[:4]],
                         ['look', 'follow', 'cuts', 'cuts'])
        self.assertTrue(g[2].lit and not g[3].lit)
        self.assertFalse(g[3].spin or g[3].bob)
        self.assertTrue(g[4].spin and g[4].bob)
        self.assertTrue(g[5].wind and g[5].birds and not g[5].lightning)
        self.assertEqual(g[6].camera, 'circle')
        self.assertTrue(g[6].lightning and not g[6].decoy and g[7].decoy)
        self.assertLess(g[8].radius, g[0].radius)
        self.assertGreater(g[8].hoops, g[0].hoops)

    def test_hoops_sit_inside_the_yard_and_apart(self):
        for rung in (1, 10, 25):
            for s in range(5):
                course = M.deal(rung, seed=s)
                self.assertEqual(len(course.hoops), course.level.hoops)
                for k, h in enumerate(course.hoops):
                    x, y, z = h.centre
                    self.assertLess(abs(x), M.HALF - 4)
                    self.assertLess(abs(z), M.HALF - 4)
                    self.assertGreater(y - h.radius, 0.0)
                    for o in course.hoops[k + 1:]:
                        self.assertGreater(math.hypot(
                            x - o.centre[0], z - o.centre[2]), 7.0)

    def test_the_reference_passes_and_idle_and_random_fail(self):
        for rung in (1, 4, 7, 10, 13, 16, 22, 28):
            for s in range(3):
                course = M.deal(rung, seed=s)
                self.assertTrue(M.play(course)[0], (rung, s))
                self.assertFalse(M.play(course, lambda run: [])[0])
                draw = random.Random(s)
                self.assertFalse(M.play(course, lambda run: [
                    draw.randrange(M.PORTS)])[0])


class TheFlying(unittest.TestCase):

    def test_pushes_follow_the_camera(self):
        course = M.deal(8, seed=1)
        run = M.Run(course)
        f, r = run.frame()
        run.step(1 / 30.0, M.FORWARD)
        moved = M.sub(run.p, M.START)
        self.assertGreater(M.dot(moved, f), 0)
        self.assertAlmostEqual(M.dot(moved, r), 0.0, places=3)
        run = M.Run(course)
        run.step(1 / 30.0, M.RIGHT)
        self.assertGreater(M.dot(M.sub(run.p, M.START), r), 0)
        run = M.Run(course)
        run.step(1 / 30.0, M.UP)
        self.assertGreater(run.p[1], M.START[1])

    def test_the_drone_coasts_then_stops_and_stays_in_the_yard(self):
        course = M.deal(1, seed=2)
        run = flown(course, 30, M.FORWARD)
        moving = M.norm(run.v)
        self.assertGreater(moving, 2.0)
        for _k in range(5):
            run.step(1 / 30.0)
        self.assertGreater(M.norm(run.v), 0.3 * moving)
        for _k in range(90):
            run.step(1 / 30.0)
        self.assertLess(M.norm(run.v), 0.1)
        run = flown(course, 900, M.BACK)
        self.assertGreaterEqual(run.p[2], -M.HALF)
        run = flown(course, 300, M.DOWN)
        self.assertGreaterEqual(run.p[1], M.FLOOR)

    def test_the_mouse_aim_flies_to_the_spot(self):
        course = M.deal(1, seed=2)
        run = M.Run(course)
        run.aim, run.aim_y = (4.0, -6.0), 6.0
        for _k in range(240):
            run.step(1 / 30.0)
        self.assertAlmostEqual(run.p[0], 4.0, delta=0.3)
        self.assertAlmostEqual(run.p[2], -6.0, delta=0.3)
        self.assertAlmostEqual(run.p[1], 6.0, delta=0.3)
        run.step(1 / 30.0, M.LEFT)
        self.assertIsNone(run.aim)


class TheHoops(unittest.TestCase):

    def place(self, run, k, along, off=0.0):
        c, n = M.hoop_at(run.course.hoops[k], run.t)
        side = (n[2], 0.0, -n[0])
        run.p = M.add(M.add(c, M.scale(n, along)), M.scale(side, off))
        run.v = M.scale(n, -6.0 if along > 0 else 6.0)

    def test_through_the_middle_passes_and_the_rim_bounces(self):
        course = M.deal(4, seed=3)
        run = M.Run(course)
        self.place(run, 0, 0.1)
        run.step(1 / 30.0)
        self.assertEqual(run.next, 1)
        run = M.Run(course)
        h = course.hoops[0]
        self.place(run, 0, 0.1, off=h.radius)
        run.step(1 / 30.0)
        self.assertEqual(run.next, 0)
        self.assertEqual(run.bumps, 1)
        c, n = M.hoop_at(h, run.t)
        self.assertGreater(M.dot(M.sub(run.p, c), n), 0)

    def test_a_wrong_hoop_loses_only_once_the_gold_is_gone(self):
        lit = M.Run(M.deal(4, seed=3))
        self.place(lit, 2, 0.1)
        lit.step(1 / 30.0)
        self.assertIsNone(lit.result)
        dark = M.Run(M.deal(11, seed=3))
        self.place(dark, 2, 0.1)
        dark.step(1 / 30.0)
        self.assertFalse(dark.result[0])

    def test_hoops_move_and_turn_from_rung_13(self):
        h = M.deal(14, seed=1).hoops[0]
        c0, n0 = M.hoop_at(h, 0.0)
        c1, n1 = M.hoop_at(h, 3.0)
        self.assertGreater(M.norm(M.sub(c0, c1)), 0.05)
        self.assertLess(M.dot(n0, n1), 0.999)


class TheCamera(unittest.TestCase):

    def test_cuts_change_the_camera_and_what_forward_means(self):
        course = M.deal(8, seed=4)
        run = M.Run(course)
        seen = set()
        frames = set()
        while run.t < course.cuts[3].t + 0.1:
            run.step(1 / 30.0)
            seen.add(run.cam)
            f, _r = run.frame()
            frames.add((round(f[0], 1), round(f[2], 1)))
        self.assertGreaterEqual(len(seen), 3)
        self.assertGreaterEqual(len(frames), 3)

    def test_the_circling_camera_goes_round(self):
        course = M.deal(22, seed=1)
        circle = [c for c in course.cuts if c.camera == -1]
        self.assertTrue(circle)
        run = M.Run(course)
        while run.t < circle[0].t + 0.1:
            run.step(1 / 30.0)
        a = run.frame()[0]
        for _k in range(45):
            run.step(1 / 30.0)
            if run.cam != -1:
                break
        if run.cam == -1:
            self.assertLess(M.dot(a, run.frame()[0]), 0.999)


class TheSound(unittest.TestCase):

    def test_the_bell_rings_faster_near_and_higher_above(self):
        course = M.deal(11, seed=2)
        far = flown(course, 90)
        bells = [n for n in far.notes if n.voice == M.BELL]
        run = M.Run(course)
        c, n = M.hoop_at(course.hoops[0], 0.0)
        run.p = M.add(c, M.scale(n, -2.5))
        run.p = (run.p[0], c[1] - 2.5, run.p[2])
        for _k in range(90):
            run.v = (0.0, 0.0, 0.0)
            run.step(1 / 30.0)
        near = [n for n in run.notes if n.voice == M.BELL]
        self.assertGreater(len(near), len(bells))
        self.assertGreater(near[-1].freq, 880.0)

    def test_gusts_are_heard_before_they_hit(self):
        course = M.deal(17, seed=1)
        gust = course.gusts[0]
        run = M.Run(course)
        while run.t < gust.t - 0.2:
            run.step(1 / 30.0)
        self.assertIsNone(M.gust_at(course, run.t))
        self.assertTrue(any(n.voice == M.WIND for n in run.notes))

    def test_birds_thunder_and_a_second_bell(self):
        course = M.deal(25, seed=1)
        run = flown(course, 30 * 12)
        voices = {n.voice for n in run.notes}
        self.assertIn(M.BIRD, voices)
        self.assertIn(M.THUNDER, voices)
        rang = {round(n.pan, 2) for n in run.notes if n.voice == M.BELL}
        self.assertGreater(len(rang), 1)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('drone_hoops', 1, pilot, seed=1, steps=2500),
                         [1.0])
        self.assertEqual(drive('drone_hoops', 1, lambda t: None, seed=1,
                               steps=3600), [-1.0])

    def test_the_agent_hears_the_bell(self):
        from nwenv import catalog
        env = catalog.env_class('drone_hoops')(seed=2, rung=11, trials=1,
                                               adaptive=False)
        try:
            heard = 0
            for _k in range(120):
                env.step(None)
                chunk = env._public_audio
                if chunk:
                    heard += len(chunk['audio_pcm'])
            self.assertGreater(heard, 0)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()
