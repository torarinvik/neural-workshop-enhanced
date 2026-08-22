# -*- coding: utf-8 -*-
"""Procedurally distorted letters: the rules, with no pixels drawn yet.

A task that shows a letter and asks which letter it is can be answered
two ways. One is to recognise the shape. The other is to remember what
that shape looks like in the handful of typefaces the task ever used.
The second is much easier, and nothing in the picture tells you which
one happened.

This module exists to close that gap. A letter is drawn in one of the
several hundred typefaces already installed on the machine, and then
put through a warp sampled from a rung of a ladder: stretched, sheared,
turned, tilted in perspective, rippled, thickened or thinned, specked,
partly covered, and faded toward its background. Every one of those is
a separate knob, sampled independently, so the space of appearances is
not a set to memorise but a volume to sample from.

The split that matters
----------------------

Two axes are deliberately kept apart, because they answer different
questions:

* what the letter *is* — which is the task's content, and
* what the letter *looks like* — which is this module.

They are dealt from different seeds and neither reads the other. A rung
of visual difficulty can therefore be put under any content difficulty
a task already has, and a result can say which of the two moved.

The other split that matters is by **family, not by file**. Georgia
Bold Italic and Georgia are one typeface in two files; holding one out
while training on the other is not a held-out test, it is a leak with a
different filename. :func:`families` groups files by the family name in
the font's own ``name`` table, and :func:`split` divides those groups,
so a family is wholly in one part or wholly in another.

What the ladder is worth
------------------------

Asserted difficulty is not difficulty, so the ladder is measured. The
measurement is a nearest-template letter classifier — :func:`signature`
and :func:`recognise` — with its templates built from clean renders in
the *training* families and its questions asked in the *held-out* ones.
It is a weak recogniser on purpose: it knows nothing but where the ink
sits in an eight-by-eight grid over the letter's own ink box.

Measured on this machine over the twenty-six capitals in the ten
held-out families of a 41/8/10 split, templates from the forty-one
training ones. 260 deals a rung, so a figure here is worth about three
points either way; ``tests/bench_glyphs.py`` reruns the whole column.

    rung  1  a clean page            0.89
    rung  2  a hand that wavers      0.87
    rung  3  a slight lean           0.78
    rung  4  off the flat            0.59
    rung  5  thick and thin          0.38
    rung  6  a rippled page          0.27
    rung  7  through the blinds      0.17
    rung  8  a bad photocopy         0.15
    rung  9  a dirty window          0.10
    rung 10  most of it is gone      0.09

Four things in that column are worth saying out loud rather than
leaving for someone to trip over.

The first rung does not score 1.00, and it never will: the recogniser
is looking at typefaces it has never seen, which is the whole point,
and Chalkduster's capital G is not an eight-by-eight match for Big
Caslon's. The 0.89 is the ceiling this measurement has, not a fault in
rung one. What the column shows is the *fall* from it.

The floor is 1/26 = 0.04, and rung ten sits at 0.09, which is to say
rung ten is very nearly unanswerable *by this recogniser*. That is a
statement about the recogniser, not about a reader or about a learner
with convolutions; do not read the last two rungs as "impossible".

The fall is not spread evenly across the knobs. Switching each off in
turn at rung six, against 0.24 with all of them on:

    matrix off   0.45      speckle off      0.37
    ripple off   0.29      occlusion off    0.30
    thicken off  0.25      contrast off     0.23
    all off      0.89

Two readings. The knobs compound: the six gains add to 0.46 and
turning all six off is worth 0.65, so a third of rung six's difficulty
is in the combination rather than in any one of it. And thickening and
contrast recover *nothing*, which is a fact about the measurement
rather than about them — a signature counts pixels above a fixed
threshold, so a letter uniformly fattened keeps its proportions and a
letter faded to eighty per cent is still well above the threshold.
Contrast is a knob aimed at something reading pixels; this oracle is
blind to it by construction and cannot price it either way.

The fourth is the reason the ripple has its own budget and its own
check. It is the knob that most looks like difficulty and it is worth
+0.05, less than the plain affine matrix underneath it: an eight-by-
eight grid barely notices ink sliding a tenth of a letter sideways.
It was worth a quarter of that before — the slope budget was split
across both axes at once, which shrank the amplitude for no gain in
safety — and finding either number took measuring it, not looking at
a picture of it.

One more thing about the pool, because it invalidated the first
version of every number above. See :func:`covered`: of the 198 font
families on this machine, only 59 actually contain Latin capitals, and
asking one of the other 139 for a capital A gets a perfectly good
letter drawn by the system's *fallback* font. A held-out family that
is really the fallback is the training typeface being scored as
unseen, and two thirds of the first pool were exactly that.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import os
import random
import struct
import sys
from typing import (Dict, Iterable, List, NamedTuple, Optional, Sequence,
                    Tuple)

TAU = math.pi * 2.0

#: Alpha at or above which a pixel counts as ink.
INK = 128

#: Cells a side in the recogniser's grid. Small on purpose: see the
#: module docstring on why the measurement is a weak one.
CELLS = 8

#: The elastic waves' steepest total slope, *per axis*. Reach 1.0 and
#: the map can fold back on itself, and a letter put through a folded
#: map is not a rearranged letter any more. Per axis rather than in
#: total because the two axes displace independently and it is each
#: one's own gradient that turns its part of the Jacobian negative;
#: budgeting the pair together halved the amplitude for nothing.
#: :func:`fold_free` measures what is actually left.
RIPPLE_SLOPE = 0.75


# ---------------------------------------------------------------------------
# Coverage: a rectangle of alpha, top row first.
# ---------------------------------------------------------------------------

class Coverage:
    """A letter as a rectangle of coverage, one byte a pixel.

    Row-major, **top row first**, which is the order the warp reads and
    the opposite of the order pyglet hands back. The flip happens once,
    where a Coverage is built from or turned into an image, rather than
    everywhere a pixel is touched.
    """

    __slots__ = ('width', 'height', 'alpha')

    def __init__(self, width: int, height: int,
                 alpha: Optional[bytearray] = None) -> None:
        self.width = int(width)
        self.height = int(height)
        if alpha is None:
            alpha = bytearray(self.width * self.height)
        if len(alpha) != self.width * self.height:
            raise ValueError('alpha is %d bytes, not %d'
                             % (len(alpha), self.width * self.height))
        self.alpha = alpha

    def at(self, x: int, y: int) -> int:
        """Coverage at an integer pixel; 0 outside the rectangle."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.alpha[y * self.width + x]
        return 0

    def sample(self, x: float, y: float) -> int:
        """Coverage at a fractional pixel, bilinear, 0 outside.

        Sampling off the edge as empty rather than as the edge pixel is
        what lets a warp move the letter partly out of frame without
        smearing its last row across everything beyond it.
        """
        left = math.floor(x)
        top = math.floor(y)
        fx = x - left
        fy = y - top
        left, top = int(left), int(top)
        one = self.at(left, top)
        two = self.at(left + 1, top)
        three = self.at(left, top + 1)
        four = self.at(left + 1, top + 1)
        upper = one + (two - one) * fx
        lower = three + (four - three) * fx
        return int(upper + (lower - upper) * fy)

    def ink(self) -> int:
        """Pixels at or above :data:`INK`."""
        return sum(1 for value in self.alpha if value >= INK)

    def weight(self) -> int:
        """Total coverage, which is ink measured without a threshold."""
        return sum(self.alpha)

    def bounds(self) -> Optional[Tuple[int, int, int, int]]:
        """The ink's bounding box as ``(x0, y0, x1, y1)``, or None.

        The box is half-open on the far corner, so an empty rectangle
        is None rather than a zero-sized box that arithmetic would
        happily divide by.
        """
        left, top = self.width, self.height
        right, bottom = 0, 0
        for y in range(self.height):
            base = y * self.width
            row = self.alpha[base:base + self.width]
            for x in range(self.width):
                if row[x] >= INK:
                    if x < left:
                        left = x
                    if x >= right:
                        right = x + 1
                    if y < top:
                        top = y
                    if y >= bottom:
                        bottom = y + 1
        if right <= left or bottom <= top:
            return None
        return left, top, right, bottom


