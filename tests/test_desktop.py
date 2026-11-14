#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Desktop: the widget grammars, the window manager, par, the boundary.

Each widget is held to doing what it looks like it does when clicked,
and to doing nothing for a click that misses it. The window manager is
held to the rules a real one keeps: only what is on top takes a click,
a click raises its window, a menu or a list or a dialog swallows the
click that dismisses it, Cancel throws a dialog's changes away and a
window with Apply keeps its changes pending. Every click costs one.
The reference is held to solving every desktop, and to being beatable
by a player who plans the order of the work. The boundary is held to
paying the reference's own clicks through the fourteen ports.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import desktop as D


def centre(rect):
    x, y, w, h = rect
    return x + w / 2, y + h / 2


def find(desk, kind, **where):
    """The first control of *kind* on a window tab or in a dialog."""
    for control in desk.controls:
        if control.kind != kind:
            continue
        if where.get('dialog') is not None and \
                (control.dialog is None) != (not where['dialog']):
            continue
        return control
    raise AssertionError('no %s' % kind)


class TheLadder(unittest.TestCase):

    def test_every_rung_has_at_least_what_the_last_had(self):
        last = D.grade(1)
        for rung in range(2, 80):
            level = D.grade(rung)
            for field in ('windows', 'tabs', 'per_tab', 'dialogs',
                          'depends', 'applies', 'goals'):
                self.assertGreaterEqual(getattr(level, field),
                                        getattr(last, field), (rung, field))
            self.assertTrue(set(last.kinds) <= set(level.kinds))
            self.assertLessEqual(level.factor, last.factor)
            last = level

    def test_the_parts_arrive_where_the_readme_says(self):
        first = {}
        for rung in range(1, 40):
            level = D.grade(rung)
            for name, there in (('tabs', level.tabs > 1),
                                ('scroll', level.rows < level.per_tab),
                                ('dialogs', level.dialogs > 0),
                                ('windows', level.windows > 1),
                                ('depends', level.depends > 0),
                                ('applies', level.applies > 0),
                                ('dropdown', 'dropdown' in level.kinds)):
                if there and name not in first:
                    first[name] = rung
        self.assertEqual(first, {'dropdown': 4, 'tabs': 5, 'scroll': 6,
                                 'dialogs': 8, 'windows': 11, 'depends': 15,
                                 'applies': 16})

    def test_past_twenty_par_is_below_the_reference(self):
        self.assertGreaterEqual(D.grade(20).factor, 1.0)
        self.assertLess(D.grade(21).factor, 1.0)


class TheScreen(unittest.TestCase):
    """Layout facts every rung must keep."""

    def test_windows_stay_on_screen_and_every_title_bar_shows(self):
        for rung in range(1, 50, 2):
            for seed in range(3):
                desk = D.Desktop(D.deal(rung, seed=seed))
                for win in desk.windows:
                    self.assertLessEqual(win.x + win.w, D.SCREEN_W)
                    self.assertLessEqual(win.y + win.h,
                                         D.SCREEN_H - D.TASKBAR_H)
                    self.assertIsNotNone(
                        desk.reachable(D.title_rect(win), win),
                        (rung, seed, win.title))

    def test_names_are_unique_within_a_window(self):
        desk = D.Desktop(D.deal(30, seed=2))
        for win in desk.windows:
            names = [c.label for c in desk.controls if c.window is win]
            self.assertEqual(len(names), len(set(names)))

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(D.deal(14, seed=3), D.deal(14, seed=3))
        self.assertNotEqual(D.deal(14, seed=3), D.deal(14, seed=4))

    def test_every_goal_starts_unmet(self):
        for seed in range(10):
            desk = D.Desktop(D.deal(18, seed=seed))
            self.assertFalse(any(desk.met(g) for g in desk.goals))


