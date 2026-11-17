# -*- coding: utf-8 -*-
"""Same or Different?: one relation, in many guises.

Two things: are they the same, or different -- in one respect, named
by the guise, while everything else about them may differ:

* **shape** -- the same outline, however turned, sized or coloured?
* **count** -- the same number of dots, however laid out?
* **orientation** -- turned the same way?
* **colour** -- the same colour, whatever the shape?
* **size** -- the same size, whatever the colour or turn?
* **pitch** -- two tones: the same note, whatever the instrument?
* **rhythm** -- two tap patterns: the same rhythm, whatever the pitch?

The relation is one thing; the guises are its looks and sounds. A run
can mix them, or keep to one (the GUISE option), so whether "same"
learned in one guise carries to another can be put to the test.

The ladder, the same for every guise: the difference to be told shrinks
as a power of the rung, from plain at rung one toward the limits of
perception; from rung 4 the other respects differ too (and must be
ignored); from rung 10 the two are shown one after the other, so the
first has to be held in mind.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import showing
from .i18n import _

GUISES = ('shape', 'count', 'orientation', 'colour', 'size', 'pitch',
          'rhythm')
SOUND = ('pitch', 'rhythm')
SAME, DIFFERENT = 0, 1


class Grade(NamedTuple):
    rung: int
    ease: float          # 1 plain; toward 0 the limits of perception
    nuisance: bool
    sequential: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(rung=r, ease=0.82 ** (r - 1), nuisance=r >= 4,
                 sequential=r >= 10)


class Thing(NamedTuple):
    """One of the two: what is drawn or heard."""
    outline: Tuple[Tuple[float, float], ...]   # a shape, unit-ish
    dots: Tuple[Tuple[float, float, float], ...]   # count: x, y, r
    turn: float
    scale: float
    hue: Tuple[int, int, int]
    x: float                                   # where in its half, -1..1
    y: float


class Puzzle(NamedTuple):
    level: Grade
    guise: str
    a: Thing
    b: Thing
    show_a: Tuple[float, float]     # when each is on screen (visual)
    show_b: Tuple[float, float]
    amount: float                   # how big the difference is
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


QUESTIONS = {
    'shape': 'Same shape?', 'count': 'Same number of dots?',
    'orientation': 'Turned the same way?', 'colour': 'Same colour?',
    'size': 'Same size?', 'pitch': 'Same note?', 'rhythm': 'Same rhythm?'}


def blob(draw: random.Random, k: int = 5) -> List[Tuple[float, float]]:
    """A random outline: a circle bent by a few harmonics."""
    coef = [(draw.uniform(-0.25, 0.25), draw.uniform(0, 2 * math.pi))
            for _j in range(k)]
    pts = []
    for i in range(72):
        t = 2 * math.pi * i / 72
        r = 1 + sum(a * math.cos((j + 2) * t + ph)
                    for j, (a, ph) in enumerate(coef))
        pts.append((r * math.cos(t), r * math.sin(t)))
    return pts


def _bend(pts, amount: float, draw) -> List[Tuple[float, float]]:
    j = draw.randint(2, 5)
    ph = draw.uniform(0, 2 * math.pi)
    out = []
    for x, y in pts:
        t = math.atan2(y, x)
        r = math.hypot(x, y) * (1 + amount * math.cos(j * t + ph))
        out.append((r * math.cos(t), r * math.sin(t)))
    return out


def _hue(h: float, s: float = 0.7, v: float = 0.9) -> Tuple[int, int, int]:
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def _dots(n: int, draw, r: float) -> Tuple[Tuple[float, float, float], ...]:
    out = []
    for _k in range(n):
        for _try in range(400):
            x, y = draw.uniform(-0.85, 0.85), draw.uniform(-0.85, 0.85)
            rr = r * draw.uniform(0.7, 1.3)
            if all(math.hypot(x - a, y - b) > rr + c + 0.04
                   for a, b, c in out):
                out.append((x, y, rr))
                break
    return tuple(out)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None,
         guise: Optional[str] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    e = level.ease
    guise = guise if guise in GUISES else draw.choice(GUISES)
    same = draw.random() < 0.5
    answer = SAME if same else DIFFERENT
    nz = level.nuisance

    def thing(**kw) -> Thing:
        base = dict(outline=(), dots=(), turn=0.0, scale=1.0,
                    hue=_hue(h0), x=0.0, y=0.0)
        base.update(kw)
        return Thing(**base)

    h0 = draw.random()
    amount = 0.0
    a = b = None
    notes: tuple = ()
    patches: tuple = ()
    if guise == 'shape':
        out = blob(draw)
        amount = max(0.03, 0.35 * e)
        other = out if same else _bend(out, amount, draw)
        a = thing(outline=tuple(out), turn=draw.uniform(0, 6.28) if nz else 0)
        b = thing(outline=tuple(other),
                  turn=draw.uniform(0, 6.28) if nz else 0,
                  scale=draw.uniform(0.7, 1.0) if nz else 1.0,
                  hue=_hue(h0 + draw.uniform(0.2, 0.8)) if nz else _hue(h0))
    elif guise == 'count':
        n = draw.randint(3, 6 + min(30, level.rung))
        delta = 0 if same else max(1, int(round(n * 0.4 * e)))
        m = n + delta if draw.random() < 0.5 or n - delta < 1 else n - delta
        ra = 0.12 / math.sqrt(max(n, m) / 6)
        a = thing(dots=_dots(n, draw, ra))
        b = thing(dots=_dots(m, draw, ra * (draw.uniform(0.7, 1.2)
                                            if nz else 1.0)),
                  hue=_hue(h0 + 0.5) if nz else _hue(h0))
        amount = delta
    elif guise == 'orientation':
        out = blob(draw, 4)
        t = draw.uniform(0, 6.28)
        amount = math.radians(max(3.0, 70 * e))
        t2 = t if same else t + amount * draw.choice((-1, 1))
        a = thing(outline=tuple(out), turn=t)
        b = thing(outline=tuple(out), turn=t2,
                  scale=draw.uniform(0.7, 1.0) if nz else 1.0,
                  hue=_hue(h0 + 0.4) if nz else _hue(h0),
                  x=draw.uniform(-0.3, 0.3) if nz else 0.0)
    elif guise == 'colour':
        amount = max(0.012, 0.25 * e)
        h1 = h0 if same else h0 + amount * draw.choice((-1, 1))
        a = thing(outline=tuple(blob(draw)), hue=_hue(h0))
        b = thing(outline=tuple(blob(draw)) if nz else a.outline,
                  hue=_hue(h1), scale=draw.uniform(0.7, 1.0) if nz else 1.0)
    elif guise == 'size':
        out = blob(draw)
        amount = max(0.03, 0.6 * e)
        s = 1.0 if same else 1.0 / (1 + amount)
        if draw.random() < 0.5:
            sa, sb = 1.0, s
        else:
            sa, sb = s, 1.0
        a = thing(outline=tuple(out), scale=sa * 0.95)
        b = thing(outline=tuple(out), scale=sb * 0.95,
                  turn=draw.uniform(0, 6.28) if nz else 0.0,
                  hue=_hue(h0 + 0.5) if nz else _hue(h0))
    elif guise == 'pitch':
        f = draw.uniform(330, 660)
        amount = max(0.08, 4.0 * e)
        f2 = f if same else showing.semitones(f, amount * draw.choice((-1, 1)))
        names = ('sine', 'flute', 'organ', 'clarinet', 'pluck', 'brass')
        pa, pb = (draw.sample(names, 2) if nz else [names[0]] * 2)
        patches = (showing.patch(pa, seed), showing.patch(pb, seed + 1))
        notes = (showing.note(0.6, 0.5, f, 0, 0.8, 0),
                 showing.note(1.6, 0.5, f2, 0,
                              draw.uniform(0.5, 0.9) if nz else 0.8, 1))
        a = b = thing()
    else:  # rhythm
        k = draw.randint(4, 6)
        gaps = [draw.choice((0.15, 0.3, 0.45)) for _j in range(k - 1)]
        amount = max(0.025, 0.25 * e)
        gaps2 = list(gaps)
        if not same:
            j = draw.randrange(len(gaps2))
            gaps2[j] = gaps2[j] + amount * (1 if gaps2[j] < 0.4 else -1)
        f = draw.uniform(400, 700)
        f2 = f * (draw.uniform(1.2, 1.6) if nz else 1.0)
        patches = (showing.patch('wood', seed),)
        notes = []
        t = 0.6
        for g in [0.0] + gaps:
            t += g
            notes.append(showing.note(t, 0.08, f, 0, 0.8, 0))
        t += 1.0
        for g in [0.0] + gaps2:
            t += g
            notes.append(showing.note(t, 0.08, f2, 0, 0.8, 0))
        notes = tuple(notes)
        a = b = thing()
    if guise in SOUND:
        end = max(n.t + n.dur for n in notes)
        show_a = show_b = (0.0, 0.0)
        open_at = end + 0.05
    elif level.sequential:
        show_a, show_b = (0.4, 1.4), (2.0, 3.0)
        open_at = 2.0
    else:
        show_a = show_b = (0.0, 1e9)
        open_at = 0.0
    return Puzzle(level, guise, a, b, show_a, show_b, amount, open_at,
                  open_at + 8.0, notes, patches, _(QUESTIONS[guise]),
                  (_('Same'), _('Different')), answer)
