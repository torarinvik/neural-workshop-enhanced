# -*- coding: utf-8 -*-
"""The Cipher Abyss on screen: a laboratory and its machine.

On the left is the machine, humming, with its intake row under it:
the input being built, slot by slot. Along the bottom is the palette
of symbols, each with its number (the machines count with them), and
the buttons: delete, run, and ready for the test. On the right is the
laboratory notebook: every experiment so far, what went in and what
came out, and in the test what was asked and what the machine gave.
Each symbol has a colour, a shape and a note, and the machine plays
its answer as a little tune.

Mouse: click a symbol to add it, a slot to take it out, then Run.
Keys: 1-6 add a symbol, Backspace takes one out, Enter runs (or gives
the answer in the test), T starts the test.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; 14-19 add symbols 0-5, 20 deletes, 21 runs
or answers, 22 starts the test.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import cipherabyss as model
from ..i18n import _
from . import polish
from .handtask import HandTask

COLOURS = ((226, 72, 64), (64, 130, 230), (70, 190, 100), (240, 200, 60),
           (170, 90, 210), (245, 140, 50))


class CipherAbyss(HandTask):
    """Work out the hidden machine, then answer for it."""

    instance: Optional['CipherAbyss'] = None

    TITLE = 'The Cipher Abyss'
    TASK_ID = 'cipher_abyss'
    PREFIX = 'CIPHER'
    CATEGORY = 'reasoning'
    FEEDBACK = 4.0
    MODEL = model
    EVENT_KEYS = dict([(getattr(key, '_%d' % (i + 1)), model.SYM + i)
                       for i in range(6)]
                      + [(key.BACKSPACE, model.DELETE),
                         (key.RETURN, model.RUN), (key.ENTER, model.RUN),
                         (key.T, model.TEST)])
    BACK = (18, 20, 34)
    FOOTNOTE = _('Click or 1-6: symbols   Backspace: take one out   '
                 'Enter: run   T: the test   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            name = dict((k + 1, n) for k, (_s, n) in
                        enumerate(model.STAGES))[self.run.level.stage]
            self.message = _('What does the machine do? (%s)') % _(name)
        return ok

    # --- pieces --------------------------------------------------------

    def sym(self, v: int, x: float, y: float, r: float, group,
            alpha: int = 255) -> None:
        c = COLOURS[v] + (alpha,)
        dark = polish.mix(COLOURS[v], (0, 0, 0), 0.4) + (alpha,)
        if v == 0:
            self.disc((x, y), r, dark, group)
            self.disc((x, y), r - 2, c, group)
        elif v == 1:
            self.rect(x - r, y - r, 2 * r, 2 * r, dark, group)
            self.rect(x - r + 2, y - r + 2, 2 * r - 4, 2 * r - 4, c, group)
        else:
            sides = {2: 3, 3: 4, 4: 5, 5: 6}[v]
            turn = math.pi / 2 if sides != 4 else 0.0
            for rr, col in ((r + 1.5, dark), (r - 1.5, c)):
                self.poly([(x + rr * math.cos(turn + 2 * math.pi * k / sides),
                            y + rr * math.sin(turn + 2 * math.pi * k / sides))
                           for k in range(sides)], col, group)

    def row(self, seq, x: float, y: float, r: float, gap: float, group,
            alpha: int = 255) -> float:
        for i, v in enumerate(seq):
            self.sym(v, x + i * gap, y, r, group, alpha)
        return x + len(seq) * gap

    def button(self, x: float, label: str, on: bool, group) -> None:
        w = model.BUTTON_W
        base = (70, 80, 110) if on else (44, 46, 60)
        self.rect(x - w / 2, model.PAL_Y - 24, w, 48,
                  polish.mix(base, (0, 0, 0), 0.4), group)
        self.rect(x - w / 2 + 2, model.PAL_Y - 22, w - 4, 44, base, group)
        self.words(label, x, model.PAL_Y, 12, bold=True, group=group,
                   colour=(235, 235, 245, 255 if on else 120))

    # --- the scene -----------------------------------------------------

    def _scene(self, run, s: float) -> None:
        lv = run.level
        g = self.g()
        self.rect(0, 0, 1000, 120, (28, 30, 46), g)            # bench
        self.rect(520, 130, 470, 500, (232, 226, 206), g)      # notebook
        for k in range(12):
            self.line((530, 560 - 38 * k), (980, 560 - 38 * k), 1,
                      (200, 196, 230), g)
        self.line((560, 140), (560, 620), 1, (220, 140, 140), g)
        # The machine.
        g = self.g()
        mx, my = 250.0, 400.0
        self.rect(mx - 190, my - 120, 380, 240, (50, 56, 80), g)
        self.rect(mx - 182, my - 112, 364, 224, (70, 78, 108), g)
        for k in range(6):                                     # lights
            on = int(run.t * 3 + k * 1.7) % 4 == 0
            self.disc((mx - 140 + 56 * k, my + 86), 7,
                      (250, 220, 120) if on else (90, 80, 60), g)
        for k in range(3):                                     # gears
            a = run.t * (1.2 if k % 2 else -1.0)
            cx, cy, r = mx - 90 + 90 * k, my - 6, 30 + 6 * (k % 2)
            for t in range(10):
                b = a + 2 * math.pi * t / 10
                self.disc((cx + r * math.cos(b), cy + r * math.sin(b)), 6,
                          (120, 128, 160), g)
            self.disc((cx, cy), r - 2, (96, 104, 140), g)
            self.disc((cx, cy), 6, (40, 44, 60), g)
        self.words(_('CIPHER MACHINE'), mx, my + 136, 14, bold=True,
                   group=g, colour=(200, 210, 240, 255))
        self.rect(mx - 30, my - 160, 60, 40, (50, 56, 80), g)  # intake
        # The intake row: what is being built.
        g = self.g()
        n = lv.length
        for i in range(n):
            x = model.slot_x(i, n)
            self.rect(x - 24, model.ROW_Y - 24, 48, 48, (36, 40, 60), g)
            self.rect(x - 22, model.ROW_Y - 22, 44, 44, (24, 26, 40), g)
            if i < len(run.entry):
                self.sym(run.entry[i], x, model.ROW_Y, 16, g)
        q = run.question()
        if q is not None:
            self.words(_('TEST %d of %d: what does it give for') %
                       (run.test_no + 1, len(run.machine.tests)),
                       250, 612, 12, bold=True, group=g,
                       colour=(250, 220, 120, 255))
            self.row(q, 250 - (len(q) - 1) * 21, 580, 14, 42, g)
            self.words(_('Type your answer below, then Enter'), 250, 250,
                       10, group=g, colour=(220, 220, 240, 220))
        else:
            self.words(_('%d experiments left') % run.left(), 250, 596, 13,
                       bold=True, group=g, colour=(220, 230, 250, 255))
            self.words(_('Build an input below and run it'), 250, 250, 10,
                       group=g, colour=(220, 220, 240, 200))
        # The palette and the buttons.
        g = self.g()
        for i in range(lv.k):
            x = model.pal_x(i)
            self.rect(x - 30, model.PAL_Y - 30, 60, 60, (44, 46, 60), g)
            self.sym(i, x, model.PAL_Y + 4, 17, g)
            self.words('%d' % i, x + 22, model.PAL_Y - 20, 9, group=g,
                       colour=(220, 220, 230, 230))
        self.button(model.DEL_X, _('DELETE'), bool(run.entry), g)
        self.button(model.RUN_X, _('ANSWER') if run.testing else _('RUN'),
                    len(run.entry) == n, g)
        self.button(model.TEST_X, _('TEST ME'), not run.testing, g)
        # The notebook.
        g = self.g()
        self.words(_('NOTEBOOK'), 760, 600, 12, bold=True, group=g,
                   colour=(60, 60, 90, 255))
        lines = [(x, y, None) for x, y in run.log] + \
            [(x, y, ok) for x, y, ok in run.answers]
        lines = lines[-12:]
        size = 9 if n <= 6 else 7.5
        gap = 2.2 * size + 3
        for k, (x, y, ok) in enumerate(lines):
            yy = 560 - 38 * k - 18
            end = self.row(x, 580, yy, size, gap, g)
            self.poly([(end + 4, yy + 5), (end + 16, yy), (end + 4, yy - 5)],
                      (90, 90, 110), g)
            self.row(y, end + 30, yy, size, gap, g)
            if ok is not None:
                self.words(_('test'), 545, yy, 8, group=g,
                           colour=((40, 140, 60, 255) if ok
                                   else (200, 50, 40, 255)))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)
