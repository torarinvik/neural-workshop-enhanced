# -*- coding: utf-8 -*-
"""Which Block?: find what makes the machine go, by trying.

Some blocks and a machine with a lamp. Blocks put on the machine may
make it light -- some do, some do not -- and a few earlier tries are
shown: which blocks were on, and whether it lit. Then the player may
put any blocks on and run it, as many times as the tries allow, and
must say which block makes it go.

The earlier tries are dealt to **mislead**: past the first rungs the
block that matters was always on together with one that does not, so
watching cannot tell them apart and only a try can -- the difference
between seeing that two things go together and testing whether one
makes the other happen.

Ports: 0-7 put a block on the machine or take it off; 8 runs the
machine (a try); 9-16 name block 0-7 as the answer -- where the machine
needs two blocks, both must be named, one after the other.

The ladder:

* rungs 1-3: three blocks, one that works, and a try that already shows
  it on its own;
* rungs 4-6: four blocks; the one that works was only ever seen with
  another; two tries;
* rungs 7-9: five blocks, two that were always together with it;
* rungs 10-12: the machine needs **two** blocks together; name both;
* rungs 13-15: six or seven blocks, tries only just enough;
* from rung 16: a block more every three rungs to eight, and the
  machine sometimes fails to light even when it should (one try in
  eight from rung 16, one in five from 22).

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from itertools import combinations
from typing import FrozenSet, List, NamedTuple, Optional, Tuple

from . import shapekit as G
from .i18n import _

MOST = 8
RUN = 8
NAME = 9          # ports 9..16 name block 0..7


class Grade(NamedTuple):
    rung: int
    blocks: int
    pair: bool           # the machine needs two blocks together
    shown_alone: bool    # an earlier try shows the cause on its own
    decoys: int          # blocks always seen with the cause
    spare: int           # tries past what the reference needs
    misfire: float       # chance the machine fails to light


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        blocks=(3 if r < 4 else 4 if r < 7 else 5 if r < 13 else 6 + r % 2
                if r < 16 else min(MOST, 6 + (r - 13) // 3)),
        pair=r >= 10,
        shown_alone=r < 4,
        decoys=0 if r < 4 else 1 if r < 7 else 2,
        spare=2 if r < 7 else 1 if r < 13 else 0,
        misfire=0.0 if r < 16 else 0.125 if r < 22 else 0.2)


Rule = FrozenSet[int]     # the blocks that must all be on


class Machine(NamedTuple):
    level: Grade
    look: G.Look
    blocks: List[G.Glyph]
    rule: Rule
    seen: List[Tuple[FrozenSet[int], bool]]
    tries: int
    seed: int


def lights(rule: Rule, on: FrozenSet[int]) -> bool:
    return rule <= on


def hypotheses(level: Grade) -> List[Rule]:
    n = level.blocks
    out = [frozenset({k}) for k in range(n)]
    if level.pair:
        out += [frozenset(c) for c in combinations(range(n), 2)]
    return out


def weights(level: Grade, seen) -> List[Tuple[Rule, float]]:
    """Each rule the tries allow, with how well it explains them. A lit
    try rules out every rule it does not satisfy; a dark one, under a
    machine that never misfires, every rule it does -- and under one
    that does, only makes those rules less likely."""
    out = []
    for h in hypotheses(level):
        w = 1.0
        for on, lit in seen:
            if lit and not lights(h, on):
                w = 0.0
                break
            if not lit and lights(h, on):
                w *= level.misfire
                if w == 0.0:
                    break
        if w > 0:
            out.append((h, w))
    return out


def standing(level: Grade, seen) -> List[Rule]:
    return [h for h, _w in weights(level, seen)]


#: How sure the reference must be before it answers a misfiring machine.
SURE = 0.97


def settled(level: Grade, seen) -> Optional[Rule]:
    """The rule to name, once the tries make it sure enough."""
    ws = weights(level, seen)
    if not ws:
        return None
    total = sum(w for _h, w in ws)
    h, w = max(ws, key=lambda hw: hw[1])
    if level.pair:
        return h if w / total >= SURE else None
    # One block works: name it once its weight is sure.
    return h if w / total >= SURE else None


class Run:
    def __init__(self, m: Machine) -> None:
        self.m = m
        self.on: set = set()
        self.seen = list(m.seen)
        self.used = 0
        self.lit: Optional[bool] = None
        self.named: List[int] = []
        self.result: Optional[Tuple[bool, str]] = None
        self.draw = random.Random(m.seed)

    @property
    def left(self) -> int:
        return self.m.tries - self.used

    def act(self, port: int) -> None:
        if self.result is not None:
            return
        n = self.m.level.blocks
        if 0 <= port < n:
            self.on ^= {port}
            self.lit = None
        elif port == RUN and self.left > 0:
            on = frozenset(self.on)
            lit = lights(self.m.rule, on) and \
                self.draw.random() >= self.m.level.misfire
            self.seen.append((on, lit))
            self.lit = lit
            self.used += 1
        elif NAME <= port < NAME + n:
            k = port - NAME
            if k in self.named:
                return
            self.named.append(k)
            if len(self.named) < len(self.m.rule):
                return
            right = set(self.named) == set(self.m.rule)
            self.result = (right, (_('Right: that is what works') if right
                                   else _('No: that is not what works')))


class Pilot:
    """The reference: tries what splits the standing rules most evenly,
    and names a block once every standing rule needs it."""

    def __init__(self) -> None:
        self.queue: List[int] = []

    def next(self, run: Run) -> int:
        if self.queue:
            return self.queue.pop(0)
        level = run.m.level
        answer = settled(level, run.seen)
        if answer is not None or run.left <= 0:
            if answer is None:
                ws = weights(level, run.seen)
                answer = max(ws, key=lambda hw: hw[1])[0] if ws \
                    else frozenset({0})
            self.queue = [NAME + k for k in sorted(answer)]
            return self.queue.pop(0)
        ws = weights(level, run.seen)
        best, score = None, -1.0
        n = level.blocks
        tries = [frozenset(c) for size in ((1, 2) if level.pair else (1,))
                 for c in combinations(range(n), size)]
        if level.pair:
            tries += [frozenset(range(n)) - {k} for k in range(n)]
        for on in tries:
            # The weight on each side of the try: the more even, the
            # more any answer tells.
            yes = sum(w for h, w in ws if lights(h, on))
            s = min(yes, sum(w for _h, w in ws) - yes)
            if s > score:
                best, score = on, s
        want = set(best)
        self.queue = [k for k in range(n) if (k in run.on) != (k in want)]
        self.queue.append(RUN)
        return self.queue.pop(0)


def play(m: Machine) -> Run:
    run = Run(m)
    pilot = Pilot()
    for _k in range(300):
        if run.result is not None:
            break
        run.act(pilot.next(run))
    return run


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Machine:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.blocks
    for _attempt in range(500):
        lk = G.look(draw, shapes=max(6, n), colours=4)
        shapes = draw.sample(range(len(lk.shapes)), n)
        blocks = [G.Glyph(s, k % len(lk.colours), 1, 1, 0, 0, -1)
                  for k, s in enumerate(shapes)]
        rule = frozenset(draw.sample(range(n), 2 if level.pair else 1))
        others = [k for k in range(n) if k not in rule]
        decoys = set(draw.sample(others, min(level.decoys, len(others))))
        seen = []
        if level.shown_alone:
            seen.append((rule, True))
        for _k in range(draw.randint(2, 3)):
            on = set(rule) | decoys
            on |= {k for k in others if draw.random() < 0.3}
            seen.append((frozenset(on), True))
        for _k in range(draw.randint(1, 2)):
            on = frozenset(k for k in others if k not in decoys
                           and draw.random() < 0.6)
            if on:
                seen.append((on, False))
        draw.shuffle(seen)
        if level.decoys and settled(level, seen) is not None:
            continue
        m = Machine(level, lk, blocks, rule, seen, 99, draw.randrange(1 << 30))
        ref = play(m)
        if not ref.result or not ref.result[0]:
            continue
        tries = ref.used + level.spare
        if level.misfire:
            tries += 1
        return m._replace(tries=max(1, tries))
    raise RuntimeError('no machine for rung %d' % rung)
