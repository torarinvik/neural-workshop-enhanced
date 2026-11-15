# -*- coding: utf-8 -*-
"""A small 3D kit for the spatial tasks: vectors, turns, solids, a camera.

Same or Mirror?, Which Is Nearer?, Shape from Motion, Fold It and Point
of View all draw solids the same way. A solid is a list of flat
:class:`Face` s in world space (y up); a :class:`Camera` turns each into
a polygon on the page, nearest last, shaded by one fixed light. Nothing
here touches pyglet: what comes out is plain 2D polygons, so the models
can be tested without a window and the screens only paint.

Drawing order is a painter's: farthest first. Each face carries an
*anchor* to sort by -- the centre of the cube or box it belongs to --
which is exact for a grid of equal cubes seen along any direction and
good enough for boxes standing apart on a table.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import math
import random
from typing import (Iterable, List, NamedTuple, Optional, Sequence, Tuple)

Vec = Tuple[float, float, float]
Mat = Tuple[Vec, Vec, Vec]
Colour = Tuple[int, int, int]
Cube = Tuple[int, int, int]


# --- vectors and turns ---------------------------------------------------

def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def length(a: Vec) -> float:
    return math.sqrt(dot(a, a))


def unit(a: Vec) -> Vec:
    n = length(a) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


IDENTITY: Mat = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def apply(m: Mat, v: Vec) -> Vec:
    return (dot(m[0], v), dot(m[1], v), dot(m[2], v))


def compose(a: Mat, b: Mat) -> Mat:
    """The turn that does *b* and then *a*."""
    cols = list(zip(*b))
    return tuple(tuple(dot(row, col) for col in cols) for row in a)


def rotation(axis: Vec, angle: float) -> Mat:
    """A turn of *angle* radians about *axis*, right-handed."""
    x, y, z = unit(axis)
    c, s = math.cos(angle), math.sin(angle)
    t = 1 - c
    return ((t * x * x + c, t * x * y - s * z, t * x * z + s * y),
            (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
            (t * x * z - s * y, t * y * z + s * x, t * z * z + c))


def random_axis(rng: random.Random) -> Vec:
    while True:
        v = (rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))
        if length(v) > 1e-6:
            return unit(v)


def angle_between(a: Mat, b: Mat) -> float:
    """How far apart two turns are: the angle of the turn from a to b."""
    # trace(a^T b) = 1 + 2 cos(theta)
    trace = sum(dot((a[0][i], a[1][i], a[2][i]),
                    (b[0][i], b[1][i], b[2][i])) for i in range(3))
    return math.acos(max(-1.0, min(1.0, (trace - 1) / 2.0)))


def _grid_turns() -> List[Tuple[Tuple[int, ...], ...]]:
    out = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            m = [[0] * 3 for _ in range(3)]
            for row, col in enumerate(perm):
                m[row][col] = signs[row]
            det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                   - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                   + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
            if det == 1:
                out.append(tuple(tuple(r) for r in m))
    return out


#: The 24 turns that take a cube grid onto itself.
GRID_TURNS = _grid_turns()


# --- polycubes -----------------------------------------------------------

STEPS: Tuple[Cube, ...] = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
                           (0, 0, 1), (0, 0, -1))


def _turn_cube(m, c: Cube) -> Cube:
    return tuple(sum(m[r][k] * c[k] for k in range(3)) for r in range(3))


def canonical(cubes: Iterable[Cube]) -> Tuple[Cube, ...]:
    cubes = list(cubes)
    low = [min(c[i] for c in cubes) for i in range(3)]
    return tuple(sorted(tuple(c[i] - low[i] for i in range(3))
                        for c in cubes))


def shape_key(cubes: Iterable[Cube]) -> Tuple[Cube, ...]:
    """The same for two cube shapes exactly when a turn makes one the
    other."""
    cubes = list(cubes)
    return min(canonical(_turn_cube(m, c) for c in cubes)
               for m in GRID_TURNS)


def mirrored(cubes: Iterable[Cube]) -> Tuple[Cube, ...]:
    return tuple((-x, y, z) for x, y, z in cubes)


def same_shape(a: Iterable[Cube], b: Iterable[Cube]) -> bool:
    return shape_key(a) == shape_key(b)


def chiral(cubes: Sequence[Cube]) -> bool:
    """True when no turn makes the shape its own mirror image."""
    return not same_shape(cubes, mirrored(cubes))


def connected(cubes: Sequence[Cube]) -> bool:
    cubes = set(cubes)
    if not cubes:
        return False
    seen, todo = set(), [next(iter(cubes))]
    while todo:
        c = todo.pop()
        if c in seen:
            continue
        seen.add(c)
        todo.extend(n for n in (add_cube(c, s) for s in STEPS)
                    if n in cubes)
    return seen == cubes


def add_cube(a: Cube, b: Cube) -> Cube:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def arms(rng: random.Random, count: int,
         segments: Optional[Tuple[int, int]] = None) -> Tuple[Cube, ...]:
    """A Shepard-Metzler figure: *count* cubes face to face in straight
    arms, each arm turning a right angle from the last and no arm
    running back along the one before. Always chiral."""
    if segments is None:
        # At least three arms: two lie in a plane, and a flat figure is
        # its own mirror image.
        segments = (2, max(2, (count - 1) // 3))
    for _try in range(500):
        cubes = [(0, 0, 0)]
        last_axis = None
        while len(cubes) < count:
            axis = rng.choice([a for a in range(3) if a != last_axis])
            sign = rng.choice((1, -1))
            step = [0, 0, 0]
            step[axis] = sign
            run = rng.randint(*segments)
            ok = True
            for _k in range(run):
                if len(cubes) >= count:
                    break
                nxt = add_cube(cubes[-1], tuple(step))
                if nxt in cubes:
                    ok = False
                    break
                cubes.append(nxt)
            if not ok:
                break
            last_axis = axis
        if len(cubes) == count and chiral(cubes) and \
                len({c[0] for c in cubes}) > 1 and \
                len({c[1] for c in cubes}) > 1 and \
                len({c[2] for c in cubes}) > 1:
            return tuple(cubes)
    raise RuntimeError('no chiral figure found')


def nudged(rng: random.Random, cubes: Sequence[Cube],
           avoid: Sequence[Sequence[Cube]] = ()) -> Tuple[Cube, ...]:
    """The figure with one end cube moved to another face of its
    neighbour: nearly the same shape, and not the same, nor its mirror,
    nor any shape in *avoid*."""
    cubes = list(cubes)
    keys = {shape_key(cubes), shape_key(mirrored(cubes))}
    keys.update(shape_key(a) for a in avoid)
    ends = [0, len(cubes) - 1]
    rng.shuffle(ends)
    for end in ends:
        body = cubes[:end] + cubes[end + 1:]
        anchor = cubes[1] if end == 0 else cubes[-2]
        options = [add_cube(anchor, s) for s in STEPS]
        rng.shuffle(options)
        for spot in options:
            if spot in body or spot == cubes[end]:
                continue
            new = body + [spot]
            if end == 0:
                new = [spot] + body
            if connected(new) and chiral(new) and \
                    shape_key(new) not in keys:
                return tuple(new)
    return tuple(cubes)


def centred(cubes: Sequence[Cube]) -> List[Vec]:
    n = float(len(cubes))
    mid = tuple(sum(c[i] for c in cubes) / n for i in range(3))
    return [sub(tuple(float(v) for v in c), mid) for c in cubes]


def radius(cubes: Sequence[Cube]) -> float:
    """How far the farthest cube corner sits from the figure's middle."""
    return max(length(c) for c in centred(cubes)) + math.sqrt(3) / 2


