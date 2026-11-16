# -*- coding: utf-8 -*-
"""Semaphore on screen: the far ship, your own two flags, the chart.

The signaller stands on the deck of a ship out at sea, small and far,
holding two flags; the ship rolls on the higher rungs and fog drifts
over it on the highest. When their back is to you the jacket is dark.
You stand in the foreground with your own flags, which you drag by
their tips. The code chart, where the rung still shows it, runs down
both sides. Along the top are the letters of the message: read, missed
or still to come.

Mouse: drag a flag by its tip. Keys: A-Z say the letter.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; ports 14-39 are the letters A to Z.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import semaphore as model
from ..i18n import _
from . import polish
from .handtask import HandTask

KEYS = {getattr(key, c): model.H.KEYS + k
        for k, c in enumerate(model.LETTERS)}


class Semaphore(HandTask):
    """Copy the pose and say the letter."""

    instance: Optional['Semaphore'] = None

    TITLE = 'Semaphore'
    TASK_ID = 'semaphore'
    PREFIX = 'SEMA'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = KEYS
    BACK = (30, 50, 80)
    TIME_BAR = False
    FOOTNOTE = _('Drag your flags by their tips to copy the signal, then '
                 'type its letter   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Copy each signal with your flags and type its '
                         'letter')
        return ok

    def _flag(self, pivot, angle, arm, size, group_of) -> None:
        d = model.way(angle)
        tip = (pivot[0] + arm * d[0], pivot[1] + arm * d[1])
        self.line(pivot, tip, max(2.0, size * 0.18), (230, 220, 200),
                  group_of())
        n = (-d[1], d[0])
        a = (tip[0] - d[0] * size, tip[1] - d[1] * size)
        b = (a[0] + n[0] * size, a[1] + n[1] * size)
        c = (tip[0] + n[0] * size, tip[1] + n[1] * size)
        self.poly([a, b, tip], (226, 60, 50), group_of())
        self.poly([b, c, tip], (250, 210, 60), group_of())

    def _scene(self, run, s: float) -> None:
        m, level = model, run.level
        for k in range(6):                                  # sky
            self.rect(0, 360 + 47 * k, 1000, 47,
                      polish.mix((190, 214, 236), (90, 140, 210), k / 5.0),
                      self.g())
        self.rect(0, 0, 1000, 360, (40, 90, 130), self.g())  # sea
        for k in range(12):
            y = 30 + 27 * k
            x = (k * 173 + run.t * (10 + 3 * k)) % 1100 - 50
            self.line((x, y), (x + 60 + 6 * k, y), 2, (120, 170, 200, 150),
                      self.g())
        roll = math.radians(run.roll())
        fx, fy = m.FAR

        def deck(x: float, y: float):
            return (fx + x * math.cos(roll) + y * math.sin(roll),
                    fy - 95 - x * math.sin(roll) + y * math.cos(roll))
        self.poly([deck(-170, 0), deck(170, 0), deck(130, -50),
                   deck(-130, -50)], (60, 40, 36), self.g())
        self.poly([deck(-150, 0), deck(150, 0), deck(150, 10),
                   deck(-150, 10)], (150, 110, 70), self.g())
        self.line(deck(-90, 10), deck(-90, 230), 5, (90, 70, 50), self.g())
        self.poly([deck(-86, 220), deck(-86, 120), deck(-10, 130)],
                  (240, 236, 220), self.g())
        back = run.back()
        coat = (30, 40, 70) if back else (240, 240, 250)
        self.poly([deck(-13, 10), deck(13, 10), deck(13, 98), deck(-13, 98)],
                  coat, self.g())
        for a in run.theirs():
            self._flag(deck(0, 95), a, m.FAR_ARM, 22, self.g)
        self.disc(deck(0, 110), 12, (70, 50, 40) if back
                  else (236, 200, 170), self.g())
        if run.fogged():
            self.rect(0, 300, 1000, 340, (200, 210, 220, 235), self.g())
        px, py = m.PIVOT                                    # you
        self.poly([(px - 60, 0), (px + 60, 0), (px + 46, py + 10),
                   (px - 46, py + 10)], (30, 40, 70), self.g())
        self.disc((px, py + 42), 30, (70, 50, 40), self.g())
        for which in (0, 1):
            self._flag(m.PIVOT, run.flags[which], m.ARM, 40, self.g)
            self.disc(run.tip(which), 7, (255, 255, 255, 200)
                      if run.held == which else (255, 255, 255, 90),
                      self.g())
        hud = pyglet.graphics.Group(order=900)
        text = pyglet.graphics.Group(order=901)
        helped = run.helped()
        k = run.index()
        if helped == 'named' and k is not None:
            self.rect(fx + 120, fy - 30, 70, 70, (16, 18, 28, 220), hud)
            self.words(run.message.text[k], fx + 155, fy + 5, 34, bold=True,
                       group=text, colour=(255, 230, 120, 255))
        if helped in ('chart', 'named'):
            for n, letter in enumerate(m.LETTERS):
                col, row = n // 13, n % 13
                x = 46 if col == 0 else 954
                y = 590 - 42 * row
                self.rect(x - 34, y - 19, 68, 38, (16, 18, 28, 200), hud)
                self.words(letter, x - 18, y, 13, bold=True, group=text,
                           colour=(255, 255, 255, 255))
                for p in m.CODE[letter]:
                    d = m.way(p * 45.0)
                    self.line((x + 12, y), (x + 12 + 15 * d[0],
                                            y + 15 * d[1]), 3,
                              (250, 210, 60), text)
                self.disc((x + 12, y), 2.5, (255, 255, 255), text)
        n = len(run.message.text)
        for i in range(n):
            x = 500 + 34 * (i - (n - 1) / 2.0)
            got = run.read[i]
            self.rect(x - 14, 598, 28, 30,
                      (60, 150, 90) if got else (170, 60, 56)
                      if got is False else (255, 220, 120) if i == k
                      else (16, 18, 28), hud)
            if got is not None:
                self.words(run.message.text[i], x, 613, 14, bold=True,
                           group=text, colour=(255, 255, 255, 255))
        if k is not None:
            share = max(0.0, 1.0 - run.since() / level.hold)
            self.rect(350, 586, 300 * share, 6, (255, 200, 70), text)
        if back:
            self.words(_('their back is to you'), 760, 566, 12, bold=True,
                       group=text, colour=(255, 255, 255, 255))
        for i in range(level.strikes):
            self.disc((150 + 24 * i, 30), 8, (236, 80, 64)
                      if i < run.strikes else (30, 50, 70), text)

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d letters') % (
            self.rung, self.trial, self.total_trials, run.level.letters)
