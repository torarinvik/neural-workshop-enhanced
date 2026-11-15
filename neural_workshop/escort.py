# -*- coding: utf-8 -*-
"""Escort: walkers cross a temple; the levers are yours.

Each walker follows a fixed path from the west gate to the east gate
and never stops of its own accord. On its path are three kinds of
device:

* a **door** holds the walker while shut and lets it on when open;
* a **bridge** spans a pit -- a walker who steps onto a pit whose
  bridge is not fully out falls;
* a **flame jet** burns on a cycle of its own that no lever touches.
  Every jet stands just past a door, so the door is how a walker is
  timed through it.

Levers flip devices: a door opens or shuts, a bridge slides out or in
(that takes a moment, and a moving bridge carries no one). The ladder:

* rungs 1-3: one walker, doors and bridges, a lever for each;
* rungs 4-9: flame jets, then more of everything;
* rungs 10-12: coupled levers -- some levers work two devices at once,
  so opening one door may pull in a bridge somewhere else;
* rungs 13-15: two walkers;
* rungs 16-19: walkers change pace without warning;
* from rung 20: three walkers, faster.

A trial passes when every walker reaches the east gate. Clocked: the
walkers walk and the jets burn.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from .i18n import _

COLS, ROWS = 26, 15
DOOR, BRIDGE, JET = 'door', 'bridge', 'jet'
MOST_LEVERS = 6
PORTS = MOST_LEVERS
SLIDE = 0.7          # seconds for a bridge to slide fully out or in
SWING = 0.35         # seconds for a door to open or shut
WARN = 0.7           # seconds a jet hisses before it fires
REACH = 0.42         # how near a device's centre counts as on it


class Grade(NamedTuple):
    rung: int
    walkers: int
    devices: int         # per walker, doors and bridges and jets
    jets: int            # per walker
    levers: int
    coupled: bool
    speed: float         # cells a second
    wobble: bool         # pace changes without warning


def grade(rung: int) -> Grade:
    rung = max(1, int(rung))
    walkers = 1 if rung < 13 else 2 if rung < 20 else 3
    if rung < 4:
        devices, jets = 2 + (rung > 1), 0
    elif rung < 7:
        devices, jets = 3 + (rung > 5), 1
    elif rung < 10:
        devices, jets = 5, 2
    elif rung < 13:
        devices, jets = 6, 2
    elif rung < 20:
        devices, jets = 4, 1 + (rung >= 16)
    else:
        devices, jets = 4, 2
    total = walkers * (devices - jets)
    coupled = rung >= 10
    levers = min(MOST_LEVERS, total if not coupled
                 else max(2, (total * 2 + 2) // 3))
    levers = min(levers, total)
    speed = 1.5 + 0.03 * min(rung, 12) + 0.04 * max(0, rung - 20)
    return Grade(rung, walkers, devices, jets, levers, coupled,
                 round(speed, 3), rung >= 16)


class Device(NamedTuple):
    kind: str
    walker: int
    at: int                  # index along the walker's path
    lever: Optional[int]     # None for a jet
    period: float = 0.0      # jets only
    duty: float = 0.0
    phase: float = 0.0


class Temple(NamedTuple):
    level: Grade
    paths: List[List[Tuple[int, int]]]
    devices: List[Device]
    levers: List[List[int]]          # device indices each lever flips
    start: List[bool]                # per device: open / out at the start
    delays: List[float]              # each walker's start, seconds
    paces: List[List[Tuple[float, float]]]   # (time, factor) changes
    seconds: float


def _path(draw: random.Random, low: int, high: int
          ) -> List[Tuple[int, int]]:
    """A meander from the west wall to the east, inside rows low..high."""
    mid = (low + high) // 2
    r = max(low, min(high, mid + draw.randint(-2, 2)))
    path = [(0, r)]
    seen = {(0, r)}
    c = 0
    run = 0
    while c < COLS - 1:
        moves = [(1, 0)] * 2
        if run < 4:
            moves += [(0, 1), (0, -1)]
        draw.shuffle(moves)
        for dc, dr in moves:
            nc, nr = c + dc, path[-1][1] + dr
            if not low <= nr <= high or (nc, nr) in seen:
                continue
            if dr and c in (0, COLS - 2):
                continue
            # Never touch the path two steps back sideways: keep it a line.
            if dr and any((nc + k, nr) in seen for k in (-1, 1)):
                continue
            break
        else:
            dc, dr, nc, nr = 1, 0, c + 1, path[-1][1]
        run = run + 1 if dr else 0
        c = nc
        path.append((nc, nr))
        seen.add((nc, nr))
    return path


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Temple:
    """A temple the reference escort brings every walker through."""
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(60):
        temple = _build(level, draw)
        if temple is None:
            continue
        best = best or temple
        if play(temple)[0] and not play(temple, lambda run: [])[0]:
            return temple
    return best or _build(level, random.Random(seed + 1))


def _build(level: Grade, draw: random.Random) -> Optional[Temple]:
    band = (ROWS - 1) / level.walkers
    paths, devices = [], []
    for w in range(level.walkers):
        low = int(round(w * band)) + (1 if w else 0)
        high = int(round((w + 1) * band)) - (1 if w < level.walkers - 1
                                             else 0)
        path = _path(draw, low, high)
        paths.append(path)
        # Pick device spots spaced along the path, jets two past a door.
        spots = list(range(3, len(path) - 3))
        kinds = ([JET] * level.jets
                 + [BRIDGE] * ((level.devices - 2 * level.jets) // 2 + 1)
                 + [DOOR] * level.devices)
        kinds = kinds[:level.devices + level.jets]
        plan = [JET] * level.jets
        rest = level.devices - 2 * level.jets
        plan += draw.sample([DOOR, BRIDGE] * rest, max(0, rest))
        draw.shuffle(plan)
        cursor = 3
        span = (len(path) - 6) / max(1, len(plan))
        for k, kind in enumerate(plan):
            at = int(3 + span * k + draw.uniform(0, max(0.0, span - 4)))
            at = max(at, cursor)
            if kind == JET:
                if at + 2 >= len(path) - 2:
                    return None
                devices.append(Device(DOOR, w, at, None))
                period = draw.uniform(2.6, 3.8)
                devices.append(Device(JET, w, at + 2, None, period,
                                      draw.uniform(0.35, 0.5),
                                      draw.uniform(0, period)))
                cursor = at + 5
            else:
                if at >= len(path) - 2:
                    return None
                devices.append(Device(kind, w, at, None))
                cursor = at + 4
        del spots, kinds
    work = [i for i, d in enumerate(devices) if d.kind != JET]
    draw.shuffle(work)
    levers: List[List[int]] = [[] for _l in range(level.levers)]
    for k, i in enumerate(work):
        levers[k % level.levers].append(i)
    if any(len(group) > 2 for group in levers):
        return None
    for lever, group in enumerate(levers):
        for i in group:
            devices[i] = devices[i]._replace(lever=lever)
    order = list(range(level.levers))
    draw.shuffle(order)
    renumber = {old: new for new, old in enumerate(order)}
    levers = [levers[old] for old in order]
    devices = [d._replace(lever=renumber[d.lever]) if d.lever is not None
               else d for d in devices]
    start = [draw.random() < 0.5 for _d in devices]
    for i, d in enumerate(devices):
        if d.kind == DOOR:
            start[i] = False if d.lever is not None and draw.random() < 0.7 \
                else start[i]
    delays = [w * draw.uniform(1.5, 3.5) for w in range(level.walkers)]
    paces = []
    for w in range(level.walkers):
        changes = []
        if level.wobble:
            t = draw.uniform(3, 7)
            while t < 120:
                changes.append((t, draw.choice((0.65, 0.8, 1.25, 1.45))))
                t += draw.uniform(3, 7)
        paces.append(changes)
    longest = max(len(p) for p in paths)
    seconds = longest / level.speed * 2.4 + max(delays) + 12
    return Temple(level, paths, devices, levers, start, delays, paces,
                  round(seconds, 1))


# --- the run ---------------------------------------------------------------------

WALKING, WAITING, SAFE, FELL, BURNED, ARRIVED = (
    'walking', 'waiting', 'queued', 'fell', 'burned', 'arrived')


class Run:
    """One temple in motion."""

    def __init__(self, temple: Temple) -> None:
        self.temple = temple
        self.t = 0.0
        self.target = list(temple.start)      # door open / bridge out
        self.progress = [1.0 if s else 0.0 for s in temple.start]
        self.pos = [0.0] * len(temple.paths)
        self.state = [SAFE] * len(temple.paths)
        self.pace = [1.0] * len(temple.paths)
        self.next_pace = [0] * len(temple.paths)
        self.result: Optional[Tuple[bool, str]] = None
        self.pulled = [0.0] * len(temple.levers)
        self.by_walker: List[List[int]] = [[] for _p in temple.paths]
        for i, d in enumerate(temple.devices):
            self.by_walker[d.walker].append(i)

    # The agent's one action.
    def pull(self, lever: int) -> None:
        if not 0 <= lever < len(self.temple.levers) or self.result:
            return
        self.pulled[lever] = self.t
        for i in self.temple.levers[lever]:
            self.target[i] = not self.target[i]

    def jet_on(self, i: int, t: Optional[float] = None) -> bool:
        d = self.temple.devices[i]
        t = self.t if t is None else t
        return ((t + d.phase) % d.period) < d.duty * d.period

    def jet_next(self, i: int) -> Tuple[float, float]:
        """Seconds until the jet next fires, and until it next goes out."""
        d = self.temple.devices[i]
        into = (self.t + d.phase) % d.period
        on = d.duty * d.period
        if into < on:
            return 0.0, on - into
        return d.period - into, d.period - into + on

    def speed(self, w: int) -> float:
        return self.temple.level.speed * self.pace[w]

    def is_open(self, i: int) -> bool:
        return self.progress[i] >= 0.999

    def step(self, dt: float) -> None:
        if self.result is not None:
            return
        temple = self.temple
        self.t += dt
        for i, d in enumerate(temple.devices):
            if d.kind == JET:
                continue
            rate = dt / (SWING if d.kind == DOOR else SLIDE)
            goal = 1.0 if self.target[i] else 0.0
            if self.progress[i] < goal:
                self.progress[i] = min(goal, self.progress[i] + rate)
            elif self.progress[i] > goal:
                self.progress[i] = max(goal, self.progress[i] - rate)
        for w, path in enumerate(temple.paths):
            changes = temple.paces[w]
            while (self.next_pace[w] < len(changes)
                   and changes[self.next_pace[w]][0] <= self.t):
                self.pace[w] = changes[self.next_pace[w]][1]
                self.next_pace[w] += 1
            if self.state[w] in (FELL, BURNED, ARRIVED):
                continue
            if self.t < temple.delays[w]:
                continue
            goal = self.pos[w] + self.speed(w) * dt
            self.state[w] = WALKING
            for i in self.by_walker[w]:
                d = temple.devices[i]
                stop = d.at - 0.5
                if (d.kind == DOOR and not self.is_open(i)
                        and self.pos[w] <= stop + 1e-9 < goal + 1e-9):
                    goal = min(goal, stop)
                    self.state[w] = WAITING
            self.pos[w] = goal
            for i in self.by_walker[w]:
                d = temple.devices[i]
                if abs(goal - d.at) > REACH:
                    continue
                if d.kind == BRIDGE and not self.is_open(i):
                    self.state[w] = FELL
                elif d.kind == JET and self.jet_on(i):
                    self.state[w] = BURNED
            if goal >= len(path) - 1:
                self.pos[w] = float(len(path) - 1)
                self.state[w] = ARRIVED
        if any(s == FELL for s in self.state):
            self.result = (False, _('A walker fell into a pit'))
        elif any(s == BURNED for s in self.state):
            self.result = (False, _('A walker walked into the flames'))
        elif all(s == ARRIVED for s in self.state):
            self.result = (True, _('Everyone crossed in %.0f s') % self.t)
        elif self.t >= temple.seconds:
            self.result = (False, _('Out of time'))

    def where(self, w: int) -> Tuple[float, float]:
        """The walker's grid position, between path cells."""
        path = self.temple.paths[w]
        p = max(0.0, min(len(path) - 1.0, self.pos[w]))
        k = min(int(p), len(path) - 2)
        f = p - k
        (c0, r0), (c1, r1) = path[k], path[k + 1]
        return c0 + (c1 - c0) * f, r0 + (r1 - r0) * f


