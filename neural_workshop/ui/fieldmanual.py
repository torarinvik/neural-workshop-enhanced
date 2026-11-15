# -*- coding: utf-8 -*-
"""Field Manual on screen: the order in words along the top, the machine
under it.

The machine is a cube drawn in perspective, a little darker on the
faces turned away. Buttons are round caps, switches are levers that sit
up or down, dials are grey knobs with a coloured cap, a pointer and the
number they stand at, sliders are a coloured handle on a track. From
rung 7 each face has a number painted in a corner.

Mouse: drag anywhere but on a part to turn the machine; click buttons
and switches; drag a dial sideways; drag a slider's handle. Keys: the
digits type, Shift is held when an order says so.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; ports 14-23 type the digits 0-9; port 24 is
Shift, which counts as held for a quarter of a second after it is sent.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import fieldmanual as model
from ..hand import add, scale
from ..i18n import _
from . import polish
from .handtask import HandTask

PAINT = ((224, 70, 60), (70, 190, 100), (70, 120, 230), (240, 210, 70),
         (240, 240, 240), (240, 140, 50))
BODY = (86, 96, 120)
DIGITS = {getattr(key, '_%d' % n): model.DIGIT + n for n in range(10)}
DIGITS.update({getattr(key, 'NUM_%d' % n): model.DIGIT + n
               for n in range(10)})


class FieldManual(HandTask):
    """Carry out each order on the machine."""

    instance: Optional['FieldManual'] = None

    TITLE = 'Field Manual'
    TASK_ID = 'field_manual'
    PREFIX = 'FIELD'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = DIGITS
    FOOTNOTE = _('Drag: turn the machine, dials and sliders   Click: '
                 'buttons and switches   0-9: type   Shift: hold   '
                 'Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Do what the order says')
        return ok

    def _held(self):
        k = self.keys
        return model.SHIFT if k[key.LSHIFT] or k[key.RSHIFT] else None

    def _scene(self, run, s: float) -> None:
        view = model.VIEW
        see = lambda p: view.see(run.world(p))          # noqa: E731
        faces = sorted(range(6), key=run.facing)
        for order, f in enumerate(faces):
            lit = run.facing(f)
            if lit <= 0.0:
                continue
            g = pyglet.graphics.Group(order=order * 3)
            g_part = pyglet.graphics.Group(order=order * 3 + 1)
            g_top = pyglet.graphics.Group(order=order * 3 + 2)
            n, r, u = model.FACES[f]
            corners = [see(add(add(n, scale(r, a)), scale(u, b)))
                       for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            self.poly(corners, polish.mix((40, 44, 60), BODY,
                                          0.35 + 0.65 * lit), g)
            for k in range(4):
                self.line(corners[k], corners[(k + 1) % 4], 2,
                          (20, 22, 32), g_part)
            word = run.job.numbers.get(f)
            if word and lit > 0.3:
                q = see(add(add(n, scale(r, -0.72)), scale(u, 0.8)))
                if q is not None:
                    self.words(word, q[0], q[1], 15 * lit + 4, group=g_top,
                               bold=True, colour=(255, 255, 255, 220))
            for i, part in enumerate(run.job.parts):
                if part.face == f:
                    self._part(run, i, part, see, lit, g_part, g_top)
        # The order, and what has been typed of it.
        g_hud = pyglet.graphics.Group(order=190)
        self.rect(20, 556, 960, 72, (16, 18, 28, 220), g_hud)
        step = run.order
        text = run.reading()
        if step is not None and not text:
            text = _('(the order has gone)')
        self.words(text, 500, 600, 20, bold=True, colour=(255, 255, 255, 255),
                   group=pyglet.graphics.Group(order=191))
        under = _('order %d of %d') % (min(run.step_no + 1,
                                           len(run.job.steps)),
                                       len(run.job.steps))
        if step is not None and step.kind == 'type':
            under += '      ' + ' '.join(
                (step.value[k] if k < run.typed else '_')
                for k in range(len(step.value)))
        if run.holding(model.SHIFT):
            under += '      ' + _('SHIFT')
        self.words(under, 500, 570, 12, colour=(200, 210, 230, 255),
                   group=pyglet.graphics.Group(order=191))

    def _part(self, run, i, part, see, lit, g, g_top) -> None:
        n, r, u = model.FACES[part.face]
        centre = run.local(i)
        colour = polish.mix((30, 30, 40), PAINT[part.colour],
                            0.45 + 0.55 * lit)

        def ring(mid, radius, count=14):
            return [see(add(mid, add(scale(r, radius * math.cos(a)),
                                     scale(u, radius * math.sin(a)))))
                    for a in (2 * math.pi * k / count for k in range(count))]

        if part.kind == model.BUTTON:
            self.poly(ring(centre, 0.2), (30, 32, 44), g)
            down = run.grab == i
            self.poly(ring(add(centre, scale(n, 0.02 if down else 0.08)),
                           0.16), colour, g_top)
        elif part.kind == model.SWITCH:
            box = [see(add(centre, add(scale(r, a * 0.1), scale(u, b * 0.2))))
                   for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            self.poly(box, (30, 32, 44), g)
            tip = add(centre, add(scale(u, 0.17 if run.state[i] else -0.17),
                                  scale(n, 0.16)))
            self.line(see(centre), see(tip), 7, colour, g_top)
            self.disc(see(tip), 6, colour, g_top)
        elif part.kind == model.DIAL:
            self.poly(ring(centre, 0.25, 18), (150, 156, 170), g)
            self.poly(ring(add(centre, scale(n, 0.06)), 0.15), colour, g_top)
            a = math.pi / 2 - 2 * math.pi * run.state[i] / model.NOTCHES
            mark = add(centre, add(scale(r, 0.25 * math.cos(a)),
                                   scale(u, 0.25 * math.sin(a))))
            self.line(see(add(centre, scale(n, 0.07))), see(mark), 3,
                      (20, 20, 28), g_top)
            q = see(add(centre, scale(n, 0.08)))
            if q is not None and lit > 0.3:
                self.words('%d' % run.state[i], q[0], q[1], 11 * lit + 3,
                           group=pyglet.graphics.Group(order=g_top.order + 1),
                           bold=True, colour=(20, 20, 28, 255))
        else:
            a = see(run.local(i, -model.TRACK))
            b = see(run.local(i, model.TRACK))
            self.line(a, b, 6, (30, 32, 44), g)
            at = run.local(i, (2 * run.state[i] - 1) * model.TRACK)
            box = [see(add(at, add(scale(r, x * 0.13), scale(u, y * 0.06))))
                   for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            self.poly(box, colour, g_top)

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   %d parts') % (
            self.rung, self.trial, self.total_trials, len(run.job.parts))
