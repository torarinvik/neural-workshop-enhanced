#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Scramble: the corruption, what it leaves, and what the screen does with it.

One property here matters more than all the others put together.
:func:`~neural_workshop.scramble.feasible` decides whether a corrupted
token could have been a given word, and every number this task
publishes — the ambiguity of a deal, how many words are pinned, what
the context-free reader gets back — is counted with it. If it ever
says *no* to the word that was actually there, all of those numbers
are counts of the wrong set and nothing says so. So it is checked the
only way worth checking: corrupt real words at every rung of the
ladder and assert the truth survives its own corruption, thousands of
times.

The rest is the corruption doing what each dial claims and no more —
a swap that changes a letter, a drop that takes two, an insert that
lands outside the word are all silent failures that would show up as
a task being harder than its own table says.

Nothing here needs the text fetched: the sentences are the ones in
:data:`neural_workshop.sentences.SEED_TEXT`, which are in the
repository. Two tests at the end use the fetched bank and say so.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('NW_HEADLESS', '1')

from uisupport import (Scramble, TASKS, close_overlays,        # noqa: E402
                       needs_ui, reset_window)
from pyglet.window import key, mouse                           # noqa: E402

from neural_workshop import scramble as S                      # noqa: E402
from neural_workshop import sentences as T                     # noqa: E402
from neural_workshop.ui.verdict import above_the_band          # noqa: E402


def pocket(grade=None):
    """The seed sentences, graded, and filtered to *grade* if given.

    In the repository, so none of this depends on 46 MB of Wikipedia
    having been read.
    """
    known = T.ranks()
    made = []
    for line in T.SEED_TEXT:
        words = tuple(line.split())
        made.append(T.Sentence(words, max(known.get(one, 1 << 30)
                                          for one in words)))
    if grade is None:
        return tuple(made)
    return tuple(one for one in made
                 if grade.span[0] <= len(one) <= grade.span[1]
                 and one.hardest <= grade.top_rank)


#: Words to put through the corruption. Short and long, repeated
#: letters and none, so a dial that only misbehaves on ``bookkeeper``
#: is not missed by a test that only tries ``horse``.
SPECIMENS = ('a', 'to', 'the', 'horse', 'black', 'walked', 'because',
             'letters', 'committee', 'bookkeeper', 'aaa', 'abcdefghijkl')


class TheDialsDoWhatTheySay(unittest.TestCase):
    """Each corruption operator, on its own, doing exactly its own job."""

    def setUp(self):
        self.rng = random.Random(4)

    def only(self, **dials):
        return S.Grade('x', (6, 12), 30000, **dials)

    def test_a_swap_keeps_every_letter(self):
        grade = self.only(swap=1)
        for word in SPECIMENS:
            got = S.scramble_word(grade, word, self.rng)
            self.assertEqual(sorted(got), sorted(word), word)
            self.assertEqual(len(got), len(word), word)

    def test_a_swap_actually_swaps_when_there_is_room(self):
        grade = self.only(swap=1)
        for word in ('horse', 'black', 'walked', 'letters'):
            changed = any(S.scramble_word(grade, word, self.rng) != word
                          for _try in range(12))
            self.assertTrue(changed, word)

    def test_an_interior_shuffle_keeps_the_ends(self):
        grade = self.only(interior=True)
        for word in SPECIMENS:
            got = S.scramble_word(grade, word, self.rng)
            self.assertEqual(got[:1], word[:1], word)
            self.assertEqual(got[-1:], word[-1:], word)
            self.assertEqual(sorted(got), sorted(word), word)

    def test_a_whole_shuffle_keeps_the_letters_and_not_the_ends(self):
        grade = self.only(whole=True)
        moved = 0
        for word in SPECIMENS:
            for _try in range(20):
                got = S.scramble_word(grade, word, self.rng)
                self.assertEqual(sorted(got), sorted(word), word)
                moved += got[:1] != word[:1]
        self.assertGreater(moved, 0, 'the first letter never moved')

    def test_a_shuffle_that_can_change_the_word_does(self):
        """A word that comes back unscrambled is a word not scrambled.

        Worth its own test because the failure is invisible: the run
        goes on, the trial is scored, and one line in five at rung two
        was simply not a puzzle before the retry loop existed.
        """
        grade = self.only(interior=True)
        for word in ('horse', 'black', 'letters', 'because'):
            same = sum(1 for _try in range(40)
                       if S.scramble_word(grade, word, self.rng) == word)
            self.assertEqual(same, 0, word)

    def test_a_drop_takes_exactly_what_it_says(self):
        for count in (1, 2):
            grade = self.only(drop=count)
            for word in SPECIMENS:
                got = S.scramble_word(grade, word, self.rng)
                want = len(word) - min(count, max(0, len(word) - 2))
                self.assertEqual(len(got), want, (word, count))

    def test_a_drop_never_leaves_less_than_two_letters(self):
        grade = self.only(drop=3)
        for word in ('a', 'to', 'the', 'four'):
            got = S.scramble_word(grade, word, self.rng)
            self.assertGreaterEqual(len(got), min(2, len(word)), word)

    def test_an_insert_adds_exactly_what_it_says(self):
        for count in (1, 2):
            grade = self.only(insert=count)
            for word in SPECIMENS:
                got = S.scramble_word(grade, word, self.rng)
                self.assertEqual(len(got), len(word) + count, (word, count))

    def test_a_substitution_keeps_the_length_and_goes_next_door(self):
        grade = self.only(substitute=1)
        for word in ('horse', 'black', 'letters'):
            got = S.scramble_word(grade, word, self.rng)
            self.assertEqual(len(got), len(word), word)
            changed = [(was, now) for was, now in zip(word, got)
                       if was != now]
            self.assertLessEqual(len(changed), 1, word)
            for was, now in changed:
                self.assertIn(now, S.NEAR_KEYS[was], (was, now))

    def test_nothing_on_leaves_the_word_alone(self):
        grade = self.only()
        for word in SPECIMENS:
            self.assertEqual(S.scramble_word(grade, word, self.rng), word)


