#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The crossword generator: the shape, the fill, and what a rung promises.

A generated crossword can be wrong in two ways that do not look wrong.
The grid can be *nearly* fully checked — one cell in the corner that
only one clue reaches — and the puzzle then has a letter nobody can
deduce, which reads to a solver as their own failure. Or the fill can
be almost right: every across entry a word and one down entry not
quite, which is only noticed by the person who cannot finish it. Both
are checked here against every cell rather than sampled.

The pool these run on is a small made-up one, so nothing here depends
on the word list having been fetched. Two tests at the end do, and
they say so.

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

from uisupport import (Crossword, TASKS, close_overlays,       # noqa: E402
                       needs_ui, reset_window)

from neural_workshop import crossword as C                    # noqa: E402
from neural_workshop import wordlist as W                     # noqa: E402
from neural_workshop.ui.verdict import above_the_band         # noqa: E402

#: A pool that owes nothing to whether anything has been fetched:
#: :data:`neural_workshop.wordlist.SEED` is in the repository, and a
#: made-up clue apiece is enough, because nothing in the generator
#: reads a clue for anything but copying it onto a slot.
def pocket() -> W.Lexicon:
    return W.Lexicon(W.Entry(one.word, one.rank, 'clue for %s' % one.word)
                     for one in W.SEED)


#: A seven by seven lattice with every run exactly three: a whole row
#: and a whole column blocked. Written out rather than generated, so
#: the fill tests are about the fill.
LATTICE = frozenset([3 + 7 * row for row in range(7)]
                    + [3 * 7 + col for col in range(7)])


class AGridIsFullyChecked(unittest.TestCase):
    """Every cell reachable two ways, or the grid is not dealt."""

    def test_runs_are_the_maximal_unblocked_stretches(self):
        blocks = {1}
        self.assertEqual(C.runs(3, blocks, False),
                         [(0,), (2,), (3, 4, 5), (6, 7, 8)])
        self.assertEqual(C.runs(3, blocks, True),
                         [(0, 3, 6), (4, 7), (2, 5, 8)])

    def test_a_run_of_one_or_two_makes_a_grid_ill_formed(self):
        self.assertFalse(C.well_formed(3, {1}))
        self.assertTrue(C.well_formed(3, set()))

    def test_nothing_is_ill_formed_at_any_rung(self):
        for rung in range(1, len(C.GRADES) + 1):
            grade = C.grade_of(rung)
            made = C.a_shape(grade.size, grade.longest_entry, random.Random(3))
            self.assertTrue(C.well_formed(grade.size, set(made)), rung)
            self.assertTrue(C.connected(grade.size, set(made)), rung)

    def test_a_split_leaves_a_legal_entry_on_both_sides(self):
        # A run of five cannot be split in the middle — that leaves a
        # two — but it can be shortened from either end. Leaving the
        # ends out was why nothing above the first rung dealt at all.
        self.assertEqual(C.split_points(5), (0, 4))
        self.assertEqual(C.split_points(7), (0, 6, 3))
        self.assertEqual(C.split_points(3), ())

    def test_the_ceiling_is_not_a_condition_of_being_well_formed(self):
        # It once was, and that stopped shape working on any grid
        # wider than the ceiling: every intermediate step was over it
        # and so every step was rolled back.
        self.assertTrue(C.well_formed(13, set()))

    def test_blocks_come_in_symmetric_pairs(self):
        made = C.a_shape(9, 5, random.Random(1))
        for cell in made:
            self.assertIn(9 * 9 - 1 - cell, made)


class AFilledGridIsWordsBothWays(unittest.TestCase):
    """The failure that does not look like one."""

    def setUp(self):
        self.pool = pocket()

    def test_every_run_of_a_filled_grid_is_a_word(self):
        rng = random.Random(5)
        letters = C.fill(7, LATTICE, self.pool, rng, C._Budget(200000))
        self.assertIsNotNone(letters)
        for down in (False, True):
            for run in C.runs(7, set(LATTICE), down):
                word = ''.join(letters[cell] for cell in run)
                self.assertTrue(self.pool.valid(word), word)

    def test_a_block_is_left_empty_rather_than_filled(self):
        letters = C.fill(7, LATTICE, self.pool, random.Random(5),
                         C._Budget(200000))
        self.assertIsNotNone(letters)
        for cell in LATTICE:
            self.assertEqual(letters[cell], '')

    def test_a_pool_that_cannot_fill_it_returns_nothing(self):
        thin = W.Lexicon([W.Entry('cat', 1, 'a pet')])
        made = C.fill(3, frozenset(), thin, random.Random(0),
                      C._Budget(5000))
        self.assertIsNone(made)

    def test_the_budget_is_what_stops_it_rather_than_a_clock(self):
        # A count and not a stopwatch, so the same seed deals the same
        # puzzle on a fast machine and a slow one.
        budget = C._Budget(40)
        made = C.fill(6, frozenset(), self.pool, random.Random(0), budget)
        self.assertIsNone(made)
        self.assertLessEqual(budget.left, 0)


