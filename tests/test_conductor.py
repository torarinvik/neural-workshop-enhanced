#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Conductor: the beat, the cues, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, settle, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import hand as H
from neural_workshop import conductor as M

RUNGS = (1, 4, 7, 10, 13, 16, 22, 35)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertLessEqual(len(rand), 1)

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 40)}
        self.assertEqual((g[1].beats, g[1].cues), (8, 1))
        self.assertEqual(g[1].kinds, ('enter',))
        self.assertIn('loud', g[4].kinds)
        self.assertIn('cut', g[7].kinds)
        self.assertEqual([g[r].numbers for r in (1, 7, 13)],
                         ['all', 'bars', 'start'])
        self.assertTrue(g[10].strict and not g[7].strict)
        self.assertTrue(g[16].bend and not g[13].bend)
        self.assertGreater(g[40].beats, g[16].beats)


class TheBeat(unittest.TestCase):

    def at_beat(self, rung, k=0):
        run = M.Run(M.deal(rung, seed=1))
        run.hand.to(500.0, 400.0)
        while run.t < run.piece.times[k]:
            run.step(1 / 60.0)
        return run

    def test_a_downward_flick_on_the_beat_marks_it(self):
        run = self.at_beat(1)
        run.hand.to(500.0, 400.0 - M.FLICK - 5)
        run.step(1 / 60.0)
        self.assertTrue(run.beaten[0])
        self.assertEqual(run.slips, 0)

    def test_a_beat_not_beaten_is_a_slip(self):
        run = self.at_beat(1, 1)
        self.assertEqual(run.slips, 1)

    def test_a_stray_beat_slips_only_when_time_is_strict(self):
        for rung, slips in ((1, 0), (10, 1)):
            run = M.Run(M.deal(rung, seed=1))
            run.hand.to(500.0, 400.0)
            settle(run, 0.5)
            run.hand.to(500.0, 400.0 - M.FLICK - 5)
            run.step(1 / 60.0)
            self.assertEqual(run.slips, slips, rung)

    def test_a_click_on_the_section_on_its_beat_brings_it_in(self):
        for s in range(40):
            piece = M.deal(1, seed=s)
            if piece.cues[0].kind == 'enter':
                break
        cue = piece.cues[0]
        run = M.Run(piece)
        while run.t < piece.times[cue.beat - 1]:
            run.hand.to(500.0, 400.0)
            run.step(1 / 60.0)
            run.hand.to(500.0, 340.0)
            run.step(1 / 60.0)
        self.assertFalse(run.playing[cue.section])
        x, y = M.spot(cue.section)
        run.hand.to(x, y)
        run.press()
        self.assertTrue(run.playing[cue.section])
        self.assertTrue(run.done[0])

    def test_the_drum_sounds_on_every_beat(self):
        run = M.Run(M.deal(1, seed=1))
        while run.result is None:
            run.step(1 / 60.0)
        drums = [n for n in run.notes if n.voice == M.DRUM]
        self.assertGreaterEqual(len(drums), 3)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('conductor', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('conductor', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('conductor', M), 0)


if __name__ == '__main__':
    unittest.main()
