# -*- coding: utf-8 -*-
"""Scenes: a picture as a list of plain shapes, with no pixels drawn.

The perception tasks built on this describe what is on screen as a list
of primitives in a page W wide and 1 tall (origin bottom left), and
:mod:`neural_workshop.ui.scenetask` draws any such list. So a task's
model can say exactly what was shown -- and a test can check it --
without a window:

``('rect', x, y, w, h, colour)``
``('disc', x, y, r, colour)``
``('ring', x, y, r, width, colour)``
``('poly', points, colour)``
``('line', x0, y0, x1, y1, width, colour)``
``('text', x, y, size, words, colour)``
``('hit', x, y, w, h, choice)``      a region that answers when clicked

A model gives ``scene(puzzle, t, judged)``.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import colorsys
import math
import random
from typing import List, Sequence, Tuple

W = 1.6
INK = (40, 42, 50)
PAPER = (248, 247, 242)
PAPERS = ((248, 247, 242), (240, 245, 250), (250, 244, 236),
          (243, 248, 240), (246, 243, 250))

Colour = Tuple[int, int, int]


def hsv(h: float, s: float = 0.7, v: float = 0.9) -> Colour:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)),
                                  max(0.0, min(1.0, v)))
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def grey(v: float, tint: float = 0.0, hue: float = 0.0) -> Colour:
    """A grey of lightness *v* (0..1), faintly tinted."""
    return hsv(hue, tint, v)


def rect(x, y, w, h, colour):
    return ('rect', x, y, w, h, colour)


def disc(x, y, r, colour):
    return ('disc', x, y, r, colour)


def ring(x, y, r, width, colour):
    return ('ring', x, y, r, width, colour)


def poly(points, colour):
    return ('poly', tuple(points), colour)


def line(x0, y0, x1, y1, width=0.008, colour=INK):
    return ('line', x0, y0, x1, y1, width, colour)


def text(x, y, size, words, colour=INK):
    return ('text', x, y, size, words, colour)


def hit(x, y, w, h, choice):
    return ('hit', x, y, w, h, choice)


def polyline(points: Sequence[Tuple[float, float]], width=0.008,
             colour=INK) -> List[tuple]:
    out = [line(a[0], a[1], b[0], b[1], width, colour)
           for a, b in zip(points, points[1:])]
    out += [disc(x, y, width / 2, colour) for x, y in points]
    return out


def area(points: Sequence[Tuple[float, float]]) -> float:
    """The area inside a closed outline (shoelace)."""
    s = 0.0
    n = len(points)
    for k in range(n):
        x0, y0 = points[k]
        x1, y1 = points[(k + 1) % n]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


def blob(draw: random.Random, k: int = 5, wild: float = 0.25,
         n: int = 60) -> List[Tuple[float, float]]:
    """A random smooth outline about the origin, reaching about 1."""
    coef = [(draw.uniform(-wild, wild), draw.uniform(0, 2 * math.pi))
            for _j in range(k)]
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        r = 1 + sum(a * math.cos((j + 2) * t + ph)
                    for j, (a, ph) in enumerate(coef))
        pts.append((r * math.cos(t), r * math.sin(t)))
    return pts


def bend(pts, amount: float, draw: random.Random):
    """*pts* with one more ripple of size *amount*."""
    j = draw.randint(2, 5)
    ph = draw.uniform(0, 2 * math.pi)
    out = []
    for x, y in pts:
        t = math.atan2(y, x)
        r = math.hypot(x, y) * (1 + amount * math.cos(j * t + ph))
        out.append((r * math.cos(t), r * math.sin(t)))
    return out


def place(pts, cx, cy, scale, turn: float = 0.0, flip_x: bool = False,
          flip_y: bool = False):
    c, s = math.cos(turn), math.sin(turn)
    out = []
    for x, y in pts:
        if flip_x:
            x = -x
        if flip_y:
            y = -y
        out.append((cx + (x * c - y * s) * scale,
                    cy + (x * s + y * c) * scale))
    return out


def slot(seed: int, n: int) -> int:
    """Where the right answer sits among *n*: its own stream, so that
    retries in a deal cannot lean it one way."""
    return random.Random(seed * 7 + 3).randrange(n)


def stream(*keys: int) -> random.Random:
    """A random stream named by some whole numbers: the same numbers,
    the same stream, so a moving scene can be worked out for any moment
    without having been stepped there."""
    n = 0
    for k in keys:
        n = (n * 1000003 + int(k) + 12345) % (1 << 61)
    return random.Random(n)
