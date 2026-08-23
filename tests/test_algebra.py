#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Algebra: what a rung guarantees, and the two ways that can be a lie.

Two properties here matter more than everything else put together,
and both were broken when they were first written.

**The counted space has to contain the answer.** Every rung publishes
how many candidates hide its answer, and :func:`crack` walks exactly
that space. If the answer is not inside it, both numbers are
meaningless and neither says so: the column reads as difficulty and
is really a bug. The first version had it twice over — a coefficient
band too narrow for the answers the generator made, and a fraction
grid forty rows deep against denominators of seventy-two — and both
showed up as rungs that "could not be cracked", which looked like
success. :class:`TheSpaceContainsTheAnswer` is the guard.

**The forward check has to be able to fail.** Every problem is built
backwards from its answer and then checked forwards by different
code. A checker that always said yes would pass every problem,
including a broken one, and the whole generate-then-verify claim
would be decoration. So it is tested against deliberately wrong
answers, per family.

The rest is the marking: exact, with no tolerance, and refusing the
question copied back on a rung that asks you to simplify it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import os
import random
import sys
import unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('NW_HEADLESS', '1')

from uisupport import (Algebra, TASKS, close_overlays,         # noqa: E402
                       needs_ui, reset_window)
from pyglet.window import key, mouse                           # noqa: E402

from neural_workshop import algebra as A                       # noqa: E402
from neural_workshop.expressions import Poly, parse            # noqa: E402
from neural_workshop.ui.verdict import above_the_band          # noqa: E402


def dealt(rung, count=40, seed=None):
    """*count* problems at *rung*, skipping any the generator gave up on."""
    grade = A.grade_of(rung)
    rng = random.Random(rung if seed is None else seed)
    made = (A.deal_one(grade, rng) for _each in range(count))
    return [one for one in made if one is not None]


def inside(problem):
    """Whether the answer is in the space the rung counts. Exact, O(1).

    Deliberately not "did :func:`crack` find it" — that would take a
    budget of 10^28 at the top of the ladder. This is the property
    itself rather than a symptom of it.
    """
    walk = A.walk_of(problem.grade)
    if walk == 'coefficients':
        band = problem.grade.dials.get('band', 16)
        return all(abs(one) <= band
                   for one in problem.answer.terms.values())
    value = Fraction(problem.answer)
    if walk == 'fractions':
        rows, span = A.fraction_grid(problem.grade)
        return value.denominator <= rows and abs(value.numerator) <= span
    if value.denominator != 1:
        return False
    if walk == 'upward':
        return 0 <= value < problem.space
    return abs(value) <= problem.space // 2


class TheSpaceContainsTheAnswer(unittest.TestCase):
    """The one invariant both published columns rest on."""

    def test_every_rung_hides_its_answer_inside_its_own_count(self):
        for rung in range(1, len(A.GRADES) + 1):
            problems = dealt(rung, count=120, seed=900 + rung)
            self.assertTrue(problems, 'rung %d dealt nothing' % rung)
            for problem in problems:
                self.assertTrue(
                    inside(problem),
                    'rung %d: %s -> %s is outside a space of %d'
                    % (rung, problem.asked, problem.shown_answer,
                       problem.space))

    def test_the_space_and_the_count_are_the_same_number(self):
        for rung in range(1, len(A.GRADES) + 1):
            for problem in dealt(rung, count=4):
                self.assertAlmostEqual(problem.candidates,
                                       math.log10(problem.space), places=9)

    def test_a_space_that_can_be_walked_is_walked(self):
        """Where searching is affordable, it really does find it."""
        for rung in (1, 2, 3, 4, 6, 7, 8):
            for problem in dealt(rung, count=6):
                self.assertIsNotNone(
                    A.crack(problem),
                    'rung %d could not crack %s' % (rung, problem.asked))


class TheForwardCheckIsNotVacuous(unittest.TestCase):
    """A checker that cannot fail proves nothing about a generator."""

    def wrong_answer(self, problem):
        if problem.grade.kind == A.EXPRESSION:
            return problem._replace(answer=problem.answer + Poly.constant(1))
        return problem._replace(
            answer=Fraction(problem.answer) + 1)   # type: ignore[arg-type]

    def test_a_wrong_answer_is_refused_on_every_rung(self):
        for rung in range(1, len(A.GRADES) + 1):
            for problem in dealt(rung, count=6, seed=40 + rung):
                self.assertTrue(A.checks_out(problem), problem.asked)
                self.assertFalse(A.checks_out(self.wrong_answer(problem)),
                                 'rung %d accepted a wrong answer for %s'
                                 % (rung, problem.asked))

    def test_every_dealt_problem_has_already_been_checked(self):
        for rung in range(1, len(A.GRADES) + 1):
            for problem in dealt(rung, count=8, seed=70 + rung):
                self.assertTrue(A.checks_out(problem))


