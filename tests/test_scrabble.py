#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Scrabble: the scoring, the rules, and the claim that the best is the best.

The whole task rests on one number — the best play that existed on
that board — and a solver that quietly missed a play would flatter
every player by an unknown amount and never say so. So the middle of
this file is a brute force: every ordered subset of the rack into every
run of squares, scored the long way, compared with what the solver
found. It is far too slow to be the real solver and that is what makes
it worth having.

The rest is the scoring rules, which are the game's and not ours and
are the sort of thing that is wrong for years without anybody noticing:
a premium under a tile that was already there does not pay again, and a
word premium multiplies the crossing word too.

Nothing here needs the word list to have been fetched. Two tests at
the end do, and they say so.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('NW_HEADLESS', '1')

from uisupport import (Scrabble, TASKS, close_overlays,        # noqa: E402
                       geometry, needs_ui, reset_window, state)
from pyglet.window import mouse                                # noqa: E402

from neural_workshop import scrabble as S                     # noqa: E402
from neural_workshop import wordlist as W                     # noqa: E402
from neural_workshop.ui.verdict import above_the_band         # noqa: E402


def pocket() -> W.Lexicon:
    """A pool that owes nothing to whether anything has been fetched."""
    return W.Lexicon(W.Entry(one.word, one.rank, '') for one in W.SEED)


def bare(size: int, premiums: str = '') -> S.Board:
    """An empty board with every square plain, so a score is only tiles."""
    return S.Board(size, tuple([''] * (size * size)),
                   tuple([premiums] * (size * size)))


def laid_out(board: S.Board, row: int, col: int, word: str,
             down: bool = False):
    """*word* as a play starting at (row, col)."""
    step = board.size if down else 1
    at = row * board.size + col
    return [(at + position * step, letter)
            for position, letter in enumerate(word)]


class TheScoringIsTheGameS(unittest.TestCase):
    """Rules that are wrong for years without anybody noticing."""

    def test_a_plain_word_is_the_sum_of_its_letters(self):
        board = bare(7)
        score, words = S.score_play(board, laid_out(board, 3, 1, 'cat'), False)
        self.assertEqual(words, ('cat',))
        self.assertEqual(score, 3 + 1 + 1)

    def test_a_letter_premium_pays_for_that_letter_only(self):
        board = bare(7)
        board = board._replace(premiums=tuple(
            'TL' if cell == 3 * 7 + 1 else '' for cell in range(49)))
        score, _words = S.score_play(board, laid_out(board, 3, 1, 'cat'),
                                     False)
        self.assertEqual(score, 3 * 3 + 1 + 1)

    def test_a_word_premium_multiplies_the_whole_word(self):
        board = bare(7)
        board = board._replace(premiums=tuple(
            'DW' if cell == 3 * 7 + 2 else '' for cell in range(49)))
        score, _words = S.score_play(board, laid_out(board, 3, 1, 'cat'),
                                     False)
        self.assertEqual(score, (3 + 1 + 1) * 2)

    def test_a_premium_under_a_tile_already_there_is_spent(self):
        board = bare(7)
        board = board._replace(premiums=tuple(
            'TW' if cell == 3 * 7 + 1 else '' for cell in range(49)))
        board = S.written(board, [(3 * 7 + 1, 'c')])
        score, _words = S.score_play(board, [(3 * 7 + 2, 'a'),
                                             (3 * 7 + 3, 't')], False)
        self.assertEqual(score, 3 + 1 + 1)

    def test_a_crossing_word_is_scored_too(self):
        board = bare(9)
        board = S.written(board, laid_out(board, 4, 2, 'cat'))
        # 'o' under the 'c' makes 'co' down as well as whatever across.
        score, words = S.score_play(board, [(5 * 9 + 2, 'o'),
                                            (5 * 9 + 3, 'x')], False)
        self.assertEqual(sorted(words), ['ax', 'co', 'ox'])
        self.assertEqual(score, (1 + 8) + (3 + 1) + (1 + 8))

    def test_a_word_premium_multiplies_the_crossing_word_as_well(self):
        board = bare(9)
        board = board._replace(premiums=tuple(
            'DW' if cell == 5 * 9 + 2 else '' for cell in range(81)))
        board = S.written(board, laid_out(board, 4, 2, 'cat'))
        score, _words = S.score_play(board, [(5 * 9 + 2, 'o'),
                                             (5 * 9 + 3, 'x')], False)
        # The double word is under the 'o', so it doubles 'ox' and the
        # 'co' the 'o' also makes — and leaves 'ax' alone, because the
        # premium is not in it. That last part is the half people miss.
        self.assertEqual(score, (1 + 8) * 2 + (3 + 1) * 2 + (1 + 8))

    def test_laying_the_whole_rack_pays_the_bingo(self):
        board = bare(11)
        plain, _w = S.score_play(board, laid_out(board, 5, 1, 'cat'), False)
        seven, _w = S.score_play(board, laid_out(board, 5, 1, 'cattery'),
                                 False)
        self.assertEqual(plain, 5)
        self.assertEqual(seven - sum(S.VALUES[one] for one in 'cattery'),
                         S.BINGO)


