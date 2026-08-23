#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The trivia pool, the wrong answers, and the page they are drawn on.

The questions here are somebody else's and are not checked: TriviaQA
says what the answer is and this game repeats it. What *is* checked is
everything the game adds on top, and all of it can be wrong quietly.

A **wrong answer that is right** is the failure that matters. Two of a
dataset's rows can give the same answer under different names —
*Chicago* and *Chicago, Illinois* — and offering one as the other's
distractor makes a question with two right options on it, which is
marked wrong half the time and looks like a hard question. Nothing
crashes. So the alias check has a class to itself.

A **shape that leaks** is the quiet one. If a year is the only date on
a screen of six names, the question is answerable without knowing
anything, and a learner that finds that out has learnt nothing about
trivia and everything about this file. The matched rungs are measured
rather than asserted.

The **band** and the **clock** are the boundary's two standing
requirements, and both are asserted against the geometry rather than
against a sweep, for the reason ADDING_A_TASK.md gives: what this task
draws depends on how many options were dealt and how long they are.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import json
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

from uisupport import (TASKS, Trivia, close_overlays,          # noqa: E402
                       needs_ui, reset_window)
from pyglet.window import key                                  # noqa: E402

from neural_workshop import trivia as T                        # noqa: E402
from neural_workshop.trivia import (                           # noqa: E402
    GRADES, MOST_OPTIONS, Bank, Question, bank, correct, distractors,
    generate, grade_at, kind_of, normalise, question_from)
from neural_workshop.ui.verdict import above_the_band          # noqa: E402

#: Deals a rung, where a test wants a rung's worth rather than one.
MANY = 60

SEED_BANK = Bank(T.SEED)


def dealt(rung, count=MANY, seed=5, pool=SEED_BANK):
    return [generate(rung, seed=seed * 1000 + one, pool=pool)
            for one in range(count)]


class TheLadderIsWellFormed(unittest.TestCase):
    """Declarations that have to agree with each other."""

    def test_seven_rungs_that_never_narrow(self):
        self.assertEqual(len(GRADES), 7)
        widths = [grade.options for grade in GRADES]
        self.assertEqual(widths, sorted(widths))

    def test_matching_comes_in_and_stays_in(self):
        """A rung that dropped the matching again would be easier than
        the one below it while claiming to be harder."""
        matched = [grade.matched for grade in GRADES]
        self.assertEqual(matched, sorted(matched))

    def test_the_widest_rung_is_the_ports(self):
        self.assertEqual(MOST_OPTIONS,
                         max(grade.options for grade in GRADES))

    def test_a_rung_off_the_end_is_the_nearest_one(self):
        self.assertEqual(grade_at(0), GRADES[0])
        self.assertEqual(grade_at(99), GRADES[-1])

    def test_every_rung_deals_from_the_seed(self):
        for rung in range(1, len(GRADES) + 1):
            for one in dealt(rung, 6, seed=rung):
                self.assertIsNotNone(one, rung)
                self.assertEqual(len(one.options), grade_at(rung).options)

    def test_the_same_seed_deals_the_same_question(self):
        first = generate(5, seed=77, pool=SEED_BANK)
        again = generate(5, seed=77, pool=SEED_BANK)
        self.assertEqual(first, again)


class TheShapesAreShapes(unittest.TestCase):
    """:func:`kind_of` reads capitals and digits, and nothing else."""

    def test_a_four_digit_number_in_range_is_a_year(self):
        for text in ('1969', '1066', '1990s'):
            self.assertEqual(kind_of(text), 'year', text)

    def test_and_out_of_range_it_is_a_number(self):
        for text in ('206', '4', '88', '13', '2400'):
            self.assertEqual(kind_of(text), 'number', text)

    def test_capitalised_words_are_a_name(self):
        for text in ('Sinclair Lewis', 'Leonardo da Vinci', 'Pink Floyd',
                     'the Caspian Sea'):
            self.assertEqual(kind_of(text), 'name', text)

    def test_a_leading_article_is_not_part_of_the_shape(self):
        self.assertEqual(kind_of('the femur'), 'word')
        self.assertEqual(kind_of('femur'), 'word')

    def test_anything_else_multiword_is_a_phrase(self):
        for text in ('the Sound of Music', 'To Kill a Mockingbird',
                     '7 million'):
            self.assertEqual(kind_of(text), 'phrase', text)

    def test_the_seed_fills_every_shape_wide_enough_for_the_top_rung(self):
        """Otherwise the top rung silently falls back to mixed options
        on the shapes the seed is thin in, and a player who never
        fetched anything is playing rung four in rung seven's clothes.
        """
        self.assertGreaterEqual(SEED_BANK.narrowest(), MOST_OPTIONS)


