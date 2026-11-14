# -*- coding: utf-8 -*-
"""Browser on screen: a drawn browser window, and a pointer to work it.

A tab with the page's name, a toolbar with Back, Home, the address and
the cart, and the page below. Click with the mouse, scroll with the
wheel or the arrow keys; or, as the agent does, move the drawn pointer
and click. The goal is the line under the title. :mod:`neural_workshop.
browser` deals the shop and lays out every page.

For the agent boundary, as Desktop's: ports 0-11 move the pointer (up,
down, left, right, each by 80, 20 or 5 of the window's 1000 by 640
units), port 12 clicks, ports 13 and 14 scroll up and down.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import browser as model, state
from ..constants import FONTLIST
from ..i18n import _
from .rungtask import RungTask

CLICK, SCROLL_UP, SCROLL_DOWN = 12, 13, 14
PORTS = 15

TABS = (222, 226, 232)
TAB = (250, 251, 253)
TOOLBAR = (240, 242, 246)
FIELD = (255, 255, 255)
EDGE = (170, 176, 188)
PAGE = (255, 255, 255)
INK = (24, 26, 32)
LINK = (30, 80, 200)
MUTED = (120, 124, 132)
BUTTON = (228, 232, 240)
BANNER = (255, 238, 170)
GOOD = (30, 120, 60)
BAD = (170, 50, 40)
POINTER = (255, 255, 255)


class Browser(RungTask):
    """Shop a drawn website to a shopping list."""

    instance: Optional['Browser'] = None

    TITLE = 'Browser'
    TASK_ID = 'browser'
    PREFIX = 'BROWSER'
    CATEGORY = 'computer'
    FOOTNOTE = _('click links and buttons   wheel or Up/Down: scroll   '
                 'Backspace: back   Esc: menu')

    def __init__(self) -> None:
        self.session: Optional[model.Session] = None
        self.par = 0
        super().__init__()
        state.window.push_handlers(self.on_mouse_scroll)

    def close(self) -> None:
        if type(self).instance is self:
            state.window.remove_handlers(self.on_mouse_scroll)
        super().close()

    def _clear_trial(self) -> None:
        self.session = None

    def _deal(self) -> bool:
        dealt = model.deal(self.rung, rng=self.rng)
        self.session = model.Session(dealt)
        self.par = model.par(dealt)
        self.message = model.goal_words(dealt)
        return True

    # --- the frame -------------------------------------------------------

    def _frame(self) -> Tuple[float, float, float]:
        left, bottom, width, height = self._area()
        scale = min(width / model.SCREEN_W, height / model.SCREEN_H)
        x0 = left + (width - model.SCREEN_W * scale) / 2
        top = bottom + height
        return x0, top, scale

    def to_pixels(self, x: float, y: float) -> Tuple[float, float]:
        x0, top, scale = self._frame()
        return x0 + x * scale, top - y * scale

    def to_model(self, px: float, py: float) -> Tuple[float, float]:
        x0, top, scale = self._frame()
        return (px - x0) / scale, (top - py) / scale

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase != self.PLAY:
            return
        if port < CLICK:
            dx, dy = model.DIRECTIONS[port // 3]
            step = model.STEPS[port % 3]
            self.session.move(dx * step, dy * step)
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
        self.session.click(x, y)
        if self.session.checked_out:
            self._checkout()
        else:
            self._redraw()

    def scroll(self, way: int) -> None:
        if self.phase == self.PLAY:
            self.session.wheel(way)
            self._redraw()

    def _checkout(self) -> None:
        session = self.session
        right = session.right()
        cheap = session.clicks <= self.par
        if right and cheap:
            words = _('Bought the right things in %d clicks (par %d)')
        elif right:
            words = _('The right things, but %d clicks against a par of %d')
        else:
            words = _('Not what the list asked for (%d clicks, par %d)')
        self._judge(right and cheap, words % (session.clicks, self.par))

    def _key(self, symbol: int, modifiers: int) -> None:
        if symbol == key.UP:
            self.scroll(-1)
        elif symbol == key.DOWN:
            self.scroll(1)
        elif symbol == key.BACKSPACE and self.session is not None:
            self.session.clicks += 1
            self.session.do(('back',))
            self._redraw()

    def _click(self, x: float, y: float, button: int) -> None:
        if button != mouse.LEFT:
            return
        mx, my = self.to_model(x, y)
        if 0 <= mx <= model.SCREEN_W and 0 <= my <= model.SCREEN_H:
            self.click(mx, my)

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y) -> bool:
        if self.phase == self.PLAY and scroll_y:
            self.scroll(-1 if scroll_y > 0 else 1)
        return pyglet.event.EVENT_HANDLED

    # --- drawing ---------------------------------------------------------

    def _rect(self, x, y, w, h, colour, edge=None, group=None) -> None:
        px, py = self.to_pixels(x, y + h)
        _x0, _top, scale = self._frame()
        self._box(px, py, w * scale, h * scale, colour, edge,
                  group=group, thickness=1)

    def _words(self, words, x, y, size, colour=INK, bold=False,
               anchor='left', width=None) -> pyglet.text.Label:
        _x0, _top, scale = self._frame()
        px, py = self.to_pixels(x, y)
        label = self._text(words, px, py, size * scale, anchor=anchor,
                           bold=bold, colour=colour + (255,))
        if width is not None and label.content_width > width * scale:
            label.font_size *= width * scale / label.content_width
        return label

    def _draw(self, left, bottom, width, height) -> None:
        session = self.session
        dealt = session.deal
        W, H = model.SCREEN_W, model.SCREEN_H
        self._rect(0, 0, W, H, PAGE, EDGE)
        # Tab strip and toolbar.
        self._rect(0, 0, W, 32, TABS)
        self._rect(10, 4, 300, 28, TAB, EDGE)
        self._words(_page_title(dealt, session.page), 22, 18, 12,
                    width=280)
        self._rect(0, 32, W, model.VIEW_TOP - 32, TOOLBAR)
        for (x, y, w, h), words in ((model.BACK, _('Back')),
                                    (model.HOME, _('Home')),
                                    (model.CART, _('Cart (%d)')
                                     % len(session.cart))):
            self._rect(x, y, w, h, BUTTON, EDGE)
            self._words(words, x + w / 2, y + h / 2, 12, anchor='center',
                        bold=True)
        self._rect(170, 38, 700, 30, FIELD, EDGE)
        self._words(model.address(dealt, session.page), 180, 53, 12,
                    colour=MUTED, width=680)
        # The page.
        for element in session.elements():
            if not session.visible(element):
                continue
            self._element(*session.on_screen(element), element)
        self._scrollbar(session)
        self._pointer(session)

    def _element(self, x, y, w, h, element) -> None:
        style = element.style
        cy = y + h / 2
        if style == 'title':
            self._words(element.words, x, cy, 22, bold=True, width=w)
        elif style == 'link':
            label = self._words(element.words, x, cy, 15, colour=LINK,
                                width=w)
            _x0, _top, scale = self._frame()
            lx, ly = self.to_pixels(x, cy + 10)
            self.drawn.append(pyglet.shapes.Line(
                lx, ly, lx + label.content_width, ly, thickness=1,
                color=LINK, batch=self.batch, group=self.text_group))
        elif style == 'button':
            self._rect(x, y, w, h, BUTTON, EDGE)
            self._words(element.words, x + w / 2, cy, 15, bold=True,
                        anchor='center', width=w - 10)
        elif style == 'banner':
            self._rect(x, y, w, h, BANNER, EDGE)
            self._words(element.words, x + 20, cy, 16, colour=LINK,
                        bold=True, width=w - 40)
        elif style == 'muted':
            self._words(element.words, x, cy, 14, colour=MUTED, width=w)
        elif style in ('good', 'bad'):
            self._words(element.words, x, cy, 15, bold=True,
                        colour=GOOD if style == 'good' else BAD, width=w)
        else:
            self._words(element.words, x, cy, 15, width=w)

    def _scrollbar(self, session) -> None:
        most = session.max_scroll()
        if most <= 0:
            return
        total = model.VIEW_H + most
        bar = model.VIEW_H * model.VIEW_H / total
        top = model.VIEW_TOP + session.scroll / total * model.VIEW_H
        self._rect(988, model.VIEW_TOP, 10, model.VIEW_H, TABS)
        self._rect(989, top, 8, bar, MUTED)

    def _pointer(self, session) -> None:
        x, y = session.pointer
        _x0, _top, scale = self._frame()
        size = max(10.0, 22 * scale)
        px, py = self.to_pixels(x, y)
        group = self.top_group
        self.drawn.append(pyglet.shapes.Triangle(
            px - 2, py + 3, px - 2, py - size - 3, px + size * 0.75,
            py - size * 0.7, color=INK, batch=self.batch, group=group))
        self.drawn.append(pyglet.shapes.Triangle(
            px, py, px, py - size, px + size * 0.65, py - size * 0.65,
            color=POINTER, batch=self.batch,
            group=pyglet.graphics.Group(order=5)))

    def _facts(self) -> str:
        if self.session is None:
            return ''
        return _('rung %d  %d/%d   clicks %d   par %d') % (
            self.rung, self.trial, self.total_trials, self.session.clicks,
            self.par)


def _page_title(dealt, page) -> str:
    if page[0] == 'home':
        return dealt.shop.capitalize()
    if page[0] == 'list':
        return dealt.departments[page[1]]
    if page[0] == 'item':
        return dealt.products[page[1]].name
    return _('Your cart')


def reference_ports(task) -> list:
    """Ports that walk the fewest-clicks path from where the session is:
    for each action, scroll it into view, move the pointer onto it, click.
    Only good from the start of a round."""
    session = model.Session(task.session.deal)
    session.pointer = list(task.session.pointer)
    _count, path = model.fewest(session.deal)
    ports = []
    for action in path:
        if action[0] in ('home', 'cart'):
            rect = model.HOME if action[0] == 'home' else model.CART
        else:
            element = next(e for e in session.elements()
                           if e.action == action)
            while not session.visible(element):
                top = model.VIEW_TOP + element.y - session.scroll
                way = 1 if top + element.h > model.SCREEN_H else -1
                session.wheel(way)
                ports.append(SCROLL_DOWN if way > 0 else SCROLL_UP)
            rect = session.on_screen(element)
        tx, ty = model.click_point(rect)
        for port in model.moves_to(session.pointer[0], session.pointer[1],
                                   tx, ty):
            dx, dy = model.DIRECTIONS[port // 3]
            session.move(dx * model.STEPS[port % 3],
                         dy * model.STEPS[port % 3])
            ports.append(port)
        assert session.target_at(*session.pointer) == action, action
        session.click()
        ports.append(CLICK)
    return ports
