# -*- coding: utf-8 -*-
"""Piano Man on screen: a keyboard of one or two octaves.

The melody plays (on the lowest rungs each key lights as its note
sounds); then click the keys, or play them on the computer's own: the
bottom row Z X C V B N M is the white keys of the lower octave with
S D G H J its black ones, the row Q W E R T Y U and 2 3 5 6 7 the upper
octave, I the top C. Space asks to hear it again, where that is
allowed. The marked key is the first note, or higher up the keynote;
the scale's own keys are tinted on the lower rungs.

For the agent boundary: port k presses key k from the left; port 25
asks to hear it again. The melody reaches the agent only as sound.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet
from pyglet.window import key

from .. import pianoman as model
from ..i18n import _
from .clocked import ClockedTask
from .tones import Tones

LOWER = (key.Z, key.S, key.X, key.D, key.C, key.V, key.G, key.B, key.H,
         key.N, key.J, key.M)
UPPER = (key.Q, key._2, key.W, key._3, key.E, key.R, key._5, key.T, key._6,
         key.Y, key._7, key.U, key.I)
KEYS = {symbol: k for k, symbol in enumerate(LOWER + UPPER)}
KEYS[key.SPACE] = model.LISTEN

IVORY, EBONY = (246, 244, 236), (34, 34, 40)
TINT_WHITE, TINT_BLACK = (206, 226, 250), (58, 84, 130)
LIT = (250, 205, 70)
DOWN = (150, 200, 150)
RIGHT, WRONG = (60, 170, 90), (214, 64, 58)


class PianoMan(Tones, ClockedTask):
    """Hear it, play it back."""

    instance: Optional['PianoMan'] = None

    TITLE = 'Piano Man'
    TASK_ID = 'piano_man'
    PREFIX = 'PIANOMAN'
    CATEGORY = 'perception'
    MODEL = model
    SUBSTEP = 1 / 60.0
    EVENT_KEYS = KEYS
    FOOTNOTE = _('click the keys, or Z X C ... and Q W E ...   '
                 'Space: hear it again   Esc: menu')

    def _make_run(self):
        return model.Run(model.deal(self.rung, rng=self.rng))

    def _deal(self) -> bool:
        ok = super()._deal()
        run = self.run
        self.message = run.puzzle.question
        self._tones_live(run.notes, model.patches(run.puzzle),
                         run.deadline + 60.0)
        return ok

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        p = run.puzzle
        n = p.level.keys
        whites = [k for k in range(n) if not model.is_black(k)]
        ww = min(width / len(whites), height * 0.24)
        wh = min(height * 0.62, ww * 4.6)
        x0 = left + (width - ww * len(whites)) / 2
        y0 = bottom + (height - wh) / 2
        lit = run.lit()
        judged = self.phase == 'judged'
        down = run.played[-1] if run.played and \
            run.t - run.pressed_at < 0.25 else None
        # Which notes of the melody each key was, once it is over.
        told = {}
        if judged:
            for i, k in enumerate(p.melody):
                told.setdefault(k, []).append(str(i + 1))
        wrong = run.played[-1] if judged and run.result is not None \
            and not run.result[0] and run.played else None

        def colour(k, black):
            if k == wrong:
                return WRONG
            if judged and k in told:
                return RIGHT
            if k == lit:
                return LIT
            if k == down:
                return DOWN
            if p.level.tinted and model.in_scale(p, k):
                return TINT_BLACK if black else TINT_WHITE
            return EBONY if black else IVORY

        spots = {}
        for i, k in enumerate(whites):
            spots[k] = (x0 + i * ww, y0, ww, wh)
        for k in range(n):
            if model.is_black(k):
                at = spots[k - 1][0] + ww
                spots[k] = (at - ww * 0.3, y0 + wh * 0.4, ww * 0.6, wh * 0.6)
        # Black keys lie over the white ones: they are hit first, drawn last.
        for k in range(n):
            if model.is_black(k):
                self.hits.append(spots[k] + ((lambda c=k: self.steer(c)),))
        for k in whites:
            self.hits.append(spots[k] + ((lambda c=k: self.steer(c)),))
        for k in whites:
            x, y, w, h = spots[k]
            self.drawn.append(pyglet.shapes.Rectangle(
                x + 1, y, w - 2, h, color=colour(k, False), batch=self.batch,
                group=self.card_group))
        for k in range(n):
            if model.is_black(k):
                x, y, w, h = spots[k]
                self.drawn.append(pyglet.shapes.Rectangle(
                    x, y, w, h, color=colour(k, True), batch=self.batch,
                    group=self.body_group))
        self.drawn.append(pyglet.shapes.Box(
            x0 - 2, y0 - 2, ww * len(whites) + 4, wh + 4, thickness=2,
            color=self.ink, batch=self.batch, group=self.text_group))
        # The marked key.
        x, y, w, h = spots[p.mark]
        self.drawn.append(pyglet.shapes.Circle(
            x + w / 2, y + h * 0.16, max(3.0, w * 0.2), color=(215, 60, 60),
            batch=self.batch, group=self.text_group))
        for k, numbers in told.items():
            x, y, w, h = spots[k]
            self._text(' '.join(numbers), x + w / 2, y + h * 0.45,
                       max(7.0, min(w * 0.3, 13.0)), bold=True,
                       colour=(255, 255, 255, 255), group=self.top_group)
        # How far through, as dots: one a note.
        total = len(p.melody)
        gap = min(22.0, width * 0.8 / total)
        dx = left + width / 2 - gap * (total - 1) / 2
        for i in range(total):
            done = i < len(run.played) and not (wrong is not None
                                                and i == len(run.played) - 1)
            self.drawn.append(pyglet.shapes.Circle(
                dx + i * gap, y0 + wh + 24, 5,
                color=RIGHT if done else (150, 150, 160), batch=self.batch,
                group=self.body_group))
        if self.phase == self.PLAY:
            self.message = _('Listen...') if run.playing else \
                _('Now play it back')

    def _facts(self) -> str:
        if self.run is None:
            return ''
        p = self.run.puzzle
        said = _('rung %d  %d/%d   %d notes') % (
            self.rung, self.trial, self.total_trials, len(p.melody))
        if self.run.listens and not self.run.played:
            said += _('   Space: hear it again (%d left)') % self.run.listens
        if self.phase == 'judged':
            said += '   %s %s' % (model.NAMES[p.keynote], _(p.scale))
        return said