class TheWidgets(unittest.TestCase):

    def desk(self, rung=4, seed=0):
        return D.Desktop(D.deal(rung, seed=seed))

    def click_part(self, desk, control, index):
        rect = desk.control_rect(control)
        desk.click(*centre(D.parts(control, rect)[index]))

    def test_a_switch_flips(self):
        desk = self.desk(1)
        switch = desk.controls[0]
        before = switch.value
        self.click_part(desk, switch, 0)
        self.assertEqual(switch.value, 1 - before)
        self.click_part(desk, switch, 0)
        self.assertEqual(switch.value, before)

    def test_choices_and_sliders_take_the_one_clicked(self):
        for seed in range(30):
            desk = self.desk(3, seed)
            for control in desk.controls:
                if control.kind in ('choice', 'slider'):
                    self.click_part(desk, control, control.count - 1)
                    self.assertEqual(control.value, control.count - 1)
                    self.click_part(desk, control, 0)
                    self.assertEqual(control.value, 0)
                    return
        self.fail('no choice or slider dealt')

    def test_a_dropdown_opens_then_takes_the_item(self):
        for seed in range(40):
            desk = self.desk(4, seed)
            menu = [c for c in desk.controls if c.kind == 'dropdown']
            if not menu:
                continue
            control = menu[0]
            self.click_part(desk, control, 0)
            self.assertIs(desk.dropdown, control)
            items = D.dropdown_items(desk.control_rect(control), control)
            wanted = (control.value + 1) % control.count
            desk.click(*centre(items[wanted]))
            self.assertIsNone(desk.dropdown)
            self.assertEqual(control.value, wanted)
            self.assertEqual(desk.clicks, 2)
            return
        self.fail('no dropdown dealt')

    def test_a_click_away_closes_a_list_and_does_nothing_else(self):
        for seed in range(40):
            desk = self.desk(4, seed)
            menu = [c for c in desk.controls if c.kind == 'dropdown']
            if not menu:
                continue
            control = menu[0]
            others = [c for c in desk.controls if c is not control]
            values = [c.value for c in desk.controls]
            self.click_part(desk, control, 0)
            # Where another control is: the list is dismissed, not it.
            target = others[0]
            if desk.overlay_at(*centre(desk.control_rect(target))):
                continue
            desk.click(*centre(desk.control_rect(target)))
            self.assertIsNone(desk.dropdown)
            self.assertEqual([c.value for c in desk.controls], values)
            return
        self.fail('no usable dropdown dealt')

    def test_every_click_costs_one_even_on_nothing(self):
        desk = self.desk(1)
        desk.click(2, 2)
        desk.click(*D.START)
        self.assertEqual(desk.clicks, 2)
        self.assertFalse(desk.done)

    def test_done_is_a_button_on_the_taskbar(self):
        desk = self.desk(1)
        desk.click(*centre(D.DONE_RECT))
        self.assertTrue(desk.done)


class TheWindowManager(unittest.TestCase):

    def test_only_the_top_window_takes_a_click_and_it_raises(self):
        for seed in range(20):
            desk = D.Desktop(D.deal(11, seed=seed))
            bottom, top = desk.order
            for control in bottom.tabs[bottom.active]:
                rect = desk.control_rect(control)
                point = centre(D.parts(control, rect)[0])
                if desk.window_at(*point) is not top:
                    continue
                values = [c.value for c in desk.controls]
                desk.click(*point)
                self.assertEqual(desk.order[-1], top)
                self.assertEqual(
                    sum(a != c.value for a, c in zip(values, desk.controls)
                        if c.window is bottom), 0)
                desk.click(*desk.reachable(D.title_rect(bottom), bottom))
                self.assertIs(desk.order[-1], bottom)
                return
        self.fail('no covered control dealt')

    def test_tabs_show_one_page_at_a_time(self):
        desk = D.Desktop(D.deal(5, seed=1))
        win = desk.windows[0]
        hidden = win.tabs[1][0]
        self.assertIsNone(desk.control_rect(hidden))
        desk.click(*centre(D.tab_rects(win)[1]))
        self.assertIsNotNone(desk.control_rect(hidden))
        self.assertIsNone(desk.control_rect(win.tabs[0][0]))

    def test_a_long_tab_scrolls(self):
        desk = D.Desktop(D.deal(8, seed=1))
        win = desk.windows[0]
        last = win.tabs[0][-1]
        self.assertTrue(win.scrolls(0))
        self.assertIsNone(desk.control_rect(last))
        _up, down = D.scroll_rects(win)
        for _click in range(len(win.tabs[0]) - win.rows):
            desk.click(*centre(down))
        self.assertIsNotNone(desk.control_rect(last))
        desk.click(*centre(down))
        self.assertEqual(win.scroll[0], len(win.tabs[0]) - win.rows)

    def open_a_dialog(self, desk):
        win = desk.windows[0]
        desk.click(*centre(D.menu_rects(win)[0]))
        self.assertIsNotNone(desk.menu)
        desk.click(*centre(desk.menu_items()[0]))
        self.assertIsNotNone(desk.dialog)
        return desk.dialog

    def flip_in(self, desk, dialog):
        control = dialog.controls[0]
        before = control.value
        rect = desk.control_rect(control)
        index = 0 if control.kind in ('toggle', 'dropdown') else \
            (before + 1) % control.count
        desk.click(*centre(D.parts(control, rect)[index]))
        if desk.dropdown is not None:
            items = D.dropdown_items(rect, control)
            desk.click(*centre(items[(before + 1) % control.count]))
        self.assertNotEqual(control.shown, before)
        self.assertEqual(control.value, before)
        return control, before

    def test_ok_keeps_a_dialog_s_changes(self):
        desk = D.Desktop(D.deal(8, seed=2))
        dialog = self.open_a_dialog(desk)
        control, before = self.flip_in(desk, dialog)
        desk.click(*centre(desk.dialog_buttons()[1]))
        self.assertIsNone(desk.dialog)
        self.assertNotEqual(control.value, before)

    def test_cancel_throws_them_away(self):
        desk = D.Desktop(D.deal(8, seed=2))
        dialog = self.open_a_dialog(desk)
        control, before = self.flip_in(desk, dialog)
        desk.click(*centre(desk.dialog_buttons()[0]))
        self.assertIsNone(desk.dialog)
        self.assertEqual((control.value, control.shown), (before, before))

    def test_a_dialog_is_modal(self):
        desk = D.Desktop(D.deal(8, seed=2))
        self.open_a_dialog(desk)
        desk.click(*centre(D.DONE_RECT))
        self.assertFalse(desk.done)
        self.assertIsNotNone(desk.dialog)

    def test_a_greyed_control_ignores_clicks_until_its_need_is_met(self):
        for seed in range(30):
            dealt = D.deal(15, seed=seed)
            desk = D.Desktop(dealt)
            greyed = [c for c in desk.controls if c.requires]
            if not greyed:
                continue
            control = greyed[0]
            self.assertFalse(control.enabled)
            other, wanted = control.requires
            other.value = wanted
            self.assertTrue(control.enabled)
            return
        self.fail('no greyed-out control dealt')

    def test_apply_holds_changes_until_pressed(self):
        for seed in range(30):
            desk = D.Desktop(D.deal(16, seed=seed))
            waiting = [w for w in desk.windows if w.apply]
            if not waiting:
                continue
            win = waiting[0]
            desk.order.remove(win)
            desk.order.append(win)
            control = next((c for c in win.tabs[win.active]
                            if c.kind == 'toggle' and c.enabled
                            and desk.control_rect(c)), None)
            if control is None:
                continue
            before = control.value
            desk.click(*centre(D.parts(control,
                                       desk.control_rect(control))[0]))
            self.assertEqual((control.shown, control.value),
                             (1 - before, before))
            desk.click(*centre(D.apply_rect(win)))
            self.assertEqual(control.value, 1 - before)
            return
        self.fail('no Apply window with a switch dealt')


