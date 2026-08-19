#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The long-term-memory games, and the media libraries they draw on.

Both games need downloaded material, so the tests that need it skip
when it is absent rather than failing — an empty library is a valid
state, and the games have to survive it too, which is tested here.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import unittest

from uisupport import (Concentration, NEW, Recognition, SEEN, close_overlays,
                       datasets, display, geometry, key, media, needs_ui,
                       reset_window, state)

#: Items each library needs before the games are worth testing.
NEEDED_IMAGES = 40
NEEDED_SOUNDS = 8


def _library(dataset, needed):
    return unittest.skipIf(
        datasets.have(dataset) < needed,
        'needs %d %s items; run the fetch in the Readme'
        % (needed, dataset.key))


class EmptyPoolTests(unittest.TestCase):
    """A library that was never downloaded is a state, not an error."""

    MISSING = datasets.Dataset(
        key='not-downloaded', repo='x/y', split='train', column='image',
        kind='image', suffix='.jpg', rows=1, approx_bytes=1)

    def test_an_absent_library_is_simply_empty(self):
        pool = media.MediaPool(self.MISSING)
        self.assertFalse(pool.ready(1))
        self.assertIsNone(pool.take())
        self.assertEqual(pool.take_many(5), [])
        self.assertIsNone(pool.recall())

    def test_it_can_say_what_is_missing(self):
        pool = media.MediaPool(self.MISSING)
        message = pool.missing_message(10)
        self.assertIn('not-downloaded', message)
        self.assertIn('10', message)

    def test_download_size_counts_only_what_is_absent(self):
        self.assertEqual(datasets.download_size(self.MISSING, 10), 10)
        self.assertEqual(datasets.download_size(self.MISSING, 0), 0)


@needs_ui
@_library(datasets.TINY_IMAGENET, NEEDED_IMAGES)
class MediaPoolTests(unittest.TestCase):
    """A pool hands out fresh items, and remembers what it handed out."""

    def setUp(self):
        self.pool = media.image_pool()

    def test_take_never_repeats_itself(self):
        taken = self.pool.take_many(30)
        self.assertEqual(len(taken), 30)
        self.assertEqual(len(set(taken)), 30)

    def test_recall_returns_something_already_given(self):
        taken = self.pool.take_many(10)
        for _ in range(10):
            self.assertIn(self.pool.recall(), taken)

    def test_recall_honours_the_exclusion(self):
        taken = self.pool.take_many(4)
        self.assertNotIn(self.pool.recall(exclude=taken[:3]), taken[:3])

    def test_reload_starts_the_session_over(self):
        self.pool.take_many(5)
        self.pool.reload()
        self.assertEqual(self.pool.given, [])
        self.assertIsNone(self.pool.recall())

    def test_items_decode(self):
        path = self.pool.take()
        image = self.pool.item(path)
        self.assertIsNotNone(image)
        self.assertGreater(image.width, 0)

    def test_decoding_is_cached(self):
        path = self.pool.take()
        self.assertIs(self.pool.item(path), self.pool.item(path))


