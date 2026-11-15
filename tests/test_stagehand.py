#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stagehand: the script, the props, the cues, the cameras, the
boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import stagehand as M


def show_with(rung, want, seeds=400):
    """A show whose first line satisfies *want*."""
    for s in range(seeds):
        show = M.deal(rung, seed=s)
        if want(show.lines[0]):
            return show
    raise AssertionError('no such show')


def point(run, p):
    q = run.body(p)
    run.hand.to(q[0], q[1])


def click(run, p):
    point(run, p)
    run.press()
    run.step(1 / 60.0)
    run.release()


def carry(run, p, mark):
    point(run, p)
    run.press()
    x, z = M.spot_of(mark)
    q = run.view().see((x, 0.0, z))
    run.hand.to(q[0], q[1])
    run.step(1 / 60.0)
    run.release()


class TheScript(unittest.TestCase):

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 20, 40)}
        self.assertFalse(g[1].spot or g[1].waits)
        self.assertTrue(g[4].spot and g[4].waits == ('bell',))
        self.assertTrue(g[7].cut and not g[4].cut)
        self.assertIn('actor', g[7].waits)
        self.assertTrue(g[10].decoy and not g[10].named and g[7].named)
        self.assertIn(4, g[13].cams)
        self.assertNotIn(4, g[10].cams)
        self.assertGreater(g[40].lines, g[20].lines)
        self.assertLess(g[40].window, g[1].window)

    def test_a_move_ends_on_a_free_mark_on_the_stage(self):
        for rung in (1, 7, 25):
            for s in range(6):
                show = M.deal(rung, seed=s)
                self.assertEqual(len(show.lines), show.level.lines)
                self.assertEqual(len(set(show.marks)), len(show.marks))
                for line in show.lines:
                    if line.kind == 'move':
                        self.assertTrue(0 <= line.mark[0] < M.COLS)
                        self.assertTrue(0 <= line.mark[1] < M.ROWS)

    def test_key_cues_name_their_key_only_at_the_bottom(self):
        low = show_with(1, lambda line: line.kind == 'key')
        self.assertIn('press %s' % M.LETTERS[low.lines[0].key],
                      low.lines[0].text)
        high = show_with(10, lambda line: line.kind == 'key')
        self.assertNotIn('press', high.lines[0].text)

    def test_the_reference_passes_and_idle_and_random_fail(self):
        for rung in (1, 4, 7, 10, 13, 16, 22, 35):
            for s in range(2):
                show = M.deal(rung, seed=s)
                self.assertTrue(M.play(show)[0], (rung, s))
                self.assertFalse(M.play(show, lambda run: [])[0])
                draw = random.Random(s)
                self.assertFalse(M.play(show, lambda run: [
                    draw.randrange(M.PORTS)])[0])


class TheProps(unittest.TestCase):

    def test_dragging_a_prop_to_its_mark_does_the_line(self):
        show = show_with(1, lambda line: line.kind == 'move')
        run = M.Run(show)
        line = show.lines[0]
        carry(run, line.prop, line.mark)
        self.assertEqual(run.at[line.prop], line.mark)
        self.assertEqual(run.line_no, 1)

    def test_a_prop_dropped_on_another_goes_back(self):
        show = show_with(1, lambda line: line.kind == 'move')
        run = M.Run(show)
        p = show.lines[0].prop
        other = next(k for k in range(len(run.at)) if k != p)
        carry(run, p, run.at[other])
        self.assertEqual(run.at[p], show.marks[p])
        self.assertIsNone(run.result)

    def test_a_click_puts_the_spotlight_on_and_the_wrong_prop_fails(self):
        show = show_with(4, lambda line: line.kind == 'spot'
                         and not line.wait)
        run = M.Run(show)
        p = show.lines[0].prop
        click(run, p)
        self.assertEqual((run.lit, run.line_no), (p, 1))
        run = M.Run(show)
        click(run, next(k for k in range(len(run.at)) if k != p))
        self.assertFalse(run.result[0])

    def test_left_is_the_audiences_left_whatever_the_camera(self):
        run = M.Run(M.deal(13, seed=1))
        left, right = M.spot_of((0, 1)), M.spot_of((4, 1))
        self.assertLess(left[0], right[0])
        run.cam = 0
        see = lambda m: run.view().see((m[0], 0.0, m[1]))[0]   # noqa: E731
        self.assertLess(see(left), see(right))
        run.cam = 4
        self.assertGreater(see(left), see(right))


