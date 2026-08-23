#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""What follows from the premises, and whether the page says it.

Everything this task claims rests on two things being true at once,
and they fail differently.

The **algebra** can be wrong: a chain of two opposites is the same, an
order is transitive but not symmetric, and two steps on a grid add.
Get one of those backwards and the task marks right answers wrong,
loudly and immediately.

The **printing** can be wrong, and that one is quiet. A negation
rendered the wrong way round, a direction put in a frame that says
something else, a premise the shuffle dropped — the generator still
knows the answer, the page no longer says it, and nothing complains.
So most of what is here reads the printed lines back with a parser
that never saw the web and solves them again.

There is a third failure that looks like success and has its own
class below: a rung that can be answered without reasoning. The
baselines are measured, not assumed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import os
import random
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('NW_HEADLESS', '1')

from uisupport import (Syllogism, TASKS, close_overlays,       # noqa: E402
                       needs_ui, reset_window)
from pyglet.window import key                                  # noqa: E402

from neural_workshop import syllogism as S             # noqa: E402
from neural_workshop.syllogism import (                # noqa: E402
    ALL, BINARY, CATEGORICAL, FORMS, GRADES, META, NONE, NOTHING, ORDER,
    PARITY, PLANE, SOME, SOME_NOT, SPACE, UNTOLD, checks_out, correct,
    deal_one, entails, generate, grade_of, nonsense, parse_line, read_back,
    satisfiable)
from neural_workshop.ui.verdict import above_the_band          # noqa: E402

#: Deals a rung, where a test wants a rung's worth rather than one.
MANY = 40

#: Words as the page has them: lower case, letters only.
WORD = re.compile(r"[A-Za-z']+")


def _tokens(text):
    return set(one.lower() for one in WORD.findall(text))


def dealt(rung, count=MANY, seed=11):
    rng = random.Random(seed + rung)
    return [one for one in (deal_one(grade_of(rung), rng)
                            for _each in range(count)) if one]


class TheLadderIsWellFormed(unittest.TestCase):
    """Declarations that have to agree with each other."""

    def test_twelve_rungs_each_with_a_builder(self):
        self.assertEqual(len(GRADES), 12)
        for grade in GRADES:
            self.assertIn(grade.family, S.BUILDERS)

    def test_a_rung_off_the_end_is_the_nearest_one(self):
        self.assertIs(grade_of(0), GRADES[0])
        self.assertIs(grade_of(99), GRADES[-1])
        self.assertIs(grade_of(5), GRADES[4])

    def test_every_rung_deals(self):
        for rung in range(1, len(GRADES) + 1):
            self.assertIsNotNone(generate(rung, seed=rung), rung)

    def test_the_same_seed_deals_the_same_question(self):
        for rung in (1, 6, 9, 12):
            self.assertEqual(generate(rung, seed=4), generate(rung, seed=4))

    def test_the_widest_answer_is_the_ports(self):
        """The boundary declares this number; it must be the real one."""
        self.assertEqual(S.MOST_OPTIONS,
                         max(len(one.options) for rung in
                             range(1, len(GRADES) + 1)
                             for one in dealt(rung, 6)))


