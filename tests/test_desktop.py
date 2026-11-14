#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Desktop: the widget grammars, the window manager, par, the boundary.

Each widget is held to doing what it looks like it does when clicked,
and to doing nothing for a click that misses it. The window manager is
held to the rules a real one keeps: only what is on top takes a click,
a click raises its window, sticky notes stay above everything, a title
bar drags and a corner resizes, minimise sends a window to the taskbar
and close sends it to the Start menu, throwing away what it had not
applied. Menus cascade; a menu, a list, a dialog or a popup swallows
the click that dismisses it; Cancel throws a dialog's changes away and
a popup's other button undoes a window's work. Every click and every
drag costs one, and popups arrive on a numbered click whatever was
clicked. The reference is held to solving every desktop and to being
beatable by a player who plans. The boundary is held to paying the
reference's own clicks and drags through the sixteen ports.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import desktop as D

centre = D.centre


def with_kind(rung, kind, seeds=60, **extra):
    """A desktop on *rung* with a showing control of *kind*."""
    for seed in range(seeds):
        desk = D.Desktop(D.deal(rung, seed=seed))
        for control in desk.controls:
            if control.kind == kind and desk.control_rect(control) \
                    and control.enabled:
                return desk, control
    raise AssertionError('no %s dealt on rung %d' % (kind, rung))


def click_part(desk, control, index):
    desk.click(*centre(D.parts(control, desk.control_rect(control))[index]))


class TheLadder(unittest.TestCase):

    def test_every_rung_has_at_least_what_the_last_had(self):
        last = D.grade(1)
        for rung in range(2, 80):
            level = D.grade(rung)
            for field in ('windows', 'tabs', 'per_tab', 'dialogs',
                          'depends', 'applies', 'popups', 'closed', 'notes',
                          'offscreen', 'goals'):
                self.assertGreaterEqual(getattr(level, field),
                                        getattr(last, field), (rung, field))
            self.assertTrue(set(last.kinds) <= set(level.kinds))
            self.assertLessEqual(level.factor, last.factor)
            last = level

    def test_the_parts_arrive_where_the_readme_says(self):
        first = {}
        for rung in range(1, 40):
            level = D.grade(rung)
            for name, there in (
                    ('dropdown', 'dropdown' in level.kinds),
                    ('tabs', level.tabs > 1),
                    ('scroll', level.rows < level.per_tab),
                    ('colour', 'colour' in level.kinds),
                    ('dialogs', level.dialogs > 0),
                    ('stepper', 'stepper' in level.kinds),
                    ('popups', level.popups > 0),
                    ('windows', level.windows > 1),
                    ('minimised', level.minimised > 0),
                    ('small', level.rows == 2 and level.per_tab > 4),
                    ('notes', level.notes > 0),
                    ('depends', level.depends > 0),
                    ('applies', level.applies > 0),
                    ('offscreen', level.offscreen > 0),
                    ('closed', level.closed > 0),
                    ('submenus', level.submenus)):
                if there and name not in first:
                    first[name] = rung
        self.assertEqual(first, {
            'dropdown': 4, 'tabs': 5, 'scroll': 6, 'colour': 7,
            'dialogs': 8, 'stepper': 9, 'popups': 10, 'windows': 11,
            'minimised': 12, 'small': 13, 'notes': 14, 'depends': 15,
            'applies': 16, 'offscreen': 17, 'closed': 18, 'submenus': 19})

    def test_past_twenty_par_is_below_the_reference(self):
        self.assertGreaterEqual(D.grade(20).factor, 1.0)
        self.assertLess(D.grade(21).factor, 1.0)


class TheDeal(unittest.TestCase):

    def test_windows_stay_above_the_taskbar_and_on_screen_but_one(self):
        for rung in range(1, 50, 2):
            for seed in range(3):
                desk = D.Desktop(D.deal(rung, seed=seed))
                over = [w for w in desk.windows
                        if w.x + w.w > D.SCREEN_W]
                self.assertLessEqual(len(over), desk.level.offscreen)
                for win in desk.windows + desk.notes:
                    self.assertLessEqual(win.y + win.h, D.WORK_H)

    def test_names_are_unique_within_a_window(self):
        desk = D.Desktop(D.deal(30, seed=2))
        for win in desk.windows:
            names = [c.label for c in win.controls()]
            self.assertEqual(len(names), len(set(names)))

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(D.deal(19, seed=3), D.deal(19, seed=3))
        self.assertNotEqual(D.deal(19, seed=3), D.deal(19, seed=4))

    def test_every_goal_starts_unmet_and_one_window_starts_open(self):
        for seed in range(10):
            desk = D.Desktop(D.deal(24, seed=seed))
            self.assertFalse(any(desk.met(g) for g in desk.goals))
            self.assertTrue(any(w.shown for w in desk.windows))


