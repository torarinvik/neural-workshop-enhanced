# -*- coding: utf-8 -*-
"""Crazy Cog: build a gear train that lifts the bucket.

A motor turns on the left of the board, a winch waits somewhere to the
right with a bucket hanging from its drum, and along the bottom is a
tray of cogs of five sizes, each marked with its teeth, and from rung 4
a coil of chain. Drag a cog onto the board and it snaps into mesh with
the cogs it is dropped beside, or onto an axle (the motor's, the
winch's, the fan's) when it is dropped over one. Meshed cogs turn
opposite ways, and a small cog turns faster than the big one driving
it, by the ratio of their sizes. A chain from one cog to another, at
any distance, turns them the same way, by the same ratio. Drag a placed
cog to take it back; R (port 14) clears the board.

The machine has depth. From rung 10 it is a box of glass planes, one
behind the other (two at rung 10, three at 16, four at 24, five from
32): the motor turns on the front plane and the winch, its bucket and
its axle stand on the deepest. Tab (port 15) moves the hand a plane
deeper and G (port 16) a plane nearer. Cogs on different planes pass
over each other without touching, walls stand on one plane only, and a
cog dropped on a plane right over the middle of a cog on another plane
goes on the same axle: the two turn together. That is the only way the
drive travels back through the box, so every train from rung 10 on
carries it down, plane by plane, on shared axles, and a cog put on the
winch's spot on the wrong plane turns nothing.

The motor is strong at a crawl and weak at speed. A small cog on the
motor driving a big cog on the winch lifts a heavy bucket slowly; the
other way round lifts a light one quickly and stalls under a heavy one.
Turn the winch the wrong way and the bucket stays on the floor. Close a
ring of cogs that cannot all turn together and the train jams.

The ladder:

* rungs 1-3: the motor and the winch side by side: two cogs that fit;
* rungs 4-6: further apart: idlers or chains between, and the winch
  has to turn the right way;
* rungs 7-9: a heavy bucket: gear down or the motor stalls;
* rungs 10-15: walls to build around, and a second plane behind the
  first with the winch on it: carry the drive back on a shared axle;
* rungs 13-15: walls on the front plane in the direct way;
* rungs 16-19: a fan that must also turn, the way its arrow shows, and
  a tight clock, so not too slow either;
* from rung 16 a third plane, from 24 a fourth, from 32 a fifth, each
  with walls of its own from rung 20;
* from rung 20: buckets too heavy for any two cogs (only a compound
  gear lifts them), the fan's speed on its dial's green, and less time
  every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import hand as H
from .i18n import _

CLEAR = H.KEYS
LAYER = H.KEYS + 1             # one plane deeper (from the back: the front)
NEARER = H.KEYS + 2            # one plane nearer
PORTS = H.KEYS + 3
DEPTH = 5                      # planes at most, front to back
EVENTS = tuple(range(PORTS))
SIZES = (22.0, 30.0, 40.0, 52.0, 66.0)    # cog radii, screen units
PITCH = 9.0                    # screen units a tooth
TOL = 3.0                      # how close to touching is a mesh
SNAP = 28.0                    # how far a drop is pulled into place
BOARD = (30.0, 130.0, 970.0, 590.0)       # left, bottom, right, top
TRAY_Y = 62.0
FLOOR = 140.0
DRUM = 18.0
FREE = 6.0                     # the motor's speed with nothing on it
TORQUE = 1.0                   # its pull at a standstill
SETTLE = 0.25                  # seconds the train takes to come to speed
SLACK = 12.0                   # a chain wants at least this much gap
CHAIN = 'chain'
TICK, CLUNK, HUM, GRIND, DONE, MISS = range(6)
PATCHES = ('wood', 'growl', 'brass', 'growl', 'bell', 'pad')


class Grade(NamedTuple):
    rung: int
    links: int                 # links the reference train has, at least
    chains: bool
    layers: int
    load: float
    walls: int
    walls_back: int
    fan: int                   # 0 none, 1 its way, 2 its way and speed
    spare: int
    slack: float               # travel time allowed over the reference
    place: float               # seconds allowed a part to put it down


def planes(r: int) -> int:
    """How many planes deep the board is at rung *r*."""
    return 1 if r < 10 else 2 if r < 16 else 3 if r < 24 else \
        4 if r < 32 else DEPTH


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    deep = planes(r)
    links = 1 if r < 4 else 3 if r < 13 else 4 if r < 20 \
        else min(7, 5 + top // 6)
    return Grade(
        rung=r,
        links=max(links, 2 * deep - 1),       # an axle down to each plane
        chains=r >= 4,
        layers=deep,
        load=(0.3 if r < 7 else 1.0 if r < 13 else 1.2 if r < 20
              else min(3.6, 3.1 + 0.03 * top)),
        walls=0 if r < 10 else 2 if r < 20 else min(4, 2 + top // 6),
        walls_back=0 if r < 20 else min(2, 1 + top // 10),
        fan=0 if r < 16 else 1 if r < 20 else 2,
        spare=4 if r < 7 else 3 if r < 16 else 2 if r < 20
        else max(1, 2 - top // 8),
        slack=3.0 if r < 16 else 1.6 if r < 20 else max(1.2, 1.5 - 0.01 * top),
        place=12.0 if r < 4 else 9.0 if r < 16 else 6.0 if r < 20
        else max(3.5, 5.5 - 0.1 * top))


class Cog(NamedTuple):
    x: float
    y: float
    r: float
    z: int = 0                 # 0 the front layer, 1 the back


Pt = Tuple[float, float]
Wall = Tuple[float, float, float, float, int]      # x, y, w, h, layer
Link = Tuple[Cog, Cog]


class Machine(NamedTuple):
    level: Grade
    motor: Pt
    winch: Pt
    fan: Optional[Pt]
    fan_way: int               # +1 anticlockwise, -1 clockwise
    fan_band: Tuple[float, float]   # radians a second, for rung 20 on
    walls: Tuple[Wall, ...]
    tray: Tuple[float, ...]    # the radii in the tray, in slot order
    chains: int                # lengths of chain in the tray
    plan: Tuple[Cog, ...]      # a train that works, in building order
    plan_chains: Tuple[Link, ...]
    lift: float
    seconds: float
    winch_z: int = 0           # the plane the winch is on (the motor: 0)
    fan_z: int = 0


def teeth(r: float) -> int:
    return max(8, int(round(2 * math.pi * r / PITCH)))


TRAY_MAX = 14


def gap(n: int) -> float:
    """How far apart the tray's slots are."""
    return min(100.0, 940.0 / max(1, n))