class TheAlgebraIsRight(unittest.TestCase):
    """Composition, checked against what the words mean."""

    def test_two_opposites_make_a_same(self):
        web = self.parity(((0, 1, 1), (1, 2, 1)))
        self.assertEqual(S._relation(web, 2, 0)[0], 'the same')

    def test_a_same_and_an_opposite_make_an_opposite(self):
        web = self.parity(((0, 1, 0), (1, 2, 1)))
        self.assertEqual(S._relation(web, 2, 0)[0], 'the opposite')

    def parity(self, edges):
        grade = S.Grade('made up', PARITY, items=3)
        place, walk = [(0,)], []
        for left, right, value in edges:
            place.append(((place[left][0] + value) % 2,))
            walk.append((left, right, (value,)))
        return S.Web(grade, ('one', 'two', 'three'), tuple(walk),
                     tuple(place), (0, 0, 0))

    def test_an_order_is_transitive_and_not_symmetric(self):
        grade = S.Grade('made up', ORDER, items=3)
        web = S.Web(grade, ('low', 'mid', 'high'),
                    ((0, 1, (1,)), (1, 2, (1,))),
                    ((0,), (1,), (2,)), (0, 0, 0))
        self.assertEqual(S._relation(web, 2, 0)[0], 'more')
        self.assertEqual(S._relation(web, 0, 2)[0], 'less')

    def test_two_things_no_premise_orders_are_untold(self):
        """The whole reason *cannot be told* is an answer.

        Both are in one piece of the web and neither is above the
        other, which is not the same as being equal — nothing here is
        equal to anything.
        """
        grade = S.Grade('made up', ORDER, items=3)
        web = S.Web(grade, ('a', 'b', 'c'), ((0, 1, (1,)), (0, 2, (1,))),
                    ((0,), (1,), (2,)), (0, 0, 0))
        self.assertEqual(S._relation(web, 1, 2)[0], UNTOLD)

    def test_steps_on_a_grid_add(self):
        grade = S.Grade('made up', PLANE, items=3)
        web = S.Web(grade, ('a', 'b', 'c'),
                    ((0, 1, (1, 0)), (1, 2, (0, 1))),
                    ((0, 0), (1, 0), (1, 1)), (0, 0, 0))
        self.assertEqual(S._relation(web, 2, 0)[0], 'north and east')

    def test_steps_can_cancel(self):
        grade = S.Grade('made up', PLANE, items=3)
        web = S.Web(grade, ('a', 'b', 'c'),
                    ((0, 1, (1, 0)), (1, 2, (-1, 0))),
                    ((0, 0), (1, 0), (0, 0)), (0, 0, 0))
        self.assertEqual(S._relation(web, 2, 0)[0], 'the same place')

    def test_a_direction_names_which_sides_not_an_angle(self):
        self.assertEqual(S._direction((1, 1, 0)), 'north and east')
        self.assertEqual(S._direction((0, 0, -1)), 'below')
        self.assertEqual(S._direction((0, 0, 0)), 'the same place')
        self.assertEqual(S._signs((5, -2, 0)), (1, -1, 0))


class TheCategoricalSolverIsRight(unittest.TestCase):
    """Checked against syllogisms that have had names for centuries."""

    #: Terms are 0, 1, 2 — the third is the middle term throughout.
    def valid(self, premises, conclusion):
        return entails(3, premises, conclusion)

    def test_barbara(self):
        self.assertTrue(self.valid(((ALL, 0, 2), (ALL, 2, 1)), (ALL, 0, 1)))

    def test_celarent(self):
        self.assertTrue(self.valid(((ALL, 0, 2), (NONE, 2, 1)), (NONE, 0, 1)))

    def test_darii(self):
        self.assertTrue(self.valid(((SOME, 0, 2), (ALL, 2, 1)), (SOME, 0, 1)))

    def test_baroco(self):
        self.assertTrue(self.valid(((SOME_NOT, 0, 2), (ALL, 1, 2)),
                                   (SOME_NOT, 0, 1)))

    def test_the_undistributed_middle_is_not_valid(self):
        self.assertFalse(self.valid(((ALL, 0, 2), (ALL, 1, 2)), (ALL, 0, 1)))

    def test_an_illicit_conversion_is_not_valid(self):
        """*at least one X is not a Y* does not turn round."""
        self.assertFalse(self.valid(((SOME_NOT, 0, 1),), (SOME_NOT, 1, 0)))
        self.assertTrue(self.valid(((SOME, 0, 1),), (SOME, 1, 0)))
        self.assertTrue(self.valid(((NONE, 0, 1),), (NONE, 1, 0)))

    def test_the_reading_is_the_boolean_one(self):
        """*every X is a Y* does not say there are any X.

        The whole ladder rests on which reading this is, so it is
        asserted rather than left to whoever reads the generator.
        """
        self.assertFalse(self.valid(((ALL, 0, 1),), (SOME, 0, 1)))
        self.assertFalse(self.valid(((NONE, 0, 1),), (SOME_NOT, 0, 1)))
        self.assertTrue(satisfiable(2, ((ALL, 0, 1), (NONE, 0, 1))))

    def test_contradictory_premises_are_refused(self):
        self.assertFalse(satisfiable(2, ((ALL, 0, 1), (SOME_NOT, 0, 1))))
        self.assertFalse(satisfiable(2, ((NONE, 0, 1), (SOME, 0, 1))))

    def test_at_most_one_form_ever_follows(self):
        """Or the question would have two right answers and one port.

        Not argued from the shape of the four forms — walked, over
        every way three and four terms can be linked.
        """
        for count in (3, 4):
            for premises in S._shapes(count):
                if not satisfiable(count, premises):
                    continue
                holds = [form for form in FORMS
                         if entails(count, premises, (form, 0, count - 1))]
                self.assertLessEqual(len(holds), 1, premises)