class TheWidgets(unittest.TestCase):

    def test_a_switch_flips(self):
        desk = D.Desktop(D.deal(1, seed=0))
        switch = desk.controls[0]
        before = switch.value
        click_part(desk, switch, 0)
        self.assertEqual(switch.value, 1 - before)
        click_part(desk, switch, 0)
        self.assertEqual(switch.value, before)

    def test_choices_sliders_and_colours_take_the_one_clicked(self):
        for kind, rung in (('choice', 3), ('slider', 3), ('colour', 7)):
            desk, control = with_kind(rung, kind)
            click_part(desk, control, control.count - 1)
            self.assertEqual(control.value, control.count - 1, kind)
            click_part(desk, control, 0)
            self.assertEqual(control.value, 0, kind)

    def test_a_colour_s_swatches_are_named_colours(self):
        _desk, control = with_kind(7, 'colour')
        for name in control.words:
            self.assertEqual(len(D.colour_of(name)), 3)

    def test_a_stepper_goes_one_at_a_time_and_stops_at_the_ends(self):
        desk, control = with_kind(9, 'stepper')
        control.shown = control.value = 0
        click_part(desk, control, 0)
        self.assertEqual(control.value, 0)
        for _click in range(control.count + 2):
            click_part(desk, control, 1)
        self.assertEqual(control.value, control.count - 1)
        click_part(desk, control, 0)
        self.assertEqual(control.value, control.count - 2)

    def test_a_dropdown_opens_then_takes_the_item(self):
        desk, control = with_kind(4, 'dropdown')
        click_part(desk, control, 0)
        self.assertIs(desk.dropdown, control)
        items = D.dropdown_items(desk.control_rect(control), control)
        wanted = (control.value + 1) % control.count
        desk.click(*centre(items[wanted]))
        self.assertIsNone(desk.dropdown)
        self.assertEqual(control.value, wanted)
        self.assertEqual(desk.clicks, 2)

    def test_every_click_costs_one_even_on_nothing(self):
        desk = D.Desktop(D.deal(1, seed=0))
        desk.click(2, 2)
        desk.click(*D.START)
        self.assertEqual(desk.clicks, 2)
        self.assertFalse(desk.done)

    def test_done_is_a_button_on_the_taskbar(self):
        desk = D.Desktop(D.deal(1, seed=0))
        desk.click(*centre(D.DONE_RECT))
        self.assertTrue(desk.done)


