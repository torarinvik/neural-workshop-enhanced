# -*- coding: utf-8 -*-
"""How an attribute changes across a row.

Raven's matrices are read along the rows. Every rule here takes the
panels of a row and says what one attribute does across them, and the
same rule governs all the rows — which is what makes the last row
answerable from the ones above it.

That is the second big change from the previous engine. It walked
rules along routes: down columns, along diagonals, spiralling out from
a corner. Those are all *possible* patterns, and a person shown one
can eventually find it, but they are not what the test is. A matrix
whose rule runs along a diagonal reads as a trick. Rows are the
convention for a reason: the eye already scans that way, so the work
left to the player is finding the rule rather than finding where to
look for it.

**The grid is square but not fixed.** A rule carries :attr:`~Rule.across`
— how many panels a row holds — and generalises by its own logic: a
two-by-two matrix can only show a progression or a constant, which is
exactly what the easiest items of the real test are; a four-by-four
distributes four values as a four-by-four Latin square, sums three
panels into a fourth, and folds its logic across three. Each rule's
``fits`` says honestly what it needs, so a rule that cannot show
itself on a given grid is simply never dealt there — the second-order
rule, whose last row would span ``(across - 1)²`` rungs, rules itself
out of anything bigger than three-by-three because no ladder here is
ten rungs long.

The rules, easiest first:

``Constant``
    The value holds across the whole matrix.
``Progression``
    The value steps along its ladder by the same amount each time.
``DistributeThree``
    As many values as the row is long, each row holding all of them in
    some order. Laid out as a Latin square, so each column holds them
    all as well. This is the rule people picture when they picture a
    Raven's item. (The name keeps its *three* — that is the classic
    form and the name the difficulty table filters by — but the rule
    distributes however many the grid asks.)
``Arithmetic``
    The last is the first plus, or minus, all the panels between.
    Only ever applied to how many figures there are, where it is
    something a person can actually do in their head.
``SecondOrder``
    The rule itself changes between rows: each row steps further.
``Logic``
    The last panel's filled places follow from all the others'.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, Optional, Sequence

#: How many panels a row holds unless a rule is told otherwise. Three
#: is the classic grid, and the default keeps every caller that never
#: thinks about grid size on it.
ACROSS = 3


class Rule:
    """One attribute's behaviour across the rows."""

    name = 'rule'

    #: How many panels a row holds. Set by :func:`choose_rule` and
    #: :func:`apply_rule`; the default keeps hand-made rules classic.
    across = ACROSS

    def rows(self, ladder: Sequence, rng: random.Random) -> List[List]:
        """``across`` rows of ``across`` values, drawn from ``ladder``."""
        raise NotImplementedError

    def describe(self, noun: str) -> str:
        raise NotImplementedError

    @staticmethod
    def fits(ladder: Sequence, across: int = ACROSS) -> bool:
        return len(ladder) >= 1


class Constant(Rule):
    """The value holds — everywhere, not merely along each row.

    Letting each row pick its own value looks harmless and is not. An
    attribute that changes between rows is *doing* something, and a
    player is right to read it as a rule and go looking for the one it
    follows. There isn't one, so the search is wasted and the matrix is
    noisier than the puzzle it contains. Anything that varies here
    varies because a rule says so.
    """

    name = 'constant'

    def rows(self, ladder, rng):
        value = rng.choice(list(ladder))
        return [[value] * self.across for _row in range(self.across)]

    def describe(self, noun):
        return '%s is the same throughout' % noun


class Progression(Rule):
    """The value steps along its ladder by the same amount each time."""

    name = 'progression'

    def __init__(self, step: int) -> None:
        self.step = step

    def rows(self, ladder, rng):
        span = abs(self.step) * (self.across - 1)
        starts = range(len(ladder) - span) if self.step > 0 \
            else range(span, len(ladder))
        picks = list(starts)
        if not picks:
            raise ValueError('ladder too short for this progression')
        rng.shuffle(picks)
        rows = []
        for index in range(self.across):
            start = picks[index % len(picks)]
            rows.append([ladder[start + self.step * step]
                         for step in range(self.across)])
        return rows

    def describe(self, noun):
        way = {1: 'steps up', 2: 'steps up by two',
               -1: 'steps down', -2: 'steps down by two'}[self.step]
        return '%s %s' % (noun, way)

    @staticmethod
    def fits(ladder, across=ACROSS):
        return len(ladder) >= across


