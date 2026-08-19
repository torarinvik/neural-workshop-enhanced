#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The per-task options screens and the hand cursor they share.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

import pyglet

from uisupport import (GameSelect, Menu, MonkeyLadder, NCupMonte, TASKS,
                       TaskHub, close_overlays, cursor, key, needs_ui,
                       scale_to_height, state, taskoptions)


@needs_ui
class TaskOptionsTests(unittest.TestCase):
    """Every task owns a settings screen, opened with C."""

    def setUp(self):
        self.saved = {option.key: state.cfg[option.key]
                      for spec in taskoptions.TASK_SPECS.values()
                      for option in spec.options}

    def tearDown(self):
        close_overlays()
        state.cfg.update(self.saved)

    def test_every_hub_task_has_options(self):
        for tasks in TASKS.values():
            for task_id, _name in tasks:
                self.assertTrue(taskoptions.has_options(task_id), task_id)

    def test_specs_build_render_and_close(self):
        for task_id, spec in taskoptions.TASK_SPECS.items():
            menu = taskoptions.open_task_options(task_id)
            self.assertIsNotNone(menu, task_id)
            self.assertEqual(menu.title.text, spec.title)
            self.assertEqual(len(menu.options), len(spec.options))
            menu.on_draw()
            menu.move_selection(1)
            menu.select()
            menu.close()

    def test_settings_survive_a_junk_config(self):
        for spec in taskoptions.TASK_SPECS.values():
            for option in spec.options:
                state.cfg[option.key] = object()
            values = taskoptions.settings(spec)
            for option in spec.options:
                if option.values is None:
                    self.assertIsInstance(values[option.key], bool)
                else:
                    self.assertIn(values[option.key], option.values)

    def test_enter_applies_and_escape_does_not(self):
        state.cfg.MONKEY_LADDER_GRID = 5
        menu = taskoptions.open_task_options('monkey_ladder')
        menu.values['MONKEY_LADDER_GRID'].choose(7)
        menu.on_key_press(key.ESCAPE, 0)
        self.assertEqual(state.cfg.MONKEY_LADDER_GRID, 5)

        menu = taskoptions.open_task_options('monkey_ladder')
        menu.values['MONKEY_LADDER_GRID'].choose(7)
        menu.on_key_press(key.RETURN, 0)
        self.assertEqual(state.cfg.MONKEY_LADDER_GRID, 7)

    def test_monkey_ladder_c_opens_and_applies(self):
        task = MonkeyLadder()
        task.on_key_press(key.C, 0)
        menu = Menu.instance
        self.assertIsInstance(menu, taskoptions.TaskOptions)
        menu.values['MONKEY_LADDER_GRID'].choose(6)
        menu.values['MONKEY_LADDER_START_LENGTH'].choose(5)
        menu.on_key_press(key.RETURN, 0)
        self.assertEqual(task.grid, 6)
        self.assertEqual(task.level, 5)
        self.assertEqual(task.phase, 'ready')
        task.start_round()
        self.assertEqual(len(task.sequence), 5)

    def test_monkey_ladder_can_stop_adapting(self):
        task = MonkeyLadder()
        task.on_key_press(key.C, 0)
        menu = Menu.instance
        menu.values['MONKEY_LADDER_ADAPTIVE'] = False
        menu.on_key_press(key.RETURN, 0)
        self.assertFalse(task.adaptive)
        task.start_round()
        before = task.level
        task.click_cell(task.sequence[0])
        cells = ((r, c) for r in range(task.grid) for c in range(task.grid))
        task.click_cell(next(c for c in cells if c not in task.sequence))
        self.assertEqual(task.level, before)

    def test_ncup_monte_c_opens_and_applies(self):
        task = NCupMonte()
        task.on_key_press(key.C, 0)
        menu = Menu.instance
        self.assertIsInstance(menu, taskoptions.TaskOptions)
        menu.values['NCUP_MONTE_START_CUPS'].choose(5)
        menu.values['NCUP_MONTE_SWAPS'].choose(2)
        menu.on_key_press(key.RETURN, 0)
        self.assertEqual(task.cups, 5)
        task.start_round()
        task._plan_swaps()
        self.assertEqual(len(task.swaps), 2 + task.cups)
        task.skip_to_guess()
        task.choose_cup(0)

    def test_ncup_monte_max_cups_caps_growth(self):
        task = NCupMonte()
        task.on_key_press(key.C, 0)
        menu = Menu.instance
        menu.values['NCUP_MONTE_START_CUPS'].choose(4)
        menu.values['NCUP_MONTE_MAX_CUPS'].choose(4)
        menu.on_key_press(key.RETURN, 0)
        self.assertEqual(task.cups, 4)
        task.start_round()
        task.skip_to_guess()
        task.choose_cup(task.ball)
        self.assertEqual(task.cups, 4)

    def test_hub_c_opens_the_highlighted_task(self):
        hub = TaskHub(category='misc')
        self.assertEqual(hub.selected_task(), 'ncup_monte')
        hub.on_key_press(key.C, 0)
        self.assertIsInstance(Menu.instance, taskoptions.TaskOptions)
        self.assertEqual(Menu.instance.title.text,
                         taskoptions.NCUP_MONTE.title)
        Menu.instance.on_key_press(key.ESCAPE, 0)

    def test_hub_c_on_nback_opens_game_select(self):
        hub = TaskHub(category='working_memory')
        self.assertEqual(hub.selected_task(), 'nback')
        hub.on_key_press(key.C, 0)
        self.assertIsInstance(Menu.instance, GameSelect)
        Menu.instance.on_key_press(key.ESCAPE, 0)

    def test_hub_c_in_an_empty_category_is_harmless(self):
        hub = TaskHub(category='long_term_memory')
        self.assertIsNone(hub.selected_task())
        hub.on_key_press(key.C, 0)


