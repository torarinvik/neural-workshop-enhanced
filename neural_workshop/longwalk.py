# -*- coding: utf-8 -*-
"""Forgiving walks: a maze walk where a wrong press costs a step but
does not end the trial.

In the short walks of :mod:`ministeps` a press that does not bring the
goal nearer ends the trial, so every press of a trial that was not
paid was right, and there is nothing for a learner's own sub-goals to
tell apart. Here a press can bump into a wall, which wastes a step, or
lead down a dead end, which wastes the steps back out, and the trial
goes on until the goal is reached or the steps run out.

The board is the same on every rung: a seven by seven maze with one
way between any two squares, drawn afresh each trial, in the same size
and place on the screen, with the same four ports, up, down, left and
right. Only the walk gets longer.

``walk``  rung k starts k presses from the goal along the shortest way.

The steps allowed are a little above the shortest way: par plus half
of par, and never fewer than par plus two. The verdict comes at the
press that reaches the goal, or at the press that uses the last step.

These are walks, not looking-back questions: the board shows the way,
and the rules about the frame the question is put on do not apply.
Pressing at random reaches the goal at rung 1 within its three steps
about 45 times in a hundred; the tests count it.

:class:`Walk` takes its rules -- ``move``, ``far`` and ``done`` -- from
itself, so another walk on the same board can bring its own.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from collections import deque
from typing import Dict, List, NamedTuple, Optional, Tuple

from .i18n import _
from .ministeps import LOOKS, STEPS, _maze_walls

KINDS = ('walk',)
SIDE = 7
PORTS = 4

Cell = Tuple[int, int]


class Puzzle(NamedTuple):
    kind: str
    ports: int
    start: tuple                 # (square, True)
    par: int                     # presses on the shortest way
    limit: int                   # presses allowed
    data: Dict
    look: int
    question: str


def allowed(par: int) -> int:
    """Presses allowed for a walk *par* presses long."""
    return par + max(2, par // 2)


def _ways(doors, here: Cell, shut: Optional[Cell] = None) -> List[Cell]:
    out = []
    for dx, dy in STEPS:
        there = (here[0] + dx, here[1] + dy)
        if there != shut and frozenset((here, there)) in doors:
            out.append(there)
    return out


def _flood(doors, start: Cell, shut: Optional[Cell] = None
           ) -> Dict[Cell, int]:
    far = {start: 0}
    queue = deque([start])
    while queue:
        here = queue.popleft()
        for there in _ways(doors, here, shut):
            if there not in far:
                far[there] = far[here] + 1
                queue.append(there)
    return far


def _square(rng) -> Cell:
    return (rng.randrange(SIDE), rng.randrange(SIDE))


def board(rng: random.Random):
    """A fresh maze, its goal, every square's way to the goal, and
    the look, drawn in that order."""
    doors = _maze_walls(SIDE, rng)
    goal = _square(rng)
    to_goal = _flood(doors, goal)
    look = rng.randrange(len(LOOKS))
    return doors, goal, to_goal, look


def _try(kind: str, k: int, rng: random.Random) -> Optional[Puzzle]:
    if kind != 'walk':
        raise ValueError(kind)
    doors, goal, to_goal, look = board(rng)
    starts = [c for c, d in to_goal.items() if d == k]
    if not starts:
        return None
    return Puzzle(kind, PORTS, (rng.choice(starts), True), k,
                  allowed(k), {'side': SIDE, 'doors': doors,
                               'goal': goal, 'to_goal': to_goal},
                  look, _('Walk to the goal'))


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         maker=None) -> Puzzle:
    """A walk of *kind* at *rung*; *maker* deals one try of another
    walk on the same board."""
    rng = rng or random.Random()
    k = max(1, int(rung))
    for _try_no in range(2000):
        puzzle = maker(k, rng) if maker else _try(kind, k, rng)
        if puzzle is not None:
            return puzzle
    raise ValueError('no %s walk of %d could be dealt' % (kind, k))


def move(puzzle: Puzzle, state: tuple, port: int) -> tuple:
    """Where a press of *port* leaves the player: on a bump, where it
    was."""
    (x, y), held = state
    dx, dy = STEPS[port]
    to = (x + dx, y + dy)
    if frozenset(((x, y), to)) not in puzzle.data['doors']:
        return state
    return (to, held)


def far(puzzle: Puzzle, state: tuple) -> int:
    """Fewest presses from *state* to done."""
    return puzzle.data['to_goal'][state[0]]


def done(puzzle: Puzzle, state: tuple) -> bool:
    return state[0] == puzzle.data['goal']


class Walk:
    """One trial: presses until the goal, or until the steps run out."""

    move = staticmethod(move)
    far = staticmethod(far)
    done = staticmethod(done)

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.state = puzzle.start
        self.presses = 0
        self.result: Optional[Tuple[bool, str]] = None

    def press(self, port: int) -> Optional[bool]:
        """Whether the press got nearer; None when it was not a press."""
        if self.result is not None or not 0 <= port < PORTS:
            return None
        before = self.far(self.puzzle, self.state)
        self.state = self.move(self.puzzle, self.state, port)
        self.presses += 1
        if self.done(self.puzzle, self.state):
            self.result = (True, _('There in %d of %d')
                           % (self.presses, self.puzzle.limit))
        elif self.presses >= self.puzzle.limit:
            self.result = (False, _('Out of steps'))
        return self.far(self.puzzle, self.state) < before

    def good(self) -> List[int]:
        """The ports that bring the goal a press nearer."""
        here = self.far(self.puzzle, self.state)
        return [p for p in range(PORTS)
                if self.far(self.puzzle,
                            self.move(self.puzzle, self.state, p)) < here]

    def left(self) -> int:
        return self.puzzle.limit - self.presses