class TheTruthSurvivesItsOwnCorruption(unittest.TestCase):
    """The one property everything else counted here rests on."""

    def test_every_rung_leaves_its_own_word_feasible(self):
        """The whole task's arithmetic depends on this and nothing else.

        :func:`feasible` is allowed to be generous — it is a superset
        of what the corruption can make — but it may never rule out
        the word that was really there, because then the candidate
        sets it builds would be missing the answer and every count
        taken off them would be a count of the wrong thing.
        """
        rng = random.Random(11)
        words = [word for line in T.SEED_TEXT for word in line.split()]
        for rung, grade in enumerate(S.GRADES, 1):
            for word in words[:400]:
                token = S.scramble_word(grade, word, rng)
                self.assertTrue(S.feasible(grade, token, word),
                                'rung %d: %r came from %r and was refused'
                                % (rung, token, word))

    def test_a_word_is_feasible_for_itself_at_every_rung(self):
        for grade in S.GRADES:
            for word in SPECIMENS[2:]:
                self.assertTrue(S.feasible(grade, word, word), (grade, word))

    def test_a_length_far_off_is_not_feasible(self):
        grade = S.Grade('x', (6, 12), 30000, drop=1, insert=1)
        self.assertFalse(S.feasible(grade, 'ho', 'horse'))
        self.assertFalse(S.feasible(grade, 'horsesss', 'horse'))

    def test_the_ends_are_evidence_only_when_they_are_safe(self):
        """A single drop can take the last letter, so the ends stop counting.

        Anchoring on a rung that also deletes letters would be the one
        way :func:`feasible` could reject the truth, so it is turned
        off the moment anything touches the letters themselves.
        """
        self.assertTrue(S.anchored(S.Grade('x', (6, 12), 1, interior=True)))
        self.assertFalse(S.anchored(
            S.Grade('x', (6, 12), 1, interior=True, drop=1)))
        self.assertFalse(S.anchored(
            S.Grade('x', (6, 12), 1, interior=True, insert=1)))
        self.assertFalse(S.anchored(
            S.Grade('x', (6, 12), 1, interior=True, substitute=1)))
        self.assertFalse(S.anchored(S.Grade('x', (6, 12), 1, whole=True)))

    def test_bag_distance_counts_both_directions(self):
        self.assertEqual(S.bag_distance('horse', 'horse'), 0)
        self.assertEqual(S.bag_distance('hrose', 'horse'), 0)
        self.assertEqual(S.bag_distance('hrse', 'horse'), 1)
        self.assertEqual(S.bag_distance('hoxrse', 'horse'), 1)
        self.assertEqual(S.bag_distance('hoyse', 'horse'), 2)


