#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Keep the Beat: the song, the scoring, the reference, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import beat as M


def tapped(song, times):
    run = M.Run(song)
    run.taps = list(times)
    return run.score()


class TheSong(unittest.TestCase):

    def test_heard_then_silent_in_whole_cycles(self):
        for rung in (1, 10, 13, 16, 25):
            song = M.deal(rung, seed=1)
            n = len(song.level.pattern)
            self.assertEqual(len(song.beats) % n, 0)
            self.assertTrue(song.heard[0])
            self.assertFalse(song.heard[-1])
            self.assertEqual(song.judged,
                             [k for k, h in enumerate(song.heard) if not h])

    def test_a_reprise_brings_the_metronome_back(self):
        song = M.deal(16, seed=1)
        flips = sum(1 for a, b in zip(song.heard, song.heard[1:]) if a != b)
        self.assertEqual(flips, 3)

    def test_the_curtain_is_down_only_in_silence(self):
        song = M.deal(1, seed=1)
        run = M.Run(song)
        run.t = song.beats[0] - 0.1
        self.assertFalse(run.curtain())
        run.t = song.beats[song.judged[1]] - 0.1
        self.assertTrue(run.curtain())


class TheScore(unittest.TestCase):

    def test_on_the_beat_counts_off_it_does_not(self):
        song = M.deal(4, seed=2)
        beats = [song.beats[k] for k in song.judged]
        w = song.level.window
        self.assertEqual(tapped(song, beats), (len(beats), 0))
        self.assertEqual(tapped(song, [b + w * 0.9 for b in beats])[0],
                         len(beats))
        self.assertEqual(tapped(song, [b + w * 1.5 for b in beats])[0], 0)

    def test_one_tap_finds_one_beat(self):
        song = M.deal(4, seed=2)
        b = song.beats[song.judged[0]]
        self.assertEqual(tapped(song, [b, b + 0.01])[0], 1)

    def test_the_reference_passes_and_idle_and_mashing_fail(self):
        for rung in (1, 7, 10, 13, 16, 22):
            for s in range(3):
                song = M.deal(rung, seed=s)
                self.assertTrue(M.play(song)[0], (rung, s))
                self.assertFalse(M.play(song, lambda run: [])[0])
                draw = random.Random(s)
                self.assertFalse(M.play(song, lambda run: [M.TAP]
                                        if draw.random() < 0.08 else [])[0])

    def test_keeping_the_heard_tempo_through_a_swing_fails(self):
        song = M.deal(11, seed=3)
        mean = (song.beats[song.judged[0]] - song.beats[0]) / \
            song.judged[0]
        steady = [song.beats[song.judged[0]] + k * mean
                  for k in range(len(song.judged))]
        hits, _strays = tapped(song, steady)
        self.assertLess(hits, 0.75 * len(song.judged))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('keep_the_beat', 1, pilot, seed=1,
                               steps=3000), [1.0])
        self.assertEqual(drive('keep_the_beat', 1, lambda t: None, seed=1,
                               steps=3000), [-1.0])


if __name__ == '__main__':
    unittest.main()
