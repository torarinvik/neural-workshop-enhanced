# -*- coding: utf-8 -*-
"""Analogies: A is to B as C is to what?

Three glyphs, A, B and C, and a row of candidates. What turned A into B
-- a colour, a size, a number of copies, a turn, a fill, a shape, a
move across the panel -- has to be found and done to C. Every deal has
its own look (shapes and colours), so the relation is all that carries
from one to the next.

What changes are of two kinds, and the deal is careful about both:

* **becomes** -- colour, fill and shape: B *has* a colour, so C's answer
  has that colour;
* **steps** -- size, count, turn and place: B is a step from A, so C's
  answer is the same step from C.

From rung 10 C's value on a stepped property is not A's, so "the same
step" and "the same value" give different answers; only the step is
offered.

The ladder:

* rungs 1-3: one change, from colour, size, count and fill; three
  candidates;
* rungs 4-6: turning and shape join; four candidates;
* rungs 7-9: two changes at once;
* rungs 10-12: C's stepped values differ from A's; five candidates, most
  of them one property away from right;
* rungs 13-15: three changes; glyphs sit in places across the panel and
  may move;
* from rung 16: a change more every four rungs, to six, and up to
  eight candidates.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import shapekit as G
from .i18n import _

BECOMES = ('shape', 'colour', 'fill')
STEPS = ('size', 'count', 'turn', 'cell')


class Grade(NamedTuple):
    rung: int
    changes: int
    pool: Tuple[str, ...]
    choices: int
    shifted: bool        # C's stepped values differ from A's
    cells: bool          # glyphs sit in a 3 x 3 panel and may move


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    pool = ('colour', 'size', 'count', 'fill')
    if r >= 4:
        pool += ('turn', 'shape')
    if r >= 13:
        pool += ('cell',)
    return Grade(
        rung=r,
        changes=(1 if r < 7 else 2 if r < 13 else 3 if r < 16
                 else min(6, 3 + (r - 12) // 4)),
        pool=pool,
        choices=(3 if r < 4 else 4 if r < 10 else 5 if r < 16
                 else min(8, 6 + (r - 16) // 6)),
        shifted=r >= 10,
        cells=r >= 13)


class Puzzle(NamedTuple):
    level: Grade
    look: G.Look
    a: G.Glyph
    b: G.Glyph
    c: G.Glyph
    cards: List[G.Glyph]
    question: str
    choices: Tuple[str, ...]
    answer: int


Change = Dict[str, Tuple[str, object]]


def _cell_step(cell: int, step: Tuple[int, int]) -> Optional[int]:
    col, row = cell % 3 + step[0], cell // 3 + step[1]
    if not (0 <= col < 3 and 0 <= row < 3):
        return None
    return row * 3 + col


def apply(change: Change, g: G.Glyph) -> Optional[G.Glyph]:
    """*g* changed as *change* says, or None when the step runs off its
    range."""
    out = {}
    for attr, (kind, val) in change.items():
        if kind == 'becomes':
            out[attr] = val
        elif attr == 'cell':
            cell = _cell_step(g.cell, val)
            if cell is None:
                return None
            out[attr] = cell
        elif attr == 'turn':
            out[attr] = (g.turn + val) % G.TURNS
        else:
            v = getattr(g, attr) + val
            lo = 1 if attr == 'count' else 0
            hi = G.domain(attr) - (0 if attr != 'count' else -1) - 1
            if attr == 'count':
                hi = G.COUNTS
            if not lo <= v <= hi:
                return None
            out[attr] = v
    return g._replace(**out)


def infer(lk: G.Look, a: G.Glyph, b: G.Glyph) -> Change:
    """What turned *a* into *b*, as the reference reads it."""
    change: Change = {}
    for attr in G.ATTRS:
        x, y = getattr(a, attr), getattr(b, attr)
        if attr == 'turn':
            x, y = G.seen_turn(lk, a), G.seen_turn(lk, b)
        if x == y:
            continue
        if attr in BECOMES:
            change[attr] = ('becomes', y)
        elif attr == 'cell':
            change[attr] = ('steps', (y % 3 - x % 3, y // 3 - x // 3))
        elif attr == 'turn':
            change[attr] = ('steps', (y - x) % G.TURNS)
        else:
            change[attr] = ('steps', y - x)
    return change


def solve(p: Puzzle) -> Optional[int]:
    """The candidate the reference picks, by seeing."""
    want = apply(infer(p.look, p.a, p.b), p.c)
    if want is None:
        return None
    hits = [k for k, g in enumerate(p.cards)
            if G.seen(p.look, g) == G.seen(p.look, want)]
    return hits[0] if len(hits) == 1 else None


def _literal(lk, a: G.Glyph, b: G.Glyph, c: G.Glyph) -> Optional[G.Glyph]:
    """The other reading: C takes B's *values* on what changed."""
    out = {}
    for attr in G.differ(a, b):
        out[attr] = getattr(b, attr)
    try:
        return c._replace(**out)
    except Exception:
        return None


