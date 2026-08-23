# -*- coding: utf-8 -*-
"""Exact polynomials, a parser, and one canonical form to compare against.

The maths task needs three things this module is: arithmetic that is
never approximate, a way of reading what a player typed, and a way of
deciding whether two expressions that look nothing alike are the same
expression. All three are here and none of them is a dependency —
there is no sympy in this environment and there is not going to be, so
this is about four hundred lines of stdlib :mod:`fractions` instead.
That is more work than importing something, and it buys two things
worth having: every step is auditable, and nothing in the ladder can
be wrong in a way that is somebody else's fault.

**Exact, or it is not maths.** Every coefficient is a
:class:`~fractions.Fraction`. ``0.1 + 0.2`` is a wrong answer this
task would mark right if it used floats, and a ladder whose top rungs
turn on the thirtieth digit of an integer cannot use them at all.

**One canonical form.** A :class:`Poly` is a dictionary from monomial
to coefficient, kept normalised: exponents are positive, zero
coefficients are dropped, and monomials are sorted. Two polynomials
are equal exactly when those dictionaries are equal, so ``2y + 3``,
``3 + y + y`` and ``(4y + 6)/2`` are one answer rather than three.
That is what lets a rung ask for an expression and still be marked
exactly, with no tolerance and no second opinion.

**The parser is for a person in a hurry.** ``3x`` is ``3*x``,
``2(x+1)`` is ``2*(x+1)``, and ``-x^2`` is what it looks like.
Implicit multiplication is not an elegance; it is what people type,
and refusing it would make the task about the syntax.

What is deliberately *not* here: division by anything but a constant.
A rung that needs ``1/(x+1)`` would need rational functions, a second
normal form, and a gcd over polynomials to compare them — and no rung
does need it, because the ladder asks for coefficients and roots and
remainders, which are polynomials all the way up. Attempting it
raises rather than silently returning something almost right.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import re
from fractions import Fraction
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

#: A monomial: variable names with positive exponents, sorted by name.
#: The empty tuple is the constant monomial.
Mono = Tuple[Tuple[str, int], ...]

#: Variables a rung may use. Kept short deliberately — a task that
#: needed more letters than this would be asking a person to hold more
#: than the maths.
NAMES = ('x', 'y', 'z', 'n')

Number = (int, Fraction)


class ParseError(ValueError):
    """What a player typed is not an expression."""


def _mono(pairs: Iterable[Tuple[str, int]]) -> Mono:
    """A monomial from *pairs*, dropping zero powers and sorting."""
    kept: Dict[str, int] = {}
    for name, power in pairs:
        if power:
            kept[name] = kept.get(name, 0) + power
    return tuple(sorted((name, power) for name, power in kept.items()
                        if power))


class Poly:
    """A polynomial with exact rational coefficients.

    Immutable and hashable, so it can key a cache and sit in a set —
    which the candidate counting in :mod:`neural_workshop.algebra`
    relies on, because that is a count of *distinct normal forms*.
    """

    __slots__ = ('terms', '_hash')

    def __init__(self, terms: Optional[Mapping[Mono, object]] = None) -> None:
        kept: Dict[Mono, Fraction] = {}
        for mono, coefficient in (terms or {}).items():
            value = Fraction(coefficient)          # type: ignore[arg-type]
            if value:
                kept[_mono(mono)] = kept.get(_mono(mono), Fraction(0)) + value
        self.terms: Dict[Mono, Fraction] = {
            mono: value for mono, value in kept.items() if value}
        self._hash = hash(frozenset(self.terms.items()))

    # --- making one ------------------------------------------------------

    @classmethod
    def constant(cls, value) -> 'Poly':
        return cls({(): Fraction(value)})

    @classmethod
    def variable(cls, name: str) -> 'Poly':
        return cls({((name, 1),): Fraction(1)})

    # --- what it is ------------------------------------------------------

    def __bool__(self) -> bool:
        return bool(self.terms)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Poly):
            return self.terms == other.terms
        if isinstance(other, Number):
            return self.terms == Poly.constant(other).terms
        return NotImplemented

    def __hash__(self) -> int:
        return self._hash

    def is_constant(self) -> bool:
        return all(not mono for mono in self.terms)

    def constant_value(self) -> Fraction:
        """The constant, which is zero unless this *is* a constant."""
        if not self.is_constant():
            raise ValueError('not a constant: %s' % self)
        return self.terms.get((), Fraction(0))

    def variables(self) -> Tuple[str, ...]:
        found = {name for mono in self.terms for name, _power in mono}
        return tuple(sorted(found))

    def degree(self) -> int:
        """Total degree. The zero polynomial is degree zero by fiat."""
        return max((sum(power for _name, power in mono)
                    for mono in self.terms), default=0)

    def degree_in(self, name: str) -> int:
        return max((dict(mono).get(name, 0) for mono in self.terms),
                   default=0)

    def coefficient(self, name: str, power: int) -> Fraction:
        """The coefficient of ``name**power``, for a one-variable term.

        What most rungs actually ask for, so it is a method rather than
        something a caller works out of :attr:`terms`.
        """
        want = _mono([(name, power)])
        return self.terms.get(want, Fraction(0))

    # --- arithmetic ------------------------------------------------------

    def __add__(self, other) -> 'Poly':
        other = as_poly(other)
        terms = dict(self.terms)
        for mono, value in other.terms.items():
            terms[mono] = terms.get(mono, Fraction(0)) + value
        return Poly(terms)

    __radd__ = __add__

    def __neg__(self) -> 'Poly':
        return Poly({mono: -value for mono, value in self.terms.items()})

    def __sub__(self, other) -> 'Poly':
        return self + (-as_poly(other))

    def __rsub__(self, other) -> 'Poly':
        return as_poly(other) + (-self)

    def __mul__(self, other) -> 'Poly':
        other = as_poly(other)
        terms: Dict[Mono, Fraction] = {}
        for left, one in self.terms.items():
            for right, two in other.terms.items():
                mono = _mono(list(left) + list(right))
                terms[mono] = terms.get(mono, Fraction(0)) + one * two
        return Poly(terms)

    __rmul__ = __mul__

    def __truediv__(self, other) -> 'Poly':
        """Division by a constant only. See the module docstring."""
        other = as_poly(other)
        if not other.is_constant():
            raise ArithmeticError('cannot divide by a polynomial: %s' % other)
        value = other.constant_value()
        if not value:
            raise ZeroDivisionError('division by zero')
        return Poly({mono: one / value for mono, one in self.terms.items()})

    def __pow__(self, power: int) -> 'Poly':
        if not isinstance(power, int) or power < 0:
            raise ArithmeticError('only whole non-negative powers: %r' % power)
        out = Poly.constant(1)
        for _each in range(power):
            out = out * self
        return out

    # --- using it --------------------------------------------------------

    def evaluate(self, at: Mapping[str, object]) -> Fraction:
        """The value with every variable replaced. Exact, of course."""
        total = Fraction(0)
        for mono, coefficient in self.terms.items():
            term = coefficient
            for name, power in mono:
                if name not in at:
                    raise ValueError('no value given for %s' % name)
                term *= Fraction(at[name]) ** power  # type: ignore[arg-type]
            total += term
        return total

    def substitute(self, at: Mapping[str, 'Poly']) -> 'Poly':
        """Replace variables with polynomials rather than with numbers."""
        out = Poly()
        for mono, coefficient in self.terms.items():
            term = Poly.constant(coefficient)
            for name, power in mono:
                piece = at.get(name, Poly.variable(name))
                term = term * (piece ** power)
            out = out + term
        return out

    # --- reading it ------------------------------------------------------

    def __repr__(self) -> str:
        return 'Poly(%s)' % self

    def __str__(self) -> str:
        return render(self)


def as_poly(value) -> Poly:
    if isinstance(value, Poly):
        return value
    if isinstance(value, Number):
        return Poly.constant(value)
    raise TypeError('not a polynomial: %r' % (value,))


ZERO = Poly()
ONE = Poly.constant(1)


# --- writing one down -----------------------------------------------------


def _order(mono: Mono) -> Tuple:
    """Highest total degree first, then alphabetical. Reading order."""
    return (-sum(power for _name, power in mono),
            tuple((name, -power) for name, power in mono))


def render_mono(mono: Mono) -> str:
    if not mono:
        return ''
    out = []
    for name, power in mono:
        out.append(name if power == 1 else '%s^%d' % (name, power))
    return ''.join(out)


def render(poly: Poly) -> str:
    """The polynomial as a person would write it.

    Signs are folded into the joins, so it reads ``3x^2 - x + 4``
    rather than ``3x^2 + -1x + 4``. This is display only — nothing is
    ever compared as a string.
    """
    if not poly.terms:
        return '0'
    parts = []
    for mono in sorted(poly.terms, key=_order):
        coefficient = poly.terms[mono]
        body = render_mono(mono)
        size = abs(coefficient)
        if body and size == 1:
            shown = body
        elif body:
            shown = '%s%s' % (_number(size), body)
        else:
            shown = _number(size)
        parts.append(('-' if coefficient < 0 else '+', shown))
    sign, first = parts[0]
    out = ('-' + first) if sign == '-' else first
    for sign, shown in parts[1:]:
        out += ' %s %s' % (sign, shown)
    return out


def _number(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else str(value)


# --- reading one in -------------------------------------------------------


_TOKENS = re.compile(r'\s*(\d+|[a-z]|\*\*|[-+*/^()])')


def _scan(text: str) -> Sequence[str]:
    out, at = [], 0
    while at < len(text):
        found = _TOKENS.match(text, at)
        if not found:
            if text[at].isspace():
                at += 1
                continue
            raise ParseError('cannot read %r' % text[at])
        out.append(found.group(1))
        at = found.end()
    return out


class _Reader:
    """Recursive descent, smallest thing that can read what people type."""

    def __init__(self, tokens: Sequence[str]) -> None:
        self.tokens = list(tokens)
        self.at = 0

    def peek(self) -> Optional[str]:
        return self.tokens[self.at] if self.at < len(self.tokens) else None

    def take(self) -> str:
        token = self.peek()
        if token is None:
            raise ParseError('the expression stops early')
        self.at += 1
        return token

    def expression(self) -> Poly:
        out = self.term()
        while self.peek() in ('+', '-'):
            if self.take() == '+':
                out = out + self.term()
            else:
                out = out - self.term()
        return out

    def term(self) -> Poly:
        out = self.factor()
        while True:
            token = self.peek()
            if token in ('*', '/'):
                self.take()
                out = out * self.factor() if token == '*' \
                    else out / self.factor()
            elif self._implicit():
                # 3x, 2(x+1), (x+1)(x-1) -- what people write.
                out = out * self.factor()
            else:
                return out

    def _implicit(self) -> bool:
        token = self.peek()
        return token is not None and (token == '(' or token.isdigit()
                                      or (token.isalpha() and len(token) == 1))

    def factor(self) -> Poly:
        """A signed power.

        The sign is stripped *here* and not in :meth:`base`, which is
        the difference between ``-x^2`` meaning what everyone means by
        it and meaning ``(-x)^2``. Parsed the other way round the two
        agree on x = 0 and nowhere else, so a rung asking for a
        coefficient would mark a right answer wrong and look like a
        generator fault.
        """
        token = self.peek()
        if token == '-':
            self.take()
            return -self.factor()
        if token == '+':
            self.take()
            return self.factor()
        return self.power()

    def power(self) -> Poly:
        out = self.base()
        if self.peek() in ('^', '**'):
            self.take()
            # Right-associative, and the exponent may carry a sign, so
            # that x^-1 is refused for being negative rather than for
            # being unreadable.
            exponent = self.factor()
            if not exponent.is_constant():
                raise ParseError('a power has to be a whole number')
            value = exponent.constant_value()
            if value.denominator != 1 or value < 0:
                raise ParseError('a power has to be a whole number')
            out = out ** int(value)
        return out

    def base(self) -> Poly:
        token = self.take()
        if token == '(':
            inside = self.expression()
            if self.peek() != ')':
                raise ParseError('a bracket is not closed')
            self.take()
            return inside
        if token.isdigit():
            return Poly.constant(int(token))
        if token.isalpha() and len(token) == 1:
            if token not in NAMES:
                raise ParseError('%s is not one of the letters used here'
                                 % token)
            return Poly.variable(token)
        raise ParseError('cannot read %r here' % token)


def parse(text: str) -> Poly:
    """Read *text* as a polynomial, or raise :class:`ParseError`.

    Empty input is an error rather than zero. A player who has typed
    nothing has not answered nought; they have not answered.
    """
    if not text or not text.strip():
        raise ParseError('nothing to read')
    reader = _Reader(_scan(text.lower()))
    if not reader.tokens:
        raise ParseError('nothing to read')
    out = reader.expression()
    if reader.peek() is not None:
        raise ParseError('cannot read %r' % reader.peek())
    return out


def same(one: str, other) -> bool:
    """Whether typed text *one* is the expression *other*.

    The whole of the marking for a symbolic rung. Unreadable input is
    a wrong answer rather than an exception, because a player typing
    ``3x+`` and pressing return has answered wrongly, not crashed.
    """
    try:
        return parse(one) == as_poly(other)
    except (ParseError, ArithmeticError, ZeroDivisionError):
        return False


__all__ = ['Mono', 'NAMES', 'ONE', 'ParseError', 'Poly', 'ZERO', 'as_poly',
           'parse', 'render', 'render_mono', 'same']
