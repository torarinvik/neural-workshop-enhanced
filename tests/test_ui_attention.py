#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Reflex: the attention task, and the clock it runs on.

Everything here drives time by hand — a target's age is how old its
``born`` stamp is, so backdating one is the same as waiting. That
keeps the tests instant and exact instead of sleeping and hoping.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
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
                          'lookout', 'pursuit', 'out_of_sight'])

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

    def test_no_target_reaches_into_the_verdict_band(self):
        """The strip the agent boundary reads a scalar out of.

        Targets are photographs, so a target low on the screen paints
        whatever that picture happens to contain — and a saturated run
        down there is read as a scored trial on a trial nobody scored.
        It used to spawn from a tenth of the way up, which is inside the
        bottom quarter, and ``check_band.py`` caught it about one run in
        three because it depended on which pictures were drawn. That is
        the worst way for an instrument defect to behave, so the guard
        is here as well: this one does not sample.

        The bottom edge **at full size** is what is checked, because a
        target only shrinks towards its own centre — clear at spawn is
        clear for the rest of its life.
        """
        from neural_workshop.ui.verdict import above_the_band
        floor = above_the_band()
        self.game.start_run()
        low = []
        for _round in range(40):
            for target in self._spawn(1):
                _centre_x, centre_y = target.centre()
                low.append(centre_y - self.game.full_side() / 2)
            for target in list(self.game.targets):
                target.born = 0
            self.game.update(0.016)
        self.assertTrue(low)
        self.assertGreaterEqual(min(low), floor,
                                'lowest edge %.0f, band ceiling %d'
                                % (min(low), floor))

    def test_the_biggest_targets_still_have_somewhere_to_go(self):
        """Raising the floor must not pin every target to one line.

        At the largest size the sprite is most of the window's height,
        and a floor that left no room would have turned a task about
        finding them into a task about clicking the same spot.
        """
        from neural_workshop.ui.verdict import above_the_band
        state.cfg.REFLEX_SIZE = 280
        self.game.apply_options()
        self.game.start_run()
        floor = above_the_band()
        half = self.game.full_side() / 2
        seen = set()
        for _round in range(30):
            for target in self._spawn(1):
                _centre_x, centre_y = target.centre()
                self.assertGreaterEqual(centre_y - half, floor)
                self.assertLessEqual(centre_y + half, state.window.height)
                seen.add(round(target.y_frac, 2))
            for target in list(self.game.targets):
                target.born = 0
            self.game.update(0.016)
        self.assertGreater(len(seen), 3, sorted(seen))

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


class BlindTests(unittest.TestCase):
    """The slabs: pure rectangles, no window needed."""

    def test_a_slab_covers_only_its_own_rectangle(self):
        from neural_workshop.ui.outofsight import Blind
        slab = Blind(0.2, 0.3, 0.1, 0.4)
        self.assertTrue(slab.covers(0.25, 0.5))
        self.assertTrue(slab.covers(0.2, 0.3))        # its own corner
        self.assertFalse(slab.covers(0.31, 0.5))
        self.assertFalse(slab.covers(0.25, 0.71))

    def test_slabs_that_share_area_overlap(self):
        from neural_workshop.ui.outofsight import Blind
        one = Blind(0.2, 0.2, 0.2, 0.2)
        self.assertTrue(one.overlaps(Blind(0.3, 0.3, 0.2, 0.2)))
        self.assertFalse(one.overlaps(Blind(0.4, 0.2, 0.2, 0.2)))  # abutting
        self.assertFalse(one.overlaps(Blind(0.2, 0.5, 0.2, 0.2)))

    def test_only_the_part_inside_the_field_is_charged_for(self):
        """A slab hanging past the wall costs the flock nothing."""
        from neural_workshop.ui.outofsight import Blind, area_in
        field = (0.0, 1.0, 0.0, 1.0)
        self.assertAlmostEqual(area_in(Blind(0.2, 0.2, 0.4, 0.5), field),
                               0.2)
        self.assertAlmostEqual(area_in(Blind(-0.2, 0.0, 0.4, 0.5), field),
                               0.1)
        self.assertAlmostEqual(area_in(Blind(2.0, 2.0, 0.4, 0.5), field),
                               0.0)

    def test_hidden_asks_every_slab(self):
        from neural_workshop.ui.outofsight import Blind, hidden
        slabs = [Blind(0.0, 0.0, 0.1, 0.1), Blind(0.8, 0.8, 0.1, 0.1)]
        self.assertTrue(hidden(slabs, 0.85, 0.85))
        self.assertFalse(hidden(slabs, 0.5, 0.5))
        self.assertFalse(hidden([], 0.5, 0.5))