class ThePageSaysWhatTheAnswerNeeds(unittest.TestCase):
    """Read back with a parser that never saw the web."""

    def test_every_question_reads_back_off_its_own_page(self):
        for rung in range(1, len(GRADES) + 1):
            for question in dealt(rung, 25):
                self.assertEqual(read_back(question), question.answer,
                                 '%d: %s' % (rung, question.asked))

    def test_a_dealt_question_has_been_checked_already(self):
        for rung in range(1, len(GRADES) + 1):
            for question in dealt(rung, 8):
                self.assertTrue(checks_out(question), rung)

    def test_every_premise_parses(self):
        for rung in range(1, len(GRADES) + 1):
            for question in dealt(rung, 10):
                for line in question.lines:
                    self.assertIsNotNone(parse_line(line), line)

    def test_a_negation_reads_as_what_it_means(self):
        """With no ties and no third way, these are the same premise."""
        self.assertEqual(parse_line('a is not more than b'),
                         parse_line('b is more than a'))
        self.assertEqual(parse_line('a is not less than b'),
                         parse_line('a is more than b'))
        self.assertEqual(parse_line('a is not the same as b'),
                         parse_line('a is the opposite of b'))
        self.assertEqual(parse_line('a is not the opposite of b'),
                         parse_line('a is the same as b'))

    def test_a_direction_reads_back_in_every_frame_it_is_written(self):
        self.assertEqual(parse_line('b is to the north of a'),
                         (PLANE, 'a', 'b', (1, 0)))
        self.assertEqual(parse_line('b is below a'),
                         (SPACE, 'a', 'b', (0, 0, -1)))
        self.assertEqual(parse_line('b is above and to the south of a'),
                         (SPACE, 'a', 'b', (-1, 0, 1)))
        self.assertEqual(parse_line('b is in the same place as a'),
                         (PLANE, 'a', 'b', (0, 0)))

    def test_the_four_forms_read_back(self):
        self.assertEqual(parse_line('every a is a b'),
                         (CATEGORICAL, 'a', 'b', ALL))
        self.assertEqual(parse_line('no a is a b'),
                         (CATEGORICAL, 'a', 'b', NONE))
        self.assertEqual(parse_line('at least one a is a b'),
                         (CATEGORICAL, 'a', 'b', SOME))
        self.assertEqual(parse_line('at least one a is not a b'),
                         (CATEGORICAL, 'a', 'b', SOME_NOT))

    def test_a_sentence_the_task_does_not_write_does_not_parse(self):
        for text in ('a is roughly b', '', 'a is to the sideways of b',
                     'most a are b'):
            self.assertIsNone(parse_line(text), text)

    def test_the_working_quotes_the_lines_that_were_shown(self):
        """A premise rendered twice is a premise said two ways."""
        for rung in range(1, len(GRADES) + 1):
            for question in dealt(rung, 8):
                for line in question.working:
                    if parse_line(line) is not None:
                        self.assertIn(line, question.lines,
                                      '%d: %s' % (rung, line))


