#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""What a rung of Algebra is worth. Not a test — run it directly.

    PYTHONPATH=.. ../.venv/bin/python bench_algebra.py

This is where the table in :mod:`neural_workshop.algebra` comes from.
It prints four columns and they do not all say the same thing, which
is the point of printing four.

**candidates** is how many values the rung leaves standing before any
reasoning: the size of the space its answer is hidden in. Exact, and
free — the generator knows it.

**cracked** is what a solver that knows no mathematics gets. It can
only *check* an answer, so it walks that space until something fits.
Where this is 1.00 the rung gives itself away to patience alone.

**checks** is how many candidates that took, when it worked.

**steps** is how long the derivation is — how many moves the generator
made building the problem, which is an upper bound on how many are
needed to undo it.

**Candidates and steps disagree in the middle of the ladder, and that
is the finding rather than a defect.** A linear equation hides its
answer among nineteen and takes three steps to get; a sum of two
fractions hides its answer among a hundred thousand and takes one.
Searching is not reasoning, and a ladder built on either one alone
would be wrong in a different place. The rungs are ordered by what a
person has to know, and both columns are printed so that neither can
quietly become the definition.

About a minute.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neural_workshop import algebra as A            # noqa: E402

#: Problems dealt a rung. Cheap: the generator is exact arithmetic.
DEALS = 60
#: Problems a rung puts through the checker-only solver.
CRACKS = 12


def ladder() -> None:
    print('%-4s %-22s %-10s %10s %8s %10s %6s %6s'
          % ('rung', 'name', 'kind', 'candidates', 'cracked', 'checks',
             'steps', 'zero'))
    for rung, grade in enumerate(A.GRADES, 1):
        rng = random.Random(20260823 + rung)
        made = [one for one in (A.deal_one(grade, rng)
                                for _each in range(DEALS)) if one]
        if not made:
            print('%-4d %-22s dealt nothing' % (rung, grade.name))
            continue
        got = [A.crack(one) for one in made[:CRACKS]]
        checks = [one for one in got if one is not None]
        print('%-4d %-22s %-10s %10.1f %8.2f %10s %6.1f %6.2f'
              % (rung, grade.name, grade.kind,
                 statistics.median(one.candidates for one in made),
                 len(checks) / len(got),
                 int(statistics.median(checks)) if checks else '-',
                 statistics.mean(one.steps for one in made),
                 sum(1 for one in made if A.guessable(one)) / len(made)))


def disagreement() -> None:
    """Say out loud where the two columns tell different stories."""
    print()
    rows = []
    for rung, grade in enumerate(A.GRADES, 1):
        rng = random.Random(7 + rung)
        made = [one for one in (A.deal_one(grade, rng)
                                for _each in range(20)) if one]
        if made:
            rows.append((rung, grade.name,
                         statistics.median(one.candidates for one in made),
                         statistics.mean(one.steps for one in made)))
    worst = None
    for one in rows:
        for other in rows:
            if one[0] < other[0] and one[2] > other[2] + 1.5:
                gap = one[2] - other[2]
                if worst is None or gap > worst[0]:
                    worst = (gap, one, other)
    if worst is None:
        print('Candidates rise with the rung all the way up.')
        return
    _gap, low, high = worst
    print('Rung %d ("%s") hides its answer among 10^%.1f and rung %d '
          '("%s")' % (low[0], low[1], low[2], high[0], high[1]))
    print('  among 10^%.1f — the *earlier* rung has the bigger search, by '
          'a factor' % high[2])
    print('  of %d. Searching is not reasoning: rung %d takes %.0f steps '
          'and rung %d' % (10 ** (low[2] - high[2]), low[0], low[3], high[0]))
    print('  takes %.0f. Both columns are printed because either one '
          'alone would' % high[3])
    print('  put this ladder in the wrong order.')


def timing() -> None:
    print()
    for rung in (1, 7, 11, 12):
        grade = A.grade_of(rung)
        rng = random.Random(4)
        start = time.time()
        for _each in range(50):
            A.deal_one(grade, rng)
        print('rung %-3d %-22s %6.1f ms a deal'
              % (rung, grade.name, (time.time() - start) * 20))


def main() -> int:
    ladder()
    disagreement()
    timing()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