class RendezvousTests(unittest.TestCase):
    """A crossing has to be symmetric or it gives the answer away."""

    @staticmethod
    def _pair(ax=0.2, ay=0.3, bx=0.8, by=0.7):
        from neural_workshop.ui.outofsight import Dot
        return (Dot(ax, ay, 0.0, 0.0, target=True),
                Dot(bx, by, 0.0, 0.0, target=False))

    def test_both_dots_leave_at_the_asked_speed(self):
        """Neither hurries, so pace never says which dot is which."""
        from neural_workshop.ui.outofsight import rendezvous
        one, other = self._pair()
        rendezvous(one, other, 0.2, aspect=0.75)
        self.assertAlmostEqual(math.hypot(one.vx, one.vy), 0.2)
        self.assertAlmostEqual(math.hypot(other.vx, other.vy), 0.2)

    def test_the_two_velocities_are_exact_opposites(self):
        from neural_workshop.ui.outofsight import rendezvous
        one, other = self._pair()
        rendezvous(one, other, 0.2, aspect=0.75)
        self.assertAlmostEqual(one.vx, -other.vx)
        self.assertAlmostEqual(one.vy, -other.vy)

    def test_they_arrive_at_the_same_place_at_the_same_time(self):
        from neural_workshop.ui.outofsight import rendezvous
        one, other = self._pair()
        aspect = 0.75
        seconds = rendezvous(one, other, 0.2, aspect)
        self.assertGreater(seconds, 0.0)
        for dot in (one, other):
            dot.x += dot.vx * seconds * aspect
            dot.y += dot.vy * seconds
        self.assertAlmostEqual(one.x, other.x)
        self.assertAlmostEqual(one.y, other.y)

    def test_dots_already_in_the_same_place_are_left_alone(self):
        from neural_workshop.ui.outofsight import rendezvous
        one, other = self._pair(0.4, 0.4, 0.4, 0.4)
        self.assertEqual(rendezvous(one, other, 0.2, aspect=0.75), 0.0)
        self.assertEqual((one.vx, one.vy), (0.0, 0.0))


