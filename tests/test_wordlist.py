#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The word pool, exercised without touching the network.

Most of this is about one thing: a definition is not a clue. The
definitions the pool is built from are glosses — "A zebra is a large
African equine mammal" — and every single one of them opens with the
word it defines. Printed as a clue that is not a puzzle, it is a
copying exercise, so :func:`clue_from` cuts the opening and refuses
anything that still shares the answer's stem. These check that it
refuses the ones it should, because the failure is silent: a bad clue
looks exactly like a good one until you notice the answer is in it.

The download is the least interesting part and gets the same treatment
it gets in :mod:`test_fontlib` — the network is a dictionary — because
what matters about it is that a half-written file never survives to be
parsed as a short one.

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

from neural_workshop import wordlist as W                     # noqa: E402


class ADefinitionIsNotAClue(unittest.TestCase):
    """Turning a gloss into something that does not give the answer."""

    def test_the_opening_self_reference_is_cut(self):
        self.assertEqual(
            W.clue_from('zebra', 'A zebra is a large African mammal.'),
            'large African mammal.')

    def test_every_shape_of_copula_is_cut(self):
        for gloss in ('Usury is the practice of lending at high rates.',
                      'Usury refers to the practice of lending at high '
                      'rates.',
                      'Usury means the practice of lending at high rates.'):
            self.assertEqual(W.clue_from('usury', gloss),
                             'practice of lending at high rates.')

    def test_a_definition_that_still_holds_the_answer_is_refused(self):
        # Not blanked out: a blank would say how long the answer is a
        # second time, and there are a hundred and forty-nine thousand
        # words that need no such help.
        self.assertIsNone(W.clue_from(
            'running', 'The act of running quickly on foot.'))

    def test_a_longer_form_of_the_answer_counts_as_holding_it(self):
        self.assertIsNone(W.clue_from(
            'happy', 'Feeling happiness or contentment.'))
        self.assertIsNone(W.clue_from(
            'run', 'The act of running quickly on foot.'))

    def test_a_shorter_root_of_the_answer_gets_through(self):
        # The stemmer is blunt in one direction only: it catches a
        # longer form of the answer and not a shorter root of it, so
        # "one who runs" survives as a clue for "runner". Written down
        # as a limit rather than left to be discovered, because the
        # only fix is a real stemmer and that is a dependency.
        self.assertEqual(W.clue_from('runner', 'One who runs in a race.'),
                         'One who runs in a race.')

    def test_an_article_is_not_eaten_out_of_the_next_word(self):
        # 'An' followed by 'anything' once left the clue starting
        # 'nything', because the article was allowed to match without
        # a space after it.
        self.assertEqual(
            W.clue_from('nonself', 'Nonself is anything the immune '
                                   'system does not recognise.'),
            'anything the immune system does not recognise.')

    def test_a_place_or_a_person_is_refused(self):
        for gloss in ('Branford is a town in New Haven County.',
                      'Bausch is a German surname meaning bump.',
                      'Stephen is a masculine given name of Greek origin.'):
            word = gloss.split()[0].lower()
            self.assertIsNone(W.clue_from(word, gloss), gloss)

    def test_a_clue_of_one_word_is_refused(self):
        # A synonym is not a clue, and what is left of a gloss whose
        # whole body was the answer is not one either.
        self.assertIsNone(W.clue_from('vast', 'Vast is enormous.'))

    def test_a_stem_is_blunt_on_purpose(self):
        self.assertEqual(W.stem_of('running'), 'runni')
        self.assertEqual(W.stem_of('cat'), 'cat')
        self.assertEqual(W.stem_of('runs'), 'runs'[:4])


class TheSeedIsEnoughToPlayWith(unittest.TestCase):
    """What a machine that has fetched nothing still has."""

    def test_the_seed_is_words_and_only_words(self):
        for one in W.SEED:
            self.assertTrue(one.word.isalpha(), one.word)
            self.assertEqual(one.word, one.word.lower())

    def test_the_seed_carries_no_clues_and_says_so(self):
        # Which is why the crossword refuses to deal without the
        # fetched definitions rather than dealing a clueless grid.
        self.assertFalse(any(one.clue for one in W.SEED))
        self.assertFalse(W.Lexicon(W.SEED).clued)

    def test_the_seed_is_ranked_in_frequency_order(self):
        ranks = [one.rank for one in W.SEED]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(len(set(one.word for one in W.SEED)), len(W.SEED))

    def test_the_seed_holds_enough_short_words_to_fill_a_grid(self):
        pooled = W.Lexicon(W.SEED)
        for length in (3, 4, 5):
            self.assertGreater(len(pooled.by_length.get(length, ())), 40,
                               length)


