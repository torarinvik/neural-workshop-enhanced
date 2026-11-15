# -*- coding: utf-8 -*-
"""Firebreak: a forest fire is coming; cut breaks and save the town.

The land is a grid of forest, grass, water, rock and the town. Fire
spreads from cell to burning cell -- quickly through grass, slower
through forest, faster still with the wind behind it -- and every
burning cell burns out to ash. A firebreak is a cell cleared to bare
earth, which nothing can burn across. The crew digs one break at a
time, at the cursor, and the shovels are limited.

The ladder:

* rungs 1-3: one fire, a steady breeze, the town far off;
* rungs 4-6: faster fire, fewer shovels, the town nearer;
* rungs 7-9: two fires;
* rungs 10-12: the wind swings round mid-round;
* rungs 13-15: embers jump the fire two or three cells downwind;
* rungs 16-19: no wind arrow -- only the smoke shows which way it
  blows;
* from rung 20: faster fire, slower digging, fewer shovels every rung.

A trial passes when the fire is out and no part of the town has
burned. Clocked: the fire burns.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import heapq
import math
import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from .i18n import _

COLS, ROWS = 30, 19
FOREST, GRASS, WATER, ROCK, TOWN, BREAK = range(6)
FLAMMABLE = (FOREST, GRASS, TOWN)
#: Seconds a cell burns, by terrain.
BURN = {FOREST: 9.0, GRASS: 4.0, TOWN: 7.0}
#: Seconds for fire to cross a cell, by terrain, before wind.
CROSS = {FOREST: 1.9, GRASS: 0.9, TOWN: 2.4}
UNBURNT, BURNING, ASH = range(3)
SECONDS = 120.0

UP, DOWN, LEFT, RIGHT, DIG = range(5)
JUMP = 5            # ports 5-8 move the cursor four cells
PORTS = 9
STEPS = ((0, 1), (0, -1), (-1, 0), (1, 0))


class Grade(NamedTuple):
    rung: int
    fires: int
    pace: float          # multiplies spread speed
    wind: float          # strength, 0 to about 1.2
    shift: bool
    embers: float        # chance a burning cell throws one
    hidden_wind: bool
    dig: float           # seconds between breaks
    spare: int           # shovels beyond what ringing the town takes
    distance: int        # least cells from a fire to the town


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        fires=1 if r < 7 else 2,
        pace=0.8 if r < 4 else (1.0 if r < 20 else min(1.5, 1.05 + 0.05 * top)),
        wind=0.6 if r < 4 else 0.9,
        shift=r >= 10,
        embers=0.0 if r < 13 else (0.15 if r < 20 else 0.22),
        hidden_wind=r >= 16,
        dig=(0.35 if r < 4 else 0.5 if r < 13 else 0.28 if r < 20
             else min(0.5, 0.3 + 0.02 * top)),
        spare=(14 if r < 4 else 8 if r < 13 else 30 if r < 20 else
               max(18, 28 - top)),
        distance=(18 if r < 4 else 14 if r < 13 else 19))


class Land(NamedTuple):
    rung: int
    level: Grade
    terrain: Tuple[int, ...]
    #: A fixed 0.75-1.35 multiplier per cell, so fronts are ragged.
    rough: Tuple[float, ...]
    #: A fixed draw per cell deciding whether it throws an ember.
    ember_draw: Tuple[float, ...]
    fires: Tuple[int, ...]
    #: (time, angle in degrees) the wind blows towards, from time on.
    winds: Tuple[Tuple[float, float], ...]
    town: Tuple[int, ...]
    shovels: int


def cell(c: int, r: int) -> int:
    return r * COLS + c


def colrow(i: int) -> Tuple[int, int]:
    return i % COLS, i // COLS


def _smooth(values: List[float], times: int) -> List[float]:
    for _k in range(times):
        out = []
        for i in range(COLS * ROWS):
            c, r = colrow(i)
            total, n = 0.0, 0
            for dc in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    cc, rr = c + dc, r + dr
                    if 0 <= cc < COLS and 0 <= rr < ROWS:
                        total += values[cell(cc, rr)]
                        n += 1
            out.append(total / n)
        values = out
    return values


def ring(town: Sequence[int], distance: int) -> List[int]:
    """Cells exactly *distance* (in king moves) from the town's box."""
    cs = [colrow(i) for i in town]
    c0, c1 = min(c for c, _r in cs), max(c for c, _r in cs)
    r0, r1 = min(r for _c, r in cs), max(r for _c, r in cs)
    out = []
    for r in range(r0 - distance, r1 + distance + 1):
        for c in range(c0 - distance, c1 + distance + 1):
            if not (0 <= c < COLS and 0 <= r < ROWS):
                continue
            if max(c0 - c, c - c1, r0 - r, r - r1) == distance:
                out.append(cell(c, r))
    return out


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Land:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    for _attempt in range(40):
        height = _smooth([draw.random() for _i in range(COLS * ROWS)], 3)
        damp = _smooth([draw.random() for _i in range(COLS * ROWS)], 2)
        lo, hi = min(height), max(height)
        terrain = []
        for i in range(COLS * ROWS):
            h = (height[i] - lo) / (hi - lo)
            if h < 0.13:
                terrain.append(WATER)
            elif h > 0.93:
                terrain.append(ROCK)
            elif damp[i] > 0.52:
                terrain.append(GRASS)
            else:
                terrain.append(FOREST)
        # The town: a 3 by 2 block of houses, on one side.
        side = draw.randrange(2)
        tc = draw.randrange(3, 7) if side == 0 else draw.randrange(COLS - 9,
                                                                   COLS - 5)
        tr = draw.randrange(4, ROWS - 6)
        town = [cell(tc + dc, tr + dr) for dc in range(3) for dr in range(2)]
        for i in town:
            terrain[i] = TOWN
        for i in ring(town, 1):
            if terrain[i] in (WATER, ROCK):
                terrain[i] = GRASS
        # Fires: far enough away, on something that burns.
        fires = []
        for _k in range(level.fires):
            for _try in range(200):
                c = draw.randrange(1, COLS - 1)
                r = draw.randrange(1, ROWS - 1)
                i = cell(c, r)
                far = min(max(abs(c - colrow(t)[0]), abs(r - colrow(t)[1]))
                          for t in town)
                if terrain[i] in (FOREST, GRASS) and far >= level.distance \
                        and all(abs(c - colrow(f)[0]) + abs(r - colrow(f)[1])
                                > 5 for f in fires):
                    fires.append(i)
                    break
        if len(fires) < level.fires:
            continue
        # Wind: blowing roughly from the fire towards the town.
        fc, fr = colrow(fires[0])
        towards = math.degrees(math.atan2(tr - fr, tc - fc))
        winds = [(0.0, towards + draw.uniform(-35, 35))]
        if level.shift:
            when = draw.uniform(18, 30)
            winds.append((when, winds[0][1] + draw.choice((-1, 1))
                          * draw.uniform(60, 110)))
        rough = tuple(draw.uniform(0.75, 1.35) for _i in range(COLS * ROWS))
        ember_draw = tuple(draw.random() for _i in range(COLS * ROWS))
        land = Land(level.rung, level, tuple(terrain), rough, ember_draw,
                    tuple(fires), tuple(winds), tuple(town), 0)
        # Can fire reach the town at all? If not, deal again.
        if _reaches_town(land):
            break
    walls = [i for i in ring(town, 2) if terrain[i] in (FOREST, GRASS)]
    return land._replace(shovels=len(walls) + level.spare)


