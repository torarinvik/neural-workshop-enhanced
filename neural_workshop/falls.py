# -*- coding: utf-8 -*-
"""Will It Fall?: a still picture of a physical scene, and what happens next.

Every question is about plain rigid-body physics with exact answers, so
how hard a question is can be set to the millimetre:

* **stand** -- a tower of blocks: does it stand or fall? A block stays
  up while the centre of mass of it and everything on it lies over the
  part of the block below that it rests on;
* **lever** (from rung 4) -- boxes piled on a plank across a pivot:
  does it tip left, tip right or stay level? From rung 10 the pivot is
  off the plank's middle, so the plank's own weight counts too;
* **land** (from rung 8) -- a ball rolls off a table; dots show where it
  was at equal moments as it left the edge. Which bin on the floor does
  it land in?
* **first** (from rung 12) -- a tower again: which block is the first
  to topple, or does nothing fall?
* **bounce** (from rung 16) -- the ball again, but which bin does it
  land in the *second* time? How bouncy the ball is is never shown; it
  is the same every time, and can be learned;

and through the ladder the deciding margin shrinks -- from a tower
leaning a third of a block past its edge to one leaning two hundredths
-- towers grow, the bins narrow and, past rung 20, the trail of dots
gets shorter.

A choice is right or wrong; there is no par.

Units are metres and seconds in a world 12 m wide, the floor at y=0.
Nothing here imports pyglet.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

G = 9.8
#: How much of its speed down the ball keeps at a bounce.
BOUNCE = 0.6
WORLD_W, WORLD_H = 12.0, 7.0
MOST_CHOICES = 8
LETTERS = 'ABCDEFGH'


class Grade(NamedTuple):
    rung: int
    kinds: Tuple[str, ...]
    blocks: int
    #: How far, as a share of the support, the deciding centre of mass
    #: sits from the edge it is judged against.
    margin: float
    bins: int
    dots: int
    offset_pivot: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    kinds = ['stand']
    if r >= 4:
        kinds.append('lever')
    if r >= 8:
        kinds.append('land')
    if r >= 12:
        kinds.append('first')
    if r >= 16:
        kinds.append('bounce')
    return Grade(
        rung=r,
        kinds=tuple(kinds),
        blocks=min(7, 2 + r // 3),
        margin=max(0.02, 0.32 - 0.015 * (r - 1)),
        bins=min(MOST_CHOICES, 3 + (r - 8) // 3) if r >= 8 else 3,
        dots=5 if r <= 20 else max(2, 5 - (r - 18) // 3),
        offset_pivot=r >= 10,
    )


class Block(NamedTuple):
    x: float            # left
    y: float            # bottom
    w: float
    h: float

    @property
    def mass(self) -> float:
        return self.w * self.h

    @property
    def middle(self) -> float:
        return self.x + self.w / 2


class Puzzle(NamedTuple):
    kind: str
    question: str
    choices: Tuple[str, ...]
    answer: int
    #: What to draw: blocks; or a lever; or a ball's flight.
    blocks: Tuple[Block, ...] = ()
    lever: Optional[Tuple] = None
    flight: Optional[Tuple] = None


# --- towers --------------------------------------------------------------

def lean(blocks: List[Block], level: int) -> float:
    """Where the centre of mass of block *level* and all above it sits
    over its support, as a signed share of the support's width from its
    nearest edge: positive inside, negative past the edge."""
    above = blocks[level:]
    mass = sum(b.mass for b in above)
    com = sum(b.middle * b.mass for b in above) / mass
    under = blocks[level - 1]
    lo = max(under.x, blocks[level].x)
    hi = min(under.x + under.w, blocks[level].x + blocks[level].w)
    width = hi - lo
    return min(com - lo, hi - com) / width


def first_to_fall(blocks: List[Block]) -> Optional[int]:
    """The lowest block that topples, or None if the tower stands."""
    for level in range(1, len(blocks)):
        if lean(blocks, level) < 0:
            return level
    return None


def _tower(level: Grade, draw: random.Random, falls: Optional[bool],
           first: Optional[int] = None) -> Optional[List[Block]]:
    count = draw.randint(max(2, level.blocks - 2), level.blocks)
    if first is not None:
        count = max(count, first + 1)
    height = min(1.0, 5.5 / count)
    blocks = [Block(WORLD_W / 2 - 1.2, 0.0, 2.4, height)]
    for _n in range(1, count):
        under = blocks[-1]
        w = draw.uniform(0.8, 2.6)
        x = under.x + draw.uniform(-0.8 * w, under.w - 0.2 * w)
        blocks.append(Block(x, under.y + under.h, w, height))
    # Every level must be clearly in or clearly out -- no near misses
    # except at the margin the rung sets.
    for index in range(1, len(blocks)):
        if blocks[index].x + blocks[index].w <= blocks[index - 1].x \
                or blocks[index].x >= blocks[index - 1].x \
                + blocks[index - 1].w:
            return None
        if abs(lean(blocks, index)) < level.margin:
            return None
        if abs(lean(blocks, index)) > level.margin + 0.35:
            return None
    if not all(0.2 < b.x and b.x + b.w < WORLD_W - 0.2 for b in blocks):
        return None
    top = first_to_fall(blocks)
    if falls is not None and (top is not None) != falls:
        return None
    if first is not None and top != first:
        return None
    return blocks


def _stand(level: Grade, draw: random.Random) -> Optional[Puzzle]:
    falls = draw.random() < 0.5
    for _attempt in range(4000):
        blocks = _tower(level, draw, falls)
        if blocks:
            return Puzzle('stand', _('Does the tower stand or fall?'),
                          (_('It stands'), _('It falls')),
                          1 if falls else 0, tuple(blocks))
    return None


def _first(level: Grade, draw: random.Random) -> Optional[Puzzle]:
    count = level.blocks
    target = draw.choice([None] + list(range(1, count)))
    for _attempt in range(6000):
        blocks = _tower(level, draw, target is not None, target)
        if blocks:
            n = len(blocks)
            choices = tuple(_('%s falls first') % LETTERS[i]
                            for i in range(1, n)) + (_('Nothing falls'),)
            answer = n - 1 if target is None else target - 1
            return Puzzle('first', _('Which block is the first to topple?'),
                          choices, answer, tuple(blocks))
    return None


# --- the lever -----------------------------------------------------------

def _lever(level: Grade, draw: random.Random) -> Optional[Puzzle]:
    """A plank of length 10 on a pivot, piles of unit boxes at whole
    positions. Answer by the sign of the turning moment."""
    wanted = draw.randrange(3)
    for _attempt in range(4000):
        length, plank_mass = 10.0, 2.0
        pivot = draw.choice((-2, -1, 1, 2)) if level.offset_pivot else 0
        piles = {}
        for _pile in range(draw.randint(2, 2 + level.rung // 6)):
            at = draw.randint(-5, 5)
            if at == pivot:
                continue
            piles[at] = piles.get(at, 0) + draw.randint(1, 3)
        moment = sum(n * (at - pivot) for at, n in piles.items()) \
            + plank_mass * (0 - pivot)
        weight = sum(piles.values()) + plank_mass
        answer = 2 if moment == 0 else (0 if moment < 0 else 1)
        if answer != wanted:
            continue
        if moment and abs(moment) / (weight * 5.0) < level.margin * 0.4:
            continue
        return Puzzle('lever', _('Which way does the plank go?'),
                      (_('Tips left'), _('Tips right'), _('Stays level')),
                      answer, lever=(length, pivot, plank_mass,
                                     tuple(sorted(piles.items()))))
    return None


# --- the ball ------------------------------------------------------------

def landing(height: float, speed: float, edge: float,
            bounces: int) -> float:
    """Where a ball leaving a table edge level at *speed* lands after
    *bounces* bounces (0: the first time it touches the floor)."""
    fall = math.sqrt(2 * height / G)
    x = edge + speed * fall
    up = G * fall * BOUNCE
    for _bounce in range(bounces):
        x += speed * 2 * up / G
        up *= BOUNCE
    return x


def _flight(level: Grade, draw: random.Random, bounces: int
            ) -> Optional[Puzzle]:
    bins = level.bins
    index = draw.randrange(bins)
    for _attempt in range(3000):
        height = draw.uniform(1.2, 3.5)
        edge = draw.uniform(0.8, 3.0)
        lo, hi = edge + 0.4, WORLD_W - 0.2
        width = (hi - lo) / bins
        # Aim inside the chosen bin, no nearer its edges than the margin,
        # and find the speed that lands there.
        place = index + draw.uniform(level.margin, 1 - level.margin)
        x = lo + place * width
        per_speed = landing(height, 1.0, 0.0, bounces)
        speed = (x - edge) / per_speed
        if not 0.4 <= speed <= 12.0:
            continue
        dt = 0.09
        dots = tuple((edge + speed * k * dt,
                      height - 0.5 * G * (k * dt) ** 2)
                     for k in range(level.dots))
        return Puzzle(
            'bounce' if bounces else 'land',
            _('Where does the ball land the second time?') if bounces
            else _('Where does the ball land?'),
            tuple(_('Bin %d') % (i + 1) for i in range(bins)), index,
            flight=(height, edge, speed, lo, hi, dots, bounces))
    return None


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    newest = level.kinds[-1]
    for _attempt in range(50):
        kind = newest if draw.random() < 0.4 else draw.choice(level.kinds)
        if kind == 'stand':
            found = _stand(level, draw)
        elif kind == 'lever':
            found = _lever(level, draw)
        elif kind == 'first':
            found = _first(level, draw)
        elif kind == 'land':
            found = _flight(level, draw, 0)
        else:
            found = _flight(level, draw, 1)
        if found is not None:
            return found
    raise RuntimeError('no scene could be dealt for rung %d' % rung)
