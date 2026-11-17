# -*- coding: utf-8 -*-
"""Longer or Sooner?: which lasted longer; which came first?

Two kinds of question about time, each asked of a light or a tone:

* **which lasted longer** -- two in turn, the first and the second;
* **which came first** -- two at once, on the left and on the right,
  one a moment before the other (the tones on the left and right ear).

Higher up the senses are led astray: the shorter of two is the
brighter, the bigger or the higher-pitched -- all of which make a thing
seem to last longer -- and the later of two onsets is the stronger.

The ladder:

* rungs 1-3: which lasted longer, one twice the other;
* rungs 4-6: three to two; which came first as well, a third of a
  second apart;
* rungs 7-9: thirteen to ten; a twelfth of a second apart; the shorter
  one the stronger;
* rungs 10-12: six to five; a twentieth; the later onset the stronger;
* from rung 13: the ratio closes toward 1.03 and the gap toward eight
  thousandths of a second.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from . import showing
from .i18n import _

FIRST, SECOND = 0, 1
LEFT, RIGHT = 0, 1


class Grade(NamedTuple):
    rung: int
    ratio: float
    gap: float           # seconds between onsets, which-came-first
    order: bool          # which-came-first questions too
    lure: bool           # the shorter (or later) is the stronger


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        ratio=(2.0 if r < 4 else 1.5 if r < 7 else 1.3 if r < 10
               else 1.2 if r < 13 else max(1.03, 1.15 - 0.006 * (r - 13))),
        gap=(0.33 if r < 7 else 0.083 if r < 10 else 0.05 if r < 13
             else max(0.008, 0.04 - 0.002 * (r - 13))),
        order=r >= 4,
        lure=r >= 7)


class Event(NamedTuple):
    t0: float
    t1: float
    side: int            # -1 the middle, else LEFT or RIGHT
    strong: bool


class Puzzle(NamedTuple):
    level: Grade
    kind: str            # 'longer' or 'first'
    guise: str           # 'light' or 'tone'
    events: List[Event]
    hue: Tuple[int, int, int]
    open_at: float
    limit: float
    notes: tuple
    patches: tuple
    question: str
    choices: Tuple[str, ...]
    answer: int


def lit(p: Puzzle, t: float) -> List[Event]:
    return [e for e in p.events if e.t0 <= t < e.t1]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Puzzle:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    kind = 'first' if level.order and draw.random() < 0.45 else 'longer'
    guise = draw.choice(('light', 'tone'))
    hue = draw.choice(((250, 200, 60), (90, 200, 250), (250, 120, 160),
                       (130, 230, 120)))
    base = draw.uniform(440, 700)
    if kind == 'longer':
        short = draw.uniform(0.3, 0.8)
        long_ = short * level.ratio
        answer = draw.choice((FIRST, SECOND))
        d = [short, short]
        d[answer] = long_
        t0 = 0.8
        gap = draw.uniform(0.6, 0.9)
        events = [Event(t0, t0 + d[0], -1, level.lure and answer == SECOND),
                  Event(t0 + d[0] + gap, t0 + d[0] + gap + d[1], -1,
                        level.lure and answer == FIRST)]
        notes = ()
        if guise == 'tone':
            notes = tuple(showing.note(
                e.t0, e.t1 - e.t0,
                base * (1.5 if e.strong else 1.0), 0.0,
                0.95 if e.strong else 0.55) for e in events)
        end = events[1].t1
        q = _('Which lasted longer?')
        choices = (_('First'), _('Second'))
    else:
        answer = draw.choice((LEFT, RIGHT))
        t0 = 0.8
        on = [t0 + level.gap, t0 + level.gap]
        on[answer] = t0
        hold = 0.6
        events = [Event(on[s], on[s] + hold + draw.uniform(-0.05, 0.05), s,
                        level.lure and s != answer)
                  for s in (LEFT, RIGHT)]
        notes = ()
        if guise == 'tone':
            notes = tuple(showing.note(
                e.t0, e.t1 - e.t0, base * (1.0 if e.side == LEFT else 1.26),
                -0.9 if e.side == LEFT else 0.9,
                0.95 if e.strong else 0.6) for e in events)
        end = max(e.t1 for e in events)
        q = _('Which came first?')
        choices = (_('Left'), _('Right'))
    patches = (showing.patch('sine', seed),) if notes else ()
    if notes:
        q = _('Listen. ') + q
    return Puzzle(level, kind, guise, events, hue, end + 0.05, end + 6.0,
                  notes, patches, q, choices, answer)