# ---------------------------------------------------------------------------
# A 3x3 homography, as nine numbers.
# ---------------------------------------------------------------------------

Mat3 = Tuple[float, float, float, float, float, float, float, float, float]

IDENTITY: Mat3 = (1., 0., 0., 0., 1., 0., 0., 0., 1.)


def mat_mul(a: Mat3, b: Mat3) -> Mat3:
    """Matrix product, row-major."""
    out = []
    for row in range(3):
        for col in range(3):
            out.append(a[row * 3] * b[col]
                       + a[row * 3 + 1] * b[col + 3]
                       + a[row * 3 + 2] * b[col + 6])
    return tuple(out)  # type: ignore[return-value]


def mat_apply(m: Mat3, x: float, y: float) -> Tuple[float, float]:
    """Send a point through *m*, dividing by the projective row."""
    w = m[6] * x + m[7] * y + m[8]
    if abs(w) < 1e-12:
        w = 1e-12 if w >= 0 else -1e-12
    return ((m[0] * x + m[1] * y + m[2]) / w,
            (m[3] * x + m[4] * y + m[5]) / w)


def mat_inverse(m: Mat3) -> Mat3:
    """The inverse of *m*, by cofactors.

    Raises :class:`ValueError` on a singular matrix rather than
    returning something enormous, because a singular warp is a bug in
    whatever sampled it and a silent one would show up much later as a
    letter that is a single smeared row.
    """
    a, b, c, d, e, f, g, h, i = m
    one = e * i - f * h
    two = f * g - d * i
    three = d * h - e * g
    det = a * one + b * two + c * three
    if abs(det) < 1e-12:
        raise ValueError('singular warp')
    return (one / det, (c * h - b * i) / det, (b * f - c * e) / det,
            two / det, (a * i - c * g) / det, (c * d - a * f) / det,
            three / det, (b * g - a * h) / det, (a * e - b * d) / det)


