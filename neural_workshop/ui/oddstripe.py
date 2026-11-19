# -*- coding: utf-8 -*-
"""Odd Stripe.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet

from .. import oddstripe as model
from ..i18n import _
from .twins import TwinTask


class OddStripe(TwinTask):
    """Odd Stripe."""
    instance: Optional['OddStripe'] = None
    TITLE, TASK_ID, PREFIX = 'Odd Stripe', 'odd_stripe', 'ODDSTRIPE'
    RULE, LOOK, BUTTONS = 'odd', 'b', 0
    FOOTNOTE = _('click the odd one out   Esc: menu')

    def _make(self):
        return model.deal(self.rung, rng=self.rng)

    def _odd_b(self, left, bottom, width, height) -> None:
        data, hue = self.puzzle.data, self._hue()
        items = data['items']
        n = len(items)
        ring = min(width, height) * 0.36
        r = min(ring * math.sin(math.pi / n) * 0.8, ring * 0.42)
        cx, cy = left + width / 2, bottom + height / 2
        for k, tilt in enumerate(items):
            a = math.tau * (data['turn'] + k / n)
            x, y = cx + ring * math.sin(a), cy + ring * math.cos(a)
            self._card(n - 1 - k, x - r, y - r, 2 * r, 2 * r,
                       number=False)
            self.drawn.append(pyglet.shapes.Circle(
                x, y, r * 0.8, color=hue, batch=self.batch,
                group=self.text_group))
            t = math.radians(45 * tilt)
            ux, uy = math.cos(t), math.sin(t)
            for off in (-0.36, 0.0, 0.36):
                half = r * 0.8 * math.sqrt(1 - off * off)
                ox, oy = -uy * off * r * 0.8, ux * off * r * 0.8
                self.drawn.append(pyglet.shapes.Line(
                    x + ox - ux * half, y + oy - uy * half,
                    x + ox + ux * half, y + oy + uy * half,
                    thickness=max(2.0, r * 0.12), color=self.paper,
                    batch=self.batch, group=self.top_group))