class NoRungCanBeAnsweredWithoutReasoning(unittest.TestCase):
    """The failure that looks like success, so it is measured."""

    def test_no_answer_is_right_much_more_often_than_the_rest(self):
        for rung in range(1, len(GRADES) + 1):
            made = dealt(rung, 90)
            tally = collections.Counter(one.answer for one in made)
            best = tally.most_common(1)[0][1] / len(made)
            self.assertLess(best, 0.6, '%d: always answering "%s" scores %.2f'
                            % (rung, made[0].options[tally.most_common(1)[0][0]],
                               best))

    def test_the_surface_reader_does_not_beat_the_rung(self):
        """Chance, or near it, everywhere but the two-premise syllogism.

        That one is 0.5 and cannot be less: on a two-premise
        syllogism the classical rules name the right form whenever
        anything follows, so all that is left to ask is whether
        anything does. It is dealt as the coin it is.
        """
        for rung in range(1, len(GRADES) + 1):
            made = dealt(rung, 90)
            got = sum(1 for one in made if one.surface == one.answer)
            self.assertLess(got / len(made), 0.62 if rung == 5 else 0.5,
                            '%d: reading one line scores %.2f'
                            % (rung, got / len(made)))

    def test_counting_the_lines_says_nothing(self):
        """A rung where two pieces means one line fewer is a rung where
        counting the lines answers the question."""
        for rung in range(1, len(GRADES) + 1):
            if grade_of(rung).family in (BINARY, META):
                continue
            counts = set(len(one.lines) for one in dealt(rung, 40))
            self.assertEqual(len(counts), 1, '%d: %s' % (rung, counts))

    def test_the_things_asked_about_are_things_the_premises_mention(self):
        """A word that appears in no premise answers the question for you.

        It is the reason a piece of the web is never one item on its
        own: *cannot be told* would then be readable off the page
        without reading the page.
        """
        for rung in range(1, len(GRADES) + 1):
            family = grade_of(rung).family
            if family not in S.ASKED_LINE:
                continue
            for question in dealt(rung, 12):
                shown = set(' '.join(question.lines).split())
                asking = S.ASKED_LINE[family].match(question.asked)
                self.assertIsNotNone(asking, question.asked)
                for word in asking.groups():
                    self.assertIn(word, shown, '%d: %s' % (rung, word))


class WhatItOffersAndWhatItMeans(unittest.TestCase):
    """The options, and the one that is missing on purpose."""

    def test_the_options_are_the_same_at_every_deal_of_a_rung(self):
        for rung in range(1, len(GRADES) + 1):
            if grade_of(rung).family == CATEGORICAL:
                continue          # they name the terms being asked about
            offered = set(one.options for one in dealt(rung, 12))
            self.assertEqual(len(offered), 1, rung)

    def test_the_direction_rungs_do_not_offer_cannot_be_told(self):
        """They never leave a question open, and an answer that is
        never right is a free elimination."""
        for rung in (6, 9):
            for question in dealt(rung, 10):
                self.assertNotIn(UNTOLD, question.options)

    def test_every_other_rung_does(self):
        for rung in (1, 2, 3, 4, 7, 10, 11, 12):
            self.assertIn(UNTOLD, dealt(rung, 3)[0].options)
        for rung in (5, 8):
            self.assertIn(NOTHING, dealt(rung, 3)[0].options)

    def test_cannot_be_told_is_a_real_answer(self):
        for rung in (1, 2, 3, 4, 7, 10, 11, 12):
            made = dealt(rung, 60)
            where = made[0].options.index(UNTOLD)
            share = sum(1 for one in made if one.answer == where) / len(made)
            self.assertGreater(share, 0.1, rung)

    def test_the_answers_are_distinct(self):
        for rung in range(1, len(GRADES) + 1):
            for question in dealt(rung, 8):
                self.assertEqual(len(set(question.options)),
                                 len(question.options), rung)


class TheThreeValuedLogicIsKleene(unittest.TestCase):
    """The top two rungs are made of this, and it is not two-valued."""

    def test_a_false_half_settles_an_and(self):
        self.assertIs(S._kleene('and', False, None), False)
        self.assertIs(S._kleene('and', None, False), False)

    def test_a_true_half_settles_an_or(self):
        self.assertIs(S._kleene('or', True, None), True)
        self.assertIs(S._kleene('or', None, True), True)

    def test_an_unsettled_half_leaves_the_rest_unsettled(self):
        self.assertIsNone(S._kleene('and', True, None))
        self.assertIsNone(S._kleene('or', False, None))

    def test_exactly_one_of_never_settles_round_an_unsettled_half(self):
        for other in (True, False, None):
            self.assertIsNone(S._kleene('exactly one of', None, other))

    def test_it_is_otherwise_ordinary(self):
        self.assertIs(S._kleene('and', True, True), True)
        self.assertIs(S._kleene('or', False, False), False)
        self.assertIs(S._kleene('exactly one of', True, False), True)
        self.assertIs(S._kleene('exactly one of', True, True), False)


