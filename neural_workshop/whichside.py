# -*- coding: utf-8 -*-
"""Which Side?: six panels follow a rule, six do not; where does this go?

Left of a line, panels that all follow a rule nobody states; right of
it, panels that all break it. A new panel comes: left or right? The
rule has to be found from the examples alone -- nothing can be tried.

Every rule a rung allows is checked against the examples (see
:mod:`neural_workshop.features`), and a deal is kept only when every
rule they leave standing sends the new panel the same way. So the
answer is never a matter of which rule one happened to think of.

The ladder:

* rungs 1-3: one glyph a panel; the rule is one property's value --
  "red", "three copies";
* rungs 4-6: or its opposite -- "not a star";
* rungs 7-9: or two of those at once -- "large and hollow";
* rungs 10-12: or either of two -- "red or a circle";
* rungs 13-15: pairs, and rules about the pair -- "the two share a
  colour" -- as well;
* from rung 16: fewer examples a side, down to three, and the new panel
  a property away from one of them.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import features as F
from . import shapekit as G
from .i18n import _

LEFT, RIGHT = 0, 1


class Grade(NamedTuple):
    rung: int
    examples: int        # a side
    negate: bool
    conj: bool
    disj: bool
    pairs: bool
    near: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        examples=6 if r < 16 else max(3, 6 - (r - 14) // 3),
        negate=r >= 4,
        conj=r >= 7,
        disj=r >= 10,
        pairs=r >= 13,
        near=r >= 16)


class Puzzle(NamedTuple):
    level: Grade
    look: G.Look
    left: List[F.Panel]
    right: List[F.Panel]
    query: F.Panel
    rule: Tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def _rules(level: Grade, lk: G.Look):
    vocab = F.vocabulary(lk, level.pairs)
    return F.space(vocab, level.negate, level.conj, level.disj)


def standing(lk: G.Look, rules, left, right) -> list:
    """The rules every example agrees with."""
    fl = [F.features(lk, p) for p in left]
    fr = [F.features(lk, p) for p in right]
    return [r for r in rules
            if all(F.holds(r, f) for f in fl)
            and not any(F.holds(r, f) for f in fr)]


def solve(p: Puzzle, rules=None) -> Optional[int]:
    rules = rules if rules is not None else _rules(p.level, p.look)
    left = standing(p.look, rules, p.left, p.right)
    fq = F.features(p.look, p.query)
    sides = {LEFT if F.holds(r, fq) else RIGHT for r in left}
    return sides.pop() if len(sides) == 1 else None


def _panel(level, lk, draw) -> F.Panel:
    def one():
        return G.random_glyph(draw, lk, turn=0, count=draw.randint(1, 3))
    return (one(), one()) if level.pairs else (one(),)


def _pick(level: Grade, rules, draw: random.Random):
    """A rule of the rung's own kind, so the hardest kind turns up."""
    kinds = ['lit']
    if level.negate:
        kinds.append('not')
    if level.conj:
        kinds.append('and')
    if level.disj:
        kinds.append('or')
    want = kinds[-1] if draw.random() < 0.5 else draw.choice(kinds)
    of = [r for r in rules if r[0] == want]
    if level.pairs and draw.random() < 0.6:
        rel = [r for r in of if 'same' in repr(r)]
        of = rel or of
    return draw.choice(of)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    for _attempt in range(3000):
        lk = G.look(draw, shapes=5, colours=4)
        rules = _rules(level, lk)
        rule = _pick(level, rules, draw)
        left: List[F.Panel] = []
        right: List[F.Panel] = []
        for _k in range(400):
            if len(left) >= level.examples and len(right) >= level.examples:
                break
            p = _panel(level, lk, draw)
            side = left if F.holds(rule, F.features(lk, p)) else right
            if len(side) < level.examples:
                side.append(p)
        if len(left) < level.examples or len(right) < level.examples:
            continue
        answer = draw.choice((LEFT, RIGHT))
        query = None
        for _k in range(200):
            if level.near:
                q = draw.choice(left + right)
                g = list(q)
                i = draw.randrange(len(g))
                a = draw.choice(F.SAID)
                vals = [v for v in F.values(lk, a)
                        if v != getattr(g[i], a) and (a != 'count' or v <= 3)]
                g[i] = g[i]._replace(**{a: draw.choice(vals)})
                q = tuple(g)
            else:
                q = _panel(level, lk, draw)
            if F.holds(rule, F.features(lk, q)) == (answer == LEFT):
                query = q
                break
        if query is None:
            continue
        p = Puzzle(level, lk, left, right, query, rule,
                   _('Does the new panel belong on the left or the right?'),
                   (_('Left'), _('Right')), answer)
        if solve(p, rules) != answer:
            continue
        return p
    raise RuntimeError('no Which Side? puzzle for rung %d' % rung)