def _reaches_town(land: Land) -> bool:
    seen = set(land.fires)
    stack = list(land.fires)
    town = set(land.town)
    while stack:
        i = stack.pop()
        if i in town:
            return True
        c, r = colrow(i)
        for dc, dr in STEPS:
            cc, rr = c + dc, r + dr
            if 0 <= cc < COLS and 0 <= rr < ROWS:
                j = cell(cc, rr)
                if j not in seen and land.terrain[j] in FLAMMABLE:
                    seen.add(j)
                    stack.append(j)
    return False


NEIGHBOURS = tuple((dc, dr, math.hypot(dc, dr))
                   for dc in (-1, 0, 1) for dr in (-1, 0, 1)
                   if dc or dr)


class Blaze:
    """The land as it burns."""

    def __init__(self, land: Land) -> None:
        self.land = land
        self.t = 0.0
        self.terrain = list(land.terrain)
        self.state = [UNBURNT] * (COLS * ROWS)
        self.lit_at = [0.0] * (COLS * ROWS)
        self.thrown = [False] * (COLS * ROWS)
        self.cursor = (COLS // 2, ROWS // 2)
        self.shovels = land.shovels
        self.ready_at = 0.0
        self.result: Optional[Tuple[bool, str]] = None
        for f in land.fires:
            self._light(f)

    # --- the wind ----------------------------------------------------------

    def wind_angle(self, t: Optional[float] = None) -> float:
        t = self.t if t is None else t
        angle = self.land.winds[0][1]
        for when, a in self.land.winds:
            if t >= when:
                angle = a
        return angle

    def wind(self) -> Tuple[float, float]:
        a = math.radians(self.wind_angle())
        w = self.land.level.wind
        return math.cos(a) * w, math.sin(a) * w

    def cross_time(self, src: int, dst: int, length: float) -> float:
        """Seconds for fire to cross from *src* into *dst*."""
        sc, sr = colrow(src)
        dc, dr = colrow(dst)
        wx, wy = self.wind()
        along = ((dc - sc) * wx + (dr - sr) * wy) / length
        speed = math.exp(0.75 * along) * self.land.level.pace
        return CROSS[self.terrain[dst]] * length * self.land.rough[dst] / speed

    # --- the crew ------------------------------------------------------------

    def move(self, dc: int, dr: int) -> None:
        c, r = self.cursor
        self.cursor = (max(0, min(COLS - 1, c + dc)),
                       max(0, min(ROWS - 1, r + dr)))

    def put(self, c: int, r: int) -> None:
        self.cursor = (max(0, min(COLS - 1, c)), max(0, min(ROWS - 1, r)))

    def can_dig(self) -> bool:
        i = cell(*self.cursor)
        return (self.result is None and self.shovels > 0 and
                self.t >= self.ready_at and
                self.terrain[i] in (FOREST, GRASS) and
                self.state[i] == UNBURNT)

    def dig(self) -> bool:
        if not self.can_dig():
            return False
        i = cell(*self.cursor)
        self.terrain[i] = BREAK
        self.shovels -= 1
        self.ready_at = self.t + self.land.level.dig
        return True

    # --- the fire ------------------------------------------------------------

    def _light(self, i: int) -> None:
        self.state[i] = BURNING
        self.lit_at[i] = self.t

    def step(self, dt: float) -> None:
        if self.result is not None:
            return
        self.t += dt
        terrain, state, lit = self.terrain, self.state, self.lit_at
        burning = [i for i, s in enumerate(state) if s == BURNING]
        catch = []
        for i in burning:
            age = self.t - lit[i]
            if age >= BURN[terrain[i]]:
                state[i] = ASH
                continue
            c, r = colrow(i)
            for dc, dr, length in NEIGHBOURS:
                cc, rr = c + dc, r + dr
                if not (0 <= cc < COLS and 0 <= rr < ROWS):
                    continue
                j = cell(cc, rr)
                if state[j] != UNBURNT or terrain[j] not in FLAMMABLE:
                    continue
                if age >= self.cross_time(i, j, length):
                    catch.append(j)
            level = self.land.level
            if level.embers and not self.thrown[i] and \
                    age >= BURN[terrain[i]] * 0.4:
                self.thrown[i] = True
                if self.land.ember_draw[i] < level.embers:
                    wx, wy = self.wind()
                    n = math.hypot(wx, wy) or 1.0
                    reach = 2
                    cc = int(round(c + wx / n * reach))
                    rr = int(round(r + wy / n * reach))
                    if 0 <= cc < COLS and 0 <= rr < ROWS:
                        j = cell(cc, rr)
                        if state[j] == UNBURNT and terrain[j] in FLAMMABLE:
                            catch.append(j)
        for j in catch:
            if state[j] == UNBURNT:
                self._light(j)
        if any(state[t] != UNBURNT for t in self.land.town):
            self.result = (False, _('The fire reached the town'))
            return
        if not any(s == BURNING for s in state):
            self.result = (True, _('Town saved; %d cells burned')
                           % self.burned())
        elif self.t >= SECONDS:
            self.result = (False, _('Still burning when time ran out'))

    def burned(self) -> int:
        return sum(1 for s in self.state if s != UNBURNT)

    def arrival(self) -> Dict[int, float]:
        """When fire would reach each cell from now if left alone, with
        the wind as it blows now: a shortest-path sweep."""
        best: Dict[int, float] = {}
        heap = []
        for i, s in enumerate(self.state):
            if s == BURNING:
                best[i] = self.lit_at[i] - self.t
                heapq.heappush(heap, (best[i], i))
        while heap:
            t, i = heapq.heappop(heap)
            if t > best.get(i, 1e9):
                continue
            c, r = colrow(i)
            for dc, dr, length in NEIGHBOURS:
                cc, rr = c + dc, r + dr
                if not (0 <= cc < COLS and 0 <= rr < ROWS):
                    continue
                j = cell(cc, rr)
                if self.state[j] != UNBURNT or \
                        self.terrain[j] not in FLAMMABLE:
                    continue
                nt = t + self.cross_time(i, j, length)
                if nt < best.get(j, 1e9):
                    best[j] = nt
                    heapq.heappush(heap, (nt, j))
        return best


# --- a reference crew ------------------------------------------------------

def autopilot(blaze: Blaze) -> List[int]:
    """Ports a sensible crew sends now: ring the town two cells out,
    soonest-threatened cell first. Where embers fly, ring it three
    cells out first and then back that ring with the inner one."""
    if blaze.t < blaze.ready_at or blaze.shovels <= 0:
        return []
    land = blaze.land
    arrive = blaze.arrival()
    wanted = []
    rings = (3, 2) if land.level.embers else (2,)
    for rank, distance in enumerate(rings):
        for i in ring(land.town, distance):
            if blaze.terrain[i] in (FOREST, GRASS) and \
                    blaze.state[i] == UNBURNT:
                when = arrive.get(i)
                if when is None:
                    if rank == 0:
                        continue
                    # Shut off from the spread, but not from embers.
                    when = 999.0
                elif when < land.level.dig * 0.5:
                    continue
                wanted.append((rank, when, i))
    if not wanted:
        return []
    wanted.sort()
    target = wanted[0][-1]
    return _go(blaze, target)


def _go(blaze: Blaze, target: int) -> List[int]:
    tc, tr = colrow(target)
    c, r = blaze.cursor
    ports = []
    while (c, r) != (tc, tr):
        dc, dr = tc - c, tr - r
        if abs(dc) >= 4:
            ports.append(JUMP + (RIGHT if dc > 0 else LEFT))
            c += 4 if dc > 0 else -4
        elif abs(dr) >= 4:
            ports.append(JUMP + (UP if dr > 0 else DOWN))
            r += 4 if dr > 0 else -4
        elif dc:
            ports.append(RIGHT if dc > 0 else LEFT)
            c += 1 if dc > 0 else -1
        else:
            ports.append(UP if dr > 0 else DOWN)
            r += 1 if dr > 0 else -1
    ports.append(DIG)
    return ports


def apply(blaze: Blaze, port: int) -> None:
    if port == DIG:
        blaze.dig()
    elif 0 <= port < 4:
        blaze.move(*STEPS[port])
    elif JUMP <= port < JUMP + 4:
        dc, dr = STEPS[port - JUMP]
        blaze.move(dc * 4, dr * 4)


def play(land: Land, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[int, bool]:
    """Burned cells and whether the town stood, under *pilot*.

    The pilot's ports all land in the same tick: a crew that knows
    where it is going is not slowed by the walk there."""
    blaze = Blaze(land)
    while blaze.result is None:
        for port in pilot(blaze):
            apply(blaze, port)
        blaze.step(dt)
    town_ok = all(blaze.state[t] == UNBURNT for t in land.town)
    return blaze.burned(), town_ok
