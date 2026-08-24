# -*- coding: utf-8 -*-
"""Procedural number-sequence puzzles.

Every puzzle is a small seeded program. The program is evaluated to produce
the displayed terms and the answer, so generation and checking cannot drift.
Difficulty increases the number of operations, the order of recurrences and
the amount of hidden state; it is not a table of increasingly difficult
hand-authored examples.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import List, Tuple


@dataclass(frozen=True)
class SequencePuzzle:
    terms: Tuple[int, ...]
    answer: int
    rule: str
    difficulty: int
    complexity: int = 1

    @property
    def asked(self) -> str:
        return ',   '.join(str(term) for term in self.terms) + ',   ?'


# Kept as a compatibility name for callers of the first implementation. It
# is intentionally not used as a bound: finite requested levels are accepted
# without a maximum.
MAX_DIFFICULTY = None


def sequence_length(difficulty: int, requested: int | None = None) -> int:
    """Choose a visible length that grows as difficulty grows.

    An explicit length is useful for tests and curriculum design. The default
    grows without a ceiling; level 10,000 therefore has a substantially
    longer sequence than level 1, and level 100,000 is longer again.
    """
    if requested is not None:
        return max(4, int(requested))
    difficulty = max(1, int(difficulty))
    return 4 + difficulty // 40


def _polynomial(coefficients: Tuple[int, ...], n: int) -> int:
    value = 0
    for coefficient in coefficients:
        value = value * n + coefficient
    return value


def _polynomial_puzzle(rng: random.Random, difficulty: int,
                       shown: int, degree: int) -> SequencePuzzle:
    scale = 10 ** (1 + difficulty // 8)
    coefficients = tuple(rng.randint(-scale, scale) or 1
                         for _ in range(degree + 1))
    value = lambda n: _polynomial(coefficients, n)
    terms = tuple(value(n) for n in range(shown))
    return SequencePuzzle(
        terms, value(shown),
        'Evaluate a degree-%d polynomial at consecutive integers' % degree,
        difficulty, degree + 1)


def _alternating_puzzle(rng: random.Random, difficulty: int,
                        shown: int) -> SequencePuzzle:
    start = rng.randint(-8, 8)
    first = rng.randint(1, 9)
    second = rng.randint(1, 9)
    values = [start]
    for n in range(1, shown + 1):
        values.append(values[-1] + (first if n % 2 else second) * n)
    terms = tuple(values[:shown])
    return SequencePuzzle(
        terms, values[shown],
        'Add alternating, growing steps', difficulty, 6)


def _recurrence_puzzle(rng: random.Random, difficulty: int,
                       shown: int, order: int) -> SequencePuzzle:
    """Generate a linear recurrence with a procedural forcing function."""
    scale = 1 + difficulty // 12
    coefficients = [rng.randint(-3, 3) or 1 for _ in range(order)]
    initial = [rng.randint(-scale, scale) or 1 for _ in range(order)]
    force_degree = 1 + difficulty // 18
    force_coefficients = tuple(rng.randint(-scale, scale) or 1
                               for _ in range(force_degree + 1))
    period = 2 + rng.randrange(2 + difficulty // 10)
    phase = rng.randrange(period)
    forcing_layers = 1 + difficulty // 16

    def forcing(n: int) -> int:
        polynomial = _polynomial(force_coefficients, n)
        sign = 1
        for layer in range(forcing_layers):
            layer_period = period + layer
            if (n * (layer + 1) + phase) % layer_period == 0:
                sign *= -1
        return sign * polynomial

    values: List[int] = list(initial)
    while len(values) < shown + 1:
        n = len(values)
        prior = sum(coefficient * values[-index]
                    for index, coefficient in enumerate(coefficients, 1))
        values.append(prior + forcing(n))
    terms = tuple(values[:shown])
    description = ('order-%d recurrence with degree-%d polynomial and %d '
                   'periodic layers' %
                   (order, force_degree, forcing_layers))
    return SequencePuzzle(terms, values[shown], description, difficulty,
                          order + force_degree + forcing_layers + 2)


def generate(difficulty: int = 1, seed: int = 0,
             length: int | None = None) -> SequencePuzzle:
    """Generate a deterministic sequence puzzle.

    Level 1 is a seeded, child-friendly constant-step rule. Levels 2 and 3
    teach richer differences and multiplicative rules. From level 4 onward the
    generator composes polynomial, alternating-step and recurrence families;
    recurrence order and forcing depth continue growing for arbitrarily high
    requested difficulty.
    """
    difficulty = max(1, int(difficulty))
    rng = random.Random(int(seed))
    shown = sequence_length(difficulty, length)

    if difficulty == 1:
        start = rng.randint(1, 9)
        step = rng.choice((1, 2, 3))
        # The tutorial is generated, including for the default seed; it is
        # never the old fixed 0, 1, 2, 3 example.
        if start == 0 and step == 1:
            start = 2
        terms = tuple(start + step * n for n in range(shown))
        return SequencePuzzle(terms, start + step * shown,
                              'Add %d each time' % step, difficulty, 1)

    if difficulty == 2:
        step = rng.randint(2, 9)
        start = rng.randint(-9, 9)
        terms = tuple(start + step * n for n in range(shown))
        return SequencePuzzle(terms, start + step * shown,
                              'Add the same number each time', difficulty, 2)

    if difficulty == 3:
        multiplier = rng.randint(2, 5)
        offset = rng.randint(1, 8)
        start = rng.randint(1, 8)
        terms = tuple(start * multiplier ** n + offset
                      for n in range(shown))
        return SequencePuzzle(terms, start * multiplier ** shown + offset,
                              'Multiply, then add the offset', difficulty, 3)

    if difficulty <= 5:
        return _polynomial_puzzle(rng, difficulty, shown, difficulty - 2)

    if difficulty == 6:
        return _alternating_puzzle(rng, difficulty, shown)

    # Order grows with the requested finite level. Since the visible length
    # grows too, the next term always has a complete displayed history, while
    # higher levels still become increasingly difficult to infer.
    order = min(2 + difficulty // 4, max(2, shown - 1))
    return _recurrence_puzzle(rng, difficulty, shown, order)


def is_correct(puzzle: SequencePuzzle, answer: str | int) -> bool:
    """Compare an answer exactly, accepting surrounding whitespace."""
    try:
        return int(str(answer).strip()) == puzzle.answer
    except (TypeError, ValueError):
        return False


__all__ = ['MAX_DIFFICULTY', 'SequencePuzzle', 'generate', 'is_correct',
           'sequence_length']