class TheWindowManager(unittest.TestCase):

    def test_only_the_top_window_takes_a_click_and_it_raises(self):
        for seed in range(20):
            desk = D.Desktop(D.deal(11, seed=seed))
            apps = [w for w in desk.order if w.kind == 'app']
            if desk.order[-1] is not apps[-1]:
                continue
            bottom, top = apps
            for control in bottom.tabs[bottom.active]:
                point = centre(D.parts(control,
                                       desk.control_rect(control))[0])
                if desk.window_at(*point) is not top:
                    continue
                values = [c.value for c in bottom.controls()]
                desk.click(*point)
                self.assertIs(desk.order[-1], top)
                self.assertEqual([c.value for c in bottom.controls()],
                                 values)
                desk.click(*desk.reachable(D.title_rect(bottom), bottom))
                self.assertIs(desk.order[-1], bottom)
                return
        self.fail('no covered control dealt')

    def test_a_hand_that_slips_on_a_control_still_clicks_it(self):
        desk = D.Desktop(D.deal(1, seed=0))
        control = desk.windows[0].tabs[0][0]
        before = control.value
        x, y = centre(D.parts(control, desk.control_rect(control))[-1])
        desk.act(('drag', (x, y), (x + 12, y - 9)))
        self.assertNotEqual(control.value, before)
        self.assertEqual(desk.clicks, 1)

    def test_a_title_bar_drags_the_window_and_a_drag_costs_one(self):
        desk = D.Desktop(D.deal(3, seed=0))
        win = desk.windows[0]
        x, y = win.x, win.y
        grip = (win.x + 60, win.y + 15)
        desk.act(('drag', grip, (grip[0] - 100, grip[1] + 40)))
        self.assertEqual((win.x, win.y), (x - 100, y + 40))
        self.assertEqual(desk.clicks, 1)

    def test_a_window_cannot_be_dragged_out_of_reach(self):
        desk = D.Desktop(D.deal(3, seed=0))
        win = desk.windows[0]
        grip = (win.x + 60, win.y + 15)
        desk.act(('drag', grip, (D.SCREEN_W - 1, 0)))
        self.assertLessEqual(win.x, D.SCREEN_W - 60)
        self.assertIsNotNone(desk.reachable(D.title_rect(win), win))

    def test_the_corner_resizes_and_scrolling_follows(self):
        desk = D.Desktop(D.deal(13, seed=1))
        win = next(w for w in desk.windows if w.shown)
        desk.raise_window(win)
        self.assertEqual(win.rows, 2)
        corner = desk.reachable(D.grip_rect(win), win)
        desk.act(('drag', corner, (corner[0], corner[1] + 2 * D.ROW_H)))
        self.assertEqual(win.rows, 4)
        corner = desk.reachable(D.grip_rect(win), win)
        desk.act(('drag', corner, (corner[0], corner[1] + 40 * D.ROW_H)))
        self.assertEqual(win.rows, win.most_rows)
        self.assertLessEqual(win.y + win.h, D.WORK_H)

    def test_minimise_goes_to_the_taskbar_and_comes_back(self):
        desk = D.Desktop(D.deal(3, seed=0))
        win = desk.windows[0]
        desk.click(*centre(D.minimise_rect(win)))
        self.assertTrue(win.minimised)
        self.assertIsNone(desk.window_at(*centre(D.title_rect(win))))
        (owner, button), = desk.taskbar_buttons()
        self.assertIs(owner, win)
        desk.click(*centre(button))
        self.assertFalse(win.minimised)

    def test_close_sends_it_to_the_start_menu_and_drops_what_was_pending(self):
        for seed in range(30):
            desk = D.Desktop(D.deal(16, seed=seed))
            win = next((w for w in desk.windows if w.apply and w.shown),
                       None)
            if win is None:
                continue
            desk.popups = []
            control = win.tabs[win.active][0]
            control.shown = (control.value + 1) % control.count
            desk.raise_window(win)
            desk.click(*desk.reachable(D.close_rect(win), win))
            self.assertTrue(win.closed)
            self.assertEqual(control.shown, control.value)
            self.assertNotIn(win, [w for w, _r in desk.taskbar_buttons()])
            desk.click(*centre(D.START_RECT))
            self.assertTrue(desk.start_open)
            desk.click(*centre(D.all_apps_rect()))
            item = dict((id(w), r) for w, r in desk.start_items())[id(win)]
            desk.click(*centre(item))
            self.assertFalse(win.closed)
            self.assertIs(desk.order[-1 - len(desk.notes)], win)
            return
        self.fail('no open Apply window dealt')

    def test_sticky_notes_stay_on_top_and_minimise_away(self):
        desk = D.Desktop(D.deal(14, seed=0))
        note = desk.notes[0]
        for win in desk.windows:
            if win.shown:
                desk.raise_window(win)
        self.assertIs(desk.order[-1], note)
        middle = centre((note.x, note.y + D.TITLE_H, note.w, 40))
        self.assertIs(desk.window_at(*middle), note)
        desk.click(*centre(D.minimise_rect(note)))
        self.assertIsNot(desk.window_at(*middle), note)

    def test_tabs_show_one_page_at_a_time(self):
        desk = D.Desktop(D.deal(5, seed=1))
        win = desk.windows[0]
        hidden = win.tabs[1][0]
        self.assertIsNone(desk.control_rect(hidden))
        desk.click(*centre(D.tab_rects(win)[1]))
        self.assertIsNotNone(desk.control_rect(hidden))

    def test_a_long_tab_scrolls(self):
        desk = D.Desktop(D.deal(8, seed=1))
        win = desk.windows[0]
        desk.raise_window(win)
        last = win.tabs[0][-1]
        self.assertIsNone(desk.control_rect(last))
        _up, down = D.scroll_rects(win)
        for _click in range(len(win.tabs[0]) - win.rows + 1):
            desk.click(*centre(down))
        self.assertIsNotNone(desk.control_rect(last))
        self.assertEqual(win.scroll[0], len(win.tabs[0]) - win.rows)