def _base(level: Grade, lk: G.Look, draw: random.Random) -> G.Glyph:
    g = G.random_glyph(draw, lk)
    g = g._replace(count=draw.randint(1, 3),
                   turn=draw.randrange(G.TURNS))
    if level.cells:
        g = g._replace(cell=draw.randrange(G.CELLS))
    return g


def _change(level: Grade, lk: G.Look, a: G.Glyph,
            draw: random.Random) -> Change:
    attrs = draw.sample(level.pool, level.changes)
    change: Change = {}
    for attr in attrs:
        if attr in BECOMES:
            n = {'shape': len(lk.shapes), 'colour': len(lk.colours),
                 'fill': G.FILLS}[attr]
            v = draw.choice([k for k in range(n) if k != getattr(a, attr)])
            change[attr] = ('becomes', v)
        elif attr == 'cell':
            change[attr] = ('steps', draw.choice(
                [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                 if (dx, dy) != (0, 0)]))
        elif attr == 'turn':
            change[attr] = ('steps', draw.choice((1, 2, 6, 7)))
        else:
            change[attr] = ('steps', draw.choice((-1, 1)))
    return change


def _near(level: Grade, lk: G.Look, g: G.Glyph,
          draw: random.Random) -> G.Glyph:
    """*g* with one property set otherwise."""
    attr = draw.choice(('colour', 'size', 'count', 'fill', 'shape', 'turn')
                       + (('cell',) if level.cells else ()))
    if attr == 'shape':
        return g._replace(shape=(g.shape + draw.randint(1, len(lk.shapes) - 1))
                          % len(lk.shapes))
    if attr == 'colour':
        return g._replace(colour=(g.colour + draw.randint(
            1, len(lk.colours) - 1)) % len(lk.colours))
    if attr == 'count':
        return g._replace(count=draw.choice(
            [k for k in range(1, G.COUNTS + 1) if k != g.count]))
    if attr == 'cell':
        return g._replace(cell=draw.choice(
            [k for k in range(G.CELLS) if k != g.cell]))
    n = G.domain(attr)
    return g._replace(**{attr: (getattr(g, attr) + draw.randint(1, n - 1))
                         % n})


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    for _attempt in range(2000):
        lk = G.look(draw, shapes=6, colours=4, oriented=True)
        a = _base(level, lk, draw)
        change = _change(level, lk, a, draw)
        b = apply(change, a)
        if b is None:
            continue
        c = _base(level, lk, draw)
        if not level.shifted:
            # C keeps A's stepped values, so step and value agree.
            c = c._replace(**{s: getattr(a, s) for s in STEPS
                              if s in change})
        c = c._replace(**{s: getattr(a, s) for s in BECOMES
                          if s in change and draw.random() < 0.5})
        answer = apply(change, c)
        if answer is None or len(G.differ(a, c)) < 1:
            continue
        if infer(lk, a, b) != change:
            continue
        seen_answer = G.seen(lk, answer)
        literal = _literal(lk, a, b, c)
        banned = {seen_answer}
        if literal is not None:
            banned.add(G.seen(lk, literal))
        others: List[G.Glyph] = []
        pool = [c, b]
        for attr in change:
            pool.append(answer._replace(**{attr: getattr(c, attr)}))
        pool += [_near(level, lk, answer, draw) for _k in range(12)]
        pool += [_near(level, lk, c, draw) for _k in range(4)]
        for g in pool:
            if len(others) >= level.choices - 1:
                break
            if g.count < 1 or g.count > G.COUNTS:
                continue
            key = G.seen(lk, g)
            if key in banned:
                continue
            banned.add(key)
            others.append(g)
        if len(others) < level.choices - 1:
            continue
        cards = others[:]
        where = random.Random(seed * 7 + 3).randrange(level.choices)
        cards.insert(where, answer)
        p = Puzzle(level, lk, a, b, c, cards,
                   _('A is to B as C is to which?'),
                   tuple(str(k + 1) for k in range(level.choices)), where)
        if solve(p) != where:
            continue
        return p
    raise RuntimeError('no analogy for rung %d' % rung)