def _about_centre(m: Mat3) -> Mat3:
    """*m* applied about ``(0.5, 0.5)`` instead of about the origin."""
    out = (1., 0., 0.5, 0., 1., 0.5, 0., 0., 1.)
    back = (1., 0., -0.5, 0., 1., -0.5, 0., 0., 1.)
    return mat_mul(out, mat_mul(m, back))


def homography(stretch_x: float = 1.0, stretch_y: float = 1.0,
               shear: float = 0.0, turn: float = 0.0,
               tilt_x: float = 0.0, tilt_y: float = 0.0) -> Mat3:
    """The affine-plus-perspective part of a warp, about the centre.

    *turn* is in radians and *shear* is the amount ``x`` moves per unit
    of ``y``. The two tilts are the projective row: they are what makes
    a letter look photographed from an angle rather than scaled, and
    they are the only part of this that is not affine.
    """
    scale = (stretch_x, 0., 0., 0., stretch_y, 0., 0., 0., 1.)
    slant = (1., shear, 0., 0., 1., 0., 0., 0., 1.)
    cos, sin = math.cos(turn), math.sin(turn)
    spin = (cos, -sin, 0., sin, cos, 0., 0., 0., 1.)
    lean = (1., 0., 0., 0., 1., 0., tilt_x, tilt_y, 1.)
    return _about_centre(mat_mul(lean, mat_mul(spin, mat_mul(slant, scale))))


# ---------------------------------------------------------------------------
# The warp.
# ---------------------------------------------------------------------------

class Wave(NamedTuple):
    """One term of the elastic deformation.

    A sum of a few of these is a smooth, seamless, band-limited
    displacement field that needs no grid to interpolate and no blur to
    smooth — which matters here only because it means the field can be
    evaluated exactly at any point, so nothing about the deformation
    depends on the resolution it is sampled at.
    """

    amp: float          #: displacement, in unit-square units
    across: float       #: cycles along u
    down: float         #: cycles along v
    phase: float        #: 0..1
    axis: int           #: 0 displaces u, 1 displaces v

    def at(self, u: float, v: float) -> float:
        return self.amp * math.sin(TAU * (self.across * u
                                          + self.down * v + self.phase))

    @property
    def slope(self) -> float:
        """The steepest the term can get, which is what folds a map."""
        return abs(self.amp) * TAU * max(abs(self.across), abs(self.down))


class Warp(NamedTuple):
    """Where each point of the drawn letter came from in the original.

    Stored as the map from *destination* to *source*, because that is
    the direction a resampler asks in: every output pixel wants to know
    one source point, and going the other way would leave holes.

    The ripple is applied in destination coordinates and the matrix
    after it. That order is a choice and not a neutral one — it means
    the perspective divide does not stretch the ripple, so a rippled
    letter tilted away from the reader keeps its ripple's proportions.
    """

    inverse: Mat3
    ripple: Tuple[Wave, ...] = ()

    @classmethod
    def of(cls, forward: Mat3, ripple: Sequence[Wave] = ()) -> 'Warp':
        return cls(mat_inverse(forward), tuple(ripple))

    def source(self, u: float, v: float) -> Tuple[float, float]:
        """The point of the source that lands at ``(u, v)``."""
        for wave in self.ripple:
            shift = wave.at(u, v)
            if wave.axis:
                v += shift
            else:
                u += shift
        return mat_apply(self.inverse, u, v)

    def slope(self, axis: int) -> float:
        """The ripple's steepest total on one axis.

        Per axis rather than in total because that is what the budget
        in :data:`RIPPLE_SLOPE` bounds and what the fold depends on;
        a single number over both would be neither.
        """
        return sum(wave.slope for wave in self.ripple if wave.axis == axis)


