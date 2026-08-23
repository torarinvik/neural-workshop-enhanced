# -*- coding: utf-8 -*-
"""Arithmetic at the bottom, congruences at the top, one number a rung.

    3 + 4
    n = 3 (mod 7), n = 1 (mod 11), n = 4 (mod 13), ... smallest n

Both of those are this task. The first is a rung a child clears; the
last is one integer in a box of 10^30, which nothing will ever find by
looking. What runs between them is not bigger numbers — that is the
trap, and it was the first ladder written here. ``48239 x 91827`` is
unbounded and it is *clerical*: it measures how long somebody will
keep going, and at the top of it sits a calculator rather than a
mathematician. So the coefficients stay small at every rung on
purpose, and the difficulty is carried by structure.

**A rung means how big the naive search is**, and that is counted
rather than claimed. Every rung guarantees its answer lies in some
space — an interval of integers, or a set of polynomials with bounded
degree and coefficients. :attr:`Problem.candidates` is the base-ten
log of that space, and :func:`crack` is a solver that understands no
mathematics whatsoever: it can only *check* an answer, so it walks the
space until something fits. What it gets is what the rung gives away
to somebody who cannot do the maths at all. Everything above it is
what the maths buys.

=====  =====================  ==========  ==========  =======  =====
rung   name                   kind        candidates  cracked  steps
=====  =====================  ==========  ==========  =======  =====
1      one and one            number             1.6     1.00      1
2      take away              number             1.9     1.00      2
3      times before plus      number             2.3     1.00      2
4      below zero             number             2.5     1.00      2
5      exact halves           number             5.1     1.00      2
6      find the letter        number             1.3     1.00      3
7      open the brackets      expression         3.0     1.00      2
8      clock arithmetic       number             1.5     1.00      2
9      collect the powers     expression         5.4     1.00      3
10     three clocks at once   number             5.1     0.67      3
11     two letters, cubed     expression        24.6     0.00      4
12     six clocks at once     number            27.9     0.00      6
=====  =====================  ==========  ==========  =======  =====

*candidates* is the base-ten log of the space; *cracked* is the share
:func:`crack` got inside its budget; *steps* is the derivation length,
which is free because the generator counted its own moves. Median over
sixty deals a rung. Rerun it with ``tests/bench_algebra.py``.

Three things in that table are worth more than the ladder itself.

**Searching is not reasoning, and the two columns say so.** Rung 5
hides its answer among 10^5.1 values and takes two steps to get; rung
6 hides its among nineteen and takes three. The *easier-looking* rung
has a search six thousand times bigger. Sorting the ladder by
candidates would put adding two fractions above solving an equation,
which is wrong about people; sorting it by steps would put it below
adding two whole numbers, which is wrong about machines. So the rungs
are ordered by what a person has to know, both columns are printed,
and ``bench_algebra.py`` prints the disagreement in words so that
nobody has to notice it.

**The superhuman end is a cliff, not a slope.** Everything to rung 9
falls to patience alone — a solver that cannot do arithmetic at all,
only recognise a right answer, gets every one of them. Rung 10 is
right at the edge, at two thirds. Then the space goes from 10^5 to
10^25 in one rung and searching stops being a strategy for good. That
is what the top of this ladder means, and it is the reason the moduli
are five-digit primes rather than the two-digit ones three rungs
below: six two-digit primes would put the answer in a box of 10^9,
which is a long afternoon for a laptop. Six five-digit primes put it
in 10^28, which is not an afternoon for anything.

**Nothing here is a bigger sum.** The numbers printed on the page
never exceed five digits, at any rung. What grows is how much has to
be true at once.

**Copying the question is a right answer, unless you stop it.** A
symbolic rung asks for an expression and marks it by normal form —
which is the only exact way to accept ``2y + 3``, ``3 + y + y`` and
``(4y + 6)/2`` as one answer. But the *question* has the same normal
form as its own answer, so typing the question back would be marked
right, and the rung would be a copying exercise. The crossword had
this exact defect with its clues. So a symbolic answer must also be
**collected**: no brackets, and no more written terms than the
canonical form has. That is not syntax policing, it is what the word
simplify means, and :func:`collected` is where it lives.

**Generated backwards, checked forwards, by two different pieces of
code.** Every problem is built from its answer outwards, so the answer
is known rather than solved for. It is then checked by an evaluator
that knows nothing about how it was made — substitute and evaluate,
or reduce the congruence — and a problem that fails its own check is
never dealt. A generator that is its own verifier proves nothing.

**Nothing here is a float.** Every coefficient is a
:class:`~fractions.Fraction` (see :mod:`neural_workshop.expressions`).
A ladder whose top rung turns on the thirtieth digit of an integer
cannot afford a rounding error, and one whose fifth rung asks for
``2/3 + 3/4`` cannot afford ``1.5833333333333333``.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import re
from fractions import Fraction
from typing import Callable, Dict, NamedTuple, Optional, Tuple

from .expressions import ParseError, Poly, parse, render

#: Answers are one of two shapes, and a rung says which.
NUMBER, EXPRESSION = 'number', 'expression'

#: The times sign the arithmetic rungs print. Not ``x``: this task
#: uses x for the unknown four rungs later, and a screen that means
#: two things by one letter is teaching its own notation. The parser
#: never sees it — :func:`checks_out` turns it back into ``*``.
TIMES = '\u00d7'


class Grade(NamedTuple):
    """One rung: what it asks, and how big the space it hides it in."""

    name: str
    #: Which builder deals it. Named rather than a function so the
    #: table reads as a table.
    family: str
    #: ``NUMBER`` or ``EXPRESSION`` — what the player types.
    kind: str
    #: Free parameters for the builder, all small on purpose.
    dials: Dict[str, int] = {}


class Problem(NamedTuple):
    """One dealt problem, with everything measured about it."""

    grade: Grade
    #: The question, as shown.
    asked: str
    #: The answer. A :class:`~fractions.Fraction` for a numeric rung,
    #: a :class:`~neural_workshop.expressions.Poly` for a symbolic one.
    answer: object
    #: How many candidates a checker-only solver must walk. One
    #: definition, used by :attr:`candidates` and by :func:`crack`
    #: both — two would drift, and the drift would be silent: a space
    #: that does not contain the answer makes *cracked* a measure of
    #: nothing, which is how the first version read.
    space: int
    #: How many steps the generator took to build it, which is an
    #: upper bound on how many a solver needs and is free to know.
    steps: int
    #: The derivation, shown after the verdict. A player told only
    #: that they were wrong has learned nothing from the problem.
    working: Tuple[str, ...]
    #: What to hand back, when the question alone does not say it.
    #: Kept apart from :attr:`asked` rather than glued on the end of
    #: it, so the screen can size the two differently and the forward
    #: check can read the question without unpicking a separator.
    wants: str = ''

    @property
    def candidates(self) -> float:
        """Base-ten log of :attr:`space`. What the table prints."""
        return math.log10(max(1, self.space))

    @property
    def shown_answer(self) -> str:
        return (render(self.answer) if isinstance(self.answer, Poly)
                else _number(self.answer))


def _number(value) -> str:
    value = Fraction(value)
    return (str(value.numerator) if value.denominator == 1
            else '%d/%d' % (value.numerator, value.denominator))


# --- the ladder -----------------------------------------------------------


GRADES: Tuple[Grade, ...] = (
    Grade('one and one', 'add', NUMBER, {'digits': 1}),
    Grade('take away', 'chain', NUMBER, {'high': 20}),
    Grade('times before plus', 'precedence', NUMBER, {'high': 9}),
    Grade('below zero', 'signs', NUMBER, {'high': 12}),
    Grade('exact halves', 'fractions', NUMBER, {'high': 9}),
    Grade('find the letter', 'linear', NUMBER, {'high': 9}),
    Grade('open the brackets', 'expand', EXPRESSION,
          {'degree': 1, 'band': 16}),
    Grade('clock arithmetic', 'congruence', NUMBER, {'modulus': 60}),
    Grade('collect the powers', 'expand', EXPRESSION,
          {'degree': 2, 'band': 32}),
    Grade('three clocks at once', 'crt', NUMBER,
          {'moduli': 3, 'digits': 2}),
    Grade('two letters, cubed', 'expand', EXPRESSION,
          {'degree': 3, 'letters': 2, 'band': 144}),
    Grade('six clocks at once', 'crt', NUMBER,
          {'moduli': 6, 'digits': 5}),
)


def grade_of(rung: int) -> Grade:
    return GRADES[max(0, min(len(GRADES) - 1, int(rung) - 1))]


# --- building one, from the answer outwards -------------------------------


def _pick(rng: random.Random, low: int, high: int, avoid: int = None) -> int:
    while True:
        got = rng.randint(low, high)
        if got != avoid:
            return got


def build_add(grade: Grade, rng: random.Random) -> Problem:
    """``3 + 4``. The bottom of the ladder, and it should be."""
    high = 10 ** grade.dials.get('digits', 1) - 1
    left, right = rng.randint(1, high), rng.randint(1, high)
    return Problem(grade, '%d + %d' % (left, right), Fraction(left + right),
                   4 * high + 1, 1,
                   ('%d + %d = %d' % (left, right, left + right),))


def build_chain(grade: Grade, rng: random.Random) -> Problem:
    """``12 - 5 + 3``. Three terms, so the order has to be kept."""
    high = grade.dials.get('high', 20)
    one, two, three = (rng.randint(2, high) for _each in range(3))
    total = one - two + three
    return Problem(grade, '%d - %d + %d' % (one, two, three), Fraction(total),
                   4 * high + 1, 2,
                   ('%d - %d = %d' % (one, two, one - two),
                    '%d + %d = %d' % (one - two, three, total)))


def build_precedence(grade: Grade, rng: random.Random) -> Problem:
    """``3 + 4 x 2``. Small numbers, one real idea: which goes first."""
    high = grade.dials.get('high', 9)
    one, two, three = (rng.randint(2, high) for _each in range(3))
    total = one + two * three
    return Problem(grade, '%d + %d %s %d' % (one, two, TIMES, three),
                   Fraction(total), 2 * (high * high + high) + 1, 2,
                   ('%d %s %d = %d, before the plus'
                    % (two, TIMES, three, two * three),
                    '%d + %d = %d' % (one, two * three, total)))


def build_signs(grade: Grade, rng: random.Random) -> Problem:
    """``-7 + 12 x (-3)``. The idea is the sign, not the size."""
    high = grade.dials.get('high', 12)
    one = -rng.randint(2, high)
    two = rng.randint(2, high)
    three = -rng.randint(2, high)
    total = one + two * three
    return Problem(grade, '%d + %d %s (%d)' % (one, two, TIMES, three),
                   Fraction(total), 2 * (high * high + high) + 1, 2,
                   ('%d %s (%d) = %d' % (two, TIMES, three, two * three),
                    '%d + (%d) = %d' % (one, two * three, total)))


def fraction_grid(grade: Grade) -> Tuple[int, int]:
    """The rows and columns of the fraction rung's search.

    Derived from the rung's own dial rather than fixed, because the
    grid has to *contain* the answer: two denominators of nine can
    make a seventy-second, and a grid forty rows deep silently failed
    to crack one deal in six — which read as difficulty and was a bug.
    """
    high = grade.dials.get('high', 9)
    rows = high * high
    return rows, high * rows


def build_fractions(grade: Grade, rng: random.Random) -> Problem:
    """``2/3 + 3/4``. Exact, and the answer is a fraction too.

    The denominators are forced apart and the total forced off a whole
    number. Left to chance, a third of these came out as ``3/2 + 7/2``
    — one denominator, integer answer — which is the previous rung
    wearing a costume.
    """
    high = grade.dials.get('high', 9)
    for _try in range(200):
        below, other = rng.randint(2, high), rng.randint(2, high)
        if below == other:
            continue
        one = Fraction(rng.randint(1, high), below)
        two = Fraction(rng.randint(1, high), other)
        total = one + two
        if (total.denominator > 1 and one.denominator > 1
                and two.denominator > 1):
            break
    common = math.lcm(one.denominator, two.denominator)
    rows, span = fraction_grid(grade)
    return Problem(grade, '%s + %s' % (_number(one), _number(two)), total,
                   rows * (2 * span + 1), 2,
                   ('over %d: %s + %s' % (
                       common, _number(one * common), _number(two * common)),
                    'which is %s' % _number(total)))


def build_linear(grade: Grade, rng: random.Random) -> Problem:
    """``3(x - 2) + 5 = 2x + 9``. Built from the answer outwards."""
    high = grade.dials.get('high', 9)
    answer = Fraction(rng.randint(-high, high))
    left_slope = _pick(rng, 2, high)
    right_slope = _pick(rng, 1, high - 1, avoid=left_slope)
    shift = rng.randint(-high, high)
    tail = rng.randint(-high, high)
    # left_slope*(x + shift) + tail  ==  right_slope*x + rest
    rest = (left_slope - right_slope) * answer + left_slope * shift + tail
    asked = '%d(x %s %d) %s %d = %dx %s %d' % (
        left_slope, '+' if shift >= 0 else '-', abs(shift),
        '+' if tail >= 0 else '-', abs(tail),
        right_slope, '+' if rest >= 0 else '-', abs(rest))
    gap = left_slope - right_slope
    return Problem(grade, asked, answer, 2 * high + 1, 3,
                   ('open the bracket: %dx + %d %s %d = %dx %s %d'
                    % (left_slope, left_slope * shift,
                       '+' if tail >= 0 else '-', abs(tail),
                       right_slope, '+' if rest >= 0 else '-', abs(rest)),
                    'gather: %dx = %s' % (gap, _number(
                        rest - left_slope * shift - tail)),
                    'x = %s' % _number(answer)), wants='x = ?')


def build_expand(grade: Grade, rng: random.Random) -> Optional[Problem]:
    """A product of small factors, minus another, collected.

    The answer is a polynomial rather than a number, and the question
    is deliberately *longer* than its answer so that copying it back
    fails :func:`collected` even though it would pass on normal form.
    """
    degree = grade.dials.get('degree', 1)
    letters = grade.dials.get('letters', 1)
    names = ('x', 'y')[:letters]
    low = 1

    def linear() -> Poly:
        out = Poly.constant(rng.randint(-4, 4) or 2)
        for name in names:
            out = out + Poly.variable(name) * rng.randint(low, 3)
        return out

    band = grade.dials.get('band', 16)
    for _try in range(400):
        product = Poly.constant(1)
        pieces = []
        for _each in range(degree):
            piece = linear()
            pieces.append('(%s)' % render(piece))
            product = product * piece
        taken = linear() * rng.randint(1, 3)
        answer = product - taken
        # Two guards, both found by measuring rather than by thinking.
        # A quarter of the easiest rung's deals used to collapse to one
        # term or to nothing, which is not a collecting exercise; and an
        # answer outside the declared band would sit outside the space
        # crack() searches, making that column a measure of nothing.
        if len(answer.terms) < 2:
            continue
        if max(abs(one) for one in answer.terms.values()) > band:
            continue
        asked = '%s - (%s)' % (''.join(pieces), render(taken))
        return Problem(grade, asked, answer,
                       (2 * band + 1) ** len(answer.terms), degree + 1,
                       ('multiply out: %s' % render(product),
                        'take away %s' % render(taken),
                        'which leaves %s' % render(answer)),
                       wants='expand and collect')
    return None


def build_congruence(grade: Grade, rng: random.Random) -> Problem:
    """``7x = 3 (mod 26)``. One solution, because gcd(a, m) is one."""
    modulus = grade.dials.get('modulus', 60)
    while True:
        base = rng.randint(3, max(4, modulus - 1))
        multiplier = rng.randint(2, modulus - 1)
        if math.gcd(multiplier, base) == 1:
            break
    answer = rng.randrange(base)
    right = (multiplier * answer) % base
    asked = '%dx = %d  (mod %d)' % (multiplier, right, base)
    inverse = pow(multiplier, -1, base)
    return Problem(grade, asked, Fraction(answer), base, 2,
                   ('%d has inverse %d mod %d' % (multiplier, inverse, base),
                    'x = %d %s %d = %d (mod %d)'
                    % (inverse, TIMES, right, answer, base)),
                   wants='smallest x >= 0')


#: Small primes, so the moduli of a CRT rung are coprime by
#: construction rather than by a check that might not fire.
PRIMES = (7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67,
          71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137)


def is_prime(number: int) -> bool:
    """Trial division. The moduli here are five digits at the most."""
    if number < 2:
        return False
    if number % 2 == 0:
        return number == 2
    step = 3
    while step * step <= number:
        if number % step == 0:
            return False
        step += 2
    return True


def primes_near(rng: random.Random, digits: int,
                count: int) -> Tuple[int, ...]:
    """*count* distinct primes with *digits* digits.

    The size of the moduli is the whole of what makes the top rung
    superhuman rather than merely tedious: six two-digit primes put
    the answer in a box of 10^9, which is a long afternoon for a
    laptop that only knows how to guess. Six five-digit primes put it
    in 10^28, which is not.
    """
    low, high = 10 ** (digits - 1), 10 ** digits - 1
    found: list = []
    while len(found) < count:
        candidate = rng.randint(low, high) | 1
        if candidate not in found and is_prime(candidate):
            found.append(candidate)
    return tuple(found)


def build_crt(grade: Grade, rng: random.Random) -> Problem:
    """Congruences over coprime moduli: one answer in a very large box.

    This is the honest shape of a superhuman rung. The box is the
    product of the moduli, so it is enormous and the answer is unique
    in it *by the remainder theorem* rather than by hoping. The
    derivation is a dozen exact steps. Nothing about it is a bigger
    sum: the numbers on the page stay two digits.
    """
    count = grade.dials.get('moduli', 3)
    digits = grade.dials.get('digits', 2)
    moduli = (rng.sample(PRIMES, count) if digits <= 2
              else primes_near(rng, digits, count))
    product = math.prod(moduli)
    answer = rng.randrange(product)
    parts = ['n = %d (mod %d)' % (answer % one, one) for one in moduli]
    asked = ',  '.join(parts)
    working = ['the moduli are coprime, so there is one n below %d'
               % product]
    running, running_mod = 0, 1
    for one in moduli:
        running = _combine(running, running_mod, answer % one, one)
        running_mod *= one
        working.append('after mod %d:  n = %d (mod %d)'
                       % (one, running, running_mod))
    if running != answer:
        raise ArithmeticError('the remainder theorem disagreed with itself')
    return Problem(grade, asked, Fraction(answer), product,
                   count, tuple(working), wants='smallest n >= 0')


def _combine(one: int, one_mod: int, two: int, two_mod: int) -> int:
    """The n below ``one_mod * two_mod`` agreeing with both congruences."""
    inverse = pow(one_mod % two_mod, -1, two_mod)
    step = ((two - one) * inverse) % two_mod
    return one + one_mod * step


BUILDERS: Dict[str, Callable[[Grade, random.Random],
                             Optional[Problem]]] = {
    'add': build_add,
    'chain': build_chain,
    'precedence': build_precedence,
    'signs': build_signs,
    'fractions': build_fractions,
    'linear': build_linear,
    'expand': build_expand,
    'congruence': build_congruence,
    'crt': build_crt,
}


def deal_one(grade: Grade, rng: random.Random) -> Optional[Problem]:
    """One problem at *grade*, checked forwards before it is handed over."""
    builder = BUILDERS.get(grade.family)
    if builder is None:
        return None
    for _try in range(20):
        made = builder(grade, rng)
        if made is not None and checks_out(made):
            return made
    return None


def generate(level_number: int, seed: Optional[int] = None) \
        -> Optional[Problem]:
    """A problem for *level_number*, one-based into :data:`GRADES`."""
    return deal_one(grade_of(level_number), random.Random(seed))


# --- checked forwards, by something that did not build it -----------------


def checks_out(problem: Problem) -> bool:
    """Whether the answer really answers the question.

    Deliberately not the generator's own arithmetic run again. For a
    congruence it reduces; for an expression it substitutes numbers
    into both sides; for a sum it re-reads the printed question with
    the parser a player's answer goes through. A generator that
    verifies itself proves only that it is consistent.
    """
    family = problem.grade.family
    if family == 'expand':
        return _expression_checks(problem)
    if family == 'crt':
        return _crt_checks(problem)
    if family == 'congruence':
        return _congruence_checks(problem)
    if family == 'linear':
        return _linear_checks(problem)
    return _sum_checks(problem)


def _expression_checks(problem: Problem) -> bool:
    """Substitute random numbers into the question and the answer."""
    try:
        stated = parse(problem.asked)
    except (ParseError, ArithmeticError, ZeroDivisionError):
        return False
    answer = problem.answer
    if not isinstance(answer, Poly):
        return False
    rng = random.Random(1234)
    for _each in range(8):
        at = {name: Fraction(rng.randint(-6, 6))
              for name in ('x', 'y', 'z', 'n')}
        if stated.evaluate(at) != answer.evaluate(at):
            return False
    return True


def _crt_checks(problem: Problem) -> bool:
    answer = int(Fraction(problem.answer))       # type: ignore[arg-type]
    if answer < 0:
        return False
    for part in problem.asked.split(',  '):
        body = part.strip()
        left, right = body.split(' = ')
        value, modulus = right.split(' (mod ')
        if answer % int(modulus.rstrip(')')) != int(value):
            return False
        if left.strip() != 'n':
            return False
    return True


def _congruence_checks(problem: Problem) -> bool:
    left, right = problem.asked.split(' = ')
    multiplier = int(left.strip().rstrip('x'))
    value, modulus = right.split('  (mod ')
    base = int(modulus.rstrip(')'))
    answer = int(Fraction(problem.answer))       # type: ignore[arg-type]
    return (0 <= answer < base
            and (multiplier * answer) % base == int(value))


def _sum_checks(problem: Problem) -> bool:
    """Re-read the printed sum with the player's own parser.

    Which is the point: the question a person sees is the question
    that gets checked, so a generator that prints something other
    than what it computed is caught here rather than by the player.
    """
    head = problem.asked.replace(TIMES, '*')
    try:
        got = parse(head)
    except (ParseError, ArithmeticError, ZeroDivisionError):
        return False
    return got.is_constant() and got.constant_value() == Fraction(
        problem.answer)                          # type: ignore[arg-type]


def _linear_checks(problem: Problem) -> bool:
    left, right = problem.asked.split(' = ')
    try:
        one, two = parse(left), parse(right)
    except (ParseError, ArithmeticError, ZeroDivisionError):
        return False
    at = {'x': Fraction(problem.answer)}         # type: ignore[arg-type]
    return one.evaluate(at) == two.evaluate(at)


# --- marking --------------------------------------------------------------


def collected(typed: str, answer: Poly) -> bool:
    """Whether *typed* is the answer *and already gathered up*.

    Normal form alone would accept the question back, because a
    question and its own answer are the same polynomial. So a
    symbolic answer must also be written out: no brackets, and no
    more written terms than the collected form has. Ordering is
    free — ``4 + 3x`` and ``3x + 4`` both pass — and so is an
    explicit times sign, which changes no term count.

    A *leading* sign is stripped before the terms are counted, because
    ``-2x - 1`` is two terms and not three, and a run of signs counts
    once, because ``1 + -11x`` is also two. Allowing a spare term
    instead — which is what this did first — let ``y + y + 3`` through
    as a gathered form of ``2y + 3``, which is the one thing the
    function exists to refuse.
    """
    if '(' in typed or ')' in typed:
        return False
    body = re.sub(r'^[+-]+', '', re.sub(r'\s+', '', typed))
    written = 1 + len(re.findall(r'[+-]+', body))
    return written <= len(answer.terms)


def correct(problem: Problem, typed: str) -> bool:
    """Whether *typed* answers *problem*. Exact, with no tolerance."""
    if not typed or not typed.strip():
        return False
    try:
        got = parse(typed)
    except (ParseError, ArithmeticError, ZeroDivisionError):
        return False
    if problem.grade.kind == NUMBER:
        return (got.is_constant()
                and got.constant_value() == Fraction(
                    problem.answer))             # type: ignore[arg-type]
    answer = problem.answer
    if not isinstance(answer, Poly):
        return False
    return got == answer and collected(typed, answer)


# --- the solver that knows no mathematics ---------------------------------


#: How many candidates :func:`crack` will look at before giving up.
#: Not a difficulty setting — a stopwatch. A rung whose space is
#: bigger than this is a rung searching cannot reach, which is the
#: whole claim the top of the ladder makes.
BUDGET = 200000


def walk_of(grade: Grade) -> str:
    """How a checker-only solver would sensibly search this rung.

    Not a detail: a rung that says *smallest n >= 0* is searched
    upwards, and one whose answer may be negative is searched outwards
    from zero. Searching a congruence outwards would throw away half
    of every step and report the rung as twice as hard as it is.
    """
    if grade.kind == EXPRESSION:
        return 'coefficients'
    if grade.family in ('crt', 'congruence'):
        return 'upward'
    if grade.family == 'fractions':
        return 'fractions'
    return 'outward'


def crack(problem: Problem, budget: int = BUDGET) -> Optional[int]:
    """Search the answer space, checking rather than reasoning.

    Returns how many candidates it looked at, or ``None`` if it ran
    out of budget. This is the ladder: what a rung gives away to
    somebody who cannot do the maths at all, only recognise the answer
    on tripping over it. It is a floor and not a solver, exactly like
    the reader in :mod:`neural_workshop.scramble`.

    It walks :attr:`Problem.space`, which is the same number
    :attr:`Problem.candidates` reports. That is deliberate and it is
    the one invariant here worth a test of its own: a space that does
    not contain the answer would make both columns meaningless while
    still printing a number.
    """
    walk = walk_of(problem.grade)
    ceiling = min(problem.space, budget)
    if walk == 'coefficients':
        return _crack_expression(problem, ceiling)
    answer = Fraction(problem.answer)            # type: ignore[arg-type]
    if walk == 'fractions':
        return _crack_fraction(answer, ceiling, fraction_grid(problem.grade))
    if walk == 'upward':
        for seen, guess in enumerate(range(ceiling), start=1):
            if guess == answer:
                return seen
        return None
    for seen, guess in enumerate(_outwards(ceiling // 2 + 1), start=1):
        if seen > ceiling:
            return None
        if guess == answer:
            return seen
    return None


def _outwards(span: int):
    """0, 1, -1, 2, -2, ... which is where small answers actually live."""
    yield 0
    for step in range(1, span + 1):
        yield step
        yield -step


def _crack_fraction(answer: Fraction, ceiling: int,
                    grid: Tuple[int, int]) -> Optional[int]:
    """Denominators down, numerators across."""
    rows, span = grid
    seen = 0
    for denominator in range(1, rows + 1):
        for numerator in _outwards(span):
            seen += 1
            if seen > ceiling:
                return None
            if Fraction(numerator, denominator) == answer:
                return seen
    return None


def _crack_expression(problem: Problem, ceiling: int) -> Optional[int]:
    """Every polynomial on the answer's monomials, coefficients banded.

    The band is the rung's own declared one, so the space searched is
    the space counted, and the answer is guaranteed to be inside it —
    the generator refuses to deal one that is not.
    """
    answer = problem.answer
    if not isinstance(answer, Poly):
        return None
    band = problem.grade.dials.get('band', 16)
    monomials = sorted(answer.terms, key=lambda mono: str(mono))
    for seen, values in enumerate(_bands(len(monomials), band), start=1):
        if seen > ceiling:
            return None
        if Poly(dict(zip(monomials, values))) == answer:
            return seen
    return None


def _bands(count: int, band: int):
    """Every coefficient tuple with entries in [-band, band]."""
    if not count:
        yield ()
        return
    for head in _outwards(band):
        for rest in _bands(count - 1, band):
            yield (head,) + rest


def guessable(problem: Problem) -> bool:
    """Whether the single commonest guess would have got it.

    Zero is the answer a guesser should try first on every numeric
    rung, so this is the floor below the floor and it belongs in the
    table rather than in a footnote.
    """
    if problem.grade.kind == EXPRESSION:
        return False
    return Fraction(problem.answer) == 0         # type: ignore[arg-type]


__all__ = ['BUDGET', 'EXPRESSION', 'GRADES', 'NUMBER', 'PRIMES', 'TIMES',
           'Grade', 'Problem', 'checks_out', 'collected', 'correct', 'crack',
           'deal_one', 'generate', 'grade_of', 'guessable', 'is_prime',
           'primes_near']
