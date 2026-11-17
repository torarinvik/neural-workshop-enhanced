# -*- coding: utf-8 -*-
"""What can be said of a panel of glyphs, and the rules made of it.

Odd One Out and Which Side? both show panels that follow a rule (and
one or some that do not), and both must be sure the rule they meant is
the only one the panels allow -- or at least that every rule the panels
allow gives the same answer. So the rules are not written by hand: a
panel's **features** are listed here (``colour is 2``, ``the two glyphs
share a shape``), a rung's rule space is built out of them, and the
deal checks its panels against the whole space.

A panel is a tuple of glyphs: one, or a pair.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from itertools import combinations
from typing import FrozenSet, List, Sequence, Tuple

from . import shapekit as G

Panel = Tuple[G.Glyph, ...]
Feature = Tuple
#: Properties a rule may be about, with how many values each has
#: (shape and colour take theirs from the look).
SAID = ('shape', 'colour', 'size', 'fill', 'count')


def values(lk: G.Look, attr: str) -> Sequence[int]:
    if attr == 'shape':
        return range(len(lk.shapes))
    if attr == 'colour':
        return range(len(lk.colours))
    if attr == 'count':
        return range(1, G.COUNTS + 1)
    return range(G.domain(attr))


def features(lk: G.Look, panel: Panel,
             attrs: Sequence[str] = SAID) -> FrozenSet[Feature]:
    """Every feature *panel* has."""
    out = set()
    for g in panel:
        for a in attrs:
            out.add(('has', a, getattr(g, a)))
    if len(panel) == 2:
        x, y = panel
        for a in attrs:
            if getattr(x, a) == getattr(y, a):
                out.add(('same', a))
    return frozenset(out)


def vocabulary(lk: G.Look, pairs: bool,
               attrs: Sequence[str] = SAID) -> List[Feature]:
    """Every feature a panel of this kind could have."""
    out = [('has', a, v) for a in attrs for v in values(lk, a)]
    if pairs:
        out += [('same', a) for a in attrs]
    return out


Rule = Tuple[str, Tuple]           # ('lit', f) ('not', f) ('and', f, g)...


def holds(rule, feats: FrozenSet[Feature]) -> bool:
    kind = rule[0]
    if kind == 'lit':
        return rule[1] in feats
    if kind == 'not':
        return rule[1] not in feats
    if kind == 'and':
        return holds(rule[1], feats) and holds(rule[2], feats)
    if kind == 'or':
        return holds(rule[1], feats) or holds(rule[2], feats)
    raise ValueError(rule)


def space(vocab: Sequence[Feature], negate: bool, conj: bool,
          disj: bool) -> List[Rule]:
    """The rules of a rung, from its vocabulary."""
    lits = [('lit', f) for f in vocab]
    if negate:
        lits += [('not', f) for f in vocab]
    rules: List[Rule] = list(lits)
    if conj:
        rules += [('and', a, b) for a, b in combinations(lits, 2)]
    if disj:
        rules += [('or', a, b) for a, b in combinations(lits, 2)]
    return rules


def say(rule) -> str:
    """A rule in words, for the verdict."""
    kind = rule[0]
    if kind in ('lit', 'not'):
        f = rule[1]
        if f[0] == 'same':
            words = 'both share a %s' % f[1]
        else:
            words = '%s %s' % (f[1], f[2])
        return ('not ' if kind == 'not' else '') + words
    joint = ' and ' if kind == 'and' else ' or '
    return say(rule[1]) + joint + say(rule[2])
