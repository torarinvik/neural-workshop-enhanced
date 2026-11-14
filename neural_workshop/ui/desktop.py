# -*- coding: utf-8 -*-
"""Desktop: operate a small computer to reach the settings on a card.

The screen is drawn here and nowhere else: windows with title bars,
menu bars, tabs, rows of controls, scroll arrows and Apply buttons, and
over them menus, dropdown lists and dialogs, and a taskbar with Done.
The card on the right lists the settings to reach, each named by its
window -- or its dialog -- and ticked once it holds. Click Done, or
press Enter, when they all do. Every click costs a point, whatever it
hits; moving the pointer is free. :mod:`neural_workshop.desktop` has
the model, the ladder and the reference, and decides what every click
does, so the screen and the reference cannot disagree.

People click with the mouse. The arrow keys move the drawn pointer too
(Shift for a long step, Alt for a short one) and Space clicks, which is
exactly how the agent plays: twelve ports move the pointer by a long,
a medium or a short step in each direction, one clicks and one is Done.

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
CLICK, DONE = 12, 13
PORTS = 14

TITLE_COLOURS = ((58, 98, 170), (150, 70, 60), (60, 130, 90),
                 (120, 80, 150), (170, 120, 40), (60, 120, 140))
PANEL = (244, 245, 248)
PANEL_EDGE = (90, 96, 110)
DESK = (70, 102, 130)
TASKBAR = (34, 38, 46)
ACCENT = (52, 110, 220)
ON = (60, 160, 90)
OFF = (176, 180, 188)
GREY = (150, 152, 158)
BUTTON = (222, 226, 234)
INK = (20, 22, 28)
POINTER = (255, 255, 255)


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
        self.message = _('Press Space to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_mouse_motion, self.on_draw)
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
            _('arrows: pointer (Shift long, Alt short)   Space: click   '
              'Enter: done   Esc: menu'),
            calc_fontsize(12), from_bottom_edge(26))
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        _left, _top, scale = self._frame()
        self.pointer_size = max(10.0, 22 * scale)
        self.pointer = pyglet.shapes.Triangle(
            0, 0, 0, 0, 0, 0, color=POINTER, batch=self.batch,
            group=pyglet.graphics.Group(order=900))
        self.pointer_edge = pyglet.shapes.Triangle(
            0, 0, 0, 0, 0, 0, color=INK, batch=self.batch,
            group=pyglet.graphics.Group(order=899))
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.desk = None
        self.phase = 'ready'
        self.message = _('Press Space to start')
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
        """One agent port: move the pointer, click, or Done."""
        if self.phase != 'working':
            return
        if port < CLICK:
            dx, dy = DIRECTIONS[port // 3]
            step = model.STEPS[port % 3]
            self.desk.move(dx * step, dy * step)
            self._place_pointer()
        elif port == CLICK:
            self.click()
        else:
            self.finish_round()

    def click(self, x: Optional[float] = None,
              y: Optional[float] = None) -> None:
        if self.phase != 'working':
            return
        self.desk.click(x, y)
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

    # --- drawing ---------------------------------------------------------

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
        x, y, w, h = rect
        px, py = self.to_pixels(x, y + h)
        _l, _t, scale = self._frame()
        self.drawn.append(pyglet.shapes.Rectangle(
            px, py, w * scale, h * scale, color=colour, batch=self.batch,
            group=group))
        if edge is not None:
            self.drawn.append(pyglet.shapes.Box(
                px, py, w * scale, h * scale, thickness=1, color=edge,
                batch=self.batch, group=group))

    def _words(self, words, x, y, group, size=13.0, colour=INK,
               anchor='left', bold=False) -> None:
        _l, _t, scale = self._frame()
        px, py = self.to_pixels(x, y)
        self.drawn.append(pyglet.text.Label(
            words, font_size=max(5.0, size * scale), x=px, y=py,
            anchor_x=anchor, anchor_y='center', color=colour + (255,),
            weight='bold' if bold else 'normal', batch=self.batch,
            group=group, font_name=FONTLIST))

    def _place_pointer(self) -> None:
        live = self.desk is not None and self.phase == 'working'
        self.pointer.visible = self.pointer_edge.visible = live
        if live:
            # Every corner, not just the first: a pyglet triangle's
            # position moves only its first vertex.
            px, py = self.to_pixels(*self.desk.pointer)
            size = self.pointer_size
            for shape, grow in ((self.pointer, 0.0),
                                (self.pointer_edge, 3.0)):
                shape.x, shape.y = px - grow * 0.6, py + grow
                shape.x2, shape.y2 = px - grow * 0.6, py - size - grow * 1.6
                shape.x3, shape.y3 = (px + size * 0.62 + grow * 1.4,
                                      py - size * 0.62 - grow * 0.4)

    def _redraw(self) -> None:
        self._clear_drawn()
        desk = self.desk
        if desk is not None and self.phase in ('working', 'judged'):
            back = self._group(0)
            self._rect((0, 0, model.SCREEN_W, model.SCREEN_H), DESK, back)
            for depth, win in enumerate(desk.order):
                self._draw_window(win, 10 + depth * 4)
            self._draw_taskbar()
            if desk.menu is not None:
                self._draw_menu(700)
            if desk.dialog is not None:
                self._draw_dialog(720)
            if desk.dropdown is not None:
                self._draw_dropdown(780)
            self._draw_card()
        self._place_pointer()
        self._update_labels()

    def _draw_window(self, win: model.Window, base: int) -> None:
        body, parts, text = (self._group(base), self._group(base + 1),
                             self._group(base + 2))
        self._rect((win.x, win.y, win.w, win.h), PANEL, body, PANEL_EDGE)
        colour = TITLE_COLOURS[win.ident % len(TITLE_COLOURS)]
        self._rect(model.title_rect(win), colour, parts)
        self._words(win.title, win.x + 12, win.y + model.TITLE_H / 2, text,
                    colour=(255, 255, 255), bold=True)
        for index, rect in enumerate(model.menu_rects(win)):
            self._words(win.menus[index][0], rect[0] + 8,
                        rect[1] + rect[3] / 2, text)
        for index, rect in enumerate(model.tab_rects(win)):
            active = index == win.active
            self._rect(rect, PANEL if active else BUTTON, parts, PANEL_EDGE)
            self._words(model.TABS[index], rect[0] + rect[2] / 2,
                        rect[1] + rect[3] / 2, text, bold=active,
                        anchor='center')
        tab = win.active
        for control in win.tabs[tab]:
            self._draw_control(control, win.w, parts, text)
        if win.scrolls(tab):
            up, down = model.scroll_rects(win)
            for rect, arrow in ((up, '▲'), (down, '▼')):
                self._rect(rect, BUTTON, parts, PANEL_EDGE)
                self._words(arrow, rect[0] + rect[2] / 2,
                            rect[1] + rect[3] / 2, text, anchor='center')
        if win.apply:
            rect = model.apply_rect(win)
            pending = any(c.shown != c.value for page in win.tabs
                          for c in page)
            self._rect(rect, ACCENT if pending else BUTTON, parts,
                       PANEL_EDGE)
            self._words(_('Apply'), rect[0] + rect[2] / 2,
                        rect[1] + rect[3] / 2, text, anchor='center',
                        colour=(255, 255, 255) if pending else INK)

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
        if control.kind == 'toggle':
            part = regions[0]
            self._rect(part, (ON if value else OFF) if enabled else BUTTON,
                       parts, PANEL_EDGE)
            knob = (part[0] + (part[2] - part[3] if value else 0) + 3,
                    part[1] + 3, part[3] - 6, part[3] - 6)
            self._rect(knob, (255, 255, 255), text)
        elif control.kind == 'dropdown':
            part = regions[0]
            self._rect(part, (255, 255, 255), parts, PANEL_EDGE)
            self._words(control.word(value) + '  ▾', part[0] + 8,
                        part[1] + part[3] / 2, text, colour=ink)
        elif control.kind == 'choice':
            for index, part in enumerate(regions):
                picked = index == value
                self._rect(part, ACCENT if picked and enabled else
                           (GREY if picked else BUTTON), parts, PANEL_EDGE)
                self._words(control.word(index), part[0] + part[2] / 2,
                            part[1] + part[3] / 2, text, size=10.0,
                            anchor='center',
                            colour=(255, 255, 255) if picked else ink)
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

    def _draw_taskbar(self) -> None:
        group, text = self._group(600), self._group(601)
        top = model.SCREEN_H - model.TASKBAR_H
        self._rect((0, top, model.SCREEN_W, model.TASKBAR_H), TASKBAR, group)
        self._rect(model.DONE_RECT, ON, text)
        x, y, w, h = model.DONE_RECT
        self._words(_('Done'), x + w / 2, y + h / 2, self._group(602),
                    colour=(255, 255, 255), anchor='center', bold=True)

    def _draw_menu(self, base: int) -> None:
        desk = self.desk
        win, index = desk.menu
        group, text = self._group(base), self._group(base + 1)
        for item, rect in enumerate(desk.menu_items()):
            self._rect(rect, (255, 255, 255), group, PANEL_EDGE)
            self._words(win.menus[index][1][item].title + '…', rect[0] + 10,
                        rect[1] + rect[3] / 2, text)

    def _draw_dialog(self, base: int) -> None:
        desk = self.desk
        dialog = desk.dialog
        body, parts, text = (self._group(base), self._group(base + 1),
                             self._group(base + 2))
        x, y, w, h = desk.dialog_rect()
        self._rect((x, y, w, h), PANEL, body, PANEL_EDGE)
        self._rect((x, y, w, model.TITLE_H), (80, 84, 96), parts)
        self._words(dialog.title, x + 12, y + model.TITLE_H / 2, text,
                    colour=(255, 255, 255), bold=True)
        for control in dialog.controls:
            self._draw_control(control, model.DIALOG_W, parts, text)
        cancel, ok = desk.dialog_buttons()
        for rect, words in ((cancel, _('Cancel')), (ok, _('OK'))):
            self._rect(rect, BUTTON, parts, PANEL_EDGE)
            self._words(words, rect[0] + rect[2] / 2, rect[1] + rect[3] / 2,
                        text, anchor='center', bold=words == _('OK'))

    def _draw_dropdown(self, base: int) -> None:
        control = self.desk.dropdown
        rect = self.desk.control_rect(control)
        group, text = self._group(base), self._group(base + 1)
        for value, item in enumerate(model.dropdown_items(rect, control)):
            self._rect(item, ACCENT if value == control.shown
                       else (255, 255, 255), group, PANEL_EDGE)
            self._words(control.word(value), item[0] + 8,
                        item[1] + item[3] / 2, text,
                        colour=(255, 255, 255) if value == control.shown
                        else INK)

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
            self.drawn.append(pyglet.text.Label(
                '%s%s › %s: %s' % (mark, where, control.label,
                                   control.word(value)),
                font_size=size, x=x, y=top - line * (index + 1.5),
                anchor_x='left', anchor_y='center', color=self.textcolor,
                batch=self.batch, group=group, font_name=FONTLIST))

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
                                     self.on_mouse_motion, self.on_draw)
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
            elif symbol in (key.RETURN, key.ENTER):
                self.finish_round()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        if self.phase == 'working' and self.desk is not None:
            mx, my = self.to_model(x, y)
            if 0 <= mx < model.SCREEN_W and 0 <= my < model.SCREEN_H:
                self.desk.pointer = (mx, my)
                self._place_pointer()

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase != 'working' or button != mouse.LEFT:
            return pyglet.event.EVENT_HANDLED
        mx, my = self.to_model(x, y)
        if 0 <= mx < model.SCREEN_W and 0 <= my < model.SCREEN_H:
            self.click(mx, my)
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


def _points(value: float) -> str:
    return ('%d' % value) if float(value).is_integer() else ('%.1f' % value)