# --- faces ---------------------------------------------------------------

class Face(NamedTuple):
    points: Tuple[Vec, ...]
    colour: Colour
    normal: Vec
    #: Sorted by: the middle of the solid the face belongs to.
    anchor: Vec
    #: What a click on it means (a box's index, a mark's owner).
    tag: object = None
    #: Drawn after a face on the same anchor with a smaller bias.
    bias: float = 0.0
    #: Lit by the light (False: flat colour, for marks and shadows).
    lit: bool = True


def _square(centre: Vec, n: Vec, r: Vec, u: Vec, half: float):
    return tuple(add(centre, add(mul(r, half * a), mul(u, half * b)))
                 for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)))


def frame_of(n: Vec) -> Tuple[Vec, Vec]:
    """Two directions along a face with outward normal *n*, r x u = n."""
    helper = (0.0, 1.0, 0.0) if abs(n[1]) < 0.9 else (0.0, 0.0, 1.0)
    r = unit(cross(helper, n))
    u = cross(n, r)
    return r, u


def cube_faces(cubes: Sequence[Cube], turn: Mat = IDENTITY,
               colour: Colour = (200, 170, 120), size: float = 1.0,
               offset: Vec = (0.0, 0.0, 0.0)) -> List[Face]:
    """The outside faces of a figure of cubes, centred, turned, moved."""
    have = set(cubes)
    out = []
    for cube, mid in zip(cubes, centred(cubes)):
        anchor = add(apply(turn, mul(mid, size)), offset)
        for step in STEPS:
            if add_cube(cube, step) in have:
                continue
            n = tuple(float(v) for v in step)
            r, u = frame_of(n)
            centre = add(mid, mul(n, 0.5))
            pts = _square(centre, n, r, u, 0.5)
            out.append(Face(
                tuple(add(apply(turn, mul(p, size)), offset) for p in pts),
                colour, apply(turn, n), anchor))
    return out


