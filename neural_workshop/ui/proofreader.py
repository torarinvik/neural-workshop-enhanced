# -*- coding: utf-8 -*-
"""The Proofreader on screen: a page of damaged text and a pen.

The passage sits on a sheet of paper, one sentence a line, each word on
a tile. On the left of each line is its number, the handle that moves
the sentence. The first word of a line is shown with its capital and
the line ends with a full stop, wherever the line has been moved to, so
neither gives away where a sentence or a word belongs. A word in the
hand floats under the pointer; a sentence in the hand is lifted off the
page. A clicked word is underlined and the forms it could take appear
in a strip below the page.

Mouse: drag a word along its line, a sentence by its number; click a
word, then one of its forms. Keys: Enter hands it in, R puts the damage
back.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; 14 hands the passage in, 15 resets it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import proofreader as model
from ..i18n import _
from .handtask import HandTask

PAPER = (246, 240, 226)
INK = (40, 36, 48, 255)
TILE = (255, 252, 244)
EDGE = (190, 180, 160)


class Proofreader(HandTask):
    """Mend the passage."""

    instance: Optional['Proofreader'] = None

    TITLE = 'The Proofreader'
    TASK_ID = 'proofreader'
    PREFIX = 'PROOF'
    CATEGORY = 'reasoning'
    FEEDBACK = 4.0
    MODEL = model
    EVENT_KEYS = {key.RETURN: model.DONE_KEY, key.ENTER: model.DONE_KEY,
                  key.R: model.RESET}
    BACK = (54, 60, 74)
    FOOTNOTE = _('Drag words along a line, sentences by their number   '
                 'Click a word for its forms   Enter: done   R: reset')

    def _deal(self) -> bool:
        ok = super()._deal()
        run = self.run
        if run is not None:
            lv = run.level
            if lv.hint:
                self.message = _('Mend the passage: %d mistake(s)') % (
                    len([d for d in run.machine.damage if d[0] != 'order']))
                if any(d[0] == 'order' for d in run.machine.damage):
                    self.message += _(', and the sentences out of order')
            else:
                self.message = _('Mend the passage')
        return ok

    def _judge(self, passed: bool, message: str) -> None:
        if not passed and self.run is not None:
            message += ': ' + ' '.join(
                ' '.join(s).capitalize() + '.'
                for s in self.run.machine.original)
            if len(message) > 140:
                message = message[:137] + '...'
        super()._judge(passed, message)

    # --- layers: each layer's words just above its shapes -------------

    def g(self):
        self.layer += 1
        self._tg = pyglet.graphics.Group(order=10 * self.layer + 5)
        return pyglet.graphics.Group(order=10 * self.layer)

    def words(self, text, x, y, size, group=None, **kw):
        return super().words(text, x, y, size,
                             group=group or getattr(self, '_tg', None), **kw)

    # --- the page --------------------------------------------------------

    def tile(self, x, y, w, text, group, lift=False, picked=False,
             size=15.0) -> None:
        h = model.TILE_H
        if lift:
            self.rect(x - w / 2 + 4, y - h / 2 - 4, w, h, (0, 0, 0, 60),
                      group)
        self.rect(x - w / 2, y - h / 2, w, h, EDGE, group)
        self.rect(x - w / 2 + 1.5, y - h / 2 + 1.5, w - 3, h - 3,
                  (255, 236, 170) if picked else TILE, group)
        self.words(text, x, y, size, colour=INK)
        if picked:
            self.line((x - w / 2 + 6, y - h / 2 + 5),
                      (x + w / 2 - 6, y - h / 2 + 5), 2,
                      (200, 60, 40), group)

    def _scene(self, run, s: float) -> None:
        n = run.n()
        g = self.g()
        top = model.row_y(0, n) + 44
        bottom = model.row_y(n - 1, n) - 40
        self.rect(20, bottom, 960, top - bottom, PAPER, g)
        self.rect(20, bottom, 6, top - bottom, (220, 120, 110), g)
        carry = run.carry
        for r, row in enumerate(run.rows):
            g = self.g()
            y = model.row_y(r, n)
            lifted = carry is not None and carry[0] == 'row' and \
                carry[1] == r
            dy = run.hand.y - y if lifted else 0.0
            # the handle: the line's number
            hx = model.HANDLE_X
            self.rect(hx - 22, y + dy - 16, 44, 32,
                      (120, 130, 160) if lifted else (150, 160, 190), g)
            self.words(str(r + 1), hx, y + dy, 13, bold=True,
                       colour=(255, 255, 255, 255))
            ws, k = model.widths(row)
            cs = model.centres(row)
            for i, t in enumerate(row):
                if carry is not None and carry[0] == 'tok' and \
                        carry[1] == r and carry[2] == i:
                    continue
                text = t.text
                if i == 0:
                    text = text[:1].upper() + text[1:]
                if i == len(row) - 1:
                    text += '.'
                self.tile(cs[i], y + dy, ws[i], text, g, lift=lifted,
                          picked=t.id == run.selected, size=15.0 * k)
        # the word in the hand
        if carry is not None and carry[0] == 'tok':
            _t, r, i = carry
            row = run.rows[r]
            ws, k = model.widths(row)
            text = row[i].text
            self.tile(run.hand.x, run.hand.y, ws[i], text, self.g(),
                      lift=True, size=15.0 * k)
        # the forms of the word clicked
        opts = run.options()
        g = self.g()
        if opts:
            self.words(_('Its forms:'), 500, model.OPT_Y + 30, 10,
                       colour=(230, 230, 240, 255))
            for k, o in enumerate(opts):
                self.tile(model.option_x(k, len(opts)), model.OPT_Y,
                          model.OPT_W, o, g)
        # the buttons
        for (x, y), label in ((model.DONE_AT, _('DONE')),
                              (model.RESET_AT, _('RESET'))):
            self.rect(x - model.BUTTON_W / 2, y - model.BUTTON_H / 2,
                      model.BUTTON_W, model.BUTTON_H, (90, 100, 130), g)
            self.words(label, x, y, 12, bold=True,
                       colour=(240, 240, 250, 255))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)
