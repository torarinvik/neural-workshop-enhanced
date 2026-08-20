# -*- coding: utf-8 -*-
"""How an attribute changes across a row.

Raven's matrices are read along the rows. Every rule here takes the
three panels of a row and says what one attribute does across them,
and the same rule governs all three rows — which is what makes the
third row answerable from the first two.

That is the second big change from the previous engine. It walked
rules along routes: down columns, along diagonals, spiralling out from
a corner. Those are all *possible* patterns, and a person shown one
can eventually find it, but they are not what the test is. A matrix
whose rule runs along a diagonal reads as a trick. Rows are the
convention for a reason: the eye already scans that way, so the work
left to the player is finding the rule rather than finding where to
look for it.

The four rules are the ones the literature settles on:

``Constant``
    The value holds across the row.
``Progression``
    The value steps along its ladder by the same amount each time.
``DistributeThree``
    Three values, and each row holds all three in some order. Laid out
    as a Latin square, so each column holds all three as well. This is
    the rule people picture when they picture a Raven's item.
``Arithmetic``
    The third is the first plus or minus the second. Only ever applied
    to how many figures there are, where it is something a person can
    actually do in their head.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, Sequence

#: How many panels a row holds. Not a setting — every rule here is
#: written for three, and Latin squares of three are what the
#: distribute rule is.
ACROSS = 3


class Rule:
    """One attribute's behaviour across the rows."""

    name = 'rule'

    def rows(self, ladder: Sequence, rng: random.Random) -> List[List]:
        """Three rows of three values, drawn from ``ladder``."""
        raise NotImplementedError

    def describe(self, noun: str) -> str:
        raise NotImplementedError

    @staticmethod
    def fits(ladder: Sequence) -> bool:
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
        return [[value] * ACROSS for _row in range(ACROSS)]

    def describe(self, noun):
        return '%s is the same throughout' % noun


class Progression(Rule):
    """The value steps along its ladder by the same amount each time."""

    name = 'progression'

    def __init__(self, step: int) -> None:
        self.step = step

    def rows(self, ladder, rng):
        span = abs(self.step) * (ACROSS - 1)
        starts = range(len(ladder) - span) if self.step > 0 \
            else range(span, len(ladder))
        picks = list(starts)
        if not picks:
            raise ValueError('ladder too short for this progression')
        rng.shuffle(picks)
        rows = []
        for index in range(ACROSS):
            start = picks[index % len(picks)]
            rows.append([ladder[start + self.step * step]
                         for step in range(ACROSS)])
        return rows

    def describe(self, noun):
        way = {1: 'steps up', 2: 'steps up by two',
               -1: 'steps down', -2: 'steps down by two'}[self.step]
        return '%s %s' % (noun, way)

    @staticmethod
    def fits(ladder):
        return len(ladder) >= ACROSS


class DistributeThree(Rule):
    """Three values, each row holding all three in a different order.

    Rotated rather than shuffled, so each column holds all three too.
    A player who has found the rule can read the missing value off
    either the row or the column, and both agree — which is what makes
    a matrix feel solvable rather than merely consistent.
    """

    name = 'distribute three'

    def rows(self, ladder, rng):
        chosen = rng.sample(list(ladder), ACROSS)
        return [[chosen[(column + row) % ACROSS] for column in range(ACROSS)]
                for row in range(ACROSS)]

    def describe(self, noun):
        return '%s: the same three each row, reordered' % noun

    @staticmethod
    def fits(ladder):
        return len(ladder) >= ACROSS


class Arithmetic(Rule):
    """The third value is the first plus, or minus, the second."""

    name = 'arithmetic'

    def __init__(self, sign: int) -> None:
        self.sign = sign

    def rows(self, ladder, rng):
        values = list(ladder)
        lowest, highest = values[0], values[-1]
        rows = []
        for _row in range(ACROSS):
            for _try in range(200):
                first = rng.choice(values)
                second = rng.choice(values)
                third = first + self.sign * second
                if lowest <= third <= highest and second != 0:
                    rows.append([first, second, third])
                    break
            else:
                raise ValueError('no arithmetic row fits this ladder')
        return rows

    def describe(self, noun):
        return ('%s: third is first %s second'
                % (noun, 'plus' if self.sign > 0 else 'minus'))

    @staticmethod
    def fits(ladder):
        return len(ladder) >= 3 and all(isinstance(value, int)
                                        for value in ladder)


#: The rules a rule-carrying attribute may take, and how often each is
#: drawn. Distribute-three is weighted up because it is the rule that
#: makes a matrix feel like a Raven's item rather than a sequence.
def rule_choices(ladder: Sequence, allow_arithmetic: bool = False
                 ) -> List[Rule]:
    """Every rule that can actually be applied to this ladder."""
    choices: List[Rule] = []
    if DistributeThree.fits(ladder):
        choices.extend([DistributeThree()] * 3)
    for step in (1, -1, 2, -2):
        candidate = Progression(step)
        if Progression.fits(ladder) and abs(step) * (ACROSS - 1) < len(ladder):
            choices.append(candidate)
    if allow_arithmetic and Arithmetic.fits(ladder):
        choices.extend([Arithmetic(1), Arithmetic(-1)])
    return choices


def choose_rule(ladder: Sequence, rng: random.Random,
                allow_arithmetic: bool = False) -> Rule:
    """One rule that suits this ladder, or ``Constant`` if none does."""
    choices = rule_choices(ladder, allow_arithmetic)
    return rng.choice(choices) if choices else Constant()


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
        return Constant().rows(ladder, rng)