def box_faces(centre: Vec, size: Vec, colour: Colour, tag: object = None,
              yaw: float = 0.0) -> List[Face]:
    """An upright box, turned *yaw* radians about the vertical."""
    turn = rotation((0.0, 1.0, 0.0), yaw)
    out = []
    for step in STEPS:
        n = tuple(float(v) for v in step)
        r, u = frame_of(n)
        pts = []
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            local = add(mul(n, 0.5), add(mul(r, 0.5 * a), mul(u, 0.5 * b)))
            local = (local[0] * size[0], local[1] * size[1],
                     local[2] * size[2])
            pts.append(add(centre, apply(turn, local)))
        out.append(Face(tuple(pts), colour, apply(turn, n), centre, tag))
    return out


def prism_faces(centre: Vec, radius: float, height: float, sides: int,
                colour: Colour, tag: object = None, top: float = 1.0,
                yaw: float = 0.0) -> List[Face]:
    """An upright prism of *sides* sides standing on its base; *top* is
    the top's size against the base's (0 for a pyramid or cone)."""
    out = []
    y0, y1 = centre[1] - height / 2, centre[1] + height / 2
    ring = [(math.cos(yaw + 2 * math.pi * k / sides),
             math.sin(yaw + 2 * math.pi * k / sides)) for k in range(sides)]
    base = [(centre[0] + radius * c, y0, centre[2] + radius * s)
            for c, s in ring]
    tip = [(centre[0] + radius * top * c, y1, centre[2] + radius * top * s)
           for c, s in ring]
    for k in range(sides):
        j = (k + 1) % sides
        if top > 0:
            pts = (base[k], tip[k], tip[j], base[j])
        else:
            pts = (base[k], (centre[0], y1, centre[2]), base[j])
        n = unit(cross(sub(pts[1], pts[0]), sub(pts[-1], pts[0])))
        if dot(n, sub(pts[0], centre)) < 0:
            n = mul(n, -1)
        out.append(Face(pts, colour, n, centre, tag))
    out.append(Face(tuple(reversed(base)), colour, (0.0, -1.0, 0.0),
                    centre, tag))
    if top > 0:
        out.append(Face(tuple(tip), colour, (0.0, 1.0, 0.0), centre, tag))
    return out


# --- the camera ----------------------------------------------------------

