#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Reflex: the attention task, and the clock it runs on.

Everything here drives time by hand — a target's age is how old its
``born`` stamp is, so backdating one is the same as waiting. That
keeps the tests instant and exact instead of sleeping and hoping.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import time
import unittest

from uisupport import (Reflex, TASKS, TaskHub, close_overlays, datasets,
                       display, geometry, key, needs_ui, reset_window, state)

NEEDED_IMAGES = 20


def _needs_images(cls):
    return unittest.skipIf(
        datasets.have(datasets.TINY_IMAGENET) < NEEDED_IMAGES,
        'needs %d images; run the fetch in the Readme' % NEEDED_IMAGES)(cls)


class AttentionCategoryTests(unittest.TestCase):
    """The hub gained a category, and it holds the task."""

    def test_attention_is_a_category(self):
        from neural_workshop.ui.taskhub import CATEGORIES
        ids = [cat for cat, _name in CATEGORIES]
        self.assertIn('attention', ids)
        self.assertIn('attention', TASKS)

    def test_the_roster_is_complete(self):
        self.assertEqual([task for task, _name in TASKS['attention']],
                         ['reflex', 'ncup_monte', 'moving_targets',
                          'lookout', 'pursuit'])

    def test_it_has_an_options_screen(self):
        from neural_workshop.ui import taskoptions
        self.assertTrue(taskoptions.has_options('reflex'))


@needs_ui
class AttentionHubTests(unittest.TestCase):
    """The category shows up on the hub and launches the task."""

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_the_hub_shows_the_category(self):
        hub = TaskHub(category='attention')
        self.assertEqual(hub.category, 'attention')
        self.assertEqual(hub.selected_task(), 'reflex')
        self.assertEqual(len(hub.tab_rects), len(TASKS))
        hub.on_draw()

    def test_every_tab_still_fits(self):
        hub = TaskHub()
        window_width = state.window.width
        for left, _bottom, width, _height, _cat in hub.tab_rects:
            self.assertGreaterEqual(left, 0)
            self.assertLessEqual(left + width, window_width)

    def test_cycling_reaches_it(self):
        hub = TaskHub(category='working_memory')
        seen = set()
        for _ in range(len(TASKS)):
            seen.add(hub.category)
            hub.cycle_category(1)
        self.assertIn('attention', seen)


