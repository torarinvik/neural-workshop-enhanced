#!/usr/bin/env python
"""Smoke tests for the screens the agent-boundary tests never reach.

These build every menu, draw every screen state and push a few keys.
They assert little about appearance — the point is that no screen raises,
which is exactly what a package split is most likely to break.

Run from the project root:

    python tests/test_ui_smoke.py
"""
from __future__ import annotations

import os
import sys
import unittest
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('NW_HEADLESS', '1')
os.environ.setdefault('NW_TICK_MS', '1')
os.environ.setdefault('NW_TRIAL_MS', '10')

warnings.filterwarnings('ignore', category=ResourceWarning)

try:
    from pyglet.window import key

    from neural_workshop import bootstrap, state
    from neural_workshop.events import on_draw, on_key_press
    from neural_workshop.grid import (current_active_position_ids,
                                      current_cell_count, current_3d_color_count,
                                      decode_3d_colors, decode_3d_pattern)
    from neural_workshop.session import end_session, new_session
    from neural_workshop.ui.gameselect import GameSelect
    from neural_workshop.ui.menu import AllCycler, Cycler, PercentCycler
    from neural_workshop.ui.monkeyladder import MonkeyLadder
    from neural_workshop.ui.ncupmonte import NCupMonte
    from neural_workshop.ui.screens import (ImageSelect, LanguageScreen,
                                            OptionsScreen, SoundSelect,
                                            UserScreen)
    from neural_workshop.ui.taskhub import TASKS, TaskHub, tasks_for
    from neural_workshop.ui import taskoptions
    from neural_workshop.ui.menu import Menu
    bootstrap.build_application()
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - no GL context available
    _IMPORT_ERROR = exc


@unittest.skipIf(_IMPORT_ERROR is not None,
                 'cannot build application: %s' % (_IMPORT_ERROR,))
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


@unittest.skipIf(_IMPORT_ERROR is not None,
                 'cannot build application: %s' % (_IMPORT_ERROR,))
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


@unittest.skipIf(_IMPORT_ERROR is not None,
                 'cannot build application: %s' % (_IMPORT_ERROR,))
class ScreenDrawTests(unittest.TestCase):
    """Each top-level screen state must draw."""

    def tearDown(self):
        if TaskHub.instance:
            TaskHub.instance.close()
        if MonkeyLadder.instance:
            MonkeyLadder.instance.close()
        if NCupMonte.instance:
            NCupMonte.instance.close()
        state.mode.title_screen = False
        state.mode.draw_graph = False
        state.mode.saccadic = False
        if state.mode.started:
            end_session(cancelled=True)

    def test_title_screen_draws(self):
        state.mode.title_screen = True
        on_draw()

    def test_hub_draws(self):
        state.mode.title_screen = False
        on_draw()

    def test_monkey_ladder_round(self):
        game = MonkeyLadder()
        try:
            game.start_round()
            game.phase = 'input'
            first = game.sequence[0]
            game.click_cell(first)
            self.assertEqual(game.next_index, 1)
            game.on_draw()
        finally:
            game.close()

    def test_ncup_monte_guess(self):
        game = NCupMonte()
        try:
            game.skip_to_guess()
            game.choose_cup(game.ball)
            self.assertEqual(game.phase, 'result')
            self.assertGreaterEqual(game.cups, 3)
            game.on_draw()
        finally:
            game.close()

    def test_graph_draws(self):
        state.graph.parse_stats()
        state.graph.graph = state.mode.mode
        state.mode.draw_graph = True
        on_draw()

    def test_graph_cycles_modes_and_styles(self):
        state.graph.parse_stats()
        for _ in range(3):
            state.graph.next_mode()
        state.graph.next_style()

    def test_saccadic_draws(self):
        state.saccadic.start()
        try:
            on_draw()
            state.saccadic.tick(0.5)
            on_draw()
        finally:
            state.saccadic.stop()

    def test_session_draws(self):
        new_session()
        try:
            on_draw()
        finally:
            end_session(cancelled=True)

    def test_3d_cube_mode_session_draws(self):
        prev_3d = state.cfg.GRID_3D
        state.cfg.GRID_3D = True
        state.field.rebuild_grid()
        try:
            new_session()
            state.visuals[0].spawn(position=1, color=1)
            self.assertTrue(state.visuals[0].visible)
            self.assertGreaterEqual(len(state.visuals[0].poly_3d), 18)
            self.assertTrue(state.field.v_lines)
            blue = [s.color[:3] for s in state.visuals[0].poly_3d
                    if hasattr(s, 'color') and s.color[2] > s.color[0] + 40]
            state.visuals[0].hide()
            state.visuals[0].spawn(position=1, color=6)
            red = [s.color[:3] for s in state.visuals[0].poly_3d
                   if hasattr(s, 'color') and s.color[0] > s.color[2] + 40]
            self.assertTrue(blue)
            self.assertTrue(red)
            state.visuals[0].hide()
            state.visuals[0].spawn(position=0, color=8)
            washed = [s.color[:3] for s in state.visuals[0].poly_3d
                      if hasattr(s, 'color') and s.color[0] > 180
                      and s.color[1] > 160]
            self.assertTrue(washed)
            on_draw()
        finally:
            end_session(cancelled=True)
            state.cfg.GRID_3D = prev_3d
            state.field.rebuild_grid()


