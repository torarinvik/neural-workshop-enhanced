# -*- coding: utf-8 -*-
"""A pinhole camera for screens that draw a little 3D with flat shapes.

Points go to the screen with :meth:`Lens.see`, which also says how far
off they are (for drawing far things first and fogging them), and a
point on the screen goes back into the world with :meth:`Lens.on_floor`
-- which is how a mouse over a drawn floor becomes a spot on that floor.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

Vec = Tuple[float, float, float]


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(v: Vec) -> Vec:
    d = math.sqrt(_dot(v, v)) or 1.0
    return (v[0] / d, v[1] / d, v[2] / d)


class Lens:
    def __init__(self, eye: Vec, target: Vec, focal: float, cx: float,
                 cy: float, up: Vec = (0.0, 1.0, 0.0)) -> None:
        self.eye = eye
        self.f = _unit(_sub(target, eye))
        self.r = _unit(_cross(self.f, up))
        self.u = _cross(self.r, self.f)
        self.focal = focal
        self.cx, self.cy = cx, cy

    def see(self, p: Sequence[float], near: float = 0.05
            ) -> Optional[Tuple[float, float, float]]:
        """(x, y, depth) on the screen, or None behind the camera."""
        d = _sub(tuple(p), self.eye)
        z = _dot(d, self.f)
        if z < near:
            return None
        k = self.focal / z
        return self.cx + _dot(d, self.r) * k, self.cy + _dot(d, self.u) * k, z

    def fit(self, points: Sequence[Vec], left: float, bottom: float,
            width: float, height: float, margin: float = 0.04) -> 'Lens':
        """Set the focal length and centre so every point in *points* is
        on the screen inside the rectangle."""
        self.focal, self.cx, self.cy = 1.0, 0.0, 0.0
        seen = [self.see(p) for p in points]
        seen = [q for q in seen if q is not None]
        if not seen:
            return self
        xs = [q[0] for q in seen]
        ys = [q[1] for q in seen]
        w = max(1e-6, max(xs) - min(xs))
        h = max(1e-6, max(ys) - min(ys))
        self.focal = min(width * (1 - 2 * margin) / w,
                         height * (1 - 2 * margin) / h)
        self.cx = left + width / 2 - self.focal * (max(xs) + min(xs)) / 2
        self.cy = bottom + height / 2 - self.focal * (max(ys) + min(ys)) / 2
        return self

    def size(self, world: float, depth: float) -> float:
        return world * self.focal / max(depth, 1e-6)

    def ray(self, sx: float, sy: float) -> Vec:
        a = (sx - self.cx) / self.focal
        b = (sy - self.cy) / self.focal
        return _unit(tuple(self.f[i] + a * self.r[i] + b * self.u[i]
                           for i in range(3)))

    def on_floor(self, sx: float, sy: float, y: float = 0.0
                 ) -> Optional[Tuple[float, float]]:
        """Where the screen point (sx, sy) lands on the plane at height y."""
        d = self.ray(sx, sy)
        if abs(d[1]) < 1e-6:
            return None
        s = (y - self.eye[1]) / d[1]
        if s <= 0:
            return None
        return self.eye[0] + d[0] * s, self.eye[2] + d[2] * s
