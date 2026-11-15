# -*- coding: utf-8 -*-
"""Spreadsheet on screen, through Browser's pointer and drawing.

The filter bar, the sortable headers (an arrow shows the sort), the
rows, the sum buttons and the status bar on the left; the answer box,
keypad and Submit on the right. Digits, Backspace and Enter work from
the keyboard too, each counted as a click.

For the agent boundary, Browser's: ports 0-11 move the pointer, port 12
clicks, ports 13 and 14 scroll the rows.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional

from pyglet.window import key

from .. import browser, sheet as model
from ..i18n import _
from . import browser as shopui
from .browser import Browser

CLICK, SCROLL_UP, SCROLL_DOWN = shopui.CLICK, shopui.SCROLL_UP, \
    shopui.SCROLL_DOWN
GRID = (214, 218, 226)
HEAD = (232, 236, 244)
ON = (40, 90, 220)
STRIPE = (247, 248, 251)


class Spreadsheet(Browser):
    """Answer a question about a table, with its tools, in few clicks."""

    instance: Optional['Spreadsheet'] = None

    TITLE = 'Spreadsheet'
    TASK_ID = 'spreadsheet'
    PREFIX = 'SPREADSHEET'
    CATEGORY = 'computer'
    FOOTNOTE = _('click   wheel or Up/Down: scroll   digits, Backspace, '
                 'Enter: answer   Esc: menu')

    def __init__(self) -> None:
        self.sheet: Optional[model.Sheet] = None
        super().__init__()

    def _clear_trial(self) -> None:
        self.sheet = None
        self.session = None

    def _deal(self) -> bool:
        puzzle = model.deal(self.rung, rng=self.rng)
        self.sheet = model.Sheet(puzzle)
        self.session = self.sheet
        self.par = model.par(puzzle)
        self.message = puzzle.question
        return True

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase != self.PLAY:
            return
        if port < CLICK:
            dx, dy = browser.DIRECTIONS[port // 3]
            step = browser.STEPS[port % 3]
            self.sheet.move(dx * step, dy * step)
            self._redraw()
        elif port == CLICK:
            self.click()
        elif port == SCROLL_UP:
            self.scroll(-1)
        elif port == SCROLL_DOWN:
            self.scroll(1)

    def click(self, x: Optional[float] = None,
              y: Optional[float] = None) -> None:
        if self.phase != self.PLAY:
            return
        self.sheet.click(x, y)
        self._after()

    def _after(self) -> None:
        sheet = self.sheet
        if sheet.submitted is None:
            self._redraw()
            return
        answer = sheet.puzzle.answer
        right = sheet.submitted == answer
        cheap = sheet.clicks <= self.par
        if right and cheap:
            words = _('Right: %d, in %d clicks (par %d)') % (
                answer, sheet.clicks, self.par)
        elif right:
            words = _('Right, but %d clicks against a par of %d') % (
                sheet.clicks, self.par)
        else:
            words = _('No: the answer was %d') % answer
        self._judge(right and cheap, words)

    def scroll(self, way: int) -> None:
        if self.phase == self.PLAY:
            self.sheet.wheel(way)
            self._redraw()

    def _key(self, symbol: int, modifiers: int) -> None:
        sheet = self.sheet
        action = None
        if key._0 <= symbol <= key._9:
            action = ('key', chr(ord('0') + symbol - key._0))
        elif symbol == key.BACKSPACE:
            action = ('key', 'del')
        elif symbol in (key.ENTER, key.RETURN):
            action = ('submit',)
        elif symbol == key.UP:
            self.scroll(-1)
        elif symbol == key.DOWN:
            self.scroll(1)
        if action is not None:
            sheet.clicks += 1
            sheet.do(action)
            self._after()

    # --- drawing ---------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        sheet = self.sheet
        puzzle = sheet.puzzle
        W, H = model.SCREEN_W, model.SCREEN_H
        self._rect(0, 0, W, H, (255, 255, 255), shopui.EDGE)
        # Filter chips.
        for name, (x, y, w, h) in model.chips(puzzle.categories):
            on = sheet.filter == name
            self._rect(x, y, w, h, ON if on else shopui.BUTTON, shopui.EDGE)
            self._words(_(name), x + w / 2, y + h / 2, 13, anchor='center',
                        colour=(255, 255, 255) if on else shopui.INK,
                        bold=on)
        xs = model.column_x()
        # Headers.
        for col, label, w in model.COLUMNS:
            x = xs[col][0]
            self._rect(x, model.HEAD_Y, w, model.HEAD_H, HEAD, GRID)
            mark = ''
            if sheet.sort and sheet.sort[0] == col:
                mark = '  v' if sheet.sort[1] else '  ^'
            self._words(_(label) + mark, x + 8, model.HEAD_Y +
                        model.HEAD_H / 2, 14, bold=True)
        # Rows.
        for i, row in enumerate(sheet.shown()):
            y = model.ROWS_Y + i * model.ROW_H
            self._rect(model.LEFT, y, xs['total'][0] + xs['total'][1] -
                       model.LEFT, model.ROW_H,
                       STRIPE if i % 2 else (255, 255, 255), GRID)
            for col, _label, w in model.COLUMNS:
                x = xs[col][0]
                value = getattr(row, col)
                numeric = col in model.NUMERIC or col == 'id'
                self._words(str(value), x + w - 10 if numeric else x + 8,
                            y + model.ROW_H / 2, 14,
                            anchor='right' if numeric else 'left',
                            width=w - 14)
        count = len(sheet.visible_rows())
        if count > model.VISIBLE:
            self._words(_('rows %d-%d of %d') % (
                sheet.scroll + 1, min(count, sheet.scroll + model.VISIBLE),
                count), model.LEFT, model.ROWS_Y + model.VISIBLE *
                model.ROW_H + 2 + 0, 11, colour=shopui.MUTED)
        # Sum buttons and the status bar.
        for col, (x, y, w, h) in model.sum_buttons():
            on = sheet.stat == col
            self._rect(x, y, w, h, ON if on else shopui.BUTTON, shopui.EDGE)
            self._words(_('Sum'), x + w / 2, y + h / 2, 13, anchor='center',
                        colour=(255, 255, 255) if on else shopui.INK)
        stats = sheet.stats()
        words = _('pick a Sum button to see the visible rows added up')
        if stats is not None:
            words = _('%s of visible rows:  sum %d   count %d   largest %d') \
                % ((dict((k, l) for k, l, _w in model.COLUMNS)[sheet.stat],)
                   + stats)
        self._rect(model.LEFT, model.STATUS_Y, 760, 30, HEAD, GRID)
        self._words(words, model.LEFT + 10, model.STATUS_Y + 15, 14,
                    width=740)
        # The answer panel.
        self._words(_('Answer'), model.PANEL_X, 52, 15, bold=True)
        x, y, w, h = model.ANSWER
        self._rect(x, y, w, h, (255, 255, 255), ON)
        self._words(sheet.typed + '|', x + 10, y + h / 2, 20, bold=True)
        for label, (x, y, w, h) in model.keypad():
            self._rect(x, y, w, h, shopui.BUTTON, shopui.EDGE)
            self._words(label, x + w / 2, y + h / 2, 18, anchor='center',
                        bold=True)
        x, y, w, h = model.SUBMIT
        self._rect(x, y, w, h, shopui.BUTTON, shopui.EDGE)
        self._words(_('Submit'), x + w / 2, y + h / 2, 18, anchor='center',
                    bold=True)
        self._pointer(sheet)

    def _facts(self) -> str:
        if self.sheet is None:
            return ''
        return _('rung %d  %d/%d   clicks %d   par %d') % (
            self.rung, self.trial, self.total_trials, self.sheet.clicks,
            self.par)


def reference_ports(task) -> List[int]:
    """Ports that carry out the reference plan from the start."""
    sheet = model.Sheet(task.sheet.puzzle)
    sheet.pointer = list(task.sheet.pointer)
    rects = dict(sheet.targets())
    ports: List[int] = []
    for action in model.plan(sheet.puzzle):
        tx, ty = browser.click_point(rects[action])
        for port in browser.moves_to(sheet.pointer[0], sheet.pointer[1],
                                     tx, ty):
            dx, dy = browser.DIRECTIONS[port // 3]
            sheet.move(dx * browser.STEPS[port % 3],
                       dy * browser.STEPS[port % 3])
            ports.append(port)
        assert sheet.target_at(*sheet.pointer) == action, action
        sheet.click()
        ports.append(CLICK)
    return ports
