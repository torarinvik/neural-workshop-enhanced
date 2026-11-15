# -*- coding: utf-8 -*-
"""Hold It: hold the key exactly as long as the lamp was lit.

A lamp lights, a tone sounds, for some time; then they go out. Hold the
key down for just as long -- the lamp lights again while it is held, but
nothing shows how long has gone. Close enough, measured as a share of
the time asked for, passes.

The ladder:

* rungs 1-3: one short time, a generous margin;
* rungs 4-6: longer times, a narrower margin;
* rungs 7-9: hold half as long, or twice as long, as was shown;
* rungs 10-12: two lamps, one after the other: hold for both together;
* rungs 13-15: a ticking clock runs at the wrong speed throughout, to
  lead the count astray;
* from rung 16: any of these, tighter every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Tuple

from .i18n import _

HOLD = 0
PORTS = 1
EVENTS = ()
LEAD = 0.8
GAP = 0.9                     # between lamps, and before your turn
WAIT = 4.0                    # seconds to start holding


class Grade(NamedTuple):
    rung: int
    kinds: Tuple[str, ...]    # 'copy', 'scale', 'sum'
    span: Tuple[float, float]
    margin: float             # share of the target either way
    ticks: bool               # a misleading ticking clock


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 16)
    return Grade(
        rung=r,
        kinds=(('copy',) if r < 7 else ('scale',) if r < 10 else ('sum',)
               if r < 13 else ('copy', 'scale', 'sum')),
        span=((0.8, 1.6) if r < 4 else (1.0, 3.0)),
        margin=(0.25 if r < 4 else 0.18 if r < 13 else 0.16 if r < 16
                else max(0.08, 0.15 - 0.01 * top)),
        ticks=r >= 13)


class Ask(NamedTuple):
    level: Grade
    kind: str
    lamps: List[Tuple[float, float]]   # (on, off) times
    factor: float                      # for 'scale'
    target: float                      # how long to hold
    turn: float                        # when the turn to hold begins
    tick: float                        # the wrong clock's period


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Ask:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    kind = draw.choice(level.kinds)
    lamps, t = [], LEAD
    count = 2 if kind == 'sum' else 1
    for _k in range(count):
        d = round(draw.uniform(*level.span) * (0.7 if count == 2 else 1.0),
                  2)
        lamps.append((t, t + d))
        t += d + GAP
    shown = sum(b - a for a, b in lamps)
    factor = 1.0
    if kind == 'scale':
        factor = draw.choice((0.5, 2.0)) if shown <= 2.0 else 0.5
    target = round(shown * factor, 3)
    tick = draw.choice((0.37, 0.61, 0.83)) if level.ticks else 0.0
    return Ask(level, kind, lamps, factor, target, t, tick)


class Run:
    def __init__(self, ask: Ask) -> None:
        self.ask = ask
        self.level = ask.level
        self.t = 0.0
        self.down: Optional[float] = None     # when the hold began
        self.held: Optional[float] = None     # how long it lasted
        self.holding = False
        self.result: Optional[Tuple[bool, str]] = None

    def lit(self) -> bool:
        """Whether the lamp shows now (shown, or held)."""
        return self.holding or any(a <= self.t < b
                                   for a, b in self.ask.lamps)

    def your_turn(self) -> bool:
        return self.t >= self.ask.turn

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self.t += dt
        pressing = control == HOLD
        if not self.your_turn():
            return
        if pressing and self.down is None:
            self.down = self.t - dt
            self.holding = True
        elif self.holding and not pressing:
            self.holding = False
            self.held = self.t - dt - self.down
            self._judge()
        elif self.down is None and self.t > self.ask.turn + WAIT:
            self.result = (False, _('No hold'))

    def _judge(self) -> None:
        target = self.ask.target
        off = (self.held - target) / target
        if abs(off) <= self.level.margin:
            self.result = (True, _('%.2f s for %.2f s') % (self.held, target))
        else:
            self.result = (False, _('%.2f s for %.2f s -- too %s') % (
                self.held, target, _('short') if off < 0 else _('long')))


def act(run: Run, port: int) -> None:
    pass


def autopilot(run: Run) -> List[int]:
    """Hold from the turn until the target has gone."""
    a = run.ask
    if run.your_turn() and (run.down is None or
                            run.t - run.down < a.target - 1e-9):
        return [HOLD]
    return []


def play(ask: Ask, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    run = Run(ask)
    while run.result is None:
        ports = pilot(run)
        run.step(dt, ports[0] if ports else None)
    return run.result
