#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Loading Dock: the orders, the forklift, the lifting, the trucks, the
boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import loadingdock as M


def point(run, at):
    q = run.view().see(at)
    run.hand.to(q[0], q[1])


def drag(run, a, b):
    point(run, a)
    run.press()
    point(run, b)
    run.step(1 / 60.0)
    run.release()


def park_at_slot(run, k):
    run.p = (run.slot(k)[0], M.SHELF_Z + 2.4)


def park_at_truck(run, k):
    run.p = (run.bed(k)[0], M.TRUCK_Z - 2.6)


def fetch(run, need):
    k = next(j for j, kind in enumerate(run.dock.shelf) if need.met_by(kind))
    park_at_slot(run, k)
    drag(run, run.slot(k), run.fork())


class TheOrders(unittest.TestCase):

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 40)}
        self.assertEqual((g[1].trucks, g[4].trucks, g[7].trucks), (1, 2, 3))
        self.assertTrue(g[7].cut and not g[4].cut)
        self.assertTrue(g[10].tags and not g[7].tags)
        self.assertTrue(g[13].nots and 4 in g[13].cams)
        self.assertTrue(g[16].busy and not g[13].busy)
        self.assertGreater(g[40].trucks, g[16].trucks)
        self.assertLess(g[40].each, g[1].each)

    def test_orders_read_as_what_they_need(self):
        red, heavy = M.Need(colour=0), M.Need(tag=2)
        self.assertEqual(M._order('OSLO', [red, red, M.Need(colour=1)]),
                         'OSLO: two red crates and a blue crate.')
        self.assertEqual(M._order('ROME', [heavy]), 'ROME: a heavy crate.')
        self.assertEqual(M._order('LIMA', [M.Need(no=0)]),
                         'LIMA: a crate that is not red.')
        self.assertTrue(red.met_by(M.Kind(0, 1)))
        self.assertFalse(M.Need(colour=0, tag=0).met_by(M.Kind(0, 1)))
        self.assertFalse(M.Need(no=0).met_by(M.Kind(0, 0)))

    def test_every_order_can_be_met_from_the_shelf(self):
        for rung in (1, 10, 13, 30):
            for s in range(5):
                dock = M.deal(rung, seed=s)
                self.assertEqual(len(dock.trucks), dock.level.trucks)
                for truck in dock.trucks:
                    self.assertTrue(truck.text.startswith(truck.city + ':'))
                    for need in truck.needs:
                        self.assertTrue(any(need.met_by(k)
                                            for k in dock.shelf))

    def test_the_reference_passes_and_idle_and_random_fail(self):
        for rung in (1, 4, 7, 10, 13, 16, 22, 35):
            for s in range(2):
                dock = M.deal(rung, seed=s)
                self.assertTrue(M.play(dock)[0], (rung, s))
                self.assertFalse(M.play(dock, lambda run: [])[0])
                draw = random.Random(s)
                self.assertFalse(M.play(dock, lambda run: [
                    draw.randrange(M.PORTS)])[0])


class TheForklift(unittest.TestCase):

    def test_it_drives_like_a_forklift_and_stays_on_the_floor(self):
        run = M.Run(M.deal(1, seed=1))
        for _k in range(30):
            run.step(1 / 60.0, M.FWD)
        self.assertLess(run.p[1], -2.0)             # towards the shelf
        self.assertAlmostEqual(run.p[0], 0.0, places=5)
        heading = run.heading
        for _k in range(30):
            run.step(1 / 60.0, M.RIGHT)
        self.assertLess(run.heading, heading)
        for _k in range(30):
            run.step(1 / 60.0, M.FWD)
        self.assertGreater(run.p[0], 0.5)           # it turned to its right
        for _k in range(600):
            run.step(1 / 60.0, M.FWD)
            if run.result is not None:
                break
        self.assertLessEqual(abs(run.p[0]), M.WIDE)
        self.assertLessEqual(abs(run.p[1]), M.DEEP)

    def test_a_crate_comes_off_the_shelf_only_from_beside_it(self):
        run = M.Run(M.deal(1, seed=1))
        drag(run, run.slot(0), run.fork())
        self.assertEqual(run.carried, [])
        park_at_slot(run, 0)
        drag(run, run.slot(0), run.fork())
        self.assertEqual(run.carried, [run.dock.shelf[0]])
        self.assertFalse(run.stocked(0))
        for _k in range(120):
            run.step(1 / 60.0)
        self.assertTrue(run.stocked(0))

    def test_it_carries_two_and_no_more(self):
        run = M.Run(M.deal(1, seed=1))
        park_at_slot(run, 0)
        for _n in range(3):
            for _k in range(120):
                run.step(1 / 60.0)
            drag(run, run.slot(0), run.fork())
        self.assertEqual(len(run.carried), M.CARRY)