class TheCongruencesReallyHold(unittest.TestCase):
    """Recomputed from the printed question, not from the generator."""

    def test_the_answer_satisfies_every_congruence_shown(self):
        for rung in (10, 12):
            for problem in dealt(rung, count=8, seed=rung):
                answer = int(Fraction(problem.answer))
                for part in problem.asked.split(',  '):
                    left, right = part.strip().split(' = ')
                    value, modulus = right.split(' (mod ')
                    self.assertEqual(answer % int(modulus.rstrip(')')),
                                     int(value), problem.asked)

    def test_the_answer_is_the_smallest_one_that_does(self):
        for problem in dealt(10, count=6, seed=3):
            answer = int(Fraction(problem.answer))
            product = problem.space
            self.assertGreaterEqual(answer, 0)
            self.assertLess(answer, product)

    def test_the_moduli_are_coprime_so_there_is_exactly_one(self):
        for rung in (10, 12):
            for problem in dealt(rung, count=6, seed=rung):
                moduli = [int(part.split(' (mod ')[1].rstrip(')'))
                          for part in problem.asked.split(',  ')]
                self.assertEqual(len(set(moduli)), len(moduli))
                for one in range(len(moduli)):
                    for two in range(one + 1, len(moduli)):
                        self.assertEqual(math.gcd(moduli[one], moduli[two]), 1)

    def test_the_top_rung_hides_it_in_a_box_nothing_will_search(self):
        for problem in dealt(12, count=5, seed=8):
            self.assertGreater(problem.candidates, 20)
            self.assertIsNone(A.crack(problem, budget=20000))


class MarkingIsExact(unittest.TestCase):
    """No tolerance anywhere, on either kind of answer."""

    def test_the_answer_is_right(self):
        for rung in range(1, len(A.GRADES) + 1):
            for problem in dealt(rung, count=4, seed=11 + rung):
                self.assertTrue(A.correct(problem, problem.shown_answer),
                                '%s -> %s' % (problem.asked,
                                              problem.shown_answer))

    def test_a_fraction_written_differently_is_the_same_answer(self):
        problem = dealt(5, count=1, seed=8)[0]
        value = Fraction(problem.answer)
        doubled = '%d/%d' % (value.numerator * 2, value.denominator * 2)
        self.assertTrue(A.correct(problem, doubled))

    def test_a_decimal_is_not_an_answer(self):
        problem = dealt(5, count=1, seed=8)[0]
        self.assertFalse(A.correct(problem, '1.828'))

    def test_nothing_typed_is_not_an_answer(self):
        for problem in dealt(1, count=2):
            self.assertFalse(A.correct(problem, ''))
            self.assertFalse(A.correct(problem, '   '))

    def test_one_out_is_wrong(self):
        for rung in (1, 8, 10, 12):
            problem = dealt(rung, count=1, seed=rung)[0]
            wrong = str(int(Fraction(problem.answer)) + 1)
            self.assertFalse(A.correct(problem, wrong))

    def test_an_expression_may_be_written_in_any_order(self):
        problem = dealt(9, count=1, seed=4)[0]
        terms = A.render_terms(problem.answer) \
            if hasattr(A, 'render_terms') else None
        self.assertIsNone(terms)         # no such helper; ordering below
        backwards = ' + '.join(reversed(
            problem.shown_answer.replace(' - ', ' + -').split(' + ')))
        self.assertTrue(A.correct(problem, backwards),
                        '%s vs %s' % (problem.shown_answer, backwards))

    def test_an_explicit_times_sign_is_allowed(self):
        problem = dealt(7, count=1, seed=2)[0]
        spelled = problem.shown_answer.replace('x', '*x')
        if spelled.startswith('*'):
            spelled = spelled[1:]
        self.assertTrue(A.correct(problem, spelled.replace('-*x', '-x')))


