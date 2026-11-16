# -*- coding: utf-8 -*-
"""The screen shared by the Emotion tasks: something to read, answers
to pick.

Along the top, a dot for each item of the round (green right, red
wrong). In the middle, the face or the text. Under it the question, and
the answers on buttons: click one or press its number. After an answer
the right one turns green (and a wrong pick red) for a moment.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import pyglet
from pyglet.window import key

from .. import feelings as F
from ..constants import FONTLIST
from ..i18n import _
from .handtask import HandTask

PAPER = (246, 242, 232)
INK = (34, 32, 44, 255)
PALE = (232, 234, 244, 255)
DIM = (160, 166, 186, 255)
BUTTON = (74, 84, 116)
GOOD = (60, 170, 100)
BAD = (200, 70, 60)
DIGITS = (key._1, key._2, key._3, key._4, key._5, key._6, key._7, key._8)


class FeelingTask(HandTask):
    """A round of questions about feelings."""

    CATEGORY = 'emotion'
    FEEDBACK = 2.5
    BACK = (44, 48, 64)
    TIME_BAR = False
    EVENT_KEYS = {k: n for n, k in enumerate(DIGITS)}
    EVENT_KEYS.update({getattr(key, 'NUM_%d' % (n + 1)): n
                       for n in range(8)})
    FOOTNOTE = _('Click an answer or press its number')
    #: The text box for a written item.
    TEXT_BOX = (60.0, 180.0, 880.0, 380.0)

    def g(self):
        self.layer += 1
        self._tg = pyglet.graphics.Group(order=10 * self.layer + 5)
        return pyglet.graphics.Group(order=10 * self.layer)

    def words(self, text, x, y, size, group=None, **kw):
        return super().words(text, x, y, size,
                             group=group or getattr(self, '_tg', None), **kw)

    # --- the scene ------------------------------------------------------------

    def _scene(self, run, s: float) -> None:
        it = run.item()
        g = self.g()
        self._dots(run, g)
        if it is None:
            return
        if it.title:
            self.words(it.title, 500, 582, 11, bold=True, colour=DIM)
        self._show(run, it)
        g = self.g()
        st = run.step_now()
        if run.showing:
            right, _picks = run.last
            self.words((_('Right: ') if right else _('No: ')) + it.truth,
                       500, 150, 13, bold=True,
                       colour=(140, 230, 160, 255) if right
                       else (255, 150, 130, 255))
            shown = it.steps[-1] if it.tolerance < 0 else None
            if shown is not None:
                self._buttons(run, shown, g, picked=run.last[1][-1])
            return
        if st is None:
            return
        n = len(it.steps)
        ask = st.ask if n == 1 else '%s  (%d of %d)' % (
            st.ask, len(run.picks) + 1, n)
        self.words(ask, 500, 150, 13, bold=True, colour=PALE)
        self._buttons(run, st, g)
        left = max(0.0, it.seconds - (run.t - run.since))
        share = left / it.seconds
        self.rect(20, 8, 960 * share, 6, (110, 200, 140) if share > 0.3
                  else (230, 110, 80), g)

    def _dots(self, run, g) -> None:
        n = len(run.round.items)
        for k in range(n):
            x = 500 + (k - (n - 1) / 2) * 22
            if k < len(run.marks):
                c = GOOD if run.marks[k] else BAD
            elif k == run.k:
                c = (240, 210, 90)
            else:
                c = (90, 96, 120)
            self.disc((x, 616), 7, c, g)
        self.words(_('need %d') % run.round.need, 940, 616, 9, colour=DIM)

    def _buttons(self, run, st, g, picked: Optional[int] = None) -> None:
        n = len(st.options)
        size = self._fit_buttons(st.options, n)
        for k, label in enumerate(st.options):
            x, y, w, h = F.option_rect(k, n)
            c = BUTTON
            if picked is not None:
                if k == st.answer:
                    c = GOOD
                elif k == picked:
                    c = BAD
            self.rect(x, y, w, h, c, g)
            self.words('%d' % (k + 1), x + 12, y + h / 2, 9, colour=DIM)
            self.words(label, x + w / 2 + 6, y + h / 2, size, colour=PALE,
                       width=w - 30)

    def _fit_buttons(self, options, n) -> float:
        memo: Dict = self.__dict__.setdefault('_bsize', {})
        k = (tuple(options), self.fit[2])
        if k not in memo:
            w = F.option_rect(0, n)[2] - 30
            size = 12.0
            while size > 7.0:
                ok = True
                for o in options:
                    lab = pyglet.text.Label(o, font_size=size * self.fit[2],
                                            font_name=FONTLIST, width=int(
                                                w * self.fit[2]),
                                            multiline=True)
                    if lab.content_height > 2.2 * size * 1.4 * self.fit[2]:
                        ok = False
                        break
                if ok:
                    break
                size -= 0.5
            memo[k] = size
        return memo[k]

    def _show(self, run, it) -> None:
        """Draw the item itself; the text box unless a task draws more."""
        self.text_box(it.prompt)

    def text_box(self, text: str, box=None) -> None:
        x, y, w, h = box or self.TEXT_BOX
        g = self.g()
        self.rect(x, y, w, h, PAPER, g)
        size = self._fit_text(text, w - 40, h - 30)
        self.words(text, x + 20, y + h - 16, size, anchor='left',
                   anchor_y='top', width=w - 40, colour=INK)

    def _fit_text(self, text: str, w: float, h: float) -> float:
        memo: Dict = self.__dict__.setdefault('_tsize', {})
        k = (text, w, h, self.fit[2])
        if k not in memo:
            size = 20.0
            while size > 7.0:
                lab = pyglet.text.Label(text, font_size=size * self.fit[2],
                                        font_name=FONTLIST,
                                        width=int(w * self.fit[2]),
                                        multiline=True)
                if lab.content_height <= h * self.fit[2]:
                    break
                size -= 0.5
            memo[k] = size
        return memo[k]

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)