@needs_ui
class HandCursorTests(unittest.TestCase):
    """The mouse-driven screens wear the hand from res/misc/cursor."""

    def setUp(self):
        cursor.reset()

    def tearDown(self):
        close_overlays()
        cursor.reset()
        state.window.set_mouse_cursor(None)

    def test_cursor_builds_at_the_window_size(self):
        hand = cursor.hand_cursor()
        self.assertIsNotNone(hand)
        expected = max(8, scale_to_height(cursor.CURSOR_HEIGHT))
        self.assertEqual(hand.texture.height, expected)
        self.assertGreater(hand.texture.width, 0)

    def test_hot_spot_sits_on_the_fingertip(self):
        hand = cursor.hand_cursor()
        # The tip is the topmost artwork, so the hot spot is at the top
        # edge and somewhere across the middle of the image.
        self.assertEqual(hand.hot_y, hand.texture.height)
        self.assertGreater(hand.hot_x, 0)
        self.assertLess(hand.hot_x, hand.texture.width)

    def test_cursor_is_cached_until_the_size_changes(self):
        first = cursor.hand_cursor()
        self.assertIs(cursor.hand_cursor(), first)
        cursor.reset()
        self.assertIsNot(cursor.hand_cursor(), first)

    def test_mouse_tasks_take_and_give_back_the_cursor(self):
        for task_class in (MonkeyLadder, NCupMonte):
            task = task_class()
            self.assertEqual(cursor.holders(), 1, task_class.__name__)
            self.assertIsInstance(state.window._mouse_cursor,
                                  pyglet.window.ImageMouseCursor)
            task.close()
            self.assertEqual(cursor.holders(), 0, task_class.__name__)
            self.assertNotIsInstance(state.window._mouse_cursor,
                                     pyglet.window.ImageMouseCursor)

    def test_nesting_keeps_the_hand_until_the_last_screen_closes(self):
        hub = TaskHub()
        task = MonkeyLadder()
        self.assertEqual(cursor.holders(), 2)
        task.close()
        self.assertEqual(cursor.holders(), 1)
        self.assertIsInstance(state.window._mouse_cursor,
                              pyglet.window.ImageMouseCursor)
        hub.close()
        self.assertEqual(cursor.holders(), 0)
        self.assertNotIsInstance(state.window._mouse_cursor,
                                 pyglet.window.ImageMouseCursor)

    def test_missing_artwork_falls_back_to_the_system_cursor(self):
        from neural_workshop import resources
        saved = resources.resourcepaths['misc'].pop('cursor')
        try:
            cursor.reset()
            self.assertIsNone(cursor.hand_cursor())
            task = MonkeyLadder()
            self.assertNotIsInstance(state.window._mouse_cursor,
                                     pyglet.window.ImageMouseCursor)
            task.close()
        finally:
            resources.resourcepaths['misc']['cursor'] = saved
            cursor.reset()


if __name__ == '__main__':
    unittest.main(verbosity=2)
