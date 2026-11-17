# -*- coding: utf-8 -*-
"""Who Lives Where?: houses in a row, picture clues, and one question.

Houses stand in a row, numbered from the left. Each has one of every
kind of thing -- a colour, a pet (a shape), a number of lamps, a letter
on the door -- and no two houses share one. The clues are pictures:

* ``A = B``   A and B are at the same house;
* ``A ≠ B``   they are not;
* ``A | B``   A's house is just left of B's;
* ``A … B``   A's is somewhere left of B's;
* ``A ↔ B``   their houses are next to each other;
* ``A @ n``   A is at house n.

Which house has the asked thing? The clues are always enough for that
-- not always for everything else -- and none can be dropped.

The ladder:

* rungs 1-3: three houses, colours and pets, "same" and "at" clues;
* rungs 4-6: three kinds of thing; "not" and "just left of";
* rungs 7-9: four houses; "next to" and "somewhere left of";
* rungs 10-12: four kinds of thing;
* rungs 13-15: five houses;
* rungs 16-21: six houses;
* from rung 22: a fifth kind of thing, and every rung after it makes
  the clues weaker -- fewer "at" and "same", more "somewhere left of",
  "next to" and "not" -- so more of them must be chained.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from .i18n import _

KINDS = ('colour', 'pet', 'lamps', 'letter', 'flag')
SAME, NOT, LEFT, BEFORE, NEXT, AT = 'same', 'not', 'left', 'before', 'next', 'at'

Thing = Tuple[int, int]            # (kind, value)
Clue = Tuple[str, Thing, object]   # AT: object is a house index


class Grade(NamedTuple):
    rung: int
    houses: int
    kinds: int
    clues: Tuple[str, ...]


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    clues = (SAME, AT)
    if r >= 4:
        clues += (NOT, LEFT)
    if r >= 7:
        clues += (NEXT, BEFORE)
    return Grade(
        rung=r,
        houses=3 if r < 7 else 4 if r < 13 else 5 if r < 16 else 6,
        kinds=2 if r < 4 else 3 if r < 10 else 4 if r < 22 else 5,
        clues=clues)


class Puzzle(NamedTuple):
    level: Grade
    where: Dict[Thing, int]       # the solution
    clues: List[Clue]
    asked: Thing
    seed: int                     # for how things look
    question: str
    choices: Tuple[str, ...]
    answer: int


def true_of(clue: Clue, where: Dict[Thing, int]) -> Optional[bool]:
    """Whether *clue* holds of a (maybe partial) placing; None when it
    cannot be told yet."""
    kind, a, b = clue
    x = where.get(a)
    if kind == AT:
        return None if x is None else x == b
    y = where.get(b)
    if x is None or y is None:
        return None
    return {SAME: x == y, NOT: x != y, LEFT: x + 1 == y, BEFORE: x < y,
            NEXT: abs(x - y) == 1}[kind]


def _allowed(kind: str, x: int, n: int, first: bool) -> set:
    """Houses the other end of a clue may take, given this end at *x*
    (*first*: this end is the clue's first thing)."""
    if kind == SAME:
        return {x}
    if kind == NOT:
        return set(range(n)) - {x}
    if kind == NEXT:
        return {h for h in (x - 1, x + 1) if 0 <= h < n}
    if kind == LEFT:
        h = x + 1 if first else x - 1
        return {h} if 0 <= h < n else set()
    if kind == BEFORE:
        return set(range(x + 1, n)) if first else set(range(0, x))
    raise ValueError(kind)


def _propagate(dom, clues, n: int, kinds: int) -> bool:
    """Narrow *dom* in place until nothing changes; False when some
    thing is left nowhere to go."""
    changed = True
    while changed:
        changed = False
        for c in clues:
            kind, a, b = c
            if kind == AT:
                continue
            for x, y, first in ((a, b, True), (b, a, False)):
                ok = set()
                for h in dom[x]:
                    ok |= _allowed(kind, h, n, first)
                if not dom[y] <= ok:
                    dom[y] &= ok
                    if not dom[y]:
                        return False
                    changed = True
        for k in range(kinds):
            row = [(k, v) for v in range(n)]
            for t in row:
                if len(dom[t]) == 1:
                    h = next(iter(dom[t]))
                    for u in row:
                        if u != t and h in dom[u]:
                            dom[u].discard(h)
                            if not dom[u]:
                                return False
                            changed = True
            for h in range(n):
                can = [t for t in row if h in dom[t]]
                if not can:
                    return False
                if len(can) == 1 and len(dom[can[0]]) > 1:
                    dom[can[0]] = {h}
                    changed = True
    return True


def answers(level: Grade, clues: List[Clue], asked: Thing,
            stop: int = 2) -> set:
    """Houses *asked* can be at, over every placing the clues allow
    (stopping once *stop* are found): propagation, then a guess on the
    least certain thing, and propagation again."""
    n, kinds = level.houses, level.kinds
    dom = {(k, v): set(range(n)) for k in range(kinds) for v in range(n)}
    for c in clues:
        if c[0] == AT:
            dom[c[1]] &= {c[2]}
    found: set = set()

    def go(dom) -> bool:
        if not _propagate(dom, clues, n, kinds):
            return False
        if dom[asked] <= found:
            return False
        open_ = [t for t in dom if len(dom[t]) > 1]
        if not open_:
            found.add(next(iter(dom[asked])))
            return len(found) >= stop
        t = asked if len(dom[asked]) > 1 else \
            min(open_, key=lambda u: len(dom[u]))
        for h in sorted(dom[t]):
            if t == asked and h in found:
                continue
            new = {u: set(v) for u, v in dom.items()}
            new[t] = {h}
            if go(new):
                return True
        return False

    go(dom)
    return found


def solve(p: Puzzle) -> Optional[int]:
    got = answers(p.level, p.clues, p.asked)
    return got.pop() if len(got) == 1 else None


def _clue(level: Grade, where: Dict[Thing, int], draw: random.Random
          ) -> Optional[Clue]:
    kind = draw.choice(level.clues)
    weak = min(0.85, max(0.0, (level.rung - 20) * 0.05))
    if kind in (AT, SAME) and draw.random() < weak:
        kind = draw.choice([c for c in level.clues if c not in (AT, SAME)]
                           or level.clues)
    things = list(where)
    a = draw.choice(things)
    if kind == AT:
        return (AT, a, where[a])
    for _k in range(30):
        b = draw.choice(things)
        if b == a or b[0] == a[0] and kind == SAME:
            continue
        if b[0] == a[0] and kind == NOT:
            continue
        c = (kind, a, b)
        if true_of(c, where):
            return c
    return None


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.houses
    for _attempt in range(200):
        where: Dict[Thing, int] = {}
        for k in range(level.kinds):
            houses = list(range(n))
            draw.shuffle(houses)
            for v in range(n):
                where[(k, v)] = houses[v]
        asked = (draw.randrange(level.kinds), draw.randrange(n))
        clues: List[Clue] = []
        for _k in range(n * level.kinds * 6):
            c = _clue(level, where, draw)
            if c is None or c in clues:
                continue
            if c[0] == AT and c[1] == asked:
                continue
            clues.append(c)
            if len(answers(level, clues, asked)) == 1:
                break
        else:
            continue
        if len(answers(level, clues, asked)) != 1:
            continue
        # Drop what is not needed.
        draw.shuffle(clues)
        k = 0
        while k < len(clues):
            trial = clues[:k] + clues[k + 1:]
            if len(answers(level, trial, asked)) == 1:
                clues = trial
            else:
                k += 1
        if len(clues) < 2:
            continue
        return Puzzle(level, where, clues, asked, draw.randrange(1 << 30),
                      _('Which house has this?'),
                      tuple(str(h + 1) for h in range(n)), where[asked])
    raise RuntimeError('no houses for rung %d' % rung)
