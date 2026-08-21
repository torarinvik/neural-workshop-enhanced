#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sudoku: the techniques, the rating, and what each rung promises.

The rating is what the whole ladder rests on, so it is what is tested
hardest. Each technique gets a grid built to need it and nothing
cheaper, because a tier only means something if the technique it names
is really the deepest one the puzzle forces -- and a stack whose
middle is quietly dead would still produce a tidy-looking ladder, with
every rung landing on the tiers either side of the hole.

The generator's promises are checked on every rung: one solution
exactly, a stored solution the solver agrees with, and a tier inside
the band -- or, when the band was missed, above it rather than below.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from neural_workshop import sudoku as S

#: Rungs cheap enough to deal several of. The sixteens cost about a
#: second and a half apiece, so they are visited once and by name.
SMALL_RUNGS = (1, 2, 3, 4, 5)


def picture(rows):
    """A grid written out, ``.`` for a blank and A-G for 10-16."""
    flat = ''.join(rows.split())
    out = []
    for mark in flat:
        if mark == '.':
            out.append(0)
        elif mark.isdigit():
            out.append(int(mark))
        else:
            out.append(ord(mark.upper()) - ord('A') + 10)
    return tuple(out)


class ShapeTests(unittest.TestCase):
    """Rows, columns, boxes and who sees whom."""

    def test_a_nine_has_twenty_seven_units(self):
        self.assertEqual(len(S.units(3)), 27)

    def test_a_sixteen_has_forty_eight(self):
        self.assertEqual(len(S.units(4)), 48)

    def test_every_unit_holds_a_full_line_of_cells(self):
        for box in S.BOXES:
            for unit in S.units(box):
                self.assertEqual(len(unit), box * box)
                self.assertEqual(len(set(unit)), box * box)

    def test_every_cell_is_in_exactly_three_units(self):
        for box in S.BOXES:
            for cell in range(box ** 4):
                self.assertEqual(len(S.units_of(box)[cell]), 3)

    def test_a_cell_does_not_see_itself(self):
        for box in S.BOXES:
            for cell, group in enumerate(S.peers(box)):
                self.assertNotIn(cell, group)

    def test_a_nine_sees_twenty_peers(self):
        self.assertEqual(len(S.peers(3)[0]), 20)

    def test_the_top_left_box_is_the_corner(self):
        self.assertEqual(S.units(3)[18], (0, 1, 2, 9, 10, 11, 18, 19, 20))

    def test_units_are_cached_not_rebuilt(self):
        self.assertIs(S.units(3), S.units(3))
        self.assertIs(S.peers(3), S.peers(3))


class CandidateTests(unittest.TestCase):
    """What is still allowed where."""

    def test_a_blank_grid_allows_everything(self):
        cand = S.candidates([0] * 16, 2)
        self.assertEqual(cand[0], 0b1111)

    def test_a_given_narrows_its_peers(self):
        grid = [0] * 16
        grid[0] = 1
        cand = S.candidates(grid, 2)
        self.assertEqual(cand[0], 0b0001)
        self.assertEqual(cand[1], 0b1110)          # same row
        self.assertEqual(cand[4], 0b1110)          # same column
        self.assertEqual(cand[5], 0b1110)          # same box
        self.assertEqual(cand[10], 0b1111)         # sees none of it

    def test_a_repeated_digit_is_no_grid_at_all(self):
        grid = [0] * 16
        grid[0] = grid[1] = 1
        self.assertIsNone(S.candidates(grid, 2))

    def test_a_cell_with_nothing_left_is_no_grid_at_all(self):
        grid = picture('1234'
                       '34..'
                       '....'
                       '....')
        grid = list(grid)
        grid[6] = 0
        # row 1 already holds 3 and 4; column 2 will hold 1 and 2
        grid[10], grid[14] = 1, 2
        self.assertIsNone(S.candidates(grid, 2))

    def test_bits_reads_a_mask_back(self):
        self.assertEqual(S._bits(0b1011), [1, 2, 4])
        self.assertEqual(S._bits(0), [])