def slot(k: int, n: int) -> Pt:
    return (500.0 + (k - (n - 1) / 2.0) * gap(n), TRAY_Y)


def in_wall(x: float, y: float, r: float, wall) -> bool:
    wx, wy, ww, wh = wall[:4]
    nx, ny = max(wx, min(x, wx + ww)), max(wy, min(y, wy + wh))
    return math.hypot(x - nx, y - ny) < r + 2.0


def fits(c: Cog, others, walls, pegs=()) -> bool:
    """On the board, clear of its layer's walls and of the axles, and
    either meshed with or clear of every other cog on its layer."""
    l, b, rt, t = BOARD
    if not (l + c.r <= c.x <= rt - c.r and b + c.r <= c.y <= t - c.r):
        return False
    if any(w[4] == c.z and in_wall(c.x, c.y, c.r, w) for w in walls):
        return False
    for p in pegs:
        d = math.hypot(c.x - p[0], c.y - p[1])
        if 1.0 < d < c.r + 8.0:
            return False
    for o in others:
        if o.z != c.z:
            continue
        if math.hypot(c.x - o.x, c.y - o.y) < c.r + o.r - TOL:
            return False
    return True


def meshed(a: Cog, b: Cog) -> bool:
    return a.z == b.z and \
        abs(math.hypot(a.x - b.x, a.y - b.y) - (a.r + b.r)) <= TOL


def same_axle(a: Cog, b: Cog) -> bool:
    return a.z != b.z and abs(a.x - b.x) < 1.0 and abs(a.y - b.y) < 1.0


