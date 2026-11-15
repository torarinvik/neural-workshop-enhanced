# -*- coding: utf-8 -*-
"""Captcha on screen: a strip of characters and a box to type into.

The picture is drawn fresh from the dealt puzzle: a paper strip, then
whatever clutters it -- stripes, soft blobs, stray glyphs, thin lines
and arcs -- then the characters, each in its own typeface, colour, size
and lean, and last the lines struck through them. Below, the typed text
in a box. Type with the keyboard; Backspace rubs out, Enter submits.
The rule (which characters count) is said above the picture.

Typefaces are dealt as slots; each slot is a face this machine has,
from a list of very different ones, so the same puzzle looks the same
wherever the faces are installed.

For the agent boundary: ports 0-22 type the characters of
``captcha.ALPHABET`` in order; 23 rubs out; 24 submits.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import captcha as model
from ..i18n import _
from . import polish
from .rungtask import RungTask

#: A face for each slot, then fallbacks every machine has.
FACE_NAMES = ('Arial', 'Times New Roman', 'Courier New', 'Georgia',
              'Impact', 'Comic Sans MS', 'Futura', 'Marker Felt', 'Papyrus',
              'Didot', 'American Typewriter', 'Rockwell', 'Chalkduster',
              'Bradley Hand', 'Copperplate', 'Verdana')
FALLBACK = ('Arial', 'Helvetica', 'DejaVu Sans', 'Liberation Sans')
_faces = {}


def face(slot: int):
    """The font name list for a slot: its own face if this machine has
    it, else a plain one."""
    if slot not in _faces:
        want = FACE_NAMES[slot % len(FACE_NAMES)]
        try:
            have = pyglet.font.have_font(want)
        except Exception:
            have = False
        _faces[slot] = [want] + list(FALLBACK) if have else list(FALLBACK)
    return _faces[slot]


KEYS = {}
for _i, _c in enumerate(model.ALPHABET):
    KEYS[getattr(key, _c) if _c.isalpha() else getattr(key, '_' + _c)] = _i
    if _c.isdigit():
        KEYS[getattr(key, 'NUM_' + _c)] = _i


class Captcha(RungTask):
    """Type what the picture says, by its rule."""

    instance: Optional['Captcha'] = None

    TITLE = 'Captcha'
    TASK_ID = 'captcha'
    PREFIX = 'CAPTCHA'
    CATEGORY = 'perception'
    FEEDBACK = 2.5
    FOOTNOTE = _('Type the characters   Backspace: rub out   '
                 'Enter: submit   Esc: menu')

    def __init__(self) -> None:
        self.puzzle = None
        self.typed = ''
        super().__init__()

    def _clear_trial(self) -> None:
        self.puzzle = None
        self.typed = ''

    def _deal(self) -> bool:
        self.puzzle = model.deal(self.rung, rng=self.rng)
        self.typed = ''
        self.message = self.puzzle.rule
        return True

    # --- typing ---------------------------------------------------------------

    def steer(self, port: int) -> None:
        if self.phase != self.PLAY or self.puzzle is None:
            return
        if 0 <= port < len(model.ALPHABET):
            if len(self.typed) < model.LONGEST:
                self.typed += model.ALPHABET[port]
        elif port == model.BACKSPACE:
            self.typed = self.typed[:-1]
        elif port == model.SUBMIT:
            self._judge(*model.check(self.puzzle, self.typed))
            return
        self._redraw()

    def _key(self, symbol: int, modifiers: int) -> None:
        if symbol in KEYS:
            self.steer(KEYS[symbol])
        elif symbol in (key.BACKSPACE, key.DELETE):
            self.steer(model.BACKSPACE)
        elif symbol in (key.RETURN, key.ENTER, key.NUM_ENTER):
            self.steer(model.SUBMIT)

    # --- drawing --------------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        p = self.puzzle
        if p is None:
            return
        d, batch = self.drawn, self.batch
        s = min(width * 0.94 / model.W, height * 0.66 / model.H)
        x0 = left + (width - model.W * s) / 2
        y0 = bottom + height - model.H * s - height * 0.04
        CW, CH = model.W * s, model.H * s
        g = [pyglet.graphics.Group(order=-14 + k) for k in range(8)]
        polish.card(d, batch, x0 - 8, y0 - 8, CW + 16, CH + 16,
                    (250, 250, 250), radius=12, shade=(0, 0, 0, 70),
                    group=polish.STAGE)
        polish.gradient(d, batch, x0, y0, CW, CH, p.paper[0], p.paper[1],
                        bands=16, group=g[0])

        def at(x, y):
            return x0 + x * s, y0 + y * s
        # Stripes.
        def clamp(x):
            return max(x0, min(x0 + CW, x))
        for k in range(p.stripes):
            u = x0 + CW * (k + 0.5) / p.stripes
            hue = model.COLOURS[k % len(model.COLOURS)][1]
            d.append(pyglet.shapes.Polygon(
                (clamp(u - CW * 0.03), y0), (clamp(u + CW * 0.01), y0),
                (clamp(u + CW * 0.07), y0 + CH),
                (clamp(u + CW * 0.03), y0 + CH),
                color=polish.lighter(hue, 0.6) + (70,), batch=batch,
                group=g[1]))
        for m in p.marks:
            if m.kind == 'blob':
                cx, cy = at(m.points[0], m.points[1])
                d.append(pyglet.shapes.Ellipse(cx, cy, m.points[2] * s,
                                               m.points[2] * s * 0.6,
                                               color=m.colour, batch=batch,
                                               group=g[1]))
            elif m.kind == 'stray':
                cx, cy = at(m.points[0], m.points[1])
                lab = pyglet.text.Label(
                    m.char, font_name=face(m.face),
                    font_size=max(5.0, m.points[2] * s * 1.05), x=cx, y=cy,
                    anchor_x='center', anchor_y='center', color=m.colour,
                    batch=batch, group=g[2])
                lab.rotation = m.points[3]
                d.append(lab)
            elif m.kind == 'line':
                a, b = at(*m.points[:2]), at(*m.points[2:])
                d.append(pyglet.shapes.Line(*a, *b,
                                            thickness=max(1.0, m.width * s),
                                            color=m.colour, batch=batch,
                                            group=g[3]))
            elif m.kind == 'arc':
                cx, cy = at(m.points[0], m.points[1])
                d.append(pyglet.shapes.Arc(cx, cy, m.points[2] * s,
                                           thickness=max(1.0, m.width * s),
                                           angle=m.points[4],
                                           start_angle=m.points[3],
                                           color=m.colour, batch=batch,
                                           group=g[3]))
        # The characters.
        for k, gl in enumerate(p.glyphs):
            cx, cy = at(gl.x, gl.y)
            colour = model.COLOURS[gl.colour][1] + (255,)
            lab = pyglet.text.Label(
                gl.char, font_name=face(gl.face),
                font_size=max(6.0, gl.size * s * 1.05), x=cx, y=cy,
                anchor_x='center', anchor_y='center', color=colour,
                batch=batch, group=pyglet.graphics.Group(order=-5 + k % 3))
            lab.rotation = gl.angle
            d.append(lab)
        for m in p.marks:
            if m.kind != 'strike':
                continue
            pts = [at(m.points[i], m.points[i + 1])
                   for i in range(0, len(m.points), 2)]
            for a, b in zip(pts, pts[1:]):
                d.append(pyglet.shapes.Line(*a, *b,
                                            thickness=max(1.5, m.width * s),
                                            color=m.colour, batch=batch,
                                            group=g[7]))
        # After the verdict: which were the real ones.
        if self.phase == 'judged':
            for gl in p.glyphs:
                if gl.real:
                    cx, cy = at(gl.x, gl.y)
                    d.append(pyglet.shapes.Arc(
                        cx, cy, gl.size * s * 0.7, thickness=3,
                        color=(60, 200, 110, 220), batch=batch,
                        group=self.top_group))
        # The box.
        bw, bh = min(CW, width * 0.6), min(height * 0.16, 70)
        bx = left + (width - bw) / 2
        by = y0 - height * 0.08 - bh
        polish.card(d, batch, bx, by, bw, bh, (255, 255, 255), radius=10,
                    edge=(150, 160, 180), shade=(0, 0, 0, 40),
                    group=polish.CARD)
        shown = self.typed + ('_' if self.phase == self.PLAY and
                              int(self.clock() * 2) % 2 == 0 else ' ')
        self._text(' '.join(shown), bx + bw / 2, by + bh / 2, bh * 0.38,
                   bold=True, colour=(30, 34, 46, 255), group=self.top_group)

    def _facts(self) -> str:
        if self.puzzle is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)
