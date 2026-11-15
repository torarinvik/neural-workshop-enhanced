# -*- coding: utf-8 -*-
"""Point of View: a table seen from above, a camera at its edge; what
does the camera see?

The map shows the table from straight above, the solids on it as their
footprints, and a camera with the wedge it looks along. A row of
pictures shows the table from different places; one is what the camera
sees. Taking a view not one's own is the skill.

* rungs 1-3: two or three solids, the camera at the middle of a side,
  three pictures -- the others taken from the other sides;
* rungs 4-6: up to four solids, four pictures;
* rungs 7-9: one wrong picture is the right one **mirrored**, left for
  right;
* rungs 10-12: solids of different heights, so near ones hide far ones;
* rungs 13-15: the camera anywhere around the table, the wrong pictures
  taken from 45 to 90 degrees round from it;
* rungs 16-19: every solid one colour, told apart by shape and height
  alone; five pictures;
* from rung 20 the camera higher or lower, and wrong pictures as little
  as 25 degrees round; up to six solids.

Every wrong picture shows the solids in a different left-to-right order
from the right one, so the order alone can always decide. A choice is
right or wrong.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import nearer, space
from .i18n import _

TABLE = 2.0           # half the table's side
RING = 6.2            # how far the camera stands from the table's middle
LOOK_AT = (0.0, 0.35, 0.0)
TABLE_TOP = (206, 186, 150)
PLAIN = (170, 170, 176)


class Grade(NamedTuple):
    rung: int
    solids: Tuple[int, int]
    choices: int
    sides_only: bool
    #: Least and most turn, degrees, of a wrong picture's camera.
    spread: Tuple[float, float]
    mirror: bool
    heights: bool
    colours: bool
    #: Camera heights to choose from.
    heights_eye: Tuple[float, float]


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    solids = (2, 3) if r < 4 else ((3, 4) if r < 13 else
                                   ((4, 5) if r < 20 else (5, 6)))
    choices = 3 if r < 4 else (4 if r < 16 else 5)
    spread = (90.0, 270.0) if r < 13 else ((45.0, 90.0) if r < 20 else
                                           (25.0, 50.0))
    return Grade(rung=r, solids=solids, choices=choices, sides_only=r < 13,
                 spread=spread, mirror=r >= 7, heights=r >= 10,
                 colours=r < 16,
                 heights_eye=(2.6, 2.6) if r < 20 else (0.9, 5.0))


class Puzzle(NamedTuple):
    rung: int
    solids: Tuple[nearer.Solid, ...]
    #: The camera's angle round the table (radians) and its height.
    angle: float
    eye: float
    #: Each picture: (angle, height, mirrored).
    views: Tuple[Tuple[float, float, bool], ...]
    choices: Tuple[str, ...]
    answer: int
    question: str


def camera(angle: float, eye: float) -> space.Camera:
    pos = (RING * math.cos(angle), eye, RING * math.sin(angle))
    return space.Camera(pos, LOOK_AT, focal=1.0)


def order(solids, angle: float, eye: float, mirrored: bool = False
          ) -> Tuple[int, ...]:
    """The solids left to right as a picture shows them."""
    cam = camera(angle, eye)
    xs = [(cam.project(s.centre)[0] * (-1 if mirrored else 1), i)
          for i, s in enumerate(solids)]
    return tuple(i for _x, i in sorted(xs))


def _signature(solids, view, colours: bool) -> Tuple:
    seq = order(solids, *view)
    if colours:
        return seq
    return tuple((solids[i].kind, round(solids[i].size, 1)) for i in seq)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    for attempt in range(500):
        draw = random.Random(seed * 397 + attempt)
        count = draw.randint(*level.solids)
        colours = list(nearer.COLOURS)
        draw.shuffle(colours)
        kinds = list(nearer.KINDS)
        solids: List[nearer.Solid] = []
        for _place in range(300):
            if len(solids) >= count:
                break
            size = draw.uniform(0.6, 1.0)
            kind = draw.choice(kinds)
            if not level.colours:
                # One colour: shapes (and sizes) must tell them apart.
                taken = {(s.kind, round(s.size, 1)) for s in solids}
                if (kind, round(size, 1)) in taken:
                    continue
            tall = 1.0
            if level.heights:
                tall = draw.choice((0.7, 1.0, 1.6, 2.2))
            x = draw.uniform(-TABLE + 0.6, TABLE - 0.6)
            z = draw.uniform(-TABLE + 0.6, TABLE - 0.6)
            if any(math.hypot(x - s.centre[0], z - s.centre[2]) < 1.15
                   for s in solids):
                continue
            height = size * tall
            solids.append(nearer.Solid(
                kind, (x, height / 2, z), size, draw.uniform(0, math.pi),
                colours[len(solids)] if level.colours else PLAIN))
        if len(solids) < count:
            continue
        if level.sides_only:
            angle = draw.randrange(4) * math.pi / 2
        else:
            angle = draw.uniform(0, 2 * math.pi)
        eye = draw.uniform(*level.heights_eye)
        truth = (angle, eye, False)
        seen = {_signature(solids, truth, level.colours)}
        views = []
        wrong_ok = True
        for k in range(level.choices - 1):
            for _try in range(200):
                if level.mirror and k == 0:
                    view = (angle, eye, True)
                elif level.sides_only:
                    view = (angle + draw.choice((1, 2, 3)) * math.pi / 2,
                            eye, False)
                else:
                    turn = math.radians(draw.uniform(*level.spread))
                    view = (angle + draw.choice((1, -1)) * turn,
                            draw.uniform(*level.heights_eye), False)
                sig = _signature(solids, view, level.colours)
                if sig not in seen:
                    seen.add(sig)
                    views.append(view)
                    break
            else:
                wrong_ok = False
                break
        if wrong_ok:
            break
    answer = draw.randrange(level.choices)
    views.insert(answer, truth)
    return Puzzle(level.rung, tuple(solids), angle, eye, tuple(views),
                  tuple(str(i + 1) for i in range(level.choices)), answer,
                  _('Which picture does the camera on the map take?'))


def tall_faces(solid: nearer.Solid, tag) -> List[space.Face]:
    """A solid stretched to its height (its centre's height is half it)."""
    height = solid.centre[1] * 2
    s = solid.size
    c = solid.centre
    if solid.kind in ('cube', 'tall'):
        w = s * (0.7 if solid.kind == 'tall' else 1.0)
        return space.box_faces(c, (w, height, w), solid.colour, tag,
                               solid.yaw)
    if solid.kind == 'pyramid':
        return space.prism_faces(c, s * 0.62, height, 4, solid.colour, tag,
                                 top=0.0, yaw=solid.yaw)
    return space.prism_faces(c, s * 0.55, height, 6, solid.colour, tag,
                             yaw=solid.yaw)


def picture(puzzle: Puzzle, view) -> List[space.Painted]:
    angle, eye, mirrored = view
    cam = camera(angle, eye)
    top = [cam.project((x, 0.0, z)) for x, z in
           ((-TABLE, -TABLE), (TABLE, -TABLE), (TABLE, TABLE),
            (-TABLE, TABLE))]
    out = [space.Painted(tuple(top), TABLE_TOP, 1e9, None, True)]
    faces = []
    for i, solid in enumerate(puzzle.solids):
        faces += tall_faces(solid, i)
    out += space.render(faces, cam, nearer.LIGHT)
    if mirrored:
        out = [p._replace(points=tuple((-x, y) for x, y in p.points))
               for p in out]
    return out


def footprint(solid: nearer.Solid) -> List[Tuple[float, float]]:
    """The solid's outline seen from straight above, as (x, z)."""
    faces = tall_faces(solid, None)
    base = next(f for f in faces if f.normal[1] < -0.9)
    return [(p[0], p[2]) for p in base.points]