class ADealtPuzzleSaysWhatItIs(unittest.TestCase):
    """Numbering, clues, givens, and the promises a rung makes."""

    def setUp(self):
        self.grade = C.Grade('small', 6, 4, 1 << 30, 0.0, 0.0, 400000)
        self.made = C.deal_one(self.grade, random.Random(4), pocket())
        self.assertIsNotNone(self.made)

    def test_the_numbering_runs_in_reading_order(self):
        numbers = [slot.number for slot in self.made.slots]
        self.assertEqual(numbers, sorted(numbers))
        self.assertEqual(min(numbers), 1)

    def test_an_entry_starting_two_ways_gets_one_number(self):
        starts = {}
        for slot in self.made.slots:
            starts.setdefault(slot.cells[0], set()).add(slot.number)
        for cell, seen in starts.items():
            self.assertEqual(len(seen), 1, cell)

    def test_every_slot_holds_the_word_the_grid_holds(self):
        for slot in self.made.slots:
            self.assertEqual(
                ''.join(self.made.solution[cell] for cell in slot.cells),
                slot.word)

    def test_every_cell_belongs_to_one_across_and_one_down(self):
        for cell, letter in enumerate(self.made.solution):
            if not letter:
                continue
            ways = [slot.down for slot in self.made.slots
                    if cell in slot.cells]
            self.assertEqual(sorted(ways), [False, True], cell)

    def test_a_clue_comes_from_the_pool_and_not_from_thin_air(self):
        pooled = pocket()
        for slot in self.made.slots:
            self.assertEqual(slot.clue, pooled.clue(slot.word))

    def test_withholding_takes_clues_away_and_nothing_else(self):
        quiet = self.grade._replace(withheld=0.5)
        made = C.deal_one(quiet, random.Random(4), pocket())
        self.assertIsNotNone(made)
        self.assertGreater(made.unclued(), 0)
        self.assertLess(made.unclued(), len(made.slots))
        for slot in made.slots:
            self.assertTrue(slot.word)

    def test_a_given_is_the_answer_and_is_counted_out_of_the_blanks(self):
        handed = self.grade._replace(given=0.5)
        made = C.deal_one(handed, random.Random(4), pocket())
        self.assertIsNotNone(made)
        self.assertTrue(made.givens)
        for cell in made.givens:
            self.assertTrue(made.solution[cell])
        self.assertEqual(made.blanks(),
                         sum(1 for one in made.solution if one)
                         - len(made.givens))


class TheLadderClimbs(unittest.TestCase):
    """What a rung promises, checked against what it deals."""

    def test_the_grids_never_shrink_in_what_they_ask_for(self):
        # Not by size, which goes down again for the word squares, but
        # by band: a later rung never draws from a narrower slice of
        # the language than an earlier one at the same size.
        by_size = {}
        for grade in C.GRADES:
            for size, top in by_size.items():
                if size == grade.size:
                    self.assertGreaterEqual(grade.top_rank, top)
            by_size[grade.size] = grade.top_rank

    def test_the_bottom_hands_letters_over_and_the_top_does_not(self):
        self.assertGreater(C.GRADES[0].given, 0.0)
        self.assertEqual(C.GRADES[-1].given, 0.0)

    def test_only_the_far_end_withholds_a_clue(self):
        for grade in C.GRADES[:5]:
            self.assertEqual(grade.withheld, 0.0, grade.name)
        self.assertGreater(C.GRADES[-1].withheld, 0.0)

    def test_a_rung_out_of_range_is_clamped_rather_than_thrown(self):
        self.assertIs(C.grade_of(0), C.GRADES[0])
        self.assertIs(C.grade_of(999), C.GRADES[-1])

    def test_a_five_by_five_cannot_be_brought_under_five(self):
        # Geometry rather than a choice: every row needs a block to
        # come under five, and so does every column, and there is no
        # way to do both without leaving a run of one or two. So a
        # five by five is a word square whatever is asked of it, and
        # the ladder uses it as one rather than pretending.
        for seed in range(8):
            for target in (3, 4):
                made = C.a_shape(5, target, random.Random(seed))
                self.assertEqual(C.longest(5, set(made)), 5)


@unittest.skipUnless(W.index_ready() and W.pool().clued,
                     'the word list has not been fetched')
class OnTheRealPool(unittest.TestCase):
    """Two things that can only be said with the words actually here."""

    def test_every_rung_deals(self):
        for rung in range(1, len(C.GRADES) + 1):
            made = C.generate(rung, seed=11)
            self.assertIsNotNone(made, rung)

    def test_a_dealt_grid_is_words_both_ways_at_the_top_rung(self):
        made = C.generate(len(C.GRADES), seed=12)
        self.assertIsNotNone(made)
        pooled = W.pool(C.GRADES[-1].top_rank)
        for slot in made.slots:
            self.assertTrue(pooled.valid(slot.word), slot.word)


