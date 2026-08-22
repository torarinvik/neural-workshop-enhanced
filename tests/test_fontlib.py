#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The typeface fetcher, exercised without touching the network.

The download is the least interesting part. What matters is what
happens around it: spreading a fetch across the mirror instead of
pulling nine weights of one face, asking for the same fonts every time
so a held-out family can be named in a paper and found again, skipping
what is already on disk, and never leaving a half-written font behind —
a truncated font is worse than a missing one, because it parses far
enough to claim a family and then draws nothing.

And one thing that is not tested here because it cannot be: whether the
mirror's "english" folder really contains English. That is the mirror's
word, and :func:`neural_workshop.glyphs.covered` is what the rest of
the code believes instead.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('NW_HEADLESS', '1')

from neural_workshop import fontlib                          # noqa: E402

#: A mirror in miniature: four families, several weights apiece, in the
#: three filename shapes the real one actually uses.
FAKE_FILES = [
    'f/%s' % name for name in (
        '00000000000000000000000000000001_Nova_Cut_regular.ttf',
        '00000000000000000000000000000002_Nova_Cut_italic.ttf',
        '00000000000000000000000000000003_Nova_Cut_700.ttf',
        '00000000000000000000000000000004_Sofia_Sans_200italic.ttf',
        '00000000000000000000000000000005_Sofia_Sans_regular.ttf',
        '0000000000000000000000000000000000000000000000000000000000000006'
        '_DejaVuSerif-Bold.ttf',
        '0000000000000000000000000000000000000000000000000000000000000007'
        '_DejaVuSerif-Italic.ttf',
        '0000000000000000000000000000000000000000000000000000000000000008'
        '_TH Sarabun New Regular.ttf',
    )]

FAKE = fontlib.Pool('fake', 'test/fake', 'f', len(FAKE_FILES), 100, 'a mirror')


class TheFilenameIsOnlyAPlanner(unittest.TestCase):
    """Reading a family out of a mirror filename, and its limits."""

    def test_the_three_shapes_the_mirror_uses_all_read(self):
        self.assertEqual(fontlib.guessed_family(FAKE_FILES[0]), 'Nova Cut')
        self.assertEqual(fontlib.guessed_family(FAKE_FILES[3]), 'Sofia Sans')
        self.assertEqual(fontlib.guessed_family(FAKE_FILES[5]), 'DejaVuSerif')

    def test_weights_and_slants_of_one_face_read_as_one_face(self):
        self.assertEqual(fontlib.guessed_family(FAKE_FILES[0]),
                         fontlib.guessed_family(FAKE_FILES[2]))
        self.assertEqual(fontlib.guessed_family(FAKE_FILES[5]),
                         fontlib.guessed_family(FAKE_FILES[6]))

    def test_a_name_it_cannot_parse_still_names_something(self):
        # Never an empty string: an unparsed name has to group with
        # itself rather than with every other name it failed on.
        self.assertTrue(fontlib.guessed_family('f/whatever.ttf'))
        self.assertTrue(fontlib.guessed_family(FAKE_FILES[7]))


class APlanIsRepeatable(unittest.TestCase):
    """Which fonts a request picks, and why it must pick the same ones."""

    def test_one_file_per_family_rather_than_one_file(self):
        picked = fontlib.plan(FAKE_FILES, 4, seed=0)
        families = [fontlib.guessed_family(name) for name in picked]
        self.assertEqual(len(set(families)), len(families))

    def test_asking_for_more_than_there_is_gets_what_there_is(self):
        picked = fontlib.plan(FAKE_FILES, 99, seed=0)
        self.assertEqual(len(picked), 4)

    def test_asking_for_none_downloads_none(self):
        self.assertEqual(fontlib.plan(FAKE_FILES, 0), [])

    def test_the_same_seed_picks_the_same_typefaces(self):
        # A measurement that names its held-out families has to be
        # repeatable on another machine, and it cannot be if the pool
        # it drew from was shuffled differently there.
        self.assertEqual(fontlib.plan(FAKE_FILES, 3, seed=5),
                         fontlib.plan(FAKE_FILES, 3, seed=5))
        self.assertNotEqual(fontlib.plan(FAKE_FILES, 3, seed=5),
                            fontlib.plan(FAKE_FILES, 3, seed=6))

    def test_the_order_the_mirror_listed_them_in_does_not_matter(self):
        shuffled = list(reversed(FAKE_FILES))
        self.assertEqual(fontlib.plan(FAKE_FILES, 3, seed=1),
                         fontlib.plan(shuffled, 3, seed=1))