class TheRulesAboutWhereTilesMayGo(unittest.TestCase):
    """What a legal play is, which is what the screen refuses on."""

    def setUp(self):
        self.words = pocket()
        # 'its' across the middle, so a play can hook down through the
        # 't' and make 'its' again the other way.
        self.board = S.written(bare(9), laid_out(bare(9), 4, 3, 'its'))

    def test_a_word_the_pool_does_not_hold_is_not_a_play(self):
        self.assertFalse(S.legal(self.board, laid_out(self.board, 5, 3, 'zzz'),
                                 False, self.words))

    def test_a_play_floating_free_of_the_board_is_not_a_play(self):
        self.assertFalse(S.legal(self.board, laid_out(self.board, 0, 0, 'cat'),
                                 False, self.words))

    def test_a_play_hooking_onto_what_is_there_is(self):
        # 'i' above and 's' below the 't' of 'its', making 'its' down.
        self.assertTrue(S.legal(self.board, [(3 * 9 + 4, 'i'),
                                             (5 * 9 + 4, 's')], True,
                                self.words))

    def test_a_play_over_a_square_already_taken_is_not(self):
        self.assertFalse(S.legal(self.board, [(4 * 9 + 3, 'a')], False,
                                 self.words))

    def test_a_play_leaving_a_gap_in_its_own_word_is_not(self):
        self.assertFalse(S.legal(self.board, [(6 * 9 + 3, 'i'),
                                              (6 * 9 + 5, 's')], False,
                                 self.words))

    def test_a_play_in_two_lines_at_once_is_not(self):
        self.assertFalse(S.legal(self.board, [(4 * 9 + 2, 'a'),
                                              (5 * 9 + 4, 'b')], False,
                                 self.words))

    def test_a_play_that_makes_a_crossing_non_word_is_not(self):
        # 'is' laid above 'its' is a word across and makes 'ii' and
        # 'st' down, which are not, so the play is refused.
        self.assertFalse(S.legal(self.board, [(3 * 9 + 3, 'i'),
                                              (3 * 9 + 4, 's')], False,
                                 self.words))

    def test_nothing_laid_is_not_a_play(self):
        self.assertFalse(S.legal(self.board, [], False, self.words))