@needs_ui
class TheCrosswordScreen(unittest.TestCase):
    """Moving, turning, writing, and what settles a trial."""

    def setUp(self):
        close_overlays()
        self.task = Crossword()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.show_mistakes = True
        self.task.start_rung = self.task.rung = 1
        self.stocked = self.task.stocked()

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def open_one(self):
        if not self.stocked:
            self.skipTest('the word list has not been fetched')
        self.task.start_run()
        self.assertEqual(self.task.phase, 'solving')

    def blank(self):
        return next(cell for cell, letter in enumerate(self.task.filled)
                    if self.task.puzzle.solution[cell] and not letter)

    def solve(self):
        for cell, letter in enumerate(self.task.puzzle.solution):
            if letter and cell not in self.task.puzzle.givens:
                self.task.at = cell
                self.task.write(letter)

    def test_it_is_in_the_reasoning_category(self):
        self.assertIn('crossword', [task for task, _n in TASKS['reasoning']])

    def test_with_no_clues_fetched_it_says_so_instead_of_dealing(self):
        if self.stocked:
            self.skipTest('the word list is here, so it deals')
        self.task.start_run()
        self.assertEqual(self.task.phase, 'ready')
        self.assertIn('wordlist', self.task.message)

    def test_a_trial_opens_on_a_blank(self):
        self.open_one()
        self.assertFalse(self.task.filled[self.task.at])
        self.task.on_draw()

    def test_the_cursor_steps_over_a_block(self):
        self.open_one()
        size = self.task.size()
        blocks = self.task.puzzle.blocks
        if not blocks:
            self.skipTest('this rung has no blocks in it')
        cell = min(blocks)
        row, col = divmod(cell, size)
        if col == 0:
            self.skipTest('nothing to the left of it')
        self.task.at = row * size + col - 1
        self.task.move(1, 0)
        self.assertNotIn(self.task.at, blocks)

    def test_turning_changes_the_clue_without_moving(self):
        self.open_one()
        was, saying = self.task.at, self.task.clue_line()
        self.task.turn()
        self.assertEqual(self.task.at, was)
        self.assertNotEqual(self.task.clue_line(), saying)

    def test_a_withheld_clue_is_said_to_be_withheld(self):
        self.task.start_rung = self.task.rung = len(C.GRADES)
        self.open_one()
        quiet = [slot for slot in self.task.puzzle.slots if not slot.clue]
        self.assertTrue(quiet)
        self.task.at = quiet[0].cells[0]
        self.task.down = quiet[0].down
        self.assertIn('no clue', self.task.clue_line())

    def test_a_letter_is_written_where_the_cursor_is(self):
        self.open_one()
        cell = self.blank()
        self.task.at = cell
        self.task.write('q')
        self.assertEqual(self.task.filled[cell], 'q')

    def test_a_given_refuses_the_key(self):
        self.open_one()
        if not self.task.puzzle.givens:
            self.skipTest('this rung gives nothing away')
        cell = min(self.task.puzzle.givens)
        self.task.at = cell
        was = self.task.filled[cell]
        self.task.write('q')
        self.assertEqual(self.task.filled[cell], was)

    def test_a_wrong_letter_is_counted_and_marked(self):
        self.open_one()
        cell = self.blank()
        wrong = next(one for one in 'abcdefghij'
                     if one != self.task.puzzle.solution[cell])
        self.task.at = cell
        self.task.write(wrong)
        self.assertEqual(self.task.mistakes, 1)
        self.assertIn(cell, self.task.wrong())

    def test_a_clean_solve_is_green(self):
        self.open_one()
        self.solve()
        self.assertEqual(self.task.phase, 'solved')
        self.assertTrue(self.task.verdict_shown[0])

    def test_a_solve_with_a_slip_in_it_is_red(self):
        self.open_one()
        cell = self.blank()
        self.task.at = cell
        self.task.write(next(one for one in 'abcdefghij'
                             if one != self.task.puzzle.solution[cell]))
        self.solve()
        self.assertEqual(self.task.phase, 'solved')
        self.assertFalse(self.task.verdict_shown[0])

    def test_the_verdict_is_down_again_when_the_next_trial_opens(self):
        self.open_one()
        self.solve()
        self.task._next_trial()
        self.assertIsNone(self.task.verdict_shown)

    def test_a_relayout_puts_a_shown_verdict_back(self):
        self.open_one()
        self.solve()
        self.task.relayout()
        self.assertTrue(self.task.verdict.label.text)

    def test_the_grid_clears_the_verdict_band(self):
        self.open_one()
        _left, bottom, _side = self.task._board()
        self.assertGreaterEqual(bottom, above_the_band(0.0) - 1.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
