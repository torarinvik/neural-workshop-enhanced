#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Every screen state must draw, and every key must reach its handler.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

import pyglet

from uisupport import (MonkeyLadder, NCupMonte, TaskHub, bootstrap, display,
                       end_session, geometry, key, needs_ui, new_session,
                       on_draw, on_key_press, reset_window, state)


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


@needs_ui
class SplashLogoTests(unittest.TestCase):
    """The title logo is sized by the window, never by its own file.

    The artwork is a resource anyone may replace, so a logo of any
    resolution has to land in the gap between the version banner and
    the key list rather than wherever its own pixels reach to.
    """

    #: Shapes a replacement logo could plausibly arrive in, including
    #: the one that used to hang off all four edges.
    SHAPES = ((1254, 1254), (300, 300), (64, 64), (2000, 500), (400, 1600))

    def tearDown(self):
        reset_window()
        bootstrap._load_title_artwork()

    def _room(self):
        """The gap to stay inside, read off the labels that bound it."""
        banner = state.title_message_label.native
        return (state.title_keys_label.keys.y,
                banner.y - banner.content_height // 2)

    def _assert_it_fits(self, note=''):
        logo = state.brain_graphic
        floor, ceiling = self._room()
        self.assertGreater(logo.width, 0, note)
        self.assertGreaterEqual(logo.y, floor, note)
        self.assertLessEqual(logo.y + logo.height, ceiling, note)
        self.assertGreaterEqual(logo.x, 0, note)
        self.assertLessEqual(logo.x + logo.width, state.window.width, note)

    def test_the_shipped_logo_clears_the_banner_and_the_key_list(self):
        self._assert_it_fits()

    def test_it_is_refitted_when_the_window_changes(self):
        drawn = []
        for width, height in ((1024, 768), (640, 480)):
            geometry.set_window_size(width, height)
            display.relayout()
            self._assert_it_fits('%dx%d window' % (width, height))
            drawn.append(state.brain_graphic.width)
        self.assertNotEqual(drawn[0], drawn[1])

    def test_artwork_of_any_shape_lands_in_the_same_room(self):
        paper = pyglet.image.SolidColorImagePattern((0, 0, 0, 255))
        for width, height in self.SHAPES:
            state.brain_graphic = pyglet.sprite.Sprite(
                paper.create_image(width, height))
            bootstrap._place_splash()
            note = '%dx%d artwork' % (width, height)
            self._assert_it_fits(note)
            logo = state.brain_graphic
            self.assertAlmostEqual(logo.width / logo.height, width / height,
                                   places=1, msg=note)

    def test_shrinking_the_logo_puts_it_back_when_it_is_done(self):
        full = state.brain_graphic.width
        bootstrap.scale_brain(0.05)
        self.assertEqual(state.brain_graphic.width, full)

    def test_the_dark_logo_is_ink_and_not_a_white_card(self):
        """On a black screen an opaque logo would be a bright slab."""
        from neural_workshop import resources
        misc = resources.resourcepaths['misc']
        self.assertIn('splash-black', misc)
        for path in misc['splash-black']:
            with open(path, 'rb') as handle:
                image = pyglet.image.load(path, file=handle)
            pixels = image.get_image_data().get_data('RGBA', image.width * 4)
            alphas = pixels[3::16 * 4]
            self.assertGreater(sum(1 for a in alphas if a == 0),
                               len(alphas) // 2, path)
            self.assertGreater(sum(1 for a in alphas if a > 200), 0, path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
