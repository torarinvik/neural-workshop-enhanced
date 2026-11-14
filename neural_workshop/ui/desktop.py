# -*- coding: utf-8 -*-
"""Desktop: operate a small computer to reach the settings on a card.

The screen is drawn here and nowhere else: windows with title bars --
each with a minimise and a close button and a corner to resize by --
menu bars whose menus can cascade, tabs, rows of controls, scroll
arrows and Apply buttons; sticky notes on top of everything; and over
them dropdown lists, dialogs and popups, and a taskbar with a Start
menu, a button per open window and Done. The card on the right lists
the settings to reach, each named by its window -- or its dialog -- and
ticked once it holds. :mod:`neural_workshop.desktop` decides what every
click and drag does, so the screen and the reference cannot disagree.

Every click costs a point, and so does every drag; moving the pointer
is free. People use the mouse: click, and drag a title bar to move a
window or its bottom-right corner to resize it. The arrow keys move the
drawn pointer too (Shift for a long step, Alt for a short one), Space
clicks and D presses or lets go, which is exactly how the agent plays:
twelve ports move the pointer by a long, a medium or a short step in
each direction, then click, press, release and Done.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import desktop as model
from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: Seconds the verdict stays up before the next round.
FEEDBACK = 2.2

#: Ports: (up, down, left, right) x (long, medium, short), then these.
DIRECTIONS = ((0, -1), (0, 1), (-1, 0), (1, 0))
CLICK, PRESS, RELEASE, DONE = 12, 13, 14, 15
PORTS = 16

TITLE_COLOURS = ((58, 98, 170), (150, 70, 60), (60, 130, 90),
                 (120, 80, 150), (170, 120, 40), (60, 120, 140))
PANEL = (244, 245, 248)
PANEL_EDGE = (90, 96, 110)
DESK = (70, 102, 130)
TASKBAR = (34, 38, 46)
TASK_BUTTON = (70, 76, 90)
ACCENT = (52, 110, 220)
ON = (60, 160, 90)
OFF = (176, 180, 188)
GREY = (150, 152, 158)
BUTTON = (222, 226, 234)
NOTE = (250, 226, 120)
FOLDER = (236, 190, 70)
SELECTED = (196, 216, 250)
#: The band of colour across a file's page, by what it holds.
FILE_BANDS = {'doc': (52, 110, 220), 'sheet': (60, 150, 80),
              'image': (200, 90, 150), 'music': (150, 90, 200)}
APP_TILE = (70, 90, 130)
WARN = (190, 60, 50)
INK = (20, 22, 28)
WHITE = (255, 255, 255)
POINTER = (255, 255, 255)


#: Pixels a mouse may slip between press and release and still click.
JITTER = 6


class Desktop:
    """Reach the card's settings in no more clicks than par."""

    instance: Optional['Desktop'] = None

    def __init__(self) -> None:
        if Desktop.instance is not None:
            Desktop.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.desk: Optional[model.Desktop] = None
        self.par = 0.0
        self.budget = 0
        self.rung = 1
        self.trial = 0
        self.feedback_until = 0.0
        self.results: List[Tuple[int, bool, int, float]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.drawn: List[object] = []
        self._read_options()
        self.message = _('Press Space or click to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_mouse_release,
                                   self.on_mouse_motion,
                                   self.on_mouse_drag, self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        Desktop.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.DESKTOP)
        self.start_rung = int(opts['DESKTOP_RUNG'])
        self.total_trials = int(opts['DESKTOP_TRIALS'])
        self.adaptive = bool(opts['DESKTOP_ADAPTIVE'])
        self.rung = max(1, self.start_rung)

    def open_options(self) -> None:
        taskoptions.open_task_options('desktop', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _frame(self) -> Tuple[float, float, float]:
        """Left and top of the screen in pixels, and pixels per unit."""
        window = state.window
        top = from_top_edge(116)
        bottom = above_the_band(from_bottom_edge(58))
        width = window.width * 0.68
        scale = min(width / model.SCREEN_W, (top - bottom) / model.SCREEN_H)
        left = window.width * 0.02
        return left, top, scale

    def to_pixels(self, x: float, y: float) -> Tuple[float, float]:
        left, top, scale = self._frame()
        return left + x * scale, top - y * scale

    def to_model(self, px: float, py: float) -> Tuple[float, float]:
        left, top, scale = self._frame()
        return (px - left) / scale, (top - py) / scale

    def _build_chrome(self) -> None:
        self.dark = bool(state.cfg.BLACK_BACKGROUND)
        fg = 255 if self.dark else 0
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()

        def label(words, size, y, bold=False):
            return pyglet.text.Label(
                words, font_size=size, color=self.textcolor,
                weight='bold' if bold else 'normal', batch=self.batch,
                x=width_center(), y=y, anchor_x='center',
                anchor_y='center', font_name=FONTLIST)

        self.title = label(_('Desktop'), calc_fontsize(22),
                           from_top_edge(36), bold=True)
        self.status = label('', calc_fontsize(14), from_top_edge(70))
        self.facts = label('', calc_fontsize(12), from_top_edge(96))
        self.footnote = label(
            _('arrows: pointer (+Shift long, +Alt short)   Space: click   '
              'D: hold / let go   Enter: done   Esc'),
            calc_fontsize(11), from_bottom_edge(26))
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        _left, _top, scale = self._frame()
        self.pointer_size = max(10.0, 22 * scale)
        self.pointer = pyglet.shapes.Triangle(
            0, 0, 0, 0, 0, 0, color=POINTER, batch=self.batch,
            group=pyglet.graphics.Group(order=990))
        self.pointer_edge = pyglet.shapes.Triangle(
            0, 0, 0, 0, 0, 0, color=INK, batch=self.batch,
            group=pyglet.graphics.Group(order=989))
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.desk = None
        self.phase = 'ready'
        self.message = _('Press Space or click to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self.rung = max(1, self.start_rung)
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        dealt = model.deal(self.rung, rng=self.rng)
        self.par = model.par(dealt)
        self.budget = model.budget(self.par)
        self.desk = model.Desktop(dealt)
        self.verdict_shown = None
        self.verdict.clear()
        self.phase = 'working'
        self.message = _('Reach the settings on the card in %s clicks or '
                         'fewer, then Done') % _points(self.par)
        self._redraw()

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        """One agent port: move the pointer, click, press, let go, Done."""
        if self.phase != 'working':
            return
        if port < CLICK:
            dx, dy = DIRECTIONS[port // 3]
            step = model.STEPS[port % 3]
            self.desk.move(dx * step, dy * step)
            self._place_pointer()
        elif port == CLICK:
            self.click()
        elif port == PRESS:
            self.press()
        elif port == RELEASE:
            self.release()
        else:
            self.finish_round()

    def click(self, x: Optional[float] = None,
              y: Optional[float] = None) -> None:
        if self.phase != 'working':
            return
        self.desk.click(x, y)
        self._after()

    def press(self, x: Optional[float] = None,
              y: Optional[float] = None) -> None:
        if self.phase != 'working':
            return
        self.desk.press(x, y)
        self._redraw()

    def release(self, x: Optional[float] = None,
                y: Optional[float] = None) -> None:
        if self.phase != 'working' or self.desk.held is None:
            return
        self.desk.release(x, y)
        self._after()

    def _after(self) -> None:
        if self.desk.done or self.desk.clicks >= self.budget:
            self._judge()
        else:
            self._redraw()

    def finish_round(self) -> None:
        if self.phase != 'working':
            return
        self.desk.done = True
        self._judge()

    def _judge(self) -> None:
        desk = self.desk
        desk.done = True
        passed = desk.solved and desk.clicks <= self.par + 1e-9
        self.results.append((desk.level.rung, passed, desk.clicks, self.par))
        if self.adaptive:
            self.rung = self.rung + 1 if passed else max(1, self.rung - 1)
        self.phase = 'judged'
        self.feedback_until = self.clock() + FEEDBACK
        held = sum(desk.met(goal) for goal in desk.goals)
        self.message = (_('%d of %d settings in %d clicks; par was %s')
                        % (held, len(desk.goals), desk.clicks,
                           _points(self.par)))
        self.verdict_shown = (passed, self.message)
        self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        self.desk = None
        tally = self.score()
        self.message = (_('%d of %d under par   highest rung passed %d')
                        % (tally['passed'], tally['trials'],
                           tally['best_rung']))
        self._redraw()

    def score(self) -> Dict[str, float]:
        trials = len(self.results)
        return {
            'trials': trials,
            'passed': sum(1 for r in self.results if r[1]),
            'best_rung': max((r[0] for r in self.results if r[1]),
                             default=0),
            'mean_clicks': (sum(r[2] for r in self.results) / trials
                            if trials else 0.0),
        }

    def update(self, dt: float) -> None:
        if self.phase == 'judged' and self.clock() >= self.feedback_until:
            self._next_trial()

    # --- drawing primitives ----------------------------------------------

    def _clear_drawn(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []

    def _group(self, order: int) -> pyglet.graphics.Group:
        return pyglet.graphics.Group(order=order)

    def _rect(self, rect, colour, group, edge=None) -> None:
        """A rectangle in screen units, cut to the screen: a window
        hanging off the edge must not paint over the card."""
        x, y, w, h = rect
        x0, y0 = max(0.0, x), max(0.0, y)
        x1 = min(float(model.SCREEN_W), x + w)
        y1 = min(float(model.SCREEN_H), y + h)
        if x1 <= x0 or y1 <= y0:
            return
        px, py = self.to_pixels(x0, y1)
        _l, _t, scale = self._frame()
        width, height = (x1 - x0) * scale, (y1 - y0) * scale
        self.drawn.append(pyglet.shapes.Rectangle(
            px, py, width, height, color=colour, batch=self.batch,
            group=group))
        if edge is not None:
            self.drawn.append(pyglet.shapes.Box(
                px, py, width, height, thickness=1, color=edge,
                batch=self.batch, group=group))

    def _words(self, words, x, y, group, size=13.0, colour=INK,
               anchor='left', bold=False) -> None:
        if not 0 <= x < model.SCREEN_W - 8:
            return
        _l, _t, scale = self._frame()
        px, py = self.to_pixels(x, y)
        self.drawn.append(pyglet.text.Label(
            words, font_size=max(5.0, size * scale), x=px, y=py,
            anchor_x=anchor, anchor_y='center', color=colour + (255,),
            weight='bold' if bold else 'normal', batch=self.batch,
            group=group, font_name=FONTLIST))

    def _button(self, rect, words, group, text, colour=BUTTON, ink=INK,
                bold=False, size=12.0) -> None:
        self._rect(rect, colour, group, PANEL_EDGE)
        cx, cy = model.centre(rect)
        self._words(words, cx, cy, text, anchor='center', colour=ink,
                    bold=bold, size=size)

    def _place_pointer(self) -> None:
        live = self.desk is not None and self.phase == 'working'
        self.pointer.visible = self.pointer_edge.visible = live
        if live:
            # Every corner, not just the first: a pyglet triangle's
            # position moves only its first vertex.
            px, py = self.to_pixels(*self.desk.pointer)
            size = self.pointer_size
            if self.desk.held is not None:
                size *= 0.8           # pressed: the arrow shrinks a little
            for shape, grow in ((self.pointer, 0.0),
                                (self.pointer_edge, 3.0)):
                shape.x, shape.y = px - grow * 0.6, py + grow
                shape.x2, shape.y2 = px - grow * 0.6, py - size - grow * 1.6
                shape.x3, shape.y3 = (px + size * 0.62 + grow * 1.4,
                                      py - size * 0.62 - grow * 0.4)

    # --- drawing the desktop ---------------------------------------------

    def _redraw(self) -> None:
        self._clear_drawn()
        desk = self.desk
        if desk is not None and self.phase in ('working', 'judged'):
            self._rect((0, 0, model.SCREEN_W, model.SCREEN_H), DESK,
                       self._group(0))
            self._draw_desktop_icons(4)
            for depth, win in enumerate(desk.order):
                if win.shown:
                    self._draw_window(win, 10 + depth * 4)
            self._draw_taskbar(600)
            if desk.menu is not None:
                self._draw_menu(700)
            if desk.start_open:
                self._draw_start(700)
            if desk.dialog is not None:
                self._draw_dialog(720)
            if desk.dropdown is not None:
                self._draw_dropdown(780)
            if desk.popup is not None:
                self._draw_popup(820)
            self._draw_card()
        self._place_pointer()
        self._update_labels()

    def _title_bar(self, win, colour, parts, text) -> None:
        self._rect(model.title_rect(win), colour, parts)
        self._words(win.title, win.x + 12, win.y + model.TITLE_H / 2, text,
                    colour=WHITE if not win.pinned else INK, bold=True)
        self._button(model.minimise_rect(win), '–', parts, text,
                     bold=True)
        self._button(model.close_rect(win), '×', parts, text, bold=True)

    # --- icons -------------------------------------------------------------

    def _glyph(self, kind: str, rect, parts, text, name: str = '',
               faded: bool = False, file_kind: str = '') -> None:
        """An icon in the top of *rect*, with its name beneath."""
        x, y, w, h = rect
        size = min(w, h) * 0.5
        gx, gy = x + (w - size) / 2, y + 6
        if kind == 'folder':
            self._rect((gx, gy + size * 0.12, size * 0.45, size * 0.18),
                       FOLDER, parts)
            self._rect((gx, gy + size * 0.25, size, size * 0.7),
                       FOLDER, parts, PANEL_EDGE)
        elif kind == 'file':
            self._rect((gx + size * 0.15, gy, size * 0.7, size * 0.95),
                       WHITE, parts, PANEL_EDGE)
            self._rect((gx + size * 0.15, gy + size * 0.6, size * 0.7,
                        size * 0.2), FILE_BANDS.get(file_kind, GREY), text)
        elif kind == 'trash':
            self._rect((gx + size * 0.1, gy, size * 0.8, size * 0.14),
                       GREY, parts, PANEL_EDGE)
            self._rect((gx + size * 0.2, gy + size * 0.18, size * 0.6,
                        size * 0.78), (200, 204, 212), parts, PANEL_EDGE)
        else:
            self._rect((gx, gy, size, size), APP_TILE, parts, PANEL_EDGE)
            self._words(name[:1], gx + size / 2, gy + size / 2, text,
                        colour=WHITE, anchor='center', bold=True, size=16.0)
        if faded:
            self._rect((gx, gy, size, size), (230, 232, 236), text)
        shown = name if len(name) <= 10 else name[:9] + '…'
        self._words(shown, x + w / 2, y + h - 12, text, size=10.0,
                    anchor='center')

    def _draw_desktop_icons(self, base: int) -> None:
        desk = self.desk
        parts, text = self._group(base), self._group(base + 1)
        for item, rect in desk.desktop_icons():
            key = model._icon_key(item)
            if desk.picked == key:
                self._rect(rect, (110, 140, 180), parts)
            if item[0] == 'explorer':
                self._glyph('app', rect, parts, text, model.EXPLORER)
            elif item[0] == 'trash':
                self._glyph('trash', rect, parts, text, _('Trash'))
            elif item[0] == 'app':
                self._glyph('app', rect, parts, text, item[1].title)
            else:
                node = item[1]
                self._glyph('folder' if node.folder else 'file', rect,
                            parts, text, node.name,
                            file_kind=node.kind)

    def _draw_explorer(self, win: model.Window, body, parts, text) -> None:
        desk = self.desk
        place = win.places[win.place]
        for name, rect in model.tool_rects(win):
            usable = ((name == 'Back' and place.history)
                      or (name == 'Up' and place.path.parent is not None)
                      or (name in ('Cut', 'Delete')
                          and place.selected is not None)
                      or (name == 'Paste' and desk.clipboard is not None))
            self._button(rect, _(name), parts, text, size=10.0,
                         ink=INK if usable else GREY)
        for index, rect in enumerate(model.place_tab_rects(win)):
            active = index == win.place
            self._button(rect, win.places[index].path.name, parts, text,
                         colour=PANEL if active else BUTTON, bold=active,
                         size=10.0)
        if len(win.places) < model.MOST_TABS:
            self._button(model.plus_rect(win), '+', parts, text, bold=True)
        px, py, pw, ph = model.path_rect(win)
        self._rect((px, py, pw, ph), WHITE, parts, PANEL_EDGE)
        self._words(_short_path(place.path), px + 6, py + ph / 2, text,
                    size=10.0)
        for index, rect in enumerate(model.sidebar_rects(win)):
            here = place.path.ident == index
            self._rect(rect, SELECTED if here else PANEL, parts)
            self._words(_(model.PLACES[index]), rect[0] + 8,
                        rect[1] + rect[3] / 2, text, size=11.0,
                        bold=here)
        if not place.path.children:
            gx, gy, gw, _gh = model.grid_area(win)
            self._words(_('This folder is empty'), gx + gw / 2, gy + 30,
                        text, anchor='center', colour=GREY, size=11.0)
        for node, rect in desk.icon_rects(win):
            if place.selected is node:
                self._rect(rect, SELECTED, parts)
            self._glyph('folder' if node.folder else 'file', rect, parts,
                        text, node.name, faded=desk.clipboard is node,
                        file_kind=node.kind)
        if desk.ex_scrolls(win):
            up, down = model.ex_scroll_rects(win)
            self._button(up, '▲', parts, text, size=10.0)
            self._button(down, '▼', parts, text, size=10.0)

    def _draw_window(self, win: model.Window, base: int) -> None:
        body, parts, text = (self._group(base), self._group(base + 1),
                             self._group(base + 2))
        if win.kind == 'explorer':
            self._rect((win.x, win.y, win.w, win.h), PANEL, body, PANEL_EDGE)
            self._title_bar(win, (40, 60, 90), parts, text)
            self._draw_explorer(win, body, parts, text)
            return
        if win.pinned:
            self._rect((win.x, win.y, win.w, win.h), NOTE, body, PANEL_EDGE)
            self._title_bar(win, (236, 200, 80), parts, text)
            self._words(win.note, win.x + 14, win.y + model.TITLE_H + 30,
                        text, size=13.0)
            return
        self._rect((win.x, win.y, win.w, win.h), PANEL, body, PANEL_EDGE)
        self._title_bar(win, TITLE_COLOURS[win.ident % len(TITLE_COLOURS)],
                        parts, text)
        for index, rect in enumerate(model.menu_rects(win)):
            self._words(win.menus[index][0], rect[0] + 8,
                        rect[1] + rect[3] / 2, text)
        for index, rect in enumerate(model.tab_rects(win)):
            active = index == win.active
            self._button(rect, model.TABS[index], parts, text,
                         colour=PANEL if active else BUTTON, bold=active)
        tab = win.active
        for control in win.tabs[tab]:
            self._draw_control(control, win.w, parts, text)
        if win.scrolls(tab):
            up, down = model.scroll_rects(win)
            self._button(up, '▲', parts, text, size=10.0)
            self._button(down, '▼', parts, text, size=10.0)
        if win.apply:
            pending = any(c.shown != c.value for page in win.tabs
                          for c in page)
            self._button(model.apply_rect(win), _('Apply'), parts, text,
                         colour=ACCENT if pending else BUTTON,
                         ink=WHITE if pending else INK)
        # The corner to resize by: three short diagonal steps.
        gx, gy, gw, gh = model.grip_rect(win)
        for step in range(3):
            inset = 4 + step * 4
            self._rect((gx + inset, gy + gh - 3, gw - inset - 2, 2),
                       PANEL_EDGE, text)

    def _draw_control(self, control: model.Control, width: float,
                      parts, text) -> None:
        row = self.desk.row_rect(control)
        if row is None:
            return
        enabled = control.enabled
        ink = INK if enabled else GREY
        x, y, _w, h = row
        if enabled or control.requires is None:
            self._words(control.label, x + 14, y + h / 2, text, colour=ink)
        else:
            other, wanted = control.requires
            self._words(control.label, x + 14, y + h * 0.32, text,
                        colour=ink)
            self._words(_('needs %s: %s') % (other.label,
                                             other.word(wanted)),
                        x + 14, y + h * 0.75, text, size=9.0, colour=ink)
        rect = model.widget_rect(x, y, width)
        regions = model.parts(control, rect)
        value = control.shown
        kind = control.kind
        if kind == 'toggle':
            part = regions[0]
            self._rect(part, (ON if value else OFF) if enabled else BUTTON,
                       parts, PANEL_EDGE)
            knob = (part[0] + (part[2] - part[3] if value else 0) + 3,
                    part[1] + 3, part[3] - 6, part[3] - 6)
            self._rect(knob, WHITE, text)
        elif kind == 'dropdown':
            part = regions[0]
            self._rect(part, WHITE, parts, PANEL_EDGE)
            self._words(control.word(value) + '  ▾', part[0] + 8,
                        part[1] + part[3] / 2, text, colour=ink)
        elif kind == 'stepper':
            minus, plus = regions
            self._button(minus, '−', parts, text, bold=True)
            self._button(plus, '+', parts, text, bold=True)
            self._words(control.word(value), (minus[0] + minus[2] + plus[0])
                        / 2, minus[1] + minus[3] / 2, text, anchor='center',
                        colour=ink, bold=True)
        elif kind == 'colour':
            for index, part in enumerate(regions):
                px, py, pw, ph = part
                if index == value:
                    self._rect(part, INK if enabled else GREY, parts)
                swatch = (px + 3, py + 3, pw - 6, ph - 6)
                rgb = model.colour_of(control.words[index])
                self._rect(swatch, rgb if enabled else
                           tuple((c + 200) // 2 for c in rgb), text)
        elif kind == 'choice':
            for index, part in enumerate(regions):
                picked = index == value
                self._button(part, control.word(index), parts, text,
                             colour=(ACCENT if enabled else GREY)
                             if picked else BUTTON,
                             ink=WHITE if picked else ink, size=10.0)
        else:
            left, top, w, h = rect
            self._rect((left, top + h / 2 - 2, w, 4), GREY, parts)
            for index, part in enumerate(regions):
                cx = part[0] + part[2] / 2
                size = 14 if index == value else 6
                self._rect((cx - size / 2, top + h / 2 - size / 2, size,
                            size), (ACCENT if enabled else GREY)
                           if index == value else PANEL_EDGE, text)
            self._words(control.word(value), left + w + 6, top + h / 2,
                        text, size=10.0, colour=ink)

    def _draw_taskbar(self, base: int) -> None:
        desk = self.desk
        group, parts, text = (self._group(base), self._group(base + 1),
                              self._group(base + 2))
        self._rect((0, model.WORK_H, model.SCREEN_W, model.TASKBAR_H),
                   TASKBAR, group)
        self._button(model.START_RECT, _('Start'), parts, text,
                     colour=ACCENT, ink=WHITE, bold=True)
        tops = [w for w in desk.order if w.shown and not w.pinned]
        for win, rect in desk.taskbar_buttons():
            front = bool(tops) and tops[-1] is win
            self._button(rect, win.title, parts, text,
                         colour=(110, 118, 136) if front else TASK_BUTTON,
                         ink=GREY if win.minimised else WHITE, size=11.0)
        self._button(model.DONE_RECT, _('Done'), parts, text, colour=ON,
                     ink=WHITE, bold=True)

    def _draw_menu(self, base: int) -> None:
        desk = self.desk
        win, index, sub = desk.menu
        group, text = self._group(base), self._group(base + 1)
        items = win.menus[index][1]
        for which, rect in enumerate(desk.menu_items()):
            item = items[which]
            cascades = isinstance(item, model.Submenu)
            self._rect(rect, BUTTON if sub == which else WHITE, group,
                       PANEL_EDGE)
            self._words(item.name if cascades else item.title + '…',
                        rect[0] + 10, rect[1] + rect[3] / 2, text)
            if cascades:
                self._words('▸', rect[0] + rect[2] - 16,
                            rect[1] + rect[3] / 2, text)
        if sub is not None:
            for which, rect in enumerate(desk.submenu_items()):
                self._rect(rect, WHITE, group, PANEL_EDGE)
                self._words(items[sub].dialogs[which].title + '…',
                            rect[0] + 10, rect[1] + rect[3] / 2, text)

    def _draw_start(self, base: int) -> None:
        desk = self.desk
        group, parts, text = (self._group(base), self._group(base + 1),
                              self._group(base + 2))
        px, py, pw, ph = model.START_PANEL
        self._rect((px, py, pw, ph), (44, 50, 62), group, INK)
        self._words(_('All apps') if desk.start_all else _('Pinned'),
                    px + 14, py + 22, text, colour=WHITE, bold=True)
        self._button(model.all_apps_rect(),
                     _('‹ Back') if desk.start_all else _('All apps ›'),
                     parts, text, size=11.0)
        for win, rect in desk.start_items():
            if desk.start_all:
                self._rect(rect, (60, 68, 84), parts)
                self._words(win.title, rect[0] + 12, rect[1] + rect[3] / 2,
                            text, colour=WHITE)
            else:
                self._rect(rect, (60, 68, 84), parts)
                self._glyph('app', rect, parts, text, win.title)

    def _draw_dialog(self, base: int) -> None:
        desk = self.desk
        dialog = desk.dialog
        body, parts, text = (self._group(base), self._group(base + 1),
                             self._group(base + 2))
        x, y, w, h = desk.dialog_rect()
        self._rect((x, y, w, h), PANEL, body, PANEL_EDGE)
        self._rect((x, y, w, model.TITLE_H), (80, 84, 96), parts)
        self._words(dialog.title, x + 12, y + model.TITLE_H / 2, text,
                    colour=WHITE, bold=True)
        for control in dialog.controls:
            self._draw_control(control, model.DIALOG_W, parts, text)
        cancel, ok = desk.dialog_buttons()
        self._button(cancel, _('Cancel'), parts, text)
        self._button(ok, _('OK'), parts, text, bold=True)

    def _draw_dropdown(self, base: int) -> None:
        control = self.desk.dropdown
        rect = self.desk.control_rect(control)
        group, text = self._group(base), self._group(base + 1)
        for value, item in enumerate(model.dropdown_items(rect, control)):
            picked = value == control.shown
            self._rect(item, ACCENT if picked else WHITE, group, PANEL_EDGE)
            self._words(control.word(value), item[0] + 8,
                        item[1] + item[3] / 2, text,
                        colour=WHITE if picked else INK)

    def _draw_popup(self, base: int) -> None:
        desk = self.desk
        popup = desk.popup
        body, parts, text = (self._group(base), self._group(base + 1),
                             self._group(base + 2))
        x, y, w, h = model.POPUP_RECT
        self._rect((x, y, w, h), PANEL, body, INK)
        self._rect((x, y, w, model.TITLE_H), WARN, parts)
        title = desk.windows[popup.window].title
        self._words(_('%s update') % title, x + 12, y + model.TITLE_H / 2,
                    text, colour=WHITE, bold=True)
        self._words(_('Reset %s to its defaults?') % title,
                    x + 20, y + 62, text)
        safe, reset = model.popup_buttons(popup.safe_left)
        self._button(safe, _('Not now'), parts, text, bold=True)
        self._button(reset, _('Restore'), parts, text)

    def _draw_card(self) -> None:
        desk = self.desk
        window = state.window
        left, top, scale = self._frame()
        x = left + model.SCREEN_W * scale + window.width * 0.02
        size = calc_fontsize(11)
        line = size * 2.1
        group = self._group(950)
        self.drawn.append(pyglet.text.Label(
            _('Set these:'), font_size=calc_fontsize(13), weight='bold',
            x=x, y=top - line * 0.5, anchor_x='left', anchor_y='center',
            color=self.textcolor, batch=self.batch, group=group,
            font_name=FONTLIST))
        for index, (ident, value) in enumerate(desk.goals):
            control = desk.controls[ident]
            where = (control.dialog.title if control.dialog
                     else control.window.title)
            mark = '✓ ' if desk.met((ident, value)) else '•  '
            y = top - line * (index + 1.5)
            words = pyglet.text.Label(
                '%s%s › %s: %s' % (mark, where, control.label,
                                   control.word(value)),
                font_size=size, x=x, y=y, anchor_x='left',
                anchor_y='center', color=self.textcolor, batch=self.batch,
                group=group, font_name=FONTLIST)
            self.drawn.append(words)
            if control.kind == 'colour':
                chip = size * 1.2
                self.drawn.append(pyglet.shapes.Rectangle(
                    x + words.content_width + 8, y - chip / 2, chip, chip,
                    color=model.colour_of(control.words[value]),
                    batch=self.batch, group=group))
        first = len(desk.goals)
        lines: list = []
        for index, (node, dest) in enumerate(desk.moves):
            mark = '✓ ' if node.parent is dest else '•  '
            if dest.ident == model.TRASH:
                words = _('Delete %s') % node.name
            elif node.parent.ident == model.TRASH \
                    and node.parent is not dest and index >= 0 \
                    and _was_trashed(desk, node):
                words = _('Restore %s → %s') % (node.name,
                                                _short_path(dest))
            else:
                words = _('Move %s → %s') % (node.name, _short_path(dest))
            # Two lines each: what to do, and where the file is now.
            y = top - line * (first + 1.5) - line * 1.75 * index
            lines.append(self._card_line(mark + words, x, y, size, group))
            if node.parent is not dest:
                lines.append(self._card_line(
                    _('now in %s') % _short_path(node.parent),
                    x + size * 2.2, y - line * 0.6, size * 0.8, group, 0.8))
        # One size for every file line, the smallest any of them needed.
        if lines:
            least = min(line.font_size / scale for line, scale in lines)
            for line, scale in lines:
                line.font_size = least * scale

    def _card_line(self, words: str, x: float, y: float, size: float,
                   group, scale: float = 1.0):
        """A line of the card, shrunk until it fits the window."""
        line = pyglet.text.Label(
            words, font_size=size, x=x, y=y, anchor_x='left',
            anchor_y='center', color=self.textcolor, batch=self.batch,
            group=group, font_name=FONTLIST)
        room = state.window.width - x - 8
        while line.content_width > room and line.font_size > 6:
            line.font_size = line.font_size - 0.5
        self.drawn.append(line)
        return line, scale

    def _update_labels(self) -> None:
        self.status.text = self.message
        desk = self.desk
        if desk is None or self.phase not in ('working', 'judged'):
            self.facts.text = ''
            return
        self.facts.text = '  '.join([
            _('rung %d  %d/%d') % (desk.level.rung, self.trial,
                                   self.total_trials),
            _('clicks %d') % desk.clicks,
            _('par %s') % _points(self.par),
            _('out of clicks at %d') % self.budget])

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Desktop.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_mouse_release,
                                     self.on_mouse_motion,
                                     self.on_mouse_drag, self.on_draw)
        self._clear_drawn()
        Desktop.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='computer')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif self.phase == 'working':
            arrows = {key.UP: 0, key.DOWN: 1, key.LEFT: 2, key.RIGHT: 3}
            if symbol in arrows:
                size = (0 if modifiers & key.MOD_SHIFT else
                        2 if modifiers & key.MOD_ALT else 1)
                self.steer(arrows[symbol] * 3 + size)
            elif symbol == key.SPACE:
                self.click()
            elif symbol == key.D:
                if self.desk.held is None:
                    self.press()
                else:
                    self.release()
            elif symbol in (key.RETURN, key.ENTER):
                self.finish_round()
        return pyglet.event.EVENT_HANDLED

    def _on_screen(self, x: int, y: int) -> Optional[Tuple[float, float]]:
        mx, my = self.to_model(x, y)
        if 0 <= mx < model.SCREEN_W and 0 <= my < model.SCREEN_H:
            return mx, my
        return None

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        if self.phase == 'working' and self.desk is not None:
            point = self._on_screen(x, y)
            if point is not None:
                self.desk.pointer = point
                self._place_pointer()

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int,
                      buttons: int, modifiers: int) -> None:
        self.on_mouse_motion(x, y, dx, dy)

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase == 'working' and button == mouse.LEFT:
            point = self._on_screen(x, y)
            if point is not None:
                self._pressed_at = (x, y)
                self.press(*point)
        elif self.phase in ('ready', 'done') and button == mouse.LEFT:
            self.start_run()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_release(self, x: int, y: int, button: int,
                         modifiers: int) -> bool:
        if self.phase == 'working' and button == mouse.LEFT \
                and self.desk.held is not None:
            # A hand moves a few pixels while it clicks: that is a click.
            px, py = getattr(self, '_pressed_at', (x, y))
            if abs(x - px) <= JITTER and abs(y - py) <= JITTER:
                x, y = px, py
            mx, my = self.to_model(x, y)
            self.release(max(0, min(model.SCREEN_W - 1, mx)),
                         max(0, min(model.SCREEN_H - 1, my)))
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


def _short_path(node: model.Node, keep: int = 3) -> str:
    """A folder's path, Home left off and only its last few folders."""
    names = [n.name for n in node.chain() if n.ident != model.HOME]
    if not names:
        return model.PLACES[model.HOME]
    if len(names) > keep:
        names = ['…'] + names[-keep:]
    return ' / '.join(names)


def _was_trashed(desk, node) -> bool:
    """Whether the card asks for *node* back out of the Trash."""
    return any(n is node and d.ident != model.TRASH for n, d in desk.moves)


def _points(value: float) -> str:
    return ('%d' % value) if float(value).is_integer() else ('%.1f' % value)