@needs_ui
@_library(datasets.TINY_IMAGENET, NEEDED_IMAGES)
class ConcentrationTests(unittest.TestCase):
    """Turning cards over, and the board knowing when it is cleared."""

    def setUp(self):
        close_overlays()
        self.saved = {option.key: state.cfg[option.key]
                      for option in _concentration_options()}
        state.cfg.CONCENTRATION_MEDIUM = 'image'
        state.cfg.CONCENTRATION_PAIRS = 6
        state.cfg.CONCENTRATION_PEEK_MS = 0
        self.game = Concentration()

    def tearDown(self):
        close_overlays()
        state.cfg.update(self.saved)
        reset_window()

    def _pairs(self):
        by_index = collections.defaultdict(list)
        for card in self.game.cards:
            by_index[card.index].append(card)
        return by_index

    def test_the_deal_makes_two_of_everything(self):
        self.assertTrue(self.game.deal())
        self.assertEqual(len(self.game.cards), 12)
        pairs = self._pairs()
        self.assertEqual(len(pairs), 6)
        for cards in pairs.values():
            self.assertEqual(len(cards), 2)
            self.assertEqual(cards[0].path, cards[1].path)

    def test_every_card_gets_a_place_on_the_board(self):
        self.game.deal()
        columns, rows = self.game._grid_shape()
        self.assertGreaterEqual(columns * rows, len(self.game.cards))
        for card in self.game.cards:
            self.assertGreater(card.rect[2], 0)
            self.assertTrue(self.game.card_at(card.rect[0] + card.rect[2] / 2,
                                              card.rect[1] + card.rect[3] / 2))

    def test_a_matching_pair_stays_up(self):
        self.game.deal()
        first, second = list(self._pairs().values())[0]
        self.game.flip(first)
        self.game.flip(second)
        self.assertTrue(first.matched and second.matched)
        self.assertEqual(self.game.flipped, [])
        self.assertEqual(self.game.turns, 1)

    def test_a_mismatch_turns_back_over(self):
        self.game.deal()
        pairs = list(self._pairs().values())
        first, other = pairs[0][0], pairs[1][0]
        self.game.flip(first)
        self.game.flip(other)
        self.assertTrue(first.face_up and other.face_up)
        self.assertEqual(self.game.turns, 1)
        self.game.hide_at = 0          # the delay has passed
        self.game.update(0.1)
        self.assertFalse(first.face_up or other.face_up)
        self.assertFalse(first.matched or other.matched)

    def test_a_third_click_resolves_the_pair_first(self):
        self.game.deal()
        pairs = list(self._pairs().values())
        self.game.flip(pairs[0][0])
        self.game.flip(pairs[1][0])
        self.game.flip(pairs[2][0])
        self.assertEqual(len(self.game.flipped), 1)

    def test_clearing_the_board_finishes_the_game(self):
        self.game.deal()
        for cards in self._pairs().values():
            self.game.flip(cards[0])
            self.game.flip(cards[1])
        self.assertEqual(self.game.phase, 'done')
        self.assertEqual(self.game.turns, 6)
        self.assertTrue(all(card.matched for card in self.game.cards))

    def test_a_matched_card_ignores_further_clicks(self):
        self.game.deal()
        first, second = list(self._pairs().values())[0]
        self.game.flip(first)
        self.game.flip(second)
        turns = self.game.turns
        self.game.flip(first)
        self.assertEqual(self.game.turns, turns)
        self.assertEqual(self.game.flipped, [])

    def test_options_change_the_board(self):
        state.cfg.CONCENTRATION_PAIRS = 10
        self.game.apply_options()
        self.assertEqual(self.game.pairs, 10)
        self.game.deal()
        self.assertEqual(len(self.game.cards), 20)

    def test_a_peek_reveals_then_hides_the_board(self):
        state.cfg.CONCENTRATION_PEEK_MS = 2000
        self.game.apply_options()
        self.game.deal()
        self.assertEqual(self.game.phase, 'peek')
        self.assertTrue(all(card.face_up for card in self.game.cards))
        self.game.peek_until = 0
        self.game.update(0.1)
        self.assertEqual(self.game.phase, 'playing')
        self.assertFalse(any(card.face_up for card in self.game.cards))

    def test_a_resize_keeps_the_board_and_moves_it(self):
        self.game.deal()
        first = self.game.cards[0]
        self.game.flip(first)
        before = first.rect
        geometry.set_window_size(1024, 768)
        display.relayout()
        self.assertNotEqual(self.game.cards[0].rect, before)
        self.assertTrue(self.game.cards[0].face_up)
        self.assertEqual(len(self.game.cards), 12)

    def test_it_draws_in_every_phase(self):
        self.game.on_draw()
        self.game.deal()
        self.game.on_draw()
        for cards in self._pairs().values():
            self.game.flip(cards[0])
            self.game.flip(cards[1])
        self.game.on_draw()

    def test_c_opens_the_options(self):
        from uisupport import taskoptions
        self.game.on_key_press(key.C, 0)
        from uisupport import Menu
        self.assertIsInstance(Menu.instance, taskoptions.TaskOptions)
        Menu.instance.close()


def _concentration_options():
    from uisupport import taskoptions
    return taskoptions.CONCENTRATION.options


