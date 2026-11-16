# -*- coding: utf-8 -*-
"""Conductor on screen: the orchestra from the podium.

Four sections sit on the stage in front of you: strings to the left,
woodwind in the middle, brass to the right, drums at the back. A
section that is playing is lit; one that is silent sits in the dark.
The score along the top lists what is coming, beat by beat; the big
number is the beat, where the rung still shows it. Your baton runs
from the podium to the pointer.

Mouse: flick down on every beat; click a section on its beat to bring
it in or cut it off. Keys: Up / W louder, Down / S softer.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; 14 is louder and 15 softer.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import conductor as model
from ..i18n import _
from . import polish
from .handtask import HandTask

TINTS = ((200, 120, 70), (90, 170, 120), (230, 190, 70), (150, 110, 190))
LOUD = ('p', 'mf', 'f')


class Conductor(HandTask):
    """Beat time and give every cue."""

    instance: Optional['Conductor'] = None

    TITLE = 'Conductor'
    TASK_ID = 'conductor'
    PREFIX = 'CONDUCT'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = {key.UP: model.LOUDER, key.W: model.LOUDER,
                  key.DOWN: model.SOFTER, key.S: model.SOFTER}
    BACK = (26, 18, 22)
    TIME_BAR = False
    FOOTNOTE = _('Flick down on each beat   Click a section on its beat   '
                 'Up: louder   Down: softer   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Beat time, and give each cue on its beat')
        return ok

    def _scene(self, run, s: float) -> None:
        m, view = model, model.VIEW
        see = view.see
        self.rect(0, 0, 1000, 640, (40, 22, 30), self.g())
        self.poly([see((-9, 0, -13)), see((9, 0, -13)), see((9, 7, -13)),
                   see((-9, 7, -13))], (70, 34, 44), self.g())
        for side in (-1, 1):                                # curtains
            self.poly([see((side * 9, 0, -13)), see((side * 6.5, 0, -13)),
                       see((side * 6.5, 7, -13)), see((side * 9, 7, -13))],
                      (150, 36, 50), self.g())
        self.poly([see((-9, 0, -13)), see((9, 0, -13)), see((9, 0, 1)),
                   see((-9, 0, 1))], (120, 86, 56), self.g())
        self.poly([see((-3, 0.8, -12)), see((3, 0.8, -12)), see((3, 0.8, -8.6)),
                   see((-3, 0.8, -8.6))], (136, 100, 66), self.g())
        self.poly([see((-3, 0, -8.6)), see((3, 0, -8.6)), see((3, 0.8, -8.6)),
                   see((-3, 0.8, -8.6))], (96, 68, 44), self.g())
        beat = run.next - 1
        pulse = 0.0
        if beat >= 0:
            pulse = max(0.0, 1.0 - (run.t - run.piece.times[beat]) * 4.0)
        for sec in sorted(range(4), key=lambda k: m.SEATS[k][2]):
            cx, cy, cz = m.SEATS[sec]
            on = run.playing[sec]
            tint = TINTS[sec] if on else polish.mix((0, 0, 0), TINTS[sec],
                                                    0.3)
            for i in range(5):
                x = cx + (i - 2) * 0.9
                z = cz - 0.5 * (i % 2)
                foot, head = see((x, cy, z)), see((x, cy + 1.3, z))
                if foot is None or head is None:
                    continue
                wide = view.size(0.32, foot[2])
                lift = pulse * 4 if on else 0
                self.poly([(foot[0] - wide, foot[1]), (foot[0] + wide,
                                                       foot[1]),
                           (head[0] + wide, head[1] + lift),
                           (head[0] - wide, head[1] + lift)], tint,
                          self.g())
                self.disc((head[0], head[1] + wide + lift), wide * 0.8,
                          (236, 200, 170) if on else (80, 70, 66),
                          self.g())
            x, y = m.spot(sec)
            self.words(m.SECTIONS[sec], x, y - 62, 12, bold=on,
                       group=pyglet.graphics.Group(order=899), colour=(255, 255, 255, 255) if on
                       else (150, 150, 150, 255))
        self.poly([(430, 0), (570, 0), (550, 50), (450, 50)], (70, 50, 40),
                  self.g())                                 # the podium
        self.line((540, 30), (run.hand.x, run.hand.y), 3, (250, 246, 230),
                  self.g())
        hud = pyglet.graphics.Group(order=900)
        text = pyglet.graphics.Group(order=901)
        self.rect(20, 540, 960, 90, (16, 14, 20, 225), hud)
        left = [c for j, c in enumerate(run.piece.cues) if not run.done[j]
                and c.beat > run.judged]
        for row, cue in enumerate(left[:3]):
            self.words(cue.text, 180, 610 - 26 * row, 15 if row == 0 else 12,
                       anchor='left', bold=row == 0, group=text,
                       colour=(255, 255, 255, 255) if row == 0
                       else (170, 170, 180, 255))
        shown = run.shown_beat()
        self.disc((90, 585), 34 + 6 * pulse,
                  polish.mix((60, 50, 60), (255, 200, 70), pulse), text)
        self.words(shown or '·', 90, 585, 24, bold=True,
                   group=pyglet.graphics.Group(order=902),
                   colour=(20, 16, 20, 255) if pulse > 0.4
                   else (255, 255, 255, 255))
        self.words(LOUD[run.loud], 930, 600, 22, bold=True, group=text,
                   colour=(255, 220, 120, 255))
        spare = run.level.slips - run.slips
        self.words(_('slips left: %d') % max(0, spare), 930, 566, 11,
                   group=text, colour=(200, 200, 210, 255))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d beats, %d cues') % (
            self.rung, self.trial, self.total_trials, run.level.beats,
            run.level.cues)
