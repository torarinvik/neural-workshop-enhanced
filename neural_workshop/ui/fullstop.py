# -*- coding: utf-8 -*-
"""Full Stop on screen: a page of words run together.

The words lie on a sheet of paper, wrapped like a paragraph, each on a
tile, with no stops and no capitals. Clicking a word puts a red full
stop after it and gives the next word its capital; clicking it again
takes the stop away. The last word's stop is printed already.

Mouse: click the last word of each sentence. Keys: Enter hands it in,
R takes every stop away.

For the agent boundary: ports 0-11 move the drawn pointer, 12 presses
its button and 13 lets go; 14 hands the stops in, 15 takes them away.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key

from .. import fullstop as model
from ..i18n import _
from .proofreader import Proofreader, PAPER, INK

STOP = (200, 50, 40, 255)


class FullStop(Proofreader):
    """Put the full stops back."""

    instance: Optional['FullStop'] = None

    TITLE = 'Full Stop'
    TASK_ID = 'full_stop'
    PREFIX = 'STOP'
    CATEGORY = 'reasoning'
    MODEL = model
    EVENT_KEYS = {key.RETURN: model.DONE_KEY, key.ENTER: model.DONE_KEY,
                  key.R: model.RESET}
    FOOTNOTE = _('Click the last word of each sentence   '
                 'Enter: done   R: reset')

    def _deal(self) -> bool:
        ok = super(Proofreader, self)._deal()
        run = self.run
        if run is not None:
            n = len(run.machine.sentences)
            self.message = _('Put in the full stops: %d sentences') % n \
                if run.level.hint else _('Put in the full stops')
        return ok

    def _judge(self, passed: bool, message: str) -> None:
        if not passed and self.run is not None:
            message += ': ' + ' '.join(
                ' '.join(s).capitalize() + '.'
                for s in self.run.machine.sentences)
            if len(message) > 140:
                message = message[:137] + '...'
        super(Proofreader, self)._judge(passed, message)

    def _scene(self, run, s: float) -> None:
        g = self.g()
        places, k = run.places, run.scale
        top = places[0][1] + 40 * k
        bottom = places[-1][1] - 40 * k
        self.rect(20, bottom, 960, top - bottom, PAPER, g)
        self.rect(20, bottom, 6, top - bottom, (220, 120, 110), g)
        g = self.g()
        words = run.machine.words
        last = len(words) - 1
        for i, (x, y, w) in enumerate(places):
            text = words[i]
            if i == 0 or (i - 1) in run.stops:
                text = text[:1].upper() + text[1:]
            self.tile(x, y, w, text, g, picked=False, size=15.0 * k)
            if i in run.stops or i == last:
                self.disc((x + w / 2 + 5 * k, y - 11 * k), 4.5 * k,
                          STOP if i != last else INK, g)
        g = self.g()
        for (x, y), label in ((model.DONE_AT, _('DONE')),
                              (model.RESET_AT, _('RESET'))):
            self.rect(x - model.BUTTON_W / 2, y - model.BUTTON_H / 2,
                      model.BUTTON_W, model.BUTTON_H, (90, 100, 130), g)
            self.words(label, x, y, 12, bold=True,
                       colour=(240, 240, 250, 255))
        if not run.level.hint:
            return
        self.words(_('%d of %d sentences') % (run.sentences_now(),
                                              len(run.machine.sentences)),
                   120, 44, 12, colour=(230, 230, 240, 255))
