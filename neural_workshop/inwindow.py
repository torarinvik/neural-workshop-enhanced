# -*- coding: utf-8 -*-
"""In the Window: press while the moving marker is inside the window.

A marker goes round a ring, or along a track and back to its start, at
a steady pace. Part of its path is marked as the window. One port
presses; the other waits, and waiting is always allowed. A press with
the marker inside the window passes, a press outside it fails, and a
trial left unpressed for three times round fails too.

At rung 1 the window is half the path, so a press at a moment chosen
blind is right half the time. Each rung narrows it by a sixth.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import NamedTuple, Optional, Tuple

from .i18n import _

PRESS, WAIT = 0, 1
PORTS = 2
#: The press acts once; waiting is a control that does nothing.
EVENTS = frozenset((PRESS,))
#: Times round before an unpressed trial is called.
ROUNDS = 3
HUES = ((36, 104, 196), (122, 70, 170), (20, 124, 132), (176, 110, 20),
        (150, 70, 110))


def window(rung: int) -> float:
    """The share of the path that is the window."""
    return max(0.02, 0.5 * (5.0 / 6.0) ** (max(1, int(rung)) - 1))


class Dealt(NamedTuple):
    rung: int
    share: float                 # the window, as a share of the path
    start: float                 # where the window begins, 0-1
    marker: float                # where the marker begins, 0-1
    period: float                # seconds once round
    way: int                     # +1 or -1
    track: str                   # 'ring' or 'line'
    hue: int
    place: Tuple[float, float, float]
    question: str


def deal(rung: int, rng: Optional[random.Random] = None) -> Dealt:
    rng = rng or random.Random()
    return Dealt(max(1, int(rung)), window(rung), rng.random(),
                 rng.random(), rng.uniform(1.6, 2.6), rng.choice((1, -1)),
                 rng.choice(('ring', 'line')), rng.randrange(len(HUES)),
                 (rng.random(), rng.random(), 0.75 + 0.25 * rng.random()),
                 _('Press while the marker is in the window'))


def inside(dealt: Dealt, at: float) -> bool:
    return (at - dealt.start) % 1.0 < dealt.share


class Run:
    """One trial's marker, and its verdict."""

    def __init__(self, dealt: Dealt) -> None:
        self.dealt = dealt
        self.t = 0.0
        self.result: Optional[Tuple[bool, str]] = None

    @property
    def at(self) -> float:
        d = self.dealt
        return (d.marker + d.way * self.t / d.period) % 1.0

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t >= ROUNDS * self.dealt.period:
            self.result = (False, _('Never pressed'))

    def press(self) -> None:
        if self.result is not None:
            return
        hit = inside(self.dealt, self.at)
        self.result = (hit, _('In the window') if hit
                       else _('Outside the window'))


def act(run: Run, port: int) -> None:
    if port == PRESS:
        run.press()


def pilot(run: Run) -> int:
    """Press when inside, else wait."""
    return PRESS if inside(run.dealt, run.at) else WAIT