class TheBestPlayReallyIsTheBest(unittest.TestCase):
    """Checked the long way, which is the only way to know."""

    def brute(self, board, rack, words):
        """Every ordered subset of the rack into every run of squares."""
        size = board.size
        best = 0
        for down in (False, True):
            step = size if down else 1
            for start in range(size * size):
                for span in range(2, size + 1):
                    cells = [start + at * step for at in range(span)]
                    if any(not 0 <= cell < size * size for cell in cells):
                        continue
                    if not down and any(cell // size != start // size
                                        for cell in cells):
                        continue
                    empties = [cell for cell in cells if board.empty(cell)]
                    if not empties or len(empties) > len(rack):
                        continue
                    for pick in itertools.permutations(rack, len(empties)):
                        laid = list(zip(empties, pick))
                        if not S.legal(board, laid, down, words):
                            continue
                        score, _made = S.score_play(board, laid, down)
                        best = max(best, score)
        return best

    def test_the_solver_agrees_with_brute_force(self):
        words = pocket()
        grade = S.GRADES[0]._replace(size=7, rack=4, seeded=2)
        for seed in range(12):
            rng = random.Random(seed)
            board = S._seed_board(grade, words, rng)
            rack = S.draw(rng, 4)
            found = S.best_play(board, rack, words)
            self.assertEqual(found.score if found else 0,
                             self.brute(board, rack, words), seed)

    def test_it_agrees_on_a_fuller_rack_too(self):
        words = pocket()
        grade = S.GRADES[0]._replace(size=7, rack=5, seeded=3)
        for seed in range(5):
            rng = random.Random(seed)
            board = S._seed_board(grade, words, rng)
            rack = S.draw(rng, 5)
            found = S.best_play(board, rack, words)
            self.assertEqual(found.score if found else 0,
                             self.brute(board, rack, words), seed)

    def test_every_play_it_offers_is_legal(self):
        words = pocket()
        grade = S.GRADES[0]._replace(size=9, rack=5, seeded=2)
        rng = random.Random(3)
        board = S._seed_board(grade, words, rng)
        rack = S.draw(rng, 5)
        found = S.plays(board, rack, words)
        self.assertTrue(found)
        for play in found:
            self.assertTrue(S.legal(board, list(play.laid), play.down, words),
                            play.word)

    def test_no_play_is_offered_twice(self):
        words = pocket()
        grade = S.GRADES[0]._replace(size=9, rack=5, seeded=2)
        rng = random.Random(3)
        board = S._seed_board(grade, words, rng)
        found = S.plays(board, S.draw(rng, 5), words)
        keys = [(one.down, tuple(sorted(one.laid))) for one in found]
        self.assertEqual(len(set(keys)), len(keys))

    def test_a_play_uses_only_the_tiles_in_the_rack(self):
        words = pocket()
        rng = random.Random(8)
        board = S._seed_board(S.GRADES[2], words, rng)
        rack = S.draw(rng, 7)
        for play in S.plays(board, rack, words):
            left = list(rack)
            for _cell, letter in play.laid:
                self.assertIn(letter, left, play.word)
                left.remove(letter)