class WhatTheLettersStillSay(unittest.TestCase):
    """Candidate sets, and the counts taken off them."""

    def test_the_true_word_is_always_a_candidate(self):
        rng = random.Random(3)
        for grade in (S.GRADES[0], S.GRADES[3], S.GRADES[6]):
            words = S.vocab_for(grade)
            for line in T.SEED_TEXT[:12]:
                for word in line.split():
                    if word not in words.rank:
                        continue
                    token = S.scramble_word(grade, word, rng)
                    self.assertIn(word, S.candidates(grade, token, words),
                                  (grade.name, token, word))

    def test_candidates_come_back_commonest_first(self):
        grade = S.GRADES[3]
        words = S.vocab_for(grade)
        for token in ('eht', 'dna', 'saw'):
            got = S.candidates(grade, token, words)
            ranked = [words.rank[one] for one in got]
            self.assertEqual(ranked, sorted(ranked), token)

    def test_a_jumbled_word_is_usually_pinned_by_its_own_letters(self):
        """Which is the finding the module docstring leads with.

        An anagram of an English word is nearly always an anagram of
        only that word, so the classic jumbled-text trick takes almost
        no information away at all.
        """
        grade = S.GRADES[1]
        rng = random.Random(5)
        deals = [S.deal_one(grade, rng, pocket(grade)) for _each in range(20)]
        pinned = sum(one.pinned for one in deals)
        total = sum(len(one.words) for one in deals)
        self.assertGreater(pinned / total, 0.8)

    def test_taking_letters_out_takes_that_away(self):
        gentle, harsh = S.GRADES[1], S.GRADES[8]
        rng = random.Random(6)
        soft = [S.deal_one(gentle, rng, pocket(gentle)) for _each in range(15)]
        hard = [S.deal_one(harsh, rng, pocket(harsh)) for _each in range(15)]
        self.assertLess(sum(one.ambiguity for one in soft),
                        sum(one.ambiguity for one in hard))


class TheGapsAndTheOrder(unittest.TestCase):
    """The two dials that do not touch a single letter."""

    def test_moving_the_gaps_keeps_every_letter_in_place(self):
        rng = random.Random(8)
        grade = S.Grade('x', (6, 12), 30000, whole=True, spaces=1)
        for _each in range(30):
            deal = S.deal_one(grade, rng, pocket(grade))
            self.assertEqual(''.join(deal.chunks), ''.join(deal.corrupted))

    def test_taking_the_gaps_out_leaves_exactly_one_chunk(self):
        rng = random.Random(9)
        grade = S.Grade('x', (6, 12), 30000, whole=True, spaces=2)
        for _each in range(10):
            deal = S.deal_one(grade, rng, pocket(grade))
            self.assertEqual(len(deal.chunks), 1)
            self.assertNotIn(' ', deal.shown)

    def test_moved_gaps_are_usually_not_the_real_ones(self):
        rng = random.Random(10)
        grade = S.Grade('x', (6, 12), 30000, whole=True, spaces=1)
        wrong = 0
        for _each in range(30):
            deal = S.deal_one(grade, rng, pocket(grade))
            wrong += deal.chunks != deal.corrupted
        self.assertGreater(wrong, 25)

    def test_a_shuffle_only_moves_a_word_inside_its_own_block(self):
        rng = random.Random(12)
        for width in (2, 3, 4):
            grade = S.Grade('x', (6, 12), 30000, order=width)
            for count in (6, 8, 11):
                placing = S.shuffle_order(grade, count, rng)
                self.assertEqual(sorted(placing), list(range(count)))
                for block in S.blocks(count, width):
                    self.assertEqual(sorted(placing[block[0]:block[-1] + 1]),
                                     list(block))

    def test_no_shuffle_leaves_the_words_where_they_were(self):
        rng = random.Random(13)
        for width in (0, 1):
            grade = S.Grade('x', (6, 12), 30000, order=width)
            self.assertEqual(S.shuffle_order(grade, 9, rng), tuple(range(9)))

    def test_blocks_cover_every_index_once(self):
        for count in (1, 5, 9, 12):
            for width in (0, 1, 2, 3, 5):
                got = [one for block in S.blocks(count, width)
                       for one in block]
                self.assertEqual(got, list(range(count)), (count, width))