def fold_free(warp: Warp, steps: int = 24) -> float:
    """The smallest Jacobian determinant of *warp* over the unit square.

    A map that folds sends two different places to the same place, and
    a letter put through one is not a rearranged letter any more — it
    has had a piece of itself pasted back over another piece. Positive
    everywhere means it did not.

    Returns the determinant rather than a yes or no, so a test can say
    how much room was left rather than only that there was some.
    """
    worst = None
    span = 1.0 / steps
    for row in range(steps + 1):
        for col in range(steps + 1):
            u, v = col * span, row * span
            here = warp.source(u, v)
            right = warp.source(u + span * 0.5, v)
            down = warp.source(u, v + span * 0.5)
            dxdu = (right[0] - here[0]) / (span * 0.5)
            dydu = (right[1] - here[1]) / (span * 0.5)
            dxdv = (down[0] - here[0]) / (span * 0.5)
            dydv = (down[1] - here[1]) / (span * 0.5)
            det = dxdu * dydv - dxdv * dydu
            if worst is None or det < worst:
                worst = det
    return 0.0 if worst is None else worst


# ---------------------------------------------------------------------------
# The rest of the appearance: ink, dirt, and what is in the way.
# ---------------------------------------------------------------------------

class Bar(NamedTuple):
    """A rectangle of the stamp that something is in front of."""

    left: float
    top: float
    width: float
    height: float


class Distortion(NamedTuple):
    """One dealt appearance: everything but which letter it is."""

    warp: Warp
    thickness: float                 #: source pixels to grow (+) or eat (-)
    speckle: float                   #: share of pixels flipped
    bars: Tuple[Bar, ...] = ()
    contrast: float = 1.0            #: 1.0 full ink, 0.0 invisible


class Grade(NamedTuple):
    """One rung: the widest each knob is allowed to be dealt."""

    name: str
    stretch: float      #: 0.2 means 0.8x to 1.2x, per axis
    shear: float
    turn: float         #: degrees
    tilt: float
    ripple: float       #: share of :data:`RIPPLE_SLOPE` to spend
    waves: int
    thickness: float    #: source pixels, either way
    speckle: float
    occlusion: float    #: share of the stamp's area put behind bars
    contrast: float     #: the lowest the ink may fall to


GRADES: Tuple[Grade, ...] = (
    #     name                 stretch shear  turn  tilt ripple waves thick speckle occl contrast
    Grade('a clean page',         0.06, 0.02,  2.0, 0.00, 0.00, 0, 0.0, 0.000, 0.00, 1.00),
    Grade('a hand that wavers',   0.12, 0.06,  5.0, 0.03, 0.10, 1, 0.3, 0.005, 0.00, 1.00),
    Grade('a slight lean',        0.20, 0.14,  9.0, 0.07, 0.18, 2, 0.5, 0.010, 0.00, 0.95),
    Grade('off the flat',         0.28, 0.22, 13.0, 0.14, 0.26, 2, 0.7, 0.020, 0.04, 0.90),
    Grade('thick and thin',       0.34, 0.28, 16.0, 0.18, 0.34, 2, 1.3, 0.030, 0.08, 0.85),
    Grade('a rippled page',       0.40, 0.34, 19.0, 0.22, 0.52, 3, 1.5, 0.045, 0.12, 0.80),
    Grade('through the blinds',   0.44, 0.38, 21.0, 0.25, 0.62, 3, 1.7, 0.055, 0.20, 0.75),
    Grade('a bad photocopy',      0.48, 0.42, 23.0, 0.28, 0.72, 4, 2.0, 0.080, 0.26, 0.70),
    Grade('a dirty window',       0.52, 0.46, 25.0, 0.31, 0.84, 4, 2.2, 0.110, 0.32, 0.65),
    Grade('most of it is gone',   0.56, 0.50, 27.0, 0.34, 1.00, 5, 2.5, 0.150, 0.40, 0.60))


def grade_of(rung: int) -> Grade:
    """The rung's grade, counted from one and clamped to the ladder."""
    return GRADES[max(0, min(len(GRADES) - 1, int(rung) - 1))]


def _spread(rng: random.Random, width: float) -> float:
    """A number in ``[-width, width]``, weighted toward the edges.

    Uniform sampling of every knob at once puts almost every deal near
    the middle of the box, because the middle is where most of the box
    is. Pushing the mass outward is what makes a rung's *name* describe
    what a deal from it usually looks like.
    """
    if width <= 0.0:
        return 0.0
    return math.copysign(width * math.sqrt(rng.random()), rng.random() - 0.5)