class NormalisingIsHowTwoAnswersAreCompared(unittest.TestCase):

    def test_case_punctuation_and_articles_come_out(self):
        self.assertEqual(normalise('The Beatles!'), 'beatles')
        self.assertEqual(normalise('Chicago, Illinois'), 'chicago illinois')

    def test_two_spellings_of_one_answer_meet(self):
        self.assertEqual(normalise('J. K. Rowling'), normalise('J K Rowling'))


class DistillingARow(unittest.TestCase):
    """What a dataset row has to be to become a question."""

    GOOD = {'question': 'Which American-born Sinclair won the Nobel Prize '
                        'for Literature in 1930?',
            'answer': {'value': 'Sinclair Lewis',
                       'aliases': ['Harry Sinclair Lewis']}}

    def test_a_good_row_comes_through_with_its_aliases(self):
        made = question_from(self.GOOD)
        self.assertEqual(made.answer, 'Sinclair Lewis')
        self.assertEqual(made.kind, 'name')
        self.assertIn(normalise('Harry Sinclair Lewis'), made.aliases)
        self.assertIn(normalise('Sinclair Lewis'), made.aliases)

    def test_a_row_that_prints_its_own_answer_is_refused(self):
        self.assertIsNone(question_from(
            {'question': 'In which decade did Elvis Presley die, the 1970s '
                         'or the 1980s?',
             'answer': {'value': '1970s'}}))

    def test_a_yes_or_no_is_refused(self):
        self.assertIsNone(question_from(
            {'question': 'Is the Earth round, as the ancients knew?',
             'answer': {'value': 'Yes'}}))

    def test_an_answer_too_long_to_be_an_option_is_refused(self):
        self.assertIsNone(question_from(
            {'question': 'What did the note on the door of the house say '
                         'to the milkman?',
             'answer': {'value': 'x' * (T.ANSWER_CHARS + 1)}}))

    def test_a_question_too_long_for_the_page_is_refused(self):
        self.assertIsNone(question_from(
            {'question': 'Which? ' + 'word ' * 60,
             'answer': {'value': 'Norway'}}))

    def test_an_empty_row_is_refused(self):
        self.assertIsNone(question_from({}))


class AWrongAnswerHasToBeWrong(unittest.TestCase):
    """The alias check, in both directions."""

    def bench(self):
        return Bank((
            Question('Which city does David Soul come from?', 'Chicago',
                     'word', frozenset(('chicago', 'chicago illinois'))),
            Question('Which city has the Willis Tower?', 'Chicago, Illinois',
                     'phrase', frozenset(('chicago illinois', 'chicago'))),
            Question('Which city has the Colosseum?', 'Rome', 'word',
                     frozenset(('rome',))),
        ))

    def test_the_same_answer_under_another_name_is_never_offered(self):
        pool = self.bench()
        asked = pool.questions[0]
        for seed in range(20):
            wrong = distractors(asked, pool, 2, False, random.Random(seed))
            self.assertNotIn('Chicago, Illinois', wrong, seed)
            self.assertEqual(wrong, ['Rome'])

    def test_and_not_the_other_way_round_either(self):
        pool = self.bench()
        asked = pool.questions[1]
        for seed in range(20):
            wrong = distractors(asked, pool, 2, False, random.Random(seed))
            self.assertNotIn('Chicago', wrong, seed)

    def test_no_option_is_ever_written_twice(self):
        for rung in range(1, len(GRADES) + 1):
            for one in dealt(rung, 20, seed=rung):
                plain = [normalise(text) for text in one.options]
                self.assertEqual(len(set(plain)), len(plain), one.options)

    def test_exactly_one_option_is_the_answer(self):
        for rung in (1, 4, 7):
            for one in dealt(rung, 20, seed=rung):
                right = [number for number in range(len(one.options))
                         if correct(one, number)]
                self.assertEqual(right, [one.answer])

    def test_an_answer_the_question_already_prints_is_not_offered(self):
        pool = Bank((
            Question('Which sea is named for Rome?', 'Tyrrhenian', 'word',
                     frozenset(('tyrrhenian',))),
            Question('Which city has the Colosseum?', 'Rome', 'word',
                     frozenset(('rome',))),
            Question('Which city has the Eiffel Tower?', 'Paris', 'word',
                     frozenset(('paris',))),
        ))
        for seed in range(20):
            wrong = distractors(pool.questions[0], pool, 2, False,
                                random.Random(seed))
            self.assertEqual(wrong, ['Paris'], seed)


