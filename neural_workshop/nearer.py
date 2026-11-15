# -*- coding: utf-8 -*-
"""Which Is Nearer?: a few solids in a scene; which is closest?

Depth is never given straight. The eye reads it from cues, and each
rung takes one away until a single cue is left:

* rungs 1-6: the solids stand on a gridded floor, alike in kind and
  size -- nearer ones are bigger, lower on the page, on wider squares,
  and hide what is behind;
* rungs 7-9: sizes and kinds differ, sized so a solid's size on the
  page says nothing of its distance -- where it stands on the floor
  does;
* rungs 10-12: the solids float, each placed on the page with no regard
  to its depth; a shadow on the floor under each is what is left;
* rungs 13-15: no floor and no shadows, the solids crowded together:
  which hides which is all there is;
* rungs 16-19: spread out again, nothing hiding anything: the eye
  sways from side to side, and nearer things slide farther -- motion
  parallax, the only cue;
* from rung 20: put **all** of them in order, nearest first.

Two solids at rung one, up to six; and the nearest is nearer than the
next by a factor of 1.6 at rung one, 1.1 by rung nineteen, 1.04 at
thirty.

A trial is right or wrong. Clocked, because from rung 16 the evidence
is motion.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import space
from .i18n import _

EYE_Y = 1.6
#: Half the page's width, in page units, at focal one: a 58-degree view.
HALF_W = 0.55
HALF_H = 0.34
#: Sway: how far the eye moves either way, and how long one sway takes.
SWAY = 0.45
SWAY_PERIOD = 2.4

COLOURS = ((214, 96, 80), (80, 140, 214), (96, 176, 104), (226, 180, 64),
           (160, 104, 196), (90, 186, 186))
KINDS = ('cube', 'tall', 'pyramid', 'prism')


class Grade(NamedTuple):
    rung: int
    count: int
    cue: str          # 'size', 'floor', 'shadow', 'hiding', 'motion'
    ratio: float      # nearest over next, at least
    order: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 7:
        cue = 'size'
    elif r < 10:
        cue = 'floor'
    elif r < 13:
        cue = 'shadow'
    elif r < 16:
        cue = 'hiding'
    else:
        cue = 'motion'
    if r < 20:
        count = min(5, 2 + (r - 1) % 3 + (r - 1) // 9)
        ratio = 1.6 - 0.5 * (r - 1) / 18.0
    else:
        count = min(6, 3 + (r - 20) // 3)
        ratio = max(1.04, 1.1 - 0.006 * (r - 20))
    return Grade(rung=r, count=count, cue=cue, ratio=ratio, order=r >= 20)


class Solid(NamedTuple):
    kind: str
    centre: space.Vec
    size: float
    yaw: float
    colour: Tuple[int, int, int]


class Puzzle(NamedTuple):
    rung: int
    cue: str
    #: Left to right on the page; port i is solid i.
    solids: Tuple[Solid, ...]
    choices: Tuple[str, ...]
    answer: int
    #: Every solid, nearest first.
    order: Tuple[int, ...]
    ask_order: bool
    question: str


def camera(cue: str, t: float = 0.0) -> space.Camera:
    x = SWAY * math.sin(2 * math.pi * t / SWAY_PERIOD) \
        if cue == 'motion' else 0.0
    return space.Camera((x, EYE_Y, 0.0), (x, EYE_Y, 10.0), focal=1.0)


def _depths(draw: random.Random, level: Grade) -> List[float]:
    near = draw.uniform(4.0, 7.0)
    out = [near]
    for k in range(1, level.count):
        if level.order or k == 1:
            step = draw.uniform(level.ratio, level.ratio * 1.12)
        else:
            step = draw.uniform(1.0, level.ratio * 1.4)
        out.append(out[-1] * max(step, 1.02))
    if not level.order:
        # Past the second, any order beyond the nearest: shuffle the
        # rest among themselves, keeping all behind the nearest's next.
        tail = out[2:]
        draw.shuffle(tail)
        out = out[:2] + [max(t, out[1] * 1.02) for t in tail]
    return out


def _place(draw: random.Random, level: Grade, depths: List[float]
           ) -> List[Tuple[float, float, float]]:
    """(page x, page y, page radius) for each solid."""
    n = len(depths)
    spots: List[Tuple[float, float, float]] = []
    for z in depths:
        for _try in range(400):
            if level.cue in ('size',):
                radius = 0.5 / z
            elif level.cue == 'hiding':
                radius = draw.uniform(0.07, 0.11)
            else:
                radius = draw.uniform(0.045, 0.075)
            if level.cue == 'hiding':
                cx, cy = draw.uniform(-0.2, 0.2), draw.uniform(-0.13, 0.13)
                spot = (cx, cy, radius)
                if spots and not any(
                        math.hypot(cx - x, cy - y) < (radius + r) * 0.8
                        for x, y, r in spots):
                    continue
                spots.append(spot)
                break
            x = draw.uniform(-HALF_W + 0.1, HALF_W - 0.1)
            if level.cue in ('size', 'floor'):
                y = -EYE_Y / z          # standing on the floor
            elif level.cue == 'shadow':
                y = draw.uniform(-0.14, 0.2)
            else:
                y = draw.uniform(-HALF_H + 0.1, HALF_H - 0.1)
            if any(math.hypot(x - sx, y - sy) < (radius + sr) * 1.6 + 0.04
                   for sx, sy, sr in spots):
                continue
            spots.append((x, y, radius))
            break
        else:
            return []
    del n
    return spots


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    for attempt in range(200):
        draw = random.Random(seed * 211 + attempt)
        depths = _depths(draw, level)
        spots = _place(draw, level, depths)
        if spots:
            break
    colours = list(COLOURS)
    draw.shuffle(colours)
    solids = []
    for k, (z, (px, py, pr)) in enumerate(zip(depths, spots)):
        kind = 'cube' if level.cue == 'size' else draw.choice(KINDS)
        size = 2 * pr * z           # its page radius, at this depth
        if level.cue == 'size':
            size = 1.0
        x = px * z
        if level.cue in ('size', 'floor'):
            y = size / 2 * (1.6 if kind == 'tall' else 1.0)
        else:
            y = EYE_Y + py * z
            if level.cue == 'shadow':
                y = max(y, size + 0.3)
        colour = colours[k % len(colours)]
        solids.append(Solid(kind, (x, y, z), size,
                            draw.uniform(0, math.pi / 2), colour))
    # Left to right on the page, which is how ports and buttons count.
    cam = camera(level.cue)
    solids.sort(key=lambda s: cam.project(s.centre)[0])
    order = tuple(sorted(range(len(solids)),
                         key=lambda i: solids[i].centre[2]))
    labels = tuple(str(i + 1) for i in range(len(solids)))
    question = (_('Click them in order, nearest first') if level.order
                else _('Click the nearest one'))
    return Puzzle(level.rung, level.cue, tuple(solids), labels, order[0],
                  order, level.order, question)


def solid_faces(solid: Solid, tag: object) -> List[space.Face]:
    s = solid.size
    if solid.kind == 'cube':
        return space.box_faces(solid.centre, (s, s, s), solid.colour, tag,
                               solid.yaw)
    if solid.kind == 'tall':
        return space.box_faces(solid.centre, (s * 0.7, s * 1.6, s * 0.7),
                               solid.colour, tag, solid.yaw)
    if solid.kind == 'pyramid':
        return space.prism_faces(solid.centre, s * 0.62, s, 4,
                                 solid.colour, tag, top=0.0, yaw=solid.yaw)
    return space.prism_faces(solid.centre, s * 0.55, s, 6, solid.colour,
                             tag, yaw=solid.yaw)


#: Lit from behind the eye, above and to the left.
LIGHT = space.unit((-0.4, 0.8, -0.6))
GROUND = (196, 190, 176)
GRID = (150, 144, 132)
SHADOW = (120, 116, 108)


def _flat(camera_, corners, colour, tag=None) -> Optional[space.Painted]:
    pts = [camera_.project(p) for p in corners]
    if any(p is None for p in pts):
        return None
    return space.Painted(tuple(pts), colour, 1e9, tag, False)


def scene(puzzle: Puzzle, t: float = 0.0) -> List[space.Painted]:
    """Everything drawn at time *t*, back to front, in page units."""
    cam = camera(puzzle.cue, t)
    out: List[space.Painted] = []
    if puzzle.cue in ('size', 'floor', 'shadow'):
        far = 80.0
        ground = _flat(cam, ((-40, 0, 0.6), (40, 0, 0.6), (40, 0, far),
                             (-40, 0, far)), GROUND)
        out.append(ground)
        if puzzle.cue in ('size', 'floor'):
            w = 0.03
            for gx in range(-20, 21, 2):
                p = _flat(cam, ((gx - w, 0, 0.6), (gx + w, 0, 0.6),
                                (gx + w, 0, far), (gx - w, 0, far)), GRID)
                if p:
                    out.append(p)
            z = 1.0
            while z < far:
                p = _flat(cam, ((-40, 0, z - w * z / 4),
                                (40, 0, z - w * z / 4),
                                (40, 0, z + w * z / 4),
                                (-40, 0, z + w * z / 4)), GRID)
                if p:
                    out.append(p)
                z += 2.0
        for solid in sorted(puzzle.solids, key=lambda s: -s.centre[2]):
            x, _y, z = solid.centre
            r = solid.size * 0.6
            p = _flat(cam, ((x - r, 0, z - r), (x + r, 0, z - r),
                            (x + r, 0, z + r), (x - r, 0, z + r)), SHADOW)
            if p:
                out.append(p)
    faces: List[space.Face] = []
    for i, solid in enumerate(puzzle.solids):
        faces += solid_faces(solid, i)
    out += space.render(faces, cam, LIGHT)
    return space.clipped(out, -HALF_W, -HALF_H, HALF_W, HALF_H)


def boxes(painted: List[space.Painted]
          ) -> List[Tuple[int, Tuple[float, float, float, float]]]:
    """(solid, page bounds) for each solid seen, nearest first."""
    seen = {}
    for p in painted:
        if isinstance(p.tag, int):
            seen.setdefault(p.tag, []).append(p)
    out = []
    for tag, polys in seen.items():
        out.append((min(q.depth for q in polys), tag, space.bounds(polys)))
    out.sort()
    return [(tag, b) for _d, tag, b in out]