@needs_ui
@_needs_images
class ReflexTests(unittest.TestCase):
    """Targets appear, shrink, and are either hit or missed."""

    def setUp(self):
        close_overlays()
        from neural_workshop.ui import taskoptions
        self.saved = {option.key: state.cfg[option.key]
                      for option in taskoptions.REFLEX.options}
        state.cfg.REFLEX_TARGETS = 20
        state.cfg.REFLEX_MAX_ACTIVE = 3
        state.cfg.REFLEX_SPAWN_MS = 150
        state.cfg.REFLEX_LIFETIME_MS = 1600
        state.cfg.REFLEX_ADAPTIVE = False
        self.game = Reflex()

    def tearDown(self):
        close_overlays()
        state.cfg.update(self.saved)
        reset_window()

    def _spawn(self, count=1):
        """Force *count* targets onto the screen."""
        for _ in range(count):
            self.game.next_spawn = 0
            self.game.update(0.016)
        return self.game.targets

    # --- spawning --------------------------------------------------------

    def test_a_run_starts_empty_and_fills(self):
        self.assertTrue(self.game.start_run())
        self.assertEqual(self.game.targets, [])
        self._spawn(1)
        self.assertEqual(len(self.game.targets), 1)

    def test_no_more_than_the_cap_are_live_at_once(self):
        self.game.start_run()
        self._spawn(10)
        self.assertEqual(len(self.game.targets), self.game.max_active)

    def test_targets_land_fully_on_screen(self):
        self.game.start_run()
        for target in self._spawn(3):
            centre_x, centre_y = target.centre()
            half = self.game.full_side() / 2
            self.assertGreaterEqual(centre_x - half, 0)
            self.assertLessEqual(centre_x + half, state.window.width)
            self.assertGreaterEqual(centre_y - half, 0)
            self.assertLessEqual(centre_y + half, state.window.height)

    def test_targets_land_in_different_places(self):
        self.game.start_run()
        places = {(round(t.x_frac, 3), round(t.y_frac, 3))
                  for t in self._spawn(3)}
        self.assertGreater(len(places), 1)

    def test_a_run_presents_the_number_asked_for(self):
        self.game.start_run()
        guard = 0
        while self.game.phase == 'running' and guard < 2000:
            guard += 1
            self.game.next_spawn = 0
            self.game.update(0.016)
            for target in list(self.game.targets):
                target.born = 0            # let them all expire
                self.game.update(0.016)
        self.assertEqual(self.game.phase, 'done')
        self.assertEqual(self.game.score()['presented'],
                         self.game.total_targets)

    # --- shrinking -------------------------------------------------------

    def test_a_target_shrinks_with_its_age(self):
        self.game.start_run()
        target = self._spawn(1)[0]
        full = target.side
        target.born = time.time() - self.game.lifetime * 0.5
        self.game.update(0.016)
        self.assertLess(target.side, full)
        self.assertGreater(target.side, 0)

    def test_remaining_runs_from_one_to_zero(self):
        self.game.start_run()
        target = self._spawn(1)[0]
        now = time.time()
        self.assertAlmostEqual(target.remaining(target.born), 1.0, places=2)
        self.assertAlmostEqual(
            target.remaining(target.born + target.lifetime), 0.0, places=6)
        self.assertEqual(target.remaining(now + target.lifetime * 5), 0.0)

    def test_a_target_that_vanishes_is_a_miss(self):
        self.game.start_run()
        target = self._spawn(1)[0]
        target.born = 0
        self.game.update(0.016)
        self.assertEqual(self.game.misses, 1)
        self.assertEqual(self.game.hits, 0)
        self.assertNotIn(target, self.game.targets)

    # --- clicking --------------------------------------------------------

    def test_clicking_a_target_scores_it(self):
        self.game.start_run()
        target = self._spawn(1)[0]
        centre_x, centre_y = target.centre()
        self.game.on_mouse_press(int(centre_x), int(centre_y), 1, 0)
        self.assertEqual(self.game.hits, 1)
        self.assertEqual(self.game.misses, 0)
        self.assertNotIn(target, self.game.targets)

    def test_clicking_nothing_costs_nothing(self):
        self.game.start_run()
        self._spawn(1)
        live = len(self.game.targets)
        self.game.on_mouse_press(1, 1, 1, 0)
        self.assertEqual(self.game.hits, 0)
        self.assertEqual(self.game.misses, 0)
        self.assertEqual(len(self.game.targets), live)

    def test_the_hit_box_follows_the_shrinking(self):
        self.game.start_run()
        target = self._spawn(1)[0]
        centre_x, centre_y = target.centre()
        edge = centre_x + target.side / 2 - 1
        self.assertIsNotNone(self.game.target_at(edge, centre_y))
        target.born = time.time() - self.game.lifetime * 0.9
        self.game.update(0.016)
        # The old edge is outside the target now that it has shrunk.
        self.assertIsNone(self.game.target_at(edge, centre_y))
        self.assertIsNotNone(self.game.target_at(centre_x, centre_y))

    def test_overlapping_targets_award_the_smaller_one(self):
        # The one about to vanish is the one worth rewarding.
        self.game.start_run()
        first, second = self._spawn(2)[:2]
        second.x_frac, second.y_frac = first.x_frac, first.y_frac
        second.born = time.time() - self.game.lifetime * 0.7
        self.game.update(0.016)
        centre_x, centre_y = first.centre()
        self.assertIs(self.game.target_at(centre_x, centre_y), second)

    def test_a_click_before_the_run_does_nothing(self):
        self.game.on_mouse_press(100, 100, 1, 0)
        self.assertEqual(self.game.hits, 0)

    def test_reaction_times_are_recorded(self):
        self.game.start_run()
        target = self._spawn(1)[0]
        centre_x, centre_y = target.centre()
        self.game.on_mouse_press(int(centre_x), int(centre_y), 1, 0)
        self.assertEqual(len(self.game.reaction_times), 1)
        self.assertGreaterEqual(self.game.score()['mean_ms'], 0)

    # --- scoring ---------------------------------------------------------

    def test_the_tally_adds_up(self):
        self.game.start_run()
        for _ in range(4):
            target = self._spawn(1)[-1]
            centre_x, centre_y = target.centre()
            self.game.on_mouse_press(int(centre_x), int(centre_y), 1, 0)
        for _ in range(2):
            target = self._spawn(1)[-1]
            target.born = 0
            self.game.update(0.016)
        tally = self.game.score()
        self.assertEqual(tally['hits'], 4)
        self.assertEqual(tally['misses'], 2)
        self.assertEqual(tally['presented'], 6)
        self.assertEqual(tally['accuracy'], 67)

    def test_an_untouched_run_scores_zero(self):
        self.assertEqual(self.game.score(),
                         {'hits': 0, 'misses': 0, 'presented': 0,
                          'accuracy': 0, 'mean_ms': 0})

    # --- adapting --------------------------------------------------------

    def test_adapting_off_leaves_the_life_alone(self):
        self.game.start_run()
        before = self.game.lifetime
        for _ in range(10):
            self.game._adapt(hit=True)
        self.assertEqual(self.game.lifetime, before)

    def test_hits_tighten_and_misses_ease(self):
        state.cfg.REFLEX_ADAPTIVE = True
        self.game.apply_options()
        self.game.start_run()
        before = self.game.lifetime
        self.game._adapt(hit=True)
        self.assertLess(self.game.lifetime, before)
        tightened = self.game.lifetime
        self.game._adapt(hit=False)
        self.assertGreater(self.game.lifetime, tightened)

    def test_a_run_of_hits_does_not_bottom_out(self):
        # Forty perfect hits should leave headroom, not sit on the floor.
        state.cfg.REFLEX_ADAPTIVE = True
        self.game.apply_options()
        self.game.start_run()
        for _ in range(40):
            self.game._adapt(hit=True)
        from neural_workshop.ui.reflex import MIN_LIFETIME
        self.assertGreater(self.game.lifetime, MIN_LIFETIME * 1.2)

    def test_the_life_stays_inside_its_bounds(self):
        from neural_workshop.ui.reflex import (MAX_LIFETIME_FACTOR,
                                               MIN_LIFETIME)
        state.cfg.REFLEX_ADAPTIVE = True
        self.game.apply_options()
        self.game.start_run()
        for _ in range(500):
            self.game._adapt(hit=True)
        self.assertGreaterEqual(self.game.lifetime, MIN_LIFETIME)
        for _ in range(500):
            self.game._adapt(hit=False)
        self.assertLessEqual(self.game.lifetime,
                             self.game.base_lifetime * MAX_LIFETIME_FACTOR)

    def test_a_new_run_starts_from_the_configured_life(self):
        state.cfg.REFLEX_ADAPTIVE = True
        self.game.apply_options()
        self.game.start_run()
        for _ in range(20):
            self.game._adapt(hit=True)
        self.game.start_run()
        self.assertEqual(self.game.lifetime, self.game.base_lifetime)

    # --- the window ------------------------------------------------------

    def test_a_resize_moves_targets_to_the_same_relative_place(self):
        self.game.start_run()
        target = self._spawn(1)[0]
        fracs = (target.x_frac, target.y_frac)
        before = target.centre()
        geometry.set_window_size(1024, 768)
        display.relayout()
        self.assertEqual((target.x_frac, target.y_frac), fracs)
        self.assertNotEqual(target.centre(), before)
        self.assertIsNotNone(target.sprite)
        self.game.on_draw()

    def test_the_target_size_follows_the_window(self):
        self.game.start_run()
        big = self.game.full_side()
        geometry.set_window_size(640, 480)
        display.relayout()
        self.assertLess(self.game.full_side(), big)

    def test_it_draws_in_every_phase(self):
        self.game.on_draw()
        self.game.start_run()
        self._spawn(2)
        self.game.on_draw()
        for target in list(self.game.targets):
            target.born = 0
        self.game.update(0.016)
        self.game.on_draw()

    def test_closing_takes_the_targets_with_it(self):
        self.game.start_run()
        self._spawn(2)
        self.game.close()
        self.assertEqual(self.game.targets, [])

    def test_c_opens_the_options(self):
        from uisupport import Menu
        from neural_workshop.ui import taskoptions
        self.game.on_key_press(key.C, 0)
        self.assertIsInstance(Menu.instance, taskoptions.TaskOptions)
        Menu.instance.close()

    def test_options_take_effect(self):
        state.cfg.REFLEX_MAX_ACTIVE = 1
        self.game.apply_options()
        self.game.start_run()
        self._spawn(5)
        self.assertEqual(len(self.game.targets), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)


