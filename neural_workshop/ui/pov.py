# -*- coding: utf-8 -*-
"""Point of View on screen: the map on the left, the pictures on the
right.

The map is the table from straight above: each solid's footprint in its
colour, and the camera as a dot with the wedge it looks along. The
pictures sit in numbered cards; click the one the camera takes, or
press its number.

For the agent boundary: ports 0-4 choose pictures 1-5.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

from .. import pov as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import spacepaint
from .spacetask import ChoiceTask

CAMERA = (30, 34, 44)
WEDGE = (120, 140, 190)
SKY = (226, 232, 240)


class PointOfView(ChoiceTask):
    """Which picture does the camera on the map take?"""

    instance: Optional['PointOfView'] = None

    TITLE = 'Point of View'
    TASK_ID = 'point_of_view'
    PREFIX = 'POINT_OF_VIEW'
    CATEGORY = 'perception'
    BUTTONS = 0.0
    FOOTNOTE = _('click the picture or press its number   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _draw_map(self, left, bottom, width, height) -> None:
        puzzle = self.puzzle
        # The camera is drawn just off the table's edge, in the direction
        # it really stands; how far off does not matter to the question.
        ring = model.TABLE * 1.5
        reach = ring + 0.4
        scale = min(width, height) / (2 * reach)
        cx, cy = left + width / 2, bottom + height / 2

        def at(x, z):
            # Seen from straight above with x to the right, z runs *down*
            # the page (z up would be the mirror image).
            return cx + x * scale, cy - z * scale
        t = model.TABLE
        spacepaint.polygon(self, [at(-t, -t), at(t, -t), at(t, t),
                                  at(-t, t)], model.TABLE_TOP)
        for solid in puzzle.solids:
            spacepaint.polygon(self, [at(x, z) for x, z in
                                      model.footprint(solid)], solid.colour)
        a = puzzle.angle
        px, pz = ring * math.cos(a), ring * math.sin(a)
        spread = math.radians(22)
        far = ring * 0.55
        back = a + math.pi
        wedge = [at(px, pz)] + [
            at(px + far * math.cos(back + d), pz + far * math.sin(back + d))
            for d in (-spread, spread)]
        group = spacepaint.layer(self)
        spacepaint.polygon(self, wedge, WEDGE, rim=None, group=group)
        r = 0.22
        body = [at(px + r * math.cos(back + k * math.pi / 2 + math.pi / 4),
                   pz + r * math.sin(back + k * math.pi / 2 + math.pi / 4))
                for k in range(4)]
        spacepaint.polygon(self, body, CAMERA, rim=None)
        if puzzle.rung >= 20:
            self._text(_('camera height %.1f') % puzzle.eye, cx,
                       bottom + 4, calc_fontsize(12), anchor_y='bottom')

    def _draw_scene(self, left, bottom, width, height) -> None:
        puzzle = self.puzzle
        map_w = width * 0.36
        self._draw_map(left, bottom, map_w, height)
        n = len(puzzle.views)
        cols = 2 if n <= 4 else 3
        rows = int(math.ceil(n / float(cols)))
        gap = width * 0.012
        area_x = left + map_w + gap * 2
        area_w = width - map_w - gap * 2
        cw = (area_w - gap * (cols - 1)) / cols
        ch = (height - gap * (rows - 1)) / rows
        w = min(cw, ch * 1.35)
        h = w / 1.35
        for i, view in enumerate(puzzle.views):
            row, col = divmod(i, cols)
            x = area_x + col * (cw + gap) + (cw - w) / 2
            y = bottom + height - (row + 1) * ch - row * gap + (ch - h) / 2
            self._card(i, x, y, w, h)
            self._box(x + 3, y + 3, w - 6, h - 6, SKY)
            painted = model.picture(puzzle, view)
            # One scale for every picture: the table's width at the
            # camera's distance fills most of the card.
            spacepaint.paint(self, painted,
                             spacepaint.scaled(w * 1.05, x + w / 2,
                                               y + h * 0.55),
                             rim_px=1.2)
