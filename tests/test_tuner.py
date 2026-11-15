#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tuner: the tunes, the dial, the locking, the sound, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import tuner as M


def go_to(run, k, then=()):
    run.dial = run.where(k)
    for port in then:
        M.act(run, port)


class TheTunes(unittest.TestCase):

    def test_only_the_target_plays_the_tune(self):
        for rung in (1, 7, 10, 16, 22):
            for s in range(5):
                radio = M.deal(rung, seed=s)
                target = radio.stations[radio.target]
                for k, st in enumerate(radio.stations):
                    if k == radio.target:
                        continue
                    self.assertNotEqual(M.exact(st), M.exact(target))
                    if radio.level.shifted:
                        self.assertNotEqual(M.shape(st), M.shape(target))

    def test_the_tune_heard_is_the_targets_tune(self):
        radio = M.deal(4, seed=1)
        self.assertEqual(M.exact(radio.heard),
                         M.exact(radio.stations[radio.target]))
        radio = M.deal(11, seed=1)
        self.assertEqual(M.shape(radio.heard),
                         M.shape(radio.stations[radio.target]))
        self.assertNotEqual(radio.heard.root,
                            radio.stations[radio.target].root)

    def test_decoys_from_rung_10_and_16(self):
        radio = M.deal(17, seed=2)
        tune = radio.stations[radio.target].degrees
        others = [s.degrees for k, s in enumerate(radio.stations)
                  if k != radio.target]
        self.assertTrue(any(sorted(o) == sorted(tune) for o in others))
        self.assertTrue(any(sum(a != b for a, b in zip(o, tune)) == 1
                            for o in others))


class TheDial(unittest.TestCase):

    def test_locking_on_the_target_and_holding_passes(self):
        radio = M.deal(4, seed=3)
        run = M.Run(radio)
        while not run.on():
            run.step(1 / 60.0)
        go_to(run, radio.target, (M.LOCK,))
        self.assertIsNotNone(run.lock_since)
        while run.result is None:
            run.step(1 / 60.0)
        self.assertTrue(run.result[0])

    def test_locking_on_another_station_fails(self):
        radio = M.deal(4, seed=3)
        run = M.Run(radio)
        while not run.on():
            run.step(1 / 60.0)
        go_to(run, (radio.target + 1) % len(radio.stations), (M.LOCK,))
        self.assertFalse(run.result[0])

    def test_locking_on_hiss_does_nothing_and_leaving_loses_the_lock(self):
        radio = M.deal(14, seed=3)
        run = M.Run(radio)
        while not run.on():
            run.step(1 / 60.0)
        gaps = sorted(run.where(k) for k in range(len(radio.stations)))
        run.dial = (gaps[0] + gaps[1]) / 2
        M.act(run, M.LOCK)
        self.assertIsNone(run.result)
        self.assertIsNone(run.lock_since)
        go_to(run, radio.target, (M.LOCK,))
        run.dial += radio.level.width * 3
        run.step(1 / 60.0)
        self.assertIsNone(run.lock_since)
        self.assertIsNone(run.result)

    def test_the_radio_answers_the_dial(self):
        radio = M.deal(4, seed=5)
        run = M.Run(radio)
        while not run.on():
            run.step(1 / 60.0)
        run.dial = run.where(radio.target)
        start = len(run.notes)
        for _k in range(120):
            run.step(1 / 60.0)
        tuned = [n for n in run.notes[start:] if n.voice != run.hiss]
        self.assertTrue(tuned)
        self.assertEqual({n.voice for n in tuned},
                         {radio.stations[radio.target].voice})

    def test_the_reference_passes_and_idling_fails(self):
        for rung in (1, 7, 10, 13, 16, 22):
            for s in range(3):
                radio = M.deal(rung, seed=s)
                self.assertTrue(M.play(radio)[0], (rung, s))
                self.assertFalse(M.play(radio, lambda run: [])[0])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('tuner', 1, pilot, seed=1, steps=1200),
                         [1.0])
        self.assertEqual(drive('tuner', 1, lambda t: None, seed=1,
                               steps=4000), [-1.0])


if __name__ == '__main__':
    unittest.main()