def deal(rung: int, rng: random.Random) -> Distortion:
    """Sample one appearance from a rung.

    Every knob is drawn independently, so the rung is a box rather than
    a curve through the box and two deals from the same rung need not
    look alike in any particular way.
    """
    grade = grade_of(rung)
    forward = homography(
        stretch_x=1.0 + _spread(rng, grade.stretch),
        stretch_y=1.0 + _spread(rng, grade.stretch),
        shear=_spread(rng, grade.shear),
        turn=math.radians(_spread(rng, grade.turn)),
        tilt_x=_spread(rng, grade.tilt),
        tilt_y=_spread(rng, grade.tilt))

    waves: List[Wave] = []
    budget = RIPPLE_SLOPE * grade.ripple
    for axis in (0, 1):
        # Alternating, so an odd wave count leans on u. Each axis gets
        # the whole budget: see :data:`RIPPLE_SLOPE`.
        mine = [index for index in range(grade.waves) if index % 2 == axis]
        for place, _index in enumerate(mine):
            # The last wave on an axis gets what is left rather than
            # its share, so the budget is spent rather than respected.
            spent = sum(wave.slope for wave in waves if wave.axis == axis)
            share = (budget / len(mine) if place < len(mine) - 1
                     else budget - spent)
            across = rng.uniform(0.4, 1.4)
            down = rng.uniform(0.4, 1.4)
            steepest = TAU * max(across, down)
            waves.append(Wave(amp=share / steepest if steepest else 0.0,
                              across=across, down=down,
                              phase=rng.random(), axis=axis))

    bars: List[Bar] = []
    left_to_cover = grade.occlusion
    while left_to_cover > 0.01:
        # Bars, not blobs: something in front of a letter — a railing,
        # a window frame, the edge of the page — is usually straight,
        # and a straight edge is the case where a reader has to decide
        # whether a stroke continues behind it.
        thick = min(left_to_cover, rng.uniform(0.06, 0.22))
        if rng.random() < 0.5:
            bars.append(Bar(0.0, rng.random() * (1.0 - thick), 1.0, thick))
        else:
            bars.append(Bar(rng.random() * (1.0 - thick), 0.0, thick, 1.0))
        left_to_cover -= thick

    return Distortion(
        warp=Warp.of(forward, waves),
        thickness=_spread(rng, grade.thickness),
        speckle=rng.random() * grade.speckle,
        bars=tuple(bars),
        contrast=rng.uniform(grade.contrast, 1.0))


# ---------------------------------------------------------------------------
# Applying it.
# ---------------------------------------------------------------------------

def _disc(radius: float) -> Tuple[Tuple[int, int], ...]:
    """Integer offsets within *radius* of the origin."""
    reach = int(math.ceil(radius))
    return tuple((dx, dy)
                 for dy in range(-reach, reach + 1)
                 for dx in range(-reach, reach + 1)
                 if dx * dx + dy * dy <= radius * radius + 1e-9)


def thicken(cov: Coverage, radius: float) -> Coverage:
    """Grow the ink by *radius* pixels, or eat it if *radius* is negative.

    A dilation by a disc and an erosion by the same disc, which is what
    a heavier or lighter weight of the same typeface mostly is. It is
    not what it *entirely* is — a real bold face redraws the letter
    rather than fattening it, and this cannot invent that — so this
    knob should be read as wear and exposure rather than as weight.
    """
    if abs(radius) < 0.5:
        return Coverage(cov.width, cov.height, bytearray(cov.alpha))
    disc = _disc(abs(radius))
    grow = radius > 0
    out = bytearray(cov.width * cov.height)
    width, height = cov.width, cov.height
    for y in range(height):
        base = y * width
        for x in range(width):
            best = 0 if grow else 255
            for dx, dy in disc:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    value = cov.alpha[ny * width + nx]
                elif grow:
                    continue
                else:
                    value = 0
                if grow:
                    if value > best:
                        best = value
                        if best == 255:
                            break
                else:
                    if value < best:
                        best = value
                        if best == 0:
                            break
            out[base + x] = best
    return Coverage(width, height, out)


def _fit(cov: Coverage, margin: float) -> Optional[Tuple[float, float, float]]:
    """Where the unit square sits on *cov*: ``(x0, y0, span)``.

    The letter's own ink box is centred in the square with *margin*
    left over, and the box is squared off first so the letter keeps its
    proportions. An ``I`` and an ``M`` therefore arrive the same height
    rather than the same width, which is what a reader expects and what
    keeps aspect ratio out of the answer.
    """
    box = cov.bounds()
    if box is None:
        return None
    left, top, right, bottom = box
    span = max(right - left, bottom - top) / max(1e-6, 1.0 - 2.0 * margin)
    centre_x = (left + right) / 2.0
    centre_y = (top + bottom) / 2.0
    return centre_x - span / 2.0, centre_y - span / 2.0, span


