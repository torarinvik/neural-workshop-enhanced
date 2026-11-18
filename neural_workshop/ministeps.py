# -*- coding: utf-8 -*-
"""Short walks to a goal: rung n is a puzzle n right presses from done.

The maze, the tower, the tile puzzle and the box-pushing room each pay
only when the whole thing is solved, which a beginner pressing at random
never reaches. These are the same kinds of puzzle cut down to their last
few steps. Rung 1 is one press from solved; every rung above it is one
press further away. A press that does not bring the goal nearer -- a
bump, a step the wrong way, a move that is not allowed -- ends the trial
at once, so every trial is judged within a handful of presses.

Each puzzle is a state, a ``move(state, port)`` and a ``far(state)``,
the fewest presses still needed. :class:`Walk` is one trial of any of
them.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from collections import deque
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from .i18n import _

#: Up, down, left, right -- the order the four steering ports come in.
STEPS = ((0, 1), (0, -1), (-1, 0), (1, 0))
#: From peg, to peg -- the order the tower's six ports come in.
LIFTS = ((0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1))

#: Colour sets a trial is drawn in: (ground, wall, mover, goal).
LOOKS = (
    ((236, 240, 247), (52, 70, 110), (30, 110, 200), (120, 60, 170)),
    ((244, 240, 230), (110, 84, 50), (150, 90, 20), (20, 120, 130)),
    ((233, 242, 238), (40, 96, 84), (20, 130, 150), (150, 70, 120)),
    ((240, 236, 246), (86, 60, 120), (110, 70, 190), (30, 110, 160)),
    ((242, 242, 242), (70, 70, 78), (60, 90, 160), (160, 90, 30)),
)


class Puzzle(NamedTuple):
    kind: str                    # 'maze', 'tower', 'tiles', 'push', 'walk'
    ports: int
    start: Any                   # the state the trial opens in
    far: int                     # presses from done, at the start
    data: Dict[str, Any]         # what the kind needs to move and draw
    look: int                    # which colour set
    question: str


# --- the four kinds ----------------------------------------------------------

def _maze_walls(side: int, rng: random.Random):
    """A maze with one way between any two cells: the open passages."""
    seen = {(0, 0)}
    stack = [(0, 0)]
    doors = set()
    while stack:
        x, y = stack[-1]
        ways = [(x + dx, y + dy) for dx, dy in STEPS
                if 0 <= x + dx < side and 0 <= y + dy < side
                and (x + dx, y + dy) not in seen]
        if not ways:
            stack.pop()
            continue
        nxt = rng.choice(ways)
        doors.add(frozenset(((x, y), nxt)))
        seen.add(nxt)
        stack.append(nxt)
    return doors


def _flood(start, step):
    """Fewest moves from *start* to everything *step* reaches."""
    far = {start: 0}
    queue = deque([start])
    while queue:
        here = queue.popleft()
        for there in step(here):
            if there not in far:
                far[there] = far[here] + 1
                queue.append(there)
    return far


def _maze(n: int, rng: random.Random) -> Optional[Puzzle]:
    side = 6 + 2 * ((n - 1) // 12)
    doors = _maze_walls(side, rng)
    goal = (rng.randrange(side), rng.randrange(side))

    def step(c):
        return [(c[0] + dx, c[1] + dy) for dx, dy in STEPS
                if frozenset((c, (c[0] + dx, c[1] + dy))) in doors]
    far = _flood(goal, step)
    starts = [c for c, d in far.items() if d == n]
    if not starts:
        return None
    return Puzzle('maze', 4, rng.choice(starts), n,
                  {'side': side, 'doors': doors, 'goal': goal, 'far': far},
                  rng.randrange(len(LOOKS)),
                  _('Walk to the way out'))


def _tower(n: int, rng: random.Random) -> Optional[Puzzle]:
    discs = 4
    while 2 ** discs - 1 < n:
        discs += 1
    goal_peg = rng.randrange(3)
    goal = (goal_peg,) * discs

    def step(s):
        out = []
        for a, b in LIFTS:
            t = _lift(s, a, b)
            if t is not None:
                out.append(t)
        return out
    far = _flood(goal, step)             # moves undo, so this is both ways
    starts = [s for s, d in far.items() if d == n]
    if not starts:
        return None
    return Puzzle('tower', 6, rng.choice(starts), n,
                  {'discs': discs, 'goal': goal_peg, 'far': far},
                  rng.randrange(len(LOOKS)),
                  _('Move every disc to the marked peg'))


def _lift(state, a: int, b: int):
    """The tower after moving the top disc of peg *a* to *b*, or None."""
    on_a = [d for d, peg in enumerate(state) if peg == a]
    if not on_a:
        return None
    disc = min(on_a)
    on_b = [d for d, peg in enumerate(state) if peg == b]
    if on_b and min(on_b) < disc:
        return None
    return state[:disc] + (b,) + state[disc + 1:]


def _tiles(n: int, rng: random.Random) -> Optional[Puzzle]:
    if n > 8:
        return None
    # Never more than half the board turned, or a blind press would be
    # more likely right than wrong: eight tiles, then twelve, sixteen.
    cols, rows = 4, 2 if n <= 4 else 3 if n <= 6 else 4
    count = cols * rows
    home = rng.randrange(4)                  # which corner is "home"
    turned = set(rng.sample(range(count), n))
    start = tuple((home + rng.randrange(1, 4)) % 4 if k in turned else home
                  for k in range(count))
    return Puzzle('tiles', count, start, n,
                  {'cols': cols, 'rows': rows, 'home': home},
                  rng.randrange(len(LOOKS)),
                  _('Turn back every tile that is turned'))


#: The tiles on the largest board, which is the tile puzzle's port count.
TILE_PORTS = 16


def _push(n: int, rng: random.Random) -> Optional[Puzzle]:
    side = 5 + (n - 1) // 8
    cells = [(x, y) for x in range(side) for y in range(side)]
    walls = set(rng.sample(cells, rng.randrange(0, side - 2)))
    free = [c for c in cells if c not in walls]
    goal = rng.choice(free)

    def moved(state, d):
        (px, py), box = state
        dx, dy = STEPS[d]
        to = (px + dx, py + dy)
        if to not in ok:
            return None
        if to == box:
            on = (to[0] + dx, to[1] + dy)
            if on not in ok:
                return None
            return (to, on)
        return (to, box)
    ok = set(free)
    # Fewest presses to the goal from every state, found backwards.
    back: Dict[Any, List[Any]] = {}
    states = [(p, b) for p in free for b in free if p != b]
    for s in states:
        for d in range(4):
            t = moved(s, d)
            if t is not None:
                back.setdefault(t, []).append(s)
    far = {s: 0 for s in states if s[1] == goal}
    queue = deque(far)
    while queue:
        here = queue.popleft()
        for there in back.get(here, ()):
            if there not in far:
                far[there] = far[here] + 1
                queue.append(there)
    starts = [s for s, d in far.items() if d == n]
    if not starts:
        return None
    return Puzzle('push', 4, rng.choice(starts), n,
                  {'side': side, 'walls': walls, 'goal': goal, 'far': far,
                   'free': ok},
                  rng.randrange(len(LOOKS)),
                  _('Push the box onto the mark'))


def _walk(n: int, rng: random.Random,
          order: Tuple[int, ...] = (0, 1, 2, 3)) -> Optional[Puzzle]:
    side = max(5, (n + 1) // 2 + 2)
    for _try in range(200):
        start = (rng.randrange(side), rng.randrange(side))
        goal = (rng.randrange(side), rng.randrange(side))
        if abs(start[0] - goal[0]) + abs(start[1] - goal[1]) == n:
            return Puzzle('walk', 4, start, n,
                          {'side': side, 'goal': goal, 'order': tuple(order)},
                          rng.randrange(len(LOOKS)),
                          _('Move the marker onto the marked square'))
    return None


MAKERS = {'maze': _maze, 'tower': _tower, 'tiles': _tiles, 'push': _push,
          'walk': _walk}


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         **extra: Any) -> Puzzle:
    """A puzzle of *kind* exactly *rung* presses from done."""
    rng = rng or random.Random()
    n = max(1, int(rung))
    while True:
        for _try in range(300):
            puzzle = MAKERS[kind](n, rng, **extra)
            if puzzle is not None:
                return puzzle
        n -= 1                               # further than this kind goes
        if n < 1:
            raise ValueError('no %s puzzle could be dealt' % kind)


# --- moving ------------------------------------------------------------------

def move(puzzle: Puzzle, state: Any, port: int) -> Any:
    """The state after *port*, or None when the press does nothing."""
    kind, data = puzzle.kind, puzzle.data
    if not 0 <= port < puzzle.ports:
        return None
    if kind == 'maze':
        dx, dy = STEPS[port]
        to = (state[0] + dx, state[1] + dy)
        return to if frozenset((state, to)) in data['doors'] else None
    if kind == 'tower':
        return _lift(state, *LIFTS[port])
    if kind == 'tiles':
        if port >= len(state) or state[port] == data['home']:
            return None
        return state[:port] + (data['home'],) + state[port + 1:]
    if kind == 'push':
        (px, py), box = state
        dx, dy = STEPS[port]
        to = (px + dx, py + dy)
        if to not in data['free']:
            return None
        if to == box:
            on = (to[0] + dx, to[1] + dy)
            return (to, on) if on in data['free'] else None
        return (to, box)
    dx, dy = STEPS[data['order'][port]]
    to = (state[0] + dx, state[1] + dy)
    side = data['side']
    return to if 0 <= to[0] < side and 0 <= to[1] < side else None


def far(puzzle: Puzzle, state: Any) -> int:
    """Fewest presses from *state* to done."""
    kind, data = puzzle.kind, puzzle.data
    if kind == 'tiles':
        return sum(1 for turn in state if turn != data['home'])
    if kind == 'walk':
        goal = data['goal']
        return abs(state[0] - goal[0]) + abs(state[1] - goal[1])
    return data['far'].get(state, 10 ** 6)


def good(puzzle: Puzzle, state: Any) -> List[int]:
    """The ports that bring *state* a press nearer to done."""
    here = far(puzzle, state)
    out = []
    for port in range(puzzle.ports):
        to = move(puzzle, state, port)
        if to is not None and far(puzzle, to) < here:
            out.append(port)
    return out


class Walk:
    """One trial: press towards the goal until there, or until wrong."""

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.state = puzzle.start
        self.presses = 0
        #: +1 after a press that got nearer, for a caller that pays by
        #: the step; None when the last press did nothing to pay.
        self.last: Optional[bool] = None
        self.result: Optional[Tuple[bool, str]] = None

    def press(self, port: int) -> Optional[bool]:
        """Whether the press got nearer; None when it was not a press."""
        if self.result is not None or not 0 <= port < self.puzzle.ports:
            return None
        self.presses += 1
        to = move(self.puzzle, self.state, port)
        if to is None or far(self.puzzle, to) >= far(self.puzzle,
                                                     self.state):
            self.last = False
            self.result = (False, _('Wrong step after %d right')
                           % (self.presses - 1))
            return False
        self.state = to
        self.last = True
        if far(self.puzzle, to) == 0:
            self.result = (True, _('Done in %d') % self.presses)
        return True


def solve(puzzle: Puzzle) -> List[int]:
    """Presses that finish the puzzle from its start."""
    state, out = puzzle.start, []
    while far(puzzle, state):
        port = good(puzzle, state)[0]
        out.append(port)
        state = move(puzzle, state, port)
    return out
