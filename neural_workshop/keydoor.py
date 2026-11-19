# -*- coding: utf-8 -*-
"""Key and Door.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import longwalk
from .i18n import _
from .longwalk import PORTS, SIDE, Puzzle, allowed
from .ministeps import STEPS

KIND = 'key'


def _try(k: int, rng: random.Random) -> Optional[Puzzle]:
    doors, goal, to_goal, look = longwalk.board(rng)
    par = k + 1
    there = rng.randint(1, par - 1)
    keys = [c for c, d in to_goal.items() if d == there]
    if not keys:
        return None
    key = rng.choice(keys)
    to_key = longwalk._flood(doors, key, shut=goal)
    starts = [c for c, d in to_key.items() if d == par - there]
    if not starts:
        return None
    return Puzzle(KIND, PORTS, (rng.choice(starts), False), par,
                  allowed(par), {'side': SIDE, 'doors': doors,
                                 'goal': goal, 'key': key,
                                 'to_goal': to_goal, 'to_key': to_key},
                  look, _('Fetch the key, then walk to the door'))


def deal(rung: int, rng: Optional[random.Random] = None) -> Puzzle:
    return longwalk.deal(KIND, rung, rng, maker=_try)


def move(puzzle: Puzzle, state: tuple, port: int) -> tuple:
    (x, y), held = state
    dx, dy = STEPS[port]
    to = (x + dx, y + dy)
    data = puzzle.data
    if frozenset(((x, y), to)) not in data['doors']:
        return state
    if to == data['goal'] and not held:
        return state
    if to == data['key']:
        held = True
    return (to, held)


def far(puzzle: Puzzle, state: tuple) -> int:
    here, held = state
    data = puzzle.data
    if held:
        return data['to_goal'][here]
    return data['to_key'][here] + data['to_goal'][data['key']]


def done(puzzle: Puzzle, state: tuple) -> bool:
    return state[0] == puzzle.data['goal'] and state[1]


class Walk(longwalk.Walk):
    move = staticmethod(move)
    far = staticmethod(far)
    done = staticmethod(done)
