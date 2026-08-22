#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""What a rung of the two word games is worth. Not a test — run it directly.

    PYTHONPATH=.. ../.venv/bin/python bench_words.py

This is where the numbers in :mod:`neural_workshop.crossword` and
:mod:`neural_workshop.scrabble` come from, and rerunning it is the way
to find out whether they still hold after a change to either ladder.
It prints three things.

**The pool.** How many words are reachable, how many of them have a
clue, and what each rank band comes to. With nothing fetched this is
the seed list and the crossword half will say so and stop, which is
the honest outcome rather than a failure.

**The crossword ladder.** Whether each rung deals at all, how long it
takes, and how many candidate words it spent doing it. There is no
solver here to score a grid against, so what is measured is the *deal*
— and the number worth reading is not the time but the reliability:
a rung that deals seven times in eight is a rung that leaves a player
staring at a message one time in eight.

**The Scrabble ladder.** A player who knows only the three thousand
commonest words and, unlike any person, always finds the best play
among them. What share of the optimum that player scores is the whole
of what a Scrabble rung means: at the bottom it is all of it, because
down there the optimum *is* an everyday word and the task is placing
it; at the top it is two fifths, because up there it is not. Each
rung's passing share is set a little above what that player gets.

The whole thing takes about a minute, almost all of it in the
crossword fills.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import sys
import time

from neural_workshop import crossword as C
from neural_workshop import scrabble as S
from neural_workshop import wordlist as W

#: Deals a rung. Small because a nine by nine costs a second and a
#: half, and the numbers this prints are stable well before the noise
#: on them would be interesting.
CROSSWORDS = 8
BOARDS = 25

#: The band the stand-in player knows. Three thousand words is roughly
#: a comfortable reading vocabulary in the sense that matters here —
#: not what a person could recognise, but what they would produce.
KNOWS = 3000


def report_pool(say=print) -> bool:
    pooled = W.pool()
    say('%d words in the pool, %s'
        % (len(pooled),
           'with clues' if pooled.clued else 'with no clues (the seed list)'))
    if not pooled.clued:
        say('run  python -m neural_workshop.wordlist  to fetch the real one')
    for name, lo, hi in W.BANDS:
        say('  %-16s %6d words of three to eight letters'
            % (name, len(tuple(one for one in pooled.entries
                               if lo <= one.rank < hi
                               and 3 <= len(one.word) <= 8))))
    return pooled.clued


def crossword_ladder(say=print) -> None:
    say('\ncrossword — %d deals a rung\n' % CROSSWORDS)
    say('rung  name                 size  entry  band            dealt  '
        'seconds     tried')
    for rung in range(1, len(C.GRADES) + 1):
        grade = C.grade_of(rung)
        began = time.perf_counter()
        spent = []
        for seed in range(CROSSWORDS):
            made = C.generate(rung, seed=700 + seed)
            if made is not None:
                spent.append(made.tried)
        took = (time.perf_counter() - began) / CROSSWORDS
        say('%3d   %-20s %3d  %5d  %-14s  %d/%d  %7.2f  %8s'
            % (rung, grade.name, grade.size, grade.longest_entry,
               band_name(grade.top_rank), len(spent), CROSSWORDS, took,
               sorted(spent)[len(spent) // 2] if spent else '-'))


def band_name(top: int) -> str:
    for name, _lo, hi in W.BANDS:
        if top <= hi:
            return name
    return 'the whole list'


def scrabble_ladder(say=print) -> None:
    say('\nscrabble — %d boards a rung; "everyday" is a player who knows '
        'only\nthe %d commonest words and always finds the best play among '
        'them\n' % (BOARDS, KNOWS))
    say('rung  name                 size  band            best  everyday  '
        'needed   seconds')
    everyday = W.pool(KNOWS)
    for rung in range(1, len(S.GRADES) + 1):
        grade = S.grade_of(rung)
        began = time.perf_counter()
        tops, shares = [], []
        for seed in range(BOARDS):
            made = S.generate(rung, seed=900 + seed)
            if made is None:
                continue
            tops.append(made.ceiling)
            narrow = everyday.narrowed(
                hi=KNOWS, lengths=tuple(range(2, made.board.size + 1)))
            mine = S.best_play(made.board, made.rack, narrow)
            shares.append((mine.score if mine else 0) / float(made.ceiling))
        took = (time.perf_counter() - began) / BOARDS
        say('%3d   %-20s %3d  %-14s  %4.0f     %.2f      %.2f   %7.3f'
            % (rung, grade.name, grade.size, band_name(grade.top_rank),
               sum(tops) / len(tops), sum(shares) / len(shares), grade.share,
               took))


def main() -> int:
    began = time.perf_counter()
    clued = report_pool()
    if clued:
        crossword_ladder()
    else:
        print('\ncrossword — nothing to deal without clues')
    scrabble_ladder()
    print('\n%.0f seconds' % (time.perf_counter() - began))
    return 0


if __name__ == '__main__':
    sys.exit(main())