class ADealIsWhatItSaysItIs(unittest.TestCase):
    """The record a trial is scored against."""

    def test_every_rung_deals_from_the_seed_text(self):
        for rung, grade in enumerate(S.GRADES, 1):
            deal = S.deal_one(grade, random.Random(rung), pocket(grade))
            self.assertIsNotNone(deal, 'rung %d dealt nothing' % rung)
            self.assertTrue(grade.span[0] <= len(deal.words) <= grade.span[1])

    def test_nothing_to_draw_on_is_said_rather_than_guessed(self):
        self.assertIsNone(S.deal_one(S.GRADES[0], random.Random(1), ()))

    def test_the_same_seed_deals_the_same_line(self):
        for rung in (1, 6, 12):
            one = S.generate(rung, seed=77, text=pocket(S.grade_of(rung)))
            other = S.generate(rung, seed=77, text=pocket(S.grade_of(rung)))
            self.assertEqual(one, other)

    def test_the_shown_order_is_the_answer_permuted(self):
        for rung, grade in enumerate(S.GRADES, 1):
            deal = S.deal_one(grade, random.Random(rung), pocket(grade))
            self.assertEqual(sorted(deal.in_view), sorted(deal.words))
            self.assertEqual(len(deal.corrupted), len(deal.words))

    def test_a_corrupted_word_answers_to_the_word_it_is_shown_for(self):
        for rung, grade in enumerate(S.GRADES, 1):
            deal = S.deal_one(grade, random.Random(100 + rung), pocket(grade))
            for token, word in zip(deal.corrupted, deal.in_view):
                self.assertTrue(S.feasible(grade, token, word),
                                (rung, token, word))

    def test_the_answer_is_the_words_in_the_order_they_were_written(self):
        deal = S.deal_one(S.GRADES[10], random.Random(2),
                          pocket(S.GRADES[10]))
        self.assertEqual(deal.answer, ' '.join(deal.words))


class TheLadderClimbs(unittest.TestCase):
    """The published table's shape, checked rather than trusted.

    Not its exact numbers — those move with the text that was fetched
    and live in ``bench_scramble.py``. What is asserted is the shape:
    the bottom is nearly free, the top is nearly nothing, and no rung
    is easier than the one four below it.
    """

    def read_back(self, grade, deals=12, seed=1):
        rng = random.Random(seed)
        got = []
        for _each in range(deals):
            deal = S.deal_one(grade, rng, pocket(grade))
            if deal is not None:
                got.append(S.read_back(deal))
        return sum(got) / len(got) if got else 0.0

    def test_the_bottom_of_the_ladder_gives_the_letters_away(self):
        self.assertGreater(self.read_back(S.GRADES[0]), 0.85)
        self.assertGreater(self.read_back(S.GRADES[1]), 0.85)

    def test_the_top_of_the_ladder_gives_almost_nothing_away(self):
        self.assertLess(self.read_back(S.GRADES[11], deals=4), 0.35)

    def test_it_gets_harder_over_any_four_rungs(self):
        got = [self.read_back(grade, deals=8) for grade in S.GRADES[:8]]
        for lower in range(len(got) - 4):
            self.assertGreaterEqual(got[lower] + 0.01, got[lower + 4],
                                    'rung %d is not above rung %d'
                                    % (lower + 1, lower + 5))

    def test_with_the_gaps_intact_the_reader_answers_word_for_word(self):
        grade = S.GRADES[3]
        deal = S.deal_one(grade, random.Random(31), pocket(grade))
        self.assertEqual(len(S.read_off(deal)), len(deal.in_view))

    def test_with_the_gaps_gone_it_may_come_back_a_different_length(self):
        """And is scored out of the whole line anyway.

        Once the reader has to find the word boundaries itself it can
        return seven words where there were nine, so nothing may
        assume the two line up. :func:`read_back` divides by the true
        length rather than by what came back, or a reader that gave up
        after two words would score two out of two.
        """
        grade = S.GRADES[11]
        rng = random.Random(31)
        shorter = 0
        for _each in range(6):
            deal = S.deal_one(grade, rng, pocket(grade))
            got = S.read_off(deal)
            shorter += len(got) != len(deal.in_view)
            self.assertLessEqual(S.read_back(deal), 1.0)
        self.assertGreater(shorter, 0, 'the segmenter never disagreed')

    def test_the_reader_only_ever_answers_with_real_words(self):
        grade = S.GRADES[9]
        words = S.vocab_for(grade)
        deal = S.deal_one(grade, random.Random(32), pocket(grade))
        for word in S.read_off(deal):
            self.assertIn(word, words.rank, word)