def planned(dealt):
    """A player who plans: one OK per dialog and one Apply per window."""
    desk = D.Desktop(dealt)
    for _step in range(3000):
        pending = [g for g in desk.goals if not desk.met(g)]
        if not pending:
            break
        ident, value = pending[0]
        control = desk.controls[ident]
        if control.shown == value:
            same = [g for g in pending[1:]
                    if desk.controls[g[0]].shown != g[1]
                    and desk.controls[g[0]].window is control.window
                    and desk.controls[g[0]].dialog is control.dialog]
            if same:
                ident, value = same[0]
                control = desk.controls[ident]
        desk.click(*D._towards(desk, control, value))
    return desk


class TheReference(unittest.TestCase):

    def test_it_solves_every_desktop(self):
        for rung in (1, 4, 5, 6, 8, 11, 15, 16, 19, 25, 40):
            for seed in range(4):
                desk = D.reference_round(D.deal(rung, seed=seed))
                self.assertTrue(desk.solved, (rung, seed))

    def test_every_point_it_clicks_is_on_the_pointer_s_grid(self):
        desk = D.Desktop(D.deal(19, seed=1))
        for _step in range(400):
            point = D.reference_click(desk)
            if point is None:
                break
            self.assertEqual((point[0] % D.GRID, point[1] % D.GRID), (0, 0))
            desk.click(*point)
        self.assertTrue(desk.solved)

    def test_planning_the_order_beats_it_where_there_is_order_to_plan(self):
        for rung in (10, 16, 22):
            deals = [D.deal(rung, seed=seed) for seed in range(10)]
            plain = sum(D.reference_round(d).clicks for d in deals)
            plan = [planned(d) for d in deals]
            self.assertTrue(all(desk.solved for desk in plan))
            self.assertLess(sum(desk.clicks for desk in plan), plain * 0.95,
                            rung)

    def test_par_is_its_clicks_scaled_by_the_rung(self):
        dealt = D.deal(25, seed=1)
        self.assertLess(D.par(dealt), D.reference_round(dealt).clicks)
        dealt = D.deal(3, seed=1)
        self.assertGreater(D.par(dealt), D.reference_round(dealt).clicks)


