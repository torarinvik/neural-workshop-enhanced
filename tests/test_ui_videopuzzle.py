#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The video puzzles: cutting clips, the remote zip route, and the screen.

Nothing here needs the real UCF-101 download. The clips are made on the
spot by ffmpeg's own test source, and the remote route is exercised
against a zip served from a local HTTP server, so the range requests
are real requests and only the network is missing.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import functools
import http.server
import os
import random
import shutil
import subprocess
import tempfile
import threading
import unittest
import zipfile

from uisupport import (TASKS, close_overlays, datasets, display, media,
                       needs_ui, reset_window, state, taskoptions)

from neural_workshop import videoclips

HAVE_FFMPEG = videoclips.have_ffmpeg()
needs_ffmpeg = unittest.skipUnless(HAVE_FFMPEG, 'ffmpeg not installed')


def make_clip(path, seconds=4, source='testsrc2'):
    """A small moving test clip at *path*."""
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    '%s=size=320x240:rate=25' % source, '-t', str(seconds),
                    path], check=True)


class CuttingTests(unittest.TestCase):
    """Pieces are equal, contiguous, and a still clip is recognised."""

    def frames(self, count, size=12):
        return [bytes([index % 256]) * size for index in range(count)]

    def test_pieces_are_equal_and_in_order(self):
        frames = self.frames(23)
        pieces = videoclips.cut(frames, 4)
        self.assertEqual([len(piece) for piece in pieces], [5, 5, 5, 5])
        self.assertEqual(sum(pieces, []), frames[:20])

    def test_too_few_frames_cut_into_nothing(self):
        self.assertEqual(videoclips.cut(self.frames(2), 3), [])
        self.assertEqual(videoclips.cut(self.frames(9), 0), [])

    def test_a_still_clip_is_not_lively(self):
        still = [b'\x40' * 300] * 30
        self.assertFalse(videoclips.lively(videoclips.cut(still, 3)))
        moving = [bytes([index * 8]) * 300 for index in range(30)]
        self.assertTrue(videoclips.lively(videoclips.cut(moving, 3)))

    def test_a_shuffle_is_never_the_answer(self):
        from neural_workshop.ui import videopuzzle
        rng = random.Random(4)
        for pieces in range(videopuzzle.FEWEST, videopuzzle.MOST + 1):
            for _try in range(30):
                order = videopuzzle.shuffle(pieces, rng)
                self.assertEqual(sorted(order), list(range(pieces)))
                self.assertNotEqual(order, list(range(pieces)))

    def test_the_layout_picks_a_row_for_a_wide_room(self):
        from neural_workshop.ui import videopuzzle
        self.assertEqual(videopuzzle.best_columns(3, 1200, 200, 4 / 3), 3)
        self.assertEqual(videopuzzle.best_columns(4, 400, 400, 4 / 3), 2)


@needs_ffmpeg
class DecodingTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_clip_decodes_to_sized_frames_at_the_set_rate(self):
        path = os.path.join(self.tmp, 'clip.avi')
        make_clip(path, seconds=2)
        clip = videoclips.decode(path)
        self.assertIsNotNone(clip)
        self.assertEqual(len(clip.frames[0]),
                         videoclips.WIDTH * videoclips.HEIGHT * 3)
        self.assertAlmostEqual(len(clip.frames), 2 * videoclips.FPS,
                               delta=2)

    def test_a_long_clip_is_trimmed(self):
        path = os.path.join(self.tmp, 'long.avi')
        make_clip(path, seconds=12)
        clip = videoclips.decode(path)
        self.assertLessEqual(len(clip.frames),
                             videoclips.LONGEST * videoclips.FPS + 1)

    def test_a_broken_file_decodes_to_nothing(self):
        path = os.path.join(self.tmp, 'broken.avi')
        with open(path, 'wb') as handle:
            handle.write(b'not a video at all')
        self.assertIsNone(videoclips.decode(path))


