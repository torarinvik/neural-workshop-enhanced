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

    def test_reflex_and_the_cups_are_in_it(self):
        self.assertEqual([task for task, _name in TASKS['attention']],
                         ['reflex', 'ncup_monte'])

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
