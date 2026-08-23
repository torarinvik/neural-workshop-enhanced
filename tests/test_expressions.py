#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The exact-arithmetic kernel: precedence, normal form, and what it refuses.

Everything the algebra task claims rests on this module being right,
and it can be wrong in two ways that do not look wrong.

A **precedence** slip marks correct answers incorrect. ``-x^2`` parsed
as ``(-x)^2`` agrees with the truth at x = 0 and nowhere else, so a
rung asking for a coefficient would fail a player who was right, and
it would read as a fault in the generator. That one was there, and it
is why the sign is stripped in ``factor`` rather than in ``base``.

A **normal form** slip marks incorrect answers correct, which is
worse because nothing ever complains. ``2y + 3`` and ``3 + y + y``
have to be one answer; ``2y + 3`` and ``2y + 4`` must never be.

So both directions are tested, and the round trip — render a
polynomial, read it back, get the same polynomial — is checked over
generated polynomials rather than over a handful chosen by whoever
wrote the renderer.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import sys
import unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from neural_workshop.expressions import (              # noqa: E402
    NAMES, ParseError, Poly, parse, render, same)

X = Poly.variable('x')
Y = Poly.variable('y')


class ThePrecedenceIsTheOrdinaryOne(unittest.TestCase):
    """What people mean when they write it, not what is easy to parse."""

    def test_a_minus_binds_looser_than_a_power(self):
        self.assertEqual(parse('-x^2'), -(X ** 2))
        self.assertEqual(parse('-2^2'), Poly.constant(-4))
        self.assertEqual(parse('(-2)^2'), Poly.constant(4))

    def test_powers_are_right_associative(self):
        self.assertEqual(parse('2^3^2'), Poly.constant(512))

    def test_times_binds_tighter_than_plus(self):
        self.assertEqual(parse('3 + 4 * 2'), Poly.constant(11))
        self.assertEqual(parse('(3 + 4) * 2'), Poly.constant(14))

    def test_a_power_binds_tighter_than_times(self):
        self.assertEqual(parse('2*x^3'), 2 * X ** 3)
        self.assertEqual(parse('x^2y'), X ** 2 * Y)

    def test_subtraction_goes_left_to_right(self):
        self.assertEqual(parse('10 - 3 - 2'), Poly.constant(5))


class WhatPeopleActuallyType(unittest.TestCase):
    """Implicit multiplication, and both spellings of a power."""

    def test_a_number_beside_a_letter_is_a_product(self):
        self.assertEqual(parse('3x'), 3 * X)

    def test_a_number_beside_a_bracket_is_a_product(self):
        self.assertEqual(parse('2(x+1)'), 2 * X + 2)

    def test_two_brackets_are_a_product(self):
        self.assertEqual(parse('(x+1)(x-1)'), X * X - 1)

    def test_both_power_signs_work(self):
        self.assertEqual(parse('x**3'), parse('x^3'))

    def test_spaces_do_not_matter(self):
        self.assertEqual(parse('  3 x  +  4 '), parse('3x+4'))

    def test_capitals_do_not_matter(self):
        self.assertEqual(parse('3X + 4'), 3 * X + 4)


class OneFormToCompareAgainst(unittest.TestCase):
    """The whole of the marking for a symbolic rung."""

    def test_the_same_polynomial_written_three_ways(self):
        one, two = parse('2y + 3'), parse('3 + y + y')
        three = parse('(4y+6)/2')
        self.assertEqual(one, two)
        self.assertEqual(two, three)

    def test_a_different_polynomial_is_different(self):
        self.assertNotEqual(parse('2y + 3'), parse('2y + 4'))
        self.assertNotEqual(parse('2y + 3'), parse('2x + 3'))

    def test_equal_polynomials_hash_alike(self):
        """Used as dictionary keys when candidates are counted."""
        self.assertEqual(hash(parse('3 + y + y')), hash(parse('2y + 3')))
        self.assertEqual(len({parse('2y+3'), parse('3+y+y')}), 1)

    def test_zero_terms_are_dropped(self):
        self.assertEqual(parse('x - x'), Poly())
        self.assertEqual(parse('x - x + 4'), Poly.constant(4))
        self.assertFalse(parse('x - x').terms)

    def test_a_constant_knows_it_is_one(self):
        self.assertTrue(parse('3 + 4').is_constant())
        self.assertEqual(parse('3 + 4').constant_value(), Fraction(7))
        self.assertFalse(parse('x + 4').is_constant())


