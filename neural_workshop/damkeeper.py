# -*- coding: utf-8 -*-
"""Dam Keeper: a chain of reservoirs, a town below, and storms coming.

Reservoirs sit one below another down a valley; a town lies past the
last dam. Each dam has a gate with notches from shut to wide open.
Water let out of one dam reaches the next after a while. Storm clouds
drift down the valley and rain into whichever reservoirs they pass
over. Keep every reservoir from overtopping its dam, never send the
town more water than its river can carry, and never let a reservoir
run so low its turbines stop.

The trick is time: a storm's water arrives faster than a gate can let
it out, so room has to be made before the storm, and what is let out
upstream arrives downstream later, just when it may be least wanted.

The ladder:

* rungs 1-3: two dams, one storm;
* rungs 4-6: three dams, two storms;
* rungs 7-9: slower rivers between dams, a lower flood line;
* rungs 10-12: bigger storms, back to back;
* rungs 13-15: gates that take time to move a notch;
* rungs 16-19: storms show only once they are over the valley;
* from rung 20: heavier rain and a lower flood line every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from collections import deque
from typing import Deque, List, NamedTuple, Optional, Tuple

from .i18n import _

MOST = 3
PORTS = 2 * MOST              # open / shut a notch, for each dam
EVENTS = tuple(range(PORTS))
NOTCHES = 4
FLOW = 6.0                    # % of a reservoir a second, gate wide open
BASE = 0.7                    # steady inflow at the top of the valley
LOW = 10.0                    # below this the turbines stop
LOW_GRACE = 3.0
FLOOD_GRACE = 1.5
SECONDS = 90.0
VALLEY = 100.0                # the valley's length, for clouds


class Grade(NamedTuple):
    rung: int
    dams: int
    storms: int
    rain: float           # % a second while a storm is overhead
    delay: float          # seconds from one dam to the next
    flood: float          # the town's river limit, % a second
    stiff: float          # seconds a gate takes per notch
    hidden: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        dams=2 if r < 4 else 3,
        storms=1 if r < 4 else 2 if r < 10 else 3,
        rain=(4.5 if r < 10 else 4.2 if r < 20
              else min(5.5, 4.4 + 0.06 * top)),
        delay=5.0 if r < 7 else 8.0,
        flood=(6.5 if r < 7 else 6.0 if r < 20
               else max(5.0, 5.8 - 0.04 * top)),
        stiff=0.0 if r < 13 else 1.2,
        hidden=r >= 16)


class Storm(NamedTuple):
    start: float          # when its front enters the valley
    speed: float          # valley units a second
    width: float          # valley units
    rain: float


class Valley(NamedTuple):
    level: Grade
    spans: List[Tuple[float, float]]    # each reservoir's stretch of valley
    storms: List[Storm]
    start: List[float]                  # starting levels


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Valley:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(25):
        valley = _build(level, draw)
        best = best or valley
        if play(valley)[0] and not play(valley, lambda run: [])[0]:
            return valley
    return best


def _build(level: Grade, draw: random.Random) -> Valley:
    n = level.dams
    cut = VALLEY / n
    spans = [(k * cut, (k + 1) * cut) for k in range(n)]
    storms = []
    t = draw.uniform(12.0, 22.0)
    for _k in range(level.storms):
        storms.append(Storm(round(t, 1), draw.uniform(4.0, 7.0),
                            draw.uniform(25.0, 45.0),
                            level.rain * draw.uniform(0.85, 1.15)))
        t += draw.uniform(16.0, 26.0) if level.rung < 10 else \
            draw.uniform(13.0, 20.0)
    start = [draw.uniform(40.0, 65.0) for _k in range(n)]
    return Valley(level, spans, storms, start)


class Run:
    def __init__(self, valley: Valley) -> None:
        self.valley = valley
        self.level = valley.level
        self.t = 0.0
        n = valley.level.dams
        self.water = list(valley.start)
        self.gate = [0] * n                  # notch the gate is set to
        self.opening = [0.0] * n             # where it actually is
        self.pipes: List[Deque[Tuple[float, float]]] = [deque()
                                                         for _k in range(n)]
        self.arriving = [0.0] * n
        self.town = 0.0
        self.low_for = [0.0] * n
        self.flood_for = 0.0
        self.result: Optional[Tuple[bool, str]] = None

    # --- the weather
    def storm_span(self, s: Storm, t: Optional[float] = None
                   ) -> Tuple[float, float]:
        """The stretch of valley a storm covers at *t* (front, back)."""
        t = self.t if t is None else t
        front = (t - s.start) * s.speed
        return front - s.width, front

    def rain_on(self, k: int, t: Optional[float] = None) -> float:
        lo, hi = self.valley.spans[k]
        total = 0.0
        for s in self.valley.storms:
            back, front = self.storm_span(s, t)
            cover = max(0.0, min(hi, front) - max(lo, back))
            total += s.rain * cover / (hi - lo)
        return total

    def outflow(self, k: int) -> float:
        if self.water[k] <= 0.0:
            return 0.0
        return FLOW * self.opening[k] / NOTCHES

    # --- the gates
    def press(self, port: int) -> None:
        if self.result is not None:
            return
        k, way = divmod(port, 2)
        if k >= len(self.gate):
            return
        self.gate[k] = max(0, min(NOTCHES, self.gate[k] + (1 if way == 0
                                                           else -1)))
        if not self.level.stiff:
            self.opening[k] = float(self.gate[k])

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self.t += dt
        level = self.level
        n = level.dams
        for k in range(n):
            if level.stiff and self.opening[k] != self.gate[k]:
                move = dt / level.stiff
                diff = self.gate[k] - self.opening[k]
                self.opening[k] += max(-move, min(move, diff))
        out = [self.outflow(k) for k in range(n)]
        for k in range(n):
            # What upstream let out a while ago arrives now.
            pipe = self.pipes[k]
            arriving = 0.0
            while pipe and pipe[0][0] <= self.t:
                arriving += pipe.popleft()[1]
            self.arriving[k] = arriving / dt if dt else 0.0
            inflow = (BASE if k == 0 else 0.0) + self.rain_on(k)
            self.water[k] += (inflow - out[k]) * dt + arriving
            self.water[k] = max(0.0, self.water[k])
            if k + 1 < n:
                self.pipes[k + 1].append((self.t + level.delay, out[k] * dt))
        self.town = out[-1]
        for k in range(n):
            if self.water[k] >= 100.0:
                self.result = (False, _('Dam %d overtopped') % (k + 1))
                return
            if self.water[k] < LOW:
                self.low_for[k] += dt
                if self.low_for[k] > LOW_GRACE:
                    self.result = (False, _('Reservoir %d ran too low')
                                   % (k + 1))
                    return
            else:
                self.low_for[k] = 0.0
        if self.town > level.flood:
            self.flood_for += dt
            if self.flood_for > FLOOD_GRACE:
                self.result = (False, _('The town flooded'))
                return
        else:
            self.flood_for = 0.0
        if self.t >= SECONDS:
            self.result = (True, _('Through every storm, the town dry'))

    def in_pipe(self, k: int) -> float:
        return sum(q for _t, q in self.pipes[k])


# --- the reference keeper -----------------------------------------------------

def _rain_ahead(run: Run, k: int, horizon: float) -> float:
    """Rain (in % of the reservoir) due on reservoir *k* over *horizon*."""
    total, t, dt = 0.0, 0.0, 0.5
    while t < horizon:
        total += run.rain_on(k, run.t + t) * dt
        t += dt
    return total


def autopilot(run: Run) -> List[int]:
    """Aim each reservoir at a level that leaves room for the rain still
    to come, and pick the notch that gets it there without flooding the
    town or overfilling the dam below."""
    if run.result is not None:
        return []
    level = run.level
    n = level.dams
    horizon = 30.0
    want_out = []
    for k in range(n):
        coming = _rain_ahead(run, k, horizon) + run.in_pipe(k)
        # Upstream water that will be released into this one, roughly.
        if k > 0:
            coming += sum(_rain_ahead(run, j, horizon) * 0.6
                          for j in range(k))
        target = max(22.0, min(65.0, 85.0 - coming))
        inflow = (BASE if k == 0 else run.arriving[k]) + run.rain_on(k)
        q = inflow + (run.water[k] - target) / 6.0
        if run.water[k] > 88.0:
            q = FLOW
        want_out.append(max(0.0, min(FLOW, q)))
    # The town takes no more than its river holds.
    want_out[-1] = min(want_out[-1], level.flood * 0.92)
    for k in range(n):
        notch = int(round(want_out[k] / FLOW * NOTCHES))
        if k == n - 1:
            while notch > 0 and FLOW * notch / NOTCHES > level.flood * 0.97:
                notch -= 1
        if run.water[k] < LOW + 6.0:
            notch = min(notch, 0 if run.water[k] < LOW + 3 else 1)
        if notch > run.gate[k]:
            return [2 * k]
        if notch < run.gate[k]:
            return [2 * k + 1]
    return []


def act(run: Run, port: int) -> None:
    run.press(port)


def play(valley: Valley, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(valley)
    while run.result is None:
        for port in pilot(run):
            act(run, port)
        run.step(dt)
    return run.result