# --- the reference escort ------------------------------------------------------

def _jet_after(run: Run, door: int) -> Optional[int]:
    d = run.temple.devices[door]
    for i in run.by_walker[d.walker]:
        e = run.temple.devices[i]
        if e.kind == JET and e.at == d.at + 2:
            return i
    return None


def _clear(run: Run, jet: int, enter: float, leave: float) -> bool:
    """Whether the jet stays out from *enter* to *leave* seconds ahead."""
    t = enter
    while t <= leave:
        if run.jet_on(jet, run.t + t):
            return False
        t += 0.05
    return not run.jet_on(jet, run.t + leave)


def wants(run: Run) -> Dict[int, Tuple[bool, float]]:
    """For each device that matters now: the state wanted, and how much."""
    temple = run.temple
    out: Dict[int, Tuple[bool, float]] = {}
    margin = 0.35
    for w in range(len(temple.paths)):
        if run.state[w] in (FELL, BURNED, ARRIVED):
            continue
        p = run.pos[w]
        v = max(0.3, run.speed(w))
        late = max(0.0, temple.delays[w] - run.t)
        for i in run.by_walker[w]:
            d = temple.devices[i]
            ahead = d.at - p
            if ahead < -REACH - 0.05:
                continue
            reach = late + max(0.0, ahead - REACH) / v
            if d.kind == BRIDGE:
                if ahead <= REACH + 0.05:
                    out[i] = (True, 1000.0)
                elif reach < SLIDE * 1.6 + 0.6:
                    out[i] = (True, 200.0 / (1 + reach))
                elif reach < 6:
                    out[i] = (True, 5.0 / (1 + reach))
            elif d.kind == DOOR:
                if ahead < -0.5 + 1e-6:
                    continue
                jet = _jet_after(run, i)
                if jet is None:
                    if reach < 6:
                        out[i] = (True, 4.0 / (1 + reach))
                    continue
                # When the walker would meet the jet if the door were
                # open (opened now, for one held at it).
                held = ahead <= 0.5 + 0.02
                if held:
                    enter = late + SWING * (1 - run.progress[i]) + \
                        (2.5 - REACH) / v
                else:
                    enter = late + (ahead + 2 - REACH) / v
                leave = enter + 2 * REACH / v
                if temple.level.wobble:
                    # A pace change mid-crossing is a risk taken.
                    enter, leave = enter - 0.15, leave + 0.25
                ok = _clear(run, jet, max(0.0, enter - margin),
                            leave + margin)
                if held:
                    out[i] = (ok, 60.0 if ok else 300.0)
                elif not ok and (ahead - 0.5) / v < SWING * 1.4 + 0.35:
                    out[i] = (False, 300.0)
                elif not ok:
                    out[i] = (False, 3.0)
                elif reach < 4:
                    out[i] = (True, 2.0)
    return out


def autopilot(run: Run) -> List[int]:
    """Pull the one lever that most moves the temple toward what the
    walkers need, unless it would break something more urgent."""
    if run.result is not None:
        return []
    need = wants(run)
    best, best_score = None, 0.5
    for lever, group in enumerate(run.temple.levers):
        if run.t - run.pulled[lever] < 0.25:
            continue
        score = 0.0
        for i in group:
            if i not in need:
                continue
            state, weight = need[i]
            now = run.target[i]
            score += weight if (not now) == state else -weight
        if score > best_score:
            best, best_score = lever, score
    return [] if best is None else [best]


def apply(run: Run, port: int) -> None:
    run.pull(port)


def play(temple: Temple, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(temple)
    while run.result is None:
        for port in pilot(run):
            apply(run, port)
        run.step(dt)
    return run.result