def chain_ok(a: Cog, b: Cog, walls) -> bool:
    """A chain can run between these two: same layer, apart, no wall."""
    if a.z != b.z or a == b:
        return False
    d = math.hypot(a.x - b.x, a.y - b.y)
    if d < a.r + b.r + SLACK:
        return False
    for k in range(1, 20):
        x = a.x + (b.x - a.x) * k / 20.0
        y = a.y + (b.y - a.y) * k / 20.0
        if any(w[4] == a.z and in_wall(x, y, 4.0, w) for w in walls):
            return False
    return True


def lift_speed(g: float, load: float) -> float:
    """Settled winch speed with gearing *g* (motor turns per winch turn)
    under *load*: the motor's pull falls off as it speeds up."""
    return max(0.0, FREE / g * (1.0 - load / (TORQUE * g)))


def _sign(kinds) -> int:
    return (-1) ** sum(k == 'mesh' for k in kinds)


def _place(prev: Cog, kind: str, r: float, a: float,
           draw: random.Random) -> Cog:
    if kind == 'axle':                         # one plane deeper
        return Cog(prev.x, prev.y, r, prev.z + 1)
    gap = draw.uniform(60.0, 170.0) if kind == CHAIN else 0.0
    d = prev.r + r + gap
    return Cog(prev.x + d * math.cos(a), prev.y + d * math.sin(a), r, prev.z)


def _clear(c: Cog, prev: Optional[Cog], placed, walls, pegs) -> bool:
    if not fits(c, [], walls, pegs):
        return False
    for o in placed:
        if o is prev or o.z != c.z:
            continue
        if math.hypot(c.x - o.x, c.y - o.y) < c.r + o.r + SNAP + 6.0:
            return False
    return True


def _kinds(level: Grade, draw: random.Random) -> List[str]:
    """What each link of the reference train is: a mesh, a chain, or an
    axle onto the other layer. The winch must end up turning the other
    way from the motor."""
    n = level.links
    if n == 1:
        return ['mesh']
    pool = ['mesh', 'mesh'] + ([CHAIN] if level.chains else [])
    axles = level.layers - 1                   # the winch is on the back
    for _try in range(200):
        kinds = [draw.choice(pool) for _k in range(n)]
        spots = list(range(1, n - 1))
        draw.shuffle(spots)
        for k in spots[:axles]:
            kinds[k] = 'axle'
        if kinds.count('axle') != axles:
            continue
        if kinds[-1] == 'axle' or kinds[0] == 'axle':
            continue
        if any(a == b == 'axle' for a, b in zip(kinds, kinds[1:])):
            continue
        if kinds[-1] == 'mesh' and kinds[-2] == 'axle':
            continue
        if _sign(kinds) == -1:
            return kinds
    return []