@needs_ui
class OutOfSightScreenTests(unittest.TestCase):
    """The whole task, with the clock driven by hand.

    Nothing here sleeps: a phase ends when its deadline is backdated,
    a question arrives when ``next_probe`` is, and a verdict clears
    when ``verdict_until`` is. That keeps the tests exact instead of
    racing the wall clock.
    """

    def setUp(self):
        close_overlays()
        from uisupport import OutOfSight
        self.task = OutOfSight()
        self.task.total_rounds = 2
        self.task.probes_per_round = 4
        self.task.adaptive = False

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _to_tracking(self):
        self.task.start_run()
        self.task.until = time.time() - 1
        self.task.update(1 / 60.)
        self.assertEqual(self.task.phase, 'tracking')

    def _ask(self):
        """Force the next question up and hand back the ringed dot."""
        for _frame in range(240):
            self.task.next_probe = time.time() - 1
            self.task.update(1 / 60.)
            if self.task.probe is not None:
                return self.task.probe
        self.fail('no question ever came up')

    def _clear(self):
        self.task.verdict_until = time.time() - 1
        self.task.update(1 / 60.)

    def _answer_the_round(self, wrong=0):
        """Answer every question of the round, *wrong* of them badly."""
        for index in range(self.task.probes_per_round):
            dot = self._ask()
            self.task.answer(dot.target if index >= wrong
                             else not dot.target)
            self._clear()
        self.task.update(1 / 60.)          # the round notices it is over

    def _skip_the_reveal(self):
        """Walk from the reveal into the next round's motion."""
        self.task.until = time.time() - 1
        self.task.update(1 / 60.)          # revealing -> cueing
        if self.task.phase == 'cueing':
            self.task.until = time.time() - 1
            self.task.update(1 / 60.)      # cueing -> tracking

    def test_it_is_in_the_attention_category(self):
        self.assertIn('out_of_sight',
                      [task for task, _name in TASKS['attention']])

    def test_a_round_deals_the_dots_and_flashes_yours(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'cueing')
        self.assertEqual(len(self.task.dots), self.task.dot_count)
        self.assertEqual(self.task.held_now(), self.task.held)
        self.task.on_draw()

    def test_no_dot_starts_out_of_sight(self):
        """Every dot has to be seen at least once, when yours flash."""
        from neural_workshop.ui.outofsight import hidden
        self.task.blind_count = 6
        for _deal in range(20):
            self.task.start_run()
            for dot in self.task.dots:
                self.assertFalse(hidden(self.task.blinds, dot.x, dot.y))

    def test_the_dots_you_hold_never_swallow_the_whole_flock(self):
        self.task.dot_count = 4
        self.assertEqual(self.task.clamped_targets(99), 3)
        self.assertEqual(self.task.clamped_targets(0), 1)

    def test_the_flock_stands_still_for_the_cue(self):
        self.task.start_run()
        before = [(dot.x, dot.y) for dot in self.task.dots]
        for _frame in range(30):
            self.task.update(1 / 60.)
        self.assertEqual(self.task.phase, 'cueing')
        self.assertEqual([(dot.x, dot.y) for dot in self.task.dots], before)

    def test_tracking_moves_the_dots_and_keeps_them_inside(self):
        self._to_tracking()
        before = [(dot.x, dot.y) for dot in self.task.dots]
        for _frame in range(600):              # ten seconds of motion
            self.task._move(1 / 60.)
        low_x, high_x, low_y, high_y = self.task._bounds()
        for dot in self.task.dots:
            self.assertTrue(low_x <= dot.x <= high_x)
            self.assertTrue(low_y <= dot.y <= high_y)
        self.assertNotEqual([(dot.x, dot.y) for dot in self.task.dots],
                            before)

    def test_the_questions_leave_nothing_to_count(self):
        """A coin a question, not an even split of the round.

        An even split would pay for counting answers instead of
        holding dots, so the rounds have to come out uneven — while
        still landing on half over a run, or a fixed answer would
        beat the task.
        """
        self.task.rng = random.Random(3)
        self.task.probes_per_round = 6
        rounds = [self.task._probe_schedule() for _round in range(400)]
        for schedule in rounds:
            self.assertEqual(len(schedule), 6)
        self.assertTrue(any(sum(schedule) != 3 for schedule in rounds))
        asked = sum(sum(schedule) for schedule in rounds)
        self.assertAlmostEqual(asked / (400. * 6), 0.5, delta=0.05)

    def test_a_question_asks_about_the_kind_it_scheduled(self):
        self._to_tracking()
        self.task.schedule = [True] * self.task.probes_per_round
        self.assertTrue(self._ask().target)
        self.task.probes_done = 0
        self.task.probe = None
        self.task.verdict = None
        self.task.schedule = [False] * self.task.probes_per_round
        self.assertFalse(self._ask().target)

    def test_a_ringed_dot_is_always_one_you_can_see(self):
        from neural_workshop.ui.outofsight import hidden
        self.task.blind_count = 6
        self.task.probes_per_round = 12
        self._to_tracking()
        for _question in range(self.task.probes_per_round):
            dot = self._ask()
            self.assertFalse(hidden(self.task.blinds, dot.x, dot.y))
            self.task.answer(dot.target)
            self._clear()

    def test_the_ring_prefers_a_dot_whose_name_was_just_in_doubt(self):
        """Risk is dealt by the crossings and the slabs, and neither
        knows which dots are yours, so preferring it leaks nothing."""
        self._to_tracking()
        now = time.time()
        yours = [dot for dot in self.task.dots if dot.target]
        for dot in self.task.dots:
            dot.risky_until = 0.0
        yours[0].risky_until = now + 5.0
        for _draw in range(30):
            self.assertIs(self.task._probeable(True), yours[0])

    def test_the_right_answer_is_a_hit_and_a_wrong_one_is_not(self):
        self._to_tracking()
        dot = self._ask()
        self.task.answer(dot.target)
        self.assertEqual(self.task.hits, 1)
        self.assertIs(self.task.verdict, True)
        self.assertEqual(len(self.task.reaction_times), 1)
        self._clear()
        dot = self._ask()
        self.task.answer(not dot.target)
        self.assertEqual(self.task.wrong, 1)
        self.assertIs(self.task.verdict, False)
        self.task.on_draw()

    def test_a_second_answer_to_one_question_is_ignored(self):
        self._to_tracking()
        dot = self._ask()
        self.task.answer(dot.target)
        self.task.answer(not dot.target)
        self.assertEqual((self.task.hits, self.task.wrong), (1, 0))
        self.assertEqual(self.task.probes_done, 1)

    def test_a_question_left_alone_runs_out(self):
        self._to_tracking()
        self._ask()
        self.task.probe_ends = time.time() - 1
        self.task.update(1 / 60.)
        self.assertEqual(self.task.late, 1)
        self.assertEqual(self.task.hits, 0)
        self.assertEqual(self.task.probes_done, 1)

    def test_an_answer_before_any_question_does_nothing(self):
        self._to_tracking()
        self.task.answer(True)
        self.assertEqual(self.task.score()['asked'], 0)

    def test_a_crossing_puts_two_dots_in_the_same_place(self):
        from neural_workshop.ui.outofsight import rendezvous
        self._to_tracking()
        one, other = self.task.dots[0], self.task.dots[1]
        seconds = rendezvous(one, other, self.task.speed, self.task._aspect())
        closest = 9.0
        for _frame in range(int(seconds * 60) + 30):
            self.task._move(1 / 60.)
            closest = min(closest, math.hypot(
                (one.x - other.x) * state.window.width,
                (one.y - other.y) * state.window.height))
        self.assertLess(closest, self.task.radius() * 0.25)

    def test_a_crossing_marks_both_dots_when_it_happens(self):
        self._to_tracking()
        now = time.time()
        self.task.next_cross = 0.0
        self.task._maybe_cross(now)
        committed = [dot for dot in self.task.dots if dot.busy_until]
        self.assertEqual(len(committed), 2)
        for dot in committed:
            self.assertEqual(dot.risky_until, 0.0)   # not yet — it is ahead
        self.task._mark_risk(committed[0].busy_until + 0.01)
        for dot in committed:
            self.assertEqual(dot.busy_until, 0.0)
            self.assertGreater(dot.risky_until, 0.0)

    def test_a_crossing_is_no_likelier_to_pick_a_dot_of_yours(self):
        """The pair is drawn from the whole flock, so the crossings
        themselves never say which dots are yours."""
        self.task.dot_count = 10
        self.task.start_targets = 3
        self.task.held = 3
        self._to_tracking()
        self.task.rng = random.Random(11)
        drawn = {True: 0, False: 0}
        for _cross in range(600):
            for dot in self.task.dots:
                dot.busy_until = 0.0
            self.task.next_cross = 0.0
            self.task._maybe_cross(time.time())
            for dot in self.task.dots:
                if dot.busy_until:
                    drawn[dot.target] += 1
        share = drawn[True] / float(drawn[True] + drawn[False])
        self.assertAlmostEqual(share, 0.3, delta=0.05)

    def test_turning_the_crossings_off_leaves_the_headings_alone(self):
        self._to_tracking()
        self.task.cross_gap = 0.0
        self.task.next_cross = 0.0
        before = [(dot.vx, dot.vy) for dot in self.task.dots]
        self.task._maybe_cross(time.time())
        self.assertEqual([(dot.vx, dot.vy) for dot in self.task.dots],
                         before)

    def test_turning_the_slabs_off_hides_nothing(self):
        from neural_workshop.ui.outofsight import hidden
        self.task.blind_count = 0
        self._to_tracking()
        self.assertEqual(self.task.blinds, [])
        for _frame in range(600):
            self.task._move(1 / 60.)
            for dot in self.task.dots:
                self.assertFalse(hidden(self.task.blinds, dot.x, dot.y))

    def test_the_slabs_never_pile_up_on_each_other(self):
        self.task.blind_count = 8
        for _deal in range(20):
            self.task._lay_blinds()
            for index, slab in enumerate(self.task.blinds):
                for other in self.task.blinds[index + 1:]:
                    self.assertFalse(slab.overlaps(other))

    def test_a_whole_round_grows_the_flock_and_a_slip_shrinks_it(self):
        self.task.adaptive = True
        self._to_tracking()
        was = self.task.held
        self._answer_the_round()
        self.assertEqual(self.task.phase, 'revealing')
        self.assertEqual(self.task.held, self.task.clamped_targets(was + 1))
        self.assertEqual(self.task.results[-1][1],
                         self.task.results[-1][2])
        self._skip_the_reveal()
        was = self.task.held
        self._answer_the_round(wrong=1)
        self.assertEqual(self.task.held, self.task.clamped_targets(was - 1))
        self.assertLess(self.task.results[-1][2],
                        self.task.results[-1][1])

    def test_the_run_finishes_after_its_rounds(self):
        self._to_tracking()
        for _round in range(2):
            self._answer_the_round()
            self._skip_the_reveal()
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['accuracy'], 100)
        self.assertEqual(self.task.score()['rounds'], 2)
        self.task.on_draw()

    def test_the_tally_adds_up(self):
        self._to_tracking()
        dot = self._ask()
        self.task.answer(dot.target)
        self._clear()
        dot = self._ask()
        self.task.answer(not dot.target)
        self._clear()
        self._ask()
        self.task.probe_ends = time.time() - 1
        self.task.update(1 / 60.)
        tally = self.task.score()
        self.assertEqual((tally['hits'], tally['wrong'], tally['late']),
                         (1, 1, 1))
        self.assertEqual(tally['asked'], 3)
        self.assertEqual(tally['accuracy'], 33)

    def test_a_resize_moves_the_dots_to_the_same_relative_place(self):
        self.task.start_run()                  # the cue holds them still
        dot = self.task.dots[0]
        where = (dot.x, dot.y)
        geometry.set_window_size(900, 700)
        display.relayout()
        self.task.on_draw()
        self.assertEqual((dot.x, dot.y), where)
        self.assertAlmostEqual(dot.circle.x, where[0] * state.window.width,
                               places=3)

    def test_it_draws_in_every_phase(self):
        self.task.on_draw()                    # ready
        self.task.start_run()
        self.task.on_draw()                    # cueing
        self.task.until = time.time() - 1
        self.task.update(1 / 60.)
        self._ask()
        self.task.on_draw()                    # a question is up
        self.task.answer(True)
        self.task.on_draw()                    # its verdict is up
        self.task._finish()
        self.task.on_draw()                    # done

    def test_closing_takes_the_dots_and_the_slabs_with_it(self):
        self._to_tracking()
        self._ask()
        self.task.close()
        self.assertEqual(self.task.dots, [])
        self.assertEqual(self.task.blind_shapes, [])
        self.assertIsNone(self.task.ring)

    def test_it_has_an_options_screen(self):
        from neural_workshop.ui import taskoptions
        self.assertTrue(taskoptions.has_options('out_of_sight'))
        note = taskoptions.OUT_OF_SIGHT.note(
            {'SIGHT_DOTS': 4, 'SIGHT_TARGETS': 10, 'SIGHT_CROSS_MS': 0,
             'SIGHT_BLINDS': 0, 'SIGHT_PROBES': 6,
             'SIGHT_ADAPTIVE': False})
        self.assertIn('3', note)               # the clamp is spelled out
        self.assertIn('no crossings', note)    # and so is the easy field