class TheShapeIsNotTheAnswer(unittest.TestCase):
    """What the matched rungs are for, measured rather than asserted."""

    def shapes(self, rung):
        """How often the right answer is the only one of its shape."""
        alone = 0
        rounds = [one for one in dealt(rung, MANY, seed=rung) if one]
        for one in rounds:
            kinds = collections.Counter(kind_of(text) for text in one.options)
            if kinds[kind_of(one.shown_answer)] == 1:
                alone += 1
        return alone / float(len(rounds))

    def test_unmatched_rungs_leak_the_shape_constantly(self):
        """Not a defect of those rungs — it is what they are.

        Printed here because it is the thing the ladder climbs away
        from, and a rung one that stopped leaking would mean the
        matching had crept downwards and the low rungs had quietly
        become the high ones.
        """
        self.assertGreater(self.shapes(1), 0.4)

    def test_matched_rungs_hardly_ever_do(self):
        for rung in (4, 5, 6, 7):
            self.assertLess(self.shapes(rung), 0.05, rung)

    def test_the_answer_is_not_the_longest_option_more_than_by_chance(self):
        """The other free tell a multiple-choice list can carry.

        *Strictly* longest, and the difference is not pedantry: a
        matched year rung offers eight answers of four characters
        each, so counting ties would report the answer as longest on
        every one of them and this test would be measuring how often
        a year was dealt.
        """
        for rung in (4, 7):
            rounds = [one for one in dealt(rung, 240, seed=rung * 3) if one]
            longest = sum(
                1 for one in rounds
                if all(len(one.shown_answer) > len(text)
                       for number, text in enumerate(one.options)
                       if number != one.answer))
            share = longest / float(len(rounds))
            self.assertLess(share, 1.0 / grade_at(rung).options, rung)

    def test_no_position_is_the_answer_much_more_often_than_the_rest(self):
        counted = collections.Counter(
            one.answer for one in dealt(4, 240, seed=9) if one)
        for spot in range(grade_at(4).options):
            self.assertGreater(counted[spot], 240 / 4 * 0.6, counted)


class AThinPoolIsDealtRatherThanRefused(unittest.TestCase):
    """The fallbacks, which are the honest ones and not silent."""

    def test_a_pool_with_one_shape_still_fills_a_matched_rung(self):
        pool = Bank([one for one in T.SEED if one.kind == 'year'][:3]
                    + [one for one in T.SEED if one.kind == 'word'])
        made = generate(7, seed=3, pool=pool)
        self.assertEqual(len(made.options), 8)

    def test_a_pool_too_small_for_the_rung_is_dealt_narrower(self):
        pool = Bank(T.SEED[:3])
        made = generate(7, seed=3, pool=pool)
        self.assertEqual(len(made.options), 3)

    def test_an_empty_pool_deals_nothing_rather_than_something_empty(self):
        self.assertIsNone(generate(1, seed=0, pool=Bank(())))