class BounceTests(unittest.TestCase):
    """The wall bounce: pure arithmetic, no window needed."""

    def test_inside_passes_through(self):
        from neural_workshop.ui.tracking import bounced
        self.assertEqual(bounced(0.5, 0.2, 0.1, 0.9), (0.5, 0.2))

    def test_overshoot_folds_back_and_reflects(self):
        from neural_workshop.ui.tracking import bounced
        position, velocity = bounced(0.95, 0.3, 0.1, 0.9)
        self.assertAlmostEqual(position, 0.85)
        self.assertEqual(velocity, -0.3)
        position, velocity = bounced(0.05, -0.3, 0.1, 0.9)
        self.assertAlmostEqual(position, 0.15)
        self.assertEqual(velocity, 0.3)

    def test_the_bounce_never_sticks(self):
        """A ball glued to a wall with inward velocity keeps it."""
        from neural_workshop.ui.tracking import bounced
        _position, velocity = bounced(0.9, 0.3, 0.1, 0.9)
        self.assertEqual(velocity, 0.3)   # exactly on the wall: unchanged


@needs_ui
class MovingTargetsScreenTests(unittest.TestCase):

    def setUp(self):
        close_overlays()
        from uisupport import MovingTargets
        self.task = MovingTargets()
        self.task.total_rounds = 2
        self.task.adaptive = False

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _to_picking(self):
        """Walk the phases by backdating the clock, not by sleeping."""
        self.task.until = time.time() - 1
        self.task.update(1 / 60.)              # cueing -> tracking
        self.task.until = time.time() - 1
        self.task.update(1 / 60.)              # tracking -> picking
        self.assertEqual(self.task.phase, 'picking')

    def test_it_is_in_the_attention_category(self):
        self.assertIn('moving_targets',
                      [task for task, _name in TASKS['attention']])

    def test_a_round_cues_the_right_number_of_targets(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'cueing')
        self.assertEqual(len(self.task.balls), self.task.ball_count)
        self.assertEqual(self.task.tracked_now(), self.task.tracked)
        self.task.on_draw()

    def test_targets_never_swallow_the_whole_flock(self):
        self.task.ball_count = 4
        self.task.start_targets = 99
        self.assertEqual(self.task.clamped_targets(99), 3)

    def test_tracking_moves_the_balls_and_keeps_them_inside(self):
        self.task.start_run()
        self.task.until = time.time() - 1
        self.task.update(1 / 60.)
        self.assertEqual(self.task.phase, 'tracking')
        before = [(ball.x, ball.y) for ball in self.task.balls]
        for _frame in range(600):              # ten seconds of motion
            self.task._move(1 / 60.)
        low_x, high_x, low_y, high_y = self.task._bounds()
        for ball in self.task.balls:
            self.assertTrue(low_x <= ball.x <= high_x)
            self.assertTrue(low_y <= ball.y <= high_y)
        after = [(ball.x, ball.y) for ball in self.task.balls]
        self.assertNotEqual(before, after)

    def test_perfect_picks_score_and_reveal(self):
        self.task.start_run()
        self._to_picking()
        for ball in self.task.balls:
            if ball.target:
                self.task.pick(ball)
        self.assertEqual(self.task.phase, 'revealing')
        self.assertEqual(self.task.results[-1][2], self.task.results[-1][1])
        self.task.on_draw()

    def test_wrong_picks_score_what_they_caught(self):
        self.task.start_run()
        self._to_picking()
        # Pick only non-targets, as many as there are targets.
        wanted = self.task.tracked_now()
        for ball in self.task.balls:
            if not ball.target and wanted:
                self.task.pick(ball)
                wanted -= 1
        self.assertEqual(self.task.phase, 'revealing')
        self.assertEqual(self.task.results[-1][2], 0)

    def test_a_pick_can_be_taken_back(self):
        self.task.start_run()
        self._to_picking()
        if self.task.tracked_now() < 2:        # need room to change a mind
            self.skipTest('one target scores on the first pick')
        ball = self.task.balls[0]
        self.task.pick(ball)
        self.assertTrue(ball.picked)
        self.task.pick(ball)
        self.assertFalse(ball.picked)
        self.assertEqual(self.task.phase, 'picking')

    def test_adaptive_grows_on_perfect_and_shrinks_on_a_miss(self):
        self.task.adaptive = True
        self.task.start_run()
        was = self.task.tracked
        self._to_picking()
        for ball in self.task.balls:
            if ball.target:
                self.task.pick(ball)
        self.assertEqual(self.task.tracked,
                         self.task.clamped_targets(was + 1))

    def test_the_run_finishes_after_its_rounds(self):
        self.task.start_run()
        for _round in range(2):
            self._to_picking()
            for ball in self.task.balls:
                if ball.target:
                    self.task.pick(ball)
            self.task.until = time.time() - 1
            self.task.update(1 / 60.)          # revealing -> next round
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['accuracy'], 100)
        self.task.on_draw()

    def test_it_has_an_options_screen(self):
        from neural_workshop.ui import taskoptions
        self.assertTrue(taskoptions.has_options('moving_targets'))
        note = taskoptions.TRACKING.note(
            {'TRACK_BALLS': 4, 'TRACK_TARGETS': 10, 'TRACK_SECONDS': 8,
             'TRACK_ADAPTIVE': False})
        self.assertIn('3', note)               # the clamp is spelled out


