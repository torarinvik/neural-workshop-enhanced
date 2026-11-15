# -*- coding: utf-8 -*-
"""Dr Shape: a 3D turtle draws a shape and sings it; find it again.

A turtle flies through space laying down a line, and every stroke it
draws is also a note: the stroke's height is the note's pitch, its
left-right place is where the note sits between the two ears -- and the
note travels from one ear toward the other as the stroke does -- its
nearness is how loud and bright it rings, and its length is how long it
lasts. Each colour a stroke is drawn in is an instrument. So every shape
has a sound, and the sound is the shape heard.

What has to be understood grows rung by rung: a shape however it is
turned; a shape and its mirror; which colour goes where; how big a thing
really is, when it might be near or far; and where several things stand
in a place seen from somewhere else -- or only heard.

A trial is one of six kinds:

* **see** -- watch (and hear) the turtle draw; pick the same shape from
  look-alikes on cards;
* **hear** -- the shape is only heard; pick what it sounded like;
* **sing** -- the turtle draws in silence; the cards are sounds, played
  in turn; pick the sound that is the shape;
* **echo** -- the shape is only heard; the cards are sounds again, played
  on other instruments and in another key; pick the same tune;
* **scene** -- three things stand on a platform by a beacon, each singing
  from where it stands; the cards show the platform from somewhere else;
  pick the one where everything is where it was;
* **hear_scene** -- the same, but the platform is only heard.

Each trial deals its own instruments from a bank of synthesised ones --
bells, glass, wood, reeds, brass, plucks, pads, growls, chirps, metal and
stranger things -- and higher up bends them with vibrato, tremolo,
drive, folding, ring modulation, glides and echoes. A far thing sounds
quieter, duller, a little later and with more of the room in it.

The ladder:

* rungs 1-2: flat polygons and stars, the shape stays in view;
* rungs 3-4: from memory; spirals; some trials are echoes, same
  instrument, same key;
* rungs 5-7: paths and curves through space -- knots, loops, helices --
  turned every which way; some trials ask which sound is the shape;
* rungs 8-10: mirror images, one stroke changed, prisms; two colours,
  and look-alikes with the colours moved; echoes move key;
* rungs 11-13: solids, pyramids, knots and coils; three colours; echoes
  change instruments;
* rungs 14-16: shapes only heard, and sounds to pick;
* rungs 17-19: the cards are places: each shape stands somewhere on a
  floor, near or far, and some look-alikes are the same shape bigger or
  smaller, placed so they look the same size;
* rungs 20-22: scenes, seen from another side;
* from rung 23: everything, scenes only heard, each card seen from its
  own side, and sensory overload -- branching shapes, six cards, noise,
  flicker, jitter, decoy sounds and instruments that change under every
  stroke, worse every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import array
import math
import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from .i18n import _

MOST = 6
PORTS = MOST
EVENTS = tuple(range(MOST))
RATE = 22050                 # audio samples a second, stereo
NOTE_UNIT = 0.5              # seconds of sound per unit of stroke length
LEAD_IN = 0.4
HOLD = 0.9                   # a still moment after the turtle stops
SCALE = (0, 2, 4, 7, 9)      # pentatonic: any two notes sit well together
NYQUIST_SAFE = RATE * 0.42
MODES = ('see', 'hear', 'sing', 'echo', 'scene', 'hear_scene')
#: Modes whose candidates are sounds rather than pictures.
SOUND_CARDS = ('sing', 'echo')
SCENES = ('scene', 'hear_scene')
TINTS = 3                    # most colours a shape is drawn in
SPEED_OF_SOUND = 343.0
# The floor and the platform, in shape radii.
FLOOR_EYE = 1.1              # how high the eye is above the floor
SHOW_DEPTH = 3.4             # how far off the shape stands while drawn
PLATFORM = 2.7               # the platform's radius
ORBIT = 7.0                  # the camera's distance from the platform
ORBIT_RISE = 0.5             # radians the camera looks down
OBJECT = 0.78               # the size of a thing on the platform

Vec = Tuple[float, float, float]
Segment = Tuple[Vec, Vec]
Matrix = Tuple[Vec, Vec, Vec]


class Grade(NamedTuple):
    rung: int
    families: Tuple[str, ...]
    candidates: int
    keep: bool           # the shape stays in view while choosing
    turn: str            # 'none', 'plane' or 'space'
    mirror: bool         # mirror images among the look-alikes
    near: bool           # look-alikes with one stroke changed
    colours: int         # how many colours a shape may be drawn in
    modes: Tuple[Tuple[str, float], ...]   # trial kinds and their odds
    echo_key: bool       # echoes move key
    echo_voice: bool     # echoes change instrument
    floor: bool          # picture cards stand on a floor, near or far
    each_side: bool      # every scene card seen from its own side
    tumble: bool         # candidates keep turning
    chorus: bool         # candidates sing their own shapes
    overload: float      # 0..1: noise, flicker, jitter, decoy sounds
    wild: float          # 0..1: how strange the instruments get
    instruments: Tuple[str, ...]
    choose: float        # seconds to choose
    tempo: float         # how fast the turtle draws


GENTLE = ('sine', 'flute', 'organ', 'glass')
MORE = GENTLE + ('clarinet', 'pluck', 'bell', 'wood', 'pad')
MANY = MORE + ('brass', 'metal', 'chirp', 'growl', 'square', 'sub')
ALL = MANY + ('alien', 'zap')


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    over = 0.0 if r < 23 else min(1.0, 0.25 + 0.075 * (r - 23))
    if r < 3:
        fam = ('polygon', 'star')
    elif r < 5:
        fam = ('polygon', 'star', 'spiral')
    elif r < 8:
        fam = ('space', 'curve')
    elif r < 11:
        fam = ('space', 'curve', 'prism')
    elif r < 23:
        fam = ('coil', 'space', 'curve', 'prism', 'pyramid', 'solid')
    else:
        fam = ('coil', 'space', 'curve', 'prism', 'pyramid', 'solid',
               'branch')
    if r < 3:
        modes = (('see', 1.0),)
    elif r < 5:
        modes = (('see', 0.7), ('echo', 0.3))
    elif r < 8:
        modes = (('see', 0.7), ('sing', 0.3))
    elif r < 14:
        modes = (('see', 0.6), ('sing', 0.2), ('echo', 0.2))
    elif r < 17:
        modes = (('hear', 0.5), ('sing', 0.25), ('echo', 0.25))
    elif r < 20:
        modes = (('see', 0.5), ('hear', 0.15), ('sing', 0.15),
                 ('echo', 0.2))
    elif r < 23:
        modes = (('scene', 0.5), ('see', 0.2), ('sing', 0.15),
                 ('echo', 0.15))
    else:
        modes = (('scene', 0.2), ('hear_scene', 0.15), ('see', 0.2),
                 ('hear', 0.15), ('sing', 0.15), ('echo', 0.15))
    return Grade(
        rung=r,
        families=fam,
        candidates=(3 if r < 3 else 4 if r < 11 else 5 if r < 23 else 6),
        keep=r < 3,
        turn='none' if r < 3 else 'plane' if r < 5 else 'space',
        mirror=8 <= r < 14 or r >= 17,
        near=8 <= r < 14 or r >= 17,
        colours=1 if r < 8 else 2 if r < 11 else 3,
        modes=modes,
        echo_key=r >= 8,
        echo_voice=r >= 11,
        floor=r >= 17,
        each_side=r >= 23,
        tumble=17 <= r < 20 or r >= 23,
        chorus=17 <= r < 20 or r >= 23,
        overload=over,
        wild=(0.0 if r < 5 else 0.2 if r < 11 else 0.45 if r < 23
              else 0.6 + 0.4 * over),
        instruments=(GENTLE if r < 5 else MORE if r < 11 else MANY if r < 23
                     else ALL),
        choose=(14.0 if r < 11 else 12.0 if r < 23
                else max(8.0, 11.0 - 0.15 * (r - 23))),
        tempo=1.0 if r < 23 else 1.0 + 0.6 * over)


# --- vectors ----------------------------------------------------------------

def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _turn(a: Vec, b: Vec, deg: float) -> Tuple[Vec, Vec]:
    """Rotate the pair of axes (a, b) by *deg* in their own plane."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (_add(_mul(a, c), _mul(b, s)), _sub(_mul(b, c), _mul(a, s)))


