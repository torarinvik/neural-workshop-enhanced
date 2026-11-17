# -*- coding: utf-8 -*-
"""Heavier: push the crates and say which is heaviest.

Crates that look alike stand in lanes. Push one, and it goes off as
fast as its mass and the floor under it let it; let go, and it slides
on until the floor stops it. Watching how each one gets going and how
it slows is the only way to tell them apart. Several boards make a
round, and every board must be answered right.

* rung 1: three crates, one of them three times as heavy as the others,
  the same floor under all of them;
* rungs 2-3: the masses closer -- twice, then half again;
* rungs 4-6: a different floor under every crate, so a crate can be
  slow to start because its floor grips, not because it is heavy:
  watch how it slows, too;
* rungs 7-9: four crates, and some boards ask which floor is the
  slipperiest instead;
* rungs 10-12: the crates come in different sizes, which say nothing
  of their mass;
* rungs 13 and up: the heaviest is heavier than the next by less and
  less, without end, and the push weakens.

For the agent boundary: ports 0-3 push crate 1-4 for the step they are
sent in; ports 4-7 answer crate 1-4.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .drshape import Note
from .i18n import _

PUSH = (0, 1, 2, 3)
PICK = (4, 5, 6, 7)
PORTS = 8
EVENTS = PICK
LANE = 6.0                     # metres from start to the wall
G = 9.8
PATCHES = ('wood', 'bell', 'growl')
HEAVY, SLIPPERY = 'heavy', 'slippery'


class Grade(NamedTuple):
    rung: int
    crates: int
    ratio: float               # heaviest over the next
    floors: bool               # a floor of its own under each crate
    slippery: bool             # some boards ask for the slipperiest
    sizes: bool
    boards: int
    seconds: float             # for each board
    weak: float                # the push, as a share of the plain push


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r == 1:
        return Grade(r, 3, 3.0, False, False, False, 5, 30.0, 1.0)
    if r < 4:
        return Grade(r, 3, 2.0 if r == 2 else 1.5, False, False, False, 5,
                     30.0, 1.0)
    if r < 7:
        return Grade(r, 3, 1.5 - 0.05 * (r - 4), True, False, False, 5,
                     30.0, 1.0)
    if r < 10:
        return Grade(r, 4, 1.35, True, True, False, 4, 32.0, 1.0)
    if r < 13:
        return Grade(r, 4, 1.3 - 0.03 * (r - 10), True, True, True, 4, 32.0,
                     1.0)
    return Grade(r, 4, 1.0 + 0.2 * 0.85 ** (r - 13), True, True, True, 4,
                 32.0, max(0.5, 0.95 ** (r - 13)))


class Board(NamedTuple):
    ask: str
    mass: Tuple[float, ...]
    grip: Tuple[float, ...]        # the floor's friction under each crate
    size: Tuple[float, ...]
    force: float
    answer: int


class Round(NamedTuple):
    level: Grade
    boards: Tuple[Board, ...]


def _board(level: Grade, draw, ask: str) -> Board:
    n = level.crates
    for _k in range(200):
        # masses: one stands out by *ratio*, the rest spread below it
        top = draw.uniform(2.0, 4.0)
        rest = [top / level.ratio / draw.uniform(1.0, 1.0 + 0.6 *
                                                  (level.ratio - 1))
                for _i in range(n - 1)]
        rest[0] = top / level.ratio
        mass = [top] + rest
        if level.floors:
            grips = [draw.uniform(0.15, 0.45) for _i in range(n)]
        else:
            grips = [draw.uniform(0.2, 0.4)] * n
        if ask == SLIPPERY:
            lo = draw.uniform(0.12, 0.3)
            grips = [lo] + [lo * level.ratio * draw.uniform(1.0, 1.3)
                            for _i in range(n - 1)]
            mass = [draw.uniform(1.0, 4.0) for _i in range(n)]
        order = list(range(n))
        draw.shuffle(order)
        mass = [mass[k] for k in order]
        grips = [grips[k] for k in order]
        answer = order.index(0)
        size = [draw.uniform(0.45, 0.9) if level.sizes else 0.7
                for _i in range(n)]
        # every crate gets going, the slowest at a creep that weakens
        force = max(m * (g * G + 0.25 + 0.75 * level.weak)
                    for m, g in zip(mass, grips))
        b = Board(ask, tuple(mass), tuple(grips), tuple(size), force, answer)
        if ask == HEAVY and level.floors:
            # the crate quickest off the mark must not always be the
            # lightest: the floors have to matter
            a = [force / m - g * G for m, g in zip(mass, grips)]
            if a.index(min(a)) == answer and draw.random() < 0.6:
                continue
        return b
    return b


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Round:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _k in range(200):
        boards = []
        for i in range(level.boards):
            ask = SLIPPERY if level.slippery and draw.random() < 0.4 \
                else HEAVY
            boards.append(_board(level, draw, ask))
        answers = [b.answer for b in boards]
        if len(set(answers)) < 2:
            continue
        rnd = Round(level, tuple(boards))
        if play(rnd)[0]:
            return rnd
    raise RuntimeError('heavier: no round for rung %d' % rung)


class Run(object):
    def __init__(self, rnd: Round) -> None:
        self.rnd = rnd
        self.level = rnd.level
        self.t = 0.0
        self.board = 0
        self.started = 0.0
        self.right = 0
        self.result: Optional[Tuple[bool, str]] = None
        self.notes: List[Note] = []
        self.end = rnd.level.seconds * rnd.level.boards
        self._reset()

    def _reset(self) -> None:
        n = self.level.crates
        self.x = [0.0] * n
        self.v = [0.0] * n
        self.pushed = [0.0] * n            # seconds pushed, for the record

    @property
    def now(self) -> Board:
        # the last board stays on show once it has been answered
        return self.rnd.boards[min(self.board, len(self.rnd.boards) - 1)]

    def _note(self, dur, f, voice, gain) -> None:
        self.notes.append(Note(self.t, dur, f, 0.0, 0.0, gain, gain, 0.8,
                               voice, len(self.notes) + 1, -1, 0.0))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        b = self.now
        push = control if isinstance(control, int) and \
            control in PUSH[:self.level.crates] else None
        for k in range(self.level.crates):
            m, g = b.mass[k], b.grip[k]
            f = b.force if k == push and self.x[k] < LANE - b.size[k] else 0.0
            if f:
                self.pushed[k] += dt
            stop = g * G
            if self.v[k] > 0:
                a = f / m - stop
                v = self.v[k] + a * dt
                if not f and v < 0:
                    v = 0.0
            else:
                v = self.v[k] + max(0.0, f / m - stop) * dt
            self.v[k] = max(0.0, v)
            self.x[k] += self.v[k] * dt
            if self.x[k] > LANE - b.size[k]:
                self.x[k] = LANE - b.size[k]
                if self.v[k] > 0.5:
                    self._note(0.12, 140.0, 0, min(0.4, 0.1 * self.v[k]))
                self.v[k] = 0.0
        if self.t - self.started > self.level.seconds:
            self.result = (False, _('Out of time on board %d') % (
                self.board + 1))

    def answer(self, k: int) -> None:
        if self.result is not None or k >= self.level.crates:
            return
        b = self.now
        if k != b.answer:
            word = _('heaviest') if b.ask == HEAVY else _('slipperiest')
            self.result = (False, _('Board %d: crate %d was the %s') % (
                self.board + 1, b.answer + 1, word))
            self._note(0.4, 110.0, 2, 0.4)
            return
        self.right += 1
        self._note(0.2, 880.0, 1, 0.3)
        self.board += 1
        if self.board == len(self.rnd.boards):
            self.result = (True, _('Every board right'))
            return
        self.started = self.t
        self._reset()


def act(run: Run, port: int) -> None:
    if port in PICK:
        run.answer(port - PICK[0])


def autopilot(run: Run) -> List[int]:
    """Pushes each crate in turn for a little over half a second, lets it slide
    to rest, and reads from what it saw: the slowing gives the floor,
    the getting-going then gives the mass."""
    if run.result is not None:
        return []
    n = run.level.crates
    memo = getattr(run, '_memo', None)
    if memo is None or memo[0] != run.board:
        memo = [run.board, 0, None, {}, 0.0]    # board, crate, phase, seen
        run._memo = memo
    _b, k, phase, seen, mark = memo
    if k >= n:
        b = run.now
        if b.ask == HEAVY:
            best = max(range(n), key=lambda i: seen[i][0])
        else:
            best = min(range(n), key=lambda i: seen[i][1])
        return [PICK[best]]
    if phase is None:
        memo[2], memo[4] = 'push', run.t
        return [PUSH[k]]
    if phase == 'push':
        if run.t - mark < 0.6:
            return [PUSH[k]]
        memo[2] = 'slide'
        memo[4] = run.t
        seen[k] = [run.v[k], None, run.t - mark, None]
        return []
    if phase == 'slide':
        if run.t - mark >= 1 / 30.0 - 1e-9 and seen[k][3] is None:
            # the slowing over the slide's first step: before it can stop
            v0 = seen[k][0]
            seen[k][3] = (v0 - run.v[k]) / (run.t - mark)
        if seen[k][3] is not None:
            decel = max(1e-6, seen[k][3])
            grip = decel / G
            a_push = seen[k][0] / seen[k][2]
            mass = run.now.force / (a_push + decel)
            seen[k] = (mass, grip)
            memo[1] += 1
            memo[2] = None
        return []
    return []


def play(rnd: Round, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(rnd)
    while run.result is None:
        ports = pilot(run)
        held = [p for p in ports if p not in EVENTS]
        for p in ports:
            if p in EVENTS:
                act(run, p)
        run.step(dt, held[0] if held else None)
    return run.result
