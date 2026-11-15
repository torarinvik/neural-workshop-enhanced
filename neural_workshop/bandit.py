# -*- coding: utf-8 -*-
"""Explore or Exploit: a row of machines; pull the ones that pay.

Each machine pays a few coins a pull, around a mean of its own that the
player never sees. A run is a fixed number of pulls; the score is the
coins. Pulling the best-looking machine wins coins now; pulling another
finds out whether it has become better. Every machine shows its last
few payouts and how often it has been pulled.

* rungs 1-3: two machines that keep their means, one clearly better;
  thirty pulls;
* rungs 4-6: three or four machines, closer together; forty pulls;
* rungs 7-9: the means **drift**, a little every pull;
* rungs 10-12: and now and then they are dealt afresh, all at once;
* rungs 13-15: six machines, drifting faster;
* rungs 16-19: payouts are shown only every five pulls, all at once;
* from rung 20 eight machines, eighty pulls, noisier payouts.

The same run is fixed in advance -- what every machine would pay at
every pull -- so a player and the reference meet the very same luck.
Par is what the reference collects: it keeps a fading average of each
machine and tries one it knows little about when the doubt is worth
it. Ground is given below rung twenty; past it a share of the way to
pulling the best machine every time is asked for on top.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _


class Grade(NamedTuple):
    rung: int
    arms: int
    pulls: int
    gap: float
    drift: float
    jumps: int          # pulls between fresh deals; 0 for none
    batch: int          # payouts shown every this many pulls
    noise: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    arms = 2 if r < 4 else (3 + (r >= 5) if r < 13 else
                            (6 if r < 20 else 8))
    pulls = 30 if r < 4 else (40 if r < 7 else (60 if r < 20 else 80))
    return Grade(rung=r, arms=arms, pulls=pulls,
                 gap=3.0 if r < 4 else 1.5,
                 drift=0.0 if r < 7 else (0.3 if r < 13 else 0.5),
                 jumps=0 if r < 10 else 18,
                 batch=5 if r >= 16 else 1,
                 noise=2.0 if r < 20 else 2.6)


class Run(NamedTuple):
    rung: int
    level: Grade
    #: means[t][k]: machine k's mean at pull t.
    means: Tuple[Tuple[float, ...], ...]
    #: pays[t][k]: what machine k pays if pulled at pull t.
    pays: Tuple[Tuple[int, ...], ...]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Run:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)

    def fresh():
        while True:
            m = [draw.uniform(1.5, 8.5) for _k in range(level.arms)]
            top = sorted(m, reverse=True)
            if top[0] - top[1] >= level.gap * 0.6:
                return m
    m = fresh()
    means, pays = [], []
    for t in range(level.pulls):
        if level.jumps and t and t % level.jumps == 0:
            m = fresh()
        means.append(tuple(m))
        pays.append(tuple(int(max(0, min(10, round(draw.gauss(v, level.noise)))))
                          for v in m))
        if level.drift:
            m = [max(0.5, min(9.5, v + draw.gauss(0, level.drift)))
                 for v in m]
    return Run(level.rung, level, tuple(means), tuple(pays))


def seen_after(run: Run, t: int) -> int:
    """How many pulls' payouts are shown once *t* pulls are made."""
    b = run.level.batch
    return t - t % b if b > 1 else t


def play(run: Run, policy) -> int:
    """Coins a policy collects; *policy(history, t)* picks a machine
    from what is shown: history[k] is [(pull, pay), ...] seen so far."""
    chosen: List[int] = []
    coins = 0
    for t in range(run.level.pulls):
        shown = seen_after(run, t)
        history = [[] for _k in range(run.level.arms)]
        for s in range(shown):
            history[chosen[s]].append((s, run.pays[s][chosen[s]]))
        k = policy(history, t, chosen)
        chosen.append(k)
        coins += run.pays[t][k]
    return coins


def reference_policy(run: Run, fade: Optional[float] = None,
                     doubt: Optional[float] = None):
    level = run.level
    # Chosen once per kind of run, from a search over many runs: forget
    # nothing when nothing changes, a little when means drift, more when
    # they are dealt afresh.
    if fade is None:
        fade = 1.0 if not (level.drift or level.jumps) else \
            (0.92 if level.jumps else 0.97)
    if doubt is None:
        doubt = 1.5 if fade == 1.0 else 1.0

    def policy(history, t, chosen):
        best, pick = -1e9, 0
        total = 0.0
        stats = []
        for k, seen in enumerate(history):
            w = s = 0.0
            for pull, pay in seen:
                f = fade ** (t - pull)
                w += f
                s += f * pay
            stats.append((w, s))
            total += w
        for k, (w, s) in enumerate(stats):
            if w < 1e-6:
                # Not tried (or not yet shown): try it, unless it has
                # been pulled and is only waiting to be shown.
                if k not in chosen[seen_after(run, t):]:
                    return k
                score = 5.0
            else:
                score = s / w + doubt * math.sqrt(math.log(1 + total) / w)
            if score > best:
                best, pick = score, k
        return pick
    return policy


def reference(run: Run) -> int:
    return play(run, reference_policy(run))


def floor(run: Run) -> float:
    """What pulling at random collects, on average."""
    return sum(sum(row) / len(row) for row in run.pays)


def best(run: Run) -> int:
    """Pulling the machine with the best mean every time."""
    return sum(run.pays[t][max(range(run.level.arms),
                               key=lambda k: run.means[t][k])]
               for t in range(run.level.pulls))


def par(run: Run) -> float:
    from .ui.rungtask import ladder_par
    return ladder_par(run.rung, reference(run), floor(run), best(run))
