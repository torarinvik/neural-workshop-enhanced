#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Every menu screen must build, render, cycle its values and close.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import (AllCycler, Cycler, GameSelect, ImageSelect,
                       LanguageScreen, OptionsScreen, PercentCycler,
                       SoundSelect, TASKS, TaskHub, UserScreen,
                       close_overlays, current_3d_color_count,
                       current_active_position_ids, current_cell_count,
                       decode_3d_colors, decode_3d_pattern, key, needs_ui,
                       state, tasks_for)


@needs_ui
class MenuTests(unittest.TestCase):
    """Every menu must build, render and close without raising."""

    def _exercise(self, menu):
        menu.update_labels()
        menu.on_draw()
        menu.move_selection(1)
        menu.move_selection(-1)
        menu.select()
        menu.close()

    def test_game_select(self):
        menu = GameSelect()
        self.assertTrue(menu.newmode)
        self._exercise(menu)

    def test_task_hub_switches_categories(self):
        hub = TaskHub()
        try:
            self.assertEqual([task[0] for task in tasks_for('working_memory')],
                             ['nback', 'monkey_ladder'])
            self.assertEqual(
                [task for task, _name in TASKS['long_term_memory']],
                ['concentration', 'recognition'])
            self.assertEqual([task[0] for task in tasks_for('attention')],
                             ['reflex', 'ncup_monte', 'moving_targets'])
            hub.set_category('attention')
            self.assertEqual(hub.category, 'attention')
            self.assertEqual(len(hub.task_rects), 3)
            hub.set_category('long_term_memory')
            self.assertEqual(hub.category, 'long_term_memory')
            self.assertEqual(len(hub.task_rects), 2)
            self.assertEqual(hub.empty.text, '')
            hub.on_draw()
        finally:
            hub.close()

    def test_the_hub_says_so_when_a_category_is_empty(self):
        TASKS['_empty_for_test'] = []
        hub = TaskHub()
        try:
            hub.set_category('_empty_for_test')
            self.assertEqual(hub.empty.text, 'No tasks in this category yet.')
            self.assertEqual(hub.task_rects, [])
            hub.on_draw()
        finally:
            hub.close()
            del TASKS['_empty_for_test']

    def test_task_hub_launches_nback(self):
        hub = TaskHub()
        hub.launch('nback')
        self.assertIsNone(TaskHub.instance)
        self.assertFalse(state.mode.title_screen)

    def test_3d_game_select_toggle(self):
        menu = GameSelect()
        try:
            menu.values['grid_3d'] = True
            menu.values['grid_3d_cubes'].choose(3)
            menu.update_labels()
            self.assertTrue(menu.modelabel.text.startswith('3D '))
            menu.save()
            self.assertTrue(state.cfg.GRID_3D)
            self.assertEqual(state.cfg.GRID_3D_CUBES, 3)
            self.assertEqual(current_cell_count(), 216)
            self.assertEqual(len(current_active_position_ids()), 216)
            self.assertEqual(decode_3d_pattern(122, 3), [1, 2, 3])
            self.assertEqual(decode_3d_colors(1, 2), [1, 1])
            self.assertEqual(decode_3d_colors(2, 2), [2, 1])
            self.assertEqual(decode_3d_colors(9, 2), [1, 2])
            self.assertEqual(current_3d_color_count(), 8 ** 3)
        finally:
            menu.values['grid_3d'] = False
            menu.values['grid_3d_cubes'].choose(1)
            menu.save()
            menu.close()

    def test_image_select(self):
        self._exercise(ImageSelect())

    def test_sound_select(self):
        self._exercise(SoundSelect())

    def test_user_screen(self):
        menu = UserScreen()
        menu.update_labels()
        menu.on_draw()
        menu.close()

    def test_language_screen(self):
        menu = LanguageScreen()
        menu.update_labels()
        menu.close()

    def test_options_screen(self):
        menu = OptionsScreen()
        menu.update_labels()
        menu.close()

    def test_arrow_keys_cycle_a_value_both_ways(self):
        from neural_workshop.ui import taskoptions
        menu = taskoptions.open_task_options('matrix_reasoning')
        try:
            cyclers = [k for k, v in menu.values.items()
                       if isinstance(v, Cycler) and len(v.values) > 2]
            self.assertTrue(cyclers)
            k = cyclers[0]
            menu.move_selection(menu.options.index(k), relative=False)
            before = menu.values[k].value()
            menu.on_text_motion(key.MOTION_RIGHT)
            forward = menu.values[k].value()
            self.assertNotEqual(forward, before)
            menu.on_text_motion(key.MOTION_LEFT)
            self.assertEqual(menu.values[k].value(), before)
            menu.on_text_motion(key.MOTION_LEFT)
            backward = menu.values[k].value()
            self.assertNotEqual(backward, before)
            self.assertNotEqual(backward, forward)
        finally:
            menu.close()

    def test_arrow_keys_toggle_a_boolean(self):
        menu = GameSelect()
        try:
            menu.move_selection(menu.options.index('selfpaced'),
                                relative=False)
            before = menu.values['selfpaced']
            menu.on_text_motion(key.MOTION_LEFT)
            self.assertEqual(menu.values['selfpaced'], not before)
            menu.on_text_motion(key.MOTION_RIGHT)
            self.assertEqual(menu.values['selfpaced'], before)
        finally:
            menu.close()

    def test_arrow_keys_leave_command_rows_alone(self):
        menu = UserScreen()
        try:
            menu.on_text_motion(key.MOTION_LEFT)
            menu.on_text_motion(key.MOTION_RIGHT)
            self.assertFalse(menu.closed)
        finally:
            menu.close()

    def test_game_select_resolves_every_base_mode(self):
        """Ticking a mode's own modalities must resolve back to that mode."""
        menu = GameSelect()
        try:
            for mode_number in (2, 3, 10, 11, 20, 21, 28):
                modalities = state.mode.modalities[mode_number]
                for option in ('position1', 'color', 'image', 'audio',
                               'audio2', 'arithmetic'):
                    menu.values[option] = option in modalities
                menu.values['combination'] = False
                menu.values['crab'] = False
                menu.values['selfpaced'] = False
                menu.values['multi'].i = 0
                menu.calc_mode()
                self.assertEqual(menu.newmode, mode_number)
        finally:
            menu.close()