class MenusDialogsAndPopups(unittest.TestCase):

    def open_a_dialog(self, desk):
        win = desk.windows[0]
        desk.click(*centre(D.menu_rects(win)[0]))
        desk.click(*centre(desk.menu_items()[0]))
        self.assertIsNotNone(desk.dialog)
        return desk.dialog

    def change(self, desk, control):
        before = control.value
        rect = desk.control_rect(control)
        if control.kind == 'stepper':
            index = 1 if before == 0 else 0
        elif control.kind in ('toggle', 'dropdown'):
            index = 0
        else:
            index = (before + 1) % control.count
        desk.click(*centre(D.parts(control, rect)[index]))
        if desk.dropdown is not None:
            items = D.dropdown_items(rect, control)
            desk.click(*centre(items[(before + 1) % control.count]))
        self.assertNotEqual(control.shown, before)
        return before

    def test_ok_keeps_a_dialog_s_changes_and_cancel_drops_them(self):
        for button, keeps in ((1, True), (0, False)):
            desk = D.Desktop(D.deal(8, seed=2))
            control = self.open_a_dialog(desk).controls[0]
            before = self.change(desk, control)
            self.assertEqual(control.value, before)
            desk.click(*centre(desk.dialog_buttons()[button]))
            self.assertIsNone(desk.dialog)
            self.assertEqual(control.value != before, keeps)

    def test_a_dialog_is_modal(self):
        desk = D.Desktop(D.deal(8, seed=2))
        self.open_a_dialog(desk)
        desk.click(*centre(D.DONE_RECT))
        self.assertFalse(desk.done)

    def test_menus_cascade(self):
        desk = D.Desktop(D.deal(19, seed=0))
        win = next(w for w in desk.windows if w.shown)
        desk.raise_window(win)
        for note in desk.notes:
            note.minimised = True
        desk.click(*centre(D.menu_rects(win)[0]))
        items = win.menus[0][1]
        sub = next(i for i, item in enumerate(items)
                   if isinstance(item, D.Submenu))
        desk.click(*centre(desk.menu_items()[sub]))
        self.assertEqual(desk.menu[2], sub)
        desk.click(*centre(desk.submenu_items()[0]))
        self.assertIs(desk.dialog, items[sub].dialogs[0])

    def test_a_popup_arrives_on_its_click_whatever_was_clicked(self):
        dealt = D.deal(10, seed=3)
        due = dealt.popups[0].at
        for spot in ((2, 2), centre(D.title_rect(D.Desktop(dealt)
                                                 .windows[0]))):
            desk = D.Desktop(dealt)
            for _click in range(due - 1):
                desk.click(*spot)
            self.assertIsNone(desk.popup)
            desk.click(*spot)
            self.assertIsNotNone(desk.popup)

    def test_a_popup_takes_every_click_until_it_is_answered(self):
        dealt = D.deal(10, seed=3)
        desk = D.Desktop(dealt)
        while desk.popup is None:
            desk.click(2, 2)
        clicks = desk.clicks
        desk.click(*centre(D.DONE_RECT))
        self.assertFalse(desk.done)
        self.assertEqual(desk.clicks, clicks + 1)
        safe, _reset = D.popup_buttons(desk.popup.safe_left)
        desk.click(*centre(safe))
        self.assertIsNone(desk.popup)

    def test_its_other_button_undoes_the_window_s_work(self):
        dealt = D.deal(10, seed=3)
        desk = D.Desktop(dealt)
        win = desk.windows[desk.popups[0].window]
        control = win.tabs[win.active][0]
        while desk.popup is None:
            if desk.clicks == 0:
                self.change(desk, control)
            else:
                desk.click(2, 2)
        self.assertNotEqual(control.value, control.start)
        _safe, reset = D.popup_buttons(desk.popup.safe_left)
        desk.click(*centre(reset))
        self.assertEqual(control.value, control.start)



def explorer_desk(rung=12, seed=0):
    """A desktop with its explorer opened on top and no popups due."""
    desk = D.Desktop(D.deal(rung, seed=seed))
    desk.popups = []
    desk.open_app(desk.explorer)
    return desk, desk.explorer


def hit(desk, rect, win):
    point = desk.reachable(rect, win)
    assert point is not None, rect
    desk.click(*point)


