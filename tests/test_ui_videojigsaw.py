#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Video Jigsaw: the jigsaw's board with a playing clip for a picture.

Nothing here needs the real UCF-101 download: the clips are made on
the spot by ffmpeg's own test source.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest

from uisupport import (TASKS, close_overlays, datasets, display, media,
                       needs_ui, reset_window, state, taskoptions)

from neural_workshop import videoclips
from neural_workshop.ui import jigsaw

HAVE_FFMPEG = videoclips.have_ffmpeg()
needs_ffmpeg = unittest.skipUnless(HAVE_FFMPEG, 'ffmpeg not installed')


def make_clip(path, seconds=2, source='testsrc2'):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    '%s=size=320x240:rate=25' % source, '-t', str(seconds),
                    path], check=True)


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@needs_ui
@needs_ffmpeg
class VideoJigsawScreenTests(unittest.TestCase):

    STUB = datasets.Dataset(
        key='videojigsaw-test', repo='x/y', split='train', column='video',
        kind='video', suffix='.avi', rows=3, approx_bytes=1)

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        folder = os.path.join(cls.tmp, cls.STUB.key)
        os.makedirs(folder)
        for index in range(3):
            make_clip(os.path.join(folder, '%07d.avi' % index))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        from neural_workshop.ui.videojigsaw import VideoJigsaw
        self.VideoJigsaw = VideoJigsaw
        close_overlays()
        self.saved_dir = datasets.datasets_dir
        datasets.datasets_dir = lambda: self.tmp
        try:
            os.remove(os.path.join(self.tmp, self.STUB.key,
                                   VideoJigsaw.SEEN))
        except OSError:
            pass
        self.task = VideoJigsaw()
        self.task.pool = media.MediaPool(self.STUB, self.task.rng)
        self.task.clock = FakeClock()
        self.task.total_puzzles = 2
        self.task.adaptive = False

    def tearDown(self):
        self.task.close()
        datasets.datasets_dir = self.saved_dir
        close_overlays()
        reset_window()

    def _solve(self):
        while self.task.phase == 'solving':
            position = next(p for p, tile in enumerate(self.task.order)
                            if tile != p)
            home = self.task.order[position]
            self.task._pick(position)
            self.task._pick(home)

    def test_it_deals_a_wide_grid_of_a_decoded_clip(self):
        self.task.start_pieces = 12
        self.task.start_run()
        self.assertEqual(self.task.phase, 'solving')
        self.assertEqual((self.task.columns, self.task.rows), (4, 3))
        self.assertGreater(len(self.task.clip), 10)
        self.assertEqual(len(self.task.sprites), 12)
        self.task.on_draw()

    def test_two_pieces_and_hundreds(self):
        self.task.start_pieces = 2
        self.task.start_run()
        self.assertEqual(self.task.trial_pieces, 2)
        self._solve()
        self.assertEqual(self.task.phase, 'solved')
        self.task.close()
        self.task = self.VideoJigsaw()
        self.task.pool = media.MediaPool(self.STUB, self.task.rng)
        self.task.clock = FakeClock()
        self.task.start_pieces = 1200
        self.task.start_run()
        self.assertEqual((self.task.columns, self.task.rows), (40, 30))
        self.task.on_draw()
        self._solve()
        self.assertEqual(self.task.swaps, self.task.par)

    def test_the_tiles_play_without_a_sprite_being_touched(self):
        """One texture carries the clip, so the frame moves on under
        every tile at once and the picture on the board changes."""
        import pyglet
        self.task.start_pieces = 300
        self.task.start_run()
        regions = [sprite.image for sprite in self.task.sprites]

        def pixels():
            return self.task.image.get_image_data().get_data(
                'RGB', self.task.image.width * 3)

        before = pixels()
        self.task.clock.now += 1.0
        self.task.update(1 / 30.)
        self.assertEqual(self.task.frame, videoclips.FPS)
        self.assertNotEqual(pixels(), before)
        self.assertEqual([id(sprite.image) for sprite in self.task.sprites],
                         [id(region) for region in regions])
        self.task.on_draw()

    def test_the_clip_loops(self):
        self.task.start_run()
        length = len(self.task.clip)
        self.task.clock.now += (length + 3) / float(videoclips.FPS) + 0.01
        self.task.update(1 / 30.)
        self.assertEqual(self.task.frame, 3)

    def test_a_run_ends_scored_and_uses_its_own_rotation(self):
        self.task.start_run()
        for _puzzle in range(2):
            self._solve()
            self.task.clock.now += 5
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['efficiency'], 100)
        folder = os.path.join(self.tmp, self.STUB.key)
        self.assertTrue(os.path.exists(
            os.path.join(folder, 'seen_jigsaw.txt')))
        self.assertFalse(os.path.exists(os.path.join(folder, 'seen.txt')))

    def test_an_absent_library_says_so(self):
        self.task.pool = media.MediaPool(datasets.Dataset(
            key='never-fetched', repo='x/y', split='train', column='video',
            kind='video', suffix='.avi', rows=1, approx_bytes=1))
        self.task.start_run()
        self.assertEqual(self.task.phase, 'ready')
        self.assertIn('Readme', self.task.message)
        self.task.on_draw()

    def test_resizing_keeps_the_puzzle_playing(self):
        self.task.start_run()
        order = list(self.task.order)
        state.window.set_size(720, 560)
        display.ensure_laid_out()
        self.task.relayout()
        self.assertEqual(self.task.order, order)
        self.task.clock.now += 0.5
        self.task.update(0)
        self.task.on_draw()

    def test_closing_gives_back_its_handlers(self):
        self.task.start_run()
        self.task.close()
        self.assertIsNone(self.VideoJigsaw.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class VideoJigsawHubTests(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_reasoning_beside_the_jigsaw(self):
        ids = [task_id for task_id, _label in TASKS['reasoning']]
        self.assertEqual(ids.index('video_jigsaw'),
                         ids.index('jigsaw') + 1)
        self.assertIn('video_sequence', ids)
        self.assertNotIn('video_puzzle', ids)

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.videojigsaw import VideoJigsaw
        launch_task('video_jigsaw')
        self.assertIsNotNone(VideoJigsaw.instance)
        VideoJigsaw.instance.close()

    def test_the_options_note_counts_the_tiles(self):
        note = taskoptions.video_jigsaw_note(
            {'VIDEO_JIGSAW_PIECES': 300, 'VIDEO_JIGSAW_ADAPTIVE': True})
        self.assertIn('20 columns by 15 rows', note)

    def test_the_env_has_the_jigsaw_ports_and_a_clock(self):
        from nwenv import catalog
        env = catalog.env_class('video_jigsaw')
        self.assertEqual(env.ports, jigsaw.PORTS)
        self.assertTrue(env.clocked)
        self.assertEqual(catalog.env_class('jigsaw').ports, jigsaw.PORTS)


if __name__ == '__main__':
    unittest.main()
