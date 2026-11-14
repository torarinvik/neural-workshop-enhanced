#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""What Happens Next: the decoys, the ladder, the boundary, the screen.

The model is tested on made-up frames; the screen on clips ffmpeg makes
on the spot, so nothing here needs the real UCF-101 download.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
import unittest

from uisupport import TASKS, close_overlays, datasets, display, media, \
    needs_ui, reset_window, state, taskoptions

from neural_workshop import videoclips, whatnext as W

HAVE_FFMPEG = videoclips.have_ffmpeg()
needs_ffmpeg = unittest.skipUnless(HAVE_FFMPEG, 'ffmpeg not installed')


def moving(count, seed=0, size=600):
    """Frames that change steadily, so every stretch is its own."""
    return [bytes([(seed * 37 + index * 6 + k) % 256
                   for k in range(0, size * 3, 3)])
            for index in range(count)]


class TheLadder(unittest.TestCase):

    def test_options_grow_from_two_to_six(self):
        self.assertEqual(W.grade(1).choices, 2)
        self.assertEqual(W.grade(30).choices, 6)
        last = W.grade(1)
        for rung in range(2, 40):
            level = W.grade(rung)
            self.assertGreaterEqual(level.choices, last.choices)
            self.assertLessEqual(level.context, last.context)
            last = level

    def test_the_decoys_come_in_on_their_rungs(self):
        self.assertEqual(W.grade(3).kinds, ('other',))
        self.assertIn('reversed', W.grade(4).kinds)
        self.assertIn('later', W.grade(8).kinds)
        self.assertIn('skipped', W.grade(12).kinds)
        self.assertNotIn('other', W.grade(16).kinds)
        self.assertEqual(W.grade(20).context, 1.0)
        self.assertLess(W.grade(21).context, 1.0)

    def test_there_are_enough_kinds_for_the_options_on_every_rung(self):
        for rung in range(1, 40):
            level = W.grade(rung)
            if 'other' not in level.kinds:
                self.assertGreaterEqual(len(level.kinds),
                                        level.choices - 1, rung)


class ThePuzzles(unittest.TestCase):

    def test_every_rung_builds_from_an_eight_second_clip(self):
        frames = moving(120)
        others = [moving(100, seed=s + 3) for s in range(6)]
        for rung in range(1, 32):
            puzzle = W.build(frames, others, W.grade(rung),
                             random.Random(rung))
            self.assertIsNotNone(puzzle, rung)
            self.assertEqual(len(puzzle.options), W.grade(rung).choices)
            self.assertEqual(puzzle.kinds.count('truth'), 1)
            self.assertEqual(puzzle.kinds[puzzle.answer], 'truth')

    def test_the_truth_is_what_follows_the_opening(self):
        frames = moving(120)
        puzzle = W.build(frames, [moving(90, 5)], W.grade(9),
                         random.Random(3))
        cut, piece = W.spans(120)
        self.assertEqual(puzzle.opening, frames[:cut])
        self.assertEqual(list(puzzle.options[puzzle.answer]),
                         frames[cut:cut + piece])

    def test_the_backwards_decoy_is_the_truth_reversed(self):
        frames = moving(120)
        puzzle = W.build(frames, [], W.grade(17), random.Random(4))
        backwards = puzzle.options[puzzle.kinds.index('reversed')]
        self.assertEqual(list(backwards),
                         list(puzzle.options[puzzle.answer])[::-1])

    def test_options_are_all_the_same_length(self):
        puzzle = W.build(moving(120), [moving(80, 9)] * 2, W.grade(13),
                         random.Random(5))
        self.assertEqual(len({len(o) for o in puzzle.options}), 1)

    def test_a_still_clip_makes_no_puzzle(self):
        still = [b'\x40' * 1800] * 120
        self.assertIsNone(W.build(still, [], W.grade(17),
                                  random.Random(1)))

    def test_the_answer_moves_about(self):
        answers = {W.build(moving(120), [moving(90, 3)], W.grade(6),
                           random.Random(seed)).answer
                   for seed in range(40)}
        self.assertEqual(answers, {0, 1, 2})

    def test_past_twenty_less_of_the_opening_is_shown(self):
        frames = moving(120)
        full = W.build(frames, [], W.grade(20), random.Random(1))
        short = W.build(frames, [], W.grade(28), random.Random(1))
        self.assertLess(len(short.opening), len(full.opening))
        self.assertEqual(short.opening[-1], full.opening[-1])


def make_clip(path, source, seconds=6):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    '%s=size=320x240:rate=25' % source, '-t', str(seconds),
                    path], check=True)


STUB = datasets.Dataset(
    key='whatnext-test', repo='x/y', split='train', column='video',
    kind='video', suffix='.avi', rows=3, approx_bytes=1)


class Library:
    """A folder of moving test clips standing in for UCF-101."""

    def __enter__(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = datasets.datasets_dir
        datasets.datasets_dir = lambda: self.tmp
        folder = os.path.join(self.tmp, STUB.key)
        os.makedirs(folder)
        for index, source in enumerate(('testsrc2', 'mandelbrot',
                                        'testsrc', 'rgbtestsrc')):
            make_clip(os.path.join(folder, '%07d.avi' % index), source)
        return self

    def __exit__(self, *ignored):
        datasets.datasets_dir = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)


