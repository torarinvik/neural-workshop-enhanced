#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Overrun: the runway, the clock, and what the screen does with both.

Two properties here carry the task and everything else is detail.

The first is the runway rule: a wave starts with as much clear road
ahead of it as it has characters. Get that wrong and a level stops
meaning one thing — a long sentence would be a harder question than a
short one at the same setting, the published words-a-minute would be
an average over two different tasks, and nothing would say so. So it
is checked as an identity rather than sampled: for every sentence in
the pool, the seconds a wave allows are its own length over the drift.

The second is that the drawing and the arithmetic agree about where
the end of the line is. The rules module kills a line by counting
character cells; the screen draws glyphs. If a glyph is wider than its
cell the two are answering different questions and a player loses a
life to a line that still looked clear of the margin. That is asserted
against the font this machine actually has, rather than trusted.

Nothing here needs the text fetched: the pool falls back to the
sentences in :data:`neural_workshop.sentences.SEED_TEXT`, which are in
the repository, and fifty-eight of the seventy are short enough to
deal. Two tests say when they want the fetched bank.

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

from uisupport import (Overrun, close_overlays, key,           # noqa: E402
                       needs_ui, reset_window)

from neural_workshop import overrun as O                       # noqa: E402
from neural_workshop import sentences as T                     # noqa: E402
from neural_workshop.ui.verdict import above_the_band          # noqa: E402


def waves(rung=6, count=40, seed=11):
    """A rung's worth of waves, dealt reproducibly."""
    rng = random.Random(seed)
    return [one for one in (O.deal_one(O.grade_of(rung), rng)
                            for _each in range(count)) if one]


class TheLadderTurnsOneDial(unittest.TestCase):
    """Twelve rungs, and the claim is that only the clock differs."""

    def test_there_are_twelve_of_them(self):
        self.assertEqual(len(O.GRADES), 12)

    def test_the_drift_climbs_and_never_sits_still(self):
        speeds = [grade.speed for grade in O.GRADES]
        self.assertEqual(speeds, sorted(speeds))
        for lower, higher in zip(speeds, speeds[1:]):
            self.assertGreater(higher, lower)

    def test_the_top_is_a_typist_and_the_bottom_is_not(self):
        """The range is the claim the options screen makes to a player."""
        self.assertLess(O.pace(1), 22.0)
        self.assertGreater(O.pace(len(O.GRADES)), 75.0)

    def test_the_pace_is_the_drift_and_nothing_else(self):
        """So a curve across the rungs is about rate rather than words.

        If any rung ever gains a vocabulary or a length of its own,
        this is the line that fails: the ratio of the demanded pace to
        the drift is one number for the whole ladder.
        """
        ratios = [O.pace(rung) / O.grade_of(rung).speed
                  for rung in range(1, len(O.GRADES) + 1)]
        self.assertAlmostEqual(min(ratios), max(ratios), places=9)

    def test_a_rung_off_the_end_is_the_nearest_one_on_it(self):
        self.assertEqual(O.grade_of(0), O.GRADES[0])
        self.assertEqual(O.grade_of(-4), O.GRADES[0])
        self.assertEqual(O.grade_of(99), O.GRADES[-1])


class TheRunwayIsAsLongAsTheText(unittest.TestCase):
    """The one rule that makes a level mean a single thing."""

    def test_the_end_of_the_line_starts_its_own_length_from_the_margin(self):
        for wave in waves(count=60):
            self.assertAlmostEqual(O.right_cell(wave, 0, 0.0),
                                   O.CELLS - wave.length, places=9)

    def test_so_the_time_allowed_is_the_length_over_the_drift(self):
        for wave in waves(count=60):
            self.assertAlmostEqual(
                O.deadline(wave, 0), wave.length / wave.grade.speed,
                places=9)
            self.assertAlmostEqual(wave.seconds, O.deadline(wave, 0),
                                   places=9)

    def test_and_the_rate_it_asks_for_is_the_drift_times_the_gaps(self):
        """Every wave of a rung asks for the same rate, near enough.

        Near enough, and the residue is the sentences rather than the
        layout: a line with long words in it is more keys for the same
        number of cells. Measured, the spread inside a rung is under a
        fifth; under the layout this replaced it was a factor of three,
        which is in ``tests/bench_overrun.py``.
        """
        for rung in (1, 6, 12):
            asked = [one.demand for one in waves(rung=rung, count=200)]
            self.assertLess(max(asked) / min(asked), 1.2, rung)

    def test_no_wave_starts_off_the_left_hand_end_of_the_lane(self):
        """Which is only true while the lane is twice the longest line."""
        self.assertGreaterEqual(O.CELLS, 2 * O.LONGEST)
        for wave in waves(count=60):
            self.assertGreaterEqual(wave.start_cell, 0)

    def test_the_whole_line_is_inside_the_lane_when_it_is_dealt(self):
        for wave in waves(count=60):
            self.assertGreaterEqual(O.left_cell(wave, 0.0), 0)
            self.assertLessEqual(O.right_cell(wave, 0, 0.0), O.CELLS)