class TheThingsAreNamedAfterWords(unittest.TestCase):
    """Real nouns where the machine has them, and made up where not."""

    def setUp(self):
        self.addCleanup(S.forget)

    def spy(self, made_up):
        """Deal every rung, keeping what each deal named its things."""
        S.forget()
        if made_up:
            S._POOL = ()
        called = set()
        real = S.things

        def watch(rng, count):
            got = real(rng, count)
            called.update(got)
            return got

        S.things = watch
        try:
            printed = set()
            for rung in range(1, len(GRADES) + 1):
                for one in dealt(rung, 12):
                    printed.update(_tokens(
                        ' '.join(one.lines + one.options + one.working
                                 + (one.asked,))))
        finally:
            S.things = real
        return called, printed

    def test_they_are_words_where_the_index_has_been_fetched(self):
        if not S._pool():
            self.skipTest('no word index on this machine')
        got = S.things(random.Random(3), 14)
        for word in got:
            self.assertIn(word, S._pool())

    def test_they_are_made_up_where_it_has_not(self):
        S._POOL = ()
        got = S.things(random.Random(3), 14)
        self.assertEqual(len(set(got)), 14)
        for word in got:
            self.assertTrue(4 <= len(word) <= 8, word)

    def test_they_are_distinct_and_open_differently_either_way(self):
        for empty in (True, False):
            S.forget()
            if empty:
                S._POOL = ()
            got = S.things(random.Random(2), 14)
            self.assertEqual(len(set(got)), 14)
            self.assertEqual(len(set(one[:2] for one in got)), 14)

    def test_nothing_is_named_after_a_word_the_task_prints(self):
        """"north is north of south" is a line that reads as grammar."""
        for word in S.things(random.Random(5), 18):
            self.assertNotIn(word, S.GRAMMAR)
            self.assertNotIn(word, S.NEARLY)

    def test_the_grammar_is_the_whole_page_less_the_names(self):
        """The guard on :data:`GRAMMAR`, so a new frame cannot drift.

        Every word printed anywhere — premises, question, options,
        working — is either the name of a thing or one of the words
        the task says things in, and the second set is declared.

        Dealt both ways, because a machine with no word index deals a
        different stream and this has to be the same set on both —
        less one word. Invented names all open with a consonant, so
        "an" is a word only real ones ever call for.
        """
        for made_up in (False, True):
            called, printed = self.spy(made_up)
            self.assertEqual(printed - called,
                             S.GRAMMAR - ({'an'} if made_up else set()),
                             made_up)

    def test_a_or_an_by_how_the_name_sounds(self):
        """A question nobody had to ask while the words were invented."""
        for word, want in (('idiot', 'an'), ('bank', 'a'), ('egg', 'an'),
                           ('hour', 'an'), ('union', 'a'), ('use', 'a'),
                           ('umbrella', 'an')):
            self.assertEqual(S.article(word), want, word)

    def test_every_printed_article_agrees_with_its_name(self):
        """The renderer has to ask, not assume: "a idiot" is how it read."""
        said = re.compile(r'\b(an?) ([a-z]+)')
        seen = 0
        for rung in (5, 8):
            for one in dealt(rung, 20):
                for text in one.lines + one.options + one.working:
                    for article, name in said.findall(text):
                        self.assertEqual(article, S.article(name), text)
                        seen += 1
        self.assertGreater(seen, 100)

    def test_a_made_up_word_is_never_a_common_english_word(self):
        common = S._real_words()
        self.assertIn('water', common)
        for seed in range(8):
            for word in nonsense(random.Random(seed), 12):
                self.assertNotIn(word, common)

    def test_more_than_a_question_needs_is_refused(self):
        with self.assertRaises(ValueError):
            nonsense(random.Random(0), 200)


class TheMarkingIsExact(unittest.TestCase):
    """One answer, and nothing partial counts."""

    def test_the_answer_is_right_and_nothing_else_is(self):
        question = generate(1, seed=3)
        self.assertTrue(correct(question, question.answer))
        for number in range(len(question.options)):
            if number != question.answer:
                self.assertFalse(correct(question, number))

    def test_an_option_the_rung_does_not_have_is_wrong(self):
        question = generate(1, seed=3)
        self.assertFalse(correct(question, len(question.options)))
        self.assertFalse(correct(question, -1))
        self.assertFalse(correct(question, 99))

    def test_what_is_measured_adds_up(self):
        for rung in range(1, len(GRADES) + 1):
            for question in dealt(rung, 10):
                self.assertGreaterEqual(question.steps, 1)
                self.assertGreaterEqual(question.decoys, 0)
                if grade_of(rung).family not in (BINARY, META):
                    self.assertEqual(question.steps + question.decoys,
                                     len(question.lines), rung)

    def test_an_unsettled_answer_counts_every_line_as_a_step(self):
        """Proving that nothing links two things takes all of it."""
        for rung in (1, 3, 7):
            for question in dealt(rung, 20):
                if question.shown_answer == UNTOLD:
                    self.assertEqual(question.steps, len(question.lines))
                    self.assertEqual(question.decoys, 0)