class TheFiles(unittest.TestCase):

    def test_the_ladder_brings_the_files_in_order(self):
        self.assertFalse(D.grade(5).explorer)
        self.assertTrue(D.grade(6).explorer)
        self.assertEqual(D.grade(6).moves, 1)
        self.assertEqual(D.grade(11).ex_tabs, 1)
        self.assertEqual(D.grade(12).ex_tabs, 2)
        self.assertTrue(D.grade(14).deletes)
        self.assertTrue(D.grade(15).explorer_closed)
        self.assertTrue(D.grade(18).restores)
        self.assertGreater(D.grade(40).depth, D.grade(16).depth)
        self.assertGreater(D.grade(40).moves, D.grade(16).moves)

    def test_no_files_before_the_explorer(self):
        desk = D.Desktop(D.deal(5, seed=0))
        self.assertIsNone(desk.explorer)
        self.assertEqual(desk.moves, [])
        self.assertEqual(desk.desktop_icons(), [])

    def test_a_double_click_opens_a_folder_and_back_returns(self):
        desk, ex = explorer_desk()
        place = ex.places[ex.place]
        start = place.path
        folder, rect = next((n, r) for n, r in desk.icon_rects(ex)
                            if n.folder)
        hit(desk, rect, ex)
        self.assertIs(place.selected, folder)
        self.assertIs(place.path, start)
        hit(desk, rect, ex)
        self.assertIs(place.path, folder)
        tools = dict(D.tool_rects(ex))
        hit(desk, tools['Back'], ex)
        self.assertIs(place.path, start)

    def test_two_single_clicks_apart_do_not_open(self):
        desk, ex = explorer_desk()
        place = ex.places[ex.place]
        folder, rect = next((n, r) for n, r in desk.icon_rects(ex)
                            if n.folder)
        hit(desk, rect, ex)
        desk.click(*D.centre(D.title_rect(ex)))
        hit(desk, rect, ex)
        self.assertIsNot(place.path, folder)

    def test_up_and_the_sidebar_go_where_they_say(self):
        desk, ex = explorer_desk()
        place = ex.places[ex.place]
        hit(desk, D.sidebar_rects(ex)[D.DOCUMENTS], ex)
        self.assertIs(place.path, desk.nodes[D.DOCUMENTS])
        hit(desk, dict(D.tool_rects(ex))['Up'], ex)
        self.assertIs(place.path, desk.nodes[D.HOME])

    def test_cut_and_paste_move_a_file(self):
        desk, ex = explorer_desk()
        place = ex.places[ex.place]
        hit(desk, D.sidebar_rects(ex)[D.DOCUMENTS], ex)
        node, rect = next((n, r) for n, r in desk.icon_rects(ex)
                          if not n.folder)
        hit(desk, rect, ex)
        hit(desk, dict(D.tool_rects(ex))['Cut'], ex)
        hit(desk, D.sidebar_rects(ex)[D.DESKTOP_DIR], ex)
        hit(desk, dict(D.tool_rects(ex))['Paste'], ex)
        self.assertIs(node.parent, desk.nodes[D.DESKTOP_DIR])
        self.assertIsNone(desk.clipboard)
        self.assertIn(node, [i[1] for i, _r in desk.desktop_icons()
                             if i[0] == 'node'])
        del place

    def test_delete_sends_it_to_the_trash_and_no_further(self):
        desk, ex = explorer_desk()
        hit(desk, D.sidebar_rects(ex)[D.DOCUMENTS], ex)
        node, rect = next((n, r) for n, r in desk.icon_rects(ex)
                          if not n.folder)
        hit(desk, rect, ex)
        hit(desk, dict(D.tool_rects(ex))['Delete'], ex)
        self.assertIs(node.parent, desk.nodes[D.TRASH])

    def test_a_folder_cannot_go_inside_itself(self):
        desk = D.Desktop(D.deal(12, seed=0))
        folder = next(n for n in desk.nodes if n.folder
                      and n.ident >= len(D.PLACES) and n.children
                      and any(c.folder for c in n.children))
        inner = next(c for c in folder.children if c.folder)
        self.assertFalse(desk.move_file(folder, inner))
        self.assertFalse(desk.move_file(desk.nodes[D.DOCUMENTS],
                                        desk.nodes[D.TRASH]))

    def test_tabs_keep_their_own_place_and_plus_adds_one(self):
        desk, ex = explorer_desk()
        self.assertEqual(len(ex.places), 2)
        first, second = ex.places
        self.assertIsNot(first.path, second.path)
        hit(desk, D.place_tab_rects(ex)[1], ex)
        self.assertEqual(ex.place, 1)
        hit(desk, D.plus_rect(ex), ex)
        self.assertEqual(len(ex.places), 3)
        self.assertIs(ex.places[2].path, desk.nodes[D.HOME])
        self.assertEqual(ex.place, 2)

    def test_dragging_an_icon_onto_the_sidebar_moves_it(self):
        desk, ex = explorer_desk()
        hit(desk, D.sidebar_rects(ex)[D.DOCUMENTS], ex)
        node, rect = next((n, r) for n, r in desk.icon_rects(ex)
                          if not n.folder)
        clicks = desk.clicks
        desk.act(('drag', desk.reachable(rect, ex),
                  desk.reachable(D.sidebar_rects(ex)[D.TRASH], ex)))
        self.assertIs(node.parent, desk.nodes[D.TRASH])
        self.assertEqual(desk.clicks, clicks + 1)

    def test_dragging_onto_the_other_tab_moves_it_there(self):
        desk, ex = explorer_desk()
        hit(desk, D.place_tab_rects(ex)[1], ex)
        hit(desk, D.sidebar_rects(ex)[D.DESKTOP_DIR], ex)
        hit(desk, D.place_tab_rects(ex)[0], ex)
        hit(desk, D.sidebar_rects(ex)[D.DOCUMENTS], ex)
        node, rect = next((n, r) for n, r in desk.icon_rects(ex)
                          if not n.folder)
        there = ex.places[1].path
        desk.act(('drag', desk.reachable(rect, ex),
                  desk.reachable(D.place_tab_rects(ex)[1], ex)))
        self.assertIs(node.parent, there)

    def test_dropping_on_the_bare_desktop_saves_it_there(self):
        desk, ex = explorer_desk()
        hit(desk, D.sidebar_rects(ex)[D.DOCUMENTS], ex)
        node, rect = next((n, r) for n, r in desk.icon_rects(ex)
                          if not n.folder)
        spot = (D.SCREEN_W - 20, D.WORK_H - 20)
        self.assertIsNone(desk.window_at(*spot))
        desk.act(('drag', desk.reachable(rect, ex), spot))
        self.assertIs(node.parent, desk.nodes[D.DESKTOP_DIR])

    def test_the_desktop_trash_icon_takes_a_drop_and_opens(self):
        desk, ex = explorer_desk(rung=14)
        file = next(n for n in desk.nodes[D.DESKTOP_DIR].listing()
                    if not n.folder)
        icons = dict((D._icon_key(i), r) for i, r in desk.desktop_icons())
        desk.minimised = None
        desk.click(*D.centre(D.minimise_rect(ex)))
        for win in list(desk.order):
            if not win.minimised:
                win.minimised = True
        desk.act(('drag', D.centre(icons[D._icon_key(('node', file))]),
                  D.centre(icons[('trash',)])))
        self.assertIs(file.parent, desk.nodes[D.TRASH])
        trash = D.centre(dict((D._icon_key(i), r)
                              for i, r in desk.desktop_icons())[('trash',)])
        desk.click(*trash)
        desk.click(*trash)
        self.assertFalse(ex.minimised)
        self.assertIs(ex.places[ex.place].path, desk.nodes[D.TRASH])