class ClearingAWordHaulsTheLineBack(unittest.TestCase):
    """The tug of war, in the arithmetic rather than on the screen."""

    def test_a_cleared_word_buys_its_own_width_and_the_gap_after_it(self):
        for wave in waves(count=30):
            for index, word in enumerate(wave.words[:-1]):
                self.assertAlmostEqual(
                    O.deadline(wave, index + 1) - O.deadline(wave, index),
                    (len(word) + 1) / wave.grade.speed, places=9)

    def test_a_cleared_line_has_no_deadline_left(self):
        for wave in waves(count=20):
            self.assertEqual(O.deadline(wave, len(wave.words)),
                             float('inf'))
            self.assertFalse(O.overrun(wave, len(wave.words), 1e6))

    def test_the_line_is_safe_up_to_the_deadline_and_gone_at_it(self):
        for wave in waves(count=30):
            for cleared in range(len(wave.words)):
                due = O.deadline(wave, cleared) * wave.grade.speed
                self.assertFalse(O.overrun(wave, cleared, due - 1e-6))
                self.assertTrue(O.overrun(wave, cleared, due))

    def test_the_front_of_the_line_moves_only_with_the_clock(self):
        """Which is why the eye has one place to look.

        :func:`~neural_workshop.overrun.left_cell` does not take a word
        count, and this is the test that says that is deliberate rather
        than an omission: clearing a word takes the front off the line
        and what is behind it moves up into the same place.
        """
        wave = waves(count=1)[0]
        self.assertAlmostEqual(O.left_cell(wave, 3.0),
                               wave.start_cell + 3.0, places=9)


class TheLineIsLaidOutLikeASentence(unittest.TestCase):
    """The offsets are what ``' '.join`` would have put them at."""

    def test_every_word_is_where_its_offset_says_it_is(self):
        for wave in waves(count=40):
            line = wave.line
            for index, word in enumerate(wave.words):
                at = wave.starts[index]
                self.assertEqual(line[at:at + len(word)], word)

    def test_the_gaps_are_counted_but_never_typed(self):
        for wave in waves(count=40):
            self.assertEqual(wave.length,
                             wave.letters + len(wave.words) - 1)

    def test_the_offsets_of_an_empty_line_are_empty(self):
        self.assertEqual(O.starts_of([]), ())

    def test_one_word_starts_at_nothing(self):
        self.assertEqual(O.starts_of(['cat']), (0,))


class ThePoolIsSentencesThatFit(unittest.TestCase):
    """What the task will and will not deal."""

    def test_every_sentence_is_short_enough_to_have_its_own_runway(self):
        for one in O.pool():
            self.assertLessEqual(len(one.text), O.LONGEST)
            self.assertGreaterEqual(len(one.text), O.SHORTEST)

    def test_every_sentence_is_made_of_words_worth_typing(self):
        for one in O.pool():
            self.assertLessEqual(one.hardest, O.TOP_RANK)

    def test_there_is_something_to_play_with_nothing_fetched(self):
        """The seed text is in the repository, and it has to be enough.

        Not many — fifty-eight of the seventy written into the source —
        but a task that could not deal a wave offline would be a task
        whose first run says "no sentence at this level".
        """
        got = [one for one in T._graded(T.SEED_TEXT)
               if O.SHORTEST <= len(one.text) <= O.LONGEST
               and one.hardest <= O.TOP_RANK]
        self.assertGreater(len(got), 20)

    def test_the_pool_is_the_same_pool_twice(self):
        self.assertIs(O.pool(), O.pool())

    def test_forgetting_it_lets_it_be_read_again(self):
        first = O.pool()
        O.forget()
        again = O.pool()
        self.assertIsNot(first, again)
        self.assertEqual(len(first), len(again))

    def test_the_letter_share_is_measured_off_the_pool(self):
        found = O.pool()
        want = sum(sum(len(word) for word in one.words) / len(one.text)
                   for one in found) / len(found)
        self.assertAlmostEqual(O.letter_share(), want, places=9)


