# -*- coding: utf-8 -*-
"""Emotion on screen: a face, and the emotions to choose from.

A photograph is shown large in the middle (or, without the photographs,
a face drawn from a few lines). From rung 8 it is covered after a
moment; from rung 10 some faces show only the eyes or the mouth.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import pyglet

from .. import emotion as model
from ..i18n import _
from .feelings import FeelingTask

SIDE = 330.0                   # the face's size on the 1000 by 640 screen
CENTRE = (500.0, 380.0)
SKIN = (232, 196, 170)
LINE = (60, 40, 40)


class Emotion(FeelingTask):
    """Name the emotion on the face."""

    instance: Optional['Emotion'] = None

    TITLE = 'Emotion'
    TASK_ID = 'emotion'
    PREFIX = 'EMO'
    MODEL = model

    def _deal(self) -> bool:
        ok = super()._deal()
        if self.run is not None:
            self.message = _('Which emotion is this face showing?')
        return ok

    def _show(self, run, it) -> None:
        g = self.g()
        cx, cy = CENTRE
        half = SIDE / 2
        self.rect(cx - half - 6, cy - half - 6, SIDE + 12, SIDE + 12,
                  (24, 26, 34), g)
        if not run.face_visible():
            self.rect(cx - half, cy - half, SIDE, SIDE, (110, 112, 120), g)
            self.words('?', cx, cy, 40, bold=True,
                       colour=(200, 200, 210, 255))
            return
        face = it.face
        if face.path:
            self._photo(face.path, it.crop, g)
        else:
            self._drawn(face.drawn, it.crop, g)

    def _photo(self, path: str, crop: str, g) -> None:
        cache: Dict = self.__dict__.setdefault('_images', {})
        img = cache.get(path)
        if img is None:
            try:
                img = pyglet.image.load(path)
            except Exception:
                return
            cache[path] = img
            if len(cache) > 64:
                cache.pop(next(iter(cache)))
        cx, cy = CENTRE
        half = SIDE / 2
        k = SIDE / img.width
        region, y0 = img, 0.0
        if crop == 'eyes':
            region, y0 = img.get_region(0, img.height // 2 - 2, img.width,
                                        img.height * 2 // 5), \
                img.height // 2 - 2
        elif crop == 'mouth':
            region, y0 = img.get_region(0, 2, img.width,
                                        img.height * 2 // 5), 2
        if crop:
            self.rect(cx - half, cy - half, SIDE, SIDE, (24, 26, 34), g)
        x, y = self.px(cx - half, cy - half + y0 * k)
        sprite = pyglet.sprite.Sprite(region, x, y, batch=self.batch,
                                      group=self._tg)
        sprite.scale = k * self.fit[2]
        self.drawn.append(sprite)

    def _drawn(self, p, crop: str, g) -> None:
        tilt, brow_h, eye_open, curve, mouth_open, smirk = p
        cx, cy = CENTRE
        if crop != 'mouth':
            self.oval((cx, cy), 120, 150, SKIN, g)
        else:
            self.rect(cx - 120, cy - 150, 240, 120, SKIN, g)
        if crop == 'eyes':
            self.rect(cx - 125, cy - 160, 250, 150, (24, 26, 34), g)
        g2 = self.g()
        if crop != 'mouth':
            for side in (-1, 1):
                ex, ey = cx + side * 45, cy + 35
                self.oval((ex, ey), 18, 4 + 12 * max(0.1, eye_open),
                          (250, 250, 250), g2)
                self.disc((ex, ey), 7, (60, 50, 40), g2)
                by = ey + 30 + 18 * brow_h
                inner = by - side * 0 + 16 * tilt * -1 * 0.8
                self.line((ex - side * 26, by - 10 * tilt * 0.0),
                          (ex + side * -2, inner), 6, LINE, g2)
        if crop != 'eyes':
            my = cy - 70
            pts = []
            for k in range(13):
                u = (k - 6) / 6.0
                lift = curve * 26 * (u * u) - curve * 10
                lift += smirk * 18 * max(0.0, u)
                pts.append((cx + u * 50, my + lift))
            for a, b in zip(pts, pts[1:]):
                self.line(a, b, 5, LINE, g2)
            if mouth_open > 0.2:
                self.oval((cx, my - 4), 20 + 10 * mouth_open,
                          4 + 20 * mouth_open, (90, 30, 40), g2)
