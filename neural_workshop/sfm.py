# -*- coding: utf-8 -*-
"""Shape from Motion: dots on a turning solid; name the solid.

Dots are scattered over the surface of a solid that turns about the
vertical, seen straight on: every dot alike, no shading, no outline,
nothing hidden. A still frame is a flat spray of dots; while it turns
the eye puts them back on a surface -- the kinetic depth effect.

* rungs 1-3: three very different solids, 300 dots that last;
* rungs 4-6: four choices;
* rungs 7-9: five, and each dot lives half a second before it moves to
  a fresh spot -- no dot can be followed for long;
* from rung 10 a third of the trials ask instead **which way the front
  turns**. Seen straight on, a cloud turning one way and its depth
  reflection turning the other give the same picture, so a little
  perspective is the only tell: near dots slide faster and look bigger.
  It weakens up the ladder;
* from rung 12 a share of the dots is noise, and the wrong choices are
  solids like the right one;
* from rung 16 fewer dots, more noise, shorter lives; from 20 six
  choices and a slower turn; from 25 fifty dots, sixty per cent noise.

A trial is right or wrong. Clocked: the evidence is motion.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import functools
import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

SOLIDS = ('sphere', 'cube', 'cylinder', 'cone', 'torus', 'pyramid',
          'saddle', 'helix')
NAMES = {'sphere': _('Ball'), 'cube': _('Cube'), 'cylinder': _('Cylinder'),
         'cone': _('Cone'), 'torus': _('Ring'), 'pyramid': _('Pyramid'),
         'saddle': _('Saddle'), 'helix': _('Spring')}
#: Solids that look alike, to draw the hard wrong choices from.
ALIKE = {'sphere': ('cylinder', 'cube', 'torus'),
         'cube': ('cylinder', 'pyramid', 'sphere'),
         'cylinder': ('cube', 'sphere', 'cone'),
         'cone': ('pyramid', 'cylinder', 'saddle'),
         'torus': ('helix', 'sphere', 'cylinder'),
         'pyramid': ('cone', 'cube', 'saddle'),
         'saddle': ('cone', 'pyramid', 'torus'),
         'helix': ('torus', 'cylinder', 'saddle')}
#: Far apart, for the easy rungs.
GROUPS = (('sphere', 'cube', 'cylinder'), ('cone', 'pyramid'),
          ('torus', 'helix'), ('saddle',))

#: Seconds a turn takes, and the forward tilt that shows the top a bit.
TILT = math.radians(14)
#: Page half-size of the view, in solid units.
VIEW = 1.35


class Grade(NamedTuple):
    rung: int
    choices: int
    dots: int
    noise: float
    life: Optional[float]
    spin_share: float
    #: Eye distance in solid radii for the spin question; None: no tell.
    eye: float
    period: float
    alike: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 4:
        choices = 3
    elif r < 7:
        choices = 4
    elif r < 20:
        choices = 5
    else:
        choices = 6
    if r < 16:
        dots = 300
    elif r < 20:
        dots = 150
    elif r < 25:
        dots = 90
    else:
        dots = 50
    noise = 0.0 if r < 12 else (0.3 if r < 16 else (0.5 if r < 25
                                                    else 0.6))
    life = None if r < 7 else (0.5 if r < 16 else 0.25)
    return Grade(rung=r, choices=choices, dots=dots, noise=noise, life=life,
                 spin_share=0.0 if r < 10 else 1 / 3.0,
                 eye=min(14.0, 3.0 + 0.6 * max(0, r - 10)),
                 period=4.0 if r < 20 else 7.0, alike=r >= 12)


class Puzzle(NamedTuple):
    rung: int
    seed: int
    solid: str
    kind: str                 # 'shape' or 'spin'
    #: +1: the front moves right; -1: left.
    way: int
    choices: Tuple[str, ...]
    answer: int
    #: Names of the solids behind each choice (shape questions).
    options: Tuple[str, ...]
    level: Grade
    question: str


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    solid = draw.choice(SOLIDS)
    way = draw.choice((1, -1))
    if draw.random() < level.spin_share:
        choices = (_('Front turns left'), _('Front turns right'))
        return Puzzle(level.rung, seed, solid, 'spin', way, choices,
                      0 if way < 0 else 1, (), level,
                      _('Which way does the front of it turn?'))
    if level.alike:
        pool = list(ALIKE[solid])
        rest = [s for s in SOLIDS if s != solid and s not in pool]
        draw.shuffle(rest)
        wrong = (pool + rest)[:level.choices - 1]
    else:
        mine = next(g for g in GROUPS if solid in g)
        far = [s for s in SOLIDS if s not in mine]
        near = [s for s in mine if s != solid]
        draw.shuffle(far)
        draw.shuffle(near)
        wrong = (far + near)[:level.choices - 1]
    options = list(wrong)
    answer = draw.randrange(level.choices)
    options.insert(answer, solid)
    return Puzzle(level.rung, seed, solid, 'shape', way,
                  tuple(NAMES[s] for s in options), answer, tuple(options),
                  level, _('What solid are the dots on?'))


# --- the dots ------------------------------------------------------------

def surface(solid: str, draw: random.Random) -> Tuple[float, float, float]:
    """A point spread evenly over the solid's surface, size about one."""
    u, v = draw.random(), draw.random()
    if solid == 'sphere':
        y = 2 * u - 1
        a = 2 * math.pi * v
        r = math.sqrt(1 - y * y)
        return (r * math.cos(a), y, r * math.sin(a))
    if solid == 'cube':
        face = draw.randrange(6)
        a, b = 2 * u - 1, 2 * v - 1
        s = 0.8
        p = [(s, a * s, b * s), (-s, a * s, b * s), (a * s, s, b * s),
             (a * s, -s, b * s), (a * s, b * s, s), (a * s, b * s, -s)]
        return p[face]
    if solid == 'cylinder':
        r, h = 0.8, 0.9
        side = 2 * math.pi * r * 2 * h
        caps = 2 * math.pi * r * r
        a = 2 * math.pi * v
        if u * (side + caps) < side:
            return (r * math.cos(a), draw.uniform(-h, h), r * math.sin(a))
        rr = r * math.sqrt(draw.random())
        return (rr * math.cos(a), h if draw.random() < 0.5 else -h,
                rr * math.sin(a))
    if solid == 'cone':
        r, h = 0.95, 1.8
        slant = math.pi * r * math.hypot(r, h)
        base = math.pi * r * r
        a = 2 * math.pi * v
        if u * (slant + base) < slant:
            t = math.sqrt(draw.random())          # area grows toward base
            return (t * r * math.cos(a), 0.9 - t * h, t * r * math.sin(a))
        rr = r * math.sqrt(draw.random())
        return (rr * math.cos(a), -0.9, rr * math.sin(a))
    if solid == 'torus':
        big, small = 0.72, 0.3
        while True:
            a, b = 2 * math.pi * u, 2 * math.pi * v
            if draw.random() * (big + small) <= big + small * math.cos(b):
                break
            u, v = draw.random(), draw.random()
        rr = big + small * math.cos(b)
        return (rr * math.cos(a), small * math.sin(b), rr * math.sin(a))
    if solid == 'pyramid':
        h, s = 1.8, 0.9
        side = draw.randrange(5)
        if side == 4:
            return (s * (2 * u - 1), -0.9, s * (2 * v - 1))
        t = math.sqrt(draw.random())
        a = (2 * u - 1) * t * s
        corners = ((1, 1), (-1, 1), (-1, -1), (1, -1))
        (x0, z0), (x1, z1) = corners[side], corners[(side + 1) % 4]
        mx, mz = (x0 + x1) / 2 * s * t, (z0 + z1) / 2 * s * t
        dx, dz = (x1 - x0) / 2, (z1 - z0) / 2
        return (mx + dx * a, 0.9 - t * h, mz + dz * a)
    if solid == 'saddle':
        x, z = 2 * u - 1, 2 * v - 1
        return (x * 0.9, 0.75 * (x * x - z * z), z * 0.9)
    # helix: a coiled tube
    turns = 2.5
    a = 2 * math.pi * turns * u
    b = 2 * math.pi * v
    big, small = 0.7, 0.16
    rr = big + small * math.cos(b)
    y = -0.9 + 1.8 * u + small * math.sin(b)
    return (rr * math.cos(a), y, rr * math.sin(a))