class MarkingIsExact(unittest.TestCase):
    """One string, compared once."""

    def setUp(self):
        self.deal = S.deal_one(S.GRADES[0], random.Random(21),
                               pocket(S.GRADES[0]))

    def test_the_answer_is_right(self):
        self.assertTrue(S.correct(self.deal, self.deal.answer))

    def test_case_and_punctuation_do_not_count(self):
        shouted = self.deal.answer.upper() + '.'
        self.assertTrue(S.correct(self.deal, shouted))

    def test_extra_spaces_do_not_count(self):
        spaced = '   ' + '   '.join(self.deal.words) + '  '
        self.assertTrue(S.correct(self.deal, spaced))

    def test_one_word_wrong_is_wrong(self):
        wrong = list(self.deal.words)
        wrong[0] = 'zebra'
        self.assertFalse(S.correct(self.deal, ' '.join(wrong)))

    def test_the_right_words_in_the_wrong_order_are_wrong(self):
        if len(set(self.deal.words)) < 2:
            self.skipTest('nothing to reorder')
        self.assertFalse(S.correct(self.deal,
                                   ' '.join(reversed(self.deal.words))))

    def test_normalise_keeps_only_words(self):
        self.assertEqual(S.normalise('  The, BLACK   horse! '),
                         'the black horse')