class TheIndexRoundTrips(unittest.TestCase):
    """Fetched pages in, one tab-separated file out, questions back.

    No network: the pages are written by hand in the shape the
    datasets-server returns, which is the shape :func:`question_from`
    is written against.
    """

    PAGE = {'rows': [
        {'row_idx': 0,
         'row': {'question': 'Which American-born Sinclair won the Nobel '
                             'Prize for Literature in 1930?',
                 'answer': {'value': 'Sinclair Lewis',
                            'aliases': ['Harry Sinclair Lewis']}}},
        {'row_idx': 1,
         'row': {'question': 'From which country did Angola achieve '
                             'independence in 1975?',
                 'answer': {'value': 'Portugal', 'aliases': ['PORTUGAL']}}},
        # The same question again, which the dataset does hold: two
        # rows with the same question and different evidence.
        {'row_idx': 2,
         'row': {'question': 'From which country did Angola achieve '
                             'independence in 1975?',
                 'answer': {'value': 'Portugal', 'aliases': []}}},
        {'row_idx': 3, 'row': {'question': 'Too short?',
                               'answer': {'value': 'No'}}},
    ]}

    def setUp(self):
        self.where = tempfile.mkdtemp(prefix='nw-trivia-')
        sys.argv.append('--datadir')
        sys.argv.append(self.where)
        T.forget()

    def tearDown(self):
        sys.argv.remove(self.where)
        sys.argv.remove('--datadir')
        T.forget()
        shutil.rmtree(self.where, ignore_errors=True)

    def write_page(self, offset=0):
        with open(T.page_path(offset), 'w', encoding='utf-8') as handle:
            json.dump(self.PAGE, handle)

    def test_nothing_fetched_deals_from_the_seed(self):
        self.assertFalse(T.fetched())
        self.assertEqual(len(bank()), len(T.SEED))

    def test_a_page_is_distilled_and_read_back(self):
        self.write_page()
        self.assertEqual(T.build_index(), 2)
        self.assertTrue(T.index_ready())
        T.forget()
        pool = bank()
        self.assertTrue(T.fetched())
        self.assertEqual(sorted(one.answer for one in pool.questions),
                         ['Portugal', 'Sinclair Lewis'])
        kept = [one for one in pool.questions if one.answer == 'Portugal'][0]
        self.assertIn(normalise('PORTUGAL'), kept.aliases)

    def test_a_page_already_here_is_not_fetched_again(self):
        """The whole of the resume: no network is touched for it."""
        self.write_page()
        self.assertEqual(T.fetch(T.PAGE), T.PAGE)

    def test_a_page_written_after_the_index_makes_it_stale(self):
        self.write_page()
        T.build_index()
        self.write_page(T.PAGE)
        self.assertFalse(T.index_ready())

    def test_the_missing_message_says_what_and_how(self):
        said = T.missing_message()
        self.assertIn(T.REPO, said)
        self.assertIn('python -m neural_workshop.trivia', said)


