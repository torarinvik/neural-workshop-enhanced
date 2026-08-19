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
    from neural_workshop.session import end_session, new_session
    from neural_workshop.ui.gameselect import GameSelect
    from neural_workshop.ui.menu import AllCycler, Cycler, PercentCycler
    from neural_workshop.ui.screens import (ImageSelect, LanguageScreen,
                                            OptionsScreen, SoundSelect,
                                            UserScreen)
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


@unittest.skipIf(_IMPORT_ERROR is not None,
                 'cannot build application: %s' % (_IMPORT_ERROR,))
class KeyDispatchTests(unittest.TestCase):

    def tearDown(self):
        state.mode.title_screen = False
        state.mode.draw_graph = False
        if state.mode.started:
            end_session(cancelled=True)

    def test_space_leaves_title_screen(self):
        state.mode.title_screen = True
        on_key_press(key.SPACE, 0)
        self.assertFalse(state.mode.title_screen)

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
