# -*- coding: utf-8 -*-
"""Walks from memory: where to go is shown for a moment and then
hidden, and the player walks there under the forgiving rules.

``one``  the goal shows for two frames (a second) and is hidden; then
         walk to where it was. Rung k puts it k presses away.
``two``  two goals show, one a frame, and are hidden; then visit them
         in the order they were shown. Stepping on the second before
         the first does nothing. Two places need at least two presses,
         so rung k is k + 1 presses on the shortest way: rung 1 is two.

The floor is an open seven by seven board, the same on every rung,
with the four ports moving the player up, down, left and right. Presses
while the goals show are ignored. Then, as in Long Way Round, a press
that goes the wrong way, or into the edge, costs a step, and the trial
ends at the goal (the second goal, for ``two``), at the press that uses
the last step (par plus half of par, at least par plus two), or when
the time runs out. Nothing on screen changes when a goal is reached,
and nothing shows where the goals were once they are hidden.

The floor for a player without memory. Once the goals are hidden the
screen shows the board and the player and nothing else -- no rung, no
count of steps -- so a player who sees only the current frame sees the
same thing every time it stands on the same square, and can only map
squares to presses. Where the goal is, among the squares at the rung's
distance from where the player stood, is drawn evenly; the tests count
that. Measured over 3000 trials a rung (the tests count again):

======== ============================ ======= ======= =======
kind     player                       rung 1  rung 3  rung 5
======== ============================ ======= ======= =======
one      random presses               0.36    0.07    0.02
one      one fixed direction, best    0.26    0.09    0.04
one      head for the middle          0.31    0.15    0.06
two      random presses               0.13    0.02    0.01
two      one fixed direction, best    0.06    0.02    0.01
two      head for the middle          0.09    0.04    0.01
======== ============================ ======= ======= =======

So the floor is the level of random presses, give or take what the
middle of the board is worth: a goal far from where the player stands
is likelier to lie towards the middle.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from .framed import FRAME, GIVE
from .i18n import _
from .ministeps import LOOKS, STEPS

KINDS = ('one', 'two')
SIDE = 7
PORTS = 4
#: Ports act when pressed.
EVENTS = (0, 1, 2, 3)
#: Frames the goals show for before the walk opens.
SHOWN = 2
#: Seconds allowed a step, and to spare, once the walk opens.
PER_STEP, SPARE = 2.0, 4.0

Cell = Tuple[int, int]

QUESTIONS = {
    'one': _('Walk to where the goal was'),
    'two': _('Visit the two places in the order shown'),
}


class Puzzle(NamedTuple):
    kind: str
    ports: int
    start: tuple                 # (square, goals reached)
    goals: Tuple[Cell, ...]      # in the order to visit them
    par: int
    limit: int
    open_at: float
    data: Dict
    look: int
    question: str


def allowed(par: int) -> int:
    """Presses allowed for a walk *par* presses long: as Long Way Round."""
    return par + max(2, par // 2)


def apart(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def ring(centre: Cell, k: int) -> List[Cell]:
    """The squares of the board *k* presses from *centre*."""
    return [(x, y) for x in range(SIDE) for y in range(SIDE)
            if apart((x, y), centre) == k]


def _try(kind: str, k: int, rng: random.Random):
    start = (rng.randrange(SIDE), rng.randrange(SIDE))
    if kind == 'one':
        cells = ring(start, k)
        if not cells:
            return None
        return start, (rng.choice(cells),), k
    par = k + 1
    first = rng.randint(1, par - 1)
    near = ring(start, first)
    if not near:
        return None
    a = rng.choice(near)
    far = ring(a, par - first)
    if not far:
        return None
    return start, (a, rng.choice(far)), par


def deal(kind: str, rung: int, rng: Optional[random.Random] = None
         ) -> Puzzle:
    rng = rng or random.Random()
    k = max(1, min(int(rung), 2 * (SIDE - 1) - (kind == 'two')))
    while True:
        got = _try(kind, k, rng)
        if got is not None:
            break
    start, goals, par = got
    return Puzzle(kind, PORTS, (start, 0), goals, par, allowed(par),
                  SHOWN * FRAME, {'side': SIDE,
                                  'place': (rng.random(), rng.random())},
                  rng.randrange(len(LOOKS)), QUESTIONS[kind])


def move(puzzle: Puzzle, state: tuple, port: int) -> tuple:
    (x, y), reached = state
    dx, dy = STEPS[port]
    to = (x + dx, y + dy)
    if not (0 <= to[0] < SIDE and 0 <= to[1] < SIDE):
        return state
    if reached < len(puzzle.goals) and to == puzzle.goals[reached]:
        reached += 1
    return (to, reached)


def far(puzzle: Puzzle, state: tuple) -> int:
    """Fewest presses from *state* to done."""
    here, reached = state
    total, at = 0, here
    for goal in puzzle.goals[reached:]:
        total += apart(at, goal)
        at = goal
    return total


class Run:
    """One trial on the clock: the goals show, then the walk."""

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.state = puzzle.start
        self.t = 0.0
        self.presses = 0
        self.result: Optional[Tuple[bool, str]] = None
        self.limit_t = puzzle.open_at + PER_STEP * puzzle.limit + SPARE

    @property
    def open(self) -> bool:
        return self.t + GIVE >= self.puzzle.open_at

    def showing(self) -> Optional[int]:
        """Which goal shows now, or None."""
        if self.open:
            return None
        f = int(self.t / FRAME + GIVE)
        if self.puzzle.kind == 'one':
            return 0
        return min(f, len(self.puzzle.goals) - 1)

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t >= self.limit_t:
            self.result = (False, _('Too slow'))

    def press(self, port: int) -> Optional[bool]:
        if self.result is not None or not self.open \
                or not 0 <= port < PORTS:
            return None
        before = far(self.puzzle, self.state)
        self.state = move(self.puzzle, self.state, port)
        self.presses += 1
        if self.state[1] == len(self.puzzle.goals):
            self.result = (True, _('There in %d of %d')
                           % (self.presses, self.puzzle.limit))
        elif self.presses >= self.puzzle.limit:
            self.result = (False, _('Out of steps'))
        return far(self.puzzle, self.state) < before

    def good(self) -> List[int]:
        here = far(self.puzzle, self.state)
        return [p for p in range(PORTS)
                if far(self.puzzle, move(self.puzzle, self.state, p)) < here]

    def left(self) -> int:
        return self.puzzle.limit - self.presses


def act(run: Run, port: int) -> None:
    run.press(port)