def apply(m: Matrix, v: Vec) -> Vec:
    return (_dot(m[0], v), _dot(m[1], v), _dot(m[2], v))


def matmul(a: Matrix, b: Matrix) -> Matrix:
    cols = list(zip(*b))
    return tuple(tuple(_dot(row, col) for col in cols) for row in a)


IDENTITY: Matrix = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def axis_turn(axis: Vec, angle: float) -> Matrix:
    x, y, z = axis
    n = math.sqrt(x * x + y * y + z * z) or 1.0
    x, y, z = x / n, y / n, z / n
    c, s = math.cos(angle), math.sin(angle)
    t = 1 - c
    return ((t * x * x + c, t * x * y - s * z, t * x * z + s * y),
            (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
            (t * x * z - s * y, t * y * z + s * x, t * z * z + c))


def random_turn(draw: random.Random) -> Matrix:
    """A uniformly random rotation (from a random unit quaternion)."""
    u1, u2, u3 = draw.random(), draw.random(), draw.random()
    a, b = math.sqrt(1 - u1), math.sqrt(u1)
    w, x = a * math.sin(2 * math.pi * u2), a * math.cos(2 * math.pi * u2)
    y, z = b * math.sin(2 * math.pi * u3), b * math.cos(2 * math.pi * u3)
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))


# --- the turtle -------------------------------------------------------------

Op = Tuple  # ('F', length) ('Y', deg) ('P', deg) ('R', deg) ('[',) (']',)


def trace(program: Sequence[Op]) -> List[Segment]:
    """Fly the turtle; the strokes it lays down, in the order drawn,
    centred and scaled so the farthest point is one unit out."""
    pos: Vec = (0.0, 0.0, 0.0)
    head: Vec = (1.0, 0.0, 0.0)
    left: Vec = (0.0, 1.0, 0.0)
    up: Vec = (0.0, 0.0, 1.0)
    stack = []
    segs: List[Segment] = []
    for op in program:
        kind = op[0]
        if kind == 'F':
            nxt = _add(pos, _mul(head, op[1]))
            segs.append((pos, nxt))
            pos = nxt
        elif kind == 'Y':
            head, left = _turn(head, left, op[1])
        elif kind == 'P':
            head, up = _turn(head, up, op[1])
        elif kind == 'R':
            left, up = _turn(left, up, op[1])
        elif kind == '[':
            stack.append((pos, head, left, up))
        elif kind == ']':
            pos, head, left, up = stack.pop()
    return normalise(segs)


def normalise(segs: List[Segment]) -> List[Segment]:
    pts = points(segs)
    if not pts:
        return segs
    c = _mul((sum(p[0] for p in pts), sum(p[1] for p in pts),
              sum(p[2] for p in pts)), 1.0 / len(pts))
    far = max(math.sqrt(_dot(_sub(p, c), _sub(p, c))) for p in pts) or 1.0
    return [(_mul(_sub(a, c), 1 / far), _mul(_sub(b, c), 1 / far))
            for a, b in segs]


def points(segs: Sequence[Segment]) -> List[Vec]:
    """Every distinct point the strokes touch, in drawing order."""
    out: List[Vec] = []
    for seg in segs:
        for p in seg:
            if not any(abs(p[0] - q[0]) + abs(p[1] - q[1]) + abs(p[2] - q[2])
                       < 1e-6 for q in out):
                out.append(p)
    return out


def signature(segs: Sequence[Segment]) -> List[float]:
    """Sorted distances between all points: the same for a shape however
    it is turned or mirrored."""
    pts = points(segs)
    out = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = _sub(pts[i], pts[j])
            out.append(math.sqrt(_dot(d, d)))
    return sorted(out)


def unlike(a: Sequence[Segment], b: Sequence[Segment],
           margin: float = 0.12) -> bool:
    """Whether two shapes differ by more than *margin* however they are
    turned (a mirror image does not count as different here)."""
    if len(a) != len(b):
        return True
    sa, sb = signature(a), signature(b)
    if len(sa) != len(sb):
        return True
    return max((abs(x - y) for x, y in zip(sa, sb)), default=0.0) > margin


def handedness(segs: Sequence[Segment]) -> float:
    """Signed twist of the path: flips sign in a mirror, zero when flat."""
    total = 0.0
    dirs = [_sub(b, a) for a, b in segs]
    for k in range(len(dirs) - 2):
        total += _dot(_cross(dirs[k], dirs[k + 1]), dirs[k + 2])
    return total


def mirrored(segs: Sequence[Segment]) -> List[Segment]:
    return [((-a[0], a[1], a[2]), (-b[0], b[1], b[2])) for a, b in segs]


def turned(m: Matrix, segs: Sequence[Segment]) -> List[Segment]:
    return [(apply(m, a), apply(m, b)) for a, b in segs]


# --- shape families ---------------------------------------------------------

def make_program(family: str, draw: random.Random) -> List[Op]:
    if family == 'polygon':
        n = draw.choice((3, 4, 5, 6, 8))
        return [op for _k in range(n) for op in (('F', 1.0),
                                                   ('Y', 360.0 / n))]
    if family == 'star':
        n, k = draw.choice(((5, 2), (7, 2), (7, 3), (8, 3), (9, 2), (9, 4)))
        return [op for _i in range(n) for op in (('F', 1.0),
                                                   ('Y', 360.0 * k / n))]
    if family == 'spiral':
        n = draw.randint(6, 10)
        a = draw.choice((60, 72, 90, 120))
        g = draw.uniform(1.12, 1.3)
        return [op for i in range(n) for op in (('F', g ** i), ('Y', a))]
    if family == 'space':
        n = draw.randint(4, 7)
        out = []
        for _i in range(n):
            out += [('Y', draw.choice((-120, -90, -60, 60, 90, 120))),
                    ('P', draw.choice((-90, -60, -30, 0, 30, 60, 90))),
                    ('F', draw.choice((1.0, 1.5, 2.0)))]
        return out
    if family == 'coil':
        motif = []
        for _i in range(draw.randint(2, 3)):
            motif += [('Y', draw.choice((-90, -60, 60, 90, 120))),
                      ('P', draw.choice((-45, -30, 30, 45))),
                      ('F', draw.choice((1.0, 1.5)))]
        reps = draw.randint(3, 5)
        roll = draw.choice((60, 72, 90, 120))
        return [op for _k in range(reps) for op in motif + [('R', roll)]]
    if family == 'branch':
        a = draw.choice((25, 30, 40))
        b = draw.choice((20, 35, 45))
        depth = draw.choice((2, 3))
        shrink = draw.uniform(0.55, 0.7)

        def grow(level: int, size: float) -> List[Op]:
            if level == 0:
                return [('F', size)]
            twist = draw.choice((60, 90, 120))
            return [('F', size), ('[', ), ('Y', a), ('P', b / 2),
                    *grow(level - 1, size * shrink), (']', ), ('[', ),
                    ('R', twist), ('Y', -b), *grow(level - 1, size * shrink),
                    (']', )]
        return [('P', 90)] + grow(depth, 1.0)
    raise ValueError(family)


def bend(program: List[Op], draw: random.Random) -> List[Op]:
    """The same program with one stroke changed."""
    out = list(program)
    spots = [i for i, op in enumerate(out) if op[0] in ('Y', 'P', 'F')]
    i = draw.choice(spots)
    kind, value = out[i]
    if kind == 'F':
        out[i] = ('F', value * draw.choice((0.5, 1.6, 2.0)))
    else:
        out[i] = (kind, value + draw.choice((-60, -45, 45, 60)))
    return out

# --- forms: strokes, faces and colours ----------------------------------------

Face = Tuple[Tuple[Vec, ...], int]


