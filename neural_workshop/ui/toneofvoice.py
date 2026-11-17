# -*- coding: utf-8 -*-
"""Tone of Voice on screen: a speaker, the words said, the answers.

The words are shown so that only the voice is left to tell the feeling;
the speaker's rings pulse while the voice plays. See
:mod:`neural_workshop.toneofvoice` for what is played.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from .. import toneofvoice as model
from ..i18n import _
from .feelings import DIM, FeelingTask, INK, PAPER


class ToneOfVoice(FeelingTask):
    """Hear how the speaker feels."""

    instance: Optional['ToneOfVoice'] = None

    TITLE = 'Tone of Voice'
    TASK_ID = 'tone_of_voice'
    PREFIX = 'VOICE'
    CATEGORY = 'emotion'
    MODEL = model
    FOOTNOTE = _('Listen, then click an answer or press its number')

    def _deal(self) -> bool:
        ok = super()._deal()
        run = self.run
        if run is not None:
            self.message = _('How does the speaker feel?')
            self._tones_stream(lambda t0, t1, run=run: model.mix(run, t0, t1),
                               run.end + 1.0)
        return ok

    def _playing(self, run) -> bool:
        it = run.item()
        if it is None or run.showing:
            return False
        n = model.length(it.face, run.level.cut)
        t = run.t - run.since - model.LEAD
        return 0 <= t <= n or n + model.GAP <= t <= 2 * n + model.GAP

    def _show(self, run, it) -> None:
        x, y, w, h = self.TEXT_BOX
        g = self.g()
        self.rect(x, y, w, h, PAPER, g)
        cx, cy = 500.0, y + h * 0.62
        # the speaker: a box and a cone, rings while it plays
        self.rect(cx - 70, cy - 22, 26, 44, (70, 70, 90), g)
        self.line((cx - 44, cy + 22), (cx - 10, cy + 50), 4, (70, 70, 90), g)
        self.line((cx - 44, cy - 22), (cx - 10, cy - 50), 4, (70, 70, 90), g)
        self.line((cx - 10, cy + 50), (cx - 10, cy - 50), 4, (70, 70, 90), g)
        if self._playing(run):
            for k in range(3):
                r = 22 + 18 * k + 6 * math.sin(run.t * 9 - k)
                a = int(200 - 50 * k)
                self.disc((cx + 10 + r * 0.2, cy), 3, (80, 120, 200, a), g)
                for j in range(-3, 4):
                    ang = j * 0.22
                    self.disc((cx + 4 + r * math.cos(ang),
                               cy + r * math.sin(ang)), 2.4,
                              (80, 120, 200, a), g)
        self.words(it.prompt, 500, y + 70, 20, colour=INK)
        self.words(_('the same words, said one way'), 500, y + 36, 10,
                   colour=DIM)