class FetchingWithoutAMirror(unittest.TestCase):
    """The download, with the network replaced by a dictionary."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved_dir = fontlib.fonts_dir
        self.saved_listing = fontlib.listing
        self.saved_get = fontlib._get
        self.asked = []
        fontlib.fonts_dir = lambda: self.tmp
        fontlib.listing = lambda pool, refresh=False: list(FAKE_FILES)

        def get(url, timeout=None):
            self.asked.append(url)
            return b'a font, honestly' * 4
        fontlib._get = get

    def tearDown(self):
        fontlib.fonts_dir = self.saved_dir
        fontlib.listing = self.saved_listing
        fontlib._get = self.saved_get
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_fetch_brings_back_one_font_a_family(self):
        self.assertEqual(fontlib.fetch(FAKE, 4), 4)
        self.assertEqual(len(self.asked), 4)
        self.assertEqual(fontlib.have(FAKE), 4)

    def test_asking_twice_downloads_once(self):
        fontlib.fetch(FAKE, 4)
        self.asked = []
        self.assertEqual(fontlib.fetch(FAKE, 4), 4)
        self.assertEqual(self.asked, [])

    def test_a_bigger_ask_only_fetches_the_difference(self):
        fontlib.fetch(FAKE, 2, seed=0)
        self.asked = []
        fontlib.fetch(FAKE, 4, seed=0)
        self.assertEqual(len(self.asked), 2)

    def test_a_filename_with_a_space_in_it_is_still_asked_for(self):
        # http.client refuses a request line containing a space, and a
        # few of the mirror's filenames have one. Left unquoted this
        # raised rather than skipping the file, which took the whole
        # fetch down with it.
        fontlib.fetch(FAKE, 99)
        self.assertTrue(any('%20' in url for url in self.asked))
        self.assertFalse(any(' ' in url for url in self.asked))

    def test_a_failed_download_leaves_no_half_font_behind(self):
        def broken(url, timeout=None):
            raise OSError('mirror gone')
        fontlib._get = broken
        self.assertEqual(fontlib.fetch(FAKE, 4), 0)
        left = os.listdir(fontlib.pool_dir(FAKE))
        self.assertFalse([name for name in left if name.endswith('.part')])
        self.assertEqual(fontlib.local_files(FAKE), [])

    def test_one_font_failing_does_not_lose_the_others(self):
        first = [True]

        def flaky(url, timeout=None):
            if first[0]:
                first[0] = False
                raise OSError('mirror gone')
            return b'a font'
        fontlib._get = flaky
        self.assertEqual(fontlib.fetch(FAKE, 4), 3)

    def test_progress_is_reported_up_to_what_was_asked_for(self):
        seen = []
        fontlib.fetch(FAKE, 3, progress=lambda got, want: seen.append((got,
                                                                       want)))
        self.assertEqual(seen[-1], (3, 3))
        self.assertTrue(all(got <= want for got, want in seen))

    def test_an_empty_pool_directory_contributes_no_typefaces(self):
        # font_dirs is called before anything has been fetched, every
        # time, so it has to be quiet about a pool that is not there.
        self.assertNotIn(os.path.join(self.tmp, 'english'),
                         fontlib.font_dirs())
        fontlib.fetch(fontlib.POOLS['english'], 0)
        self.assertIn(os.path.join(self.tmp, 'english'), fontlib.font_dirs())

    def test_the_machine_s_own_typefaces_are_still_in_the_mix(self):
        from neural_workshop import glyphs
        self.assertEqual(fontlib.font_dirs()[:len(glyphs.platform_dirs())],
                         glyphs.platform_dirs())

    def test_the_listing_is_not_refetched_for_every_request(self):
        fontlib.listing = self.saved_listing
        calls = []

        def get(url, timeout=None):
            calls.append(url)
            return b''
        fontlib._get = get
        path = os.path.join(fontlib.pool_dir(FAKE), '_listing.json')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('["f/x.ttf"]')
        self.assertEqual(fontlib.listing(FAKE), ['f/x.ttf'])
        self.assertEqual(calls, [])


class TheCatalogueSaysWhatItHolds(unittest.TestCase):

    def test_every_pool_names_a_folder_of_a_repository(self):
        for key, pool in fontlib.POOLS.items():
            self.assertEqual(pool.key, key)
            self.assertIn('/', pool.repo)
            self.assertTrue(pool.folder)
            self.assertGreater(pool.files, 0)
            self.assertGreater(pool.approx_bytes, 0)

    def test_an_unknown_pool_is_refused_rather_than_guessed(self):
        self.assertEqual(fontlib.main(['no-such-pool', '1']), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