def reference_port(task):
    """The reference's next click, steered there through the ports."""
    from nwenv.desktop import CLICK, DONE
    desk = task.desk
    target = D.reference_click(desk)
    if target is None:
        return DONE
    px, py = desk.pointer
    for gap, back, forth in ((target[1] - py, 0, 1), (target[0] - px, 2, 3)):
        if abs(gap) > 1e-6:
            size = next(i for i, step in enumerate(D.STEPS)
                        if step <= abs(gap))
            return (forth if gap > 0 else back) * 3 + size
    return CLICK


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, policy=reference_port, seed=0):
        from nwenv import catalog
        env = catalog.env_class('desktop')(seed=seed, rung=rung, trials=1,
                                           adaptive=False)
        scalars = []
        try:
            for _step in range(20000):
                task = env.task
                port = policy(task) if task.phase == 'working' else None
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_the_reference_s_clicks_pass_one_window(self):
        self.assertEqual(self.drive(6), [1.0])

    def test_and_overlapping_windows_with_dialogs(self):
        self.assertEqual(self.drive(13), [1.0])

    def test_past_twenty_its_clicks_are_not_enough(self):
        self.assertEqual(self.drive(24), [-1.0])

    def test_done_with_the_card_unmet_is_a_paid_loss(self):
        from nwenv.desktop import DONE
        self.assertEqual(self.drive(3, policy=lambda task: DONE), [-1.0])

    def test_the_ports_are_fourteen(self):
        from nwenv import catalog
        from neural_workshop.ui import desktop as screen
        self.assertEqual(catalog.env_class('desktop').ports, 14)
        self.assertEqual(screen.PORTS, 14)


@needs_ui
class TheTask(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.desktop import Desktop
        close_overlays()
        self.task = Desktop()
        self.task.rng = random.Random(5)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def press_at(self, x, y):
        from pyglet.window import mouse
        px, py = self.task.to_pixels(x, y)
        self.task.on_mouse_press(int(round(px)), int(round(py)),
                                 mouse.LEFT, 0)

    def test_a_mouse_click_lands_where_the_model_says(self):
        self.task.start_rung = 1
        self.task.start_run()
        desk = self.task.desk
        switch = desk.controls[0]
        before = switch.value
        rect = desk.control_rect(switch)
        self.press_at(*centre(D.parts(switch, rect)[0]))
        self.assertEqual(switch.value, 1 - before)
        self.assertEqual(desk.clicks, 1)
        self.task.on_draw()

    def test_keys_move_the_pointer_and_click(self):
        from pyglet.window import key
        self.task.start_run()
        start = self.task.desk.pointer
        self.task.on_key_press(key.LEFT, key.MOD_SHIFT)
        self.task.on_key_press(key.DOWN, key.MOD_ALT)
        self.assertEqual(self.task.desk.pointer,
                         (start[0] - D.STEPS[0], start[1] + D.STEPS[2]))
        self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.desk.clicks, 1)

    def test_solving_under_par_is_green_and_climbs(self):
        self.task.start_rung = 13
        self.task.start_run()
        desk = self.task.desk
        while self.task.phase == 'working':
            point = D.reference_click(desk)
            if point is None:
                self.task.finish_round()
            else:
                self.task.click(*point)
            self.task.on_draw()
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 14)

    def test_running_out_of_clicks_ends_the_round(self):
        self.task.start_run()
        while self.task.phase == 'working':
            self.task.click(2, 2)
        self.assertFalse(self.task.verdict_shown[0])
        self.assertEqual(self.task.results[-1][2], self.task.budget)

    def test_everything_fits_and_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        self.task.start_rung = 30
        self.task.start_run()
        for size in ((1824, 1368), (1280, 720), (2560, 1080)):
            state.window.set_size(*size)
            display.ensure_laid_out()
            self.task.relayout()
            _x, bottom = self.task.to_pixels(0, D.SCREEN_H)
            self.assertGreaterEqual(
                bottom, above_the_band(from_bottom_edge(58)) - 0.5, size)
            right, _y = self.task.to_pixels(D.SCREEN_W, 0)
            self.assertLess(right, state.window.width * 0.72, size)
            for line in (self.task.facts, self.task.footnote,
                         self.task.status):
                self.assertLessEqual(line.content_width,
                                     state.window.width - 16, size)

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.desktop import Desktop
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Desktop.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_has_a_computer_use_tab(self):
        self.assertIn('desktop', [t for t, _l in TASKS['computer']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.desktop import Desktop
        launch_task('desktop')
        self.assertIsNotNone(Desktop.instance)
        Desktop.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.desktop_note({'DESKTOP_RUNG': 25})
        self.assertIn('dialogs', note)
        self.assertIn('beat the reference', note)


if __name__ == '__main__':
    unittest.main()