class ADealIsReproducible(unittest.TestCase):
    """A seed is a wave, so a bench and a bug report mean something."""

    def test_the_same_seed_deals_the_same_wave(self):
        for rung in range(1, len(O.GRADES) + 1):
            one = O.generate(rung, seed=4)
            other = O.generate(rung, seed=4)
            self.assertEqual(one, other)

    def test_different_seeds_mostly_deal_different_waves(self):
        got = {O.generate(6, seed=seed).line for seed in range(40)}
        self.assertGreater(len(got), 30)

    def test_a_wave_carries_the_grade_it_was_dealt_at(self):
        for rung in range(1, len(O.GRADES) + 1):
            self.assertEqual(O.generate(rung, seed=1).grade,
                             O.grade_of(rung))


class WordsAMinuteIsTheUsualConversion(unittest.TestCase):
    """Five characters to a word, because that is what typing is sold in."""

    def test_sixty_letters_in_a_minute_is_twelve_words(self):
        self.assertAlmostEqual(O.words_a_minute(60, 60.0), 12.0)

    def test_no_time_is_no_rate_rather_than_a_division(self):
        self.assertEqual(O.words_a_minute(20, 0.0), 0.0)
        self.assertEqual(O.words_a_minute(20, -1.0), 0.0)


# --- the screen -----------------------------------------------------------