class CopyingTheQuestionIsNotAnAnswer(unittest.TestCase):
    """The hazard normal-form marking creates, and the guard for it.

    A question and its own answer are the same polynomial, so equality
    alone would mark the question copied back as right and the rung
    would be a copying exercise rather than a collecting one.
    """

    def test_the_question_is_refused_on_every_symbolic_rung(self):
        for rung in (7, 9, 11):
            for problem in dealt(rung, count=10, seed=rung):
                self.assertEqual(parse(problem.asked), problem.answer,
                                 'the question is not its own answer?')
                self.assertFalse(A.correct(problem, problem.asked),
                                 'rung %d marked the question right: %s'
                                 % (rung, problem.asked))

    def test_a_bracket_left_in_is_refused(self):
        problem = dealt(9, count=1, seed=4)[0]
        self.assertFalse(A.correct(problem, '(%s)' % problem.shown_answer))

    def test_the_gathered_answer_is_accepted(self):
        for rung in (7, 9, 11):
            for problem in dealt(rung, count=6, seed=rung):
                self.assertTrue(A.correct(problem, problem.shown_answer))

    def test_collected_counts_terms_rather_than_policing_spelling(self):
        answer = parse('2y + 3')
        self.assertTrue(A.collected('2y+3', answer))
        self.assertTrue(A.collected('3 + 2y', answer))
        self.assertTrue(A.collected('2*y + 3', answer))
        self.assertFalse(A.collected('y + y + 3', answer))
        self.assertFalse(A.collected('(4y+6)/2', answer))


class EveryRungIsWhatItSaysItIs(unittest.TestCase):
    """The table and the deals agreeing with each other."""

    def test_every_rung_deals(self):
        for rung in range(1, len(A.GRADES) + 1):
            self.assertTrue(dealt(rung, count=5), 'rung %d dealt nothing'
                            % rung)

    def test_the_answer_is_the_kind_the_rung_declares(self):
        for rung in range(1, len(A.GRADES) + 1):
            for problem in dealt(rung, count=5):
                if problem.grade.kind == A.EXPRESSION:
                    self.assertIsInstance(problem.answer, Poly)
                else:
                    self.assertIsInstance(Fraction(problem.answer), Fraction)

    def test_a_symbolic_answer_really_has_more_than_one_term(self):
        """A one-term answer is not a collecting exercise."""
        for rung in (7, 9, 11):
            for problem in dealt(rung, count=40, seed=rung):
                self.assertGreaterEqual(len(problem.answer.terms), 2,
                                        problem.asked)

    def test_every_problem_shows_its_working(self):
        for rung in range(1, len(A.GRADES) + 1):
            for problem in dealt(rung, count=3):
                self.assertTrue(problem.working)
                for line in problem.working:
                    self.assertTrue(line.strip())

    def test_the_same_seed_deals_the_same_problem(self):
        for rung in (1, 7, 12):
            one, other = A.generate(rung, seed=99), A.generate(rung, seed=99)
            self.assertEqual(one, other)

    def test_the_letters_used_are_the_letters_the_screen_offers(self):
        from nwenv.algebra import KEYS
        for rung in (7, 9, 11):
            for problem in dealt(rung, count=6, seed=rung):
                for name in problem.answer.variables():
                    self.assertIn(name, KEYS)


class TheLadderClimbs(unittest.TestCase):
    """Its shape, checked. The exact numbers live in bench_algebra.py."""

    def cracked(self, rung, count=8):
        problems = dealt(rung, count=count, seed=200 + rung)
        got = [A.crack(one, budget=50000) for one in problems]
        return sum(1 for one in got if one is not None) / max(1, len(got))

    def test_the_bottom_gives_itself_away_to_searching(self):
        for rung in (1, 2, 3, 4):
            self.assertEqual(self.cracked(rung), 1.0)

    def test_the_top_does_not(self):
        for rung in (11, 12):
            self.assertEqual(self.cracked(rung, count=4), 0.0)

    def test_the_search_grows_from_the_bottom_to_the_top(self):
        low = max(one.candidates for one in dealt(1, count=20))
        high = min(one.candidates for one in dealt(12, count=6))
        self.assertGreater(high, low + 20)

    def test_zero_is_the_guess_worth_measuring(self):
        """The floor below the floor, and it belongs in the table."""
        for rung in (1, 2, 3):
            problems = dealt(rung, count=60, seed=rung)
            share = sum(1 for one in problems
                        if A.guessable(one)) / len(problems)
            self.assertLess(share, 0.5)