class DistributeThree(Rule):
    """A row's worth of values, each row holding all of them.

    Rotated rather than shuffled, so each column holds all of them
    too. A player who has found the rule can read the missing value
    off either the row or the column, and both agree — which is what
    makes a matrix feel solvable rather than merely consistent.
    """

    name = 'distribute three'

    WORDS = {2: 'two', 3: 'three', 4: 'four', 5: 'five'}

    def rows(self, ladder, rng):
        chosen = rng.sample(list(ladder), self.across)
        return [[chosen[(column + row) % self.across]
                 for column in range(self.across)]
                for row in range(self.across)]

    def describe(self, noun):
        many = self.WORDS.get(self.across, str(self.across))
        return '%s: the same %s each row, reordered' % (noun, many)

    @staticmethod
    def fits(ladder, across=ACROSS):
        return len(ladder) >= across


class Arithmetic(Rule):
    """The last value is the first plus, or minus, all the between."""

    name = 'arithmetic'

    def __init__(self, sign: int) -> None:
        self.sign = sign

    def rows(self, ladder, rng):
        values = list(ladder)
        lowest, highest = values[0], values[-1]
        rows = []
        for _row in range(self.across):
            for _try in range(200):
                drawn = [rng.choice(values)
                         for _panel in range(self.across - 1)]
                last = drawn[0] + self.sign * sum(drawn[1:])
                if lowest <= last <= highest and 0 not in drawn[1:]:
                    rows.append(drawn + [last])
                    break
            else:
                raise ValueError('no arithmetic row fits this ladder')
        return rows

    def describe(self, noun):
        which = 'the second' if self.across == 3 else 'those between'
        return ('%s: the last is the first %s %s'
                % (noun, 'plus' if self.sign > 0 else 'minus', which))

    @staticmethod
    def fits(ladder, across=ACROSS):
        return len(ladder) >= 3 and all(isinstance(value, int)
                                        for value in ladder)


class SecondOrder(Rule):
    """The rule itself changes between rows: each steps further.

    The one rule here about a rule. Row one holds its value, row two
    steps along the ladder, row three steps twice as far — so no row's
    rule is the answer, and what has to be inferred is the progression
    *of* rules. These are the items at the very top of the real test's
    advanced form: solving one means representing "how this row works"
    as a thing that can itself change, which is a level of abstraction
    the first-order rules never ask for.

    The rows start where they like. Tying them to one start would let
    the item be read as a plain pattern of positions; left loose, the
    only thread through the three rows is the accelerating step.
    """

    name = 'second order'

    def __init__(self, delta: int) -> None:
        self.delta = delta

    def rows(self, ladder, rng):
        rows = []
        for row in range(self.across):
            step = self.delta * row
            span = abs(step) * (self.across - 1)
            starts = list(range(len(ladder) - span)) if step >= 0 \
                else list(range(span, len(ladder)))
            if not starts:
                raise ValueError('ladder too short for a second order')
            start = rng.choice(starts)
            rows.append([ladder[start + step * column]
                         for column in range(self.across)])
        return rows

    def describe(self, noun):
        way = 'up' if self.delta > 0 else 'down'
        return ('%s steps %s further each row: not at all, then by one, '
                'then by two' % (noun, way))

    @staticmethod
    def fits(ladder, across=ACROSS):
        # The last row spans (across - 1)² rungs, so it needs one more
        # rung than that to exist at all. Two rows cannot show a step
        # that accelerates; ten rungs, which is what a four-by-four
        # would need, is longer than any ladder here — so this rule
        # lives on the three-by-three grid by arithmetic, not by
        # decree.
        return across >= 3 and len(ladder) > (across - 1) ** 2