@needs_ui
class TheOverrunScreen(unittest.TestCase):
    """The lane drawn, and the keys that empty it."""

    def setUp(self):
        reset_window()
        close_overlays()
        self.task = Overrun()
        self.task.rng = random.Random(5)
        # A clock of our own, because the pause between waves is on the
        # task's clock and not on the frame time — which is the whole
        # point of it having one, and is what lets a stepped boundary
        # drive this task at all.
        self.now = [1000.0]
        self.task.clock = lambda: self.now[0]
        self.task.start_rung = 6
        self.task.total_waves = 4
        self.task.adaptive = False
        self.task.start_run()

    def tearDown(self):
        close_overlays()
        reset_window()

    def go_on(self):
        """Let the pause after a settled wave pass, and deal the next."""
        self.now[0] += 5.0
        self.task.update(1 / 60.)

    def type_the_word(self):
        """Type the word at the front of the line, correctly."""
        word = self.task._target()
        for letter in word:
            self.task.write(letter)
        return word

    def type_the_line(self):
        while self.task.phase == 'typing':
            self.type_the_word()

    def run_out(self, limit=4000):
        """Let the clock take the line, touching nothing."""
        ticks = 0
        while self.task.phase == 'typing' and ticks < limit:
            self.task.update(1 / 60.)
            ticks += 1
        return ticks

    # --- the two ways a wave ends ------------------------------------

    def test_it_opens_with_three_lives(self):
        self.assertEqual(self.task.lives, O.START_LIVES)
        self.assertEqual(O.START_LIVES, 3)

    def test_a_line_typed_away_is_a_life_back(self):
        self.type_the_line()
        self.assertEqual(self.task.phase, 'settled')
        self.assertEqual(self.task.lives, O.START_LIVES + 1)
        self.assertEqual(self.task.verdict_shown[0], True)

    def test_a_line_that_runs_out_is_a_life_gone(self):
        self.run_out()
        self.assertEqual(self.task.phase, 'settled')
        self.assertEqual(self.task.lives, O.START_LIVES - 1)
        self.assertEqual(self.task.verdict_shown[0], False)

    def test_the_line_runs_out_when_the_arithmetic_says_it_does(self):
        """The screen's clock and the rules module agree, to a tick."""
        wave = self.task.wave
        ticks = self.run_out()
        self.assertAlmostEqual(ticks / 60., wave.seconds, delta=2 / 60.)

    def test_lives_do_not_climb_past_the_ceiling(self):
        self.task.lives = O.MOST_LIVES
        self.type_the_line()
        self.assertEqual(self.task.lives, O.MOST_LIVES)

    def test_the_run_ends_when_the_lives_do(self):
        self.task.lives = 1
        self.run_out()
        self.assertEqual(self.task.lives, 0)
        self.go_on()
        self.assertEqual(self.task.phase, 'done')

    def test_the_run_ends_when_the_waves_do(self):
        for _each in range(self.task.total_waves):
            self.type_the_line()
            self.go_on()
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(len(self.task.results), self.task.total_waves)

    def test_a_wave_is_not_counted_twice(self):
        self.type_the_line()
        self.go_on()
        self.assertEqual(self.task.trial, 2)
        self.assertEqual(len(self.task.results), 1)

    # --- typing ------------------------------------------------------

    def test_a_letter_that_lands_shows_in_the_word(self):
        word = self.task._target()
        self.task.write(word[0])
        self.assertEqual(self.task.typed, word[0])

    def test_a_wrong_letter_stays_where_it_was_put(self):
        """The whole floor of the task, in one assertion.

        Ignoring it would let a correct prefix only ever grow, which is
        what a walk needs to clear two thirds of the ladder without
        reading. See ``tests/bench_overrun.py``.
        """
        word = self.task._target()
        wrong = 'q' if word[0] != 'q' else 'z'
        self.task.write(wrong)
        self.assertEqual(self.task.typed, wrong)
        for letter in word[1:]:
            self.task.write(letter)
        self.assertEqual(self.task.cleared, 0, 'the word cleared anyway')

    def test_the_word_will_not_clear_until_the_wrong_letter_is_rubbed_out(
            self):
        word = self.task._target()
        wrong = 'q' if word[0] != 'q' else 'z'
        self.task.write(wrong)
        self.task.erase()
        for letter in word:
            self.task.write(letter)
        self.assertEqual(self.task.cleared, 1)

    def test_the_buffer_refuses_to_grow_past_the_word(self):
        """So a wrong line cannot be pushed out of its own cells."""
        word = self.task._target()
        wrong = 'q' if 'q' not in word else 'z'
        for _each in range(len(word) + 6):
            self.task.write(wrong)
        self.assertEqual(len(self.task.typed), len(word))

    def test_the_rate_printed_at_the_end_counts_only_what_landed(self):
        """Or a run of mashing would report a typing speed it never had."""
        word = self.task._target()
        wrong = 'q' if word[0] != 'q' else 'z'
        for _each in range(len(word)):
            self.task.write(wrong)
        self.assertEqual(self.task.landed, 0)
        self.assertEqual(self.task.missed, len(word))
        for _each in range(len(word)):
            self.task.erase()
        for letter in word:
            self.task.write(letter)
        self.assertEqual(self.task.landed, len(word))

    def test_a_rub_out_with_nothing_to_rub_out_does_nothing(self):
        self.task.erase()
        self.assertEqual(self.task.typed, '')
        self.assertEqual(self.task.phase, 'typing')

    def test_nothing_is_typed_once_the_wave_has_settled(self):
        self.run_out()
        settled = self.task.typed
        self.task.write('a')
        self.assertEqual(self.task.typed, settled)

    def test_a_key_that_is_not_a_letter_is_not_a_key(self):
        before = self.task.typed
        self.task.write('7')
        self.task.write(' ')
        self.assertEqual(self.task.typed, before)

    def test_the_words_are_cleared_in_the_order_they_are_written(self):
        wave = self.task.wave
        for index in range(len(wave.words)):
            self.assertEqual(self.task._target(), wave.words[index])
            if index < len(wave.words) - 1:
                self.type_the_word()

    # --- the ladder --------------------------------------------------

    def test_a_cleared_wave_climbs_a_rung_when_that_is_asked_for(self):
        self.task.adaptive = True
        self.task.rung = 6
        self.type_the_line()
        self.assertEqual(self.task.rung, 7)

    def test_a_spoiled_wave_drops_one(self):
        self.task.adaptive = True
        self.task.rung = 6
        self.run_out()
        self.assertEqual(self.task.rung, 5)

    def test_the_ladder_has_ends(self):
        self.task.adaptive = True
        self.task.rung = 1
        self.run_out()
        self.assertEqual(self.task.rung, 1)

    # --- the drawing -------------------------------------------------

    def test_every_glyph_fits_inside_its_own_cell(self):
        """Or the screen and the arithmetic disagree about the margin.

        Measured against whichever font this machine actually has,
        because that is what decides it. A glyph wider than its cell
        would be drawn past the end of the line the rules module is
        counting, and a player would lose a life to a word that still
        looked clear.
        """
        _left, _right, _middle, cell = self.task._lane()
        for label in self.task.chars:
            self.assertLessEqual(label.content_width, cell, label.text)

    def test_there_is_a_label_for_every_letter_and_none_for_a_gap(self):
        wave = self.task.wave
        self.assertEqual(len(self.task.chars), wave.letters)
        self.assertEqual(''.join(label.text for label in self.task.chars),
                         ''.join(wave.words))

    def test_the_line_is_drawn_where_the_arithmetic_puts_it(self):
        for _each in range(30):
            self.task.update(1 / 60.)
        left, _right, _middle, cell = self.task._lane()
        wave, task = self.task.wave, self.task
        want = left + (O.left_cell(wave, task.drift) + 0.5) * cell
        self.assertAlmostEqual(task.chars[0].x, want, delta=1.0)

    def test_the_end_of_the_line_reaches_the_margin_as_it_is_taken(self):
        self.run_out()
        _left, right, _middle, cell = self.task._lane()
        # One tick past the deadline, so the last drawn frame had the
        # line inside the margin and this one is the verdict.
        self.assertLess(self.task.drift * cell,
                        right + cell)

    def test_a_cleared_word_leaves_nothing_drawn(self):
        word = self.type_the_word()
        drawn = ''.join(label.text for label in self.task.chars)
        self.assertEqual(drawn, ''.join(self.task.wave.words[1:]))
        self.assertNotEqual(word, '')

    def test_the_word_being_typed_is_at_the_front_of_the_line(self):
        """It moves with the clock and never with the typing."""
        left, _right, _middle, cell = self.task._lane()
        before = self.task.chars[0].x
        self.type_the_word()
        after = next(label.x for index, label in enumerate(self.task.chars)
                     if self.task.owner[index] == self.task.cleared)
        self.assertAlmostEqual(before, after, delta=1.0)
        self.assertGreater(before, left)

    def test_a_typed_letter_is_painted_over_the_one_it_replaces(self):
        word = self.task._target()
        wrong = 'q' if word[0] != 'q' else 'z'
        self.task.write(wrong)
        self.assertEqual(self.task.chars[0].text, wrong)
        self.task.erase()
        self.task.write(word[0])
        self.assertEqual(self.task.chars[0].text, word[0])

    def test_the_lives_on_screen_are_the_lives_held(self):
        for lives in (3, 1, 0, O.MOST_LIVES):
            self.task.lives = lives
            self.task._redraw()
            shown = sum(1 for disc in self.task.life_discs if disc.visible)
            self.assertEqual(shown, lives)

    # --- the band ----------------------------------------------------

    def test_nothing_this_task_draws_reaches_the_verdict_band(self):
        """Asserted against the geometry rather than swept for.

        The line is drawn in three saturated colours and the margin in
        a fourth, and every one of them has a blend with the page that
        the boundary's reader would count. A sweep would only ever say
        that the wave it happened to deal was clear.
        """
        ceiling = above_the_band(0)
        self.assertGreaterEqual(self.task._floor(), ceiling)
        for shape in self.task.drawn:
            self.assertGreater(min(shape.y, shape.y2), ceiling)
        for disc in self.task.life_discs:
            self.assertGreater(disc.y - disc.radius, ceiling)
        for label in self.task.chars:
            self.assertGreater(label.y - label.font_size, ceiling)

    # --- the keyboard ------------------------------------------------

    def test_a_letter_key_is_a_letter(self):
        word = self.task._target()
        self.task.on_key_press(key.A + (ord(word[0]) - ord('a')), 0)
        self.assertEqual(self.task.typed, word[0])

    def test_backspace_rubs_out(self):
        word = self.task._target()
        self.task.write(word[0])
        self.task.on_key_press(key.BACKSPACE, 0)
        self.assertEqual(self.task.typed, '')

    def test_space_is_not_a_key_in_this_game(self):
        """The words clear themselves, so the bar is free to be the way on."""
        before = self.task.typed
        self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.typed, before)
        self.assertEqual(self.task.phase, 'typing')

    def test_the_options_key_is_refused_while_the_line_is_moving(self):
        """Because O is a letter, and a letter is a move here."""
        self.task.on_key_press(key.O, 0)
        self.assertEqual(self.task.phase, 'typing')
        self.assertEqual(self.task.typed, 'o')