@needs_ui
class TheAlgebraScreen(unittest.TestCase):
    """Typing, marking, and where the screen may draw."""

    def setUp(self):
        close_overlays()
        self.task = Algebra()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.start_rung = self.task.rung = 1

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def open_one(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'working')

    def type_out(self, text):
        for character in text:
            self.task.write(character)

    def test_it_is_in_the_reasoning_category(self):
        self.assertIn('algebra', [task for task, _n in TASKS['reasoning']])

    def test_a_trial_opens_with_a_question_and_an_empty_answer(self):
        self.open_one()
        self.assertTrue(self.task.problem.asked)
        self.assertEqual(self.task.typed, '')
        self.task.on_draw()

    def test_characters_go_into_the_answer(self):
        self.open_one()
        self.type_out('12')
        self.assertEqual(self.task.typed, '12')

    def test_a_character_the_task_does_not_take_is_ignored(self):
        self.open_one()
        self.type_out('1q!2')
        self.assertEqual(self.task.typed, '12')

    def test_rubbing_out_takes_the_last_character(self):
        self.open_one()
        self.type_out('123')
        self.task.erase()
        self.assertEqual(self.task.typed, '12')

    def test_an_empty_answer_cannot_be_submitted(self):
        self.open_one()
        self.task.submit()
        self.assertEqual(self.task.phase, 'working')

    def test_the_right_answer_is_green(self):
        self.open_one()
        self.type_out(self.task.problem.shown_answer)
        self.task.submit()
        self.assertEqual(self.task.phase, 'judged')
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.score()['right'], 1)

    def test_a_wrong_answer_is_red_and_is_told_the_answer(self):
        self.open_one()
        answer = self.task.problem.shown_answer
        self.type_out('99999')
        self.task.submit()
        self.assertFalse(self.task.verdict_shown[0])
        self.assertIn(answer, self.task.message)

    def test_the_working_is_shown_only_after_the_answer_is_in(self):
        self.task.show_working = True
        self.open_one()
        self.assertNotIn(self.task.problem.working[0], self.task.working.text)
        self.type_out('99999')
        self.task.submit()
        self.assertIn(self.task.problem.working[0], self.task.working.text)

    def test_the_working_can_be_turned_off(self):
        self.task.show_working = False
        self.open_one()
        self.type_out('99999')
        self.task.submit()
        self.assertEqual(self.task.working.text, '')

    def test_no_verdict_is_up_while_it_can_still_be_answered(self):
        self.open_one()
        self.assertIsNone(self.task.verdict_shown)
        self.type_out('1')
        self.assertIsNone(self.task.verdict_shown)

    def test_the_next_question_takes_the_verdict_down(self):
        self.open_one()
        self.type_out('99999')
        self.task.submit()
        self.assertIsNotNone(self.task.verdict_shown)
        self.task.advance()
        self.assertEqual(self.task.phase, 'working')
        self.assertIsNone(self.task.verdict_shown)

    def test_a_run_ends_after_its_questions(self):
        self.open_one()
        for _each in range(2):
            self.type_out('99999')
            self.task.submit()
            self.task.advance()
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['asked'], 2)

    def test_climbing_needs_the_answer_right(self):
        self.task.adaptive = True
        self.open_one()
        self.type_out(self.task.problem.shown_answer)
        self.task.submit()
        self.assertEqual(self.task.rung, 2)

    def test_a_wrong_answer_climbs_back_down(self):
        self.task.adaptive = True
        self.task.start_rung = self.task.rung = 4
        self.open_one()
        self.type_out('99999')
        self.task.submit()
        self.assertEqual(self.task.rung, 3)

    def test_typing_comes_through_on_text(self):
        """Because a plus sign is a different key on a different board."""
        self.open_one()
        self.task.on_text('3')
        self.task.on_text('+')
        self.assertEqual(self.task.typed, '3+')

    def test_enter_marks_and_a_click_moves_on(self):
        self.open_one()
        self.type_out('7')
        self.task.on_key_press(key.ENTER, 0)
        self.assertEqual(self.task.phase, 'judged')
        self.task.on_mouse_press(10, 10, mouse.LEFT, 0)
        self.assertEqual(self.task.phase, 'working')

    def test_space_does_not_start_a_run_while_one_is_open(self):
        self.open_one()
        before = self.task.problem
        self.task.on_key_press(key.SPACE, 0)
        self.assertIs(self.task.problem, before)

    def test_the_search_size_is_printed_and_grows_with_the_rung(self):
        from neural_workshop.ui.algebra import search_line
        low = A.generate(1, seed=3)
        high = A.generate(12, seed=3)
        self.assertIn('one of about', search_line(low))
        self.assertIn('10^', search_line(high))

    def test_nothing_is_drawn_in_the_verdict_band(self):
        """Asserted against the geometry, at three window sizes.

        The typed line is blue, and blue on a pale page has a rim of
        every blend between the two, part of which the band reader
        counts as a verdict. Whether a run painted a pixel there would
        otherwise depend on how long the answer was.
        """
        from neural_workshop import geometry, state
        for width, height in ((800, 600), (1280, 720), (1024, 768)):
            state.window.set_size(width, height)
            geometry._size_changed()
            self.task.relayout()
            self.open_one()
            self.type_out('123456789')
            floor = above_the_band(0.0)
            self.assertGreaterEqual(self.task._floor(), floor,
                                    '%dx%d' % (width, height))
            for label in (self.task.question, self.task.working,
                          self.task.entry):
                self.assertGreaterEqual(label.y, self.task._floor(),
                                        '%dx%d' % (width, height))

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