@needs_ui
class CyclerTests(unittest.TestCase):

    def test_cycler_wraps(self):
        cycler = Cycler([1, 2, 3])
        self.assertEqual(cycler.value(), 1)
        self.assertEqual(cycler.nxt(), 2)
        cycler.nxt()
        self.assertEqual(cycler.nxt(), 1)

    def test_cycler_steps_backward_and_wraps(self):
        cycler = Cycler([1, 2, 3])
        self.assertEqual(cycler.prv(), 3)
        self.assertEqual(cycler.prv(), 2)
        self.assertEqual(cycler.prv(), 1)

    def test_cycler_choose(self):
        cycler = Cycler(['a', 'b'])
        cycler.choose('b')
        self.assertEqual(cycler.value(), 'b')
        cycler.choose('missing')
        self.assertEqual(cycler.value(), 'b')

    def test_percent_and_all_formatting(self):
        self.assertEqual(str(PercentCycler([0.5])), '50.0%')
        self.assertEqual(str(AllCycler([0])), 'all')
        self.assertEqual(str(AllCycler([4])), '4')


@needs_ui
class HubArrowKeyTests(unittest.TestCase):
    """One press of an arrow moves the selection exactly one place.

    pyglet dispatches ``on_key_press`` *and* ``on_text_motion`` for a
    single arrow press, so these drive both — testing either alone
    would pass while the hub moved two categories per press, which is
    the bug that hid behind three categories evenly dividing into two.
    """

    def setUp(self):
        close_overlays()
        self.hub = TaskHub(category='working_memory')

    def tearDown(self):
        close_overlays()

    def _press(self, symbol, motion):
        """One arrow key press, as the window really delivers it."""
        self.hub.on_key_press(symbol, 0)
        self.hub.on_text_motion(motion)

    def _ids(self):
        from neural_workshop.ui.taskhub import CATEGORIES
        return [cat for cat, _name in CATEGORIES]

    def test_right_moves_one_category(self):
        ids = self._ids()
        for expected in ids[1:]:
            self._press(key.RIGHT, key.MOTION_RIGHT)
            self.assertEqual(self.hub.category, expected)

    def test_left_moves_one_category(self):
        ids = self._ids()
        for expected in list(reversed(ids))[:-1]:
            self._press(key.LEFT, key.MOTION_LEFT)
            self.assertEqual(self.hub.category, expected)

    def test_right_all_the_way_round_returns_home(self):
        ids = self._ids()
        for _ in range(len(ids)):
            self._press(key.RIGHT, key.MOTION_RIGHT)
        self.assertEqual(self.hub.category, ids[0])

    def test_right_then_left_is_where_it_started(self):
        for start in self._ids():
            self.hub.set_category(start)
            self._press(key.RIGHT, key.MOTION_RIGHT)
            self._press(key.LEFT, key.MOTION_LEFT)
            self.assertEqual(self.hub.category, start)

    def test_every_category_is_reachable_by_arrow(self):
        seen = {self.hub.category}
        for _ in range(len(self._ids())):
            self._press(key.RIGHT, key.MOTION_RIGHT)
            seen.add(self.hub.category)
        self.assertEqual(seen, set(self._ids()))

    def test_up_and_down_move_one_task(self):
        self.hub.set_category('working_memory')
        tasks = tasks_for('working_memory')
        self.assertGreater(len(tasks), 1)
        self.assertEqual(self.hub.selected, 0)
        self._press(key.DOWN, key.MOTION_DOWN)
        self.assertEqual(self.hub.selected, 1)
        self._press(key.UP, key.MOTION_UP)
        self.assertEqual(self.hub.selected, 0)

    def test_only_one_handler_acts_on_the_arrows(self):
        # Belt and braces: the key handler alone must not move anything.
        before = self.hub.category
        self.hub.on_key_press(key.RIGHT, 0)
        self.hub.on_key_press(key.LEFT, 0)
        self.assertEqual(self.hub.category, before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