class Form(NamedTuple):
    """A shape as drawn: strokes in drawing order, each in a colour
    (0..TINTS-1), and the flat faces between them, each in a colour."""
    segs: List[Segment]
    tints: List[int]
    faces: List[Face]


def form_of(segs: Sequence[Segment], tints: Optional[Sequence[int]] = None,
            faces: Sequence[Face] = ()) -> Form:
    return Form(list(segs), list(tints) if tints is not None
                else [0] * len(segs), list(faces))


def map_form(f: Form, fn) -> Form:
    return Form([(fn(a), fn(b)) for a, b in f.segs], list(f.tints),
                [(tuple(fn(v) for v in poly), t) for poly, t in f.faces])


def normalise_form(f: Form) -> Form:
    pts = points(f.segs)
    c = _mul((sum(p[0] for p in pts), sum(p[1] for p in pts),
              sum(p[2] for p in pts)), 1.0 / len(pts))
    far = max(math.sqrt(_dot(_sub(p, c), _sub(p, c))) for p in pts) or 1.0
    return map_form(f, lambda p: _mul(_sub(p, c), 1.0 / far))


def turned_form(m: Matrix, f: Form) -> Form:
    return map_form(f, lambda p: apply(m, p))


def mirrored_form(f: Form) -> Form:
    return map_form(f, lambda p: (-p[0], p[1], p[2]))


def _ring(n: int, r: float, y: float, twist: float = 0.0) -> List[Vec]:
    return [(r * math.cos(2 * math.pi * k / n + twist), y,
             r * math.sin(2 * math.pi * k / n + twist)) for k in range(n)]