@needs_ui
class TheSyllogismScreen(unittest.TestCase):
    """Picking, marking, and where the screen may draw."""

    def setUp(self):
        close_overlays()
        self.task = Syllogism()
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

    def test_it_is_in_the_reasoning_category(self):
        self.assertIn('syllogism', [task for task, _n in TASKS['reasoning']])

    def test_a_trial_opens_with_premises_a_question_and_answers(self):
        self.open_one()
        self.assertTrue(self.task.premises.text)
        self.assertTrue(self.task.asked.text)
        self.assertEqual(len(self.task.options),
                         len(self.task.question.options))
        self.task.on_draw()

    def test_the_convention_is_printed(self):
        """It is a choice rather than a fact, so it is on the screen."""
        self.open_one(2)
        self.assertIn('not more than', self.task.note.text)

    def test_the_arrows_walk_the_highlight_and_come_round(self):
        self.open_one()
        count = len(self.task.question.options)
        self.task.move(1)
        self.assertEqual(self.task.choice, 1)
        self.task.move(-1)
        self.assertEqual(self.task.choice, 0)
        self.task.move(-1)
        self.assertEqual(self.task.choice, count - 1)

    def test_enter_answers_the_one_highlighted(self):
        self.open_one()
        self.task.choice = self.task.question.answer
        self.task.submit()
        self.assertEqual(self.task.phase, 'judged')
        self.assertTrue(self.task.verdict_shown[0])

    def test_a_number_key_answers_outright(self):
        self.open_one()
        wanted = self.task.question.answer
        self.task.on_key_press(key._1 + wanted, 0)
        self.assertEqual(self.task.phase, 'judged')
        self.assertTrue(self.task.verdict_shown[0])

    def test_a_wrong_answer_is_told_what_it_was(self):
        self.open_one()
        self.task.choose((self.task.question.answer + 1)
                         % len(self.task.question.options))
        self.assertFalse(self.task.verdict_shown[0])
        self.assertIn(self.task.question.shown_answer, self.task.message)

    def test_an_answer_the_rung_does_not_have_does_nothing(self):
        self.open_one()
        self.task.choose(len(self.task.question.options))
        self.task.choose(-1)
        self.assertEqual(self.task.phase, 'asking')

    def test_the_working_goes_up_after_the_verdict_and_not_before(self):
        self.open_one()
        before = self.task.premises.text
        self.task.choose(self.task.question.answer)
        self.assertNotEqual(self.task.premises.text, before)
        self.assertIn(self.task.question.working[-1],
                      self.task.premises.text)

    def test_the_verdict_comes_down_when_the_next_trial_opens(self):
        self.open_one()
        self.task.choose(self.task.question.answer)
        self.task.advance()
        self.assertEqual(self.task.phase, 'asking')
        self.assertIsNone(self.task.verdict_shown)

    def test_a_click_does_not_answer(self):
        self.open_one()
        self.task.on_mouse_press(10, 10, 1, 0)
        self.assertEqual(self.task.phase, 'asking')

    def test_nothing_is_drawn_in_the_verdict_band(self):
        """Asserted against the geometry, at three window sizes.

        The answer being pointed at is blue, and blue on a pale page
        has a rim of every blend between the two, part of which the
        band reader counts as a verdict. Whether a run painted a pixel
        there would otherwise depend on how many answers were dealt —
        which is three on most rungs and twenty-seven on one.
        """
        from neural_workshop import geometry, state
        for width, height in ((800, 600), (1280, 720), (1024, 768)):
            for rung in (1, 9, 12):
                state.window.set_size(width, height)
                geometry._size_changed()
                self.task.relayout()
                self.open_one(rung)
                where = '%dx%d rung %d' % (width, height, rung)
                floor = above_the_band(0.0)
                self.assertGreaterEqual(self.task._floor(), floor, where)
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