class TechniqueTests(unittest.TestCase):
    """Each technique on a grid that needs it and nothing cheaper.

    The tier is the deepest technique *forced*, so a puzzle testing
    tier n must be unsolvable by tiers below n -- which is what the
    rating check on each one is really asserting.
    """

    def _fires(self, technique, grid, box):
        cand = S.candidates(grid, box)
        self.assertIsNotNone(cand, 'the test grid contradicts itself')
        return technique(list(grid), cand, box)

    def test_a_naked_single_is_seen(self):
        grid = picture('123.'
                       '....'
                       '....'
                       '....')
        self.assertTrue(self._fires(S._naked_single, grid, 2))

    def test_a_naked_single_is_not_seen_where_there_is_none(self):
        self.assertFalse(self._fires(S._naked_single, (0,) * 16, 2))

    def test_a_hidden_single_is_seen(self):
        # 4 is barred from three cells of the top row by its column,
        # so it has exactly one home there without any cell being down
        # to one candidate.
        grid = picture('....'
                       '4...'
                       '.4..'
                       '..4.')
        self.assertTrue(self._fires(S._hidden_single, grid, 2))

    #: A seed whose deal is decided by each technique in turn. Found by
    #: sweeping, and pinned rather than re-sampled: fish decide one
    #: nine-by-nine in five hundred, so a test that went looking would
    #: have to deal thousands to be sure of finding one -- and would
    #: still pass by luck on the day the technique broke.
    TIER_SEEDS = {0: 176, 1: 2, 2: 1, 3: 3, 4: 30, 5: 740, 6: 0}

    def _deal_at(self, seed):
        full = S._full_grid(3, random.Random(seed))
        return S._dig(full, 3, random.Random(seed + 77))

    def test_every_technique_can_be_the_deepest_one_needed(self):
        """A dead technique would leave a hole the ladder cannot see."""
        for tier, seed in sorted(self.TIER_SEEDS.items()):
            got = S.rate(self._deal_at(seed), 3)[0]
            self.assertEqual(got, tier,
                             'seed %d should be decided by %s, got %s'
                             % (seed, S.TECHNIQUES[tier], S.TECHNIQUES[got]))

    def test_the_tiers_are_not_all_the_same_puzzle(self):
        deals = {tier: tuple(self._deal_at(seed))
                 for tier, seed in self.TIER_SEEDS.items()}
        self.assertEqual(len(set(deals.values())), len(deals))

    def test_a_technique_reports_a_contradiction_apart_from_nothing(self):
        """None and False are opposite answers, not the same one."""
        grid = list(picture('1...'
                            '....'
                            '....'
                            '....'))
        cand = S.candidates(grid, 2)
        self.assertFalse(S._naked_single(list(grid), list(cand), 2))
        starved = list(cand)
        starved[5] = 0
        self.assertIsNone(S._naked_single(list(grid), starved, 2))


class SolveTests(unittest.TestCase):
    """Finding solutions, and proving there is only the one."""

    EASY = ('53..7....' '6..195...' '.98....6.'
            '8...6...3' '4..8.3..1' '7...2...6'
            '.6....28.' '...419..5' '....8..79')
    HARD = ('8........' '..36.....' '.7..9.2..'
            '.5...7...' '....457..' '...1...3.'
            '..1....68' '..85...1.' '.9....4..')

    def test_a_known_puzzle_has_one_solution(self):
        self.assertEqual(len(S.solutions(picture(self.EASY), 3, 2)), 1)

    def test_the_solution_is_a_legal_grid(self):
        found = S.solutions(picture(self.EASY), 3, 1)[0]
        for unit in S.units(3):
            self.assertEqual(sorted(found[c] for c in unit),
                             list(range(1, 10)))

    def test_the_solution_keeps_every_given(self):
        given = picture(self.EASY)
        found = S.solutions(given, 3, 1)[0]
        for cell, value in enumerate(given):
            if value:
                self.assertEqual(found[cell], value)

    def test_an_empty_grid_has_many_solutions(self):
        self.assertEqual(len(S.solutions([0] * 16, 2, 2)), 2)

    def test_a_contradictory_grid_has_none(self):
        grid = [0] * 16
        grid[0] = grid[1] = 1
        self.assertEqual(S.solutions(grid, 2, 2), [])

    def test_an_easy_puzzle_needs_only_singles(self):
        self.assertEqual(S.rate(picture(self.EASY), 3), (0, 0))

    def test_a_notorious_puzzle_runs_the_stack_out(self):
        tier, guesses = S.rate(picture(self.HARD), 3)
        self.assertEqual(tier, S.SEARCH_TIER)
        self.assertGreater(guesses, 0)

    def test_rating_the_same_grid_twice_gives_the_same_answer(self):
        for _twice in range(3):
            self.assertEqual(S.rate(picture(self.HARD), 3),
                             S.rate(picture(self.HARD), 3))

    def test_a_finished_grid_needs_nothing(self):
        full = S._full_grid(2, random.Random(1))
        self.assertEqual(S.rate(full, 2), (0, 0))