def stamp(cov: Coverage, dist: Distortion, size: int,
          rng: Optional[random.Random] = None,
          margin: float = 0.12) -> Coverage:
    """Put a letter through one dealt appearance.

    Order matters, and this is the order a real page would apply them:
    the typeface is worn or fattened first, because that happened to
    the printing; then the sheet is warped, because that happened to
    the paper; then the sheet is dirtied and something is put in front
    of it, because those happened last and to the picture rather than
    to the letter.

    Doing the thickening after the warp instead would grow the ink by a
    disc in *screen* pixels, so a letter tilted away from the reader
    would come back with its far end proportionally fatter — which is
    not wear, it is a mistake that looks like one.
    """
    rng = rng or random.Random(0)
    worn = thicken(cov, dist.thickness)
    placed = _fit(worn, margin)
    out = Coverage(size, size)
    if placed is None:
        return out
    origin_x, origin_y, span = placed
    step = 1.0 / size
    alpha = out.alpha
    for row in range(size):
        v = (row + 0.5) * step
        base = row * size
        for col in range(size):
            u, source_v = dist.warp.source((col + 0.5) * step, v)
            alpha[base + col] = worn.sample(origin_x + u * span,
                                            origin_y + source_v * span)

    if dist.speckle > 0.0:
        for index in range(size * size):
            if rng.random() < dist.speckle:
                alpha[index] = 0 if alpha[index] >= INK else 255

    for bar in dist.bars:
        x0 = max(0, int(bar.left * size))
        x1 = min(size, int(math.ceil((bar.left + bar.width) * size)))
        y0 = max(0, int(bar.top * size))
        y1 = min(size, int(math.ceil((bar.top + bar.height) * size)))
        for row in range(y0, y1):
            base = row * size
            for col in range(x0, x1):
                alpha[base + col] = 0

    if dist.contrast < 1.0:
        scale = max(0.0, min(1.0, dist.contrast))
        for index in range(size * size):
            value = alpha[index]
            if value:
                alpha[index] = int(value * scale)
    return out


# ---------------------------------------------------------------------------
# The measurement: does it still say what it said?
# ---------------------------------------------------------------------------

#: Share of the ink allowed to fall outside the box a signature is
#: measured in, at each end of each axis. Zero was the first thing
#: tried and it made the measurement worthless: a single speck of
#: noise dropped in a corner is enough to double the box, which moves
#: every cell boundary, so a rung's *speckle* knob was being scored as
#: if it had destroyed the letter when all it had done was move the
#: ruler. Trimming two per cent an end costs a clean letter nothing —
#: a capital has no two per cent of its ink out at its extreme rows —
#: and leaves the box where the letter is.
TRIM = 0.02


def _mass_box(cov: Coverage, trim: float) -> Optional[Tuple[int, int, int, int]]:
    """The box holding all but *trim* of the ink at each end of each axis."""
    columns = [0] * cov.width
    rows = [0] * cov.height
    total = 0
    for y in range(cov.height):
        base = y * cov.width
        for x in range(cov.width):
            if cov.alpha[base + x] >= INK:
                columns[x] += 1
                rows[y] += 1
                total += 1
    if not total:
        return None
    want = total * trim

    def span(profile: List[int]) -> Tuple[int, int]:
        seen = 0
        low = 0
        for index, count in enumerate(profile):
            seen += count
            if seen > want:
                low = index
                break
        seen = 0
        high = len(profile)
        for index in range(len(profile) - 1, -1, -1):
            seen += profile[index]
            if seen > want:
                high = index + 1
                break
        return low, max(low + 1, high)

    left, right = span(columns)
    top, bottom = span(rows)
    return left, top, right, bottom


def signature(cov: Coverage, cells: int = CELLS,
              trim: float = TRIM) -> Tuple[float, ...]:
    """Ink per cell of a grid over the letter's own ink box.

    Measuring within the ink box rather than the frame is what makes
    this blind to where the letter ended up and how big it is, which is
    deliberate: position and scale are knobs this module turns, and a
    recogniser that they alone could beat would measure the knobs
    rather than the damage. See :data:`TRIM` for why the box is not
    simply :meth:`Coverage.bounds`.

    An empty coverage gives all zeros, which every letter is equally
    far from — so a stamp with nothing left in it is a wrong answer
    rather than a crash, and the ladder's bottom rungs need that.
    """
    box = _mass_box(cov, trim)
    out = [0.0] * (cells * cells)
    if box is None:
        return tuple(out)
    left, top, right, bottom = box
    wide = (right - left) / float(cells)
    tall = (bottom - top) / float(cells)
    for y in range(top, bottom):
        base = y * cov.width
        cell_y = min(cells - 1, int((y - top) / tall))
        row_base = cell_y * cells
        for x in range(left, right):
            if cov.alpha[base + x] >= INK:
                out[row_base + min(cells - 1, int((x - left) / wide))] += 1.0
    total = sum(out)
    if total <= 0.0:
        return tuple(out)
    return tuple(value / total for value in out)


def distance(one: Sequence[float], two: Sequence[float]) -> float:
    """L1 between two signatures."""
    return sum(abs(a - b) for a, b in zip(one, two))


