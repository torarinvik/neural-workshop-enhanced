# -*- coding: utf-8 -*-
"""Where Was It?: look round a few rooms; one comes back changed.

A trial shows rooms one after another -- a tiled floor and solids
standing on its squares -- for as long as the player likes. Then one of
them comes back with one change, and the player clicks where it is:
the thing that moved, the square a missing thing stood on, either of
two that swapped, or the thing that changed colour. The rooms seen
after the tested one, and before it, are what makes it hard: memory
for where, under interference.

* rungs 1-3: one room of four things on a four-by-three floor; a thing
  moved or gone;
* rungs 4-6: two rooms, then one of them;
* rungs 7-9: three rooms, five things; two may **swap**, or one
  change colour;
* rungs 10-12: every room holds **the same things**, only placed
  differently -- the rooms now get in each other's way; five-by-four;
* rungs 13-15: four rooms;
* rungs 16-19: the room comes back seen **from another side**, 25 to
  45 degrees round;
* from rung 20 five rooms of seven things on six-by-five, seen from
  anywhere round, and a moved thing moves only to a neighbouring
  square.

A click is right or wrong.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import nearer, pov, space
from .i18n import _

KINDS = nearer.KINDS
COLOURS = ((214, 96, 80), (80, 140, 214), (96, 176, 104), (226, 180, 64),
           (160, 104, 196), (90, 186, 186), (230, 140, 180),
           (120, 120, 128))
TINTS = ((236, 226, 206), (214, 226, 236), (222, 236, 214),
         (236, 216, 222), (230, 230, 210))
NAMES = ('the study', 'the kitchen', 'the hall', 'the bedroom',
         'the workshop')


class Grade(NamedTuple):
    rung: int
    rooms: int
    things: int
    cols: int
    rows: int
    changes: Tuple[str, ...]
    shared: bool
    #: Least and most turn of the view at the test, degrees.
    turn: Tuple[float, float]
    near_move: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    rooms = 1 if r < 4 else (2 if r < 7 else (3 if r < 13 else
                                              (4 if r < 20 else 5)))
    things = 4 if r < 7 else (5 if r < 10 else (6 if r < 20 else 7))
    cols, rows = (4, 3) if r < 10 else ((5, 4) if r < 20 else (6, 5))
    changes = ('moved', 'gone') if r < 7 else ('moved', 'gone', 'swapped',
                                               'recoloured')
    turn = (0.0, 0.0) if r < 16 else ((25.0, 45.0) if r < 20 else
                                      (30.0, 180.0))
    return Grade(r, rooms, things, cols, rows, changes, r >= 10, turn,
                 r >= 20)


class Thing(NamedTuple):
    cell: int
    kind: str
    colour: Tuple[int, int, int]
    size: float
    yaw: float


class Room(NamedTuple):
    name: str
    tint: Tuple[int, int, int]
    things: Tuple[Thing, ...]


class Puzzle(NamedTuple):
    rung: int
    cols: int
    rows: int
    rooms: Tuple[Room, ...]
    tested: int
    changed: Room
    change: str
    #: The squares a right click may land on.
    answer: Tuple[int, ...]
    #: The view at the test: radians round from the front.
    angle: float
    question: str


def _neighbours(cell: int, cols: int, rows: int) -> List[int]:
    c, r = cell % cols, cell // cols
    out = []
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if 0 <= c + dc < cols and 0 <= r + dr < rows:
            out.append((r + dr) * cols + c + dc)
    return out


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    cells = level.cols * level.rows

    def set_of_things():
        colours = draw.sample(COLOURS, level.things)
        return [(draw.choice(KINDS), colour, draw.uniform(0.5, 0.75))
                for colour in colours]
    shared = set_of_things()
    tints = list(TINTS)
    names = list(NAMES)
    draw.shuffle(tints)
    draw.shuffle(names)
    rooms = []
    for k in range(level.rooms):
        kinds = shared if level.shared else set_of_things()
        spots = draw.sample(range(cells), level.things)
        rooms.append(Room(names[k], tints[k], tuple(
            Thing(spot, kind, colour, size, draw.uniform(0, math.pi / 2))
            for spot, (kind, colour, size) in zip(spots, kinds))))
    tested = draw.randrange(level.rooms)
    room = rooms[tested]
    things = list(room.things)
    change = draw.choice(level.changes)
    taken = {t.cell for t in things}
    i = draw.randrange(len(things))
    if change == 'moved':
        free = [c for c in range(cells) if c not in taken]
        if level.near_move:
            near = [c for c in _neighbours(things[i].cell, level.cols,
                                           level.rows) if c not in taken]
            free = near or free
        to = draw.choice(free)
        things[i] = things[i]._replace(cell=to)
        answer = (to,)
        question = _('Something in %s has moved. Click it.') % room.name
    elif change == 'gone':
        answer = (things[i].cell,)
        del things[i]
        question = _('Something in %s has gone. Click where it stood.') \
            % room.name
    elif change == 'swapped':
        j = draw.choice([k for k in range(len(things)) if k != i])
        a, b = things[i].cell, things[j].cell
        things[i] = things[i]._replace(cell=b)
        things[j] = things[j]._replace(cell=a)
        answer = (a, b)
        question = _('Two things in %s have swapped places. Click one.') \
            % room.name
    else:
        used = {t.colour for t in things}
        colour = draw.choice([c for c in COLOURS if c not in used])
        things[i] = things[i]._replace(colour=colour)
        answer = (things[i].cell,)
        question = _('Something in %s has changed colour. Click it.') \
            % room.name
    turn = math.radians(draw.uniform(*level.turn)) * draw.choice((1, -1))
    return Puzzle(level.rung, level.cols, level.rows, tuple(rooms), tested,
                  room._replace(things=tuple(things)), change,
                  tuple(sorted(answer)), turn, question)


# --- drawing -------------------------------------------------------------

def camera(cols: int, rows: int, angle: float = 0.0) -> space.Camera:
    """From the front and above, turned *angle* round the middle."""
    mid = (cols / 2.0, 0.0, rows / 2.0)
    back = rows / 2.0 + 4.2
    eye = (mid[0] - back * math.sin(angle), 5.2 + 0.25 * max(cols, rows),
           mid[2] - back * math.cos(angle))
    return space.Camera(eye, (mid[0], 0.0, mid[2] + 0.2), focal=1.0)


def cell_corners(cell: int, cols: int):
    c, r = cell % cols, cell // cols
    return ((c, 0.0, r), (c + 1, 0.0, r), (c + 1, 0.0, r + 1),
            (c, 0.0, r + 1))


def scene(cols: int, rows: int, room: Room, angle: float = 0.0
          ) -> List[space.Painted]:
    """The floor and the things, back to front, in page units. Floor
    squares are tagged ('cell', i); a thing's faces are tagged with the
    square it stands on."""
    cam = camera(cols, rows, angle)
    floor = []
    for cell in range(cols * rows):
        c, r = cell % cols, cell // cols
        shade = 1.0 if (c + r) % 2 == 0 else 0.93
        colour = tuple(int(v * shade) for v in room.tint)
        pts = tuple(cam.project(p) for p in cell_corners(cell, cols))
        mid = ((c + 0.5), 0.0, (r + 0.5))
        floor.append((cam.depth(mid), space.Painted(pts, colour, 0.0,
                                                    ('cell', cell))))
    floor.sort(key=lambda pair: -pair[0])
    out = [p for _d, p in floor]
    faces = []
    for thing in room.things:
        c, r = thing.cell % cols, thing.cell // cols
        tall = 1.5 if thing.kind == 'tall' else 1.0
        height = thing.size * tall
        solid = nearer.Solid(thing.kind, (c + 0.5, height / 2, r + 0.5),
                             thing.size, thing.yaw, thing.colour)
        faces += pov.tall_faces(solid, thing.cell)
    out += space.render(faces, cam, nearer.LIGHT)
    return out


def inside(poly, x: float, y: float) -> bool:
    hit = False
    n = len(poly)
    for k in range(n):
        (x0, y0), (x1, y1) = poly[k - 1], poly[k]
        if (y0 > y) != (y1 > y):
            if x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                hit = not hit
    return hit


def pick(painted: List[space.Painted], x: float, y: float
         ) -> Optional[int]:
    """The square under a page point: the thing drawn on top there, or
    the floor square."""
    for p in reversed(painted):
        if p.tag is None or not inside(p.points, x, y):
            continue
        if isinstance(p.tag, tuple):
            return p.tag[1]
        return p.tag
    return None


def bounds(cols: int, rows: int, angle: float = 0.0):
    cam = camera(cols, rows, angle)
    pts = [cam.project((x, y, z)) for x in (0, cols) for z in (0, rows)
           for y in (0.0, 1.2)]
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))