class APoolAnswersTheTwoQuestionsAGameAsks(unittest.TestCase):
    """Is this a word, and what words could go here."""

    def setUp(self):
        self.pool = W.Lexicon([
            W.Entry('cat', 1, 'a small pet'), W.Entry('cot', 2, 'a small bed'),
            W.Entry('cut', 3, 'a slice'), W.Entry('dog', 4, 'a large pet'),
            W.Entry('cattle', 900, 'cows'), W.Entry('at', 5, 'beside'),
        ])

    def test_a_word_in_it_is_valid_and_one_out_of_it_is_not(self):
        self.assertTrue(self.pool.valid('cat'))
        self.assertFalse(self.pool.valid('cta'))

    def test_a_pattern_finds_what_fits_and_nothing_longer(self):
        found = [one.word for one in self.pool.fitting('c.t')]
        self.assertEqual(sorted(found), ['cat', 'cot', 'cut'])
        self.assertEqual([one.word for one in self.pool.fitting('cat')],
                         ['cat'])
        self.assertEqual(self.pool.fitting('ca'), ())

    def test_prefixes_are_kept_by_length_rather_than_pooled(self):
        # 'cat' is a live opening for a six-letter slot because
        # 'cattle' exists, and is a dead one for a three-letter slot
        # because nothing three long starts 'cat' and continues.
        self.assertIn('cat', self.pool.prefixes(6))
        self.assertNotIn('cat', self.pool.prefixes(3))
        self.assertIn('ca', self.pool.prefixes(3))

    def test_a_band_is_a_slice_of_the_frequency_list(self):
        self.assertEqual([one.word for one in self.pool.band(1, 4)],
                         ['cat', 'cot', 'cut'])
        self.assertEqual([one.word for one in self.pool.band(1, 10, 3)],
                         ['cat', 'cot', 'cut', 'dog'])

    def test_narrowing_gives_the_same_pool_back_twice(self):
        # The same object, because the prefix sets and the pattern
        # answers live on it and a fill that rebuilt them each deal
        # would throw away most of its own work.
        first = self.pool.narrowed(hi=100, lengths=(3,))
        self.assertIs(first, self.pool.narrowed(hi=100, lengths=(3,)))
        self.assertEqual(len(first), 4)


class FetchingWithoutAMirror(unittest.TestCase):
    """The download, with the network replaced by a dictionary."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved_dir = W.words_dir
        self.saved_open = W._open
        self.saved_words = W.WORDS
        W.words_dir = lambda: self.tmp
        # A source with a small expected size, so a small fake file is
        # not read as a truncated big one.
        W.WORDS = W.WORDS._replace(approx_bytes=40)
        self.body = b'Rank,Word,Frequency count\n1,the,9\n' * 4

        class Response:
            def __init__(self, body):
                self.headers = {'Content-Length': str(len(body))}
                self._rest = body

            def read(self, size=-1):
                out, self._rest = self._rest[:size], self._rest[size:]
                return out

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        self.asked = []

        def opener(url, timeout=None):
            self.asked.append(url)
            return Response(self.body)
        W._open = opener

    def tearDown(self):
        W.words_dir = self.saved_dir
        W._open = self.saved_open
        W.WORDS = self.saved_words
        W.forget()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_fetch_brings_the_file_back(self):
        self.assertTrue(W.fetch(W.WORDS))
        self.assertTrue(os.path.exists(W.local_path(W.WORDS)))
        self.assertEqual(len(self.asked), 1)

    def test_asking_twice_downloads_once(self):
        W.fetch(W.WORDS)
        self.asked = []
        self.assertTrue(W.fetch(W.WORDS))
        self.assertEqual(self.asked, [])

    def test_a_failed_download_leaves_no_half_file_behind(self):
        def broken(url, timeout=None):
            raise OSError('mirror gone')
        W._open = broken
        self.assertFalse(W.fetch(W.WORDS))
        self.assertFalse(os.path.exists(W.local_path(W.WORDS)))
        self.assertFalse([name for name in os.listdir(self.tmp)
                          if name.endswith('.part')])

    def test_a_truncated_file_does_not_count_as_having_it(self):
        # A short file parses perfectly and is quietly missing most of
        # the language, which is worse than no file at all.
        big = W.WORDS._replace(approx_bytes=1_000_000)
        with open(W.local_path(big), 'w', encoding='utf-8') as handle:
            handle.write('Rank,Word\n1,the\n')
        self.assertFalse(W.have(big))

    def test_the_ranks_come_off_the_csv(self):
        W.fetch(W.WORDS)
        self.assertEqual(W.ranks(), {'the': 1})

    def test_progress_is_reported_up_to_the_whole_file(self):
        seen = []
        W.fetch(W.WORDS, progress=lambda got, want: seen.append((got, want)))
        self.assertEqual(seen[-1][0], len(self.body))
        self.assertTrue(all(got <= want for got, want in seen))

    def test_an_index_older_than_its_sources_is_not_believed(self):
        W.fetch(W.WORDS)
        with open(W.index_path(), 'w', encoding='utf-8') as handle:
            handle.write('the\t1\tdefinite article\n')
        os.utime(W.index_path(), (1, 1))
        self.assertFalse(W.index_ready())

    def test_a_missing_source_says_what_to_run(self):
        said = W.missing_message(W.CLUES)
        self.assertIn('neural_workshop.wordlist', said)
        self.assertIn(W.CLUES.repo, said)


class TheCatalogueSaysWhatItHolds(unittest.TestCase):

    def test_every_source_names_a_file_of_a_dataset(self):
        for key, source in W.SOURCES.items():
            self.assertEqual(source.key, key)
            self.assertIn('/', source.repo)
            self.assertTrue(source.path)
            self.assertGreater(source.approx_bytes, 0)
            self.assertTrue(source.licence)

    def test_an_unknown_source_is_refused_rather_than_guessed(self):
        self.assertEqual(W.main(['no-such-source']), 2)

    def test_the_bands_climb(self):
        tops = [hi for _name, _lo, hi in W.BANDS]
        self.assertEqual(tops, sorted(tops))


if __name__ == '__main__':
    unittest.main(verbosity=2)