@unittest.skipIf(_IMPORT_ERROR is not None,
                 'cannot build application: %s' % (_IMPORT_ERROR,))
class KeyDispatchTests(unittest.TestCase):

    def tearDown(self):
        if TaskHub.instance:
            TaskHub.instance.close()
        if MonkeyLadder.instance:
            MonkeyLadder.instance.close()
        if NCupMonte.instance:
            NCupMonte.instance.close()
        state.mode.title_screen = False
        state.mode.draw_graph = False
        if state.mode.started:
            end_session(cancelled=True)

    def test_space_leaves_title_screen(self):
        state.mode.title_screen = True
        on_key_press(key.SPACE, 0)
        self.assertFalse(state.mode.title_screen)
        self.assertIsNotNone(TaskHub.instance)

    def test_g_opens_and_closes_the_graph(self):
        state.mode.title_screen = False
        on_key_press(key.G, 0)
        self.assertTrue(state.mode.draw_graph)
        on_key_press(key.G, 0)
        self.assertFalse(state.mode.draw_graph)

    def test_pause_toggles_during_a_session(self):
        new_session()
        try:
            on_key_press(key.P, 0)
            self.assertTrue(state.mode.paused)
            on_key_press(key.P, 0)
            self.assertFalse(state.mode.paused)
        finally:
            end_session(cancelled=True)

    def test_hide_text_toggles_during_a_session(self):
        new_session()
        try:
            before = state.mode.hide_text
            on_key_press(key.F8, 0)
            self.assertNotEqual(before, state.mode.hide_text)
            on_key_press(key.F8, 0)
            self.assertEqual(before, state.mode.hide_text)
        finally:
            end_session(cancelled=True)

    def test_unbound_key_is_harmless(self):
        state.mode.title_screen = False
        on_key_press(key.Z, 0)


@unittest.skipIf(_IMPORT_ERROR is not None,
                 'cannot build application: %s' % (_IMPORT_ERROR,))
class TaskOptionsTests(unittest.TestCase):
    """Every task owns a settings screen, opened with C."""

    def setUp(self):
        self.saved = {option.key: state.cfg[option.key]
                      for spec in taskoptions.TASK_SPECS.values()
                      for option in spec.options}

    def tearDown(self):
        for screen in (Menu.instance, TaskHub.instance,
                       MonkeyLadder.instance, NCupMonte.instance):
            if screen is not None:
                screen.close()
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
