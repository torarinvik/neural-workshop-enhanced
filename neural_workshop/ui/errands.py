# -*- coding: utf-8 -*-
"""Errands on screen: an app strip, and Mail, Shop or Expenses below it.

The strip along the top switches apps and holds Done. Mail is an inbox
and a reading pane; Shop is the Browser task's shop, drawn by the same
code; Expenses is a claim form -- two number fields filled from an
on-screen keypad, a category, Submit -- beside the claims filed so far.
:mod:`neural_workshop.errands` holds the mail, the computer and par.

For the agent boundary, Browser's: ports 0-11 move the pointer, port 12
clicks, ports 13 and 14 scroll.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional

import pyglet
from pyglet.window import key, mouse

from .. import browser, errands as model
from ..i18n import _
from . import browser as shopui
from .browser import Browser

CLICK, SCROLL_UP, SCROLL_DOWN = shopui.CLICK, shopui.SCROLL_UP, \
    shopui.SCROLL_DOWN
PORTS = shopui.PORTS

STRIP = (52, 58, 70)
STRIP_TAB = (84, 92, 110)
STRIP_ON = (236, 240, 246)
WHITE = (255, 255, 255)
MAIL = (250, 251, 253)
SEEN = (120, 124, 132)
FIELD_ON = (40, 90, 220)


class Errands(Browser):
    """Work across Mail, Shop and Expenses to a request."""

    instance: Optional['Errands'] = None

    TITLE = 'Errands'
    TASK_ID = 'errands'
    PREFIX = 'ERRANDS'
    CATEGORY = 'computer'
    FOOTNOTE = _('click   wheel or Up/Down: scroll   digits type into a '
                 'claim   Esc: menu')

    def __init__(self) -> None:
        self.office: Optional[model.Office] = None
        super().__init__()

    def _clear_trial(self) -> None:
        self.office = None
        self.session = None

    def _deal(self) -> bool:
        dealt = model.deal(self.rung, rng=self.rng)
        self.office = model.Office(dealt)
        self.session = self.office.shop
        self.par = model.par(dealt)
        self.message = _('Do what the mail asks, then press Done')
        return True

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase != self.PLAY:
            return
        if port < CLICK:
            dx, dy = browser.DIRECTIONS[port // 3]
            step = browser.STEPS[port % 3]
            self.office.move(dx * step, dy * step)
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
        self.office.click(x, y)
        if self.office.done:
            self._finish_round()
        else:
            self._redraw()

    def scroll(self, way: int) -> None:
        if self.phase == self.PLAY:
            self.office.wheel(way)
            self._redraw()

    def _finish_round(self) -> None:
        office = self.office
        wrong = office.mistakes()
        cheap = office.clicks <= self.par
        if not wrong and cheap:
            words = _('All done in %d clicks (par %d)') % (office.clicks,
                                                           self.par)
        elif not wrong:
            words = _('All done, but %d clicks against a par of %d') % (
                office.clicks, self.par)
        else:
            words = _('Not done: %s') % '; '.join(wrong)
        self._judge(not wrong and cheap, words)

    def _key(self, symbol: int, modifiers: int) -> None:
        office = self.office
        if office.app == 'expenses' and (key._0 <= symbol <= key._9
                                         or symbol == key.BACKSPACE):
            office.clicks += 1
            office.do(('key', 'del' if symbol == key.BACKSPACE
                       else chr(ord('0') + symbol - key._0)))
            self._redraw()
        elif symbol == key.UP:
            self.scroll(-1)
        elif symbol == key.DOWN:
            self.scroll(1)

    # --- drawing ---------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        office = self.office
        W, H = model.SCREEN_W, model.SCREEN_H
        self._rect(0, 0, W, H, (255, 255, 255), shopui.EDGE)
        if office.app == 'shop':
            self._draw_shop(office.shop)
        elif office.app == 'mail':
            self._draw_mail(office)
        else:
            self._draw_expenses(office)
        self._draw_strip(office)
        self._pointer(office)

    def _draw_strip(self, office) -> None:
        self._rect(0, 0, model.SCREEN_W, model.STRIP, STRIP)
        names = {'mail': _('Mail'), 'shop': _('Shop'),
                 'expenses': _('Expenses')}
        for app in office.apps():
            x, y, w, h = model.TABS[app]
            on = app == office.app
            self._rect(x, y, w, h, STRIP_ON if on else STRIP_TAB)
            self._words(names[app], x + w / 2, y + h / 2, 13,
                        colour=shopui.INK if on else WHITE, bold=True,
                        anchor='center')
        x, y, w, h = model.DONE
        self._rect(x, y, w, h, STRIP_TAB, WHITE)
        self._words(_('Done'), x + w / 2, y + h / 2, 13, colour=WHITE,
                    bold=True, anchor='center')

    def _draw_mail(self, office) -> None:
        dealt = office.deal
        top = model.STRIP
        self._rect(0, top, model.SCREEN_W, model.SCREEN_H - top, MAIL)
        if office.reading is None:
            self._words(_('Inbox'), 30, top + 30, 20, bold=True)
            for i, mail in enumerate(dealt.mails):
                y = model.INBOX_TOP + i * model.ROW_H
                seen = i in office.read
                self._rect(20, y, 960, model.ROW_H - 4,
                           (255, 255, 255), shopui.EDGE)
                colour = SEEN if seen else shopui.INK
                mid = y + (model.ROW_H - 4) / 2
                self._words(mail.sender, 34, mid, 14, colour=colour,
                            bold=not seen, width=190)
                self._words(mail.subject, 240, mid, 14, colour=colour,
                            width=620)
                self._words(mail.time, 960, mid, 13, colour=SEEN,
                            anchor='right')
            return
        mail = dealt.mails[office.reading]
        self._words(_('< Inbox'), 30, top + 29, 15, colour=shopui.LINK,
                    bold=True)
        self._words(_('From: %s      %s') % (mail.sender, mail.time), 30,
                    top + 70, 15)
        self._words(mail.subject, 30, top + 104, 20, bold=True, width=940)
        y = top + 150
        for line in model.wrap(mail.body):
            self._words(line, 30, y, 15, width=940)
            y += 26

    def _draw_expenses(self, office) -> None:
        top = model.STRIP
        self._rect(0, top, model.SCREEN_W, model.SCREEN_H - top, MAIL)
        self._words(_('New expense claim'), 30, top + 32, 20, bold=True)
        for name, label in (('order', _('Order number')),
                            ('amount', _('Amount ($)'))):
            x, y, w, h = model.FIELDS[name]
            self._words(label, 30, y + h / 2, 14)
            on = office.focus == name
            self._rect(x, y, w, h, (255, 255, 255),
                       FIELD_ON if on else shopui.EDGE)
            if on:
                self._rect(x - 2, y - 2, w + 4, 2, FIELD_ON)
                self._rect(x - 2, y + h, w + 4, 2, FIELD_ON)
            self._words(office.fields[name] + ('|' if on else ''),
                        x + 12, y + h / 2, 17, bold=True)
        for label, (x, y, w, h) in model.keypad_rects():
            self._rect(x, y, w, h, shopui.BUTTON, shopui.EDGE)
            self._words(_('del') if label == 'del' else label, x + w / 2,
                        y + h / 2, 18, bold=True, anchor='center')
        x0 = model.category_rects()[0][1][1]
        self._words(_('Category'), 30, x0 + 20, 14)
        for name, (x, y, w, h) in model.category_rects():
            chosen = office.category == name
            self._rect(x, y, w, h, (255, 255, 255),
                       FIELD_ON if chosen else shopui.EDGE)
            self._words(('(o) ' if chosen else '( ) ') + name, x + 12,
                        y + h / 2, 15, bold=chosen)
        x, y, w, h = model.SUBMIT
        self._rect(x, y, w, h, shopui.BUTTON, shopui.EDGE)
        self._words(_('Submit claim'), x + w / 2, y + h / 2, 16,
                    bold=True, anchor='center')
        if office.notice:
            self._words(office.notice, 290, y + h / 2, 14)
        self._words(_('Filed claims'), 760, top + 32, 16, bold=True)
        for i, claim in enumerate(office.claims[-10:]):
            self._words('#%s  $%s  %s' % claim, 760, top + 72 + i * 30, 13,
                        width=230)

    def _facts(self) -> str:
        if self.office is None:
            return ''
        return _('rung %d  %d/%d   clicks %d   par %d') % (
            self.rung, self.trial, self.total_trials, self.office.clicks,
            self.par)

    def _click(self, x: float, y: float, button: int) -> None:
        if button != mouse.LEFT:
            return
        mx, my = self.to_model(x, y)
        if 0 <= mx <= model.SCREEN_W and 0 <= my <= model.SCREEN_H:
            self.click(mx, my)


def reference_ports(task) -> List[int]:
    """Ports that carry out the reference plan from the round's start."""
    office = model.Office(task.office.deal)
    office.pointer = list(task.office.pointer)
    ports: List[int] = []
    for action in model.plan(office.deal):
        rect = None
        if action[0] == 'shop' and action[1][0] not in ('home', 'cart',
                                                         'back'):
            shop = office.shop
            element = next(e for e in shop.elements()
                           if e.action == action[1])
            while not shop.visible(element):
                top = shop.view_top + element.y - shop.scroll
                way = 1 if top + element.h > model.SCREEN_H else -1
                shop.wheel(way)
                ports.append(SCROLL_DOWN if way > 0 else SCROLL_UP)
            rect = shop.on_screen(element)
        elif action[0] == 'shop':
            rect = dict((a[0], r) for r, a in office.shop.chrome())[
                action[1][0]]
        else:
            rect = dict(office.targets())[action]
        tx, ty = browser.click_point(rect)
        for port in browser.moves_to(office.pointer[0], office.pointer[1],
                                     tx, ty):
            dx, dy = browser.DIRECTIONS[port // 3]
            office.move(dx * browser.STEPS[port % 3],
                        dy * browser.STEPS[port % 3])
            ports.append(port)
        assert office.target_at(*office.pointer) == action, (
            action, office.target_at(*office.pointer))
        office.click()
        ports.append(CLICK)
    return ports