@needs_ui
class TheTriviaScreen(unittest.TestCase):
    """Picking, marking, and where the screen may draw."""

    def setUp(self):
        close_overlays()
        self.task = Trivia()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.start_rung = self.task.rung = 1

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def open_one(self, rung=1):
        self.task.start_rung = self.task.rung = rung
        self.task.start_run()
        self.assertEqual(self.task.phase, 'asking')

    def test_it_is_in_the_long_term_memory_category(self):
        self.assertIn('trivia',
                      [task for task, _n in TASKS['long_term_memory']])

    def test_a_trial_opens_with_a_question_and_its_options(self):
        self.open_one()
        self.assertTrue(self.task.asked.text)
        self.assertEqual(len(self.task.options),
                         len(self.task.round.options))
        self.task.on_draw()

    def test_the_rung_reaches_the_deal(self):
        for rung in (1, 4, 7):
            self.open_one(rung)
            self.assertEqual(len(self.task.round.options),
                             grade_at(rung).options)

    def test_the_arrows_walk_the_highlight_and_come_round(self):
        self.open_one(3)
        count = len(self.task.round.options)
        self.task.move(1)
        self.assertEqual(self.task.choice, 1)
        self.task.move(-1)
        self.assertEqual(self.task.choice, 0)
        self.task.move(-1)
        self.assertEqual(self.task.choice, count - 1)

    def test_enter_answers_the_one_highlighted(self):
        self.open_one()
        self.task.choice = self.task.round.answer
        self.task.submit()
        self.assertEqual(self.task.phase, 'judged')
        self.assertTrue(self.task.verdict_shown[0])

    def test_a_number_key_answers_outright(self):
        self.open_one(7)
        wanted = self.task.round.answer
        self.task.on_key_press(key._1 + wanted, 0)
        self.assertEqual(self.task.phase, 'judged')
        self.assertTrue(self.task.verdict_shown[0])

    def test_a_wrong_answer_is_told_what_it_was(self):
        self.open_one()
        self.task.choose((self.task.round.answer + 1)
                         % len(self.task.round.options))
        self.assertFalse(self.task.verdict_shown[0])
        self.assertIn(self.task.round.shown_answer, self.task.message)

    def test_an_option_the_rung_does_not_have_does_nothing(self):
        self.open_one()
        self.task.choose(len(self.task.round.options))
        self.task.choose(-1)
        self.assertEqual(self.task.phase, 'asking')

    def test_the_right_option_is_marked_only_after_the_answer(self):
        """Painted a frame early it would be the answer key."""
        from neural_workshop.ui.trivia import RIGHT
        self.open_one(4)
        marked = [label.color[:3] for label in self.task.options]
        self.assertNotIn(RIGHT, marked)
        self.task.choose((self.task.round.answer + 1)
                         % len(self.task.round.options))
        self.assertEqual(self.task.options[self.task.round.answer].color[:3],
                         RIGHT)

    def test_the_verdict_comes_down_when_the_next_trial_opens(self):
        self.open_one()
        self.task.choose(self.task.round.answer)
        self.task.advance()
        self.assertEqual(self.task.phase, 'asking')
        self.assertIsNone(self.task.verdict_shown)

    def test_a_click_does_not_answer(self):
        self.open_one()
        self.task.on_mouse_press(10, 10, 1, 0)
        self.assertEqual(self.task.phase, 'asking')

    def test_the_clock_is_the_one_the_driver_owns(self):
        """A stepped run advances a virtual clock, and the time a
        question took has to come off that one."""
        self.task.clock = lambda: 1234.0
        self.open_one()
        self.assertEqual(self.task.started_at, 1234.0)
        self.task.clock = lambda: 1240.0
        self.task.choose(self.task.round.answer)
        self.assertAlmostEqual(self.task.results[-1][2], 6.0)

    def test_nothing_is_drawn_in_the_verdict_band(self):
        """Asserted against the geometry, at three window sizes.

        The option being pointed at is blue and the right one green,
        and either on a pale page has a rim of every blend between it
        and the background, part of which the band reader counts as a
        verdict. Whether a run painted a pixel there would otherwise
        depend on how many options were dealt, which is two on the
        bottom rung and eight on the top.
        """
        from neural_workshop import geometry, state
        for width, height in ((800, 600), (1280, 720), (1024, 768)):
            for rung in (1, 4, 7):
                state.window.set_size(width, height)
                geometry._size_changed()
                self.task.relayout()
                self.open_one(rung)
                where = '%dx%d rung %d' % (width, height, rung)
                self.assertGreaterEqual(self.task._floor(),
                                        above_the_band(0.0), where)
                for label in self.task.options:
                    self.assertGreaterEqual(label.y, self.task._floor(),
                                            where)

    def test_the_footnote_fits_the_window(self):
        from neural_workshop import geometry, state
        for width, height in ((800, 600), (1024, 768), (1280, 800)):
            state.window.set_size(width, height)
            geometry._size_changed()
            self.task.relayout()
            self.assertLess(self.task.footnote.content_width,
                            state.window.width, '%dx%d' % (width, height))


if __name__ == '__main__':
    unittest.main()
