#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Every screen state must draw, and every key must reach its handler.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import (MonkeyLadder, NCupMonte, TaskHub, end_session, key,
                       needs_ui, new_session, on_draw, on_key_press, state)


@needs_ui
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


@needs_ui
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