class CueTests(unittest.TestCase):
    """The channel logic: pure functions, no window needed."""

    def test_channel_match_reads_only_its_channel(self):
        from neural_workshop.ui.lookout import Cue, channel_match
        cue = Cue(2, 1)
        self.assertTrue(channel_match(2, 3, cue, 'color'))
        self.assertFalse(channel_match(3, 3, cue, 'color'))
        self.assertTrue(channel_match(5, 1, cue, 'form'))
        self.assertFalse(channel_match(2, 0, cue, 'form'))

    def test_channel_words_name_the_right_half(self):
        from neural_workshop.ui.lookout import Cue, channel_words
        self.assertIn('orange', channel_words(Cue(0, 2), 'color'))
        self.assertIn('triangle', channel_words(Cue(0, 2), 'form'))
        self.assertNotIn('triangle', channel_words(Cue(0, 2), 'color'))

    def test_the_answer_keys_are_the_home_row_pair(self):
        from neural_workshop.ui.lookout import CHANNEL_KEYS
        self.assertEqual(CHANNEL_KEYS[key.F], 'form')
        self.assertEqual(CHANNEL_KEYS[key.J], 'color')


@needs_ui
class LookoutScreenTests(unittest.TestCase):

    def setUp(self):
        close_overlays()
        from uisupport import Lookout
        self.task = Lookout()
        self.task.total_cues = 2
        self.task.adaptive = False
        self.task.watching = 'both'

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _bend(self, channel, wanted=True):
        """Make the first shape satisfy (or every shape spoil) *channel*."""
        from neural_workshop.ui.lookout import channel_match
        cue = self.task.cue
        if wanted:
            drifter = self.task.shapes[0]
            if channel == 'color':
                drifter.color = cue.color
            else:
                drifter.form = cue.form
            drifter.drawn = None
            return
        for drifter in self.task.shapes:
            while channel_match(drifter.color, drifter.form, cue, channel):
                if channel == 'color':
                    drifter.color = (drifter.color + 1) % 6
                else:
                    drifter.form = (drifter.form + 1) % 4
                drifter.drawn = None

    def test_it_is_in_the_attention_category(self):
        self.assertIn('lookout',
                      [task for task, _name in TASKS['attention']])

    def test_a_run_begins_below_the_signal_on_every_channel(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'watching')
        for channel in self.task.channels():
            self.assertFalse(self.task.channel_on_screen(channel))
        self.assertEqual(len(self.task.shapes), self.task.count)
        self.task.on_draw()

    def test_each_channel_key_hits_its_own_signal(self):
        self.task.start_run()
        self._bend('form')
        self.task.update(1 / 60.)
        self.assertIsNotNone(self.task.seen['form'])
        self.assertIsNone(self.task.seen['color'])
        self.task.answer('form')
        self.assertEqual(self.task.hits, 1)
        self.assertEqual(len(self.task.reaction_times), 1)
        self.assertEqual(self.task.phase, 'feedback')

    def test_the_wrong_key_on_a_present_signal_is_a_false_alarm(self):
        self.task.start_run()
        self._bend('form')
        self.task.update(1 / 60.)
        self.task.answer('color')       # the shape is there, its colour not
        self.assertEqual(self.task.false_alarms, 1)
        self.assertEqual(self.task.hits, 0)

    def test_a_dead_channels_key_does_nothing(self):
        self.task.watching = 'color'
        self.task.start_run()
        self.task.answer('form')
        self.assertEqual(self.task.false_alarms, 0)
        self.assertEqual(self.task.phase, 'watching')

    def test_a_match_that_churns_away_is_a_miss(self):
        self.task.start_run()
        self._bend('color')
        self.task.update(1 / 60.)
        self.assertIsNotNone(self.task.seen['color'])
        self._bend('color', wanted=False)
        self.task.update(1 / 60.)
        self.assertEqual(self.task.misses, 1)
        self.assertEqual(self.task.phase, 'feedback')

    def test_a_drought_forces_a_dry_channel_into_the_flock(self):
        self.task.start_run()
        self.task.cued_at = time.time() - 60    # a long, dry watch
        drifter = self.task.shapes[0]
        drifter.next_morph = time.time() - 1
        self.task.update(1 / 60.)
        self.assertTrue(any(self.task.channel_on_screen(channel)
                            for channel in self.task.channels()))

    def test_morphs_always_change_something(self):
        self.task.start_run()
        drifter = self.task.shapes[0]
        self.task.phase = 'ready'               # no drought forcing
        for _try in range(30):
            was = (drifter.color, drifter.form)
            self.task._morph(drifter, time.time())
            self.assertNotEqual((drifter.color, drifter.form), was)
        self.task.phase = 'watching'

    def test_the_run_finishes_after_its_cues(self):
        self.task.start_run()
        for _cue in range(2):
            self.task.answer('color')            # false alarm, fine
            self.task.until = time.time() - 1
            self.task.update(1 / 60.)            # feedback -> next
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['false_alarms'], 2)
        self.task.on_draw()

    def test_adaptive_grows_on_hits_and_shrinks_on_mistakes(self):
        self.task.adaptive = True
        self.task.start_run()
        was = self.task.count
        self._bend('color')
        self.task.update(1 / 60.)
        self.task.answer('color')
        self.assertEqual(self.task.count, self.task.clamped(was + 1))
        self.task.until = time.time() - 1
        self.task.update(1 / 60.)                # next cue, flock grown
        self.assertEqual(len(self.task.shapes), self.task.count)
        self.task.answer('form')                 # false alarm
        self.assertEqual(self.task.count, self.task.clamped(was))

    def test_the_footnote_names_only_live_keys(self):
        self.task.watching = 'color'
        line = self.task._keys_line()
        self.assertIn('J', line)
        self.assertNotIn('F:', line)

    def test_it_has_an_options_screen(self):
        from neural_workshop.ui import taskoptions
        self.assertTrue(taskoptions.has_options('lookout'))
        note = taskoptions.LOOKOUT.note(
            {'LOOKOUT_SHAPES': 8, 'LOOKOUT_CUE': 'both',
             'LOOKOUT_ADAPTIVE': True})
        self.assertIn('Two keys', note)


