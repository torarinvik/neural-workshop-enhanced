#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mr. Time: the interval it asks about, and the one it must not leak.

Most of what can go wrong in a timing task is not visible in a
screenshot, so most of these drive a virtual clock and check the
arithmetic that follows from it. Three of them are about something
else and are the reason this file is long:

* the interval is **frozen when the question appears**, so thinking
  about the answer costs nothing. Read again at submit, the task would
  be marking the player's typing speed while claiming to mark their
  timing.
* **nothing on screen counts**, and in particular the tolerance is
  never shown before the answer is in. The band is a fixed share of
  the interval, so a tolerance on the page is the answer divided by a
  constant.
* the shape stays **clear of the verdict band**, and that is asserted
  against the geometry rather than against a sweep, because where the
  shape lands is random and a clean sweep of random placements proves
  nothing about the placements it did not draw.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import (MrTime, TASKS, TaskHub, close_overlays, display,
                       geometry, key, needs_ui, reset_window, state)

#: Enough deals that a rare bad placement still shows up.
SAMPLE = 500


class LadderTests(unittest.TestCase):
    """The rungs, and the arithmetic that makes one harder than the last.

    No window needed: the ladder is a table and two functions over it.
    """

    def test_the_rungs_get_finer(self):
        from neural_workshop.ui.mrtime import RUNGS
        for lower, higher in zip(RUNGS, RUNGS[1:]):
            self.assertGreater(higher.per_second, lower.per_second)
            self.assertLess(higher.share, lower.share)

    def test_the_ladder_ends_in_nanoseconds(self):
        from neural_workshop.ui.mrtime import RUNGS
        self.assertEqual(RUNGS[-1].per_second, 1000000000.0)

    def test_a_rung_number_is_clamped_to_the_ladder(self):
        from neural_workshop.ui.mrtime import RUNGS, rung_at
        self.assertEqual(rung_at(-4), RUNGS[0])
        self.assertEqual(rung_at(99), RUNGS[-1])

    def test_the_band_is_a_share_of_the_interval(self):
        """Weber, not a fixed window: the whole point of the ladder."""
        from neural_workshop.ui.mrtime import tolerance
        self.assertAlmostEqual(tolerance(4.0, 1), 1.0)
        self.assertAlmostEqual(tolerance(8.0, 1), 2.0)
        self.assertAlmostEqual(tolerance(4.0, 3), 0.16)

    def test_a_climb_tightens_the_band(self):
        from neural_workshop.ui.mrtime import MAX_RUNG, tolerance
        bands = [tolerance(3.0, n) for n in range(1, MAX_RUNG + 1)]
        self.assertEqual(bands, sorted(bands, reverse=True))

    def test_the_top_rung_is_below_a_frame(self):
        """It is a ceiling rather than a rung, and the task says so."""
        from neural_workshop.ui.mrtime import MAX_RUNG, tolerance
        self.assertLess(tolerance(3.0, MAX_RUNG), 1 / 60.)

    def test_a_quantity_reads_in_its_own_unit(self):
        from neural_workshop.ui.mrtime import quantity
        self.assertEqual(quantity(0.042, 4), '42 ms')
        self.assertEqual(quantity(0.0042, 4), '4.20 ms')
        self.assertEqual(quantity(0.2, 1), '0.20 s')
        self.assertEqual(quantity(1.5, 6), '1,500,000,000 ns')


class PerceptionCategoryTests(unittest.TestCase):
    """It is in the hub, in the category it belongs to."""

    def test_mr_time_is_in_perception(self):
        self.assertIn('mr_time', [task for task, _name in
                                  TASKS['perception']])

    def test_it_has_an_options_screen(self):
        from neural_workshop.ui import taskoptions
        self.assertTrue(taskoptions.has_options('mr_time'))

    def test_the_options_note_does_not_leak_a_trial(self):
        """It quotes the band against the *longest* gap, not a dealt one."""
        from neural_workshop.ui import taskoptions
        note = taskoptions.MR_TIME.note(taskoptions.settings(
            taskoptions.MR_TIME))
        self.assertIn('%', note)
        self.assertIn('seconds', note)


