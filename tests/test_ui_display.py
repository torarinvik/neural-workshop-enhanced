#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Re-laying the game out when the window changes size.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import (MonkeyLadder, NCupMonte, TaskHub, close_overlays,
                       display, end_session, geometry, key, needs_ui,
                       new_session, on_draw, on_key_press, reset_window, state,
                       taskoptions, trial_advance_significant)


@needs_ui
class RelayoutTests(unittest.TestCase):
    """Changing the window size rebuilds every widget in place.

    Real fullscreen needs a display server, so these resize the window
    instead — the code path a fullscreen toggle takes is the same.
    """

    #: Logical window sizes. ``window.width`` reports backing-store
    #: pixels, which on a scaled display is not what set_size takes.
    SIZES = ((1024, 768), (912, 684))

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        if state.mode.started:
            end_session(cancelled=True)
        reset_window()

    def _resize(self, width, height):
        geometry.set_window_size(width, height)
        display.relayout()

    def test_widgets_follow_the_window(self):
        centres = []
        for width, height in self.SIZES:
            self._resize(width, height)
            centres.append((state.field.center_x, state.field.center_y,
                            state.field.size))
            on_draw()
        self.assertNotEqual(centres[0], centres[1])

    def test_relayout_keeps_the_game_state(self):
        mode = state.mode
        before = (mode.mode, mode.back, mode.num_trials, id(mode), id(state.stats))
        self._resize(*self.SIZES[0])
        after = (mode.mode, mode.back, mode.num_trials, id(state.mode),
                 id(state.stats))
        self.assertEqual(before, after)

    def test_relayout_mid_trial_keeps_the_stimulus_on_screen(self):
        state.mode.title_screen = False
        new_session()
        try:
            trial_advance_significant()
            self.assertEqual(state.mode.phase, 'stimulus')
            stim = dict(state.mode.current_stim)
            trial = state.mode.trial_number
            visible = [visual.visible for visual in state.visuals]
            self._resize(*self.SIZES[0])
            self.assertEqual(dict(state.mode.current_stim), stim)
            self.assertEqual(state.mode.trial_number, trial)
            self.assertEqual([v.visible for v in state.visuals], visible)
        finally:
            end_session(cancelled=True)

    def test_open_overlays_are_listed_while_open_only(self):
        self.assertEqual(display.open_overlays(), [])
        hub = TaskHub()
        self.assertEqual([type(o).__name__ for o in display.open_overlays()],
                         ['TaskHub'])
        hub.close()
        self.assertEqual(display.open_overlays(), [])

    def test_overlays_relayout_with_the_window(self):
        hub = TaskHub()
        task = MonkeyLadder()
        task.start_round()
        sequence = list(task.sequence)
        menu = taskoptions.open_task_options('monkey_ladder')
        self.assertEqual(len(display.open_overlays()), 3)

        before = (hub.title.y, task.cell, menu.title.y)
        self._resize(*self.SIZES[0])
        self.assertNotEqual(before, (hub.title.y, task.cell, menu.title.y))
        # A re-layout must not disturb the round in progress.
        self.assertEqual(task.sequence, sequence)
        for overlay in (hub, task, menu):
            overlay.on_draw()

    def test_cup_order_survives_a_relayout(self):
        task = NCupMonte()
        task.start_round()
        task._plan_swaps()
        task._begin_swap()
        order = list(task.order)
        self._resize(*self.SIZES[0])
        self.assertEqual(task.order, order)
        self.assertEqual(len(task.xs), task.cups)

    def test_f11_is_bound_on_every_screen(self):
        calls = []
        original = display.toggle_fullscreen
        display.toggle_fullscreen = lambda: calls.append(True)
        try:
            state.mode.title_screen = True
            on_key_press(key.F11, 0)
            state.mode.title_screen = False
            on_key_press(key.F11, 0)
            self.assertEqual(len(calls), 2)

            hub = TaskHub()
            hub.on_key_press(key.F11, 0)
            task = MonkeyLadder()
            task.on_key_press(key.F11, 0)
            menu = taskoptions.open_task_options('monkey_ladder')
            menu.on_key_press(key.F11, 0)
            self.assertEqual(len(calls), 5)
        finally:
            display.toggle_fullscreen = original

    def test_toggle_is_a_no_op_when_the_state_already_matches(self):
        self.assertFalse(display.is_fullscreen())
        self.assertFalse(display.set_fullscreen(False))


if __name__ == '__main__':
    unittest.main(verbosity=2)
