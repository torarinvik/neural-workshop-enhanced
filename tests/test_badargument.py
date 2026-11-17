#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Bad Argument: every made argument is what it says it is.

The forms are checked the hard way: each argument is read back, and its
conclusion tried against every way three or four sets (or two facts)
could be. Valid means no way makes the premises true and the
conclusion false.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import random
import re
import unittest

from feelingsupport import boundary, outcomes

from neural_workshop import badargument as M


def _cat_valid(text: str) -> bool:
    lines = [l.rstrip('.') for l in text.split('\n')]
    *premises, conclusion = lines
    conclusion = conclusion[len('So '):]
    claims = []
    for l in premises + [conclusion]:
        m = re.match(r'(All|all|No|no) (.+?) are (.+)$', l)
        assert m, l
        claims.append((m.group(1).lower(), m.group(2), m.group(3)))
    terms = sorted({t for _q, a, b in claims for t in (a, b)})
    world = range(3)
    subsets = [frozenset(c) for k in range(4)
               for c in itertools.combinations(world, k)]

    def holds(q, a, b, v):
        return v[a] <= v[b] if q == 'all' else not (v[a] & v[b])

    for pick in itertools.product(subsets, repeat=len(terms)):
        v = dict(zip(terms, pick))
        if all(holds(*c, v) for c in claims[:-1]) and \
                not holds(*claims[-1], v):
            return False
    return True


def _cond_valid(form: str) -> bool:
    given = {'mp': lambda p, q: p, 'mt': lambda p, q: not q,
             'ac': lambda p, q: q, 'da': lambda p, q: not p}[form]
    so = {'mp': lambda p, q: q, 'mt': lambda p, q: not p,
          'ac': lambda p, q: p, 'da': lambda p, q: not q}[form]
    return all(so(p, q) for p, q in itertools.product((0, 1), repeat=2)
               if ((not p) or q) and given(p, q))


class TheForms(unittest.TestCase):

    def test_every_categorical_argument_is_labelled_right(self):
        d = random.Random(1)
        for _k in range(60):
            for form in M.CAT:
                a = M.nonsense(form, d)
                self.assertEqual(_cat_valid(a.text), a.valid, a.text)
                for b in (True, False):
                    w = M.worldly(form, b, d)
                    if w is not None:
                        self.assertEqual(_cat_valid(w.text), w.valid, w.text)
            for valid in (True, False):
                c = M.chain(valid, d)
                self.assertEqual(_cat_valid(c.text), valid, c.text)

    def test_every_conditional_form_is_labelled_right(self):
        d = random.Random(2)
        for form in M.COND:
            self.assertEqual(M.nonsense(form, d).valid, _cond_valid(form))

    def test_judging_by_the_content_is_no_better_than_guessing(self):
        rnd = random.Random(3)
        right = n = 0
        for _k in range(400):
            valid, believable = rnd.random() < 0.5, rnd.random() < 0.5
            forms = [f for f in M.COND + M.CAT
                     if (f in ('mp', 'mt', 'barbara', 'celarent')) == valid]
            a = M.worldly(rnd.choice(forms), believable, rnd)
            if a is None:
                continue
            n += 1
            right += a.believable == a.valid
        self.assertLess(abs(right / n - 0.5), 0.1)

    def test_naming_the_flaw_from_rung_10(self):
        self.assertFalse(M.grade(9).name)
        self.assertTrue(M.grade(10).name)
        it = M.deal(10, seed=1).items
        self.assertTrue(any(len(i.steps[0].options) == 5 for i in it))


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for r, seed, ref, wins in outcomes(M, (1, 2, 4, 7, 10, 13, 16)):
            self.assertTrue(ref, (r, seed))
            self.assertEqual(wins, [], (r, seed))


class TheBoundary(unittest.TestCase):

    def test_reference_idle_and_sound(self):
        boundary(self, 'bad_argument', M, idle_steps=20000)


if __name__ == '__main__':
    unittest.main()
