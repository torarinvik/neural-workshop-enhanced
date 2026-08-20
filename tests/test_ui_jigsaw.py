#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The jigsaw puzzles: scrambling, the swap minimum, and the screen.

The screen tests run against a tiny generated photograph library in a
temporary folder, so nothing here needs the real DIV2K download — an
absent library is itself one of the states under test.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import os
import random
import shutil
import tempfile
import unittest

from uisupport import (JigsawPuzzle, TASKS, close_overlays, datasets,
                       display, key, media, needs_ui, reset_window, state,
                       taskoptions)

from neural_workshop.ui import jigsaw


class ScrambleTests(unittest.TestCase):
    """The shuffle, and the minimum it is measured against."""

    def setUp(self):
        self.rng = random.Random(20260820)

    def test_a_scramble_is_a_permutation_and_never_the_answer(self):
        for side in (2, 3, 4, 6):
            for _try in range(50):
                order = jigsaw.scramble(side, self.rng)
                self.assertEqual(sorted(order), list(range(side * side)))
                self.assertTrue(any(tile != position
                                    for position, tile in enumerate(order)))

    def test_the_minimum_is_size_minus_cycles(self):
        self.assertEqual(jigsaw.minimum_swaps([0, 1, 2, 3]), 0)
        self.assertEqual(jigsaw.minimum_swaps([1, 0, 2, 3]), 1)
        self.assertEqual(jigsaw.minimum_swaps([1, 2, 0, 3]), 2)
        self.assertEqual(jigsaw.minimum_swaps([1, 0, 3, 2]), 2)
        self.assertEqual(jigsaw.minimum_swaps([3, 2, 1, 0]), 2)

    def test_the_minimum_really_is_the_minimum(self):
        """Check against brute force on every permutation of four —
        no swap sequence shorter than the formula's answer sorts it."""
        for order in itertools.permutations(range(4)):
            best = None
            frontier = {order: 0}
            while frontier:
                for candidate, cost in frontier.items():
                    if list(candidate) == sorted(candidate):
                        best = cost
                        break
                else:
                    grown = {}
                    for candidate, cost in frontier.items():
                        for one in range(4):
                            for two in range(one + 1, 4):
                                swapped = list(candidate)
                                swapped[one], swapped[two] = \
                                    swapped[two], swapped[one]
                                grown.setdefault(tuple(swapped), cost + 1)
                    frontier = grown
                    continue
                break
            self.assertEqual(jigsaw.minimum_swaps(list(order)), best,
                             order)

    def test_solving_along_the_cycles_meets_the_minimum(self):
        for _try in range(100):
            order = jigsaw.scramble(4, self.rng)
            par = jigsaw.minimum_swaps(order)
            swaps = 0
            for position in range(len(order)):
                while order[position] != position:
                    tile = order[position]
                    order[position], order[tile] = order[tile], \
                        order[position]
                    swaps += 1
            self.assertEqual(swaps, par)


