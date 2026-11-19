# -*- coding: utf-8 -*-
"""In the Window.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import NamedTuple, Optional, Tuple

from .i18n import _

PRESS, WAIT = 0, 1
PORTS = 2
EVENTS = frozenset((PRESS,))
ROUNDS = 3
HUES = ((36, 104, 196), (122, 70, 170), (20, 124, 132), (176, 110, 20),
        (150, 70, 110))


def window(rung: int) -> float:
    return max(0.02, 0.5 * (5.0 / 6.0) ** (max(1, int(rung)) - 1))


class Dealt(NamedTuple):
    rung: int
    share: float
    start: float
    marker: float
    period: float
    way: int
    track: str
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
    """In the Window."""

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
    return PRESS if inside(run.dealt, run.at) else WAIT