def build(level: Grade, draw: random.Random) -> Optional[Machine]:
    kinds = _kinds(level, draw)
    if not kinds:
        return None
    for _try in range(300):
        radii = [draw.choice(SIZES) for _k in range(len(kinds) + 1)]
        ratio = 1.0                              # motor turns a winch turn
        for k, kind in enumerate(kinds):
            if kind != 'axle':
                ratio *= radii[k + 1] / radii[k]
        if level.load <= 0.5 or level.load * 1.15 < ratio < \
                level.load * 3.2:
            break
    else:
        return None
    if lift_speed(ratio, level.load) <= 0.0:
        return None
    motor = Cog(draw.uniform(90, 170), draw.uniform(200, 480), radii[0])
    pegs: List[Pt] = [(motor.x, motor.y)]
    plan, prev, head = [motor], motor, draw.uniform(-0.3, 0.4)
    for k, kind in enumerate(kinds):
        last = k == len(kinds) - 1
        for _try in range(30):
            c = _place(prev, kind, radii[k + 1],
                       head + draw.uniform(-0.9, 0.9), draw)
            if kind == 'axle':
                if _clear(c, prev, plan, (), ()):
                    break
                return None
            if _clear(c, prev, plan, (), pegs if not last else pegs[:1]) \
                    and (not last or (c.y >= 360.0 and c.x <= 880.0
                                      and (len(kinds) == 1 or
                                           c.x - motor.x >= 200.0))):
                break
        else:
            return None
        plan.append(c)
        prev = c
    wc = plan[-1]
    rope_x = wc.x + DRUM
    if rope_x + 40 > BOARD[2]:
        return None
    if any(o.x - o.r < rope_x + 26 and rope_x - 26 < o.x + o.r
           and o.y < wc.y and o.z == wc.z for o in plan[:-1]):
        return None
    pegs.append((wc.x, wc.y))
    links = list(zip(plan, plan[1:], kinds))
    fan, fan_way, band, fan_parts = None, 0, (0.0, 0.0), []
    if level.fan:
        idx = draw.randrange(1, len(plan) - 1)
        base = plan[idx]
        sign = -1 * _sign(kinds[:idx])           # base's way, motor clockwise
        speed_base = 1.0
        for k in range(idx):
            if kinds[k] != 'axle':
                speed_base *= radii[k] / radii[k + 1]
        if level.chains and draw.random() < 0.5:
            fc = None
            for _try in range(30):
                fc = _place(base, CHAIN, draw.choice(SIZES),
                            draw.uniform(0.5, 2.6), draw)
                if _clear(fc, base, plan, (), pegs):
                    break
                fc = None
            if fc is None:
                return None
            fan_parts = [(fc, base, CHAIN)]
            way = sign
            speed = speed_base * base.r / fc.r
        else:
            mid = fc = None
            for _try in range(40):
                mid = _place(base, 'mesh', draw.choice(SIZES),
                             draw.uniform(0.5, 2.6), draw)
                if not _clear(mid, base, plan, (), pegs):
                    continue
                fc = _place(mid, 'mesh', draw.choice(SIZES),
                            draw.uniform(0.3, 2.8), draw)
                if _clear(fc, mid, plan + [mid], (), pegs):
                    break
                fc = None
            if fc is None:
                return None
            fan_parts = [(fc, None, None), (mid, base, 'mesh')]
            way = sign
            speed = speed_base * base.r / fc.r
        if math.hypot(fc.x - motor.x, fc.y - motor.y) < 130.0 or \
                math.hypot(fc.x - wc.x, fc.y - wc.y) < 110.0 or \
                fc.y > 540.0 or not 90.0 < fc.x < 910.0 or \
                (fc.x + fc.r > rope_x - 10 and fc.y < wc.y and fc.z == wc.z):
            return None
        fan, fan_way = (fc.x, fc.y), way
        motor_speed = lift_speed(ratio, level.load) * ratio
        band = (motor_speed * speed * 0.85, motor_speed * speed * 1.15)
        pegs.append(fan)
    every = plan + [p[0] for p in fan_parts]
    walls: List[Wall] = []
    line = (motor.x, motor.y, wc.x, wc.y)
    want = [(0, level.walls)] + [(z, level.walls_back)
                                 for z in range(1, level.layers)]
    for z, count in want:
        got = 0
        for _try in range(300):
            if got >= count:
                break
            ww, wh = draw.uniform(20, 70), draw.uniform(80, 220)
            t = draw.uniform(0.25, 0.75)
            cx = line[0] + (line[2] - line[0]) * t + draw.uniform(-120, 120)
            cy = line[1] + (line[3] - line[1]) * t + draw.uniform(-140, 140)
            wall = (cx - ww / 2, cy - wh / 2, ww, wh, z)
            l, b, rt, top_ = BOARD
            if wall[0] < l or wall[1] < b or wall[0] + ww > rt or \
                    wall[1] + wh > top_:
                continue
            if any(c.z == z and in_wall(c.x, c.y, c.r + 10.0, wall)
                   for c in every):
                continue
            if z == 0 and level.layers > 1 and _try < 250 and not any(
                    in_wall(line[0] + (line[2] - line[0]) * k / 30.0,
                            line[1] + (line[3] - line[1]) * k / 30.0, 1.0,
                            wall) for k in range(31)):
                continue                         # stand in the direct way
            if any(in_wall(p[0], p[1], 75.0, wall) for p in pegs) or \
                    in_wall(wc.x, wc.y + 84, 20.0, wall):
                continue
            if z == wc.z and wall[0] < rope_x + 40 and \
                    wall[0] + ww > rope_x - 30 and wall[1] < wc.y:
                continue
            if any(o[4] == z and wall[0] < o[0] + o[2] + 20 and
                   o[0] < wall[0] + ww + 20 and wall[1] < o[1] + o[3] + 20
                   and o[1] < wall[1] + wh + 20 for o in walls):
                continue
            if any(kind == CHAIN and a.z == z and not chain_ok(a, b2, [wall])
                   for a, b2, kind in links):
                continue
            walls.append(wall)
            got += 1
        if got < count:
            return None
    chains = [(a, b2) for a, b2, kind in links if kind == CHAIN]
    for fc_, base_, kind in fan_parts:
        if kind == CHAIN:
            chains.append((base_, fc_))
    if any(not chain_ok(a, b2, walls) for a, b2 in chains):
        return None
    # Building order: each part goes down where it lands exactly.
    order: List[Cog] = [motor]
    body = plan[1:-1]
    last_kind = kinds[-1]
    if last_kind == 'mesh' and body:
        order += body[:-1]
        order += [p[0] for p in fan_parts]
        order += [wc, body[-1]]
    else:
        order += body
        order += [p[0] for p in fan_parts]
        order.append(wc)
    if len(set(order)) != len(order):
        return None
    tray = [c.r for c in order] + [draw.choice(SIZES)
                                   for _k in range(level.spare)]
    n_chain = len(chains) + (1 if level.chains else 0)
    if len(tray) + (1 if level.chains else 0) > TRAY_MAX:
        return None
    draw.shuffle(tray)
    lift = wc.y - 70.0 - FLOOR
    travel = lift / (lift_speed(ratio, level.load) * DRUM) + SETTLE * 4
    seconds = level.place * (len(order) + len(chains)) + \
        travel * level.slack + 3.0
    fan_z = fan_parts[0][0].z if fan_parts else 0
    return Machine(level, (motor.x, motor.y), (wc.x, wc.y), fan, fan_way,
                   band, tuple(walls), tuple(tray), n_chain, tuple(order),
                   tuple(chains), lift, seconds, wc.z, fan_z)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Machine:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=4000)


