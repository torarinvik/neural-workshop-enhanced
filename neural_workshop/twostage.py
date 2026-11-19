# -*- coding: utf-8 -*-
"""Forgiving walks in two stages: a half-way point on the board that has
to be reached first.

The rules are those of Long Way Round (:mod:`longwalk`): a seven by
seven board, the same size and place on every rung; four ports, up,
down, left and right, each moving the player a square that way; a
press into a block or the edge costs a step and leaves the player
where it was; the trial ends at the goal, or at the press that uses
the last step, par plus half of par and never fewer than par plus two.

``fetch``  an open floor with a few blocks, a thing and a mark: walk
           onto the thing to pick it up, then carry it onto the mark.
           Stepping on the mark without it does nothing.
``plate``  an open floor with a few blocks and a goal in a pen whose
           one way in is a shut gate, a bar across the opening: step on
           the plate to open the gate, which stays open, then walk
           through it to the goal. The plate may lie anywhere outside
           the pen, the square in front of the gate too.

Two stages need two presses at least, so rung k is k + 1 presses on
the shortest way: rung 1 is two. Nothing dealt can be spoilt: the thing
once held stays held and the gate once open stays open, and the floor
is all of a piece, so a wrong press may waste steps, never the trial.

The board shows everything the walk needs, so a player seeing only the
current frame can walk it; pressing at random reaches the goal at rung
1 within its four steps about one time in eight on either kind (the
tests count it).

``order`` in a deal says which way each port moves, as indices into
:data:`ministeps.STEPS`: up, down, left, right unless a deal says
otherwise.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from collections import deque
from typing import Dict, Optional, Tuple

from . import longwalk
from .i18n import _
from .longwalk import PORTS, SIDE, Puzzle, allowed
from .ministeps import LOOKS, STEPS

KINDS = ('fetch', 'plate')
#: Up, down, left, right.
ORDER = (0, 1, 2, 3)
QUESTIONS = {'fetch': _('Fetch the thing and carry it to the mark'),
             'plate': _('Step on the plate, then go through the gate')}

Cell = Tuple[int, int]


def _inside(c: Cell) -> bool:
    return 0 <= c[0] < SIDE and 0 <= c[1] < SIDE


def _flood(blocked, start: Cell) -> Dict[Cell, int]:
    far = {start: 0}
    queue = deque([start])
    while queue:
        here = queue.popleft()
        for dx, dy in STEPS:
            there = (here[0] + dx, here[1] + dy)
            if _inside(there) and there not in blocked and \
                    there not in far:
                far[there] = far[here] + 1
                queue.append(there)
    return far


def _cells():
    return [(x, y) for x in range(SIDE) for y in range(SIDE)]


def _fetch(k: int, rng: random.Random, order, look) -> Optional[Puzzle]:
    par = k + 1
    blocks = frozenset(rng.sample(_cells(), rng.randint(4, 7)))
    free = [c for c in _cells() if c not in blocks]
    mark = rng.choice(free)
    to_mark = _flood(blocks, mark)
    if len(to_mark) != len(free):
        return None
    there = rng.randint(1, par - 1)
    things = [c for c, d in to_mark.items() if d == there]
    if not things:
        return None
    thing = rng.choice(things)
    to_thing = _flood(blocks, thing)
    starts = [c for c, d in to_thing.items()
              if d == par - there and c != mark]
    if not starts:
        return None
    data = {'side': SIDE, 'blocks': blocks, 'mark': mark, 'thing': thing,
            'to_mark': to_mark, 'to_thing': to_thing, 'order': order}
    return Puzzle('fetch', PORTS, (rng.choice(starts), False), par,
                  allowed(par), data, look, QUESTIONS['fetch'])


def _plate(k: int, rng: random.Random, order, look) -> Optional[Puzzle]:
    par = k + 1
    goal = (rng.randrange(SIDE), rng.randrange(SIDE))
    around = [(goal[0] + dx, goal[1] + dy) for dx, dy in STEPS]
    around = [c for c in around if _inside(c)]
    gate = rng.choice(around)                 # the square before the bar
    pen = frozenset(c for c in around if c != gate)
    rest = [c for c in _cells() if c not in pen and c not in (goal, gate)]
    blocks = pen | frozenset(rng.sample(rest, rng.randint(3, 5)))
    free = [c for c in _cells() if c not in blocks]
    to_goal = _flood(blocks, goal)
    if len(to_goal) != len(free):
        return None
    plate = rng.choice([c for c in free if c != goal])
    to_plate = _flood(blocks | {goal}, plate)
    if len(to_plate) != len(free) - 1:        # all but the goal
        return None
    there = to_goal[plate]
    if not 1 <= there <= par - 1:
        return None
    starts = [c for c, d in to_plate.items()
              if d == par - there and c != plate]
    if not starts:
        return None
    data = {'side': SIDE, 'blocks': blocks, 'goal': goal, 'gate': gate,
            'plate': plate, 'to_goal': to_goal, 'to_plate': to_plate,
            'order': order}
    return Puzzle('plate', PORTS, (rng.choice(starts), False), par,
                  allowed(par), data, look, QUESTIONS['plate'])


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         order: Tuple[int, ...] = ORDER, look: Optional[int] = None
         ) -> Puzzle:
    """A two-stage walk; *order* says which way each port moves."""
    if kind not in KINDS:
        raise ValueError(kind)
    rng = rng or random.Random()
    maker = _fetch if kind == 'fetch' else _plate

    def one(k, rng):
        shown = rng.randrange(len(LOOKS)) if look is None else look
        return maker(k, rng, tuple(order), shown)
    return longwalk.deal(kind, rung, rng, maker=one)


def move(puzzle: Puzzle, state: tuple, port: int) -> tuple:
    (x, y), stage = state
    data = puzzle.data
    dx, dy = STEPS[data['order'][port]]
    to = (x + dx, y + dy)
    if not _inside(to) or to in data['blocks']:
        return state
    if puzzle.kind == 'fetch':
        return (to, stage or to == data['thing'])
    if to == data['goal'] and not stage:
        return state
    return (to, stage or to == data['plate'])


def far(puzzle: Puzzle, state: tuple) -> int:
    """Fewest presses from *state* to done."""
    here, stage = state
    data = puzzle.data
    if puzzle.kind == 'fetch':
        if stage:
            return data['to_mark'][here]
        return data['to_thing'][here] + data['to_mark'][data['thing']]
    if stage:
        return data['to_goal'][here]
    return data['to_plate'][here] + data['to_goal'][data['plate']]


def done(puzzle: Puzzle, state: tuple) -> bool:
    end = puzzle.data['mark' if puzzle.kind == 'fetch' else 'goal']
    return state[0] == end and state[1]


class Walk(longwalk.Walk):
    move = staticmethod(move)
    far = staticmethod(far)
    done = staticmethod(done)
