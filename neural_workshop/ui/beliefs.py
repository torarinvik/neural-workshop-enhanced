# -*- coding: utf-8 -*-
"""Who Knows What? on screen: the story in panels, the answers below.

Each panel is the room just after one event: the containers in a row
with what is really in each (the reader sees everything), the people in
the room, the people outside in a grey strip on the right, and the
event in words underneath. Read left to right, top to bottom.

For the agent boundary: ports 0-3 choose containers 1-4.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet

from .. import beliefs as model
from ..geometry import calc_fontsize
from ..i18n import _
from .spacetask import ChoiceTask

ROOM = (246, 244, 238)
ROOM_DARK = (40, 42, 48)
OUT = (214, 216, 222)
OUT_DARK = (62, 64, 72)


class WhoKnowsWhat(ChoiceTask):
    """Where will someone look -- or think someone else will look?"""

    instance: Optional['WhoKnowsWhat'] = None

    TITLE = 'Who Knows What?'
    TASK_ID = 'who_knows_what'
    PREFIX = 'WHO_KNOWS_WHAT'
    CATEGORY = 'reasoning'
    BUTTONS = 0.1

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _circle(self, x, y, r, colour, group=None):
        self.drawn.append(pyglet.shapes.Circle(
            x, y, r, color=colour, batch=self.batch,
            group=group or self.body_group))

    def _panel(self, k, x, y, w, h) -> None:
        story = self.puzzle
        cap_h = h * 0.3
        room_h = h - cap_h
        out_w = w * 0.2
        self._box(x, y + cap_h, w - out_w, room_h,
                  ROOM_DARK if self.dark else ROOM, self.ink, thickness=1)
        self._box(x + w - out_w, y + cap_h, out_w, room_h,
                  OUT_DARK if self.dark else OUT, self.ink, thickness=1)
        small = min(calc_fontsize(10), room_h * 0.1, w * 0.035)
        self._text('out', x + w - out_w / 2, y + h - 3, small * 0.9,
                   anchor_y='top')
        # Containers along the back of the room.
        n = len(story.containers)
        inner = w - out_w
        cw = inner / (n + 0.6)
        gap = (inner - cw * n) / (n + 1)
        places = dict(story.places[k])
        top = y + h - room_h * 0.12
        ch = room_h * 0.4
        for c in range(n):
            cx = x + gap + c * (cw + gap)
            self._box(cx, top - ch, cw, ch, model.CONTAINER_COLOURS[c],
                      self.ink, thickness=1)
            self._text(story.containers[c], cx + cw / 2, top - ch - 2,
                       small, anchor_y='top')
            inside = [t for t, where in places.items() if where == c]
            for j, thing in enumerate(inside):
                self._circle(cx + cw * (j + 1) / (len(inside) + 1),
                             top - ch / 2, min(cw, ch) * 0.16,
                             model.THING_COLOURS[thing], self.top_group)
        # People: inside along the front, outside in the strip.
        present = set(story.present[k])
        r = min(room_h * 0.11, w * 0.04)
        ins = [p for p in range(len(story.people)) if p in present]
        outs = [p for p in range(len(story.people)) if p not in present]
        for i, p in enumerate(ins):
            px = x + inner * (i + 1) / (len(ins) + 1)
            self._person(p, px, y + cap_h + r * 1.6, r, small)
        for i, p in enumerate(outs):
            py = y + cap_h + room_h * (1 - (i + 1) / (len(outs) + 1.3))
            self._person(p, x + w - out_w / 2, py, r, small)
        self._text('%d. %s' % (k + 1, model.caption(story, k)), x + 2,
                   y + cap_h - 2,
                   min(calc_fontsize(11), cap_h * 0.3), anchor='left',
                   anchor_y='top', width=w - 4)

    def _person(self, p, x, y, r, size) -> None:
        self._circle(x, y, r, model.PERSON_COLOURS[p])
        self._text(self.puzzle.people[p][0], x, y, size, bold=True,
                   colour=(255, 255, 255, 255), group=self.top_group)

    def _draw_scene(self, left, bottom, width, height) -> None:
        story = self.puzzle
        # A key to the things, by colour, along the bottom.
        size = calc_fontsize(11)
        key_h = size * 2.2
        step = width / (len(story.things) + 1)
        for i, thing in enumerate(story.things):
            kx = left + step * (i + 1)
            self._circle(kx - size * 1.6, bottom + key_h / 2, size * 0.5,
                         model.THING_COLOURS[i], self.top_group)
            self._text(_('the %s') % thing, kx - size, bottom + key_h / 2,
                       size, anchor='left')
        bottom += key_h
        height -= key_h
        n = len(story.events)
        cols = min(4, n)
        rows = int(math.ceil(n / float(cols)))
        gap = width * 0.01
        w = (width - gap * (cols - 1)) / cols
        h = min((height - gap * (rows - 1)) / rows, w * 0.75)
        y0 = bottom + height - (h * rows + gap * (rows - 1))
        for k in range(n):
            row, col = divmod(k, cols)
            self._panel(k, left + col * (w + gap),
                        y0 + (rows - 1 - row) * (h + gap), w, h)