@needs_ui
class TheVerdictIsPaintedWhenItIsEarned(unittest.TestCase):
    """A verdict is the trial's scalar, so when it goes up matters."""

    def setUp(self):
        reset_window()
        close_overlays()
        self.task = Overrun()
        self.task.rng = random.Random(9)
        self.now = [1000.0]
        self.task.clock = lambda: self.now[0]
        self.task.total_waves = 3
        self.task.start_run()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_no_verdict_is_up_while_the_line_can_still_be_typed(self):
        for _each in range(20):
            self.task.write(self.task._target()[0])
            self.task.update(1 / 60.)
            if self.task.phase != 'typing':
                break
            self.assertIsNone(self.task.verdict_shown)

    def test_the_coach_is_off_for_a_person(self):
        """So the human game is pixel-identical to the one before it."""
        self.assertFalse(self.task.coach)

    def test_with_the_coach_on_a_letter_that_lands_pays(self):
        self.task.coach = True
        self.task.write(self.task._target()[0])
        self.assertEqual(self.task.verdict_shown[0], True)

    def test_with_the_coach_on_a_letter_that_misses_costs(self):
        self.task.coach = True
        word = self.task._target()
        self.task.write('q' if word[0] != 'q' else 'z')
        self.assertEqual(self.task.verdict_shown[0], False)

    def test_a_rub_out_pays_nothing_at_all(self):
        """Or typing a wrong letter would be worth doing to take it back."""
        self.task.coach = True
        word = self.task._target()
        self.task.write('q' if word[0] != 'q' else 'z')
        self.task.erase()
        self.assertIsNone(self.task.verdict_shown)

    def test_the_verdict_is_taken_down_before_the_next_wave(self):
        while self.task.phase == 'typing':
            self.task.update(1 / 60.)
        self.assertIsNotNone(self.task.verdict_shown)
        self.now[0] += 5.0
        self.task.update(1 / 60.)
        self.assertEqual(self.task.phase, 'typing')
        self.assertIsNone(self.task.verdict_shown)

    def test_a_verdict_already_up_survives_a_resize(self):
        """Or a window change on the frame a wave settles loses its scalar."""
        while self.task.phase == 'typing':
            self.task.update(1 / 60.)
        shown = self.task.verdict_shown
        self.task.relayout()
        self.assertEqual(self.task.verdict_shown, shown)
        self.assertTrue(self.task.verdict.label.visible)


