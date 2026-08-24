#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""What a rung of Overrun is worth. Not a test — run it directly.

    PYTHONPATH=.. ../.venv/bin/python bench_overrun.py

This is where the table in :mod:`neural_workshop.overrun` comes from.

The task has one dial and the whole of this file is about whether that
dial means what it says. Three questions, in order of how much they
would cost to get wrong:

**Does a rung ask the same thing of every sentence it deals?** It is
supposed to: a wave starts with as much clear road ahead of it as it
has characters, so the time it allows is its own length over the
drift and the rate it demands is the drift, whatever was dealt. The
second section measures the spread of that rate inside a rung, and
prints beside it what the spread would have been under the obvious
alternative — every wave starting at the left-hand end of the lane —
which is the version that was written first.

**Can the rung be beaten without reading?** The third section plays
two rules against each other at sixty presses a second. Under the
rule this task uses, a wrong letter stays where it was put and a word
clears only on an exact match. Under the rule it does not use, a wrong
key is ignored, so a correct prefix can only grow. The second is
kinder and it is also the whole floor of the task: a uniform walk
lands a letter every twenty-six presses under it, and that turns out
to clear every wave to the fifth rung, ninety-five in a hundred at the
sixth and one in eight as high as the tenth. Two thirds of the ladder,
without reading a word of it.

**How long is a wave?** Printed because it is what decides whether a
step budget sees any outcomes at all: at the bottom rung a wave runs
nineteen seconds, which is 1,160 ticks, so a 900-step sweep of the
boundary can end without one having finished. That is the clock and
not the ports.

About twenty seconds.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import statistics
import sys
import time
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neural_workshop import overrun as O                # noqa: E402

#: Waves a rung is measured over. A proportion over this many is good
#: to about ±0.02, which is finer than any difference below is.
WAVES = 600

#: Presses a second a simulated typist gets. Sixty because that is the
#: rate the agent boundary steps a clocked task at, and the point of
#: the third section is what that rate is worth to a walk.
PRESSES = 60.0

_DEALT: Dict[Tuple[int, int], List[O.Wave]] = {}


def deal(rung: int, count: int = WAVES) -> List[O.Wave]:
    """Kept, because three sections ask the same rung for the same waves."""
    key = (rung, count)
    if key not in _DEALT:
        rng = random.Random(20260823 + rung)
        _DEALT[key] = [one for one
                       in (O.deal_one(O.grade_of(rung), rng)
                           for _each in range(count)) if one]
    return _DEALT[key]


def ladder() -> None:
    print('%-4s %-36s %5s %6s %6s %7s %6s'
          % ('rung', 'name', 'drift', 'chars', 'keys', 'seconds', 'wpm'))
    for rung in range(1, len(O.GRADES) + 1):
        made = deal(rung)
        if not made:
            print('%-4d %-36s dealt nothing' % (rung, O.grade_of(rung).name))
            continue
        grade = O.grade_of(rung)
        print('%-4d %-36s %5.1f %6.1f %6.1f %7.1f %6.1f'
              % (rung, grade.name, grade.speed,
                 statistics.mean(one.length for one in made),
                 statistics.mean(one.letters for one in made),
                 statistics.mean(one.seconds for one in made),
                 statistics.mean(O.words_a_minute(one.letters, one.seconds)
                                 for one in made)))


def runway() -> None:
    """Whether the rung asks one thing, or a different thing per sentence.

    The alternative measured beside it is not a straw man — it is what
    this task did first. Starting every wave at the left-hand end of
    the lane is the obvious layout, and under it the road ahead of a
    line is the lane minus the line, so a long sentence gets less time
    *and* has more to type. The two effects multiply.
    """
    print()
    print('what one rung asks of the fingers, in words a minute:')
    print('%-4s %-24s %-24s' % ('rung', 'runway = the text',
                                'every wave from the left'))
    for rung in (1, 6, 12):
        made = deal(rung)
        if not made:
            continue
        speed = O.grade_of(rung).speed
        ours = [O.words_a_minute(one.letters, one.length / speed)
                for one in made]
        theirs = [O.words_a_minute(one.letters,
                                   max(0.01, (O.CELLS - one.length) / speed))
                  for one in made]
        print('%-4d %6.1f  (%4.1f to %4.1f)   %6.1f  (%4.1f to %4.1f)'
              % (rung, statistics.mean(ours), min(ours), max(ours),
                 statistics.mean(theirs), min(theirs), max(theirs)))
    print('  The spread on the left is the sentences themselves — a line')
    print('  with long words in it is more keys for the same number of')
    print('  cells — and it is a few words a minute wide. The spread on')
    print('  the right is the layout, and it is a factor of three: the')
    print('  same rung would be two different tasks depending on which')
    print('  sentence came up.')


