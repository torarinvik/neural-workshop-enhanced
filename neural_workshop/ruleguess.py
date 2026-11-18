# -*- coding: utf-8 -*-
"""Which Rule?: one hidden rule holds for the whole run; find it.

Every trial shows three things, each on its own card, and exactly one
of them is the right one to press. Which one is decided by a rule that
is drawn when the run starts and does not change: "the largest", "the
red one", "the round one". The rule is one of a short list of
candidates -- two at rung 1, one more with each rung -- and every press
is judged at once, so a wrong press rules candidates out and a right
one rules out the rest.

The three things differ in every way the rules look at: their sizes
and heights are all different, exactly one is red, one round, one
hollow, one dotted. Each of those lands on a card independently, so
two rules agree on a trial only by chance.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

#: In the order the ladder brings them in.
RULES = ('largest', 'red', 'round', 'hollow', 'smallest', 'highest',
         'dotted', 'lowest', 'left', 'right', 'middle')
NAMES = {
    'largest': _('the largest'), 'red': _('the red one'),
    'round': _('the round one'), 'hollow': _('the hollow one'),
    'smallest': _('the smallest'), 'highest': _('the highest'),
    'dotted': _('the dotted one'), 'lowest': _('the lowest'),
    'left': _('the left one'), 'right': _('the right one'),
    'middle': _('the middle one'),
}
RED = (208, 56, 48)
OTHER_HUES = ((36, 104, 196), (30, 140, 90), (150, 110, 20),
              (122, 70, 170), (20, 124, 132))
OTHER_SHAPES = ('square', 'triangle', 'diamond', 'cross')
PORTS = 3


def candidates(rung: int) -> Tuple[str, ...]:
    """The rules the hidden one may be, at this rung."""
    return RULES[:min(len(RULES), max(1, int(rung)) + 1)]


class Thing(NamedTuple):
    size: int                    # 0 small, 1 medium, 2 large
    height: int                  # 0 low, 1 middle, 2 high
    hue: Tuple[int, int, int]
    shape: str
    hollow: bool
    dotted: bool


class Puzzle(NamedTuple):
    rule: str
    things: Tuple[Thing, ...]    # one a card, left to right
    choices: Tuple[str, ...]
    answer: int
    question: str


def pick(rule: str, things) -> int:
    """The card *rule* points at."""
    if rule in ('left', 'middle', 'right'):
        return ('left', 'middle', 'right').index(rule)
    test = {
        'largest': lambda t: t.size == 2, 'smallest': lambda t: t.size == 0,
        'highest': lambda t: t.height == 2, 'lowest': lambda t: t.height == 0,
        'red': lambda t: t.hue == RED, 'round': lambda t: t.shape == 'circle',
        'hollow': lambda t: t.hollow, 'dotted': lambda t: t.dotted,
    }[rule]
    return next(k for k, thing in enumerate(things) if test(thing))


def deal(rule: str, rung: int,
         rng: Optional[random.Random] = None) -> Puzzle:
    rng = rng or random.Random()
    among = candidates(rung)
    while True:
        sizes = rng.sample(range(3), 3)
        heights = rng.sample(range(3), 3)
        red, round_, hollow, dotted = (rng.randrange(3) for _k in range(4))
        hues = rng.sample(OTHER_HUES, 3)
        shapes = [rng.choice(OTHER_SHAPES) for _k in range(3)]
        things = tuple(
            Thing(sizes[k], heights[k], RED if k == red else hues[k],
                  'circle' if k == round_ else shapes[k], k == hollow,
                  k == dotted)
            for k in range(3))
        # A trial every candidate agrees on would teach nothing.
        if len({pick(r, things) for r in among}) > 1:
            break
    return Puzzle(rule, things, ('1', '2', '3'), pick(rule, things),
                  _('One rule holds all run. Which one is it this time?'))


def draw_rule(rung: int, rng: Optional[random.Random] = None) -> str:
    """The run's hidden rule."""
    return (rng or random).choice(candidates(rung))


def left(puzzle_log: List[Tuple[Puzzle, int, bool]],
         rung: int) -> List[str]:
    """The candidates still standing after the presses in the log, each
    (puzzle, port pressed, whether it was right)."""
    out = []
    for rule in candidates(rung):
        if all((pick(rule, p.things) == port) == right
               for p, port, right in puzzle_log):
            out.append(rule)
    return out