class Run(H.HandRun):
    def __init__(self, machine: Machine) -> None:
        super().__init__(machine.seconds)
        self.machine, self.level = machine, machine.level
        self.tray: List[Optional[float]] = list(machine.tray)
        self.chain_stock = machine.chains
        self.cogs: List[Cog] = []
        self.chains: List[Link] = []
        self.carry = None                      # a radius, CHAIN, or None
        self.chain_from: Optional[Cog] = None  # a chain's end in the hand
        self.layer = 0
        self.angle: Dict[Cog, float] = {}      # turned so far
        self.ratio: Dict[Cog, float] = {}
        self.jammed = False
        self.height = 0.0
        self.out = 0.0                         # winch speed, signed
        self.hum_at = 0.0
        self.tick_at = 0.0
        self.pegs = [machine.motor, machine.winch] + (
            [machine.fan] if machine.fan else [])
        # Each axle stands on one plane: the motor's on the front, the
        # winch's on its plane at the back.
        self.peg_z = [0, machine.winch_z] + (
            [machine.fan_z] if machine.fan else [])

    # --- the board -----------------------------------------------------

    def chain_slot(self) -> Optional[int]:
        return len(self.tray) if self.machine.chains else None

    def slots(self) -> int:
        return len(self.tray) + (1 if self.machine.chains else 0)

    def on(self, peg: Optional[Pt], z: Optional[int] = None
           ) -> Optional[Cog]:
        if peg is None:
            return None
        for c in self.cogs:
            if math.hypot(c.x - peg[0], c.y - peg[1]) < 1.0 and \
                    (z is None or c.z == z):
                return c
        return None

    def snap(self, x: float, y: float, r: float, z: Optional[int] = None
             ) -> Cog:
        """Where a cog of radius *r* dropped at (x, y) on layer *z* comes
        to rest."""
        z = self.layer if z is None else z
        for p, pz in zip(self.pegs, self.peg_z):
            if pz == z and math.hypot(x - p[0], y - p[1]) <= SNAP and \
                    self.on(p, z) is None:
                return Cog(p[0], p[1], r, z)
        for o in self.cogs:                     # onto another's axle
            if o.z != z and math.hypot(x - o.x, y - o.y) <= SNAP * 0.6 \
                    and self.on((o.x, o.y), z) is None:
                return Cog(o.x, o.y, r, z)
        best, gap = Cog(x, y, r, z), SNAP
        mine = [c for c in self.cogs if c.z == z]
        for i, a in enumerate(mine):
            for b in mine[i + 1:]:
                for p in _meet(a, b, r):
                    d = math.hypot(p[0] - x, p[1] - y)
                    if d < gap * 1.5:
                        best, gap = Cog(p[0], p[1], r, z), d / 1.5
        if gap < SNAP:
            return best
        for a in mine:
            d = math.hypot(x - a.x, y - a.y) or 1.0
            px = a.x + (x - a.x) * (a.r + r) / d
            py = a.y + (y - a.y) * (a.r + r) / d
            g = math.hypot(px - x, py - y)
            if g < gap:
                best, gap = Cog(px, py, r, z), g
        return best

    def placeable(self, c: Cog) -> bool:
        return fits(c, self.cogs, self.machine.walls,
                    [p for p in self.pegs
                     if math.hypot(c.x - p[0], c.y - p[1]) >= 1.0])

    def tray_at(self, x: float, y: float) -> Optional[int]:
        n = self.slots()
        for k in range(n):
            sx, sy = slot(k, n)
            if abs(x - sx) <= min(40.0, gap(n) / 2) and abs(y - sy) <= 40:
                if k == self.chain_slot():
                    return k if self.chain_stock > 0 else None
                return k if self.tray[k] is not None else None
        return None

    def cog_at(self, x: float, y: float) -> Optional[Cog]:
        for c in reversed(self.cogs):
            if c.z == self.layer and math.hypot(x - c.x, y - c.y) <= c.r:
                return c
        return None

    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        x, y = self.hand.x, self.hand.y
        if self.chain_from is not None:          # the chain's other end
            a, self.chain_from = self.chain_from, None
            b = self.cog_at(x, y)
            if b is not None and chain_ok(a, b, self.machine.walls) and \
                    (a, b) not in self.chains and (b, a) not in self.chains:
                self.chains.append((a, b))
                self.note(0.12, 640.0, TICK, 0.45, pan=(b.x - 500) / 500)
                self._rewire()
            else:
                self.chain_stock += 1
                self.note(0.15, 90.0, CLUNK, 0.4)
            return
        k = self.tray_at(x, y)
        if k is not None:
            if k == self.chain_slot():
                self.chain_stock -= 1
                self.carry = CHAIN
            else:
                self.carry, self.tray[k] = self.tray[k], None
            self.note(0.05, 900.0, TICK, 0.3)
            return
        c = self.cog_at(x, y)
        if c is not None:
            self.cogs.remove(c)
            for link in [l for l in self.chains if c in l]:
                self.chains.remove(link)
                self.chain_stock += 1
            self.carry = c.r
            self.note(0.05, 700.0, TICK, 0.3)
            self._rewire()

    def _back(self, r: float) -> None:
        for k, t in enumerate(self.tray):
            if t is None:
                self.tray[k] = r
                return
        self.tray.append(r)

    def release(self) -> None:
        if not self.hand.down:
            return
        self.hand.down = False
        r, self.carry = self.carry, None
        if r is None or self.result is not None:
            return
        x, y = self.hand.x, self.hand.y
        if r == CHAIN:
            a = self.cog_at(x, y) if y >= BOARD[1] else None
            if a is None:
                self.chain_stock += 1
            else:
                self.chain_from = a
                self.note(0.05, 560.0, TICK, 0.3)
            return
        if y < BOARD[1]:
            self._back(r)
            return
        c = self.snap(x, y, r)
        if not self.placeable(c):
            self._back(r)
            self.note(0.15, 90.0, CLUNK, 0.4)
            return
        self.cogs.append(c)
        n = sum(meshed(c, o) or same_axle(c, o) for o in self.cogs
                if o is not c)
        self.note(0.07, 520.0 if n else 300.0, TICK, 0.45,
                  pan=(c.x - 500) / 500)
        self._rewire()

    def key(self, port: int) -> None:
        if self.result is not None:
            return
        if port in (LAYER, NEARER):
            n = self.level.layers
            if n > 1:
                self.layer = (self.layer + (1 if port == LAYER else -1)) % n
                self.note(0.05, 600.0 - 80.0 * self.layer, TICK, 0.25)
            return
        if port != CLEAR:
            return
        for c in self.cogs:
            self._back(c.r)
        self.chain_stock += len(self.chains) + (
            1 if self.chain_from is not None else 0)
        self.cogs, self.chains, self.chain_from = [], [], None
        self._rewire()

    # --- the physics ---------------------------------------------------

    def _rewire(self) -> None:
        """Which way and how fast every cog turns, per radian a second of
        the motor; and whether the train jams."""
        self.ratio = {}
        self.jammed = False
        drive = [c for c in self.cogs if c.z == 0 and
                 math.hypot(c.x - self.machine.motor[0],
                            c.y - self.machine.motor[1]) < 1.0]
        if not drive:
            return
        for m in drive:
            self.ratio[m] = -1.0                 # the motor turns clockwise
        todo = list(drive)
        while todo:
            a = todo.pop()
            for b in self.cogs:
                if b is a:
                    continue
                if meshed(a, b):
                    w = -self.ratio[a] * a.r / b.r
                elif same_axle(a, b):
                    w = self.ratio[a]
                elif (a, b) in self.chains or (b, a) in self.chains:
                    w = self.ratio[a] * a.r / b.r
                else:
                    continue
                if b in self.ratio:
                    if abs(self.ratio[b] - w) > 1e-6:
                        self.jammed = True
                    continue
                self.ratio[b] = w
                todo.append(b)
        if self.jammed:
            self.note(0.4, 60.0, GRIND, 0.5)

    def gearing(self) -> Optional[float]:
        """The winch's turn per motor turn, anticlockwise positive."""
        w = self.on(self.machine.winch, self.machine.winch_z)
        if w is None or w not in self.ratio or self.jammed:
            return None
        return self.ratio[w]

    def motor_speed(self) -> float:
        if not self.ratio or self.jammed:
            return 0.0
        g = self.gearing()
        if g is None or g < 0:
            return FREE
        if self.height >= self.machine.lift:
            return 0.0
        return self.out / g if g else 0.0

    def turning(self, c: Cog) -> float:
        """Radians a second, anticlockwise positive."""
        return self.ratio.get(c, 0.0) * self.motor_speed()

    def fan_speed(self) -> float:
        f = self.on(self.machine.fan, self.machine.fan_z)
        return 0.0 if f is None else self.turning(f)

    def fan_ok(self) -> bool:
        mc = self.machine
        if mc.fan is None:
            return True
        s = self.fan_speed() * mc.fan_way
        if s <= 0.05:
            return False
        if self.level.fan >= 2:
            return mc.fan_band[0] <= s <= mc.fan_band[1]
        return True

    def stalled(self) -> bool:
        g = self.gearing()
        return g is not None and g > 0 and \
            lift_speed(1.0 / g, self.level.load) <= 0.0

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        mc = self.machine
        g = self.gearing()
        if g is None:
            want = 0.0
        elif g > 0:
            want = lift_speed(1.0 / g, mc.level.load)
        else:
            want = FREE * g                     # turned the wrong way
        self.out += (want - self.out) * min(1.0, dt / SETTLE)
        fan_was_ok = self.fan_ok()
        self.height = max(0.0, min(mc.lift,
                                   self.height + self.out * DRUM * dt))
        for c in self.cogs:
            self.angle[c] = self.angle.get(c, 0.0) + self.turning(c) * dt
        speed = self.motor_speed()
        if self.t >= self.hum_at and self.ratio:
            self.hum_at = self.t + 0.5
            if self.jammed:
                self.note(0.3, 55.0, GRIND, 0.45, pan=-0.6)
            elif self.stalled():
                self.note(0.45, 70.0, HUM, 0.4, pan=-0.6)
            else:
                self.note(0.45, 80.0 + 30.0 * speed, HUM, 0.3, pan=-0.6)
            if mc.fan is not None and abs(self.fan_speed()) > 0.05:
                self.note(0.45, 200.0 + 40.0 * abs(self.fan_speed()), MISS,
                          0.2, pan=(mc.fan[0] - 500) / 500)
        if self.out > 0.05 and self.height // 20 != self.tick_at:
            self.tick_at = self.height // 20
            self.note(0.04, 1200.0, TICK, 0.3, pan=0.6)
        if self.height >= mc.lift:
            if fan_was_ok:
                self.note(0.6, 880.0, DONE, 0.5)
                self.result = (True, _('Bucket up'))
            else:
                self.note(0.6, 110.0, CLUNK, 0.5)
                self.result = (False, _('Bucket up, but the fan was wrong'))
        elif self.t >= self.end:
            self.result = (False, _('Out of time'))