class Logic(Rule):
    """The last panel's filled places follow from all the others'.

    The one rule here that is not about a ladder. It governs *which*
    of a lattice's places hold a figure: the last panel of a row holds
    the places in any of the others, in all of them, or in exactly an
    odd number (which on three panels reads as "exactly one of the
    first two"), and the same operation runs down every row. These are
    the items at the hard end of the real test, and they are hard for
    a reason — nothing steps or repeats, so the rule cannot be spotted
    by watching one figure. It has to be inferred from what whole
    panels have to do with one another.

    The ladder handed to :meth:`rows` is the universe of places, and
    the values produced are frozensets of them. All three operations
    are associative, which is what lets a row longer than three fold
    them across every panel before the last.
    """

    #: op → how the last panel is made from the others. The classic
    #: three-by-three grid gets the plainer two-operand wording.
    SAYINGS = {
        'or': 'the last panel gathers everything in the others',
        'and': 'the last panel keeps only what all the others share',
        'xor': 'the last panel keeps what is in an odd number of the '
               'others',
    }
    CLASSIC = {
        'or': 'the third panel gathers everything in the first two',
        'and': 'the third panel keeps only what the first two share',
        'xor': 'the third panel keeps what is in exactly one of the '
               'first two',
    }

    name = 'logic'

    def __init__(self, op: str) -> None:
        self.op = op

    def _fold(self, panels: List[frozenset]) -> frozenset:
        folded = panels[0]
        for panel in panels[1:]:
            if self.op == 'or':
                folded = folded | panel
            elif self.op == 'and':
                folded = folded & panel
            else:
                folded = folded ^ panel
        return folded

    def rows(self, ladder, rng):
        universe = list(ladder)
        rows = []
        for _row in range(self.across):
            for _try in range(400):
                drawn = [frozenset(rng.sample(
                    universe, rng.randint(1, len(universe) - 1)))
                    for _panel in range(self.across - 1)]
                last = self._fold(drawn)
                # The row has to *show* the operation: identical
                # operands show nothing, and a result equal to one of
                # them is explained by "copy that one" just as well.
                if (last and len(set(drawn)) == len(drawn)
                        and last not in drawn):
                    rows.append(drawn + [last])
                    break
            else:
                raise ValueError('no logic row fits this lattice')
        return rows

    def describe(self, noun):
        sayings = self.CLASSIC if self.across == 3 else self.SAYINGS
        return '%s: %s' % (noun, sayings[self.op])

    @staticmethod
    def fits(ladder, across=ACROSS):
        return len(ladder) >= 4


def rule_choices(ladder: Sequence, allow_arithmetic: bool = False,
                 allowed: Optional[Sequence[str]] = None,
                 across: int = ACROSS) -> List[Rule]:
    """Every rule that can actually be applied to this ladder.

    ``allowed`` narrows the pool by rule name; ``None`` allows all.
    The easy end of the difficulty ladder is made partly of this — a
    first puzzle offers a progression and nothing else, so the player
    meets one idea at a time. Every rule returned already knows the
    grid it was chosen for.
    """
    choices: List[Rule] = []
    if DistributeThree.fits(ladder, across):
        choices.extend([DistributeThree() for _copy in range(3)])
    for step in (1, -1, 2, -2):
        if abs(step) * (across - 1) < len(ladder):
            choices.append(Progression(step))
    if allow_arithmetic and Arithmetic.fits(ladder, across):
        choices.extend([Arithmetic(1), Arithmetic(-1)])
    if SecondOrder.fits(ladder, across):
        choices.extend([SecondOrder(1), SecondOrder(-1)])
    if allowed is not None:
        choices = [rule for rule in choices if rule.name in allowed]
    for rule in choices:
        rule.across = across
    return choices


def choose_rule(ladder: Sequence, rng: random.Random,
                allow_arithmetic: bool = False,
                allowed: Optional[Sequence[str]] = None,
                across: int = ACROSS) -> Rule:
    """One rule that suits this ladder, or ``Constant`` if none does."""
    choices = rule_choices(ladder, allow_arithmetic, allowed, across)
    if choices:
        return rng.choice(choices)
    fallback = Constant()
    fallback.across = across
    return fallback


def apply_rule(rule: Rule, ladder: Sequence,
               rng: random.Random) -> List[List]:
    """Run a rule, falling back to ``Constant`` if it cannot fit.

    A rule that cannot be laid on a ladder is a generation accident,
    not a puzzle worth throwing away: holding the attribute constant
    leaves a matrix that is still sound, only easier.
    """
    try:
        return rule.rows(ladder, rng)
    except ValueError:
        fallback = Constant()
        fallback.across = rule.across
        return fallback.rows(ladder, rng)