@needs_ui
class TheScrambleScreen(unittest.TestCase):
    """Typing, marking, and where the screen is allowed to draw."""

    def setUp(self):
        close_overlays()
        self.task = Scramble()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.start_rung = self.task.rung = 1

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def open_one(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'reading')

    def type_out(self, text):
        for character in text:
            if character == ' ':
                self.task.space()
            else:
                self.task.write(character)

    def test_it_is_in_the_reasoning_category(self):
        self.assertIn('scramble', [task for task, _n in TASKS['reasoning']])

    def test_a_trial_opens_with_a_line_and_an_empty_answer(self):
        self.open_one()
        self.assertTrue(self.task.deal.shown)
        self.assertEqual(self.task.typed, '')
        self.task.on_draw()

    def test_letters_go_into_the_answer(self):
        self.open_one()
        self.type_out('horse')
        self.assertEqual(self.task.typed, 'horse')

    def test_a_space_needs_something_before_it(self):
        self.open_one()
        self.task.space()
        self.assertEqual(self.task.typed, '')
        self.type_out('the')
        self.task.space()
        self.task.space()
        self.assertEqual(self.task.typed, 'the ')

    def test_rubbing_out_takes_the_last_thing_typed(self):
        self.open_one()
        self.type_out('the ')
        self.task.erase()
        self.task.erase()
        self.assertEqual(self.task.typed, 'th')

    def test_an_empty_answer_cannot_be_submitted(self):
        self.open_one()
        self.task.submit()
        self.assertEqual(self.task.phase, 'reading')
        self.task.space()
        self.task.submit()
        self.assertEqual(self.task.phase, 'reading')

    def test_the_right_line_is_green(self):
        self.open_one()
        self.type_out(self.task.deal.answer)
        self.task.submit()
        self.assertEqual(self.task.phase, 'judged')
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.score()['right'], 1)

    def test_a_wrong_line_is_red_and_is_told_the_answer(self):
        self.open_one()
        answer = self.task.deal.answer
        self.type_out('zebra')
        self.task.submit()
        self.assertEqual(self.task.phase, 'judged')
        self.assertFalse(self.task.verdict_shown[0])
        self.assertIn(answer, self.task.message)

    def test_nothing_is_typed_once_the_answer_is_in(self):
        # Compared against what was typed rather than looked for by
        # letter: the sentence is dealt unseeded, and "x unexpectedly
        # found" is what this said the day it drew one about an
        # explanation. It also catches the rub-out, which looking for
        # a letter never did.
        self.open_one()
        self.type_out(self.task.deal.answer)
        self.task.submit()
        settled = self.task.typed
        self.task.write('x')
        self.task.erase()
        self.assertEqual(self.task.typed, settled)

    def test_no_verdict_is_up_while_the_line_can_still_be_answered(self):
        self.open_one()
        self.assertIsNone(self.task.verdict_shown)
        self.type_out('the')
        self.assertIsNone(self.task.verdict_shown)

    def test_the_next_line_takes_the_verdict_down(self):
        self.open_one()
        self.type_out('zebra')
        self.task.submit()
        self.assertIsNotNone(self.task.verdict_shown)
        self.task.advance()
        self.assertEqual(self.task.phase, 'reading')
        self.assertIsNone(self.task.verdict_shown)

    def test_a_run_ends_after_its_lines(self):
        self.open_one()
        for _each in range(2):
            self.type_out('zebra')
            self.task.submit()
            self.task.advance()
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['asked'], 2)

    def test_climbing_needs_the_line_right(self):
        self.task.adaptive = True
        self.open_one()
        self.type_out(self.task.deal.answer)
        self.task.submit()
        self.assertEqual(self.task.rung, 2)

    def test_a_wrong_line_climbs_back_down(self):
        self.task.adaptive = True
        self.task.start_rung = self.task.rung = 4
        self.open_one()
        self.type_out('zebra')
        self.task.submit()
        self.assertEqual(self.task.rung, 3)

    def test_a_click_starts_a_run_and_goes_on(self):
        self.task.on_mouse_press(10, 10, mouse.LEFT, 0)
        self.assertEqual(self.task.phase, 'reading')
        self.type_out('zebra')
        self.task.submit()
        self.task.on_mouse_press(10, 10, mouse.LEFT, 0)
        self.assertEqual(self.task.phase, 'reading')

    def test_space_types_while_reading_and_advances_otherwise(self):
        """The one key with two jobs, and the reason it has to have them.

        A sentence has spaces in it, so Space cannot be reserved for
        starting a run; and a run has to start somehow. The phase
        decides, which is unambiguous because there is nothing to type
        before a line is up.
        """
        self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.phase, 'reading')
        self.task.on_key_press(key.A, 0)
        self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.typed, 'a ')

    def test_enter_marks_the_line(self):
        self.open_one()
        self.type_out('zebra')
        self.task.on_key_press(key.ENTER, 0)
        self.assertEqual(self.task.phase, 'judged')

    def test_the_reading_count_is_printed_and_hedges_when_it_should(self):
        from neural_workshop.ui.scramble import readings
        for rung, grade in enumerate(S.GRADES, 1):
            deal = S.deal_one(grade, random.Random(rung), pocket(grade))
            said = readings(deal)
            self.assertIn('reading', said)
            self.assertEqual('at least' in said, grade.spaces > 0,
                             'rung %d hedged wrongly: %s' % (rung, said))

    def test_the_word_count_is_shown_only_when_it_is_asked_for(self):
        self.task.show_count = True
        self.open_one()
        self.assertIn('words', self.task.status.text)
        self.task.show_count = False
        self.task._redraw()
        self.assertNotIn('words', self.task.status.text)

    def test_nothing_is_drawn_in_the_verdict_band(self):
        """Asserted against the geometry, at three window sizes.

        The typed line is blue, and blue on a pale page has a rim of
        every blend between the two, part of which the band reader
        counts as a verdict. Whether a given run painted a pixel there
        would otherwise depend on how long the sentence was, so this
        guards the layout and lets the sweep be what finds a mistake
        rather than what certifies the absence of one.
        """
        from neural_workshop import geometry, state
        for width, height in ((800, 600), (1280, 720), (1024, 768)):
            state.window.set_size(width, height)
            geometry._size_changed()
            self.task.relayout()
            self.open_one()
            self.type_out('the quick brown horse and the rest of it')
            floor = above_the_band(0.0)
            self.assertGreaterEqual(self.task._floor(), floor,
                                    '%dx%d' % (width, height))
            for label in (self.task.line, self.task.entry):
                self.assertGreaterEqual(label.y, self.task._floor(),
                                        '%dx%d %s' % (width, height,
                                                      label.text[:20]))

    def test_the_footnote_fits_the_window(self):
        """Measured in pixels, which is not what ``set_size`` takes.

        ``set_size`` is given points and ``window.width`` reports
        pixels, and on a doubled display those differ by two. Comparing
        a label's pixel width against the points it was asked for
        reports every footnote in the Workshop as clipped, which is
        how this test read before it was pointed at the right number.
        """
        from neural_workshop import geometry, state
        for width, height in ((800, 600), (1024, 768), (1280, 800)):
            state.window.set_size(width, height)
            geometry._size_changed()
            self.task.relayout()
            self.assertLess(self.task.footnote.content_width,
                            state.window.width, '%dx%d' % (width, height))


class OnTheRealText(unittest.TestCase):
    """The two things only the fetched bank can say."""

    def setUp(self):
        if not T.have():
            self.skipTest('the sentences have not been fetched')

    def test_every_rung_has_a_thousand_lines_to_draw_on(self):
        for rung, grade in enumerate(S.GRADES, 1):
            self.assertGreater(len(T.choose(grade.span, grade.top_rank)),
                               1000, 'rung %d is thin' % rung)

    def test_no_sentence_carries_a_capital_or_a_digit(self):
        for one in T.bank()[:4000]:
            for word in one.words:
                self.assertRegex(word, r'^[a-z]+$')


if __name__ == '__main__':
    unittest.main()