@functools.lru_cache(maxsize=20000)
def _spot(seed: int, solid: str, k: int, cycle: int):
    draw = random.Random((seed * 1000003 + k) * 7919 + cycle)
    return surface(solid, draw), draw.random()


@functools.lru_cache(maxsize=20000)
def _speck(seed: int, k: int, cycle: int):
    draw = random.Random((seed * 1000033 + k) * 6151 + cycle)
    return ((draw.uniform(-1, 1), draw.uniform(-1, 1)),
            (draw.uniform(-0.3, 0.3), draw.uniform(-0.3, 0.3)))


def dots(puzzle: Puzzle, t: float) -> List[Tuple[float, float, float]]:
    """(page x, page y, size) of every dot at time *t*, in solid units;
    size is one but for the spin question's perspective."""
    level = puzzle.level
    angle = puzzle.way * 2 * math.pi * t / level.period
    ca, sa = math.cos(angle), math.sin(angle)
    ct, st = math.cos(TILT), math.sin(TILT)
    noise = int(round(level.dots * level.noise))
    out = []
    eye = level.eye if puzzle.kind == 'spin' else None
    for k in range(level.dots - noise):
        cycle = 0
        if level.life:
            phase = (k * 0.6180339887) % 1.0
            cycle = int(t / level.life + phase)
        (x, y, z), _r = _spot(puzzle.seed, puzzle.solid, k, cycle)
        # Turn about the vertical; the front (toward the eye, -z) of a
        # solid turning with way +1 moves right.
        x, z = x * ca - z * sa, x * sa + z * ca
        # Tilt forward, to show a little of the top.
        y, z = y * ct - z * st, y * st + z * ct
        if eye:
            k_ = eye / (eye + z)
            out.append((x * k_, y * k_, k_))
        else:
            out.append((x, y, 1.0))
    for k in range(noise):
        cycle = int(t / (level.life or 1.0) + (k * 0.381966) % 1.0)
        (x0, y0), (vx, vy) = _speck(puzzle.seed, k, cycle)
        age = (t / (level.life or 1.0) + (k * 0.381966) % 1.0) - cycle
        out.append((x0 + vx * age, y0 + vy * age, 1.0))
    return out
