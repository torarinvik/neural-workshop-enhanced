# -*- coding: utf-8 -*-
"""The Missing Word on screen: a page of text with holes and weeds.

One sentence a line, each word on a tile, as in The Proofreader. Under
every gap between two words is a small caret. Click a caret and four
words that could go there appear in a strip below the page; click one
and it goes in. Click a word and the strip offers to strike it out.

Mouse: click a caret, then a word; click a word, then strike out. Keys:
Enter hands it in, R puts the passage back as dealt.

For the agent boundary: ports 0-11 move the drawn pointer, 12 presses
its button and 13 lets go; 14 hands the passage in, 15 resets it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key

from .. import missingword as model
from ..i18n import _
from .proofreader import Proofreader, PAPER

CARET = (120, 110, 100)
CARET_ON = (210, 80, 50)


class MissingWord(Proofreader):
    """Put back what is missing, strike out what is not."""

    instance: Optional['MissingWord'] = None

    TITLE = 'The Missing Word'
    TASK_ID = 'missing_word'
    PREFIX = 'GAPW'
    CATEGORY = 'reasoning'
    MODEL = model
    EVENT_KEYS = {key.RETURN: model.DONE_KEY, key.ENTER: model.DONE_KEY,
                  key.R: model.RESET}
    FOOTNOTE = _('Click a caret for words to put in, a word to strike it'
                 '   Enter: done   R: reset')

    def _deal(self) -> bool:
        ok = super(Proofreader, self)._deal()
        run = self.run
        if run is not None:
            dmg = run.machine.damage
            miss = sum(1 for d in dmg if d[0] == 'missing')
            extra = len(dmg) - miss
            if run.level.hint:
                self.message = _('Mend the passage: %d word(s) missing') \
                    % miss
                if extra:
                    self.message += _(', %d too many') % extra
            else:
                self.message = _('Mend the passage')
        return ok

    def _scene(self, run, s: float) -> None:
        n = run.n()
        g = self.g()
        top = model.row_y(0, n) + 44
        bottom = model.row_y(n - 1, n) - 56
        self.rect(20, bottom, 960, top - bottom, PAPER, g)
        self.rect(20, bottom, 6, top - bottom, (220, 120, 110), g)
        chosen = run.chosen
        for r, row in enumerate(run.rows):
            g = self.g()
            y = model.row_y(r, n)
            ws, k = model.widths(row)
            for i, (t, x) in enumerate(zip(row, model.centres(row))):
                text = t.text
                if i == 0:
                    text = text[:1].upper() + text[1:]
                if i == len(row) - 1:
                    text += '.'
                self.tile(x, y, ws[i], text, g,
                          picked=chosen == ('word', r, i), size=15.0 * k)
            cy = y - model.CARET_DY
            for j, x in enumerate(model.carets(row)):
                on = chosen == ('gap', r, j)
                c = CARET_ON if on else CARET
                self.poly([(x - 6, cy - 4), (x + 6, cy - 4), (x, cy + 6)],
                          c, g)
        opts = run.options()
        g = self.g()
        if opts:
            label = _('Strike it out?') if chosen[0] == 'word' else \
                _('Put in:')
            self.words(label, 500, model.OPT_Y + 30, 10,
                       colour=(230, 230, 240, 255))
            for k, o in enumerate(opts):
                self.tile(model.option_x(k, len(opts)), model.OPT_Y,
                          model.OPT_W, _('strike out') if o ==
                          model.STRIKE_OUT else o, g)
        for (x, y), label in ((model.DONE_AT, _('DONE')),
                              (model.RESET_AT, _('RESET'))):
            self.rect(x - model.BUTTON_W / 2, y - model.BUTTON_H / 2,
                      model.BUTTON_W, model.BUTTON_H, (90, 100, 130), g)
            self.words(label, x, y, 12, bold=True,
                       colour=(240, 240, 250, 255))
