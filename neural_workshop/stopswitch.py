# -*- coding: utf-8 -*-
"""Stop & Switch: answer fast by the rule, unless told to stop.

A block is a stream of stimuli -- a circle or a square, blue or orange,
in the middle or off to one side -- each answered Left or Right by the
rule shown above it:

* SHAPE: circle left, square right;
* COLOUR: blue left, orange right;
* OPPOSITE: the side away from where it is.

Sometimes, a moment after a stimulus appears, a red ring closes round
it: stop -- do not answer at all. A block passes when enough answers
are right: in time, by the rule in force, and none at all to a stop.

* rungs 1-3: SHAPE only, in the middle; the time to answer shrinks
  from 1.5 seconds to 1.1;
* rungs 4-6: stop signals on a quarter of the stimuli, coming 0.10 to
  0.20 seconds after the stimulus;
* rungs 7-9: stimuli off to one side, a side that has nothing to do
  with the answer;
* rungs 10-12: SHAPE and COLOUR take turns, the rule changing every four
  to six stimuli, shown ahead;
* rungs 13-15: the rule changes without a pattern, three times in ten;
* rungs 16-19: the rule shows only with the stimulus, no time to
  prepare; most stimuli point opposite ways under the two rules;
* from rung 20 OPPOSITE joins in, the stop comes later and the time to
  answer keeps shrinking; nine in ten must be right.

Clocked: speed is part of the answer.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

LEFT, RIGHT = 0, 1
RULES = {'shape': _('SHAPE'), 'colour': _('COLOUR'),
         'opposite': _('OPPOSITE')}
#: Seconds of blank (with the rule shown, unless it comes with the
#: stimulus) between one answer and the next stimulus.
GAP = 0.6


class Grade(NamedTuple):
    rung: int
    count: int
    window: float
    stops: float
    ssd: float
    sides: bool
    rules: Tuple[str, ...]
    switching: str        # 'none', 'cued', 'random'
    prepared: bool
    incongruent: float
    needed: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    count = 12 if r < 4 else (16 if r < 10 else 20)
    if r < 4:
        window = 1.5 - 0.2 * (r - 1)
    elif r < 16:
        window = 1.0 if r < 7 else 0.9
    elif r < 20:
        window = 0.8 - 0.03 * (r - 16)
    else:
        window = max(0.45, 0.68 - 0.025 * (r - 20))
    stops = 0.0 if r < 4 else (0.25 if r < 20 else 0.3)
    ssd = 0.0 if r < 4 else (0.1 + 0.05 * (r - 4) if r < 7 else
                             (0.2 if r < 16 else
                              (0.25 if r < 20 else
                               min(0.35, 0.25 + 0.01 * (r - 20)))))
    rules = ('shape',) if r < 10 else (('shape', 'colour') if r < 20 else
                                       ('shape', 'colour', 'opposite'))
    switching = 'none' if r < 10 else ('cued' if r < 13 else 'random')
    return Grade(rung=r, count=count, window=window, stops=stops, ssd=ssd,
                 sides=r >= 7, rules=rules, switching=switching,
                 prepared=r < 16, incongruent=0.7 if r >= 16 else 0.5,
                 needed=0.85 if r < 20 else 0.9)


class Stimulus(NamedTuple):
    shape: str           # 'circle' or 'square'
    colour: str          # 'blue' or 'orange'
    side: int            # -1 left, 0 middle, 1 right
    rule: str
    stop: bool


def answer(s: Stimulus) -> int:
    if s.rule == 'shape':
        return LEFT if s.shape == 'circle' else RIGHT
    if s.rule == 'colour':
        return LEFT if s.colour == 'blue' else RIGHT
    return RIGHT if s.side < 0 else LEFT


class Block(NamedTuple):
    rung: int
    level: Grade
    stimuli: Tuple[Stimulus, ...]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Block:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    out: List[Stimulus] = []
    rule = draw.choice(level.rules)
    left_in_run = draw.randint(4, 6)
    for k in range(level.count):
        if k:
            if level.switching == 'cued':
                left_in_run -= 1
                if left_in_run == 0:
                    rule = draw.choice([r for r in level.rules if r != rule])
                    left_in_run = draw.randint(4, 6)
            elif level.switching == 'random' and draw.random() < 0.3:
                rule = draw.choice([r for r in level.rules if r != rule])
        side = draw.choice((-1, 1)) if level.sides or rule == 'opposite' \
            else 0
        shape = draw.choice(('circle', 'square'))
        # Under two rules a stimulus can point the same way under both
        # or opposite ways; from rung 16 mostly opposite.
        same = draw.random() >= level.incongruent
        shape_way = LEFT if shape == 'circle' else RIGHT
        colour_way = shape_way if same else 1 - shape_way
        colour = 'blue' if colour_way == LEFT else 'orange'
        stop = k > 0 and draw.random() < level.stops
        out.append(Stimulus(shape, colour, side, rule, stop))
    return Block(level.rung, level, tuple(out))


def right(s: Stimulus, key: Optional[int], rt: Optional[float],
          level: Grade) -> bool:
    """Whether a reply (None for none) to *s* was right."""
    if s.stop:
        return key is None
    return key == answer(s) and rt is not None and rt <= level.window
