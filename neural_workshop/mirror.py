# -*- coding: utf-8 -*-
"""Same or Mirror?: is that the same figure turned, or its mirror image?

The figures are Shepard and Metzler's: cubes face to face in straight
arms, each arm at a right angle to the last, built so that no figure is
its own mirror image -- turning can never make one into the other, and
only a turn done in the head tells them apart. Shepard and Metzler found
the time to answer grows in a straight line with the angle between the
two views; the ladder grows that angle first.

* rungs 1-6: two figures; the second turned about the **vertical**, by
  up to 40 degrees at rung one and up to a half turn by rung six;
* rungs 7-12: turned about **any** axis, up to 60 degrees at seven and a
  half turn from ten;
* from rung 13 a figure and a row of others: **which is the same
  figure?** -- three choices, the rest mirror images; four from 16, one
  of them the figure with one end cube moved; five from 21, every wrong
  choice one cube away from the figure or from its mirror;
* more cubes as the ladder climbs, seven to eleven; and from rung 25 no
  shading, so faces read only by their edges.

A choice is right or wrong; there is no par.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import NamedTuple, Optional, Tuple

from . import space
from .i18n import _

SAME, MIRROR = 0, 1


class Grade(NamedTuple):
    rung: int
    cubes: int
    any_axis: bool
    #: The largest turn between views, degrees.
    most: float
    #: 0: a pair, Same or Mirror; else how many to choose among.
    options: int
    #: Wrong options one cube away from the figure or its mirror.
    nudged: int
    lit: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 7:
        any_axis, most = False, min(180.0, 40.0 + 28.0 * (r - 1))
    elif r < 10:
        any_axis, most = True, 60.0 + 40.0 * (r - 7)
    else:
        any_axis, most = True, 180.0
    if r < 13:
        options, nudged = 0, 0
    elif r < 16:
        options, nudged = 3, 0
    elif r < 21:
        options, nudged = 4, 1
    else:
        options, nudged = 5, 4
    return Grade(rung=r, cubes=min(11, 7 + max(0, r - 6) // 5),
                 any_axis=any_axis, most=most, options=options,
                 nudged=nudged, lit=r < 25)


class Figure(NamedTuple):
    cubes: Tuple[space.Cube, ...]
    turn: space.Mat


class Puzzle(NamedTuple):
    rung: int
    reference: Figure
    #: The figure(s) to judge: one for a pair, a row for a pick.
    others: Tuple[Figure, ...]
    choices: Tuple[str, ...]
    answer: int
    #: Degrees from the reference to each of *others*.
    angles: Tuple[float, ...]
    lit: bool
    question: str


#: A view of every figure from a little above and to the side.
EYE = (7.0, 5.5, 11.0)


def camera() -> space.Camera:
    return space.Camera(EYE, (0.0, 0.0, 0.0))


def _turned(draw: random.Random, base: space.Mat, level: Grade
            ) -> Tuple[space.Mat, float]:
    """A view turned from *base* by between a third of the rung's most
    and all of it (at least 15 degrees)."""
    most = math.radians(level.most)
    angle = draw.uniform(max(math.radians(15), most / 3.0), most)
    axis = space.random_axis(draw) if level.any_axis else (0.0, 1.0, 0.0)
    if draw.random() < 0.5:
        angle = -angle
    turn = space.compose(space.rotation(axis, angle), base)
    return turn, math.degrees(space.angle_between(base, turn))


def _base(draw: random.Random) -> space.Mat:
    grid = draw.choice(space.GRID_TURNS)
    grid = tuple(tuple(float(v) for v in row) for row in grid)
    return space.compose(space.rotation((0.0, 1.0, 0.0),
                                        draw.uniform(-0.4, 0.4)), grid)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    figure = space.arms(draw, level.cubes)
    mirror = space.mirrored(figure)
    base = _base(draw)
    reference = Figure(figure, base)
    if not level.options:
        answer = draw.choice((SAME, MIRROR))
        turn, angle = _turned(draw, base, level)
        other = Figure(figure if answer == SAME else mirror, turn)
        return Puzzle(level.rung, reference, (other,),
                      (_('Same'), _('Mirror')), answer, (angle,),
                      level.lit,
                      _('The same figure turned, or its mirror image?'))
    wrong = []
    for k in range(level.options - 1):
        if k < level.nudged:
            source = figure if k % 2 == 0 else mirror
            wrong.append(space.nudged(draw, source, avoid=wrong))
        else:
            wrong.append(mirror)
    answer = draw.randrange(level.options)
    shapes = wrong[:answer] + [figure] + wrong[answer:]
    others, angles = [], []
    for cubes in shapes:
        turn, angle = _turned(draw, base, level)
        others.append(Figure(tuple(cubes), turn))
        angles.append(angle)
    return Puzzle(level.rung, reference, tuple(others),
                  tuple(str(i + 1) for i in range(level.options)), answer,
                  tuple(angles), level.lit,
                  _('Which of the row is the same figure as the one on top?'))


def faces(figure: Figure, lit: bool = True,
          colour=(214, 176, 112)) -> list:
    out = space.cube_faces(figure.cubes, figure.turn, colour)
    if not lit:
        out = [f._replace(lit=False) for f in out]
    return out


def correct(puzzle: Puzzle, choice: int) -> bool:
    return choice == puzzle.answer


def truth(puzzle: Puzzle) -> bool:
    """Checked from the cubes, not from how the deal was made: is
    the answer's figure the reference turned, and no other?"""
    ref = puzzle.reference.cubes
    if len(puzzle.others) == 1:
        same = space.same_shape(ref, puzzle.others[0].cubes)
        return same == (puzzle.answer == SAME)
    hits = [i for i, f in enumerate(puzzle.others)
            if space.same_shape(ref, f.cubes)]
    return hits == [puzzle.answer]