class DatasetTests(unittest.TestCase):
    """The DIV2K library is catalogued and fetched by the zip route."""

    def test_div2k_is_catalogued(self):
        self.assertIs(datasets.by_key('div2k'), datasets.DIV2K)
        self.assertEqual(datasets.DIV2K.kind, 'image')
        self.assertTrue(datasets.DIV2K.archives)
        for url in datasets.DIV2K.archives:
            self.assertTrue(url.startswith('https://'), url)

    def test_the_validation_archive_comes_first(self):
        """Asking for the default hundred images should cost one
        download of the small archive, not the three-and-a-half
        gigabyte training set."""
        self.assertIn('valid', datasets.DIV2K.archives[0])
        self.assertIn('train', datasets.DIV2K.archives[1])

    def test_the_zip_route_unpacks_numbered_and_idempotent(self):
        """A local archive stands in for the real one: fetching
        unpacks its images onto the numbered names every other route
        uses, a second fetch adds nothing, and the scratch zip is
        cleaned away."""
        import zipfile
        tmp = tempfile.mkdtemp()
        saved = datasets.datasets_dir
        datasets.datasets_dir = lambda: tmp
        try:
            archive_path = os.path.join(tmp, 'source.zip')
            with zipfile.ZipFile(archive_path, 'w') as archive:
                for name in ('b.png', 'a.png', 'c.png', 'notes.txt'):
                    archive.writestr(name, b'not-really-a-%s' % name.encode())
            stub = datasets.Dataset(
                key='zip-test', repo='x/y', split='train', column='image',
                kind='image', suffix='.png', rows=3, approx_bytes=1,
                archives=('file://' + archive_path,))
            total = datasets.fetch(stub, 3)
            self.assertEqual(total, 3)
            names = [os.path.basename(path)
                     for path in datasets.local_files(stub)]
            self.assertEqual(names, ['0000000.png', '0000001.png',
                                     '0000002.png'])
            with open(datasets.local_files(stub)[0], 'rb') as handle:
                self.assertEqual(handle.read(), b'not-really-a-a.png')
            folder = os.path.join(tmp, 'zip-test')
            self.assertEqual(datasets.fetch(stub, 3), 3)
            self.assertFalse([name for name in os.listdir(folder)
                              if name.endswith('.zip')])
        finally:
            datasets.datasets_dir = saved
            shutil.rmtree(tmp, ignore_errors=True)

    def test_an_archive_dataset_never_takes_the_row_route(self):
        """fetch() must hand archives to the zip route: the rows and
        parquet behind this dataset hold server-side file paths, not
        images, and fetching them would fill the library with junk."""
        calls = []
        original = datasets.fetch_archives
        datasets.fetch_archives = lambda *args, **kw: calls.append(1) or 0
        try:
            datasets.fetch(datasets.DIV2K, 1)
        finally:
            datasets.fetch_archives = original
        self.assertEqual(calls, [1])