class TheStartPanel(unittest.TestCase):

    def test_pinned_tiles_open_their_app(self):
        desk = D.Desktop(D.deal(18, seed=0))
        desk.popups = []
        desk.click(*D.centre(D.START_RECT))
        self.assertTrue(desk.start_open)
        win, rect = desk.start_items()[0]
        self.assertIn(win, desk.pinned)
        win.closed = True
        desk.click(*D.centre(rect))
        self.assertFalse(win.closed)
        self.assertFalse(desk.start_open)

    def test_all_apps_lists_every_app_by_name(self):
        desk = D.Desktop(D.deal(18, seed=0))
        desk.popups = []
        desk.click(*D.centre(D.START_RECT))
        desk.click(*D.centre(D.all_apps_rect()))
        listed = [w for w, _r in desk.start_items()]
        self.assertEqual(sorted(w.title for w in listed),
                         [w.title for w in listed])
        self.assertEqual(set(map(id, listed)), set(map(id, desk.apps)))

    def test_a_click_elsewhere_shuts_it(self):
        desk = D.Desktop(D.deal(18, seed=0))
        desk.popups = []
        desk.click(*D.centre(D.START_RECT))
        desk.click(D.SCREEN_W - 20, 20)
        self.assertFalse(desk.start_open)

    def test_a_closed_explorer_starts_the_round_closed(self):
        desk = D.Desktop(D.deal(15, seed=0))
        self.assertTrue(desk.explorer.closed)
        self.assertNotIn(desk.explorer, [w for w, _r in
                                         desk.taskbar_buttons()])