@needs_ui
class PursuitScreenTests(unittest.TestCase):

    def setUp(self):
        close_overlays()
        from uisupport import Pursuit
        self.task = Pursuit()
        self.task.total_rounds = 2
        self.task.adaptive = False

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _cursor_on(self):
        quarry = self.task.quarry
        self.task.mouse = (quarry.x * state.window.width,
                           quarry.y * state.window.height)

    def _cursor_off(self):
        self.task.mouse = (-500.0, -500.0)

    def test_it_is_in_the_attention_category(self):
        self.assertIn('pursuit',
                      [task for task, _name in TASKS['attention']])

    def test_a_round_spawns_the_quarry_mid_screen(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'chasing')
        self.assertAlmostEqual(self.task.quarry.x, 0.5)
        self.assertAlmostEqual(self.task.quarry.y, 0.5)
        self.task.on_draw()

    def test_on_and_off_frames_split_the_round(self):
        self.task.start_run()
        self._cursor_on()
        self.task._sample(0.5)
        self._cursor_off()
        self.task._sample(0.5)
        self.assertAlmostEqual(self.task.on_time, 0.5)
        self.assertAlmostEqual(self.task.run_time, 1.0)
        self.assertEqual(self.task.off_samples, 1)
        self.assertGreater(self.task.off_sum, 0)

    def test_the_round_scores_its_share_and_drift(self):
        self.task.start_run()
        self._cursor_on()
        self.task._sample(3.0)
        self._cursor_off()
        self.task._sample(1.0)
        self.task._score()
        share, drift, _mult = self.task.results[-1]
        self.assertAlmostEqual(share, 0.75)
        self.assertGreater(drift, 100)
        self.assertEqual(self.task.phase, 'feedback')

    def test_swerves_change_heading_abruptly(self):
        self.task.start_run()
        quarry = self.task.quarry
        for _try in range(20):
            was = quarry.heading
            self.task._swerve(quarry, time.time())
            self.assertNotEqual(quarry.heading, was)
            self.assertLessEqual(abs(quarry.heading - was),
                                 self.task.sharpness + 1e-9)

    def test_surges_stay_around_the_base_pace(self):
        self.task.surge_depth = 0.6
        self.task.start_run()
        quarry = self.task.quarry
        for _try in range(50):
            self.task._lurch(quarry, time.time())
            self.assertGreaterEqual(quarry.surge, 0.15)
            self.assertLessEqual(quarry.surge, 1.6)

    def test_motion_stays_inside_the_bounds(self):
        self.task.start_run()
        self.task.multiplier = 3.0        # fast enough to hit walls
        for _frame in range(1200):
            if _frame % 40 == 0:
                self.task._swerve(self.task.quarry, time.time())
            self.task._move(1 / 60.)
        low_x, high_x, low_y, high_y = self.task._bounds()
        self.assertTrue(low_x <= self.task.quarry.x <= high_x)
        self.assertTrue(low_y <= self.task.quarry.y <= high_y)

    def test_zeroed_axes_never_fire(self):
        self.task.surge_depth = 0.0
        self.task.wobble = 0.0
        self.task.morph_gap = 0.0
        self.task.start_run()
        quarry = self.task.quarry
        was = (quarry.surge, quarry.radius, quarry.form)
        quarry.next_surge = quarry.next_resize = quarry.next_morph = 0.0
        quarry.next_turn = time.time() + 60
        self.task.update(1 / 60.)
        self.assertEqual((quarry.surge, quarry.radius, quarry.form), was)

    def test_adaptive_multiplier_moves_in_five_percent_steps(self):
        self.task.adaptive = True
        self.task.start_run()
        self._cursor_on()
        self.task._sample(1.0)
        self.task._score()                   # 100% on -> harder
        self.assertAlmostEqual(self.task.multiplier, 1.05)
        self.task.phase = 'chasing'
        self.task.on_time = 0.0
        self.task.run_time = 0.0
        self._cursor_off()
        self.task._sample(1.0)
        self.task._score()                   # 0% on -> easier
        self.assertAlmostEqual(self.task.multiplier, 1.05 * 0.95)

    def test_the_run_finishes_with_an_aggregate(self):
        self.task.start_run()
        for _round in range(2):
            self._cursor_on()
            self.task._sample(1.0)
            self.task._score()
            self.task.until = time.time() - 1
            self.task.update(1 / 60.)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['on_percent'], 100)
        self.task.on_draw()

    def test_it_has_an_options_screen(self):
        from neural_workshop.ui import taskoptions
        self.assertTrue(taskoptions.has_options('pursuit'))
        note = taskoptions.PURSUIT.note(
            {'PURSUIT_SPEED': 18, 'PURSUIT_TURN_MS': 900,
             'PURSUIT_TURN_DEGREES': 120, 'PURSUIT_SURGE': 0,
             'PURSUIT_SIZE_WOBBLE': 0, 'PURSUIT_MORPH_MS': 0,
             'PURSUIT_ADAPTIVE': True})
        self.assertIn('Switched off', note)