def recognise(sig: Sequence[float],
              templates: Dict[str, Sequence[Sequence[float]]]) -> str:
    """The letter whose nearest template is nearest to *sig*."""
    best_letter, best = '', None
    for letter, shapes in templates.items():
        for shape in shapes:
            gap = distance(sig, shape)
            if best is None or gap < best:
                best, best_letter = gap, letter
    return best_letter


# ---------------------------------------------------------------------------
# Typefaces on this machine, grouped by family.
# ---------------------------------------------------------------------------

#: Where a platform keeps its fonts. Missing directories are skipped,
#: so this is a list of places to look rather than a claim about any
#: one machine.
FONT_DIRS: Tuple[str, ...] = (
    '/System/Library/Fonts',
    '/System/Library/Fonts/Supplemental',
    '/Library/Fonts',
    os.path.expanduser('~/Library/Fonts'),
    '/usr/share/fonts',
    '/usr/local/share/fonts',
    os.path.expanduser('~/.local/share/fonts'),
    os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts'),
)

_SUFFIXES = ('.ttf', '.otf', '.ttc', '.otc')


def _tables(data: bytes, base: int = 0) -> Dict[bytes, Tuple[int, int]]:
    """The table directory of the font whose header starts at *base*."""
    count = struct.unpack('>H', data[base + 4:base + 6])[0]
    found: Dict[bytes, Tuple[int, int]] = {}
    for index in range(count):
        head = base + 12 + index * 16
        tag, _checksum, offset, length = struct.unpack(
            '>4sIII', data[head:head + 16])
        found[tag] = (offset, length)
    return found


def _table_names(data: bytes, base: int) -> Dict[int, str]:
    """The ``name`` table of the font whose header starts at *base*."""
    tables = _tables(data, base)
    if b'name' not in tables:
        return {}
    offset, _length = tables[b'name']
    _format, records, strings = struct.unpack(
        '>HHH', data[offset:offset + 6])
    found: Dict[int, str] = {}
    for index in range(records):
        head = offset + 6 + index * 12
        platform, _encoding, _language, name_id, length, at = struct.unpack(
            '>HHHHHH', data[head:head + 12])
        raw = data[offset + strings + at:offset + strings + at + length]
        try:
            text = raw.decode('utf-16-be' if platform in (0, 3)
                              else 'mac-roman')
        except (UnicodeDecodeError, LookupError):
            continue
        found.setdefault(name_id, text.strip())
    return found


def face_name(path: str) -> Optional[Tuple[str, str]]:
    """``(family, style)`` read out of the font file itself.

    Read from the file rather than taken from its name because the
    filename is not the family: ``Georgia Bold Italic.ttf`` and
    ``Georgia.ttf`` are one typeface, and splitting on filenames would
    put them on opposite sides of a held-out test and call the result
    generalisation.

    Returns None for anything unreadable, including collections, which
    hold several families in one file and cannot be attributed to one.
    """
    try:
        with open(path, 'rb') as handle:
            data = handle.read()
    except OSError:
        return None
    if len(data) < 12:
        return None
    if data[:4] == b'ttcf':
        return None
    try:
        names = _table_names(data, 0)
    except (struct.error, IndexError):
        return None
    family = names.get(16) or names.get(1)
    if not family:
        return None
    return family, names.get(2) or 'Regular'


def _ranges(data: bytes, at: int) -> List[Tuple[int, int]]:
    """The character ranges of one ``cmap`` subtable at *at*."""
    kind = struct.unpack('>H', data[at:at + 2])[0]
    out: List[Tuple[int, int]] = []
    if kind == 4:
        pairs = struct.unpack('>H', data[at + 6:at + 8])[0] // 2
        ends = at + 14
        starts = ends + pairs * 2 + 2
        for index in range(pairs):
            last = struct.unpack('>H', data[ends + index * 2:
                                            ends + index * 2 + 2])[0]
            first = struct.unpack('>H', data[starts + index * 2:
                                             starts + index * 2 + 2])[0]
            if first <= last and last != 0xFFFF:
                out.append((first, last))
    elif kind == 12:
        groups = struct.unpack('>I', data[at + 12:at + 16])[0]
        for index in range(min(groups, 20000)):
            head = at + 16 + index * 12
            first, last, _glyph = struct.unpack('>III', data[head:head + 12])
            out.append((first, last))
    return out