class FileGoals(unittest.TestCase):

    def test_every_rung_with_an_explorer_deals_file_goals(self):
        for rung in (6, 12, 18, 30):
            desk = D.Desktop(D.deal(rung, seed=3))
            self.assertGreaterEqual(len(desk.moves), D.grade(rung).moves)
            for node, dest in desk.moves:
                self.assertIsNot(node.parent, dest)
                self.assertTrue(dest.folder)

    def test_the_round_is_not_solved_until_the_files_are_moved(self):
        desk = D.Desktop(D.deal(6, seed=0))
        for ident, value in desk.goals:
            desk.controls[ident].value = value
        self.assertFalse(desk.solved)
        for node, dest in desk.moves:
            self.assertTrue(desk.move_file(node, dest))
        self.assertTrue(desk.solved)

    def test_restores_come_out_of_the_trash(self):
        found = False
        for seed in range(10):
            desk = D.Desktop(D.deal(18, seed=seed))
            found |= any(node.within(desk.nodes[D.TRASH])
                         and not dest.within(desk.nodes[D.TRASH])
                         for node, dest in desk.moves)
        self.assertTrue(found)

    def test_long_horizon_rungs_bury_files_deep(self):
        desk = D.Desktop(D.deal(30, seed=0))
        deepest = max(len(node.chain()) for node, _d in desk.moves)
        self.assertGreaterEqual(deepest, 5)

def planned(dealt):
    """A player who plans: stretches a window rather than scroll it, and
    finishes a dialog or a window before its OK or Apply."""
    desk = D.Desktop(dealt)
    for win in desk.windows:
        if win.shown and any(desk.controls[i].window is win
                             and desk.controls[i].dialog is None
                             and desk.controls[i].row >= win.rows
                             for i, _v in desk.goals):
            corner = desk.reachable(D.grip_rect(win), win)
            if corner is not None:
                desk.act(('drag', corner, (corner[0], corner[1]
                                           + (win.most_rows - win.rows)
                                           * D.ROW_H)))
    for _step in range(3000):
        if desk.popup is not None:
            desk.act(D.reference_action(desk))
            continue
        pending = [g for g in desk.goals if not desk.met(g)]
        if not pending:
            # Files are the reference's business; it ends with Done.
            action = D.reference_action(desk)
            if action is None:
                break
            desk.act(action)
            continue
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
        desk.act(D._towards(desk, control, value))
    return desk


class TheReference(unittest.TestCase):

    def test_it_solves_every_desktop(self):
        for rung in (1, 4, 7, 8, 9, 10, 12, 13, 14, 16, 17, 18, 19, 25, 40):
            for seed in range(4):
                desk = D.reference_round(D.deal(rung, seed=seed))
                self.assertTrue(desk.solved, (rung, seed))

    def test_every_point_it_uses_is_on_the_pointer_s_grid(self):
        desk = D.Desktop(D.deal(19, seed=1))
        for _step in range(600):
            action = D.reference_action(desk)
            if action is None:
                break
            for point in action[1:]:
                self.assertEqual((point[0] % D.GRID, point[1] % D.GRID),
                                 (0, 0), action)
            desk.act(action)
        self.assertTrue(desk.solved)

    def test_planning_beats_it_where_there_is_planning_to_do(self):
        for rung in (8, 13, 16):
            deals = [D.deal(rung, seed=seed) for seed in range(10)]
            plain = sum(D.reference_round(d).clicks for d in deals)
            plan = [planned(d) for d in deals]
            self.assertTrue(all(desk.solved for desk in plan))
            # The file goals cost both the same, which dilutes the gap.
            self.assertLess(sum(desk.clicks for desk in plan), plain * 0.98,
                            rung)

    def test_par_is_its_clicks_scaled_by_the_rung(self):
        dealt = D.deal(25, seed=1)
        self.assertLess(D.par(dealt), D.reference_round(dealt).clicks)
        dealt = D.deal(3, seed=1)
        self.assertGreater(D.par(dealt), D.reference_round(dealt).clicks)


