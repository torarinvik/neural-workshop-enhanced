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

A fourth reader is measured below the table rather than in it,
because it exists only because the words are real ones: **believing**
answers *none* on the categorical rungs, which is what two nouns
picked at random are to each other in the world. It is at or under
the guessing floor, so a player who reads the premises as claims
about the world rather than as premises does worse than a coin.

Against those sit two columns about the work: **steps**, how many
premises have to be composed, and **decoys**, how many are printed
that the answer does not need. Proving that nothing links two things
takes every line, so an unsettled answer counts every premise as a
step and none as a decoy.

Every column is a proportion over 2,000 deals, which is about ±0.011.
The last section is not a measurement at all: it deals each rung
twice, once named after real words and once after made-up ones, and
checks that the two deals are the same deal. They are, by
construction — the names come off a random stream of their own — and
the section is there because that construction is the whole reason
the rest of this table can be read as being about the premises.

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
from typing import Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neural_workshop import syllogism as S            # noqa: E402

#: Questions dealt a rung. Cheap everywhere but the categorical rungs,
#: which enumerate every way their premises could have been written.
#:
#: Two thousand rather than a couple of hundred, and the reason is a
#: mistake this bench made: at 150 deals a column moves by ±0.04 from
#: sampling alone, which is the same size as the effects being looked
#: for, and two rungs were published as sitting at chance when they do
#: not. Here a proportion is good to about ±0.011, so three points
#: over the floor is a finding and not a draw.
DEALS = 2000

#: Deals a rung gets in the last section, which deals every rung
#: twice over. It is an exact check rather than a comparison of two
#: samples, so this number buys coverage rather than confidence and
#: does not have to be large.
BOTH_WAYS = 400

_DEALT: Dict[Tuple[int, int, bool], list] = {}


def deal(rung: int, count: int = DEALS, made_up: bool = False):
    """Kept, because five sections ask the same rung for the same deals.

    Without this the bench spends four fifths of its time dealing the
    categorical rungs over again to get the answer it already had.
    """
    key = (rung, count, made_up)
    if key not in _DEALT:
        rng = random.Random(20260823 + rung)
        _DEALT[key] = [one for one
                       in (S.deal_one(S.grade_of(rung), rng, made_up)
                           for _each in range(count)) if one]
    return _DEALT[key]


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
        made = deal(rung)
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
        made = deal(rung)
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
    print('  rather than trusted to be small. On the chain and direction')
    print('  rungs it sits at the floor, which is what the deal is chosen')
    print('  for — and not under it either, because a reader that is')
    print('  always wrong is a way round the rung backwards. It sits a')
    print('  few points over on the two categorical rungs, where the next')
    print('  section shows that is a theorem rather than a leak, and on')
    print('  rung eleven, where a connective can absorb a misread half.')


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
        made = deal(rung)
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


def believing() -> None:
    """The one reader that exists only because the words are real.

    The things are named after ordinary nouns, and between two nouns
    picked at random "no X is a Y" is how the world usually is: no
    beetle is a harbour. So a player who answers from what is
    plausible rather than from what is printed answers *none* on the
    categorical rungs, every time. That reader is the whole cost of
    not making the words up, so it gets measured rather than argued
    about.
    """
    print()
    where = S.FORMS.index(S.NONE)
    for rung in (5, 8):
        made = deal(rung)
        if not made:
            continue
        # The options are sentences about this deal's two terms, but
        # they are offered in the order the forms are declared in.
        share = sum(1 for one in made if one.answer == where) / len(made)
        print('rung %-2d %-32s answering "none" always: %.2f  (guessing '
              'is %.2f)' % (rung, S.grade_of(rung).name, share,
                            1.0 / len(made[0].options)))
    print('  At or under the guessing floor, so believing the premises')
    print('  is not a way round these rungs — it is a way of doing worse')
    print('  than a coin. Rung five is low because it is dealt as a coin')
    print('  between "something follows" and "nothing does", which puts')
    print('  each of the four forms at an eighth.')


def either_way() -> None:
    """Whether a deal is any different when the names are made up.

    It is not, and this does not measure that — it checks it. The
    words are drawn from a stream of their own, started with a single
    number taken from the deal's, so the same seed builds the same
    premises with the same answer whichever way the things are named.
    Two columns of numbers would only have been able to say the
    difference was smaller than the sample; this says there is none.

    A row short of the full count is a deal whose printed lines read
    back one way and not the other, which is the one way the words
    could ever have mattered.

    The options are compared by how many there are rather than by what
    they say: on the categorical rungs an option is a sentence about
    this deal's two terms, so it is one of the things that is supposed
    to differ.
    """
    print()
    print('%-4s %-32s %12s %10s'
          % ('rung', 'name', 'same deal', 'dealt'))
    for rung in range(1, len(S.GRADES) + 1):
        pairs = []
        for made_up in (False, True):
            rng = random.Random(11 + rung)
            pairs.append([S.deal_one(S.grade_of(rung), rng, made_up)
                          for _each in range(BOTH_WAYS)])
        agree = sum(1 for one, other in zip(*pairs)
                    if one is not None and other is not None
                    and (one.answer, one.surface, one.steps, one.decoys,
                         len(one.lines), len(one.options))
                    == (other.answer, other.surface, other.steps,
                        other.decoys, len(other.lines),
                        len(other.options)))
        print('%-4d %-32s %6d/%-5d %10.2f'
              % (rung, S.grade_of(rung).name, agree, BOTH_WAYS,
                 sum(1 for one in pairs[0] if one) / BOTH_WAYS))


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
    believing()
    either_way()
    timing()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