def install(task):
    task.pool = media.MediaPool(STUB, task.rng)
    task.rotation = media.Rotation(task.pool, 'seen_next.txt')


@needs_ui
@needs_ffmpeg
class TheScreen(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.library = Library().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.library.__exit__()

    def setUp(self):
        from neural_workshop.ui.whatnext import WhatNext
        close_overlays()
        datasets.datasets_dir = lambda: self.library.tmp
        self.task = WhatNext()
        self.task.rng = random.Random(3)
        install(self.task)
        self.task.total_trials = 2
        self.now = 100.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def test_it_deals_and_plays(self):
        self.task.start_rung = 9
        self.task.start_run()
        self.assertEqual(self.task.phase, 'choosing')
        self.assertEqual(len(self.task.puzzle.options), 4)
        opening = len(self.task.puzzle.opening)
        self.now += (opening + 2.5) / float(videoclips.FPS)
        self.task.update(0)
        self.assertEqual(self.task.shown_at[0], opening - 1)
        self.assertEqual(self.task.shown_at[1], 2)
        self.task.on_draw()

    def test_a_click_on_the_answer_is_green(self):
        from pyglet.window import mouse
        self.task.start_run()
        x, y, w, h, _action = self.task.hits[self.task.puzzle.answer]
        self.task.on_mouse_press(int(x + w / 2), int(y + h / 2),
                                 mouse.LEFT, 0)
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 2)
        self.task.on_draw()

    def test_a_wrong_key_is_red_and_names_the_decoy(self):
        from pyglet.window import key
        self.task.start_rung = 5
        self.task.start_run()
        wrong = (self.task.puzzle.answer + 1) % 3
        self.task.on_key_press(key._1 + wrong, 0)
        self.assertFalse(self.task.verdict_shown[0])
        self.assertIn(W.describe(self.task.puzzle.kinds[wrong]),
                      self.task.message)

    def test_a_run_ends_with_a_tally(self):
        self.task.start_run()
        for _trial in range(2):
            self.task.choose(self.task.puzzle.answer)
            self.now = self.task.feedback_until
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['passed'], 2)

    def test_it_keeps_its_own_rotation(self):
        self.task.start_run()
        folder = os.path.join(self.library.tmp, STUB.key)
        self.assertTrue(os.path.exists(os.path.join(folder,
                                                    'seen_next.txt')))
        self.assertFalse(os.path.exists(os.path.join(folder, 'seen.txt')))

    def test_an_absent_library_says_so(self):
        self.task.pool = media.MediaPool(datasets.Dataset(
            key='never-fetched', repo='x/y', split='train', column='video',
            kind='video', suffix='.avi', rows=1, approx_bytes=1))
        self.task.rotation = media.Rotation(self.task.pool, 'x.txt')
        self.task.start_run()
        self.assertEqual(self.task.phase, 'ready')
        self.assertIn('Readme', self.task.message)
        self.task.on_draw()

    def test_everything_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        self.task.start_rung = 24
        self.task.start_run()
        self.task.choose(0)
        for size in ((1824, 1368), (1280, 720), (2560, 1080)):
            state.window.set_size(*size)
            display.ensure_laid_out()
            self.task.relayout()
            floor = above_the_band(from_bottom_edge(58)) - 0.5
            for x, y, w, h, _action in self.task.hits:
                self.assertGreaterEqual(y, floor, size)
            for item in self.task.drawn:
                if hasattr(item, 'content_height'):
                    self.assertGreaterEqual(
                        item.y - item.content_height / 2, floor - 2)

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.whatnext import WhatNext
        self.task.start_run()
        self.task.close()
        self.assertIsNone(WhatNext.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
@needs_ffmpeg
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, pick):
        from nwenv import catalog
        with Library() as library:
            env = catalog.env_class('what_next')(seed=2, rung=6, trials=1,
                                                 adaptive=False)
            install(env.task)
            env.task.start_run()        # it stalled on the real library
            scalars = []
            try:
                for _step in range(400):
                    task = env.task
                    port = (pick(task) if task.phase == 'choosing'
                            and task.puzzle is not None else None)
                    _obs, events, done = env.step(port)
                    scalars += [e['scalar'] for e in events
                                if e.get('type') == 'outcome']
                    if done or scalars:
                        break
            finally:
                env.close()
        return scalars

    def test_the_true_ending_is_paid(self):
        self.assertEqual(self.drive(lambda t: t.puzzle.answer), [1.0])

    def test_a_decoy_is_not(self):
        self.assertEqual(self.drive(lambda t: (t.puzzle.answer + 1) % 3),
                         [-1.0])


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_perception(self):
        self.assertIn('what_next', [t for t, _l in TASKS['perception']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.whatnext import WhatNext
        launch_task('what_next')
        self.assertIsNotNone(WhatNext.instance)
        WhatNext.instance.close()

    def test_the_options_note_names_the_decoys(self):
        note = taskoptions.what_next_note({'WHAT_NEXT_RUNG': 24})
        self.assertIn('backwards', note)
        self.assertIn('opening is shown', note)


if __name__ == '__main__':
    unittest.main()