class ABoardIsABoard(unittest.TestCase):
    """The premium layout, and the position a rung deals."""

    def test_the_premiums_are_symmetric_eight_ways(self):
        for size in (7, 9, 11, 13, 15):
            found = S.premiums(size)
            for row in range(size):
                for col in range(size):
                    here = found[row * size + col]
                    for other in ((row, size - 1 - col),
                                  (size - 1 - row, col),
                                  (col, row)):
                        self.assertEqual(found[other[0] * size + other[1]],
                                         here, (size, row, col))

    def test_the_middle_is_a_double_word(self):
        for size in (7, 9, 15):
            self.assertEqual(S.premiums(size)[size // 2 * size + size // 2],
                             S.DOUBLE_WORD)

    def test_the_corners_are_triple_words(self):
        found = S.premiums(15)
        for cell in (0, 14, 14 * 15, 15 * 15 - 1):
            self.assertEqual(found[cell], S.TRIPLE_WORD)

    def test_a_seeded_board_has_the_words_the_rung_asked_for(self):
        words = pocket()
        for seeded in (1, 2, 3, 4):
            grade = S.GRADES[4]._replace(seeded=seeded)
            board = S._seed_board(grade, words, random.Random(2))
            found = set()
            for down in (False, True):
                for cell in range(board.size * board.size):
                    if board.empty(cell):
                        continue
                    word, cells = S._run(board, cell, down, {})
                    if len(word) > 1:
                        found.add((word, cells))
            for word, _cells in found:
                self.assertTrue(words.valid(word), word)
            self.assertGreaterEqual(len(found), seeded)

    def test_the_bag_is_the_real_one(self):
        self.assertEqual(sum(S.BAG.values()), 98)   # 100 less two blanks
        self.assertEqual(S.BAG['e'], 12)
        self.assertEqual(S.VALUES['q'], 10)
        self.assertEqual(set(S.BAG), set(S.VALUES))

    def test_a_rack_is_drawn_from_the_bag_and_not_the_alphabet(self):
        vowels = 0
        for seed in range(60):
            vowels += sum(1 for one in S.draw(random.Random(seed), 7)
                          if one in 'aeiou')
        # Uniform over the alphabet would give about a fifth vowels;
        # the bag is nearer two fifths, and a rack of consonants is
        # not the game.
        self.assertGreater(vowels / (60 * 7.0), 0.3)


class TheLadderClimbs(unittest.TestCase):
    """What a rung promises, checked against the table."""

    def test_the_share_needed_never_falls(self):
        shares = [grade.share for grade in S.GRADES]
        self.assertEqual(shares, sorted(shares))

    def test_the_band_never_narrows(self):
        tops = [grade.top_rank for grade in S.GRADES]
        self.assertEqual(tops, sorted(tops))

    def test_the_top_rung_pays_for_the_best_play_and_nothing_else(self):
        self.assertEqual(S.GRADES[-1].share, 1.0)

    def test_a_full_rack_from_the_third_rung_on(self):
        for grade in S.GRADES[2:]:
            self.assertEqual(grade.rack, S.RACK, grade.name)

    def test_a_rung_out_of_range_is_clamped_rather_than_thrown(self):
        self.assertIs(S.grade_of(0), S.GRADES[0])
        self.assertIs(S.grade_of(999), S.GRADES[-1])


@unittest.skipUnless(W.index_ready() and len(W.pool()) > 10000,
                     'the word list has not been fetched')
class OnTheRealPool(unittest.TestCase):
    """Two things that can only be said with the words actually here."""

    def test_every_rung_deals_a_position_with_a_play_in_it(self):
        for rung in range(1, len(S.GRADES) + 1):
            made = S.generate(rung, seed=21)
            self.assertIsNotNone(made, rung)
            self.assertGreater(made.ceiling, 0, rung)

    def test_the_best_play_gets_harder_to_reach_up_the_ladder(self):
        # A player who knows only the everyday band and always finds
        # the best play among them. Measured over the whole ladder in
        # tests/bench_words.py; here it is only asserted at the two
        # ends, where the gap is far wider than the noise.
        everyday = W.pool(3000)

        def share(rung, seeds):
            got = []
            for seed in seeds:
                made = S.generate(rung, seed=seed)
                if made is None:
                    continue
                narrow = everyday.narrowed(
                    hi=3000, lengths=tuple(range(2, made.board.size + 1)))
                mine = S.best_play(made.board, made.rack, narrow)
                got.append((mine.score if mine else 0) / made.ceiling)
            return sum(got) / len(got)

        self.assertGreater(share(1, range(40, 52)),
                           share(len(S.GRADES), range(40, 52)) + 0.2)


@needs_ui
class TheScrabbleScreen(unittest.TestCase):
    """Laying tiles, refusing nonsense, and what settles a trial."""

    def setUp(self):
        close_overlays()
        self.task = Scrabble()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.start_rung = self.task.rung = 3

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def open_one(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'playing')

    def play_the_best(self):
        """Lay the best play the way a person would, tile by tile."""
        best = self.task.deal.best
        for cell, letter in best.laid:
            slot = next(at for at, held in enumerate(self.task.deal.rack)
                        if held == letter and at not in self.task.spent)
            self.task.at = cell
            self.task.lay(slot)
        self.task.down = best.down
        self.task.submit()

    def test_it_is_in_the_reasoning_category(self):
        self.assertIn('scrabble', [task for task, _n in TASKS['reasoning']])

    def test_a_trial_deals_a_rack_and_a_board_with_words_on_it(self):
        self.open_one()
        self.assertEqual(len(self.task.deal.rack),
                         S.grade_of(self.task.rung).rack)
        self.assertTrue(self.task.deal.board.filled())
        self.assertGreater(self.task.deal.ceiling, 0)
        self.task.on_draw()

    def test_a_tile_goes_where_the_cursor_is_and_the_cursor_steps_on(self):
        self.open_one()
        cell = next(one for one in range(self.task.size() ** 2)
                    if self.task.deal.board.empty(one)
                    and one % self.task.size() < self.task.size() - 1)
        self.task.at = cell
        self.task.down = False
        self.task.lay(0)
        self.assertEqual(self.task.laid, [(cell, self.task.deal.rack[0])])
        self.assertEqual(self.task.at, cell + 1)

    def test_a_tile_is_played_once(self):
        self.open_one()
        self.task.lay(0)
        was = list(self.task.laid)
        self.task.lay(0)
        self.assertEqual(self.task.laid, was)

    def test_a_square_already_taken_refuses_the_tile(self):
        self.open_one()
        self.task.at = next(one for one in range(self.task.size() ** 2)
                            if not self.task.deal.board.empty(one))
        self.task.lay(0)
        self.assertEqual(self.task.laid, [])

    def test_a_trial_opens_the_cursor_on_a_free_square(self):
        # The middle square holds the first seeded word, so opening
        # there meant the first tile laid was refused, which reads as
        # the keyboard not working.
        self.open_one()
        self.assertTrue(self.task.deal.board.empty(self.task.at))

    def test_taking_back_lifts_the_last_tile_and_nothing_else(self):
        self.open_one()
        self.task.at = next(one for one in range(self.task.size() ** 2)
                            if self.task.deal.board.empty(one))
        self.task.lay(0)
        self.task.at = next(one for one in range(self.task.size() ** 2)
                            if self.task.deal.board.empty(one)
                            and one != self.task.laid[0][0])
        self.task.lay(1)
        self.task.take_back()
        self.assertEqual(len(self.task.laid), 1)
        self.assertEqual(self.task.spent, [0])

    def test_what_was_on_the_board_cannot_be_taken_back(self):
        self.open_one()
        was = self.task.deal.board.letters
        self.task.take_back()
        self.assertEqual(self.task.deal.board.letters, was)

    def test_nonsense_is_refused_rather_than_scored_as_zero(self):
        self.open_one()
        # Two tiles in a far corner, touching nothing.
        self.task.at = 0
        self.task.down = False
        self.task.lay(0)
        self.task.lay(1)
        self.task.submit()
        self.assertEqual(self.task.phase, 'playing')
        self.assertIsNone(self.task.verdict_shown)
        self.assertEqual(len(self.task.laid), 2)

    def test_an_empty_submission_is_refused(self):
        self.open_one()
        self.task.submit()
        self.assertEqual(self.task.phase, 'playing')
        self.assertIsNone(self.task.verdict_shown)

    def test_the_best_play_is_green(self):
        self.open_one()
        self.play_the_best()
        self.assertEqual(self.task.phase, 'scored')
        self.assertTrue(self.task.verdict_shown[0])

    def test_the_best_score_is_only_said_once_the_play_is_in(self):
        self.open_one()
        self.assertNotIn(str(self.task.deal.ceiling), self.task.status.text)
        self.play_the_best()
        self.assertIn(str(self.task.deal.ceiling), self.task.message)

    def test_a_poor_play_is_red(self):
        self.open_one()
        found = S.plays(self.task.deal.board, self.task.deal.rack,
                        W.pool(S.grade_of(self.task.rung).top_rank).narrowed(
                            hi=S.grade_of(self.task.rung).top_rank,
                            lengths=tuple(range(2, self.task.size() + 1))))
        worst = min(found, key=lambda one: one.score)
        if worst.score >= self.task.deal.ceiling * \
                S.grade_of(self.task.rung).share:
            self.skipTest('every play on this board is a good one')
        for cell, letter in worst.laid:
            slot = next(at for at, held in enumerate(self.task.deal.rack)
                        if held == letter and at not in self.task.spent)
            self.task.at = cell
            self.task.lay(slot)
        self.task.down = worst.down
        self.task.submit()
        self.assertEqual(self.task.phase, 'scored')
        self.assertFalse(self.task.verdict_shown[0])

    def test_the_verdict_is_down_again_when_the_next_trial_opens(self):
        self.open_one()
        self.play_the_best()
        self.task._next_trial()
        self.assertIsNone(self.task.verdict_shown)

    def test_a_relayout_puts_a_shown_verdict_back(self):
        self.open_one()
        self.play_the_best()
        self.task.relayout()
        self.assertTrue(self.task.verdict.label.text)

    # --- the mouse -------------------------------------------------------

    def middle_of(self, cell):
        x, y, step = self.task._cell_rect(cell)
        return int(x + step / 2), int(y + step / 2)

    def middle_of_tile(self, slot):
        x, y, width, height = self.task._tile_rect(slot)
        return int(x + width / 2), int(y + height / 2)

    def middle_of_play(self):
        left, bottom, width, height = self.task.play_rect()
        return int(left + width / 2), int(bottom + height / 2)

    def free_square(self):
        """A square with nothing on it — including nothing laid this turn.

        A tile laid this turn is not on the board yet, so
        ``board.empty`` still says yes about the square under it; a
        helper that trusted that walked the cursor onto its own tiles
        and the lays after the first were refused.
        """
        mine = {cell for cell, _letter in self.task.laid}
        return next(cell for cell in range(self.task.size() ** 2)
                    if self.task.deal.board.empty(cell)
                    and cell not in mine and cell != self.task.at)

    def play_the_best_by_mouse(self):
        best = self.task.deal.best
        for cell, letter in best.laid:
            self.task.on_mouse_press(*self.middle_of(cell), mouse.LEFT, 0)
            slot = next(at for at, held in enumerate(self.task.deal.rack)
                        if held == letter and at not in self.task.spent)
            self.task.on_mouse_press(*self.middle_of_tile(slot), mouse.LEFT, 0)
        self.task.down = best.down
        self.task.on_mouse_press(*self.middle_of_play(), mouse.LEFT, 0)

    def test_every_square_is_found_under_its_own_middle(self):
        self.open_one()
        for cell in range(self.task.size() ** 2):
            self.assertEqual(self.task.cell_at(*self.middle_of(cell)), cell)

    def test_a_click_goes_to_the_square_under_it(self):
        self.open_one()
        wanted = self.free_square()
        self.task.on_mouse_press(*self.middle_of(wanted), mouse.LEFT, 0)
        self.assertEqual(self.task.at, wanted)

    def test_clicking_the_square_you_are_on_turns(self):
        self.open_one()
        was, facing = self.task.at, self.task.down
        self.task.on_mouse_press(*self.middle_of(was), mouse.LEFT, 0)
        self.assertEqual(self.task.at, was)
        self.assertNotEqual(self.task.down, facing)

    def test_a_right_click_turns_without_moving(self):
        self.open_one()
        was, facing = self.task.at, self.task.down
        self.task.on_mouse_press(0, 0, mouse.RIGHT, 0)
        self.assertEqual(self.task.at, was)
        self.assertNotEqual(self.task.down, facing)

    def test_a_click_on_a_square_already_taken_lays_nothing(self):
        self.open_one()
        taken = next(cell for cell in range(self.task.size() ** 2)
                     if not self.task.deal.board.empty(cell))
        was = self.task.at
        self.task.on_mouse_press(*self.middle_of(taken), mouse.LEFT, 0)
        self.assertEqual(self.task.at, was)
        self.assertEqual(self.task.laid, [])

    def test_a_click_on_a_rack_tile_lays_it_where_the_cursor_is(self):
        self.open_one()
        where = self.task.at
        self.task.on_mouse_press(*self.middle_of_tile(0), mouse.LEFT, 0)
        self.assertEqual(self.task.laid, [(where, self.task.deal.rack[0])])

    def test_a_tile_already_played_is_not_there_to_click(self):
        self.open_one()
        where = self.middle_of_tile(0)
        self.task.on_mouse_press(*where, mouse.LEFT, 0)
        self.assertIsNone(self.task.tile_at(*where))
        self.task.on_mouse_press(*where, mouse.LEFT, 0)
        self.assertEqual(len(self.task.laid), 1)

    def test_clicking_a_tile_you_laid_lifts_that_one(self):
        self.open_one()
        for slot in (0, 1, 2):
            self.task.at = self.free_square()
            self.task.on_mouse_press(*self.middle_of_tile(slot), mouse.LEFT, 0)
        self.assertEqual(len(self.task.laid), 3)
        first, letter = self.task.laid[0]
        self.task.on_mouse_press(*self.middle_of(first), mouse.LEFT, 0)
        self.assertEqual(len(self.task.laid), 2)
        self.assertNotIn(first, [cell for cell, _l in self.task.laid])
        self.assertEqual(self.task.rack_left().count(letter),
                         self.task.deal.rack.count(letter)
                         - [held for _c, held in self.task.laid].count(letter))

    def test_lifting_out_of_order_puts_back_the_right_tile(self):
        # The slot lifted has to be the slot that tile came from, or a
        # rack of two Es lifts one and returns the other, and the tile
        # values quietly stop adding up.
        self.open_one()
        for slot in (0, 1, 2):
            self.task.at = self.free_square()
            self.task.on_mouse_press(*self.middle_of_tile(slot), mouse.LEFT, 0)
        middle_cell = self.task.laid[1][0]
        self.task.lift(middle_cell)
        self.assertEqual(self.task.spent, [0, 2])
        self.assertIsNotNone(self.task.tile_at(*self.middle_of_tile(1)))

    def test_the_play_button_plays(self):
        self.open_one()
        self.play_the_best_by_mouse()
        self.assertEqual(self.task.phase, 'scored')
        self.assertTrue(self.task.verdict_shown[0])

    def test_the_play_button_with_nothing_laid_is_refused(self):
        self.open_one()
        self.task.on_mouse_press(*self.middle_of_play(), mouse.LEFT, 0)
        self.assertEqual(self.task.phase, 'playing')
        self.assertIsNone(self.task.verdict_shown)

    def test_the_mouse_and_the_keyboard_lay_the_same_tiles(self):
        self.open_one()
        cell = self.free_square()
        self.task.at = cell
        self.task.on_mouse_press(*self.middle_of_tile(0), mouse.LEFT, 0)
        by_mouse = list(self.task.laid)
        self.task.take_back()
        self.task.at = cell
        self.task.lay(0)
        self.assertEqual(self.task.laid, by_mouse)

    def test_a_click_starts_a_run_and_takes_the_next_board(self):
        self.assertEqual(self.task.phase, 'ready')
        self.task.on_mouse_press(1, 1, mouse.LEFT, 0)
        self.assertEqual(self.task.phase, 'playing')
        self.play_the_best_by_mouse()
        self.task.on_mouse_press(1, 1, mouse.LEFT, 0)
        self.assertIn(self.task.phase, ('playing', 'done'))

    def test_hovering_is_not_choosing(self):
        self.open_one()
        was = self.task.at
        wanted = self.free_square()
        self.task.on_mouse_motion(*self.middle_of(wanted), 0, 0)
        self.assertEqual(self.task.hovered, wanted)
        self.assertEqual(self.task.at, was)
        self.task.on_mouse_motion(*self.middle_of_tile(0), 0, 0)
        self.assertEqual(self.task.hovered_tile, 0)
        self.assertEqual(self.task.laid, [])
        self.task.on_mouse_motion(*self.middle_of_play(), 0, 0)
        self.assertTrue(self.task.hovered_play)
        self.assertIsNone(self.task.hovered)

    def test_the_rack_and_the_button_sit_on_one_centred_row(self):
        # Centring the rack alone and hanging the button off its end
        # put the row off centre by half a button.
        self.open_one()
        left = self.task._tile_rect(0)[0]
        right = self.task.play_rect()[0] + self.task.play_rect()[2]
        self.assertAlmostEqual((left + right) / 2,
                               state.window.width / 2.0, delta=2.0)
        self.assertGreater(self.task.play_rect()[0],
                           self.task._tile_rect(
                               len(self.task.deal.rack) - 1)[0])

    def test_the_play_button_clears_the_verdict_band(self):
        self.open_one()
        for width, height in ((1024, 768), (912, 684), (800, 600)):
            geometry.set_window_size(width, height)
            self.task.relayout()
            self.assertGreaterEqual(self.task.play_rect()[1],
                                    above_the_band(0.0) - 1.0,
                                    (width, height))
            self.assertLessEqual(self.task.play_rect()[0]
                                 + self.task.play_rect()[2],
                                 state.window.width, (width, height))

    def test_the_rack_clears_the_verdict_band(self):
        # The rack is drawn below the board, so the board's own
        # clearance is not the task's — and a premium square is
        # painted vermilion, which is a colour the verdict reader
        # counts. Asserted against the geometry rather than left to
        # the sweep, because which premiums get painted depends on
        # which board was dealt.
        self.open_one()
        for width, height in ((1024, 768), (912, 684), (800, 600)):
            geometry.set_window_size(width, height)
            self.task.relayout()
            self.assertGreaterEqual(self.task.rack_box()[0],
                                    above_the_band(0.0) - 1.0,
                                    (width, height))
            self.assertGreaterEqual(self.task._board()[1],
                                    self.task.rack_box()[1], (width, height))


if __name__ == '__main__':
    unittest.main(verbosity=2)