class TheTrucks(unittest.TestCase):

    def test_the_right_crate_loads_and_the_lamp_sends_the_truck(self):
        dock = M.deal(1, seed=2)
        run = M.Run(dock)
        fetch(run, dock.trucks[0].needs[0])
        park_at_truck(run, 0)
        drag(run, run.fork(), run.bed(0))
        self.assertTrue(run.complete(0))
        self.assertIsNone(run.result)
        point(run, run.lamp(0))
        run.press()
        run.release()
        self.assertEqual(run.result[0], True)

    def test_the_wrong_crate_and_a_short_truck_both_lose(self):
        dock = M.deal(1, seed=2)
        run = M.Run(dock)
        wrong = next(k for k, kind in enumerate(dock.shelf)
                     if not dock.trucks[0].needs[0].met_by(kind))
        park_at_slot(run, wrong)
        drag(run, run.slot(wrong), run.fork())
        park_at_truck(run, 0)
        drag(run, run.fork(), run.bed(0))
        self.assertFalse(run.result[0])
        run = M.Run(dock)
        point(run, run.lamp(0))
        run.press()
        run.release()
        self.assertFalse(run.result[0])

    def test_a_crate_cannot_be_loaded_from_across_the_floor(self):
        dock = M.deal(1, seed=2)
        run = M.Run(dock)
        fetch(run, dock.trucks[0].needs[0])
        drag(run, run.fork(), run.bed(0))
        self.assertFalse(run.complete(0))
        self.assertEqual(len(run.carried), 1)

    def test_the_horn_sounds_before_a_truck_leaves_short(self):
        dock = M.deal(1, seed=2)
        run = M.Run(dock)
        leave = dock.trucks[0].leave
        while run.t < leave - M.HORN_AHEAD + 0.2:
            run.step(1 / 30.0)
        self.assertIsNone(run.result)
        self.assertTrue(any(n.voice == M.HORN for n in run.notes))
        while run.result is None:
            run.step(1 / 30.0)
        self.assertFalse(run.result[0])
        self.assertAlmostEqual(run.t, leave, delta=0.1)

    def test_cameras_cut_and_one_looks_from_behind_the_shelf(self):
        self.assertFalse(M.deal(4, seed=1).cuts)
        dock = M.deal(13, seed=1)
        self.assertTrue(dock.cuts)
        run = M.Run(dock)
        see = lambda x: run.view().see((x, 0.0, 0.0))[0]     # noqa: E731
        self.assertLess(see(-5.0), see(5.0))
        run.cam = 4
        self.assertGreater(see(-5.0), see(5.0))

    def test_another_forklift_works_the_floor_from_rung_16(self):
        self.assertIsNone(M.Run(M.deal(13, seed=1)).other())
        run = M.Run(M.deal(16, seed=1))
        a = run.other()
        for _k in range(60):
            run.step(1 / 30.0)
        self.assertNotEqual(a[0], run.other()[0])
        self.assertTrue(math.isfinite(run.other()[2]))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('loading_dock', 7, pilot, seed=1, steps=9000),
                         [1.0])
        self.assertEqual(drive('loading_dock', 1, lambda t: None, seed=1,
                               steps=3600), [-1.0])

    def test_the_agent_hears_the_engine(self):
        from nwenv import catalog
        env = catalog.env_class('loading_dock')(seed=2, rung=1, trials=1,
                                                adaptive=False)
        try:
            heard = 0
            for _k in range(300):
                env.step(M.FWD)
                chunk = env._public_audio
                if chunk:
                    heard += len(chunk['audio_pcm'])
            self.assertGreater(heard, 0)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()