def covered(path: str) -> Optional[List[Tuple[int, int]]]:
    """The character ranges *path* claims to draw, or None if unreadable.

    Read because pyglet will not tell you. Ask a font with no Latin in
    it for a capital A and the platform quietly substitutes one from
    somewhere else, and pyglet hands back a perfectly good letter — in
    a typeface that is not the one that was asked for.

    That is not a cosmetic problem here, it is the measurement's whole
    validity. Most of the several hundred families on a macOS install
    are Noto faces for scripts with no Latin at all, so a held-out
    "family" is very often the system's fallback wearing a held-out
    name, and every one of those is the *training* typeface being
    scored as if it were unseen. Filtering on this is what makes a
    held-out number mean what it says.

    Ranges rather than a set of codepoints, because a CJK font's set
    runs to tens of thousands of entries and nothing here needs them
    enumerated. Format 4 ranges are taken whole, so a range with a hole
    punched in it by ``idRangeOffset`` reads as covered — an
    over-claim, and the rare direction to be wrong in.
    """
    try:
        with open(path, 'rb') as handle:
            data = handle.read()
    except OSError:
        return None
    if len(data) < 12 or data[:4] == b'ttcf':
        return None
    try:
        tables = _tables(data)
        if b'cmap' not in tables:
            return None
        base = tables[b'cmap'][0]
        count = struct.unpack('>H', data[base + 2:base + 4])[0]
        best: List[Tuple[int, int]] = []
        for index in range(count):
            head = base + 4 + index * 8
            platform, encoding, offset = struct.unpack(
                '>HHI', data[head:head + 8])
            if platform not in (0, 3):
                continue
            if platform == 3 and encoding not in (1, 10):
                continue
            found = _ranges(data, base + offset)
            if len(found) > len(best):
                best = found
        return best or None
    except (struct.error, IndexError):
        return None


def draws(ranges: Sequence[Tuple[int, int]], text: str) -> bool:
    """Whether *ranges* covers every character of *text*."""
    return all(any(first <= ord(ch) <= last for first, last in ranges)
               for ch in text)


def families(dirs: Optional[Iterable[str]] = None,
             must_draw: str = '') -> Dict[str, Tuple[str, ...]]:
    """Every readable font on this machine, grouped by family name.

    The value is the family's files, sorted, so a caller that wants one
    file a family gets the same one every run.

    *must_draw* keeps only files whose own ``cmap`` covers every
    character in it — see :func:`covered` for why a caller measuring
    anything should pass the alphabet it is going to ask for.
    """
    found: Dict[str, List[str]] = {}
    for folder in (FONT_DIRS if dirs is None else dirs):
        if not os.path.isdir(folder):
            continue
        for entry in sorted(os.listdir(folder)):
            if not entry.lower().endswith(_SUFFIXES):
                continue
            path = os.path.join(folder, entry)
            named = face_name(path)
            if named is None:
                continue
            if must_draw:
                ranges = covered(path)
                if ranges is None or not draws(ranges, must_draw):
                    continue
            found.setdefault(named[0], []).append(path)
    return {family: tuple(paths) for family, paths in sorted(found.items())}


def split(names: Iterable[str], seed: int = 0,
          shares: Sequence[float] = (0.7, 0.15, 0.15)
          ) -> Tuple[Tuple[str, ...], ...]:
    """Divide family names into parts that share no family.

    Whole families, so a face cannot appear in training under one style
    and in testing under another. Deterministic from *seed*, so a run
    that reports a held-out number can be repeated exactly.

    Rounding goes to the last part, which is the test set. Given three
    families and a seventy-fifteen-fifteen split that leaves the test
    part with everything the other two did not round up to — a real
    hazard of tiny pools, and a caller with a tiny pool should be
    checking the parts it got rather than trusting the shares.
    """
    pool = sorted(set(names))
    random.Random(seed).shuffle(pool)
    parts: List[Tuple[str, ...]] = []
    taken = 0
    for share in list(shares)[:-1]:
        size = int(len(pool) * share)
        parts.append(tuple(pool[taken:taken + size]))
        taken += size
    parts.append(tuple(pool[taken:]))
    return tuple(parts)


def platform_dirs() -> Tuple[str, ...]:
    """The directories in :data:`FONT_DIRS` that exist here."""
    if sys.platform.startswith('darwin'):
        wanted = FONT_DIRS[:4]
    elif sys.platform.startswith('win'):
        wanted = FONT_DIRS[7:]
    else:
        wanted = FONT_DIRS[4:7]
    return tuple(folder for folder in wanted if os.path.isdir(folder))


__all__ = ['CELLS', 'FONT_DIRS', 'GRADES', 'IDENTITY', 'INK', 'RIPPLE_SLOPE',
           'TAU', 'Bar', 'Coverage', 'Distortion', 'Grade', 'Mat3', 'Warp',
           'Wave', 'deal', 'distance', 'face_name', 'families', 'fold_free',
           'grade_of', 'homography', 'mat_apply', 'mat_inverse', 'mat_mul',
           'covered', 'draws', 'platform_dirs', 'recognise', 'signature', 'split',
           'stamp', 'TRIM',
           'thicken']
