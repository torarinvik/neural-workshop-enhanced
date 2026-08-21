#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The media fetcher, exercised without touching the network.

The interesting behaviour is not the download — it is what happens
around it: covering a whole split rather than sampling it forever,
choosing the bulk route when the request is large, and leaving a
usable library behind when something fails part way.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('NW_HEADLESS', '1')

from neural_workshop import datasets                        # noqa: E402

#: A small split, so a test can ask for all of it.
FAKE = datasets.Dataset(
    key='fake', repo='test/fake', split='train', column='image',
    kind='image', suffix='.bin', rows=1000, approx_bytes=10)


class FetcherTests(unittest.TestCase):
    """Fetching, with the network replaced by an in-memory split."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved_dir = datasets.datasets_dir
        datasets.datasets_dir = lambda: self.tmp
        self.saved_rows = datasets._list_rows
        self.saved_one = datasets._download_one
        self.listed = []

        def list_rows(dataset, offset, length):
            self.listed.append(offset)
            end = min(dataset.rows, offset + min(length, datasets._PAGE))
            return [(index, 'fake://%d' % index) for index in range(offset, end)]

        def download_one(dataset, row_idx, url):
            path = os.path.join(datasets.local_dir(dataset),
                                '%07d%s' % (row_idx, dataset.suffix))
            if os.path.exists(path):
                return False
            with open(path, 'wb') as handle:
                handle.write(b'x')
            return True

        datasets._list_rows = list_rows
        datasets._download_one = download_one

    def tearDown(self):
        datasets.datasets_dir = self.saved_dir
        datasets._list_rows = self.saved_rows
        datasets._download_one = self.saved_one
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- coverage --------------------------------------------------------

    def test_a_small_request_is_satisfied(self):
        self.assertEqual(datasets.fetch(FAKE, 50), 50)

    def test_asking_for_the_whole_split_gets_the_whole_split(self):
        # The bug this pins: sampling pages at random used to stop
        # short, because re-drawing a page already taken counted as a
        # stall. Asking for everything must return everything.
        got = datasets.fetch(FAKE, FAKE.rows)
        self.assertEqual(got, FAKE.rows)

    def test_no_page_is_visited_twice(self):
        datasets.fetch(FAKE, FAKE.rows)
        self.assertEqual(len(self.listed), len(set(self.listed)))

    def test_pages_are_not_taken_in_order(self):
        # Random offsets are what stop a small library being the first
        # few classes of a split sorted by label.
        #
        # Seeded, because four pages drawn at random come out in order
        # about once in every twenty-four runs. Unseeded, this test
        # failed the whole suite that often and passed on the retry,
        # which is worse than not having it: a test that cries wolf
        # one run in twenty-four teaches people to re-run rather than
        # to read.
        datasets.fetch(FAKE, 400, rng=random.Random(0))
        self.assertNotEqual(self.listed, sorted(self.listed))

    def test_fetching_again_adds_nothing(self):
        first = datasets.fetch(FAKE, 200)
        calls = len(self.listed)
        second = datasets.fetch(FAKE, 200)
        self.assertEqual(first, second)
        self.assertEqual(len(self.listed), calls)

    def test_a_bigger_request_tops_up_what_is_there(self):
        datasets.fetch(FAKE, 100)
        self.assertEqual(datasets.fetch(FAKE, 300), 300)

    def test_it_stops_when_asked_to(self):
        stop = {'now': False}

        def should_stop():
            done = stop['now']
            stop['now'] = True
            return done

        got = datasets.fetch(FAKE, FAKE.rows, should_stop=should_stop)
        self.assertGreater(got, 0)
        self.assertLess(got, FAKE.rows)

    def test_a_failing_listing_gives_up_but_keeps_what_it_has(self):
        calls = {'n': 0}
        working = datasets._list_rows

        def flaky(dataset, offset, length):
            calls['n'] += 1
            if calls['n'] > 2:
                raise OSError('network gone')
            return working(dataset, offset, length)

        datasets._list_rows = flaky
        got = datasets.fetch(FAKE, FAKE.rows)
        self.assertGreater(got, 0)
        self.assertLess(got, FAKE.rows)

    # --- choosing the route ----------------------------------------------

    def test_a_large_request_prefers_the_bulk_route(self):
        used = []
        saved = datasets.fetch_bulk

        def bulk(dataset, wanted, progress=None, should_stop=None):
            used.append(wanted)
            return datasets.have(dataset)

        datasets.fetch_bulk = bulk
        try:
            datasets.fetch(FAKE, FAKE.rows)
        finally:
            datasets.fetch_bulk = saved
        self.assertEqual(used, [FAKE.rows])

    def test_a_small_request_stays_on_the_row_api(self):
        used = []
        saved = datasets.fetch_bulk
        datasets.fetch_bulk = lambda *a, **k: used.append(1)
        try:
            datasets.fetch(FAKE, 20)
        finally:
            datasets.fetch_bulk = saved
        self.assertEqual(used, [])

    def test_bulk_without_pyarrow_falls_back_rather_than_failing(self):
        saved = datasets.fetch_bulk

        def no_pyarrow(dataset, wanted, progress=None, should_stop=None):
            raise ImportError('no pyarrow')

        datasets.fetch_bulk = no_pyarrow
        try:
            self.assertEqual(datasets.fetch(FAKE, FAKE.rows), FAKE.rows)
        finally:
            datasets.fetch_bulk = saved

    def test_a_broken_bulk_route_falls_back_too(self):
        saved = datasets.fetch_bulk

        def broken(dataset, wanted, progress=None, should_stop=None):
            raise RuntimeError('corrupt parquet')

        datasets.fetch_bulk = broken
        try:
            self.assertEqual(datasets.fetch(FAKE, FAKE.rows), FAKE.rows)
        finally:
            datasets.fetch_bulk = saved

    # --- bookkeeping -----------------------------------------------------

    def test_progress_is_reported_and_ends_at_the_target(self):
        seen = []
        datasets.fetch(FAKE, 150, progress=lambda got, want: seen.append(got))
        self.assertTrue(seen)
        self.assertEqual(max(seen), 150)

    def test_files_are_named_by_row_so_the_routes_agree(self):
        datasets.fetch(FAKE, 30)
        names = [os.path.basename(p) for p in datasets.local_files(FAKE)]
        self.assertTrue(all(name.endswith('.bin') for name in names))
        self.assertEqual(names, sorted(names))
        self.assertTrue(all(len(name) == 11 for name in names))

    def test_partial_files_are_not_counted_as_library(self):
        folder = datasets.local_dir(FAKE)
        with open(os.path.join(folder, '9999999.bin.part'), 'wb') as handle:
            handle.write(b'half')
        self.assertEqual(datasets.have(FAKE), 0)

    def test_download_size_is_what_is_still_missing(self):
        datasets.fetch(FAKE, 100)
        self.assertEqual(datasets.download_size(FAKE, 150),
                         50 * FAKE.approx_bytes)
        self.assertEqual(datasets.download_size(FAKE, 100), 0)


class CatalogueTests(unittest.TestCase):
    """The datasets the games know about."""

    def test_every_entry_is_reachable_by_key(self):
        for key, dataset in datasets.CATALOGUE.items():
            self.assertIs(datasets.by_key(key), dataset)
            self.assertEqual(dataset.key, key)

    def test_unknown_keys_are_none(self):
        self.assertIsNone(datasets.by_key('no-such-dataset'))

    def test_each_has_a_default_fetch_size(self):
        for key in datasets.CATALOGUE:
            self.assertGreater(datasets.DEFAULT_COUNTS.get(key, 0), 0)

    def test_the_kinds_are_ones_media_can_load(self):
        for dataset in datasets.CATALOGUE.values():
            self.assertIn(dataset.kind, ('image', 'audio'))

    def test_the_command_line_rejects_an_unknown_name(self):
        self.assertEqual(datasets.main(['no-such-dataset']), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