class FullGridTests(unittest.TestCase):
    """Filling a grid from nothing, bounded."""

    def test_a_full_grid_is_legal(self):
        for box in S.BOXES:
            full = S._full_grid(box, random.Random(box))
            for unit in S.units(box):
                self.assertEqual(sorted(full[c] for c in unit),
                                 list(range(1, box * box + 1)))

    def test_a_full_grid_has_no_blanks(self):
        full = S._full_grid(3, random.Random(2))
        self.assertNotIn(0, full)

    def test_filling_is_bounded_on_a_sixteen(self):
        """A blind backtracker takes minutes on the unlucky seed."""
        for seed in range(12):
            full = S._full_grid(4, random.Random(seed))
            self.assertEqual(len(full), 256)

    def test_different_seeds_fill_differently(self):
        self.assertNotEqual(S._full_grid(3, random.Random(1)),
                            S._full_grid(3, random.Random(2)))


class DigTests(unittest.TestCase):
    """Taking cells out while the answer stays the only one."""

    def test_digging_leaves_exactly_one_solution(self):
        rng = random.Random(7)
        for _deal in range(6):
            full = S._full_grid(3, rng)
            givens = S._dig(full, 3, rng)
            self.assertEqual(len(S.solutions(givens, 3, 2)), 1)

    def test_digging_keeps_the_solution_it_started_from(self):
        rng = random.Random(8)
        full = S._full_grid(3, rng)
        givens = S._dig(full, 3, rng)
        self.assertEqual(S.solutions(givens, 3, 1)[0], tuple(full))

    def test_keeping_cells_stops_early(self):
        rng = random.Random(9)
        full = S._full_grid(3, rng)
        givens = S._dig(full, 3, rng, keep=50)
        self.assertEqual(sum(1 for v in givens if v), 50)

    def test_digging_to_minimal_leaves_far_fewer(self):
        rng = random.Random(10)
        full = S._full_grid(3, rng)
        givens = S._dig(full, 3, rng)
        self.assertLess(sum(1 for v in givens if v), 40)

    def test_a_cell_that_would_open_a_second_answer_goes_back(self):
        full = list(S._full_grid(2, random.Random(4)))
        # A 4x4 dug to nothing has many solutions, so digging must stop
        # well short of empty.
        givens = S._dig(full, 2, random.Random(4))
        self.assertGreater(sum(1 for v in givens if v), 0)
        self.assertEqual(len(S.solutions(givens, 2, 2)), 1)


class LadderTests(unittest.TestCase):
    """The rungs themselves, before anything is dealt."""

    def test_the_ladder_climbs(self):
        for lower, upper in zip(S.GRADES, S.GRADES[1:]):
            self.assertGreaterEqual(
                (upper.box, upper.floor, upper.guesses),
                (lower.box, lower.floor, lower.guesses), upper.name)

    def test_every_band_is_the_right_way_round(self):
        for grade in S.GRADES:
            self.assertLessEqual(grade.floor, grade.ceiling, grade.name)
            self.assertGreaterEqual(grade.floor, 0, grade.name)
            self.assertLessEqual(grade.ceiling, S.SEARCH_TIER, grade.name)

    def test_only_the_search_tier_may_ask_for_guesses(self):
        for grade in S.GRADES:
            if grade.guesses:
                self.assertEqual(grade.floor, S.SEARCH_TIER, grade.name)

    def test_every_box_size_is_one_the_palette_can_carry(self):
        for grade in S.GRADES:
            self.assertIn(grade.box, S.BOXES, grade.name)

    def test_keeping_more_cells_than_there_are_is_not_asked_for(self):
        for grade in S.GRADES:
            self.assertLess(grade.keep, grade.box ** 4, grade.name)

    def test_every_rung_is_given_something_to_spend(self):
        for grade in S.GRADES:
            self.assertGreater(grade.tries, 0, grade.name)

    def test_the_names_are_all_different(self):
        names = [grade.name for grade in S.GRADES]
        self.assertEqual(len(names), len(set(names)))

    def test_the_ladder_starts_easy_and_ends_superhuman(self):
        self.assertEqual(S.GRADES[0].box, 2)
        self.assertEqual(S.GRADES[0].floor, 0)
        self.assertEqual(S.GRADES[-1].box, 4)
        self.assertEqual(S.GRADES[-1].floor, S.SEARCH_TIER)


class MissTests(unittest.TestCase):
    """Which near miss a rung would rather have."""

    def _puzzle(self, tier, guesses=0, box=3):
        return S.Puzzle(box=box, givens=(), solution=(), tier=tier,
                        guesses=guesses)

    def test_landing_in_the_band_is_no_miss_at_all(self):
        grade = S.Grade('x', 3, 2, 3)
        self.assertEqual(S._miss(self._puzzle(2), grade), (0, 0))
        self.assertEqual(S._miss(self._puzzle(3), grade), (0, 0))

    def test_too_hard_beats_too_easy_by_the_same_distance(self):
        grade = S.Grade('x', 3, 4, 5)
        harder = S._miss(self._puzzle(6), grade)
        easier = S._miss(self._puzzle(3), grade)
        self.assertLess(harder, easier)

    def test_a_shortfall_in_guesses_only_breaks_a_tie_on_depth(self):
        grade = S.Grade('x', 3, 6, 6, 10)
        deep = S._miss(self._puzzle(6, guesses=1), grade)
        shallow = S._miss(self._puzzle(5, guesses=99), grade)
        self.assertLess(deep, shallow)