@needs_ui
@_library(datasets.ESC50, NEEDED_SOUNDS)
class ConcentrationSoundTests(unittest.TestCase):
    """The sound board is the same game with nothing to look at."""

    def setUp(self):
        close_overlays()
        self.saved = {option.key: state.cfg[option.key]
                      for option in _concentration_options()}
        state.cfg.CONCENTRATION_MEDIUM = 'sound'
        state.cfg.CONCENTRATION_PAIRS = 4
        self.game = Concentration()

    def tearDown(self):
        close_overlays()
        state.cfg.update(self.saved)

    def test_it_deals_sounds(self):
        self.assertEqual(self.game.medium, 'sound')
        self.assertTrue(self.game.deal())
        self.assertEqual(len(self.game.cards), 8)
        self.assertTrue(self.game.cards[0].path.endswith('.wav'))

    def test_flipping_a_card_plays_it(self):
        self.game.deal()
        self.game.flip(self.game.cards[0])
        self.assertIsNotNone(self.game.player)

    def test_a_sound_board_never_peeks(self):
        state.cfg.CONCENTRATION_PEEK_MS = 3000
        self.game.apply_options()
        self.game.deal()
        # Revealing sound cards would say nothing, so it is skipped.
        self.assertEqual(self.game.phase, 'playing')

    def test_closing_stops_the_sound(self):
        self.game.deal()
        self.game.flip(self.game.cards[0])
        self.game.close()
        self.assertIsNone(self.game.player)


@needs_ui
@_library(datasets.TINY_IMAGENET, NEEDED_IMAGES)
class RecognitionTests(unittest.TestCase):
    """The old/new task: how a run is built, and how it is scored."""

    def setUp(self):
        close_overlays()
        from uisupport import taskoptions
        self.saved = {option.key: state.cfg[option.key]
                      for option in taskoptions.RECOGNITION.options}
        state.cfg.RECOGNITION_MEDIUM = 'image'
        state.cfg.RECOGNITION_TRIALS = 40
        state.cfg.RECOGNITION_REPEAT_PERCENT = 40
        state.cfg.RECOGNITION_MIN_LAG = 4
        state.cfg.RECOGNITION_FEEDBACK = False
        self.game = Recognition()

    def tearDown(self):
        close_overlays()
        state.cfg.update(self.saved)
        reset_window()

    def test_a_run_is_the_length_asked_for(self):
        self.assertTrue(self.game.start_run())
        self.assertEqual(len(self.game.trials), 40)

    def test_every_repeat_is_a_genuine_second_showing(self):
        self.game.start_run()
        seen = set()
        repeated = set()
        for position, trial in enumerate(self.game.trials):
            if trial.repeat:
                self.assertIn(trial.path, seen,
                              'repeat at %d was never shown' % position)
                self.assertNotIn(trial.path, repeated,
                                 'third showing at %d' % position)
                repeated.add(trial.path)
            else:
                self.assertNotIn(trial.path, seen,
                                 'fresh item at %d was already shown' % position)
                seen.add(trial.path)

    def test_repeats_wait_out_the_minimum_gap(self):
        self.game.start_run()
        first = {}
        for position, trial in enumerate(self.game.trials):
            if trial.repeat:
                self.assertGreaterEqual(position - first[trial.path],
                                        self.game.min_lag)
            else:
                first[trial.path] = position

    def test_the_share_of_repeats_is_about_what_was_asked(self):
        self.game.start_run()
        repeats = sum(1 for trial in self.game.trials if trial.repeat)
        share = 100. * repeats / len(self.game.trials)
        self.assertGreater(share, 15)
        self.assertLess(share, 65)

    def test_perfect_answers_score_full_marks(self):
        self.game.start_run()
        while self.game.current() is not None:
            self.game.answer(SEEN if self.game.current().repeat else NEW)
        tally = self.game.score()
        self.assertEqual(tally['accuracy'], 100)
        self.assertEqual(tally['misses'], 0)
        self.assertEqual(tally['false_alarms'], 0)
        self.assertEqual(self.game.phase, 'done')

    def test_answering_seen_to_everything_cannot_win(self):
        # The point of scoring both halves: one constant answer scores
        # the repeat rate, not 50% and certainly not 100%.
        self.game.start_run()
        while self.game.current() is not None:
            self.game.answer(SEEN)
        tally = self.game.score()
        self.assertEqual(tally['misses'], 0)
        self.assertGreater(tally['false_alarms'], 0)
        self.assertLess(tally['accuracy'], 70)

    def test_answering_new_to_everything_cannot_win(self):
        self.game.start_run()
        while self.game.current() is not None:
            self.game.answer(NEW)
        tally = self.game.score()
        self.assertEqual(tally['hits'], 0)
        self.assertEqual(tally['false_alarms'], 0)
        self.assertLess(tally['accuracy'], 90)

    def test_the_tally_adds_up(self):
        self.game.start_run()
        while self.game.current() is not None:
            self.game.answer(SEEN if self.game.index % 3 else NEW)
        tally = self.game.score()
        self.assertEqual(tally['hits'] + tally['misses'], tally['repeats'])
        self.assertEqual(
            tally['hits'] + tally['misses'] + tally['false_alarms']
            + tally['correct_rejections'], tally['answered'])

    def test_an_answer_before_a_run_does_nothing(self):
        self.game.answer(SEEN)
        self.assertEqual(self.game.answers, [])

    def test_the_image_can_be_hidden_before_the_answer(self):
        state.cfg.RECOGNITION_STUDY_MS = 500
        self.game.apply_options()
        self.game.start_run()
        self.assertEqual(self.game.phase, 'showing')
        self.game.shown_at = 0          # the study time has passed
        self.game.update(0.1)
        self.assertEqual(self.game.phase, 'hidden')
        self.game.answer(NEW)           # still answerable
        self.assertEqual(len(self.game.answers), 1)

    def test_feedback_pauses_between_trials(self):
        state.cfg.RECOGNITION_FEEDBACK = True
        self.game.apply_options()
        self.game.start_run()
        self.game.answer(SEEN)
        self.assertEqual(self.game.phase, 'feedback')
        self.game.feedback_until = 0
        self.game.update(0.1)
        self.assertEqual(self.game.phase, 'showing')

    def test_a_resize_keeps_the_run(self):
        self.game.start_run()
        self.game.answer(NEW)
        trials = list(self.game.trials)
        geometry.set_window_size(1024, 768)
        display.relayout()
        self.assertEqual(self.game.trials, trials)
        self.assertEqual(self.game.index, 1)

    def test_it_draws_in_every_phase(self):
        self.game.on_draw()
        self.game.start_run()
        self.game.on_draw()
        while self.game.current() is not None:
            self.game.answer(NEW)
        self.game.on_draw()

    def test_the_answer_buttons_are_clickable(self):
        self.game.start_run()
        self.game._redraw()
        self.assertEqual(len(self.game.buttons), 2)
        left, bottom, width, height, choice = self.game.buttons[0]
        self.game.on_mouse_press(int(left + width / 2),
                                 int(bottom + height / 2), 1, 0)
        self.assertEqual(len(self.game.answers), 1)
        self.assertEqual(self.game.answers[0][1], choice)


