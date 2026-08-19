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
                       current_3d_color_count, current_active_position_ids,
                       current_cell_count, decode_3d_colors,
                       decode_3d_pattern, needs_ui, state, tasks_for)


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
            self.assertEqual(TASKS['long_term_memory'], [])
            self.assertEqual([task[0] for task in tasks_for('misc')],
                             ['ncup_monte'])
            hub.set_category('misc')
            self.assertEqual(hub.category, 'misc')
            self.assertEqual(len(hub.task_rects), 1)
            hub.set_category('long_term_memory')
            self.assertEqual(hub.empty.text, 'No tasks in this category yet.')
            hub.on_draw()
        finally:
            hub.close()

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
