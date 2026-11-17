# -*- coding: utf-8 -*-
"""Turning written questions into rounds for :mod:`neural_workshop.feelings`.

The Social, Rationality and verbal tasks all ask the same way: a text,
a question, a few answers. This is what they share: answers shuffled
(so a player who always presses the same number is only guessing),
cut down to the number a rung offers (the right one always kept), time
to read by the length of the text, and long answers laid out one to a
row.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Callable, List, NamedTuple, Optional, Sequence

from . import feelings as F

#: An answer longer than this goes on a full-width row of its own.
WIDE = 30


class Pace(NamedTuple):
    base: float                # seconds every item gets
    wps: float                 # words a second the reader is given


def pace(rung: int, slow: float = 2.2, fast: float = 4.5,
         base: float = 6.0, floor: float = 2.5, over: int = 24) -> Pace:
    """Reading speed by rung: from *slow* words a second at rung 1 to
    *fast* at rung *over* and beyond, with the base time shrinking from
    *base* to *floor*."""
    k = min(1.0, max(0.0, (rung - 1) / float(over - 1)))
    return Pace(base + (floor - base) * k, slow + (fast - slow) * k)


def words(*texts: str) -> int:
    return sum(len(t.split()) for t in texts)


def seconds(p: Pace, *texts: str) -> float:
    return p.base + words(*texts) / p.wps


def step(ask: str, options: Sequence[str], answer: int,
         draw: random.Random, most: Optional[int] = None,
         keep_order: bool = False) -> F.Step:
    """A step with its answers shuffled and, given *most*, cut down to
    that many, the right one among them."""
    idx = list(range(len(options)))
    if most is not None and len(idx) > most:
        others = [i for i in idx if i != answer]
        draw.shuffle(others)
        idx = sorted([answer] + others[:most - 1])
    if not keep_order:
        draw.shuffle(idx)
    opts = tuple(options[i] for i in idx)
    return F.Step(ask, opts, idx.index(answer),
                  wide=max(len(o) for o in opts) > WIDE)


def item(prompt: str, steps: Sequence[F.Step], p: Pace, title: str = '',
         truth: Optional[str] = None) -> F.Item:
    texts = [prompt] + [s.ask for s in steps] + \
        [o for s in steps for o in s.options]
    secs = seconds(p, *texts) + 1.5 * (len(steps) - 1)
    if truth is None:
        truth = ', '.join(s.options[s.answer] for s in steps)
    return F.Item(prompt, tuple(steps), secs, truth=truth, title=title)


def chance(it: F.Item) -> float:
    c = 1.0
    for s in it.steps:
        c /= len(s.options)
    return c


def fixed_pass(items: Sequence[F.Item], need: int) -> bool:
    """Would pressing the same number every time pass? (A number past
    an item's last answer presses its last, as :func:`F.always` does.)"""
    for k in range(F.PORTS):
        right = sum(all(s.answer == min(k, len(s.options) - 1)
                        for s in it.steps) for it in items)
        if right >= need:
            return True
    return False


def assemble(level, items: Sequence[F.Item], skill: float,
             ceiling: float = 0.03) -> Optional[F.Round]:
    """A round whose pass bar no guesser reaches more than *ceiling* of
    the time, and never under *skill* of the items; ``None`` if the
    answers happen to fall so that one number pressed throughout would
    pass it (the deal then tries again)."""
    import math
    need = min(len(items), max(F.need_mixed([chance(i) for i in items],
                                            ceiling),
                               int(math.ceil(skill * len(items)))))
    if fixed_pass(items, need):
        return None
    return F.Round(level, tuple(items), need)


def deck(seq: Sequence, draw: random.Random) -> Callable[[], object]:
    """A shuffled deck of *seq* that starts over when it runs out;
    drawing from an empty one gives ``None``."""
    cards = list(seq)
    draw.shuffle(cards)
    at = [0]

    def deal_one():
        if not cards:
            return None
        card = cards[at[0] % len(cards)]
        at[0] += 1
        return card
    return deal_one


def mixed(kinds: Sequence[str], n: int, draw: random.Random,
          make: Callable[[str], Optional[F.Item]], tries: int = 400
          ) -> List[F.Item]:
    """*n* items, the kinds taken in turn from a shuffled cycle so each
    kind of the rung is asked about equally often."""
    order = [kinds[k % len(kinds)] for k in range(n)]
    draw.shuffle(order)
    out: List[F.Item] = []
    seen = set()
    spent = set()              # kinds with nothing new left: repeats now
    for kind in order:
        it = None
        for _t in range(1 if kind in spent else tries):
            got = make(kind)
            if got is None:
                continue
            if it is None:
                it = got
            if got.prompt not in seen:
                it = got
                break
        else:
            spent.add(kind)
        if it is not None:
            out.append(it)
            seen.add(it.prompt)
    return out
