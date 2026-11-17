# -*- coding: utf-8 -*-
"""Button Box: what does each button do? Make the figure match.

A figure on a screen, a target figure beside it, and a row of buttons.
Each button does one thing to the figure -- turns it, recolours it,
grows it, moves it a cell, changes its shape -- and which button does
what is dealt afresh every trial. Pressing is the only way to find out,
and presses are counted: match the target before they run out. Reset
puts the figure back where it started, and costs nothing.

So this is a task where pressing changes the frame, and where finding
out what the actions do is the whole of it. Every property wraps round
(the last colour steps to the first, the right edge to the left), so
every press can be undone by pressing on.

The ladder:

* rungs 1-3: two or three buttons, the target one press away, presses
  to spare;
* rungs 4-6: four buttons, two presses away;
* rungs 7-9: five or six buttons, three away; a button may do nothing;
* rungs 10-12: a button may do two things at once; no presses spare
  past what finding out and doing need;
* from rung 13: a button more every two rungs, to twelve, and the
  target a press farther every three, to ten.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from collections import deque
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import shapekit as G
from .i18n import _

#: Ports 0-11 press buttons; port 12 resets.
RESET = 12
MOST = 12

#: A state: shape, colour, size, turn, fill, cell -- all wrapping.
State = Tuple[int, int, int, int, int, int]
SIZES = 3
#: What a button can do: (property, step).
EFFECTS = (('shape', 1), ('colour', 1), ('colour', -1), ('size', 1),
           ('turn', 1), ('turn', 2), ('turn', -1), ('fill', 1),
           ('col', 1), ('col', -1), ('row', 1), ('row', -1))
FIELDS = ('shape', 'colour', 'size', 'turn', 'fill', 'col', 'row')


class Grade(NamedTuple):
    rung: int
    buttons: int
    distance: int
    spare: int
    duds: bool
    doubles: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        buttons=(2 if r == 1 else 3 if r < 4 else 4 if r < 7 else 5 + r % 2
                 if r < 13 else min(MOST, 6 + (r - 13) // 2)),
        distance=(1 if r < 4 else 2 if r < 7 else 3 if r < 13
                  else min(10, 3 + (r - 10) // 3)),
        spare=3 if r < 4 else 2 if r < 7 else 1 if r < 10 else 0,
        duds=r >= 7,
        doubles=r >= 10)


Effect = Tuple[Tuple[str, int], ...]


class Box(NamedTuple):
    level: Grade
    look: G.Look
    start: Dict[str, int]
    target: Dict[str, int]
    buttons: List[Effect]
    budget: int
    hues: List[Tuple[int, int, int]]      # each button's colour


def _sizes(lk: G.Look) -> Dict[str, int]:
    return {'shape': len(lk.shapes), 'colour': len(lk.colours),
            'size': SIZES, 'turn': G.TURNS, 'fill': G.FILLS,
            'col': 3, 'row': 3}


def press(lk: G.Look, state: Dict[str, int], effect: Effect
          ) -> Dict[str, int]:
    n = _sizes(lk)
    out = dict(state)
    for field, step in effect:
        out[field] = (out[field] + step) % n[field]
    return out


def key(state: Dict[str, int]) -> Tuple[int, ...]:
    return tuple(state[f] for f in FIELDS)


def glyph(state: Dict[str, int]) -> G.Glyph:
    return G.Glyph(state['shape'], state['colour'], state['size'], 1,
                   state['turn'], state['fill'],
                   state['row'] * 3 + state['col'])


def distance(lk: G.Look, start, target, effects: List[Effect],
             cap: int = 14) -> Optional[int]:
    """Fewest presses from *start* to *target*, by breadth first."""
    goal = key(target)
    seen = {key(start)}
    todo = deque([(start, 0)])
    while todo:
        s, d = todo.popleft()
        if key(s) == goal:
            return d
        if d >= cap:
            continue
        for e in effects:
            t = press(lk, s, e)
            k = key(t)
            if k not in seen:
                seen.add(k)
                todo.append((t, d + 1))
    return None


class Run:
    """One trial: the figure as it stands and the presses spent."""

    def __init__(self, box: Box) -> None:
        self.box = box
        self.state = dict(box.start)
        self.used = 0
        self.result: Optional[Tuple[bool, str]] = None
        self.last: Optional[int] = None

    @property
    def left(self) -> int:
        return self.box.budget - self.used

    def matched(self) -> bool:
        return key(self.state) == key(self.box.target)

    def act(self, port: int) -> None:
        if self.result is not None:
            return
        if port == RESET:
            self.state = dict(self.box.start)
            self.last = RESET
            return
        if not 0 <= port < len(self.box.buttons):
            return
        self.state = press(self.box.look, self.state, self.box.buttons[port])
        self.used += 1
        self.last = port
        if self.matched():
            self.result = (True, _('Matched in %d presses') % self.used)
        elif self.left <= 0:
            self.result = (False, _('Out of presses'))


class Pilot:
    """The reference player: tries each button once from the start,
    resetting after it, and then takes the shortest way."""

    def __init__(self, box: Box) -> None:
        self.known: Dict[int, Effect] = {}
        self.plan: List[int] = []
        self.box = box
        self.trying: Optional[int] = None
        self.before: Optional[Dict[str, int]] = None

    def next(self, run: Run) -> int:
        box = self.box
        if self.trying is not None:
            self.known[self.trying] = tuple(
                (f, (run.state[f] - self.before[f]) % _sizes(box.look)[f])
                for f in FIELDS if run.state[f] != self.before[f])
            self.trying = None
            return RESET
        unknown = [k for k in range(len(box.buttons)) if k not in self.known]
        if unknown:
            self.trying = unknown[0]
            self.before = dict(run.state)
            return unknown[0]
        if not self.plan:
            self.plan = path(box.look, run.state, box.target,
                             {k: e for k, e in self.known.items()})
        return self.plan.pop(0)


def path(lk, start, target, effects: Dict[int, Effect]) -> List[int]:
    goal = key(target)
    seen = {key(start): None}
    todo = deque([start])
    while todo:
        s = todo.popleft()
        if key(s) == goal:
            out = []
            k = key(s)
            while seen[k] is not None:
                k, b = seen[k]
                out.append(b)
            return out[::-1]
        for b, e in effects.items():
            t = press(lk, s, e)
            if key(t) not in seen:
                seen[key(t)] = (key(s), b)
                todo.append(t)
    return []


def play(box: Box) -> Run:
    run = Run(box)
    pilot = Pilot(box)
    for _k in range(400):
        if run.result is not None:
            break
        run.act(pilot.next(run))
    return run


HUES = ((230, 90, 80), (70, 140, 230), (250, 190, 50), (80, 190, 110),
        (170, 100, 220), (240, 140, 60), (60, 190, 200), (230, 110, 170),
        (140, 140, 150), (120, 170, 60), (200, 160, 110), (100, 110, 200))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Box:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    for _attempt in range(500):
        lk = G.look(draw, shapes=4, colours=4, oriented=True)
        pool: List[Tuple[str, int]] = []

        def take() -> Tuple[str, int]:
            if not pool:
                pool.extend(EFFECTS)
                draw.shuffle(pool)
            return pool.pop()
        buttons: List[Effect] = []
        for k in range(level.buttons):
            if level.duds and draw.random() < 0.12:
                buttons.append(())
            elif level.doubles and draw.random() < 0.3:
                a, b = take(), take()
                if a[0] == b[0]:
                    b = ('shape', 1) if a[0] != 'shape' else ('fill', 1)
                buttons.append((a, b))
            else:
                buttons.append((take(),))
        start = {'shape': draw.randrange(4), 'colour': draw.randrange(4),
                 'size': draw.randrange(SIZES), 'turn': draw.randrange(8),
                 'fill': draw.randrange(G.FILLS), 'col': draw.randrange(3),
                 'row': draw.randrange(3)}
        state = dict(start)
        live = [k for k, e in enumerate(buttons) if e]
        for _k in range(level.distance):
            state = press(lk, state, buttons[draw.choice(live)])
        # A long walk often doubles back; a target most of its length
        # away is far enough.
        far = distance(lk, start, state, buttons)
        if far is None or far < max(1, (level.distance * 7 + 9) // 10):
            continue
        box = Box(level, lk, start, state, buttons, 99,
                  draw.sample(HUES, level.buttons))
        ref = play(box)
        if not ref.result or not ref.result[0]:
            continue
        return box._replace(budget=ref.used + level.spare)
    raise RuntimeError('no button box for rung %d' % rung)