@needs_ui
class JigsawScreenTests(unittest.TestCase):
    """The screen: cutting, swapping, scoring, and cleaning up."""

    STUB = datasets.Dataset(
        key='jigsaw-test', repo='x/y', split='train', column='image',
        kind='image', suffix='.png', rows=4, approx_bytes=1)

    def setUp(self):
        close_overlays()
        self.tmp = tempfile.mkdtemp()
        self.saved_dir = datasets.datasets_dir
        datasets.datasets_dir = lambda: self.tmp
        self._make_library()
        self.task = JigsawPuzzle()
        self.task.pool = media.MediaPool(self.STUB, self.task.rng)
        self.task.total_puzzles = 2
        self.task.adaptive = False

    def tearDown(self):
        self.task.close()
        datasets.datasets_dir = self.saved_dir
        shutil.rmtree(self.tmp, ignore_errors=True)
        close_overlays()
        reset_window()

    def _make_library(self):
        import pyglet
        folder = os.path.join(self.tmp, self.STUB.key)
        os.makedirs(folder, exist_ok=True)
        for index, color in enumerate(((255, 40, 40, 255),
                                       (40, 255, 40, 255),
                                       (40, 40, 255, 255))):
            image = pyglet.image.SolidColorImagePattern(
                color).create_image(96, 96)
            path = os.path.join(folder, '%07d.png' % index)
            with open(path, 'wb') as handle:
                image.save(path, file=handle)

    def _solve(self):
        """Follow the cycles, which meets the minimum exactly."""
        while self.task.phase == 'solving':
            position = next(p for p, tile in enumerate(self.task.order)
                            if tile != p)
            home = self.task.order[position]
            self.task._pick(position)
            self.task._pick(home)

    def test_starting_deals_a_scrambled_board(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'solving')
        side = self.task.trial_side
        self.assertEqual(len(self.task.tiles), side * side)
        self.assertEqual(sorted(self.task.order),
                         list(range(side * side)))
        self.assertGreater(self.task.par, 0)
        self.task.on_draw()
        wanted = side * side + (1 if self.task.preview else 0)
        self.assertEqual(len(self.task.sprites), wanted)

    def test_two_clicks_swap_and_count(self):
        self.task.start_run()
        before = list(self.task.order)
        self.task._pick(0)
        self.assertEqual(self.task.picked, 0)
        self.task._pick(1)
        self.assertIsNone(self.task.picked)
        self.assertEqual(self.task.swaps, 1)
        self.assertEqual(self.task.order[0], before[1])
        self.assertEqual(self.task.order[1], before[0])

    def test_clicking_a_tile_twice_unpicks_it(self):
        self.task.start_run()
        self.task._pick(3)
        self.task._pick(3)
        self.assertIsNone(self.task.picked)
        self.assertEqual(self.task.swaps, 0)

    def test_solving_at_the_minimum_scores_a_perfect_efficiency(self):
        self.task.start_run()
        self._solve()
        self.assertEqual(self.task.phase, 'solved')
        side, efficiency, _took = self.task.results[-1]
        self.assertEqual(side, self.task.trial_side)
        self.assertEqual(efficiency, 1.0)
        self.assertIn('minimum was %d' % self.task.par, self.task.message)

    def test_an_efficient_solve_grows_the_grid_and_a_loose_one_shrinks(self):
        self.task.adaptive = True
        self.task.side = 3
        self.task.start_run()
        self._solve()
        self.assertEqual(self.task.side, 4)
        self.task.side = 4
        self.task.phase = 'solving'
        self.task.order = jigsaw.scramble(self.task.trial_side,
                                          self.task.rng)
        self.task.par = jigsaw.minimum_swaps(self.task.order)
        self.task.swaps = self.task.par * 3      # flailing
        self.task.results = []
        # finish it along the cycles; the wasted swaps stay counted
        while any(t != p for p, t in enumerate(self.task.order)):
            position = next(p for p, tile in enumerate(self.task.order)
                            if tile != p)
            home = self.task.order[position]
            self.task._pick(position)
            self.task._pick(home)
        self.assertEqual(self.task.side, 3)

    def test_a_run_ends_with_a_score_on_both_axes(self):
        self.task.start_run()
        for _puzzle in range(2):
            self._solve()
            self.task.feedback_until = 0
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        tally = self.task.score()
        self.assertEqual(tally['puzzles'], 2)
        self.assertEqual(tally['efficiency'], 100)
        self.assertIn('swap efficiency', self.task.message)

    def test_an_absent_library_says_so_and_stays_calm(self):
        self.task.pool = media.MediaPool(datasets.Dataset(
            key='never-fetched', repo='x/y', split='train', column='image',
            kind='image', suffix='.png', rows=1, approx_bytes=1))
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
        self.task.start_run()
        self.task.close()
        self.assertIsNone(JigsawPuzzle.instance)
        self.assertNotIn(self.task, display.open_overlays())

    def test_a_second_task_closes_the_first(self):
        first = self.task
        self.task = JigsawPuzzle()
        self.task.pool = media.MediaPool(self.STUB, self.task.rng)
        self.assertIs(JigsawPuzzle.instance, self.task)
        self.assertNotIn(first, display.open_overlays())


@needs_ui
class JigsawHubTests(unittest.TestCase):
    """Reachable, named, and configurable."""

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_reasoning(self):
        self.assertIn('jigsaw',
                      [task_id for task_id, _label in TASKS['reasoning']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        launch_task('jigsaw')
        self.assertIsNotNone(JigsawPuzzle.instance)
        JigsawPuzzle.instance.close()

    def test_the_options_note_counts_the_tiles(self):
        note = taskoptions.jigsaw_note({'JIGSAW_SIDE': 5,
                                        'JIGSAW_ADAPTIVE': False})
        self.assertIn('25 tiles', note)
        library = taskoptions.jigsaw_note({'JIGSAW_SIDE': 2,
                                           'JIGSAW_ADAPTIVE': True})
        self.assertTrue('downloaded' in library or 'Readme' in library)


if __name__ == '__main__':
    unittest.main()