class GenerateTests(unittest.TestCase):
    """What every dealt puzzle promises."""

    def test_the_same_seed_deals_the_same_puzzle(self):
        self.assertEqual(S.generate(4, seed=21), S.generate(4, seed=21))

    def test_another_seed_deals_another_puzzle(self):
        self.assertNotEqual(S.generate(4, seed=21), S.generate(4, seed=22))

    def test_a_level_past_the_ladder_is_the_last_rung(self):
        got = S.generate(len(S.GRADES) + 30, seed=2)
        self.assertEqual(got.box, S.GRADES[-1].box)

    def test_a_level_below_the_ladder_is_the_first_rung(self):
        self.assertEqual(S.generate(0, seed=2).box, S.GRADES[0].box)

    def test_every_rung_deals_a_puzzle_of_its_own_size(self):
        for rung in range(1, len(S.GRADES) + 1):
            grade = S.GRADES[rung - 1]
            got = S.generate(rung, seed=400 + rung)
            self.assertEqual(got.box, grade.box, grade.name)
            self.assertEqual(len(got.givens), grade.box ** 4, grade.name)

    def test_every_dealt_puzzle_has_exactly_one_solution(self):
        for rung in SMALL_RUNGS + (7,):
            got = S.generate(rung, seed=700 + rung)
            self.assertEqual(len(S.solutions(got.givens, got.box, 2)), 1,
                             S.GRADES[rung - 1].name)

    def test_the_stored_solution_is_the_one_the_solver_finds(self):
        for rung in SMALL_RUNGS:
            got = S.generate(rung, seed=800 + rung)
            self.assertEqual(S.solutions(got.givens, got.box, 1)[0],
                             got.solution)

    def test_every_given_agrees_with_the_solution(self):
        for rung in SMALL_RUNGS:
            got = S.generate(rung, seed=900 + rung)
            for cell, value in enumerate(got.givens):
                if value:
                    self.assertEqual(got.solution[cell], value)

    def test_the_stored_rating_is_the_one_the_rater_gives(self):
        for rung in SMALL_RUNGS:
            got = S.generate(rung, seed=1000 + rung)
            self.assertEqual(S.rate(got.givens, got.box),
                             (got.tier, got.guesses))

    def test_the_nine_rungs_land_in_their_bands(self):
        for rung in (2, 3, 4, 5, 7, 8):
            grade = S.GRADES[rung - 1]
            got = S.generate(rung, seed=1100 + rung)
            self.assertGreaterEqual(got.tier, grade.floor, grade.name)
            self.assertGreaterEqual(got.guesses, grade.guesses, grade.name)

    def test_a_rung_that_misses_its_band_lands_above_it_never_below(self):
        """The direction a fallback falls, on the rung that falls."""
        grade = S.GRADES[5]                       # 'hard', tiers 4-5
        for trial in range(8):
            got = S.generate(6, seed=1300 + trial)
            self.assertGreaterEqual(got.tier, grade.floor,
                                    'dealt tier %d below the band'
                                    % got.tier)

    def test_a_gentle_rung_really_is_gentle(self):
        for trial in range(4):
            got = S.generate(2, seed=1500 + trial)
            self.assertEqual(got.tier, 0)

    def test_blanks_counts_what_is_left_to_do(self):
        got = S.generate(3, seed=6)
        self.assertEqual(got.blanks(),
                         sum(1 for v in got.givens if not v))
        self.assertEqual(got.size, got.box * got.box)

    def test_one_try_still_deals_a_legal_puzzle(self):
        got = S.generate(5, seed=9, attempts=1)
        self.assertEqual(len(S.solutions(got.givens, got.box, 2)), 1)

    def test_a_sixteen_is_dealt_and_is_a_sixteen(self):
        got = S.generate(9, seed=11)
        self.assertEqual(got.box, 4)
        self.assertEqual(got.size, 16)
        self.assertEqual(len(got.givens), 256)
        self.assertEqual(len(S.solutions(got.givens, 4, 2)), 1)

    def test_the_superhuman_rung_runs_the_stack_out(self):
        got = S.generate(len(S.GRADES), seed=13)
        self.assertEqual(got.tier, S.SEARCH_TIER)
        self.assertGreater(got.guesses, 1)


if __name__ == '__main__':
    unittest.main()