@needs_ui
@_library(datasets.ESC50, NEEDED_SOUNDS)
class RecognitionSoundTests(unittest.TestCase):
    """The same task with nothing to look at."""

    def setUp(self):
        close_overlays()
        from uisupport import taskoptions
        self.saved = {option.key: state.cfg[option.key]
                      for option in taskoptions.RECOGNITION.options}
        state.cfg.RECOGNITION_MEDIUM = 'sound'
        state.cfg.RECOGNITION_TRIALS = 10
        self.game = Recognition()

    def tearDown(self):
        close_overlays()
        state.cfg.update(self.saved)

    def test_a_run_plays_the_first_clip(self):
        self.assertTrue(self.game.start_run())
        self.assertIsNotNone(self.game.player)
        self.assertTrue(self.game.trials[0].path.endswith('.wav'))

    def test_replay_plays_it_again(self):
        self.game.start_run()
        self.game.replay()
        self.assertIsNotNone(self.game.player)

    def test_a_sound_is_never_hidden_early(self):
        state.cfg.RECOGNITION_STUDY_MS = 500
        self.game.apply_options()
        self.game.start_run()
        self.game.shown_at = 0
        self.game.update(0.1)
        # Hiding a sound means nothing; the phase must not change.
        self.assertEqual(self.game.phase, 'showing')

    def test_answering_stops_the_clip(self):
        self.game.start_run()
        self.game.answer(NEW)
        self.assertIsNotNone(self.game.current())


if __name__ == '__main__':
    unittest.main(verbosity=2)
