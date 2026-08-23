#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""What a rung of Scramble is worth. Not a test — run it directly.

    PYTHONPATH=.. ../.venv/bin/python bench_scramble.py

This is where the table in :mod:`neural_workshop.scramble` comes from,
and rerunning it is the way to find out whether it still holds after a
change to the ladder. It prints three things.

**The text.** How many sentences are on hand and how many of them each
rung can draw on. With nothing fetched this is the sixty-odd seed
sentences and the rungs will say so — a rung with a handful of lines
in it deals the same line twice in a run, which is a fact about the
bank and not about the ladder.

**The ladder.** For each rung: how many readings the letters still
allow, how many words are pinned by their own letters alone, and what
the context-free reader gets back. That last column is the ladder.
It is not a solver — it knows no English at all — so what it gets is
what the page still says outright and everything above it is what a
reader has to bring.

**What the reader is blind to.** Four rungs in the middle sit at
almost the same number while being plainly not the same difficulty,
because moving the spaces and shuffling the words take nothing out of
the letters and the reader only reads letters. That is printed as its
own line rather than left for someone to notice in the table.

Two or three minutes, nearly all of it in the top rung: with the
spaces gone every substring of the line is a word to look up, and
there are hundreds of those.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neural_workshop import scramble as S            # noqa: E402
from neural_workshop import sentences as T           # noqa: E402

#: Deals a rung, for the ambiguity and pinned columns. Cheap.
DEALS = 40
#: Most deals a rung puts through the reader.
READS = 120
#: Longest a rung may spend reading. The top rung costs about two
#: seconds a line — every substring of a line with no gaps in it is a
#: word to look up — so a flat count would either starve the cheap
#: rungs of samples or make this bench ten minutes long. The table
#: prints the sample size it actually got, because a read-back over
#: fifteen lines and one over a hundred are not the same claim.
SECONDS = 25.0


def report_text() -> None:
    """What there is to read."""
    bank = T.bank()
    print('Sentences: %d %s'
          % (len(bank), 'fetched' if T.have() else 'seed (nothing fetched)'))
    if not T.have():
        print('  ' + T.missing_message())
    print()


def ladder() -> None:
    print('%-4s %-22s %6s %9s %7s %7s %5s %6s'
          % ('rung', 'name', 'lines', 'ambiguity', 'pinned', 'read', 'of',
             'secs'))
    scores = []
    for rung, grade in enumerate(S.GRADES, 1):
        available = len(T.choose(grade.span, grade.top_rank))
        rng = random.Random(20260823 + rung)
        start = time.time()
        deals = []
        for _each in range(DEALS):
            made = S.deal_one(grade, rng)
            if made is None:
                break
            deals.append(made)
        if not deals:
            print('%-4d %-22s %6d   no sentences of this shape'
                  % (rung, grade.name, available))
            scores.append(None)
            continue
        got = []
        reading = time.time()
        while len(got) < READS and time.time() - reading < SECONDS:
            more = S.deal_one(grade, rng)
            if more is None:
                break
            got.append(S.read_back(more))
        scores.append(statistics.mean(got) if got else None)
        print('%-4d %-22s %6d %9.1f %7.2f %7.2f %5d %6.1f'
              % (rung, grade.name, available,
                 statistics.median(one.ambiguity for one in deals),
                 statistics.mean(one.pinned / len(one.words)
                                 for one in deals),
                 scores[-1] or 0.0, len(got), time.time() - start))
    blind(scores)


def blind(scores) -> None:
    """Say out loud where the reader stops being able to tell rungs apart."""
    print()
    flat = [(rung, score) for rung, score in enumerate(scores, 1)
            if score is not None]
    if len(flat) < 2:
        return
    runs, current = [], [flat[0]]
    for rung, score in flat[1:]:
        if abs(score - current[-1][1]) <= 0.06:
            current.append((rung, score))
        else:
            runs.append(current)
            current = [(rung, score)]
    runs.append(current)
    for group in runs:
        if len(group) < 3:
            continue
        print('Rungs %d-%d read back within six points of each other (%s).'
              % (group[0][0], group[-1][0],
                 ' '.join('%.2f' % score for _rung, score in group)))
        print('  The reader only reads letters. Where a rung takes its '
              'difficulty')
        print('  out of the spaces or the word order instead, this column '
              'cannot see it.')


def main() -> int:
    report_text()
    ladder()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
