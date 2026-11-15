# -*- coding: utf-8 -*-
"""Dr Shape: a 3D turtle draws a shape and sings it; find it again.

A turtle flies through space laying down a line, and every stroke it
draws is also a note: the stroke's height is the note's pitch, its
left-right place is where the note sits between the two ears -- and the
note travels from one ear toward the other as the stroke does -- its
nearness is how loud and bright it rings, and its length is how long it
lasts. So every shape has a sound, and the sound is the shape heard.

A trial is one of four kinds:

* **see** -- watch (and hear) the turtle draw; pick the same shape from
  look-alikes on cards;
* **hear** -- the shape is only heard; pick what it sounded like from
  shapes on cards;
* **sing** -- the turtle draws in silence; the cards are sounds, played
  in turn; pick the sound that is the shape;
* **echo** -- the shape is only heard; the cards are sounds again, played
  on another instrument and in another key; pick the same tune.

Each trial deals its own instruments from a bank of synthesised ones --
bells, glass, wood, reeds, brass, plucks, pads, growls, chirps, metal and
stranger things -- and higher up bends them with vibrato, tremolo,
drive, folding, ring modulation, glides and echoes.

The ladder:

* rungs 1-2: flat polygons and stars, the shape stays in view;
* rungs 3-4: flat shapes from memory; some trials are echoes, same
  instrument, same key;
* rungs 5-7: paths through space, turned every which way; some trials
  ask which sound is the shape;
* rungs 8-10: mirror images and shapes with one stroke changed; echoes
  move key;
* rungs 11-13: knots and coils, five candidates, colours that lie;
  echoes change instrument too;
* rungs 14-16: shapes only heard, and sounds to pick;
* rungs 17-19: the candidates tumble and sing their own shapes;
* from rung 20: sensory overload -- branching shapes, six candidates,
  noise, flicker, jitter, decoy sounds and instruments that change
  under every stroke, worse every rung.

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
MODES = ('see', 'hear', 'sing', 'echo')
#: Modes whose candidates are sounds rather than pictures.
SOUND_CARDS = ('sing', 'echo')

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
    recolour: bool       # colours mean nothing
    modes: Tuple[Tuple[str, float], ...]   # trial kinds and their odds
    echo_key: bool       # echoes move key
    echo_voice: bool     # echoes change instrument
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
    over = 0.0 if r < 20 else min(1.0, 0.25 + 0.075 * (r - 20))
    if r < 3:
        fam = ('polygon', 'star')
    elif r < 5:
        fam = ('polygon', 'star', 'spiral')
    elif r < 11:
        fam = ('space',)
    elif r < 20:
        fam = ('coil', 'space')
    else:
        fam = ('space', 'coil', 'branch')
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
        modes = (('see', 0.4), ('hear', 0.2), ('sing', 0.2), ('echo', 0.2))
    else:
        modes = tuple((m, 0.25) for m in MODES)
    return Grade(
        rung=r,
        families=fam,
        candidates=(3 if r < 3 else 4 if r < 11 else 5 if r < 20 else 6),
        keep=r < 3,
        turn='none' if r < 3 else 'plane' if r < 5 else 'space',
        mirror=8 <= r < 14 or r >= 17,
        near=8 <= r < 14 or r >= 17,
        recolour=r >= 11,
        modes=modes,
        echo_key=r >= 8,
        echo_voice=r >= 11,
        tumble=r >= 17,
        chorus=r >= 17,
        overload=over,
        wild=(0.0 if r < 5 else 0.2 if r < 11 else 0.45 if r < 20
              else 0.6 + 0.4 * over),
        instruments=(GENTLE if r < 5 else MORE if r < 11 else MANY if r < 20
                     else ALL),
        choose=(14.0 if r < 11 else 12.0 if r < 20
                else max(8.0, 11.0 - 0.15 * (r - 20))),
        tempo=1.0 if r < 20 else 1.0 + 0.6 * over)


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
    segs: List[Segment]       # in its own frame
    view: Matrix              # how it is shown
    spin: Vec                 # axis it tumbles about (zero: it does not)
    colour: int


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
    who: int                  # -1 the shape, k candidate k, -2 noise


class Puzzle(NamedTuple):
    level: Grade
    mode: str                 # 'see', 'hear', 'sing' or 'echo'
    shape: List[Segment]      # the target, as the turtle drew it
    view: Matrix              # how the target is shown and heard
    candidates: List[Candidate]
    answer: int
    patches: List[Patch]
    notes: List[Note]
    drawn_by: List[float]     # when each stroke is finished
    show_end: float
    choose: float             # seconds to choose
    spans: List[Tuple[int, float, float]]   # (card, from, to) it sounds
    seed: int

    @property
    def heard(self) -> bool:
        """The shape is only heard, never seen."""
        return self.mode in ('hear', 'echo')

    @property
    def sound_cards(self) -> bool:
        """The candidates are sounds, not pictures."""
        return self.mode in SOUND_CARDS


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None,
         mode: Optional[str] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    for _attempt in range(60):
        puzzle = _build(level, draw, seed, mode)
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


def tune(segs: Sequence[Segment], view: Matrix) -> Tuple:
    """What an ear can tell of a shape's song: each note's step on the
    scale, its length and which side it is on."""
    notes, _done, _end = sing(segs, view, 0.0)
    return tuple((round(math.log2(n.freq / 196.0) * 12),
                  round(n.dur * 10), round((n.pan + n.pan2) * 2))
                 for n in notes)


def _build(level: Grade, draw: random.Random, seed: int,
           mode: Optional[str] = None) -> Optional[Puzzle]:
    mode = mode or _pick_mode(level, draw)
    family = draw.choice(level.families)
    program = make_program(family, draw)
    shape = trace(program)
    if len(shape) < 3:
        return None
    strict = mode != 'see'            # told apart by ear, at least partly
    chiral = abs(handedness(shape)) > 0.08
    view = _tilt(draw, level)
    known = {tune(shape, view)}
    # The look-alikes.
    decoys: List[List[Segment]] = []
    tries = 0
    while len(decoys) < level.candidates - 1 and tries < 80:
        tries += 1
        roll = draw.random()
        if level.mirror and chiral and roll < 0.3 and \
                not any(not unlike(d, shape) for d in decoys):
            other = mirrored(shape)
        elif level.near and (not strict or level.rung >= 17) and \
                roll < 0.75:
            other = trace(bend(program, draw))
            if len(other) < 3 or not unlike(other, shape,
                                            0.25 if strict else 0.12):
                continue
        else:
            fam = family if strict and draw.random() < 0.5 else \
                draw.choice(level.families)
            other = trace(make_program(fam, draw))
            if len(other) < 3 or not unlike(other, shape,
                                            0.25 if strict else 0.12):
                continue
        if any(not unlike(other, d, 0.1) and
               (handedness(other) > 0) == (handedness(d) > 0)
               for d in decoys):
            continue
        if strict:
            heard = tune(other, view)
            if heard in known:
                continue
            known.add(heard)
        decoys.append(other)
    if len(decoys) < level.candidates - 1:
        return None
    answer = draw.randrange(level.candidates)
    shapes = decoys[:answer] + [shape] + decoys[answer:]
    hue = draw.randrange(12)
    cands = []
    for k, segs in enumerate(shapes):
        if level.turn == 'none' or strict:
            v = view
        elif level.turn == 'plane':
            v = matmul(view, axis_turn((0, 0, 1),
                                       draw.uniform(0.5, 2 * math.pi - 0.5)))
        else:
            v = random_turn(draw)
        spin = (draw.uniform(-1, 1), draw.uniform(-1, 1),
                draw.uniform(-1, 1)) if level.tumble and mode == 'see' \
            else (0.0, 0.0, 0.0)
        colour = draw.randrange(12) if level.recolour else hue
        cands.append(Candidate(segs, v, spin, colour))
    # The instruments: the shape's own, an echo's, and spares.
    names = level.instruments
    main = draw.choice(names)
    patches = [make_patch(main, draw, level.wild)]
    if level.echo_voice:
        patches.append(make_patch(draw.choice([n for n in names
                                               if n != main]), draw,
                                  level.wild))
    else:
        patches.append(patches[0])
    for _k in range(4):
        patches.append(make_patch(draw.choice(names), draw, level.wild))
    spare = list(range(2, len(patches)))
    # The shape's own song (silent in a sing trial, where only the
    # cards sound).
    voices: Tuple[int, ...] = (0,)
    if level.overload >= 0.5 and mode in ('see', 'hear'):
        voices = (0, draw.choice(spare))
    notes, drawn_by, end = sing(shape, view, LEAD_IN, level.tempo, voices)
    if mode == 'sing':
        notes = []
    show_end = end + HOLD
    choose = level.choose
    spans: List[Tuple[int, float, float]] = []
    if mode in SOUND_CARDS:
        shift = draw.choice((-12, -7, -5, 5, 7, 12)) \
            if mode == 'echo' and level.echo_key else 0
        voice = 1 if mode == 'echo' else 0
        t = show_end + 0.5
        for _pass in range(2):
            for k, c in enumerate(cands):
                more, _d, e = sing(c.segs, view, t, level.tempo * 1.15,
                                   (voice,), transpose=shift, who=k)
                notes += more
                spans.append((k, t, e))
                t = e + 0.45
            t += 0.6
        choose = max(choose, t - show_end + 2.5)
    elif level.chorus:
        n = len(cands)
        t = show_end + 0.6
        for k, c in enumerate(cands):
            pan = -0.8 + 1.6 * k / max(1, n - 1)
            more, _d, e = sing(c.segs, c.view, t, 1.3,
                               (spare[k % len(spare)],), pan_shift=pan,
                               pan_width=0.2, gain=0.55, who=k)
            notes += more
            spans.append((k, t, e))
            t = e + 0.25 if level.overload < 0.5 else t + 0.6
    if level.overload:
        patches += [make_patch(draw.choice(('hiss', 'zap', 'chirp', 'wood',
                                            'metal', 'alien')), draw, 1.0)
                    for _k in range(3)]
        notes += _decoys(level, draw, show_end + choose,
                         len(patches) - 3)
    notes.sort()
    return Puzzle(level, mode, shape, view, cands, answer, patches, notes,
                  drawn_by, show_end, choose, spans, seed)


def sing(segs: Sequence[Segment], view: Matrix, start: float,
         tempo: float = 1.0, voices: Sequence[int] = (0,),
         pan_shift: float = 0.0, pan_width: float = 1.0, gain: float = 1.0,
         transpose: int = 0, who: int = -1
         ) -> Tuple[List[Note], List[float], float]:
    """A shape heard: one note per stroke, in the order drawn. Height is
    pitch, left-right is pan (moving with the stroke), nearness is
    loudness and brightness, and length is duration. Returns the notes,
    when each stroke is done, and when the last note ends."""
    notes, done = [], []
    t = start
    for k, (a, b) in enumerate(segs):
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
        notes.append(Note(t, dur, freq, pan(a), pan(b),
                          gain * (0.35 + 0.65 * near(a)),
                          gain * (0.35 + 0.65 * near(b)),
                          0.25 + 0.75 * near(mid),
                          voices[k % len(voices)], k + 1000 * (who + 3),
                          who))
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
        reach = span + max((d for d, _g, _p in p.taps), default=0.0)
        if n.t >= t1 or n.t + reach <= t0:
            continue
        base = int(math.floor((t0 - n.t) * rate + 0.5 + 1e-9))
        qend = int(span * rate)
        mid = 0.5 * (n.pan + n.pan2)
        lag = int(round(ITD * abs(mid) * rate))
        lag_l, lag_r = (lag, 0) if mid > 0 else (0, lag)
        # (lag left, lag right, gain, fixed pan or None to follow the note)
        sources = [(lag_l, lag_r, 1.0, None)]
        for d, g, pm in p.taps:
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
