#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""What a rung of Syllogisms is worth. Not a test — run it directly.

    PYTHONPATH=.. ../.venv/bin/python bench_syllogism.py

This is where the table in :mod:`neural_workshop.syllogism` comes from.

**Counting what is left standing measures almost nothing here**, and
that is worth saying before the table rather than after it. Ten of the
twelve rungs offer three answers, so *candidates* is log-ten of three
on nearly all of them however long the derivation gets. It is the
opposite of Algebra, where the size of the space is the whole
difficulty. So this task is measured by three baselines that know
nothing instead, and any of them beating chance is a way round the
rung:

**guess** is one over the number of answers. **const** is what the
single best fixed answer gets — the column that says whether *cannot
be told* is really an answer or a decoration. **surface** is a reader
that never puts two premises together: it takes the one line that
names the thing being asked about and answers with that line's
relation. On the categorical rungs it is the atmosphere effect
instead — negative premise, negative conclusion; particular premise,
particular conclusion — which is a real thing people do and, on a
two-premise syllogism, is not even wrong.

Against those sit two columns about the work: **steps**, how many
premises have to be composed, and **decoys**, how many are printed
that the answer does not need. Proving that nothing links two things
takes every line, so an unsettled answer counts every premise as a
step and none as a decoy.

About a minute.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neural_workshop import syllogism as S            # noqa: E402

#: Questions dealt a rung. Cheap everywhere but the categorical rungs,
#: which enumerate every way their premises could have been written.
DEALS = 150


def deal(rung: int, count: int = DEALS):
    rng = random.Random(20260823 + rung)
    return [one for one in (S.deal_one(S.grade_of(rung), rng)
                            for _each in range(count)) if one]


def ladder() -> None:
    print('%-4s %-32s %5s %5s %6s %6s %7s %6s %6s'
          % ('rung', 'name', 'ans', 'lines', 'guess', 'const', 'surface',
             'steps', 'decoy'))
    for rung in range(1, len(S.GRADES) + 1):
        made = deal(rung)
        if not made:
            print('%-4d %-32s dealt nothing' % (rung, S.grade_of(rung).name))
            continue
        answers = len(made[0].options)
        tally = collections.Counter(one.answer for one in made)
        print('%-4d %-32s %5d %5.1f %6.2f %6.2f %7.2f %6.1f %6.1f'
              % (rung, S.grade_of(rung).name, answers,
                 statistics.mean(len(one.lines) for one in made),
                 1.0 / answers,
                 tally.most_common(1)[0][1] / len(made),
                 sum(1 for one in made if one.surface == one.answer)
                 / len(made),
                 statistics.mean(one.steps for one in made),
                 statistics.mean(one.decoys for one in made)))


def unsettled() -> None:
    """How often the honest answer is that the premises do not say."""
    print()
    print('how often "cannot be told" (or "nothing follows") is the answer:')
    for rung in range(1, len(S.GRADES) + 1):
        made = deal(rung, 80)
        if not made:
            continue
        options = made[0].options
        where = [number for number, one in enumerate(options)
                 if one in (S.UNTOLD, S.NOTHING)]
        if not where:
            print('  rung %-2d %-32s not offered — this rung always settles'
                  % (rung, S.grade_of(rung).name))
            continue
        share = sum(1 for one in made if one.answer in where) / len(made)
        print('  rung %-2d %-32s %.2f  (evenly would be %.2f)'
              % (rung, S.grade_of(rung).name, share, 1.0 / len(options)))


def faking() -> None:
    """Say out loud where a reader that knows nothing does best."""
    print()
    worst = None
    for rung in range(1, len(S.GRADES) + 1):
        made = deal(rung, 80)
        if not made:
            continue
        got = sum(1 for one in made if one.surface == one.answer) / len(made)
        over = got - 1.0 / len(made[0].options)
        if worst is None or over > worst[0]:
            worst = (over, rung, got, 1.0 / len(made[0].options))
    if worst is None:
        return
    _over, rung, got, floor = worst
    print('The surface reader does best on rung %d ("%s"): %.2f against a '
          % (rung, S.grade_of(rung).name, got))
    print('  guessing floor of %.2f. Everything above that floor is a rung'
          % floor)
    print('  that can be answered without reasoning, and it is printed')
    print('  rather than trusted to be small. Deals are chosen so that reader lands at')
    print('  chance and no better — and no worse either, because a reader')
    print('  that is always wrong is a way round the rung backwards.')


def atmosphere() -> None:
    """Where the surface reader is not a heuristic but a theorem.

    The classical rules — a valid conclusion is negative exactly when
    a premise is, and particular exactly when a premise is — are what
    the atmosphere reader knows. On a two-premise syllogism they are
    necessary conditions for validity, so whenever *something*
    follows, atmosphere names it. Measured rather than asserted,
    because the same is not true once there are premises off the path
    between the two terms being asked about.
    """
    print()
    for rung in (5, 8):
        made = deal(rung, 120)
        follows = [one for one in made if one.answer < len(S.FORMS)]
        if not follows:
            continue
        named = sum(1 for one in follows if one.surface == one.answer)
        print('rung %-2d %-32s something follows %3d/%d, and'
              % (rung, S.grade_of(rung).name, len(follows), len(made)))
        print('        atmosphere names it %3d of those times (%.2f)'
              % (named, named / len(follows)))
    print('  Where that is 1.00 the four forms are one answer between them')
    print('  and the only question left is whether anything follows at all,')
    print('  so the rung is dealt as the coin it is: both a fixed answer and')
    print('  the atmosphere reader sit at one half. That is the honest floor')
    print('  for a rung like that, and the reason there are two of these on')
    print('  the ladder rather than six.')


def timing() -> None:
    print()
    for rung in (1, 5, 8, 12):
        rng = random.Random(4)
        start = time.time()
        for _each in range(30):
            S.deal_one(S.grade_of(rung), rng)
        print('rung %-3d %-32s %6.1f ms a deal'
              % (rung, S.grade_of(rung).name, (time.time() - start) / 0.03))


def main() -> int:
    ladder()
    unsettled()
    faking()
    atmosphere()
    timing()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
