# -*- coding: utf-8 -*-
"""More forgiving walks: three other kinds of walk under the rules of
Long Way Round.

As there, a wrong press costs a step and never ends the trial; the
trial ends at the goal, or at the press that uses the last step, at
par plus half of par and never fewer than par plus two; rung k is k
presses on the shortest way; and the board (seven by seven squares,
the same size and place on every rung) and the four ports (up, down,
left, right: the player moves one square that way) are the same on
every rung, so a higher rung is a longer walk, not another task.

``pushpull``  a box and a mark on an open floor with a few blocks: walk
              into the box to push it a square, and step straight away
              from it to pull it after you. Done when the box is on the
              mark. A push into a corner is undone by a pull.
``oneway``    a maze with one way between any two squares, and a few
              more openings that can be passed one way only, shown by a
              wedge pointing the way: walk to the goal.
``ice``       an open floor with a few blocks, all ice: a press slides
              the player that way until a block or the edge stops it.
              Done when the player comes to rest on the goal. Slides
              cover ground fast, so the ladder tops out at rung 10:
              higher rungs play as rung 10.

No board is dealt on which a press can lead anywhere the goal cannot
be reached from: a wrong press may waste steps, never the trial. (A
push into a corner is undone by a pull; a one-way opening is never the
only way back; an ice floor with a trap is dealt again.)

Random presses, measured over 600 trials a rung (the tests count
again), are paid within the step limit:

=========== ======= ======= =======
kind        rung 1  rung 3  rung 5
=========== ======= ======= =======
pushpull    0.37    0.04    0.01
oneway      0.44    0.06    0.01
ice         0.44    0.08    0.01
=========== ======= ======= =======

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from collections import deque
from typing import Dict, List, NamedTuple, Optional, Tuple

from .i18n import _
from .ministeps import LOOKS, STEPS, _maze_walls

KINDS = ('pushpull', 'oneway', 'ice')
SIDE = 7
#: The longest ice walk dealt.
ICE_TOP = 10
PORTS = 4

Cell = Tuple[int, int]

QUESTIONS = {
    'pushpull': _('Push or pull the box onto the mark'),
    'oneway': _('Walk to the goal; wedges go one way'),
    'ice': _('Slide to a stop on the goal'),
}


class Puzzle(NamedTuple):
    kind: str
    ports: int
    start: tuple
    par: int
    limit: int
    data: Dict
    look: int
    question: str


def allowed(par: int) -> int:
    """Presses allowed for a walk *par* presses long: as Long Way Round."""
    return par + max(2, par // 2)


def _inside(c: Cell) -> bool:
    return 0 <= c[0] < SIDE and 0 <= c[1] < SIDE


def _blocks(rng: random.Random, n: int) -> frozenset:
    cells = [(x, y) for x in range(SIDE) for y in range(SIDE)]
    return frozenset(rng.sample(cells, n))


# --- moving ------------------------------------------------------------------

def move(puzzle: Puzzle, state: tuple, port: int) -> tuple:
    """Where a press of *port* leaves the game: unchanged on a bump."""
    dx, dy = STEPS[port]
    data = puzzle.data
    if puzzle.kind == 'pushpull':
        player, box = state
        to = (player[0] + dx, player[1] + dy)
        if not _inside(to) or to in data['blocks']:
            return state
        if to == box:
            on = (box[0] + dx, box[1] + dy)
            if not _inside(on) or on in data['blocks']:
                return state
            return (to, on)
        if box == (player[0] - dx, player[1] - dy):
            return (to, player)
        return (to, box)
    if puzzle.kind == 'oneway':
        (here,) = state
        to = (here[0] + dx, here[1] + dy)
        if frozenset((here, to)) in data['doors'] or \
                (here, to) in data['oneway']:
            return (to,)
        return state
    (here,) = state
    while True:
        to = (here[0] + dx, here[1] + dy)
        if not _inside(to) or to in data['blocks']:
            return (here,)
        here = to


def done(puzzle: Puzzle, state: tuple) -> bool:
    if puzzle.kind == 'pushpull':
        return state[1] == puzzle.data['goal']
    return state[0] == puzzle.data['goal']


def _states(kind: str, data: Dict) -> List[tuple]:
    free = [(x, y) for x in range(SIDE) for y in range(SIDE)
            if (x, y) not in data.get('blocks', ())]
    if kind == 'pushpull':
        return [(p, b) for p in free for b in free if p != b]
    return [(c,) for c in free]


def _distances(puzzle: Puzzle) -> Dict[tuple, int]:
    """Fewest presses from every state to done, by a search backwards
    from the done states."""
    states = _states(puzzle.kind, puzzle.data)
    back: Dict[tuple, List[tuple]] = {s: [] for s in states}
    for s in states:
        for port in range(PORTS):
            t = move(puzzle, s, port)
            if t != s:
                back[t].append(s)
    far = {s: 0 for s in states if done(puzzle, s)}
    queue = deque(far)
    while queue:
        s = queue.popleft()
        for r in back[s]:
            if r not in far:
                far[r] = far[s] + 1
                queue.append(r)
    return far


# --- dealing -----------------------------------------------------------------

def _board(kind: str, rng: random.Random) -> Dict:
    if kind == 'oneway':
        doors = _maze_walls(SIDE, rng)
        shut = [frozenset(((x, y), (x + dx, y + dy)))
                for x in range(SIDE) for y in range(SIDE)
                for dx, dy in ((1, 0), (0, 1))
                if _inside((x + dx, y + dy))
                and frozenset(((x, y), (x + dx, y + dy))) not in doors]
        oneway = set()
        for pair in rng.sample(shut, 6):
            a, b = sorted(pair)
            oneway.add((a, b) if rng.random() < 0.5 else (b, a))
        return {'side': SIDE, 'doors': doors, 'oneway': frozenset(oneway)}
    return {'side': SIDE, 'blocks': _blocks(rng, rng.randint(4, 7))}


def _try(kind: str, k: int, rng: random.Random) -> Optional[Puzzle]:
    data = _board(kind, rng)
    free = [c for c in ((x, y) for x in range(SIDE) for y in range(SIDE))
            if c not in data.get('blocks', ())]
    data['goal'] = rng.choice(free)
    probe = Puzzle(kind, PORTS, None, 0, 0, data, 0, '')
    far = _distances(probe)
    starts = [s for s, d in far.items() if d == k]
    if not starts:
        return None
    start = rng.choice(starts)
    if not _no_traps(probe, start, far):
        return None
    data['far'] = far
    return Puzzle(kind, PORTS, start, k, allowed(k), data,
                  rng.randrange(len(LOOKS)), QUESTIONS[kind])


def _no_traps(puzzle: Puzzle, start: tuple, far: Dict[tuple, int]) -> bool:
    """Whether done can still be reached from everywhere the start can
    lead: a wrong press may waste steps, never the trial."""
    seen = {start}
    queue = deque([start])
    while queue:
        s = queue.popleft()
        if s not in far:
            return False
        for port in range(PORTS):
            t = move(puzzle, s, port)
            if t not in seen:
                seen.add(t)
                queue.append(t)
    return True


def deal(kind: str, rung: int, rng: Optional[random.Random] = None
         ) -> Puzzle:
    rng = rng or random.Random()
    k = max(1, int(rung))
    if kind == 'ice':
        k = min(k, ICE_TOP)
    for _try_no in range(500):
        puzzle = _try(kind, k, rng)
        if puzzle is not None:
            return puzzle
    raise ValueError('no %s walk of %d could be dealt' % (kind, k))


def far(puzzle: Puzzle, state: tuple) -> int:
    return puzzle.data['far'].get(state, 10 ** 6)


class Walk:
    """One trial: presses until done, or until the steps run out."""

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.state = puzzle.start
        self.presses = 0
        self.result: Optional[Tuple[bool, str]] = None

    def press(self, port: int) -> Optional[bool]:
        """Whether the press got nearer; None when it was not a press."""
        if self.result is not None or not 0 <= port < PORTS:
            return None
        before = far(self.puzzle, self.state)
        self.state = move(self.puzzle, self.state, port)
        self.presses += 1
        if done(self.puzzle, self.state):
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