@needs_ui
class MrTimeHubTests(unittest.TestCase):
    """The hub still lays out with a second task under Perception."""

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_the_hub_lists_both(self):
        hub = TaskHub(category='perception')
        self.assertEqual([task for task, _name in TASKS['perception']],
                         ['count', 'mr_time'])
        hub.on_draw()

    def test_it_can_be_selected(self):
        hub = TaskHub(category='perception')
        hub.selected = 1
        self.assertEqual(hub.selected_task(), 'mr_time')


@needs_ui
class MrTimeRunTests(unittest.TestCase):
    """A run under a clock the test owns."""

    def setUp(self):
        close_overlays()
        from neural_workshop.ui import taskoptions
        self.saved = {option.key: state.cfg[option.key]
                      for option in taskoptions.MR_TIME.options}
        state.cfg.MRTIME_MODE = 'recall'
        state.cfg.MRTIME_RUNG = 1
        state.cfg.MRTIME_TRIALS = 5
        state.cfg.MRTIME_MAX_GAP_MS = 2000
        state.cfg.MRTIME_FLASH_MS = 400
        state.cfg.MRTIME_ADAPTIVE = True
        self.game = MrTime()
        self.now = 0.0
        self.game.clock = lambda: self.now

    def tearDown(self):
        close_overlays()
        state.cfg.update(self.saved)
        reset_window()

    # --- helpers ---------------------------------------------------------

    def run_to(self, phase, limit=4000):
        """Tick until the task reaches *phase*."""
        for _tick in range(limit):
            if self.game.phase == phase:
                return True
            self.now += 1 / 60.
            self.game.update(1 / 60.)
        return False

    def type_seconds(self, value):
        for character in str(value):
            if character == '.':
                self.game.type_point()
            else:
                self.game.type_digit(character)

    def answer(self, value):
        self.type_seconds(value)
        self.game.submit()

    # --- the recall half -------------------------------------------------

    def test_a_run_starts_by_showing_a_shape(self):
        self.game.start_run()
        self.assertEqual(self.game.phase, 'showing')
        self.assertIsNotNone(self.game.mark)
        self.assertTrue(self.game.drawn)
        self.assertEqual(self.game.trial, 1)

    def test_the_shape_goes_away_when_the_flash_is_over(self):
        """Held open, because a short enough gap asks on the same tick.

        `update` is deliberately not an `elif`, so a gap under one frame
        takes the task from `showing` straight past `waiting` to `asking`
        inside a single call and nothing sampling between calls can see
        the phase at all. The gap is not what is under test here, so pin
        it out of the way rather than draw for it.
        """
        self.game.start_run()
        self.game.ask_at = (self.game.appeared_at
                            + self.game.flash_ms / 1000. + 1.0)
        self.assertTrue(self.run_to('waiting'))
        self.assertEqual(self.game.drawn, [])
        self.assertGreaterEqual(self.now, 0.4 - 1 / 60.)

    def test_the_question_arrives_and_the_shape_stays_away(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.assertEqual(self.game.drawn, [])
        self.assertIn('How long ago', self.game.question.text)

    def test_the_interval_is_measured_from_the_shape_appearing(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.assertAlmostEqual(self.game.interval,
                               self.now - self.game.appeared_at, places=6)
        self.assertGreaterEqual(self.game.interval, 0.4)

    def test_thinking_about_it_does_not_lengthen_the_interval(self):
        """Frozen when asked. Otherwise this marks typing speed."""
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        frozen = self.game.interval
        for _tick in range(600):                  # ten seconds of dithering
            self.now += 1 / 60.
            self.game.update(1 / 60.)
        self.assertEqual(self.game.phase, 'asking')
        self.assertEqual(self.game.interval, frozen)

    def test_a_right_answer_is_green_and_climbs(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.answer('%.3f' % self.game.interval)
        self.assertEqual(self.game.phase, 'feedback')
        self.assertTrue(self.game.verdict_shown[0])
        self.assertEqual(self.game.rung, 2)

    def test_a_wrong_answer_is_red_and_drops(self):
        state.cfg.MRTIME_RUNG = 3
        self.game.apply_options()
        self.game.clock = lambda: self.now
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.answer('%.3f' % (self.game.interval + 5))
        self.assertFalse(self.game.verdict_shown[0])
        self.assertEqual(self.game.rung, 2)

    def test_the_band_is_what_decides_it(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        interval = self.game.interval
        just_inside = interval + 0.24 * interval
        self.answer('%.4f' % just_inside)
        self.assertTrue(self.game.verdict_shown[0])

    def test_just_outside_the_band_is_a_miss(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        interval = self.game.interval
        self.answer('%.4f' % (interval + 0.26 * interval))
        self.assertFalse(self.game.verdict_shown[0])

    def test_holding_the_rung_holds_it(self):
        state.cfg.MRTIME_ADAPTIVE = False
        self.game.apply_options()
        self.game.clock = lambda: self.now
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.answer('%.3f' % self.game.interval)
        self.assertEqual(self.game.rung, 1)

    def test_the_rung_stays_on_the_ladder(self):
        from neural_workshop.ui.mrtime import MAX_RUNG, MIN_RUNG
        self.game.start_run()
        for _step in range(50):
            self.game._adapt(True)
        self.assertEqual(self.game.rung, MAX_RUNG)
        for _step in range(50):
            self.game._adapt(False)
        self.assertEqual(self.game.rung, MIN_RUNG)

    # --- typing ----------------------------------------------------------

    def test_typing_builds_a_number(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.type_seconds('2.75')
        self.assertEqual(self.game.answer_text, '2.75')
        self.assertAlmostEqual(self.game.answer_seconds(), 2.75)

    def test_backspace_takes_one_back(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.type_seconds('2.75')
        self.game.backspace()
        self.assertEqual(self.game.answer_text, '2.7')

    def test_there_is_only_one_decimal_point(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.type_seconds('2.7')
        self.game.type_point()
        self.assertEqual(self.game.answer_text, '2.7')

    def test_a_point_first_is_a_leading_zero(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.game.type_point()
        self.assertEqual(self.game.answer_text, '0.')
        self.assertIsNone(self.game.answer_seconds())

    def test_an_empty_answer_is_not_submitted(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.game.submit()
        self.assertEqual(self.game.results, [])
        self.assertEqual(self.game.phase, 'asking')

    def test_the_answer_cannot_run_away(self):
        from neural_workshop.ui.mrtime import MAX_ANSWER
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        for _press in range(40):
            self.game.type_digit('7')
        self.assertLessEqual(len(self.game.answer_text), MAX_ANSWER)

    def test_nothing_types_before_the_question(self):
        self.game.start_run()
        self.game.type_digit('4')
        self.game.type_point()
        self.assertEqual(self.game.answer_text, '')

    # --- the produce half ------------------------------------------------

    def produce_run(self, rung=1):
        state.cfg.MRTIME_MODE = 'produce'
        state.cfg.MRTIME_RUNG = rung
        self.game.apply_options()
        self.game.clock = lambda: self.now
        self.game.start_run()

    def test_a_produce_trial_states_a_duration_and_shows_the_shape(self):
        self.produce_run()
        self.assertEqual(self.game.phase, 'counting')
        self.assertTrue(self.game.drawn)
        self.assertGreaterEqual(self.game.target, 0.3)
        self.assertIn('Click the shape', self.game.question.text)

    def test_acting_on_time_is_green(self):
        self.produce_run()
        target = self.game.target
        while self.now - self.game.appeared_at < target:
            self.now += 1 / 60.
            self.game.update(1 / 60.)
        self.game.act_now()
        self.assertTrue(self.game.verdict_shown[0])

    def test_acting_far_too_early_is_red(self):
        self.produce_run()
        self.game.act_now()
        self.assertFalse(self.game.verdict_shown[0])

    def test_never_acting_settles_as_never_answered(self):
        from neural_workshop.ui.mrtime import LATE_GRACE
        self.produce_run()
        limit = self.game.target + LATE_GRACE + 1
        while self.now < limit and self.game.phase == 'counting':
            self.now += 1 / 60.
            self.game.update(1 / 60.)
        self.assertEqual(self.game.phase, 'feedback')
        self.assertFalse(self.game.verdict_shown[0])
        self.assertIsNone(self.game.results[0][2])

    def test_the_target_is_a_whole_number_of_the_rungs_units(self):
        from neural_workshop.ui.mrtime import rung_at
        for rung in (1, 2, 3):
            self.produce_run(rung)
            per = rung_at(rung).per_second
            self.assertAlmostEqual(self.game.target * per,
                                   round(self.game.target * per), places=6)

    def test_typing_does_nothing_on_a_produce_trial(self):
        self.produce_run()
        self.game.type_digit('5')
        self.game.submit()
        self.assertEqual(self.game.results, [])
        self.assertEqual(self.game.phase, 'counting')

    def test_acting_does_nothing_on_a_recall_trial(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.game.act_now()
        self.assertEqual(self.game.results, [])
        self.assertEqual(self.game.phase, 'asking')

    def test_both_deals_some_of_each(self):
        state.cfg.MRTIME_MODE = 'both'
        state.cfg.MRTIME_TRIALS = 80
        self.game.apply_options()
        self.game.clock = lambda: self.now
        self.game.start_run()
        dealt = set()
        for _trial in range(60):
            dealt.add(self.game.trial_mode)
            self.game._next_trial()
        self.assertEqual(dealt, {'recall', 'produce'})

    # --- what the screen may say -----------------------------------------

    def test_the_tolerance_is_never_on_screen_before_the_answer(self):
        """It is a fixed share of the interval, so it *is* the answer."""
        from neural_workshop.ui.mrtime import quantity
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        band = quantity(self.game.interval * 0.25, self.game.rung)
        on_screen = ' '.join([self.game.status.text, self.game.question.text,
                              self.game.prompt.text, self.game.answer.text,
                              self.game.title.text])
        self.assertNotIn(band, on_screen)
        self.assertNotIn('%.2f' % self.game.interval, on_screen)

    def test_the_verdict_is_not_up_while_the_answer_can_still_be_given(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.assertIsNone(self.game.verdict_shown)
        self.assertFalse(self.game.verdict.label.visible)

    def test_the_verdict_comes_down_before_the_next_trial(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.answer('%.3f' % self.game.interval)
        self.assertTrue(self.game.verdict.label.visible)
        self.game._next_trial()
        self.assertIsNone(self.game.verdict_shown)
        self.assertFalse(self.game.verdict.label.visible)

    def test_a_resize_keeps_the_verdict_up(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.answer('%.3f' % self.game.interval)
        geometry.set_window_size(1024, 768)
        display.relayout()
        self.assertTrue(self.game.verdict.label.visible)

    def test_a_resize_keeps_the_same_shape(self):
        self.produce_run()
        mark = self.game.mark
        geometry.set_window_size(1024, 768)
        display.relayout()
        self.assertEqual(self.game.mark, mark)
        self.assertEqual(len(self.game.drawn), 1)

    # --- geometry --------------------------------------------------------

    def test_every_shape_is_clear_of_the_verdict_band(self):
        """Against the geometry, not against a sweep of random deals.

        Where a shape lands is random, so a clean run of the band sweep
        says only that these placements were clear. The floor is what
        has to hold.
        """
        from neural_workshop.ui.mrtime import above_the_band
        for _deal in range(SAMPLE):
            mark = self.game._random_mark()
            centre_x, centre_y = self.game._to_pixels(mark.x, mark.y)
            radius = self.game._radius_pixels(mark)
            self.assertGreaterEqual(centre_y - radius, above_the_band())

    def test_every_shape_stays_inside_the_drawing_area(self):
        left, bottom, width, height = self.game.canvas()
        for _deal in range(SAMPLE):
            mark = self.game._random_mark()
            centre_x, centre_y = self.game._to_pixels(mark.x, mark.y)
            radius = self.game._radius_pixels(mark)
            self.assertGreaterEqual(centre_x - radius, left - 1)
            self.assertLessEqual(centre_x + radius, left + width + 1)
            self.assertGreaterEqual(centre_y - radius, bottom - 1)
            self.assertLessEqual(centre_y + radius, bottom + height + 1)

    def test_every_kind_builds_a_drawable(self):
        from neural_workshop.ui.mrtime import KINDS, Mark
        for kind in KINDS:
            built = self.game._build_mark(
                Mark(kind, 0.5, 0.5, 0.15, 0.4))
            self.assertIsNotNone(built, kind)
            built.delete()

    def test_a_click_on_the_shape_is_the_action(self):
        self.produce_run()
        centre_x, centre_y = self.game._to_pixels(self.game.mark.x,
                                                  self.game.mark.y)
        self.assertTrue(self.game.mark_at(centre_x, centre_y))
        self.game.on_mouse_press(int(centre_x), int(centre_y), 1, 0)
        self.assertEqual(len(self.game.results), 1)

    def test_a_click_off_the_shape_is_not(self):
        self.produce_run()
        self.game.on_mouse_press(2, 2, 1, 0)
        self.assertEqual(self.game.results, [])

    # --- a whole run -----------------------------------------------------

    def play_out(self, answer):
        """Play the configured run through, answering with *answer*."""
        for _tick in range(20000):
            if self.game.phase == 'done':
                return
            if self.game.phase == 'asking':
                self.answer('%.4f' % answer(self.game.interval))
            elif (self.game.phase == 'counting'
                  and self.now - self.game.appeared_at
                  >= answer(self.game.target)):
                self.game.act_now()
            self.now += 1 / 60.
            self.game.update(1 / 60.)
        self.fail('the run never finished')

    def test_a_perfect_run_scores_full_marks(self):
        self.game.start_run()
        self.play_out(lambda true: true)
        tally = self.game.score()
        self.assertEqual(tally['trials'], 5)
        self.assertEqual(tally['accuracy'], 100)
        self.assertLess(tally['weber'], 0.001)

    def test_a_run_that_always_doubles_scores_nothing(self):
        self.game.start_run()
        self.play_out(lambda true: true * 2)
        tally = self.game.score()
        self.assertEqual(tally['accuracy'], 0)
        self.assertAlmostEqual(tally['weber'], 1.0, places=3)

    def test_an_untouched_run_scores_nothing(self):
        self.assertEqual(self.game.score()['trials'], 0)
        self.assertEqual(self.game.score()['accuracy'], 0)

    def test_the_best_rung_reached_is_reported(self):
        self.game.start_run()
        self.play_out(lambda true: true)
        self.assertEqual(self.game.score()['best_rung'], 5)

    def test_it_draws_in_every_phase(self):
        self.game.on_draw()
        self.game.start_run()
        self.game.on_draw()
        self.assertTrue(self.run_to('asking'))
        self.game.on_draw()
        self.play_out(lambda true: true)
        self.game.on_draw()

    # --- keys ------------------------------------------------------------

    def test_enter_submits_and_digits_type(self):
        self.game.start_run()
        self.assertTrue(self.run_to('asking'))
        self.game.on_key_press(key._2, 0)
        self.game.on_key_press(key.PERIOD, 0)
        self.game.on_key_press(key._5, 0)
        self.assertEqual(self.game.answer_text, '2.5')
        self.game.on_key_press(key.RETURN, 0)
        self.assertEqual(len(self.game.results), 1)

    def test_space_acts_on_a_produce_trial(self):
        self.produce_run()
        self.game.on_key_press(key.SPACE, 0)
        self.assertEqual(len(self.game.results), 1)

    def test_space_starts_a_run_and_does_not_answer_one(self):
        self.game.on_key_press(key.SPACE, 0)
        self.assertEqual(self.game.trial, 1)
        self.assertTrue(self.run_to('asking'))
        self.game.on_key_press(key.SPACE, 0)
        self.assertEqual(self.game.results, [])

    def test_c_opens_the_options_between_runs(self):
        from uisupport import Menu
        from neural_workshop.ui import taskoptions
        self.game.on_key_press(key.C, 0)
        self.assertIsInstance(Menu.instance, taskoptions.TaskOptions)
        Menu.instance.close()

    def test_c_mid_trial_opens_nothing(self):
        from uisupport import Menu
        self.game.start_run()
        Menu.instance = None
        self.game.on_key_press(key.C, 0)
        self.assertIsNone(Menu.instance)


if __name__ == '__main__':
    unittest.main(verbosity=2)