@needs_ui
class TheOptionsScreenSaysWhatTheLevelCosts(unittest.TestCase):
    """The rate is the one number a player already knows their own value of."""

    def tearDown(self):
        close_overlays()
        reset_window()

    def chosen(self, rung):
        from neural_workshop.ui import taskoptions
        spec = taskoptions.TASK_SPECS['overrun']
        picked = dict(taskoptions.settings(spec))
        picked['OVERRUN_LEVEL'] = rung
        return spec.note(picked)

    def test_the_note_prints_the_rate_the_level_asks_for(self):
        for rung in range(1, len(O.GRADES) + 1):
            said = self.chosen(rung)
            self.assertIn('%d words a minute' % int(round(O.pace(rung))),
                          said)

    def test_the_note_names_the_source_of_the_text(self):
        """Wikipedia's licence wants attribution where a person will see it."""
        self.assertIn(T.REPO, self.chosen(1))
        self.assertIn(T.LICENCE, self.chosen(1))

    def test_the_screen_opens(self):
        from neural_workshop.ui import taskoptions
        self.assertTrue(taskoptions.has_options('overrun'))
        self.assertIsNotNone(taskoptions.open_task_options('overrun'))


@needs_ui
class TheTaskReadsTheClockItIsGiven(unittest.TestCase):
    """A stepped run advances a virtual clock; nothing may read the wall."""

    def setUp(self):
        reset_window()
        close_overlays()
        self.task = Overrun()
        self.task.rng = random.Random(2)
        self.task.total_waves = 3
        self.task.start_run()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_the_settle_waits_on_the_task_s_own_clock(self):
        now = [1000.0]
        self.task.clock = lambda: now[0]
        while self.task.phase == 'typing':
            self.task.update(1 / 60.)
        self.assertEqual(self.task.phase, 'settled')
        self.task.update(1 / 60.)
        self.assertEqual(self.task.phase, 'settled')
        now[0] += 10.0
        self.task.update(1 / 60.)
        self.assertEqual(self.task.phase, 'typing')

    def test_a_stalled_frame_cannot_teleport_the_line_past_the_margin(self):
        """A slow machine is a nuisance; a life lost to it is a bug."""
        wave = self.task.wave
        self.task.update(30.0)
        self.assertLessEqual(self.task.drift, wave.grade.speed * 0.1 + 1e-9)


if __name__ == '__main__':
    unittest.main()