class TheCues(unittest.TestCase):

    def test_a_cue_before_its_moment_fails_and_in_it_passes(self):
        show = show_with(4, lambda line: line.kind == 'key'
                         and line.wait == 'bell')
        line = show.lines[0]
        run = M.Run(show)
        M.act(run, M.KEY + line.key)
        self.assertFalse(run.result[0])
        run = M.Run(show)
        while not run.open():
            run.step(1 / 60.0)
        rings = [n for n in run.notes if n.voice == M.BELL]
        self.assertEqual(len(rings), line.count)
        M.act(run, M.KEY + line.key)
        self.assertEqual(run.line_no, 1)

    def test_the_wrong_key_fails_and_a_missed_moment_fails(self):
        show = show_with(1, lambda line: line.kind == 'key')
        run = M.Run(show)
        M.act(run, M.KEY + (show.lines[0].key + 1) % 5)
        self.assertFalse(run.result[0])
        run = M.Run(show)
        for _k in range(int(show.level.pace * 60) + 5):
            run.step(1 / 60.0)
        self.assertFalse(run.result[0])

    def test_a_false_bell_rings_a_different_number_first(self):
        show = show_with(10, lambda line: line.wait == 'bell'
                         and line.decoy)
        line = show.lines[0]
        self.assertNotEqual(line.decoy, line.count)
        run = M.Run(show)
        while not run.open():
            run.step(1 / 60.0)
        rings = [n.t for n in run.notes if n.voice == M.BELL]
        self.assertEqual(len(rings), line.decoy + line.count)
        gaps = [b - a for a, b in zip(rings, rings[1:])]
        self.assertEqual(sum(1 for g in gaps if g > 1.0), 1)

    def test_the_drum_follows_a_whistle_that_is_not_it(self):
        show = show_with(13, lambda line: line.wait == 'drum'
                         and line.decoy)
        run = M.Run(show)
        while not any(n.voice == M.WHISTLE for n in run.notes):
            run.step(1 / 60.0)
        self.assertFalse(run.open())
        while not run.open():
            run.step(1 / 60.0)
        self.assertTrue(any(n.voice == M.DRUM for n in run.notes))

    def test_the_actor_has_to_arrive_first(self):
        show = show_with(7, lambda line: line.wait == 'actor')
        run = M.Run(show)
        self.assertFalse(run.open())
        start = run.actor
        while not run.open():
            run.step(1 / 60.0)
        self.assertNotEqual(run.actor, start)
        goal = run._beside(show.lines[0].to)
        self.assertAlmostEqual(run.actor[0], goal[0], places=3)

    def test_the_camera_cuts_from_rung_7(self):
        self.assertFalse(M.deal(4, seed=1).cuts)
        show = M.deal(8, seed=1)
        self.assertTrue(show.cuts)
        run = M.Run(show)
        while run.t < show.cuts[0][0] + 0.05:
            run.step(1 / 60.0)
            if run.result is not None:
                break
        if run.result is None:
            self.assertEqual(run.cam, show.cuts[0][1])


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('stagehand', 7, pilot, seed=1, steps=6000),
                         [1.0])
        self.assertEqual(drive('stagehand', 1, lambda t: None, seed=1,
                               steps=3600), [-1.0])

    def test_the_agent_hears_the_bell(self):
        from nwenv import catalog
        env = catalog.env_class('stagehand')(seed=3, rung=5, trials=3,
                                             adaptive=False)
        try:
            heard = 0
            for _k in range(1500):
                task = env.task
                port = None
                if task.phase == 'playing' and task.run is not None:
                    ports = M.autopilot(task.run)
                    port = ports[0] if ports else None
                env.step(port)
                chunk = env._public_audio
                if chunk:
                    heard += len(chunk['audio_pcm'])
            self.assertGreater(heard, 0)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()
