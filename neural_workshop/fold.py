# -*- coding: utf-8 -*-
"""Fold It: a flat net of six squares; what cube does it fold into?

A net is laid flat with its printed side up and its squares folded
down, away from the eye, so the print ends up outside. Every one of the
eleven nets of a cube can be dealt; which square lands where, and which
way up its mark ends, is worked out by carrying a frame -- the square's
outward normal and its right and up directions -- across every fold.

* rungs 1-3: lettered squares: **which face is opposite** this one? The
  plain cross-shaped net at rung one, any net after;
* rungs 4-9: coloured squares and a row of cubes, each showing three
  faces: **which cube does it fold into?** The wrong cubes have two
  faces swapped. Three cubes, four from rung 7;
* rungs 10-12: marks that point a way, on coloured squares: a wrong
  cube may also have one mark turned;
* rungs 13-15: one colour for every square: the marks alone;
* rungs 16-19: five cubes, every wrong one a single turned mark or the
  mirror image of the right cube;
* from rung 20 marks that have a handedness, so a mirrored mark is a
  different mark; six cubes from 25.

Every wrong cube is checked against all 24 ways the right one could sit:
none of them shows what a wrong cube shows. A choice is right or wrong.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import space
from .i18n import _

Cell = Tuple[int, int]
IVec = Tuple[int, int, int]


# --- nets ----------------------------------------------------------------

def neg(v: IVec) -> IVec:
    return (-v[0], -v[1], -v[2])


def icross(a: IVec, b: IVec) -> IVec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


class Frame(NamedTuple):
    normal: IVec
    right: IVec
    up: IVec


def fold(cells) -> Optional[Dict[Cell, Frame]]:
    """Each square's frame on the cube, or None if two land on one face.

    The first square lies face up (normal toward the eye, +z); the rest
    fold away from the eye about their shared edges."""
    cells = sorted(cells)
    frames = {cells[0]: Frame((0, 0, 1), (1, 0, 0), (0, 1, 0))}
    todo = [cells[0]]
    while todo:
        cell = todo.pop()
        n, r, u = frames[cell]
        x, y = cell
        steps = {(x + 1, y): Frame(r, neg(n), u),
                 (x - 1, y): Frame(neg(r), n, u),
                 (x, y + 1): Frame(u, r, neg(n)),
                 (x, y - 1): Frame(neg(u), r, n)}
        for nxt, frame in steps.items():
            if nxt in cells and nxt not in frames:
                frames[nxt] = frame
                todo.append(nxt)
    normals = {f.normal for f in frames.values()}
    if len(frames) != 6 or len(normals) != 6:
        return None
    return frames


def _canonical(cells) -> Tuple[Cell, ...]:
    forms = []
    for flip in (1, -1):
        for turn in range(4):
            pts = []
            for x, y in cells:
                x *= flip
                for _t in range(turn):
                    x, y = -y, x
                pts.append((x, y))
            lx, ly = min(p[0] for p in pts), min(p[1] for p in pts)
            forms.append(tuple(sorted((x - lx, y - ly) for x, y in pts)))
    return min(forms)


def _all_nets() -> List[Tuple[Cell, ...]]:
    found = {}
    start = (0, 0)
    shapes = {(start,)}
    for _size in range(5):
        grown = set()
        for shape in shapes:
            for x, y in shape:
                for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if nxt not in shape:
                        grown.add(tuple(sorted(shape + (nxt,))))
        shapes = grown
    for shape in shapes:
        key = _canonical(shape)
        if key not in found and fold(key) is not None:
            found[key] = key
    return sorted(found.values())


#: The eleven nets of a cube.
NETS = _all_nets()
#: The cross: a column of four with one square either side of the second.
CROSS = _canonical(((1, 0), (1, 1), (1, 2), (1, 3), (0, 2), (2, 2)))


# --- marks ---------------------------------------------------------------

class Glyph(NamedTuple):
    name: str
    #: Convex or simple polygons in [-1, 1] squared, pointing up.
    parts: Tuple[Tuple[Tuple[float, float], ...], ...]
    #: Quarter turns that leave it unchanged: 1, 2 or 4.
    symmetry: int
    #: True if its mirror image is a different mark.
    handed: bool


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


GLYPHS = {
    'none': Glyph('none', (), 4, False),
    'dot': Glyph('dot', (tuple((0.5 * c, 0.5 * s) for c, s in (
        (1, 0), (0.71, 0.71), (0, 1), (-0.71, 0.71), (-1, 0),
        (-0.71, -0.71), (0, -1), (0.71, -0.71))),), 4, False),
    'plus': Glyph('plus', (_rect(-0.8, -0.22, 0.8, 0.22),
                           _rect(-0.22, -0.8, 0.22, 0.8)), 4, False),
    'bar': Glyph('bar', (_rect(-0.85, -0.25, 0.85, 0.25),), 2, False),
    'arrow': Glyph('arrow', (((0, 0.9), (0.7, 0.15), (0.25, 0.15),
                              (0.25, -0.85), (-0.25, -0.85), (-0.25, 0.15),
                              (-0.7, 0.15)),), 1, False),
    'triangle': Glyph('triangle', (((0, 0.85), (0.8, -0.7),
                                    (-0.8, -0.7)),), 1, False),
    'half': Glyph('half', (_rect(-0.85, 0.0, 0.85, 0.85),), 1, False),
    'tee': Glyph('tee', (_rect(-0.85, 0.5, 0.85, 0.88),
                         _rect(-0.2, -0.88, 0.2, 0.5)), 1, False),
    'ell': Glyph('ell', (_rect(-0.6, -0.5, -0.2, 0.88),
                         _rect(-0.6, -0.88, 0.7, -0.5)), 1, True),
    'flag': Glyph('flag', (_rect(-0.55, -0.88, -0.2, 0.88),
                           ((-0.2, 0.88), (0.75, 0.55), (-0.2, 0.2))),
                  1, True),
}
POINTING = ('arrow', 'triangle', 'half', 'tee')
HANDED = ('ell', 'flag')

COLOURS = ((228, 102, 90), (90, 150, 226), (110, 192, 110),
           (238, 196, 72), (176, 120, 210), (120, 206, 206))
PLAIN = (226, 222, 212)
INK = (44, 46, 54)
LETTERS = 'ABCDEF'


class Mark(NamedTuple):
    glyph: str
    colour: Tuple[int, int, int]
    #: Which way the mark points, in the cube's own frame.
    up: IVec
    mirrored: bool = False


Cube = Dict[IVec, Mark]


def turn_up(frame: Frame, quarter: int) -> IVec:
    """A mark turned *quarter* quarter-turns anticlockwise on its square:
    the way it points, on the cube."""
    r, u = frame.right, frame.up
    return (u, neg(r), neg(u), r)[quarter % 4]


def net_up(quarter: int) -> Tuple[int, int]:
    return ((0, 1), (-1, 0), (0, -1), (1, 0))[quarter % 4]


# --- views ---------------------------------------------------------------

#: The three faces a cube shows the eye.
SEEN = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def _turned(turn, v: IVec) -> IVec:
    return tuple(sum(turn[i][k] * v[k] for k in range(3)) for i in range(3))


def placed(cube: Cube, turn) -> Cube:
    return {_turned(turn, n): mark._replace(up=_turned(turn, mark.up))
            for n, mark in cube.items()}


def signature(cube: Cube, turn) -> Tuple:
    """What the eye sees of *cube* sitting as *turn* puts it."""
    seen = placed(cube, turn)
    out = []
    for n in SEEN:
        mark = seen[n]
        glyph = GLYPHS[mark.glyph]
        up = mark.up
        if glyph.symmetry == 4:
            up = None
        elif glyph.symmetry == 2:
            up = max(up, neg(up))
        out.append((mark.glyph, mark.colour, up,
                    mark.mirrored and glyph.handed))
    return tuple(out)


def every_view(cube: Cube) -> set:
    return {signature(cube, t) for t in space.GRID_TURNS}


def mirror(cube: Cube) -> Cube:
    def m(v):
        return (-v[0], v[1], v[2])
    return {m(n): mark._replace(up=m(mark.up), mirrored=not mark.mirrored)
            for n, mark in cube.items()}


# --- deals ---------------------------------------------------------------

class Grade(NamedTuple):
    rung: int
    kind: str          # 'opposite' or 'cube'
    any_net: bool
    choices: int
    colours: bool
    glyphs: Tuple[str, ...]
    #: Ways a wrong cube may differ: 'swap', 'turn', 'mirror'.
    wrongs: Tuple[str, ...]


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 4:
        return Grade(r, 'opposite', r >= 2, 4, True, ('none',), ())
    if r < 10:
        return Grade(r, 'cube', r >= 5, 3 if r < 7 else 4, True,
                     ('none',), ('swap',))
    if r < 13:
        return Grade(r, 'cube', True, 4, True, POINTING + ('bar', 'dot'),
                     ('swap', 'turn'))
    if r < 16:
        return Grade(r, 'cube', True, 4, False, POINTING + ('bar',),
                     ('swap', 'turn'))
    if r < 20:
        return Grade(r, 'cube', True, 5, False, POINTING,
                     ('turn', 'mirror'))
    return Grade(r, 'cube', True, 5 if r < 25 else 6, False,
                 POINTING + HANDED, ('turn', 'mirror'))


class Puzzle(NamedTuple):
    rung: int
    kind: str
    net: Tuple[Cell, ...]
    #: Per square of the net: its mark, and its quarter turn on the net.
    marks: Tuple[Tuple[str, Tuple[int, int, int], int], ...]
    #: For 'opposite': the square asked about.
    asked: int
    #: The cubes on offer and how each sits ('cube'); empty otherwise.
    cubes: Tuple[Tuple[Tuple[Tuple[IVec, Mark], ...], Tuple], ...]
    choices: Tuple[str, ...]
    answer: int
    question: str


def folded(net, marks) -> Cube:
    frames = fold(net)
    cube = {}
    for cell, (glyph, colour, quarter) in zip(net, marks):
        frame = frames[cell]
        cube[frame.normal] = Mark(glyph, colour, turn_up(frame, quarter))
    return cube


def _wrong(draw: random.Random, cube: Cube, how: str) -> Cube:
    out = dict(cube)
    if how == 'mirror':
        return mirror(cube)
    if how == 'swap':
        a, b = draw.sample(sorted(out), 2)
        ma, mb = out[a], out[b]
        out[a] = mb._replace(up=_perp(draw, a))
        out[b] = ma._replace(up=_perp(draw, b))
        return out
    turnable = [n for n, m in out.items() if GLYPHS[m.glyph].symmetry < 4]
    if not turnable:
        return _wrong(draw, cube, 'swap')
    n = draw.choice(turnable)
    mark = out[n]
    r = icross(mark.up, n)
    out[n] = mark._replace(up=draw.choice((r, neg(r), neg(mark.up))))
    return out


def _perp(draw: random.Random, n: IVec) -> IVec:
    options = [v for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (-1, 0, 0),
                           (0, -1, 0), (0, 0, -1))
               if sum(a * b for a, b in zip(v, n)) == 0]
    return draw.choice(options)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    net = draw.choice(NETS) if level.any_net else CROSS
    colours = list(COLOURS)
    draw.shuffle(colours)
    marks = []
    for k in range(6):
        glyph = draw.choice(level.glyphs)
        colour = colours[k] if level.colours else PLAIN
        marks.append((glyph, colour, draw.randrange(4)))
    if level.kind == 'opposite':
        frames = fold(net)
        asked = draw.randrange(6)
        normal = frames[net[asked]].normal
        opposite = next(i for i, c in enumerate(net)
                        if frames[c].normal == neg(normal))
        others = [i for i in range(6) if i not in (asked, opposite)]
        draw.shuffle(others)
        picks = others[:level.choices - 1]
        answer = draw.randrange(level.choices)
        picks.insert(answer, opposite)
        return Puzzle(level.rung, 'opposite', net, tuple(marks), asked, (),
                      tuple(LETTERS[i] for i in picks), answer,
                      _('Folded up, which face is opposite %s?')
                      % LETTERS[asked])
    cube = folded(net, marks)
    truth = every_view(cube)
    offered: List[Tuple[Cube, Tuple]] = []
    seen = set()
    answer = draw.randrange(level.choices)
    for k in range(level.choices):
        for _try in range(400):
            turn = draw.choice(space.GRID_TURNS)
            if k == answer:
                option = cube
            else:
                option = _wrong(draw, cube, draw.choice(level.wrongs))
            view = signature(option, turn)
            if (k == answer) == (view in truth) and view not in seen:
                break
        seen.add(view)
        offered.append((tuple(sorted(option.items())), turn))
    return Puzzle(level.rung, 'cube', net, tuple(marks), -1,
                  tuple(offered), tuple(str(i + 1)
                                        for i in range(level.choices)),
                  answer, _('Which cube does the net fold into?'))


def check(puzzle: Puzzle) -> bool:
    """From the folding itself: is the answer right and no other?"""
    if puzzle.kind == 'opposite':
        frames = fold(puzzle.net)
        normal = frames[puzzle.net[puzzle.asked]].normal
        letter = puzzle.choices[puzzle.answer]
        other = frames[puzzle.net[LETTERS.index(letter)]].normal
        return other == neg(normal) and sum(
            frames[puzzle.net[LETTERS.index(c)]].normal == neg(normal)
            for c in puzzle.choices) == 1
    truth = every_view(folded(puzzle.net, puzzle.marks))
    hits = [i for i, (cube, turn) in enumerate(puzzle.cubes)
            if signature(dict(cube), turn) in truth]
    return hits == [puzzle.answer]


# --- drawing a cube ------------------------------------------------------

def cube_faces(cube: Cube, turn) -> List[space.Face]:
    """A unit cube with its marks, sitting as *turn* puts it."""
    seen = placed(cube, turn)
    out = []
    centre = (0.0, 0.0, 0.0)
    for n, mark in seen.items():
        nf = tuple(float(v) for v in n)
        r, u = space.frame_of(nf)
        mid = space.mul(nf, 0.5)
        pts = tuple(space.add(mid, space.add(space.mul(r, 0.5 * a),
                                             space.mul(u, 0.5 * b)))
                    for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)))
        out.append(space.Face(pts, mark.colour, nf, centre))
        glyph = GLYPHS[mark.glyph]
        up = tuple(float(v) for v in mark.up)
        right = space.cross(up, nf)
        if mark.mirrored:
            right = space.mul(right, -1)
        for part in glyph.parts:
            gp = tuple(space.add(space.add(mid, space.mul(nf, 0.001)),
                                 space.add(space.mul(right, 0.36 * a),
                                           space.mul(up, 0.36 * b)))
                       for a, b in part)
            out.append(space.Face(gp, INK, nf, centre, bias=1e-4, lit=True))
    return out


def camera() -> space.Camera:
    return space.Camera((4.0, 3.4, 5.0), (0.0, 0.0, 0.0))