def _loop(pts: Sequence[Vec]) -> List[Segment]:
    return [(pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]


def draw_params(family: str, draw: random.Random) -> Dict:
    if family in ('polygon', 'star', 'spiral', 'space', 'coil', 'branch'):
        return {'program': make_program(family, draw)}
    if family == 'curve':
        kind = draw.choice(('knot', 'lissa', 'helix'))
        if kind == 'knot':
            p, q = draw.choice(((2, 3), (3, 2), (2, 5), (3, 4)))
            return {'kind': kind, 'a': p, 'b': q, 'c': 0,
                    'n': draw.randint(12, 15)}
        if kind == 'lissa':
            a, b, c = draw.sample((1, 2, 3, 4), 3)
            return {'kind': kind, 'a': a, 'b': b, 'c': c,
                    'n': draw.randint(12, 15)}
        return {'kind': kind, 'a': draw.choice((1.5, 2.0, 2.5)),
                'b': draw.choice((1, -1)), 'c': 0, 'n': draw.randint(11, 14)}
    if family == 'prism':
        return {'n': draw.randint(3, 6), 'twist': draw.choice((0, 15, 30)),
                'taper': draw.choice((1.0, 1.0, 0.55)),
                'height': draw.choice((0.6, 1.0, 1.5))}
    if family == 'pyramid':
        return {'n': draw.randint(3, 6),
                'lean': draw.choice((0.0, 0.5, 0.9)),
                'height': draw.choice((1.0, 1.6))}
    if family == 'solid':
        return {'kind': draw.choice(('tetra', 'cube', 'octa')),
                'stretch': (draw.choice((0.6, 1.0, 1.6)),
                            draw.choice((0.6, 1.0, 1.6)),
                            draw.choice((0.6, 1.0)))}
    raise ValueError(family)


def nudge(family: str, params: Dict, draw: random.Random) -> Dict:
    """The same kind of shape with one thing about it changed."""
    out = dict(params)
    if 'program' in params:
        out['program'] = bend(params['program'], draw)
    elif family == 'curve':
        if params['kind'] == 'knot':
            pairs = [pq for pq in ((2, 3), (3, 2), (2, 5), (3, 4))
                     if pq != (params['a'], params['b'])]
            out['a'], out['b'] = draw.choice(pairs)
        elif params['kind'] == 'lissa':
            key = draw.choice('abc')
            free = [v for v in (1, 2, 3, 4, 5)
                    if v not in (params['a'], params['b'], params['c'])]
            out[key] = draw.choice(free)
        else:
            out['a'] = params['a'] + draw.choice((-0.5, 0.5, 1.0))
    elif family == 'prism':
        key = draw.choice(('n', 'twist', 'taper', 'height'))
        if key == 'n':
            out['n'] = params['n'] + (1 if params['n'] < 6 else -1)
        elif key == 'twist':
            out['twist'] = 30 if params['twist'] != 30 else 0
        elif key == 'taper':
            out['taper'] = 0.55 if params['taper'] == 1.0 else 1.0
        else:
            out['height'] = 0.6 if params['height'] != 0.6 else 1.5
    elif family == 'pyramid':
        if draw.random() < 0.5:
            out['n'] = params['n'] + (1 if params['n'] < 6 else -1)
        else:
            out['lean'] = 0.9 if params['lean'] < 0.5 else 0.0
    elif family == 'solid':
        sx, sy, sz = params['stretch']
        out['stretch'] = (sy, sx * 1.6 if sx < 1.5 else 0.6, sz)
    return out


def build(family: str, params: Dict) -> Form:
    """The shape a family's parameters describe, uncoloured."""
    if 'program' in params:
        return form_of(trace(params['program']))
    if family == 'curve':
        n, kind = params['n'], params['kind']
        pts = []
        for k in range(n + (0 if kind != 'helix' else 1)):
            t = 2 * math.pi * k / n
            if kind == 'knot':
                p, q = params['a'], params['b']
                r = math.cos(q * t) + 2.2
                pts.append((r * math.cos(p * t), r * math.sin(p * t),
                            -math.sin(q * t) * 1.3))
            elif kind == 'lissa':
                pts.append((math.sin(params['a'] * t + 0.5 * math.pi),
                            math.sin(params['b'] * t),
                            math.sin(params['c'] * t + 0.25 * math.pi)))
            else:
                turns = params['a'] * params['b']
                s = k / n
                pts.append((math.cos(2 * math.pi * turns * s), 2.4 * s - 1.2,
                            math.sin(2 * math.pi * turns * s)))
        segs = _loop(pts) if kind != 'helix' else \
            [(pts[k], pts[k + 1]) for k in range(len(pts) - 1)]
        return normalise_form(form_of(segs))
    if family == 'prism':
        n, h = params['n'], params['height'] / 2
        base = _ring(n, 1.0, -h)
        top = _ring(n, params['taper'], h, math.radians(params['twist']))
        segs = _loop(base) + [(base[k], top[k]) for k in range(n)] + \
            _loop(top)
        faces = [(tuple(base), 0), (tuple(top), 0)] + \
            [((base[k], base[(k + 1) % n], top[(k + 1) % n], top[k]), 0)
             for k in range(n)]
        return normalise_form(form_of(segs, None, faces))
    if family == 'pyramid':
        n = params['n']
        base = _ring(n, 1.0, -0.6)
        apex = (params['lean'], params['height'] - 0.6, 0.0)
        segs = _loop(base) + [(base[k], apex) for k in range(n)]
        faces = [(tuple(base), 0)] + [((base[k], base[(k + 1) % n], apex), 0)
                                      for k in range(n)]
        return normalise_form(form_of(segs, None, faces))
    if family == 'solid':
        sx, sy, sz = params['stretch']
        kind = params['kind']
        if kind == 'cube':
            v = [(x, y, z) for y in (-1, 1) for x, z in ((-1, -1), (1, -1),
                                                         (1, 1), (-1, 1))]
            bottom, top = v[:4], v[4:]
            segs = _loop(bottom) + [(bottom[k], top[k]) for k in range(4)] + \
                _loop(top)
            faces = [(tuple(bottom), 0), (tuple(top), 0)] + \
                [((bottom[k], bottom[(k + 1) % 4], top[(k + 1) % 4],
                   top[k]), 0) for k in range(4)]
        elif kind == 'octa':
            eq = [(1, 0, 0), (0, 0, 1), (-1, 0, 0), (0, 0, -1)]
            up, down = (0, 1.2, 0), (0, -1.2, 0)
            segs = _loop(eq) + [(e, up) for e in eq] + [(e, down) for e in eq]
            faces = [((eq[k], eq[(k + 1) % 4], tip), 0) for tip in (up, down)
                     for k in range(4)]
        else:
            base = _ring(3, 1.0, -0.5)
            tip = (0.0, 1.1, 0.0)
            segs = _loop(base) + [(b, tip) for b in base]
            faces = [(tuple(base), 0)] + [((base[k], base[(k + 1) % 3], tip), 0)
                                          for k in range(3)]
        f = form_of(segs, None, faces)
        f = map_form(f, lambda p: (p[0] * sx, p[1] * sy, p[2] * sz))
        return normalise_form(f)
    raise ValueError(family)


def colour(f: Form, k: int, draw: random.Random,
           style: Optional[str] = None) -> Form:
    """*f* drawn in *k* colours: in runs, in turn, or at random (every
    colour used)."""
    n = len(f.segs)
    if k <= 1 or n < 2:
        return Form(list(f.segs), [0] * n, [(p, 0) for p, _t in f.faces])
    k = min(k, n)
    style = style or draw.choice(('runs', 'cycle', 'random'))
    if style == 'runs':
        cuts = sorted(draw.sample(range(1, n), k - 1))
        tints, c = [], 0
        for i in range(n):
            if c < len(cuts) and i >= cuts[c]:
                c += 1
            tints.append(c)
    elif style == 'cycle':
        tints = [i % k for i in range(n)]
    else:
        tints = list(range(k)) + [draw.randrange(k) for _i in range(n - k)]
        draw.shuffle(tints)
    faces = [(p, draw.randrange(k)) for p, _t in f.faces]
    return Form(list(f.segs), tints, faces)


def recoloured(f: Form, draw: random.Random) -> Form:
    """The same strokes with the colours moved about."""
    used = sorted(set(f.tints))
    if len(used) < 2:
        return f
    if draw.random() < 0.5:
        a, b = draw.sample(used, 2)
        swap = {a: b, b: a}
        return Form(list(f.segs), [swap.get(t, t) for t in f.tints],
                    [(p, swap.get(t, t)) for p, t in f.faces])
    return colour(f, len(used), draw)


def _items(f: Form) -> List[Tuple[int, Vec]]:
    out = [(t, _mul(_add(a, b), 0.5)) for (a, b), t in zip(f.segs, f.tints)]
    for poly, t in f.faces:
        out.append((10 + t, _mul(tuple(map(sum, zip(*poly))), 1.0 / len(poly))))
    return out


def same_colouring(a: Form, b: Form, tol: float = 0.02) -> bool:
    """Whether two forms of the same geometry could be the same coloured
    thing however turned: their colour-tagged distances agree."""
    def groups(f: Form) -> Dict[Tuple[int, int], List[float]]:
        out: Dict[Tuple[int, int], List[float]] = {}
        items = _items(f)
        for i in range(len(items)):
            out.setdefault((items[i][0], -1), []).append(0.0)
            for j in range(i + 1, len(items)):
                d = _sub(items[i][1], items[j][1])
                key = (min(items[i][0], items[j][0]),
                       max(items[i][0], items[j][0]))
                out.setdefault(key, []).append(math.sqrt(_dot(d, d)))
        return out
    ga, gb = groups(a), groups(b)
    if set(ga) != set(gb):
        return False
    for key, xs in ga.items():
        ys = gb[key]
        if len(xs) != len(ys):
            return False
        if any(abs(x - y) > tol for x, y in zip(sorted(xs), sorted(ys))):
            return False
    return True


def distinct(a: Form, b: Form, margin: float = 0.12,
             size_a: float = 1.0, size_b: float = 1.0) -> bool:
    """Whether *b* is surely not *a*: other geometry by more than
    *margin*, its mirror, other colours, or another size. Shapes too
    close to tell apart but not the same count as not distinct."""
    if abs(math.log(size_a / size_b)) > 0.3:
        return True
    if len(a.segs) != len(b.segs):
        return True
    sa, sb = signature(a.segs), signature(b.segs)
    if len(sa) != len(sb):
        return True
    gap = max((abs(x - y) for x, y in zip(sa, sb)), default=0.0)
    if gap > margin:
        return True
    if gap > 0.02:
        return False
    ha, hb = handedness(a.segs), handedness(b.segs)
    if abs(ha) > 0.08 and (ha > 0) != (hb > 0):
        return True
    return not same_colouring(a, b)


# --- scenes -----------------------------------------------------------------

class Thing(NamedTuple):
    """Something on the platform: a form, turned once and for all."""
    form: Form
    turn: Matrix
    tint: int


Layout = Tuple[Tuple[int, float, float], ...]   # (thing, x, z)


def rest(f: Form, turn: Matrix, size: float) -> Tuple[Form, float]:
    """*f* turned and scaled, and how far to lift it so it stands on
    the ground (its lowest point at height zero)."""
    g = map_form(f, lambda p: _mul(apply(turn, p), size))
    low = min(min(a[1], b[1]) for a, b in g.segs)
    return g, -low


def _spots(draw: random.Random, n: int, avoid: Sequence[Tuple[float, float]]
           = ()) -> Optional[List[Tuple[float, float]]]:
    out: List[Tuple[float, float]] = []
    taken = list(avoid) + [(PLATFORM - 0.1, 0.0)]       # the beacon
    for _k in range(n):
        for _try in range(60):
            r = PLATFORM * 0.82 * math.sqrt(draw.random())
            a = draw.uniform(0, 2 * math.pi)
            x, z = r * math.cos(a), r * math.sin(a)
            if all(math.hypot(x - u, z - v) > 1.7 for u, v in taken + out):
                out.append((x, z))
                break
        else:
            return None
    return out


def same_layout(a: Layout, b: Layout, tol: float = 0.45) -> bool:
    if sorted(t for t, _x, _z in a) != sorted(t for t, _x, _z in b):
        return False
    where = {t: (x, z) for t, x, z in a}
    return all(math.hypot(where[t][0] - x, where[t][1] - z) < tol
               for t, x, z in b)


def eye(look: float) -> Tuple[Vec, Matrix]:
    """Where the camera stands to look at the platform from *look*
    (radians round it), and its turn: rows right, up, forward."""
    c = (ORBIT * math.cos(ORBIT_RISE) * math.sin(look),
         ORBIT * math.sin(ORBIT_RISE),
         -ORBIT * math.cos(ORBIT_RISE) * math.cos(look))
    fwd = _mul(c, -1.0 / ORBIT)
    right = _cross((0.0, 1.0, 0.0), fwd)
    right = _mul(right, 1.0 / math.sqrt(_dot(right, right)))
    up = _cross(fwd, right)
    return c, (right, up, fwd)


def seen_from(look: float, p: Vec) -> Vec:
    """A platform point in the camera's frame: x right, y up, z ahead."""
    c, m = eye(look)
    return apply(m, _sub(p, c))


# --- instruments ------------------------------------------------------------

class Patch(NamedTuple):
    """One synthesised instrument. Every part is a closed form of the
    time since the note began, so any stretch of a note can be made on
    its own and the pieces join exactly."""
    name: str
    partials: Tuple[Tuple[float, float, float], ...]   # ratio, amp, decay
    fm: Tuple[float, float, float]      # ratio, index, index decay
    attack: float
    decay: float
    sustain: float
    release: float
    vibrato: Tuple[float, float] = (0.0, 0.0)    # rate Hz, depth
    tremolo: Tuple[float, float] = (0.0, 0.0)    # rate Hz, depth
    glide: Tuple[float, float] = (0.0, 0.0)      # start offset, seconds
    noise: float = 0.0
    drive: float = 0.0
    fold: float = 0.0
    ring: Tuple[float, float] = (0.0, 0.0)       # ratio, mix
    taps: Tuple[Tuple[float, float, float], ...] = ()   # delay, gain, pan


def _saw(n: int, decay: float = 0.0) -> Tuple[Tuple[float, float, float],
                                               ...]:
    return tuple((float(k), 1.0 / k, decay * k) for k in range(1, n + 1))


def make_patch(name: str, draw: random.Random, wild: float = 0.0) -> Patch:
    """An instrument of the kind *name*, with its own small differences,
    bent further the wilder it is asked to be."""
    j = lambda lo=0.9, hi=1.1: draw.uniform(lo, hi)   # noqa: E731
    if name == 'sine':
        p = Patch(name, ((1, 1, 0),), (0, 0, 0), 0.01, 2.5 * j(), 0.3, 0.2)
    elif name == 'flute':
        p = Patch(name, ((1, 1, 0), (2, 0.15, 0), (3, 0.05, 0)), (0, 0, 0),
                  0.06, 0.5, 0.7, 0.15, vibrato=(5 * j(), 0.004),
                  noise=0.07 * j())
    elif name == 'organ':
        p = Patch(name, ((1, 1, 0), (2, 0.6 * j(), 0), (3, 0.4 * j(), 0),
                         (4, 0.25, 0), (6, 0.15, 0), (8, 0.1 * j(), 0)),
                  (0, 0, 0), 0.015, 0.0, 1.0, 0.08)
    elif name == 'clarinet':
        p = Patch(name, ((1, 1, 0), (3, 0.55 * j(), 0), (5, 0.33, 0),
                         (7, 0.2 * j(), 0), (9, 0.12, 0)), (0, 0, 0),
                  0.04, 0.8, 0.8, 0.1)
    elif name == 'brass':
        p = Patch(name, _saw(7), (1, 1.5 * j(), 3), 0.04, 1.0, 0.6, 0.1,
                  glide=(-0.03, 0.05))
    elif name == 'pluck':
        p = Patch(name, _saw(6, 1.5 * j()), (0, 0, 0), 0.003, 4 * j(), 0.0,
                  0.1)
    elif name == 'bell':
        p = Patch(name, ((1, 1, 0), (2.76 * j(0.97, 1.03), 0.5, 1),
                         (5.4 * j(0.97, 1.03), 0.25, 2)),
                  (3.5 * j(0.97, 1.03), 3 * j(), 2.5), 0.002, 1.8 * j(), 0.0,
                  0.4)
    elif name == 'glass':
        p = Patch(name, ((1, 1, 0), (2.32 * j(0.97, 1.03), 0.6, 0.8),
                         (4.25 * j(0.97, 1.03), 0.4, 1.6),
                         (6.63, 0.25, 2.5)), (0, 0, 0), 0.005, 1.2 * j(),
                  0.0, 0.5)
    elif name == 'wood':
        p = Patch(name, ((1, 1, 0), (3.9 * j(0.95, 1.05), 0.5, 6),
                         (9.2 * j(0.95, 1.05), 0.25, 12)), (0, 0, 0),
                  0.002, 9 * j(), 0.0, 0.05)
    elif name == 'pad':
        p = Patch(name, ((1, 0.7, 0), (1.004 + 0.006 * draw.random(), 0.7, 0),
                         (2, 0.3, 0), (0.5, 0.3, 0)), (0, 0, 0), 0.15, 0.3,
                  0.8, 0.3, tremolo=(3 * j(), 0.3))
    elif name == 'growl':
        p = Patch(name, ((1, 1, 0),), (0.5, 4 * j(), 0.5), 0.02, 1.5, 0.5,
                  0.1, drive=2.5 * j())
    elif name == 'chirp':
        p = Patch(name, ((1, 1, 0), (2, 0.3, 0)), (0, 0, 0), 0.005, 5 * j(),
                  0.0, 0.08, glide=(draw.choice((1.0, -0.5)),
                                    0.04 * j()))
    elif name == 'metal':
        p = Patch(name, ((1, 1, 0), (1.41, 0.8, 1), (2.83, 0.5, 2),
                         (4.1 * j(0.97, 1.03), 0.4, 3)), (0, 0, 0), 0.002,
                  2.5 * j(), 0.0, 0.3, ring=(2.7 * j(), 0.5))
    elif name == 'square':
        p = Patch(name, tuple((float(k), 1.0 / k, 0.0) for k in (1, 3, 5, 7,
                                                               9)),
                  (0, 0, 0), 0.005, 1.0, 0.6, 0.05)
    elif name == 'sub':
        p = Patch(name, ((0.5, 1, 0), (1, 0.5, 0)), (0, 0, 0), 0.01, 2.0,
                  0.3, 0.1, drive=1.5)
    elif name == 'alien':
        p = Patch(name, ((1, 1, 0), (1.5, 0.4, 0)),
                  (draw.uniform(0.3, 3.3), draw.uniform(2, 8), 1.0), 0.01,
                  1.5, 0.5, 0.15, vibrato=(9 * j(), 0.03), fold=2.2 * j())
    elif name == 'zap':
        p = Patch(name, ((1, 1, 0),), (7.1 * j(), 6, 6), 0.002, 10 * j(),
                  0.0, 0.05, glide=(2.0, 0.03))
    elif name == 'hiss':
        p = Patch(name, (), (0, 0, 0), 0.005, 8 * j(), 0.0, 0.05, noise=1.0)
    else:
        raise ValueError(name)
    if wild <= 0.0:
        return p
    roll = draw.random
    changes = {}
    if roll() < wild * 0.5:
        changes['vibrato'] = (draw.uniform(3, 12), draw.uniform(0.005, 0.04))
    if roll() < wild * 0.4:
        changes['tremolo'] = (draw.uniform(2, 14), draw.uniform(0.2, 0.7))
    if roll() < wild * 0.3:
        changes['drive'] = draw.uniform(1.5, 4.0)
    if roll() < wild * 0.25:
        changes['fold'] = draw.uniform(1.5, 3.0)
    if roll() < wild * 0.3:
        changes['ring'] = (draw.uniform(0.5, 4.0), draw.uniform(0.3, 0.8))
    if roll() < wild * 0.3:
        changes['glide'] = (draw.uniform(-0.6, 1.2), draw.uniform(0.02, 0.1))
    if roll() < wild * 0.3:
        changes['taps'] = tuple((draw.uniform(0.1, 0.3) * (k + 1),
                                 0.45 / (k + 1), draw.choice((-1.0, -0.5)))
                                for k in range(draw.randint(1, 2)))
    if roll() < wild * 0.2:
        changes['noise'] = draw.uniform(0.05, 0.3)
    return p._replace(**changes)


def _noise(seed: int, q: int) -> float:
    h = (q * 2654435761 + seed * 40503 + 12345) & 0xffffffff
    h ^= h >> 15
    h = (h * 2246822519) & 0xffffffff
    h ^= h >> 13
    return h / 2147483648.0 - 1.0


def _voice(p: Patch, freq: float, dur: float, bright: float, seed: int):
    """The note as a function of sample index since it began."""
    w = 2 * math.pi * freq
    parts = [(r, a * (1.0 if r < 1.5 else bright ** 0.7), d)
             for r, a, d in p.partials if r * freq < NYQUIST_SAFE]
    norm = 1.0 / (sum(abs(a) for _r, a, _d in parts) or 1.0)
    fr, fi, fd = p.fm
    fi *= 0.4 + 0.6 * bright
    vr, vd = p.vibrato
    vw = 2 * math.pi * vr
    tr, td = p.tremolo
    tw = 2 * math.pi * tr
    g0, gt = p.glide
    rr, rm = p.ring
    drive_norm = math.tanh(p.drive) if p.drive else 1.0
    attack, decay, sustain, release = p.attack, p.decay, p.sustain, p.release
    exp, sin = math.exp, math.sin

    def f(q: int) -> float:
        t = q / RATE
        ph = w * t
        if g0:
            ph += w * g0 * gt * (1.0 - exp(-t / gt))
        if vd:
            ph += w * vd * (1.0 - math.cos(vw * t)) / vw
        mod = fi * exp(-fd * t) * sin(fr * ph) if fi else 0.0
        x = 0.0
        for r, a, d in parts:
            x += (a * exp(-d * t) if d else a) * sin(r * ph + mod)
        x *= norm
        if p.noise:
            x += p.noise * _noise(seed, q)
        if rm:
            x = x * (1.0 - rm) + x * sin(rr * ph) * rm
        if p.drive:
            x = math.tanh(p.drive * x) / drive_norm
        if p.fold:
            x = sin(p.fold * x)
        env = t / attack if t < attack else 1.0
        if decay:
            env *= sustain + (1.0 - sustain) * exp(-decay * t)
        if t > dur:
            env *= max(0.0, 1.0 - (t - dur) / release)
        if td:
            env *= 1.0 - td * (0.5 + 0.5 * sin(tw * t))
        return x * env
    return f


# --- a trial ----------------------------------------------------------------

class Candidate(NamedTuple):
    form: Form                # in its own frame
    view: Matrix              # how it is shown
    spin: Vec                 # axis it turns about (zero: it does not)
    size: float = 1.0         # how big it really is
    depth: float = 0.0        # how far off it stands, on a floor card
    side: float = 0.0         # how far left or right, on a floor card
    layout: Optional[Layout] = None   # a scene card's things and places
    look: float = 0.0         # where a scene card is seen from

    @property
    def segs(self) -> List[Segment]:
        return self.form.segs


class Note(NamedTuple):
    t: float
    dur: float
    freq: float
    pan: float                # -1 left .. 1 right, where the stroke starts
    pan2: float               # ... and where it ends
    gain: float               # loudness where it starts
    gain2: float              # ... and where it ends
    bright: float             # 0 dull .. 1 bright
    voice: int                # which of the trial's patches
    seed: int
    who: int                  # -1 the shape, k card k, -2 noise, -10-i thing i
    room: float = 0.0         # how much of the room is heard with it


class Puzzle(NamedTuple):
    level: Grade
    mode: str
    form: Optional[Form]      # the target as the turtle drew it
    view: Matrix              # how the target is shown and heard
    candidates: List[Candidate]
    answer: int
    patches: List[Patch]
    notes: List[Note]
    drawn_by: List[float]     # when each stroke is finished
    show_end: float
    choose: float             # seconds to choose
    spans: List[Tuple[int, float, float]]   # (card, from, to) it sounds
    hues: Tuple[int, ...]     # the colour shown for each tint
    things: List[Thing]       # a scene's things (and their stand-ins)
    layout: Optional[Layout]  # where a scene's things stand
    look: float               # where a scene is first seen from
    parts: List[Tuple[int, float, float]]   # (thing, from, to) it sings
    seed: int

    @property
    def shape(self) -> List[Segment]:
        return self.form.segs if self.form is not None else []

    @property
    def heard(self) -> bool:
        """The target is only heard, never seen."""
        return self.mode in ('hear', 'echo', 'hear_scene')

    @property
    def sound_cards(self) -> bool:
        """The candidates are sounds, not pictures."""
        return self.mode in SOUND_CARDS

    @property
    def scene(self) -> bool:
        return self.mode in SCENES

    @property
    def floor(self) -> bool:
        """Picture cards stand on a floor, near or far."""
        return self.level.floor and self.mode == 'see'


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None,
         mode: Optional[str] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    for _attempt in range(80):
        kind = mode or _pick_mode(level, draw)
        if kind in SCENES:
            puzzle = _build_scene(level, kind, draw, seed)
        else:
            puzzle = _build(level, draw, seed, kind)
        if puzzle is not None:
            return puzzle
    raise RuntimeError('no Dr Shape puzzle for rung %d' % rung)


def _tilt(draw: random.Random, level: Grade) -> Matrix:
    """A pleasant three-quarter view for the target."""
    if level.turn == 'none' and 'polygon' in level.families:
        return matmul(axis_turn((1, 0, 0), -0.35),
                      axis_turn((0, 0, 1), draw.uniform(0, 2 * math.pi)))
    return matmul(axis_turn((1, 0, 0), draw.uniform(-0.6, -0.2)),
                  axis_turn((0, 1, 0), draw.uniform(0, 2 * math.pi)))


def _pick_mode(level: Grade, draw: random.Random) -> str:
    roll = draw.random() * sum(w for _m, w in level.modes)
    for m, w in level.modes:
        roll -= w
        if roll <= 0:
            return m
    return level.modes[-1][0]


def tune(form, view: Matrix) -> Tuple:
    """What an ear can tell of a shape's song: each note's step on the
    scale, its length, which side it is on and its instrument."""
    notes, _done, _end = sing(form, view, 0.0)
    return tuple((round(math.log2(n.freq / 196.0) * 12),
                  round(n.dur * 10), round((n.pan + n.pan2) * 2), n.voice)
                 for n in notes)


def _patches(level: Grade, draw: random.Random) -> List[Patch]:
    """One instrument per colour, one per colour for echoes, spares."""
    names = list(level.instruments)
    mine = draw.sample(names, TINTS)
    out = [make_patch(n, draw, level.wild) for n in mine]
    if level.echo_voice:
        others = [n for n in names if n not in mine] or names
        echo = draw.sample(others, min(TINTS, len(others)))
        while len(echo) < TINTS:
            echo.append(draw.choice(names))
        out += [make_patch(n, draw, level.wild) for n in echo]
    else:
        out += out[:TINTS]
    out += [make_patch(draw.choice(names), draw, level.wild)
            for _k in range(4)]
    return out


SPARE = 2 * TINTS            # the first spare patch


def _hues(draw: random.Random) -> Tuple[int, ...]:
    """Colours for the tints, spread round the wheel so none is mistaken
    for another."""
    h = draw.randrange(12)
    step = draw.choice((4, -4))
    return tuple((h + step * k) % 12 for k in range(TINTS))


def _build(level: Grade, draw: random.Random, seed: int,
           mode: str) -> Optional[Puzzle]:
    family = draw.choice(level.families)
    params = draw_params(family, draw)
    base = build(family, params)
    if len(base.segs) < 3:
        return None
    strict = mode != 'see'            # told apart by ear, at least partly
    floor = level.floor and mode == 'see'
    k = 1 if level.colours == 1 else draw.randint(2, level.colours)
    target = colour(base, k, draw)
    chiral = abs(handedness(target.segs)) > 0.08
    view = _tilt(draw, level)
    margin = 0.25 if strict else 0.12
    known = {tune(target, view)}
    decoys: List[Tuple[Form, float]] = []
    counts: Dict[str, int] = {}
    tries = 0
    while len(decoys) < level.candidates - 1 and tries < 120:
        tries += 1
        roll = draw.random()
        size = 1.0
        if floor and roll < 0.3 and counts.get('size', 0) < 2:
            kind, other = 'size', target
            size = draw.choice((0.55, 0.6, 1.65, 1.8))
        elif level.mirror and chiral and roll < 0.45 and \
                counts.get('mirror', 0) < 1:
            kind, other = 'mirror', mirrored_form(target)
        elif k > 1 and roll < 0.65 and counts.get('colour', 0) < 2:
            kind, other = 'colour', recoloured(target, draw)
        elif level.near and (not strict or level.rung >= 17) and roll < 0.85:
            kind = 'near'
            other = colour(build(family, nudge(family, params, draw)), k,
                           draw)
        else:
            kind = 'other'
            fam = family if strict and draw.random() < 0.5 else \
                draw.choice(level.families)
            other = colour(build(fam, draw_params(fam, draw)), k, draw)
        if len(other.segs) < 3:
            continue
        if not distinct(target, other, margin, 1.0, size):
            continue
        if any(not distinct(d, other, 0.1, ds, size) for d, ds in decoys):
            continue
        if strict:
            heard = tune(other, view)
            if heard in known:
                continue
            known.add(heard)
        counts[kind] = counts.get(kind, 0) + 1
        decoys.append((other, size))
    if len(decoys) < level.candidates - 1:
        return None
    answer = draw.randrange(level.candidates)
    forms = decoys[:answer] + [(target, 1.0)] + decoys[answer:]
    cands = []
    for f, size in forms:
        if level.turn == 'none' or strict:
            v = view
        elif level.turn == 'plane':
            v = matmul(view, axis_turn((0, 0, 1),
                                       draw.uniform(0.5, 2 * math.pi - 0.5)))
        else:
            v = random_turn(draw)
        spin: Vec = (0.0, 0.0, 0.0)
        if level.tumble and mode == 'see':
            spin = (0.0, 1.0, 0.0) if floor else \
                (draw.uniform(-1, 1), draw.uniform(-1, 1), draw.uniform(-1, 1))
        depth = side = 0.0
        if floor:
            depth = size * draw.uniform(2.3, 4.4)
            side = draw.uniform(-0.25, 0.25) * depth
        cands.append(Candidate(f, v, spin, size, depth, side))
    patches = _patches(level, draw)
    hues = _hues(draw)
    voice_of = None
    if level.overload >= 0.5 and mode in ('see', 'hear'):
        spare = SPARE + draw.randrange(4)
        voice_of = lambda t, i: t if i % 2 == 0 else spare   # noqa: E731
    notes, drawn_by, end = sing(target, view, LEAD_IN, level.tempo,
                                voice_of,
                                distance=SHOW_DEPTH if floor else None)
    if mode == 'sing':
        notes = []
    show_end = end + HOLD
    choose = level.choose
    spans: List[Tuple[int, float, float]] = []
    if mode in SOUND_CARDS:
        shift = draw.choice((-12, -7, -5, 5, 7, 12)) \
            if mode == 'echo' and level.echo_key else 0
        off = TINTS if mode == 'echo' else 0
        t = show_end + 0.5
        for _pass in range(2):
            for i, c in enumerate(cands):
                more, _d, e = sing(c.form, view, t, level.tempo * 1.15,
                                   lambda tint, _i: tint + off,
                                   transpose=shift, who=i)
                notes += more
                spans.append((i, t, e))
                t = e + 0.45
            t += 0.6
        choose = max(choose, t - show_end + 2.5)
    elif level.chorus and mode == 'see':
        n = len(cands)
        t = show_end + 0.6
        for i, c in enumerate(cands):
            pan = -0.8 + 1.6 * i / max(1, n - 1)
            more, _d, e = sing(c.form, c.view, t, 1.3, pan_shift=pan,
                               pan_width=0.2, gain=0.55, who=i,
                               distance=c.depth if floor else None)
            notes += more
            spans.append((i, t, e))
            t = e + 0.25 if level.overload < 0.5 else t + 0.6
    if level.overload:
        notes += _noise_for(level, draw, patches, show_end + choose)
    notes.sort()
    return Puzzle(level, mode, target, view, cands, answer, patches, notes,
                  drawn_by, show_end, choose, spans, hues, [], None, 0.0, [],
                  seed)


def _noise_for(level: Grade, draw: random.Random, patches: List[Patch],
               until: float) -> List[Note]:
    first = len(patches)
    patches += [make_patch(draw.choice(('hiss', 'zap', 'chirp', 'wood',
                                        'metal', 'alien')), draw, 1.0)
                for _k in range(3)]
    return _decoys(level, draw, until, first)


def _build_scene(level: Grade, mode: str, draw: random.Random, seed: int
                 ) -> Optional[Puzzle]:
    """Three things on a platform by a beacon, and the same platform with
    something changed, seen from elsewhere."""
    kinds = [f for f in level.families if f not in ('polygon', 'star',
                                                    'spiral', 'branch')]
    fams = draw.sample(kinds, 3) if len(kinds) >= 3 else \
        [draw.choice(kinds) for _k in range(3)]
    things: List[Thing] = []
    for i, fam in enumerate(fams):
        f = build(fam, draw_params(fam, draw))
        if len(f.segs) < 3:
            return None
        f = colour(f, 1, draw)
        f = Form(f.segs, [i] * len(f.segs), [(p, i) for p, _t in f.faces])
        things.append(Thing(f, random_turn(draw), i))
    spots = _spots(draw, 3)
    if spots is None:
        return None
    layout: Layout = tuple((i, x, z) for i, (x, z) in enumerate(spots))
    look0 = draw.uniform(0, 2 * math.pi)
    decoys: List[Layout] = []
    tries = 0
    while len(decoys) < level.candidates - 1 and tries < 100:
        tries += 1
        roll = draw.random()
        if roll < 0.3:
            a, b = draw.sample(range(3), 2)
            where = {t: (x, z) for t, x, z in layout}
            where[a], where[b] = where[b], where[a]
            other = tuple((t, *where[t]) for t in range(3))
        elif roll < 0.55:
            i = draw.randrange(3)
            rest_ = [(x, z) for t, x, z in layout if t != i]
            spot = _spots(draw, 1, rest_)
            if spot is None:
                continue
            other = tuple((t, *(spot[0] if t == i else (x, z)))
                          for t, x, z in layout)
        elif roll < 0.75:
            other = tuple((t, x, -z) for t, x, z in layout)
        else:
            i = draw.randrange(3)
            fam = draw.choice(kinds)
            f = build(fam, draw_params(fam, draw))
            f = Form(f.segs, [i] * len(f.segs), [(p, i) for p, _t in f.faces])
            if len(f.segs) < 3 or not distinct(things[i].form, f, 0.2):
                continue
            things.append(Thing(f, random_turn(draw), i))
            other = tuple((len(things) - 1 if t == i else t, x, z)
                          for t, x, z in layout)
        if same_layout(other, layout) or \
                any(same_layout(other, d) for d in decoys):
            continue
        decoys.append(other)
    if len(decoys) < level.candidates - 1:
        return None
    answer = draw.randrange(level.candidates)
    layouts = decoys[:answer] + [layout] + decoys[answer:]
    away = look0 + draw.choice((-1, 1)) * draw.uniform(0.9, 2.4)
    cands = []
    for lay in layouts:
        if mode == 'hear_scene':
            look = look0
        elif level.each_side:
            look = look0 + draw.choice((-1, 1)) * draw.uniform(0.9, 2.6)
        else:
            look = away
        cands.append(Candidate(things[0].form, IDENTITY, (0.0, 0.0, 0.0),
                               layout=lay, look=look))
    patches = _patches(level, draw)
    hues = _hues(draw)
    notes: List[Note] = []
    parts = []
    t = LEAD_IN
    _c, cam = eye(look0)
    for i, x, z in layout:
        th = things[i]
        g, lift = rest(th.form, th.turn, OBJECT)
        where = seen_from(look0, (x, lift, z))
        d = math.sqrt(_dot(where, where))
        pan = max(-1.0, min(1.0, 2.2 * where[0] / where[2]))
        more, _done, end = sing(th.form, matmul(cam, th.turn), t,
                                level.tempo, pan_shift=pan, pan_width=0.15,
                                who=-10 - i, distance=d, ref=ORBIT)
        notes += more
        parts.append((i, t, end))
        t = end + 0.5
    show_end = t + HOLD
    if level.overload:
        notes += _noise_for(level, draw, patches, show_end + level.choose)
    notes.sort()
    return Puzzle(level, mode, None, IDENTITY, cands, answer, patches, notes,
                  [], show_end, level.choose, [], hues, things, layout,
                  look0, parts, seed)


def sing(form, view: Matrix, start: float, tempo: float = 1.0,
         voice_of=None, pan_shift: float = 0.0, pan_width: float = 1.0,
         gain: float = 1.0, transpose: int = 0, who: int = -1,
         distance: Optional[float] = None, ref: float = SHOW_DEPTH
         ) -> Tuple[List[Note], List[float], float]:
    """A shape heard: one note per stroke, in the order drawn. Height is
    pitch, left-right is pan (moving with the stroke), nearness is
    loudness and brightness, length is duration, and colour is the
    instrument. A shape far off is quieter, duller, a little late and
    full of the room. Returns the notes, when each stroke is done, and
    when the last note ends."""
    if not isinstance(form, Form):
        form = form_of(form)
    room, late, far = 0.0, 0.0, 1.0
    if distance is not None:
        far = max(0.3, min(1.5, ref / max(0.3, distance)))
        room = min(0.85, 0.25 * distance / ref)
        late = distance / SPEED_OF_SOUND
    notes, done = [], []
    t = start
    for k, ((a, b), tint) in enumerate(zip(form.segs, form.tints)):
        a, b = apply(view, a), apply(view, b)
        mid = _mul(_add(a, b), 0.5)
        d = _sub(b, a)
        length = math.sqrt(_dot(d, d))
        dur = max(0.2, min(0.7, length * NOTE_UNIT)) / tempo
        step = int(round((mid[1] + 1.0) * 4.5))         # 0 .. 9
        step = max(0, min(9, step))
        semis = 12 * (step // 5) + SCALE[step % 5] + transpose
        freq = 196.0 * 2 ** (semis / 12.0)

        def near(p: Vec) -> float:
            return max(0.0, min(1.0, (p[2] + 1.0) / 2.0))

        def pan(p: Vec) -> float:
            return max(-1.0, min(1.0, pan_shift + p[0] * pan_width))
        voice = tint if voice_of is None else voice_of(tint, k)
        notes.append(Note(t + late, dur, freq, pan(a), pan(b),
                          far * gain * (0.35 + 0.65 * near(a)),
                          far * gain * (0.35 + 0.65 * near(b)),
                          min(1.0, far) * (0.25 + 0.75 * near(mid)),
                          voice, k + 1000 * (who + 30), who, room))
        t += dur
        done.append(t)
    return notes, done, t


def _decoys(level: Grade, draw: random.Random, until: float,
            first: int) -> List[Note]:
    """Decoy chirps and hiss, scattered across both ears."""
    out = []
    o = level.overload
    t = 0.2
    while t < until:
        p1, p2 = draw.uniform(-1, 1), draw.uniform(-1, 1)
        g = 0.12 + 0.22 * o
        out.append(Note(t, draw.uniform(0.05, 0.3), draw.uniform(150, 1600),
                        p1, p2, g, g * draw.uniform(0.3, 1.0),
                        draw.random(), first + draw.randrange(3),
                        draw.randrange(1 << 20), -2))
        t += draw.expovariate(2.0 + 8.0 * o)
    return out


# --- sound ------------------------------------------------------------------

ITD = 0.0006                 # the far ear hears a note this much later
#: A room's first reflections: delay, gain, and where each comes from
#: (as a share of the note's own side, negative for the other side).
ROOM = ((0.043, 0.55, -0.7), (0.071, 0.45, 0.6), (0.113, 0.35, -0.3),
        (0.167, 0.25, 0.8), (0.231, 0.18, -0.9))


def synth(notes: Sequence[Note], t0: float, t1: float,
          patches: Sequence[Patch], rate: int = RATE) -> bytes:
    """Stereo 16-bit PCM of *notes* from *t0* to *t1*. The far ear hears
    a note a fraction of a millisecond late and softer, as a real ear
    does, and a note slides between the ears as its stroke does, so the
    sound sits and moves in space rather than in one speaker."""
    frames = max(0, int(round((t1 - t0) * rate)))
    left = [0.0] * frames
    right = [0.0] * frames
    for n in notes:
        p = patches[n.voice]
        span = n.dur + p.release
        taps = list(p.taps)
        if n.room:
            taps += [(d, g * n.room, pm) for d, g, pm in ROOM]
        reach = span + max((d for d, _g, _p in taps), default=0.0)
        if n.t >= t1 or n.t + reach <= t0:
            continue
        base = int(math.floor((t0 - n.t) * rate + 0.5 + 1e-9))
        qend = int(span * rate)
        mid = 0.5 * (n.pan + n.pan2)
        lag = int(round(ITD * abs(mid) * rate))
        lag_l, lag_r = (lag, 0) if mid > 0 else (0, lag)
        # (lag left, lag right, gain, fixed pan or None to follow the note)
        sources = [(lag_l, lag_r, 1.0, None)]
        for d, g, pm in taps:
            ds = int(round(d * rate))
            sources.append((ds + lag_r, ds + lag_l, g, mid * pm))
        top = max(max(a, b) for a, b, _g, _p in sources)
        qlo = max(0, base - top)
        qhi = min(qend, base + frames)
        if qhi <= qlo:
            continue
        f = _voice(p, n.freq, n.dur, n.bright, n.seed)
        buf = [f(q) for q in range(qlo, qhi)]
        a0 = (n.pan + 1.0) * math.pi / 4.0
        a1 = (n.pan2 + 1.0) * math.pi / 4.0
        gl0, gr0 = math.cos(a0) * n.gain, math.sin(a0) * n.gain
        gl1, gr1 = math.cos(a1) * n.gain2, math.sin(a1) * n.gain2
        dq = max(1.0, n.dur * rate)
        for lag_a, lag_b, g, fixed in sources:
            if fixed is not None:
                af = (fixed + 1.0) * math.pi / 4.0
                fl = math.cos(af) * g * 0.5 * (n.gain + n.gain2)
                fr = math.sin(af) * g * 0.5 * (n.gain + n.gain2)
            for ear, lagq, side in ((left, lag_a, 0), (right, lag_b, 1)):
                start = max(0, qlo - base + lagq)
                stop = min(frames, qhi - base + lagq)
                for i in range(start, stop):
                    q = base + i - lagq
                    if fixed is None:
                        s = q / dq
                        s = 1.0 if s > 1.0 else s
                        if side == 0:
                            gain = gl0 + (gl1 - gl0) * s
                        else:
                            gain = gr0 + (gr1 - gr0) * s
                    else:
                        gain = fr if side else fl
                    ear[i] += gain * buf[q - qlo]
    out = array.array('h', bytes(4 * frames))
    for i in range(frames):
        out[2 * i] = int(math.tanh(left[i] * 0.8) * 30000)
        out[2 * i + 1] = int(math.tanh(right[i] * 0.8) * 30000)
    return out.tobytes()


# --- a run ------------------------------------------------------------------
# --- a run ------------------------------------------------------------------

class Run:
    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.level = puzzle.level
        self.t = 0.0
        self.choice: Optional[int] = None
        self.result: Optional[Tuple[bool, str]] = None

    @property
    def choosing(self) -> bool:
        return self.t >= self.puzzle.show_end

    def strokes(self) -> float:
        """How many strokes the turtle has drawn (fractional mid-stroke)."""
        p = self.puzzle
        prev = LEAD_IN
        for k, end in enumerate(p.drawn_by):
            if self.t < end:
                return k + max(0.0, (self.t - prev) / (end - prev))
            prev = end
        return float(len(p.drawn_by))

    def singing_thing(self) -> Optional[int]:
        """The scene's thing singing now, while the scene is shown."""
        for i, a, b in self.puzzle.parts:
            if a <= self.t <= b + 0.3:
                return i
        return None

    def sounding(self) -> Optional[int]:
        """The card whose sound is playing now, if one is."""
        for k, a, b in self.puzzle.spans:
            if a <= self.t <= b:
                return k
        return None

    def pick(self, k: int) -> None:
        if self.result is not None or not self.choosing:
            return
        if not 0 <= k < len(self.puzzle.candidates):
            return
        self.choice = k
        if k == self.puzzle.answer:
            self.result = (True, _('Card %d -- that is the one') % (k + 1))
        else:
            self.result = (False, _('Not card %d -- it was card %d')
                           % (k + 1, self.puzzle.answer + 1))

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t >= self.puzzle.show_end + self.puzzle.choose:
            self.result = (False, _('Time up -- it was card %d')
                           % (self.puzzle.answer + 1))


def act(run: Run, port: int) -> None:
    run.pick(port)


def autopilot(run: Run) -> List[int]:
    """The reference: it knows the answer, and waits until it may pick."""
    if run.result is None and run.choosing:
        return [run.puzzle.answer]
    return []


def play(puzzle: Puzzle, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(puzzle)
    while run.result is None:
        for port in pilot(run):
            act(run, port)
        run.step(dt)
    return run.result
