# -*- coding: utf-8 -*-
"""Delay: a little now, or more later -- if later comes.

A run lasts a minute. Offers come one after another: take the small
reward now, or wait for the large one. Waiting can be given up at any
moment, for nothing; while waiting, no other offer comes. The score is
what the run collects, so time is the price of waiting, and whether to
keep waiting depends on what the waits are like:

* rungs 1-3: every wait is the same and is shown: eight coins in three
  seconds against one now -- waiting pays;
* rungs 4-6: the wait is hidden and between two and six seconds:
  waiting still pays, giving up never does;
* rungs 7-9: most waits are short, but some go on far longer than the
  run: past a few seconds the large reward is probably a long way off,
  and giving up is right;
* rungs 10-12: every offer differs -- small, large and wait all shown:
  each must be weighed against what a second of the run is worth;
* rungs 13-15: hidden waits whose kind changes halfway through the run;
* rungs 16-19: three large rewards in ten never come; the rest come
  within four seconds;
* from rung 20 the kinds mixed and switching, in forty-five seconds.

Par is what the best fixed rule -- always take the small one, or wait
up to some number of seconds and then give up -- collects on the
identical run (or, where waits are shown, the best rule of taking the
large one when its pay per second clears a bar), with ground given
below rung twenty; past twenty a share of the way to what knowing every
wait in advance would collect is asked for on top.

Clocked: the waiting is real.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

#: Seconds taken to collect a reward, or to walk away from a wait.
COLLECT = 1.0
GIVE_UP = 0.5
NEVER = float('inf')


class Grade(NamedTuple):
    rung: int
    seconds: float
    kind: str        # 'fixed', 'uniform', 'heavy', 'varied', 'switch',
                     # 'never', 'mixed'
    shown: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 4:
        kind = 'fixed'
    elif r < 7:
        kind = 'uniform'
    elif r < 10:
        kind = 'heavy'
    elif r < 13:
        kind = 'varied'
    elif r < 16:
        kind = 'switch'
    elif r < 20:
        kind = 'never'
    else:
        kind = 'mixed'
    return Grade(r, 60.0 if r < 20 else 45.0, kind,
                 kind in ('fixed', 'varied'))


class Offer(NamedTuple):
    small: int
    large: int
    #: Seconds until the large reward comes; NEVER if it does not.
    wait: float


class Run(NamedTuple):
    rung: int
    level: Grade
    offers: Tuple[Offer, ...]


def _wait(draw: random.Random, kind: str) -> float:
    if kind == 'uniform':
        return draw.uniform(2.0, 6.0)
    if kind == 'heavy':
        if draw.random() < 0.6:
            return draw.uniform(1.0, 3.0)
        return 8.0 * (1.0 - draw.random()) ** -1.2     # Pareto, from 8 s
    if kind == 'never':
        return NEVER if draw.random() < 0.3 else draw.uniform(1.0, 4.0)
    return 3.0


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Run:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    offers: List[Offer] = []
    # More offers than any run can use.
    phase_kinds = ('uniform', 'heavy')
    if draw.random() < 0.5:
        phase_kinds = phase_kinds[::-1]
    mixed = draw.sample(('uniform', 'heavy', 'never'), 2)
    for k in range(200):
        if level.kind == 'fixed':
            offers.append(Offer(1, 8, 3.0))
        elif level.kind == 'varied':
            small = draw.randint(1, 3)
            large = draw.randint(small + 2, 12)
            offers.append(Offer(small, large,
                                round(draw.uniform(1.0, 8.0), 1)))
        elif level.kind == 'switch':
            offers.append(Offer(1, 8, _wait(draw, phase_kinds[k >= 14])))
        elif level.kind == 'mixed':
            offers.append(Offer(1, 8, _wait(draw, mixed[k >= 10])))
        else:
            offers.append(Offer(1, 8, _wait(draw, level.kind)))
    return Run(level.rung, level, tuple(offers))


# --- playing a rule through a run ----------------------------------------

def play(run: Run, choose) -> int:
    """Coins a rule collects. *choose(offer)* gives how long to wait
    (0 for the small reward now, NEVER to wait it out)."""
    t, coins = 0.0, 0
    end = run.level.seconds
    for offer in run.offers:
        if t >= end:
            break
        patience = choose(offer)
        if patience <= 0:
            coins += offer.small
            t += COLLECT
        elif offer.wait <= patience:
            if t + offer.wait <= end + 1e-9:
                coins += offer.large
            t += offer.wait + COLLECT
        else:
            t += min(patience, end - t) + GIVE_UP
    return coins


PATIENCE = (0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 15, 20, NEVER)


def reference(run: Run) -> int:
    """The best fixed rule on this very run."""
    if run.level.shown:
        bars = [0.0] + [b / 4.0 for b in range(1, 20)]
        return max(play(run, lambda o, b=b: o.wait if
                        o.large / (o.wait + COLLECT) >= b else 0)
                   for b in bars)
    return max([play(run, lambda o: 0)] +
               [play(run, lambda o, p=p: p) for p in PATIENCE])


def floor(run: Run) -> int:
    return play(run, lambda o: 0)


def best(run: Run) -> int:
    """Knowing every wait: take the large one when its pay per second
    beats a bar, the bar searched for."""
    bars = [b / 8.0 for b in range(0, 40)]
    return max(play(run, lambda o, b=b: o.wait if
                    o.wait < NEVER and o.large / (o.wait + COLLECT) >= b
                    else 0) for b in bars)


def par(run: Run) -> float:
    from .ui.rungtask import ladder_par
    return ladder_par(run.rung, reference(run), floor(run), best(run))
