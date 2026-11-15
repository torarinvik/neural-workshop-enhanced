# -*- coding: utf-8 -*-
"""Safecracker on screen: the clue along the top, the vault door under
it.

The door is drawn in perspective and may swing on its hinge while the
camera drifts. On it: two coloured lamps at the top corners, bolts down
its edges, the dial with a fixed mark above it and a small lamp for
each tumbler under it, the word lock's window, and the handle on the
right. Strikes show as red crosses.

Mouse: drag round the dial to turn it and let go on the thunk; drag the
handle down when both locks are done. Keys: letters type the word,
Backspace rubs out.

For the agent boundary: ports 0-11 move the drawn pointer (up, down,
left, right by 80, 20 or 5 units of a 1000 by 640 screen), 12 presses
its button and 13 lets go; ports 14-39 type A to Z and port 40 is
Backspace.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import safecracker as model
from ..i18n import _
from . import polish
from .handtask import HandTask

LAMP = ((230, 70, 60), (70, 200, 100), (80, 130, 240), (245, 245, 245))
STEEL = (120, 130, 150)
LETTERS = {getattr(key, chr(ord('A') + n)): model.LETTER + n
           for n in range(26)}
LETTERS[key.BACKSPACE] = model.BACKSPACE


class Safecracker(HandTask):
    """Set the tumblers, type the word, pull the handle."""

    instance: Optional['Safecracker'] = None

    TITLE = 'Safecracker'
    TASK_ID = 'safecracker'
    PREFIX = 'SAFE'
    CATEGORY = 'attention'
    FEEDBACK = 2.5
    MODEL = model
    EVENT_KEYS = LETTERS
    BACK = (52, 46, 44)
    FOOTNOTE = _('Drag round the dial, let go on the thunk   Letters: the '
                 'word   Drag the handle down   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self.message = _('Listen for the thunk, answer the clue, pull the '
                         'handle')
        return ok

    def _scene(self, run, s: float) -> None:
        safe = run.safe
        see = run.see
        G = pyglet.graphics.Group
        g_door, g_on, g_up, g_top = G(order=0), G(order=1), G(order=2), \
            G(order=3)
        W, Hh = model.DOOR
        # The frame the door sits in, then the door.
        frame = run.view()
        hole = [frame.see(p) for p in ((-0.25, -0.2, -0.05), (W + 0.25, -0.2,
                                                              -0.05),
                                       (W + 0.25, Hh + 0.2, -0.05),
                                       (-0.25, Hh + 0.2, -0.05))]
        self.poly(hole, (24, 22, 24), G(order=-2))
        door = [see(0, 0), see(W, 0), see(W, Hh), see(0, Hh)]
        self.poly(door, STEEL, g_door)
        edge = [see(W, 0), see(W, 0, -0.35), see(W, Hh, -0.35), see(W, Hh)]
        self.poly(edge, (80, 88, 104), G(order=-1))
        for k in range(4):
            self.line(door[k], door[(k + 1) % 4], 3, (60, 66, 80), g_on)
        for v in (0.9, Hh - 0.9):
            self.line(see(0, v - 0.3), see(0, v + 0.3), 9, (50, 54, 66),
                      g_on)
        left = (safe.bolts + 1) // 2
        for k in range(safe.bolts):
            side, j = (0, k) if k < left else (1, k - left)
            rows = left if side == 0 else safe.bolts - left
            v = 0.45 + 3.1 * (j + 0.5) / rows
            self.disc(see(0.24 if side == 0 else W - 0.24, v, 0.03), 8,
                      (214, 180, 96), g_on)
        for (u, v), c in zip(model.LAMPS, safe.lamps):
            q = see(u, v, 0.05)
            if q is not None:
                x, y = self.px(q[0], q[1])
                polish.glow(self.drawn, self.batch, x, y, 26 * s, LAMP[c],
                            strength=60, group=g_on)
                self.disc(q, 11, LAMP[c], g_up)
        # The dial.
        cu, cv, rad = model.DIAL
        ring = lambda r, out, n=28: [                       # noqa: E731
            see(cu + r * math.cos(a), cv + r * math.sin(a), out)
            for a in (2 * math.pi * k / n for k in range(n))]
        self.poly(ring(rad + 0.1, 0.0), (50, 54, 66), g_on)
        self.poly(ring(rad, 0.12), (228, 228, 222), g_up)
        for n in range(model.NUMBERS):
            a = math.pi / 2 + math.radians((n - run.reading) * model.PER)
            long = n % 5 == 0
            r0 = rad * (0.78 if long else 0.86)
            self.line(see(cu + r0 * math.cos(a), cv + r0 * math.sin(a), 0.13),
                      see(cu + rad * 0.97 * math.cos(a),
                          cv + rad * 0.97 * math.sin(a), 0.13),
                      2.5 if long else 1.2, (30, 30, 36), g_top)
            if long:
                q = see(cu + rad * 0.62 * math.cos(a),
                        cv + rad * 0.62 * math.sin(a), 0.13)
                if q is not None:
                    self.words('%d' % n, q[0], q[1], 10, group=G(order=4),
                               colour=(30, 30, 36, 255), bold=True)
        self.poly(ring(rad * 0.32, 0.3, 16), (70, 76, 92), g_top)
        lit = run.level.glow and run.on_mark()
        tip = [see(cu, cv + rad + 0.02, 0.14), see(cu - 0.1, cv + rad + 0.26,
                                                   0.14),
               see(cu + 0.1, cv + rad + 0.26, 0.14)]
        self.poly(tip, (90, 230, 120) if lit else (230, 80, 60), g_top)
        total = len(safe.combo)
        for k in range(total):
            u = cu + (k - (total - 1) / 2.0) * 0.26
            self.disc(see(u, cv - rad - 0.3, 0.05), 6,
                      (110, 230, 130) if k < run.set else (40, 44, 54), g_up)
        # The word lock.
        q0, q1 = see(cu - 1.0, 0.5, 0.03), see(cu + 1.0, 0.95, 0.03)
        box = [see(cu - 1.0, 0.45, 0.03), see(cu + 1.0, 0.45, 0.03),
               see(cu + 1.0, 1.0, 0.03), see(cu - 1.0, 1.0, 0.03)]
        self.poly(box, (20, 28, 24), g_on)
        want = safe.answer
        shown = ' '.join((run.typed[k] if k < len(run.typed) else '_')
                         for k in range(len(want)))
        q = see(cu, 0.72, 0.04)
        if q is not None:
            self.words(shown, q[0], q[1], 15, group=g_top, bold=True,
                       colour=(120, 240, 150, 255) if run.worded
                       else (230, 230, 200, 255))
        # The handle.
        hu, hv = model.HANDLE
        ku, kv = run.knob()
        self.disc(see(hu - 0.5, hv, 0.05), 10, (50, 54, 66), g_on)
        self.line(see(hu - 0.5, hv, 0.2), see(ku, kv, 0.2), 9,
                  (200, 170, 70), g_up)
        self.disc(see(ku, kv, 0.2), 13, (230, 196, 80), g_top)
        for k in range(run.strikes):
            q = see(0.5 + 0.3 * k, 0.35, 0.03)
            if q is not None:
                self.words('X', q[0], q[1], 14, group=g_top, bold=True,
                           colour=(240, 70, 60, 255))
        g_hud = G(order=190)
        self.rect(20, 572, 960, 56, (16, 18, 28, 220), g_hud)
        self.words(safe.clue, 500, 600, 18, bold=True,
                   colour=(255, 255, 255, 255), group=G(order=191))

    def _facts(self) -> str:
        run = self.run
        if run is None:
            return ''
        return _('rung %d  %d/%d   tumblers %d of %d') % (
            self.rung, self.trial, self.total_trials, run.set,
            len(run.safe.combo))
