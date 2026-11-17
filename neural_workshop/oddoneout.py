# -*- coding: utf-8 -*-
"""Odd One Out: every panel but one shares something; which one?

A row of panels, each holding a glyph -- or, higher up, a pair. All of
them but one share a property: the same colour, the same number of
copies, a pair that agrees in shape. The one that does not is the
answer. Every deal has its own look.

"Shares" is checked, not hoped for: every feature a panel can have
(see :mod:`neural_workshop.features`) is tried, and a deal is kept only
when the panel it means is the only one any feature singles out.

The ladder:

* rungs 1-3: three panels of one glyph, alike in everything but the
  odd property and one or two others;
* rungs 4-6: four panels, every other property free;
* rungs 7-9: pairs -- the odd pair is the one whose two glyphs do not
  share what the others' do;
* rungs 10-12: five panels, and the odd pair may be the one that *does*
  share it;
* from rung 13: a panel more every three rungs, to eight; from rung 16
  the odd panel is one property away from another panel.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import features as F
from . import shapekit as G
from .i18n import _


class Grade(NamedTuple):
    rung: int
    panels: int
    pairs: bool
    vary: int            # free properties (single panels); 9 for all
    flip: bool           # the odd pair may be the one that shares
    near: bool           # the odd one is a property from another panel


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        panels=(3 if r < 4 else 4 if r < 10 else 5 if r < 13
                else min(8, 5 + (r - 13) // 3)),
        pairs=r >= 7,
        vary=(1 if r == 1 else 2 if r < 4 else 9),
        flip=r >= 10,
        near=r >= 16)


class Puzzle(NamedTuple):
    level: Grade
    look: G.Look
    panels: List[F.Panel]
    rule: Tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def odd_candidates(lk: G.Look, panels: List[F.Panel]) -> set:
    """Every panel some feature singles out: one lacks what all the
    rest have, or (for pairs) one shares what the rest do not."""
    pairs = len(panels[0]) == 2
    feats = [F.features(lk, p) for p in panels]
    n = len(panels)
    out = set()
    for f in F.vocabulary(lk, pairs):
        have = [k for k in range(n) if f in feats[k]]
        if len(have) == n - 1:
            out.add(next(k for k in range(n) if k not in have))
        if f[0] == 'same' and len(have) == 1:
            out.add(have[0])
    return out


def solve(p: Puzzle) -> Optional[int]:
    found = odd_candidates(p.look, p.panels)
    return found.pop() if len(found) == 1 else None


def _glyph(lk, draw, base: G.Glyph, free) -> G.Glyph:
    g = base
    for a in free:
        if a == 'shape':
            g = g._replace(shape=draw.randrange(len(lk.shapes)))
        elif a == 'colour':
            g = g._replace(colour=draw.randrange(len(lk.colours)))
        elif a == 'count':
            g = g._replace(count=draw.randint(1, 3))
        else:
            g = g._replace(**{a: draw.randrange(G.domain(a))})
    return g


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.panels
    for _attempt in range(5000):
        lk = G.look(draw, shapes=6, colours=4)
        attr = draw.choice(F.SAID)
        odd = draw.randrange(n)
        others = [a for a in F.SAID if a != attr]
        free = others if level.vary >= 9 else draw.sample(others, level.vary)
        base = G.random_glyph(draw, lk, turn=0)
        panels: List[F.Panel] = []
        if not level.pairs:
            v = getattr(base, attr)
            choices = [x for x in F.values(lk, attr) if x != v]
            if attr == 'count':
                choices = [x for x in choices if x <= 3]
            for k in range(n):
                g = _glyph(lk, draw, base, free)
                if k == odd:
                    g = g._replace(**{attr: draw.choice(choices)})
                panels.append((g,))
            rule = ('lit', ('has', attr, v))
        else:
            share = not (level.flip and draw.random() < 0.5)
            for k in range(n):
                a = _glyph(lk, draw, base, F.SAID)
                b = _glyph(lk, draw, base, F.SAID)
                want = share != (k == odd)
                if want:
                    b = b._replace(**{attr: getattr(a, attr)})
                elif getattr(a, attr) == getattr(b, attr):
                    vals = [x for x in F.values(lk, attr)
                            if x != getattr(a, attr)
                            and (attr != 'count' or x <= 3)]
                    b = b._replace(**{attr: draw.choice(vals)})
                panels.append((a, b))
            rule = ('lit' if share else 'not', ('same', attr))
        if level.near:
            j = draw.choice([k for k in range(n) if k != odd])
            # The odd panel becomes a copy of j but for the rule.
            if not level.pairs:
                panels[odd] = (panels[j][0]._replace(
                    **{attr: getattr(panels[odd][0], attr)}),)
            else:
                a, b = panels[odd]
                panels[odd] = (panels[j][0]._replace(**{attr: getattr(a, attr)}),
                               panels[j][1]._replace(**{attr: getattr(b, attr)}))
        if odd_candidates(lk, panels) != {odd}:
            continue
        if len({tuple(G.seen(lk, g) for g in p) for p in panels}) < n:
            continue
        return Puzzle(level, lk, panels, rule,
                      _('Which one is the odd one out?'),
                      tuple(str(k + 1) for k in range(n)), odd)
    raise RuntimeError('no odd one out for rung %d' % rung)