class _Quiet(http.server.SimpleHTTPRequestHandler):
    """Serves byte ranges, which the standard handler does not."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        span = self.headers.get('Range')
        path = self.translate_path(self.path)
        if not span or not os.path.isfile(path):
            return super().do_GET()
        size = os.path.getsize(path)
        start, _dash, end = span.split('=', 1)[1].partition('-')
        start, end = int(start), min(int(end or size - 1), size - 1)
        with open(path, 'rb') as handle:
            handle.seek(start)
            body = handle.read(end - start + 1)
        self.send_response(206)
        self.send_header('Content-Range', 'bytes %d-%d/%d'
                         % (start, end, size))
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class RemoteZipTests(unittest.TestCase):
    """The UCF-101 route reads members out of a zip it never downloads."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.served = os.path.join(self.tmp, 'served')
        os.makedirs(self.served)
        self.saved = datasets.datasets_dir
        datasets.datasets_dir = lambda: os.path.join(self.tmp, 'library')
        handler = functools.partial(_Quiet, directory=self.served)
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0),
                                                      handler)
        threading.Thread(target=self.server.serve_forever,
                         daemon=True).start()
        self.names = ['Class%02d/v_%02d.avi' % (index % 7, index)
                      for index in range(40)]
        with zipfile.ZipFile(os.path.join(self.served, 'big.zip'),
                             'w') as archive:
            for name in self.names:
                archive.writestr(name, name.encode() * 2000)
            archive.writestr('README.txt', b'hello')

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        datasets.datasets_dir = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def stub(self, **extra):
        url = 'http://127.0.0.1:%d/big.zip' % self.server.server_address[1]
        fields = dict(key='remote-test', repo='x/y', split='train',
                      column='video', kind='video', suffix='.avi', rows=40,
                      approx_bytes=1, archives=(url,), remote=True)
        fields.update(extra)
        return datasets.Dataset(**fields)

    def test_ucf101_is_catalogued_remote_and_under_fifty_gigabytes(self):
        ucf = datasets.by_key('ucf101')
        self.assertIs(ucf, datasets.UCF101)
        self.assertTrue(ucf.remote)
        self.assertEqual(ucf.kind, 'video')
        self.assertLessEqual(ucf.budget_bytes, 50 * 10 ** 9)
        self.assertLessEqual(ucf.rows * ucf.approx_bytes, ucf.budget_bytes)

    def test_a_partial_fetch_is_spread_numbered_and_idempotent(self):
        stub = self.stub()
        self.assertEqual(datasets.fetch(stub, 10), 10)
        files = datasets.local_files(stub)
        numbers = sorted(int(os.path.basename(p)[:7]) for p in files)
        # spread across the archive, not its first ten entries
        self.assertNotEqual(numbers, list(range(10)))
        for path in files:
            index = int(os.path.basename(path)[:7])
            with open(path, 'rb') as handle:
                self.assertEqual(handle.read(),
                                 sorted(self.names)[index].encode() * 2000)
        self.assertEqual(datasets.fetch(stub, 10), 10)
        self.assertEqual(datasets.fetch(stub, 15), 15)
        folder = os.path.join(self.tmp, 'library', 'remote-test')
        self.assertFalse([n for n in os.listdir(folder)
                          if n.endswith('.zip')])

    def test_the_budget_is_never_crossed(self):
        member = len(self.names[0]) * 2000
        stub = self.stub(budget_bytes=member * 5 + member // 2)
        self.assertEqual(datasets.fetch(stub, 40), 5)
        self.assertLessEqual(datasets.library_bytes(stub),
                             stub.budget_bytes)


@needs_ui
@needs_ffmpeg
class VideoPuzzleScreenTests(unittest.TestCase):
    """The screen: dealing, playing, swapping, scoring, cleaning up."""

    STUB = datasets.Dataset(
        key='video-test', repo='x/y', split='train', column='video',
        kind='video', suffix='.avi', rows=3, approx_bytes=1)

    @classmethod
    def setUpClass(cls):
        cls.clips = tempfile.mkdtemp()
        for index, source in enumerate(('testsrc2', 'testsrc', 'rgbtestsrc')):
            make_clip(os.path.join(cls.clips, '%07d.avi' % index),
                      seconds=3, source=source)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.clips, ignore_errors=True)

    def setUp(self):
        from neural_workshop.ui.videopuzzle import VideoPuzzle
        close_overlays()
        self.tmp = tempfile.mkdtemp()
        self.saved_dir = datasets.datasets_dir
        datasets.datasets_dir = lambda: self.tmp
        shutil.copytree(self.clips, os.path.join(self.tmp, self.STUB.key))
        self.task = VideoPuzzle()
        self.task.pool = media.MediaPool(self.STUB, self.task.rng)
        self.task.total_puzzles = 2
        self.task.adaptive = False
        self.now = 1000.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        datasets.datasets_dir = self.saved_dir
        shutil.rmtree(self.tmp, ignore_errors=True)
        close_overlays()
        reset_window()

    def _solve(self):
        while self.task.phase == 'solving':
            position = next(p for p, piece in enumerate(self.task.order)
                            if piece != p)
            home = self.task.order[position]
            self.task._pick(position)
            self.task._pick(home)

    def test_starting_deals_shuffled_playing_pieces(self):
        self.task.start_pieces = 4
        self.task.start_run()
        self.assertEqual(self.task.phase, 'solving')
        self.assertEqual(len(self.task.segments), 4)
        lengths = {len(piece) for piece in self.task.segments}
        self.assertEqual(len(lengths), 1)
        self.assertNotEqual(self.task.order, [0, 1, 2, 3])
        self.task.on_draw()
        self.assertEqual(len(self.task.sprites), 4)
        first = [sprite.image for sprite in self.task.sprites]
        self.now += 0.5
        self.task.update(0)
        self.assertNotEqual([sprite.image for sprite in self.task.sprites],
                            first)

    def test_every_piece_plays_in_step(self):
        self.task.start_run()
        self.now += 0.4
        self.task.update(0)
        frame = self.task.frame
        for position, sprite in enumerate(self.task.sprites):
            piece = self.task.order[position]
            self.assertIs(sprite.image, self.task.segments[piece][frame])

    def test_pieces_sit_above_the_band_and_do_not_overlap(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        for pieces in range(3, 10):
            self.task.trial_pieces = pieces
            rects = self.task._tile_rects()
            floor = above_the_band(from_bottom_edge(56))
            for left, bottom, across, down in rects:
                self.assertGreaterEqual(bottom, floor - 0.5)
                self.assertLessEqual(left + across, state.window.width)
            for one in range(pieces):
                for two in range(one + 1, pieces):
                    a, b = rects[one], rects[two]
                    apart = (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0]
                             or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])
                    self.assertTrue(apart, (pieces, one, two))

    def test_solving_at_the_minimum_is_green(self):
        self.task.start_run()
        self._solve()
        self.assertEqual(self.task.phase, 'solved')
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.results[-1][1], 1.0)

    def test_a_loose_solve_is_red_and_shrinks_the_cut(self):
        self.task.adaptive = True
        self.task.start_pieces = 5
        self.task.start_run()
        self.task.swaps = self.task.par * 3
        self._solve()
        self.assertFalse(self.task.verdict_shown[0])
        self.assertEqual(self.task.pieces, 4)

    def test_a_run_ends_with_a_score(self):
        self.task.start_run()
        for _clip in range(2):
            self._solve()
            self.now = self.task.feedback_until
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['puzzles'], 2)
        self.assertIn('swap efficiency', self.task.message)

    def test_an_absent_library_says_so(self):
        self.task.pool = media.MediaPool(datasets.Dataset(
            key='never-fetched', repo='x/y', split='train', column='video',
            kind='video', suffix='.avi', rows=1, approx_bytes=1))
        self.task.start_run()
        self.assertEqual(self.task.phase, 'ready')
        self.assertIn('Readme', self.task.message)
        self.task.on_draw()

    def test_resizing_keeps_the_puzzle(self):
        self.task.start_run()
        order = list(self.task.order)
        state.window.set_size(720, 560)
        display.ensure_laid_out()
        self.task.relayout()
        self.assertEqual(self.task.order, order)
        self.task.on_draw()

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.videopuzzle import VideoPuzzle
        self.task.start_run()
        self.task.close()
        self.assertIsNone(VideoPuzzle.instance)
        self.assertNotIn(self.task, display.open_overlays())

    def test_the_boundary_pays_a_solved_clip(self):
        from nwenv import catalog
        self.task.close()
        shutil.copytree(self.clips,
                        os.path.join(self.tmp, datasets.UCF101.key))
        env = catalog.env_class('video_puzzle')(seed=0, pieces=3,
                                                puzzles=2)
        scalars = []
        try:
            for _step in range(400):
                task = env.task
                if task.phase == 'solving':
                    wrong = next((where for where, piece
                                  in enumerate(task.order)
                                  if piece != where), 0)
                    port = (wrong if task.picked is None
                            else task.order.index(task.picked))
                else:
                    port = 0
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        self.assertEqual(scalars, [1.0])


@needs_ui
class VideoPuzzleHubTests(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_reasoning(self):
        self.assertIn('video_puzzle',
                      [task_id for task_id, _label in TASKS['reasoning']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.videopuzzle import VideoPuzzle
        launch_task('video_puzzle')
        self.assertIsNotNone(VideoPuzzle.instance)
        VideoPuzzle.instance.close()

    def test_the_options_note_names_the_cut(self):
        note = taskoptions.video_puzzle_note({'VIDEO_PUZZLE_PIECES': 6,
                                              'VIDEO_PUZZLE_ADAPTIVE': False})
        self.assertIn('6 stretches', note)


if __name__ == '__main__':
    unittest.main()