class ItIsExact(unittest.TestCase):
    """A float anywhere in here would be a wrong answer marked right."""

    def test_thirds_stay_thirds(self):
        self.assertEqual(parse('1/3 + 1/3 + 1/3'), Poly.constant(1))

    def test_a_fraction_is_a_fraction(self):
        self.assertEqual(parse('2/3 + 3/4').constant_value(),
                         Fraction(17, 12))

    def test_the_same_value_written_differently_is_equal(self):
        self.assertEqual(parse('64/35'), parse('128/70'))

    def test_every_coefficient_is_a_fraction(self):
        for value in parse('x/3 - 2y/7 + 5').terms.values():
            self.assertIsInstance(value, Fraction)

    def test_a_decimal_point_is_not_readable(self):
        """Deliberate: 1.828 is not an answer to 7/5 + 3/7."""
        with self.assertRaises(ParseError):
            parse('1.828')


class WhatItRefuses(unittest.TestCase):
    """Refusing loudly beats returning something almost right."""

    def test_nothing_is_not_zero(self):
        for text in ('', '   '):
            with self.assertRaises(ParseError):
                parse(text)

    def test_an_unclosed_bracket(self):
        with self.assertRaises(ParseError):
            parse('(x+1')

    def test_an_expression_that_stops(self):
        with self.assertRaises(ParseError):
            parse('3x+')

    def test_a_letter_the_task_does_not_use(self):
        with self.assertRaises(ParseError):
            parse('q + 1')
        for name in NAMES:
            self.assertTrue(parse('%s + 1' % name))

    def test_a_negative_or_symbolic_power(self):
        for text in ('x^-1', 'x^y', 'x^(1/2)'):
            with self.assertRaises(ParseError):
                parse(text)

    def test_dividing_by_a_polynomial(self):
        with self.assertRaises(ArithmeticError):
            parse('1/(x+1)')

    def test_dividing_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            parse('1/0')

    def test_unreadable_input_is_a_wrong_answer_not_a_crash(self):
        self.assertFalse(same('3x+', 3 * X))
        self.assertFalse(same('', Poly()))
        self.assertFalse(same('1/(x+1)', X))


class TheRoundTripHolds(unittest.TestCase):
    """Render it, read it back, get it again — over generated ones."""

    def polynomials(self, count=200, seed=5):
        rng = random.Random(seed)
        for _each in range(count):
            terms = {}
            for _term in range(rng.randint(1, 5)):
                mono = tuple(sorted(
                    (name, rng.randint(1, 3))
                    for name in rng.sample(('x', 'y'), rng.randint(0, 2))))
                terms[mono] = Fraction(rng.randint(-30, 30),
                                       rng.choice((1, 1, 1, 2, 3, 7)))
            yield Poly(terms)

    def test_rendering_then_reading_is_the_identity(self):
        for poly in self.polynomials():
            self.assertEqual(parse(render(poly)), poly, render(poly))

    def test_rendering_never_produces_a_double_sign(self):
        for poly in self.polynomials():
            self.assertNotIn('+ -', render(poly))
            self.assertNotIn('--', render(poly))

    def test_the_zero_polynomial_renders_as_zero(self):
        self.assertEqual(render(Poly()), '0')
        self.assertEqual(parse('0'), Poly())


class TheArithmeticIsArithmetic(unittest.TestCase):
    """Checked against evaluation, which is a different code path."""

    def test_a_product_evaluates_like_its_factors(self):
        rng = random.Random(9)
        one, two = parse('3x^2 - 2x + 1'), parse('x + 4')
        product = one * two
        for _each in range(20):
            at = {'x': Fraction(rng.randint(-8, 8))}
            self.assertEqual(product.evaluate(at),
                             one.evaluate(at) * two.evaluate(at))

    def test_a_power_is_repeated_multiplication(self):
        self.assertEqual(parse('(x+1)^3'), parse('(x+1)(x+1)(x+1)'))
        self.assertEqual(parse('x^0'), Poly.constant(1))

    def test_substituting_a_polynomial(self):
        got = parse('x^2 + 1').substitute({'x': parse('y + 1')})
        self.assertEqual(got, parse('y^2 + 2y + 2'))

    def test_degree_and_coefficients(self):
        poly = parse('5x^3 - 7x + 2')
        self.assertEqual(poly.degree(), 3)
        self.assertEqual(poly.coefficient('x', 3), Fraction(5))
        self.assertEqual(poly.coefficient('x', 2), Fraction(0))
        self.assertEqual(poly.coefficient('x', 0), Fraction(2))

    def test_variables_are_reported(self):
        self.assertEqual(parse('x^2y - 3').variables(), ('x', 'y'))
        self.assertEqual(parse('7').variables(), ())

    def test_evaluating_needs_every_letter(self):
        with self.assertRaises(ValueError):
            parse('x + y').evaluate({'x': 1})


if __name__ == '__main__':
    unittest.main()