class Camera:
    """A viewpoint: *eye* looking at *target*; perspective with *focal*
    (page units per unit of sideways distance at depth one), or
    orthographic when *focal* is None."""

    def __init__(self, eye: Vec, target: Vec, focal: Optional[float] = None,
                 up: Vec = (0.0, 1.0, 0.0)) -> None:
        self.eye = eye
        self.forward = unit(sub(target, eye))
        self.right = unit(cross(self.forward, up))
        self.up = cross(self.right, self.forward)
        self.focal = focal

    def view(self, p: Vec) -> Vec:
        d = sub(p, self.eye)
        return (dot(d, self.right), dot(d, self.up), dot(d, self.forward))

    def project(self, p: Vec) -> Optional[Tuple[float, float]]:
        x, y, z = self.view(p)
        if self.focal is None:
            return (x, y)
        if z <= 0.05:
            return None
        return (self.focal * x / z, self.focal * y / z)

    def depth(self, p: Vec) -> float:
        if self.focal is None:
            return dot(sub(p, self.eye), self.forward)
        return length(sub(p, self.eye))

    def faces_us(self, face: Face) -> bool:
        if self.focal is None:
            return dot(face.normal, self.forward) < -1e-9
        return dot(face.normal, sub(self.eye, face.points[0])) > 1e-9


#: The light, from above, front and left of the usual viewpoints.
LIGHT: Vec = unit((-0.45, 0.85, 0.55))


def shade(colour: Colour, normal: Vec, light: Vec = LIGHT) -> Colour:
    k = 0.48 + 0.52 * max(0.0, dot(normal, light))
    return tuple(int(min(255, c * k)) for c in colour)


class Painted(NamedTuple):
    points: Tuple[Tuple[float, float], ...]
    colour: Colour
    depth: float
    tag: object
    #: Drawn with a dark rim (False for marks laid on a face).
    rim: bool = True


def render(faces: Iterable[Face], camera: Camera,
           light: Vec = LIGHT) -> List[Painted]:
    """Faces turned toward the camera as page polygons, farthest first."""
    out = []
    for face in faces:
        if not camera.faces_us(face):
            continue
        pts = [camera.project(p) for p in face.points]
        if any(p is None for p in pts):
            continue
        colour = shade(face.colour, face.normal, light) if face.lit \
            else face.colour
        key = camera.depth(face.anchor) - face.bias
        out.append((key, Painted(tuple(pts), colour,
                                 camera.depth(face.anchor), face.tag,
                                 face.lit)))
    out.sort(key=lambda pair: -pair[0])
    return [p for _k, p in out]


def bounds(painted: Sequence[Painted]) -> Tuple[float, float, float, float]:
    xs = [x for p in painted for x, _y in p.points]
    ys = [y for p in painted for _x, y in p.points]
    if not xs:
        return (0.0, 0.0, 1.0, 1.0)
    return (min(xs), min(ys), max(xs), max(ys))


def clip(points: Sequence[Tuple[float, float]], x0: float, y0: float,
         x1: float, y1: float) -> List[Tuple[float, float]]:
    """A polygon cut to a rectangle (Sutherland-Hodgman)."""
    def cut(pts, inside, meet):
        out = []
        for k in range(len(pts)):
            a, b = pts[k - 1], pts[k]
            if inside(b):
                if not inside(a):
                    out.append(meet(a, b))
                out.append(b)
            elif inside(a):
                out.append(meet(a, b))
        return out

    def at_x(x):
        return lambda a, b: (x, a[1] + (b[1] - a[1]) * (x - a[0])
                             / ((b[0] - a[0]) or 1e-12))

    def at_y(y):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (y - a[1])
                             / ((b[1] - a[1]) or 1e-12), y)

    pts = list(points)
    for inside, meet in ((lambda p: p[0] >= x0, at_x(x0)),
                         (lambda p: p[0] <= x1, at_x(x1)),
                         (lambda p: p[1] >= y0, at_y(y0)),
                         (lambda p: p[1] <= y1, at_y(y1))):
        if not pts:
            break
        pts = cut(pts, inside, meet)
    return pts


def clipped(painted: Sequence[Painted], x0: float, y0: float, x1: float,
            y1: float) -> List[Painted]:
    out = []
    for p in painted:
        pts = clip(p.points, x0, y0, x1, y1)
        if len(pts) >= 3:
            out.append(p._replace(points=tuple(pts)))
    return out
