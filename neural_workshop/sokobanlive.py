# -*- coding: utf-8 -*-
"""Sokoban Live: push crates onto their pads while the guards walk.

A warehouse floor, crates, pads and a worker -- the old puzzle -- but
the clock runs. The worker steps one square at a time with a short
recovery between steps. Guards patrol straight aisles back and forth,
one square per beat; a guard who meets a crate or a wall turns round,
so the crates you push re-route the patrols. A guard who walks into
the worker, or the worker into a guard, ends the trial. From rung 13
shutters cut some aisles, open and shut on a cycle; nothing passes a
shut shutter, and a shutter never shuts on anything standing in it.

The ladder:

* rungs 1-3: one crate, then one slow guard;
* rungs 4-9: two crates, then a second guard;
* rungs 10-12: three crates;
* rungs 13-15: shutters;
* rungs 16-19: faster guards, four crates;
* from rung 20: three guards, quicker every rung.

A crate pushed into a corner it can never leave ends the trial too,
so the worker learns it at once rather than when the time runs out.
Pass: every pad covered in time.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import heapq
import random
from collections import deque
from typing import Dict, FrozenSet, List, NamedTuple, Optional, Tuple

from . import sokoban
from .i18n import _

UP, DOWN, LEFT, RIGHT = range(4)
PORTS = 4
STEP = 0.18           # the worker's recovery between steps, seconds
COUNTED = 'counted'


class Grade(NamedTuple):
    rung: int
    width: int
    height: int
    crates: int
    guards: int
    beat: float          # seconds per guard step
    shutters: int
    pulls: int
    floor: int


def grade(rung: int) -> Grade:
    rung = max(1, int(rung))
    if rung < 4:
        crates, guards, beat, size = 1, 0 if rung == 1 else 1, 0.75, (11, 8)
    elif rung < 10:
        crates, guards, beat, size = 2, 1 if rung < 7 else 2, 0.65, (12, 9)
    elif rung < 16:
        crates, guards, beat, size = 3, 2, 0.6, (13, 9)
    elif rung < 20:
        crates, guards, beat, size = 4, 2, 0.5, (14, 10)
    else:
        crates, guards, size = 4, 3, (14, 10)
        beat = max(0.32, 0.48 - 0.012 * (rung - 20))
    shutters = 0 if rung < 13 else 1 if rung < 16 else 2
    pulls = 20 + 18 * crates
    floor = 3 + 3 * crates
    return Grade(rung, size[0], size[1], crates, guards, beat, shutters,
                 pulls, floor)


class Patrol(NamedTuple):
    cells: Tuple[int, ...]   # a straight run of floor, end to end
    start: int               # index along it
    heading: int             # +1 or -1
    phase: float             # seconds before the first beat


class Shutter(NamedTuple):
    cell: int
    period: float
    open_share: float
    phase: float


class Floor(NamedTuple):
    level: Grade
    room: sokoban.Level
    patrols: List[Patrol]
    shutters: List[Shutter]
    seconds: float


def _runs(room: sokoban.Level) -> List[Tuple[int, ...]]:
    """Every maximal straight run of floor three squares or longer."""
    w, h = room.width, room.height
    floor = [i not in room.walls for i in range(w * h)]
    out = []
    for r in range(h):
        c = 0
        while c < w:
            if floor[r * w + c]:
                k = c
                while k < w and floor[r * w + k]:
                    k += 1
                if k - c >= 3:
                    out.append(tuple(r * w + j for j in range(c, k)))
                c = k
            else:
                c += 1
    for c in range(w):
        r = 0
        while r < h:
            if floor[r * w + c]:
                k = r
                while k < h and floor[k * w + c]:
                    k += 1
                if k - r >= 3:
                    out.append(tuple(j * w + c for j in range(r, k)))
                r = k
            else:
                r += 1
    return out


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Floor:
    """A warehouse the reference worker clears."""
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    best = None
    for _attempt in range(30):
        found = _build(level, draw)
        if found is None:
            continue
        best = best or found
        if play(found)[0]:
            return found
    return best or _build(grade(1), random.Random(seed))


def _build(level: Grade, draw: random.Random) -> Optional[Floor]:
    spec = sokoban.Grade('live', level.width, level.height, level.crates,
                         0.78, level.pulls, level.floor, 0.0, 0.0)
    try:
        room = sokoban._deal(spec, draw, 200)
    except ValueError:
        return None
    if room.boxes <= room.goals:
        return None
    w = room.width
    pr, pc = divmod(room.player, w)
    runs = [run for run in _runs(room)
            if min(abs(i // w - pr) + abs(i % w - pc) for i in run) >= 3]
    draw.shuffle(runs)
    patrols: List[Patrol] = []
    used = set()
    for run in sorted(runs, key=len, reverse=True):
        if len(patrols) == level.guards:
            break
        if used & set(run):
            continue
        start = draw.randrange(len(run))
        if run[start] in room.boxes:
            continue
        patrols.append(Patrol(run, start, draw.choice((1, -1)),
                              draw.uniform(0, level.beat)))
        used |= set(run)
    if len(patrols) < level.guards:
        return None
    shutters: List[Shutter] = []
    if level.shutters:
        floor = [i for i in range(w * room.height) if i not in room.walls
                 and i not in room.boxes and i not in room.goals
                 and i != room.player]
        # A shutter belongs in a doorway: floor with walls either side.
        doors = [i for i in floor
                 if ((i - 1 in room.walls and i + 1 in room.walls)
                     or (i - w in room.walls and i + w in room.walls))]
        draw.shuffle(doors)
        for i in doors[:level.shutters]:
            period = draw.uniform(3.5, 5.0)
            shutters.append(Shutter(i, period, draw.uniform(0.45, 0.6),
                                    draw.uniform(0, period)))
        if len(shutters) < level.shutters:
            return None
    pushes = room.minimum or room.bound
    seconds = min(30 + pushes * 3 + level.crates * 10,
                  45 + level.crates * 35)
    return Floor(level, room, patrols, shutters, round(seconds))


# --- the run -----------------------------------------------------------------

class Guard:
    def __init__(self, patrol: Patrol) -> None:
        self.cells = patrol.cells
        self.k = patrol.start
        self.heading = patrol.heading
        self.next_beat = patrol.phase

    @property
    def cell(self) -> int:
        return self.cells[self.k]

    def copy(self) -> 'Guard':
        twin = Guard.__new__(Guard)
        twin.cells, twin.k = self.cells, self.k
        twin.heading, twin.next_beat = self.heading, self.next_beat
        return twin

    def beat(self, blocked) -> None:
        for _turn in range(2):
            k = self.k + self.heading
            if 0 <= k < len(self.cells) and not blocked(self.cells[k]):
                self.k = k
                return
            self.heading = -self.heading


class Run:
    """One warehouse in motion."""

    def __init__(self, floor: Floor) -> None:
        self.floor = floor
        room = floor.room
        self.width = room.width
        self.t = 0.0
        self.player = room.player
        self.boxes = set(room.boxes)
        self.guards = [Guard(p) for p in floor.patrols]
        self.ready_at = 0.0
        self.queued: Optional[int] = None
        self.result: Optional[Tuple[bool, str]] = None
        self.facing = DOWN
        self.pushes = 0
        self.steps = 0
        self.alive = sokoban.live_cells(room.width, room.height, room.walls,
                                        room.goals)
        self.shut_now = set()
        self._update_shutters()

    def delta(self, d: int) -> int:
        return (-self.width, self.width, -1, 1)[d]

    def shutter_open(self, s: Shutter, t: float) -> bool:
        return ((t + s.phase) % s.period) < s.open_share * s.period

    def _update_shutters(self) -> None:
        occupied = self.boxes | {self.player} | {g.cell for g in self.guards}
        shut = set()
        for s in self.floor.shutters:
            if not self.shutter_open(s, self.t):
                if s.cell in self.shut_now or s.cell not in occupied:
                    shut.add(s.cell)
        self.shut_now = shut

    def solid(self, cell: int) -> bool:
        return cell in self.floor.room.walls or cell in self.shut_now

    def press(self, d: int) -> None:
        if self.result is None and 0 <= d < 4:
            self.queued = d

    def _move(self, d: int) -> None:
        self.facing = d
        step = self.delta(d)
        to = self.player + step
        if self.solid(to):
            return
        guards = {g.cell for g in self.guards}
        if to in self.boxes:
            beyond = to + step
            if (self.solid(beyond) or beyond in self.boxes
                    or beyond in guards):
                return
            self.boxes.discard(to)
            self.boxes.add(beyond)
            self.pushes += 1
        self.player = to
        self.steps += 1
        self.ready_at = self.t + STEP

    def step(self, dt: float) -> None:
        if self.result is not None:
            return
        self.t += dt
        self._update_shutters()
        if self.queued is not None and self.t >= self.ready_at:
            d, self.queued = self.queued, None
            self._move(d)
        beat = self.floor.level.beat
        for g in self.guards:
            if self.t >= g.next_beat:
                g.next_beat += beat
                g.beat(lambda c: self.solid(c) or c in self.boxes)
        room = self.floor.room
        if any(g.cell == self.player for g in self.guards):
            self.result = (False, _('A guard caught the worker'))
        elif self.boxes >= set(room.goals):
            self.result = (True, _('Every pad covered in %.0f s') % self.t)
        elif any(b not in self.alive for b in self.boxes):
            self.result = (False, _('A crate is stuck for good'))
        elif self.t >= self.floor.seconds:
            self.result = (False, _('Out of time'))


# --- the reference worker -------------------------------------------------------

def _walk(width: int, solid, start: int, goal: int) -> Optional[List[int]]:
    if start == goal:
        return []
    prev = {start: None}
    queue = deque([start])
    while queue:
        at = queue.popleft()
        for d, step in enumerate((-width, width, -1, 1)):
            to = at + step
            if to in prev or solid(to):
                continue
            prev[to] = (at, d)
            if to == goal:
                out = []
                while prev[to] is not None:
                    to, d2 = prev[to]
                    out.append(d2)
                return out[::-1]
            queue.append(to)
    return None


def solve(room: sokoban.Level, boxes: FrozenSet[int], player: int,
          budget: int = 60000) -> Optional[List[int]]:
    """Directions that cover every pad, ignoring guards and shutters.

    Greedy best-first over pushes, scored by each crate's push distance
    to the nearest pad: not the fewest pushes, but quick and sure on
    rooms this open."""
    w = room.width
    walls = room.walls
    alive = sokoban.live_cells(w, room.height, walls, room.goals)
    goals = room.goals
    dist: Dict[int, int] = {}
    queue = deque()
    for g in goals:
        dist[g] = 0
        queue.append(g)
    while queue:   # pull distances: a crate at c reaches a pad in dist[c]
        at = queue.popleft()
        for step in (-w, w, -1, 1):
            to, back = at + step, at + 2 * step
            if to in walls or back in walls or to in dist:
                continue
            dist[to] = dist[at] + 1
            queue.append(to)

    def score(bx: FrozenSet[int]) -> int:
        return sum(dist.get(b, 99) for b in bx)

    def region(bx, at):
        seen = {at}
        queue = deque([at])
        while queue:
            c = queue.popleft()
            for step in (-w, w, -1, 1):
                n = c + step
                if n not in seen and n not in walls and n not in bx:
                    seen.add(n)
                    queue.append(n)
        return seen

    start = (frozenset(boxes), player)
    reach = region(start[0], player)
    key0 = (start[0], min(reach))
    parent = {key0: None}
    heap = [(score(start[0]), 0, start[0], player, key0)]
    count = 0
    while heap:
        _s, _n, bx, at, key = heapq.heappop(heap)
        if bx >= goals:
            break
        count += 1
        if count > budget:
            return None
        reach = region(bx, at)
        for b in bx:
            for d, step in enumerate((-w, w, -1, 1)):
                behind, ahead = b - step, b + step
                if (behind not in reach or ahead in walls or ahead in bx
                        or ahead not in alive):
                    continue
                moved = (bx - {b}) | {ahead}
                nreach_key = (moved, min(region(moved, b)))
                if nreach_key in parent:
                    continue
                parent[nreach_key] = (key, bx, at, behind, d, b)
                _n += 1
                heapq.heappush(heap, (score(moved), count * 10 + d, moved, b,
                                      nreach_key))
    else:
        return None
    # Rebuild: walk to each push's standing square, then push.
    pushes = []
    while parent[key] is not None:
        key, bx_before, _at, behind, d, _b = parent[key]
        pushes.append((bx_before, behind, d))
    pushes.reverse()
    out: List[int] = []
    at = player
    for bx_before, behind, d in pushes:
        walk = _walk(w, lambda c: c in walls or c in bx_before, at, behind)
        if walk is None:
            return None
        out += walk + [d]
        at = behind + (-w, w, -1, 1)[d]
    return out


class Pilot:
    """Follows a plan; waits or sidesteps when a guard would meet it."""

    def __init__(self) -> None:
        self.plan: List[int] = []
        self.expect = None
        self.since = 0.0
        self.draw = random.Random(7)

    def __call__(self, run: Run) -> List[int]:
        if run.result is not None or run.t < run.ready_at \
                or run.queued is not None:
            return []
        state = (frozenset(run.boxes), run.player)
        if state != self.expect or not self.plan:
            plan = solve(run.floor.room, state[0], state[1])
            self.plan = plan or []
        if not self.plan:
            return []
        d = self.plan[0]
        timeline = self._timeline(run, self.plan[:6])
        if timeline is not None and self._safe(run, timeline, 1.2):
            if run.solid(run.player + run.delta(d)) or self._shut_soon(
                    run, timeline):
                return []
            self.plan = self.plan[1:]
            self.expect = (timeline[0][1], timeline[0][0])
            self.since = run.t
            return [d]
        patient = run.t - self.since < 2.0
        # Unsafe: wait, if staying put is safe; else step aside.
        if patient and self._safe(run, [(run.player, run.boxes, 0.0)], 0.9):
            self.expect = state
            return []
        ways = list(range(4))
        self.draw.shuffle(ways)
        for d2 in ways:
            to = run.player + run.delta(d2)
            if run.solid(to) or to in run.boxes or any(
                    g.cell == to for g in run.guards):
                continue
            if self._safe(run, [(to, run.boxes, 0.0)], 0.9):
                self.plan = []
                self.expect = None
                self.since = run.t
                return [d2]
        return []

    def _timeline(self, run: Run, moves: List[int]):
        """[(player, boxes, arrival time)] following *moves*."""
        at, bx = run.player, set(run.boxes)
        out = [(at, frozenset(bx), -1.0)]
        t = 0.0
        for d in moves:
            step = run.delta(d)
            to = at + step
            if to in run.floor.room.walls:
                return None
            if to in bx:
                bx = (bx - {to}) | {to + step}
            at = to
            out.append((at, frozenset(bx), t))
            t += STEP + 1 / 30.0
        return out[1:] if len(out) > 1 else out

    def _safe(self, run: Run, timeline, horizon: float) -> bool:
        guards = [g.copy() for g in run.guards]
        beat = run.floor.level.beat
        events = []
        for g in guards:
            t = g.next_beat - run.t
            while t <= horizon:
                events.append((t, id(g), g))
                t += beat
        events.sort(key=lambda e: e[0])

        def where(t):
            spot = timeline[0]
            for item in timeline:
                if item[2] <= t:
                    spot = item
            return spot

        first = timeline[0]
        if any(g.cell == first[0] for g in guards):
            return False
        for t, _i, g in events:
            at, bx, _a = where(t)
            g.beat(lambda c: c in run.floor.room.walls or c in bx
                   or c in run.shut_now)
            if any(h.cell == at for h in guards):
                return False
            # Also the moment before the worker moves on.
            before = where(t - 0.08)[0]
            if g.cell == before:
                return False
        return True

    def _shut_soon(self, run: Run, timeline) -> bool:
        """Whether a shutter the next step stands in shuts on it, or a
        shutter would block the push."""
        at = timeline[0][0]
        for s in run.floor.shutters:
            if s.cell == at or s.cell in timeline[0][1]:
                if not run.shutter_open(s, run.t + 0.05):
                    return True
        return False


def autopilot_for() -> Pilot:
    return Pilot()


def apply(run: Run, port: int) -> None:
    run.press(port)


def play(floor: Floor, pilot=None, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    pilot = pilot or Pilot()
    run = Run(floor)
    while run.result is None:
        for port in pilot(run):
            apply(run, port)
        run.step(dt)
    return run.result