def press(wave: O.Wave, rng: random.Random, sticks: bool) -> bool:
    """Play one wave with a uniform walk. True if the line was cleared.

    *sticks* is the rule: with it on, a letter goes into the buffer
    wherever it lands and the word clears only on an exact match, which
    is what the task does. With it off, a wrong key is ignored and the
    correct prefix only ever grows, which is what it did first.

    Simulated rather than reasoned about because the race is not "type
    N letters in T seconds" — the deadline walks forward every time a
    word goes, so being ahead early is worth something and the closed
    form for that is worse than the loop.
    """
    letters = 'abcdefghijklmnopqrstuvwxyz'
    reach = len(letters) + (1 if sticks else 0)   # the rub-out is a port
    cleared, typed, drift = 0, '', 0.0
    step = 1.0 / PRESSES
    while cleared < len(wave.words):
        drift += wave.grade.speed * step
        if O.overrun(wave, cleared, drift):
            return False
        port = rng.randrange(reach)
        word = wave.words[cleared]
        if port == len(letters):                  # rub-out
            typed = typed[:-1]
            continue
        letter = letters[port]
        if sticks:
            if len(typed) < len(word):
                typed += letter
        elif letter == word[len(typed)]:
            typed += letter
        if typed == word:
            cleared += 1
            typed = ''
    return True


def mashing() -> None:
    """The two rules, played by something that cannot read."""
    print()
    print('waves a uniform walk clears at %g presses a second:' % PRESSES)
    print('%-4s %-36s %10s %10s %8s'
          % ('rung', 'name', 'letter sticks', 'ignored', 'asks for'))
    for rung in range(1, len(O.GRADES) + 1):
        made = deal(rung, 120)
        if not made:
            continue
        rng = random.Random(7 + rung)
        stuck = sum(1 for one in made if press(one, rng, True))
        rng = random.Random(7 + rung)
        loose = sum(1 for one in made if press(one, rng, False))
        print('%-4d %-36s %8.2f   %8.2f   %6.2f/s'
              % (rung, O.grade_of(rung).name, stuck / len(made),
                 loose / len(made),
                 statistics.mean(one.demand for one in made)))
    print('  The middle column is the task. The one beside it is the task it')
    print('  would have been. A walk never punished for a wrong key lands')
    print('  %.2f letters a second at this press rate, so the rungs asking'
          % (PRESSES / 26.0))
    print('  for less than that were always going to fall — but it clears')
    print('  rungs asking for half as much again on top of it, and that is')
    print('  the part worth having measured rather than worked out. The')
    print('  mean rate is not the race: the deadline walks forward every')
    print('  time a word goes, so a walk that gets lucky in the first two')
    print('  words is carrying that slack for the rest of the line.')


def budget() -> None:
    """How many ticks a wave is, which is what a step budget has to cover."""
    print()
    print('ticks a wave lasts at 60 Hz, if nothing is typed:')
    for rung in (1, 4, 8, 12):
        made = deal(rung)
        if not made:
            continue
        secs = statistics.mean(one.seconds for one in made)
        print('  rung %-2d %-36s %6.1f s   %5d ticks'
              % (rung, O.grade_of(rung).name, secs, int(secs * 60)))
    print('  A 900-step sweep of the boundary covers a wave from about the')
    print('  third rung up and does not reach the end of one below it. Zero')
    print('  outcomes at rung one is that, and not the ports.')


def timing() -> None:
    print()
    for rung in (1, 12):
        rng = random.Random(4)
        start = time.time()
        for _each in range(200):
            O.deal_one(O.grade_of(rung), rng)
        print('rung %-3d %-36s %6.3f ms a deal'
              % (rung, O.grade_of(rung).name, (time.time() - start) / 0.2))


def main() -> int:
    print('%d sentences in the pool, %d to %d characters, rank %d or better.'
          % (len(O.pool()), O.SHORTEST, O.LONGEST, O.TOP_RANK))
    print('Of a line\'s characters, %.3f are keys; the rest are gaps.'
          % O.letter_share())
    print()
    ladder()
    runway()
    mashing()
    budget()
    timing()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