def reference_port(task, memory):
    """The reference's next action, steered there through the ports."""
    from nwenv.desktop import CLICK, DONE, PRESS, RELEASE
    desk = task.desk
    if desk.held is not None:
        target, finish = memory['to'], RELEASE
    else:
        action = D.reference_action(desk)
        if action is None:
            return DONE
        target = action[1]
        finish = CLICK if action[0] == 'click' else PRESS
        if action[0] == 'drag':
            memory['to'] = action[2]
    px, py = desk.pointer
    for gap, back, forth in ((target[1] - py, 0, 1), (target[0] - px, 2, 3)):
        if abs(gap) > 1e-6:
            size = next(i for i, step in enumerate(D.STEPS)
                        if step <= abs(gap))
            return (forth if gap > 0 else back) * 3 + size
    return finish


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, policy=reference_port, seed=0):
        from nwenv import catalog
        env = catalog.env_class('desktop')(seed=seed, rung=rung, trials=1,
                                           adaptive=False)
        scalars, memory = [], {}
        try:
            for _step in range(40000):
                task = env.task
                port = (policy(task, memory) if task.phase == 'working'
                        else None)
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

    def test_and_a_crowded_screen_with_drags_and_popups(self):
        self.assertEqual(self.drive(19, seed=2), [1.0])

    def test_past_twenty_its_clicks_are_not_enough(self):
        self.assertEqual(self.drive(26), [-1.0])

    def test_done_with_the_card_unmet_is_a_paid_loss(self):
        from nwenv.desktop import DONE
        self.assertEqual(self.drive(3, policy=lambda task, m: DONE), [-1.0])

    def test_the_ports_are_sixteen(self):
        from nwenv import catalog
        from neural_workshop.ui import desktop as screen
        self.assertEqual(catalog.env_class('desktop').ports, 16)
        self.assertEqual(screen.PORTS, 16)


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

    def mouse(self, start, end=None):
        from pyglet.window import mouse
        end = end or start
        px, py = self.task.to_pixels(*start)
        self.task.on_mouse_press(int(round(px)), int(round(py)),
                                 mouse.LEFT, 0)
        px, py = self.task.to_pixels(*end)
        self.task.on_mouse_release(int(round(px)), int(round(py)),
                                   mouse.LEFT, 0)

    def test_a_mouse_click_lands_where_the_model_says(self):
        self.task.start_rung = 1
        self.task.start_run()
        desk = self.task.desk
        switch = desk.controls[0]
        before = switch.value
        self.mouse(centre(D.parts(switch, desk.control_rect(switch))[0]))
        self.assertEqual(switch.value, 1 - before)
        self.assertEqual(desk.clicks, 1)
        self.task.on_draw()

    def test_a_mouse_drag_moves_a_window(self):
        self.task.start_rung = 3
        self.task.start_run()
        win = self.task.desk.windows[0]
        x = win.x
        start = (win.x + 60, win.y + 15)
        self.mouse(start, (start[0] - 100, start[1]))
        self.assertAlmostEqual(win.x, x - 100, delta=D.GRID)
        self.task.on_draw()

    def test_keys_move_the_pointer_click_and_hold(self):
        from pyglet.window import key
        self.task.start_run()
        desk = self.task.desk
        start = desk.pointer
        self.task.on_key_press(key.LEFT, key.MOD_SHIFT)
        self.task.on_key_press(key.DOWN, key.MOD_ALT)
        self.assertEqual(desk.pointer,
                         (start[0] - D.STEPS[0], start[1] + D.STEPS[2]))
        self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(desk.clicks, 1)
        self.task.on_key_press(key.D, 0)
        self.assertIsNotNone(desk.held)
        self.task.on_key_press(key.D, 0)
        self.assertIsNone(desk.held)
        self.assertEqual(desk.clicks, 2)

    def test_solving_under_par_is_green_and_climbs(self):
        self.task.start_rung = 17
        self.task.start_run()
        desk = self.task.desk
        while self.task.phase == 'working':
            action = D.reference_action(desk)
            if action is None:
                self.task.finish_round()
            else:
                self.task.press(*action[1])
                self.task.release(*action[-1])
            self.task.on_draw()
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 18)

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

    def test_a_window_off_the_edge_does_not_paint_over_the_card(self):
        self.task.start_rung = 17
        self.task.start_run()
        right, _y = self.task.to_pixels(D.SCREEN_W, 0)
        for shape in self.task.drawn:
            # The card's colour chips are drawn at 950 and up, beside
            # the screen on purpose.
            if isinstance(shape, pyglet_rectangle()) \
                    and shape.group.order < 950:
                self.assertLessEqual(shape.x + shape.width, right + 1)

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.desktop import Desktop
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Desktop.instance)
        self.assertNotIn(self.task, display.open_overlays())


def pyglet_rectangle():
    import pyglet
    return pyglet.shapes.Rectangle


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
        self.assertIn('popups', note)
        self.assertIn('beat the reference', note)


if __name__ == '__main__':
    unittest.main()