def _meet(a: Cog, b: Cog, r: float) -> List[Pt]:
    """Where a cog of radius *r* meshes with both *a* and *b*."""
    ra, rb = a.r + r, b.r + r
    dx, dy = b.x - a.x, b.y - a.y
    d = math.hypot(dx, dy)
    if d < 1e-6 or d > ra + rb or d < abs(ra - rb):
        return []
    k = (ra * ra - rb * rb + d * d) / (2 * d)
    h = math.sqrt(max(0.0, ra * ra - k * k))
    mx, my = a.x + dx * k / d, a.y + dy * k / d
    return [(mx - dy * h / d, my + dx * h / d),
            (mx + dy * h / d, my - dx * h / d)]


act = H.act


def _near(a: Cog, b: Cog) -> bool:
    return a.r == b.r and a.z == b.z and abs(a.x - b.x) < 6.0 and \
        abs(a.y - b.y) < 6.0


def autopilot(run: Run) -> List[int]:
    """Put the plan's cogs down in order, each fetched from the tray on
    its layer, then hang the plan's chains."""
    if run.result is not None:
        return []
    hand, mc = run.hand, run.machine
    if any(not any(_near(c, o) for c in mc.plan) for o in run.cogs) \
            and not hand.down and run.carry is None:
        return [CLEAR]
    todo = [c for c in mc.plan if not any(_near(c, o) for o in run.cogs)]
    if todo:
        c = todo[0]
        if run.carry is None:
            if hand.down:
                return [H.RELEASE]
            if run.layer != c.z:
                return [LAYER]
            n = run.slots()
            k = next((k for k, r in enumerate(run.tray) if r == c.r), None)
            if k is None:
                return [CLEAR]
            sx, sy = slot(k, n)
            move = H.toward(hand, sx, sy, tol=4.0)
            return [move] if move is not None else [H.PRESS]
        if run.carry != c.r:
            move = H.toward(hand, 500.0, TRAY_Y, tol=10.0)
            return [move] if move is not None else [H.RELEASE]
        move = H.toward(hand, c.x, c.y, tol=3.0)
        return [move] if move is not None else [H.RELEASE]
    placed = {c: next(o for o in run.cogs if _near(c, o)) for c in mc.plan}
    hung = [(a, b) for a, b in mc.plan_chains
            if (placed.get(a), placed.get(b)) in run.chains
            or (placed.get(b), placed.get(a)) in run.chains]
    left = [l for l in mc.plan_chains if l not in hung]
    if not left:
        return [H.RELEASE] if hand.down else []
    a, b = placed[left[0][0]], placed[left[0][1]]
    if run.carry == CHAIN:
        move = H.toward(hand, a.x, a.y, tol=3.0)
        return [move] if move is not None else [H.RELEASE]
    if hand.down:
        return [H.RELEASE]
    if run.layer != a.z:
        return [LAYER]
    if run.chain_from is not None:
        move = H.toward(hand, b.x, b.y, tol=3.0)
        return [move] if move is not None else [H.PRESS]
    sx, sy = slot(run.chain_slot(), run.slots())
    move = H.toward(hand, sx, sy, tol=4.0)
    return [move] if move is not None else [H.PRESS]


def play(machine: Machine, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(machine), pilot, EVENTS, act, dt)
