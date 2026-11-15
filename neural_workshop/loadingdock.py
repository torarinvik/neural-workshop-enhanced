# -*- coding: utf-8 -*-
"""Loading Dock: read the orders, drive the forklift, load the trucks
before they leave.

A warehouse floor. Along the back, a shelf of bays, each holding one
kind of crate -- a colour, and from the middle rungs a mark, F for
fragile or H for heavy -- that refills when one is taken. Along the
front, trucks, each with a city on its side. The orders are written at
the top: "OSLO: two red crates and a blue crate."

Keys drive the forklift, the way a forklift drives: Up and Down go
forward and back, Left and Right turn it. The mouse does the lifting:
with the forklift beside a bay, drag a crate from the bay onto the
forklift (it carries two); beside a truck, drag a crate from the
forklift onto the truck. When a truck has its order, click its lamp to
send it. A truck sounds its horn three seconds before it leaves by
itself, each truck at its own pitch, and a truck that leaves without
its order -- or is sent short, or is given the wrong crate -- loses the
run.

The ladder:

* rungs 1-3: one truck, one crate, three kinds on the shelf;
* rungs 4-6: two trucks, one or two crates each;
* rungs 7-9: three trucks; the camera cuts between corners of the
  warehouse;
* rungs 10-12: marked crates -- "a fragile crate", "a heavy red crate";
* rungs 13-15: "a crate that is not red"; cameras overhead and behind
  the shelf, where left and right are the other way round;
* rungs 16-19: four trucks in two waves, another forklift at work and a
  radio, neither of them yours;
* from rung 20: more trucks, less time for each, quicker cuts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .hand import Vec
from .i18n import _

# Held keys: the forklift.
FWD, BACK, LEFT, RIGHT, FWD_LEFT, FWD_RIGHT = range(H.KEYS, H.KEYS + 6)
PORTS = H.KEYS + 6
EVENTS = H.HAND_EVENTS
DRIVE = {FWD: (1, 0), BACK: (-1, 0), LEFT: (0, 1), RIGHT: (0, -1),
         FWD_LEFT: (1, 1), FWD_RIGHT: (1, -1)}

COLOURS = (_('red'), _('blue'), _('green'), _('yellow'))
TAGS = ('', _('fragile'), _('heavy'))
MARKS = ('', 'F', 'H')
CITIES = ('OSLO', 'BERGEN', 'ROME', 'LIMA', 'CAIRO', 'KYOTO', 'QUITO',
          'TURIN', 'DELHI', 'MALMO')
NUMBER = (_('no'), _('a'), _('two'), _('three'))
WIDE, DEEP = 10.0, 5.0         # the floor the forklift may drive on
SHELF_Z, TRUCK_Z = -6.6, 6.8
BAYS = (-6.0, 0.0, 6.0)        # where trucks stand
SPEED, SPIN = 6.5, 170.0
REACH_SHELF, REACH_TRUCK = 3.0, 3.6
CARRY = 2
GRAB = 46.0                    # how near the pointer has to be, in units
LAMP = 24.0                    # ... to a truck's lamp
HORN_AHEAD = 3.0
LOOK: Vec = (0.0, 0.0, 0.5)
CAMS: Tuple[Tuple[Vec, float], ...] = (
    ((0.0, 15.0, 17.0), 640.0), ((-15.0, 12.0, 13.0), 600.0),
    ((15.0, 12.0, 13.0), 600.0), ((0.0, 26.0, 2.5), 640.0),
    ((0.0, 14.0, -17.0), 620.0))
HORN, THUD, DING, BUZZ, ENGINE, BEEP, RADIO = range(7)
PATCHES = ('brass', 'wood', 'bell', 'growl', 'organ', 'square', 'pluck')


class Grade(NamedTuple):
    rung: int
    trucks: int
    wave: int                  # trucks at the dock at once
    most: int                  # crates a truck may want
    kinds: int                 # on the shelf
    tags: bool
    nots: bool
    cams: Tuple[int, ...]
    cut: float
    busy: bool                 # another forklift and a radio
    each: float                # seconds allowed a crate


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        trucks=(1 if r < 4 else 2 if r < 7 else 3 if r < 16 else 4 if r < 20
                else 5 + top // 3),
        wave=1 if r < 4 else 2 if r < 7 else 3 if r < 16 else 2 if r < 20
        else 3,
        most=1 if r < 4 else 2 if r < 10 else 3,
        kinds=3 if r < 4 else 4 if r < 10 else 6 if r < 13 else 8,
        tags=r >= 10, nots=r >= 13,
        cams=((0,) if r < 7 else (0, 1, 2) if r < 13 else (0, 1, 2, 3, 4)),
        cut=(0.0 if r < 7 else 7.0 if r < 13 else 5.5 if r < 20
             else max(2.5, 5.0 - 0.1 * top)),
        busy=r >= 16,
        each=(22.0 if r < 4 else 18.0 if r < 10 else 15.0 if r < 20
              else max(10.0, 14.5 - 0.1 * top)))


class Kind(NamedTuple):
    colour: int
    tag: int


class Need(NamedTuple):
    colour: int = -1           # the colour it must be, or -1
    tag: int = -1              # the mark it must have, or -1
    no: int = -1               # the colour it must not be, or -1

    def met_by(self, kind: Kind) -> bool:
        return (self.colour < 0 or kind.colour == self.colour) and \
            (self.tag < 0 or kind.tag == self.tag) and \
            (self.no < 0 or kind.colour != self.no)

    def words(self, count: int) -> str:
        crate = _('crate') if count == 1 else _('crates')
        if self.no >= 0:
            return (_('%s crate that is not %s') if count == 1 else
                    _('%s crates that are not %s')) % (NUMBER[count],
                                                      COLOURS[self.no])
        parts = [NUMBER[count]]
        if self.tag > 0:
            parts.append(TAGS[self.tag])
        if self.colour >= 0:
            parts.append(COLOURS[self.colour])
        return ' '.join(parts + [crate])


class Truck(NamedTuple):
    city: str
    bay: int
    arrive: float
    leave: float
    needs: Tuple[Need, ...]    # strictest first
    text: str


class Dock(NamedTuple):
    level: Grade
    shelf: Tuple[Kind, ...]
    trucks: Tuple[Truck, ...]
    cuts: Tuple[Tuple[float, int], ...]
    seconds: float
    seed: int


def slot_x(shelf: Tuple[Kind, ...], k: int) -> float:
    n = len(shelf)
    return (k - (n - 1) / 2.0) * min(2.4, 2 * (WIDE - 1.0) / max(1, n - 1))


def _order(city: str, needs: List[Need]) -> str:
    groups: List[Tuple[Need, int]] = []
    for need in needs:
        for j, (g, c) in enumerate(groups):
            if g == need:
                groups[j] = (g, c + 1)
                break
        else:
            groups.append((need, 1))
    said = [g.words(c) for g, c in groups]
    body = said[0] if len(said) == 1 else \
        _('%s and %s') % (', '.join(said[:-1]), said[-1])
    return '%s: %s.' % (city, body)


def _build(level: Grade, draw: random.Random) -> Dock:
    tags = (0, 1, 2) if level.tags else (0,)
    pool = [Kind(c, t) for c in range(len(COLOURS)) for t in tags]
    shelf = tuple(draw.sample(pool, level.kinds))
    cities = draw.sample(CITIES, min(len(CITIES), level.trucks)) * 3
    trucks: List[Truck] = []
    t = 0.0
    for first in range(0, level.trucks, level.wave):
        leave = t + 5.0
        bays = draw.sample(range(len(BAYS)), min(level.wave, len(BAYS)))
        for j in range(min(level.wave, level.trucks - first)):
            needs: List[Need] = []
            for _n in range(draw.randint(1, level.most)):
                kind = draw.choice(shelf)
                roll = draw.random()
                if level.nots and roll < 0.25:
                    other = [c for c in range(len(COLOURS))
                             if any(k.colour != c for k in shelf)]
                    need = Need(no=draw.choice(other))
                elif level.tags and kind.tag and roll < 0.55:
                    need = Need(tag=kind.tag)
                elif level.tags and kind.tag:
                    need = Need(colour=kind.colour, tag=kind.tag)
                else:
                    need = Need(colour=kind.colour, tag=0 if level.tags
                                else -1)
                needs.append(need)
            leave += level.each * len(needs)
            text = _order(cities[first + j], needs)
            needs.sort(key=lambda n: (n.no >= 0, -(n.colour >= 0)
                                      - (n.tag >= 0)))
            trucks.append(Truck(cities[first + j], bays[j], t, leave,
                                tuple(needs), text))
        t = leave + 3.0
    cuts, at, cam = [], 0.0, 0
    while level.cut and at < t:
        at += level.cut * draw.uniform(0.8, 1.25)
        cam = draw.choice([c for c in level.cams if c != cam])
        cuts.append((at, cam))
    return Dock(level, shelf, tuple(trucks), tuple(cuts), t,
                draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Dock:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _try in range(60):
        dock = _build(level, random.Random(draw.getrandbits(32)))
        if play(dock)[0]:
            return dock
    raise RuntimeError('no dock for rung %d' % rung)


class Run(H.HandRun):
    def __init__(self, dock: Dock) -> None:
        super().__init__(dock.seconds)
        self.dock, self.level = dock, dock.level
        self.p = (0.0, 0.0)            # the forklift, (x, z)
        self.heading = math.pi         # facing the shelf
        self.speed = 0.0
        self.carried: List[Kind] = []
        self.loads: List[List[Kind]] = [[] for _t in dock.trucks]
        self.met: List[List[bool]] = [[False] * len(t.needs)
                                      for t in dock.trucks]
        self.sent = [False] * len(dock.trucks)
        self.horned = [False] * len(dock.trucks)
        self.empty_until = [0.0] * len(dock.shelf)
        self.drag: Optional[Tuple[str, Kind, int]] = None
        self.pressed: Optional[int] = None     # a lamp being clicked
        self.cut_no, self.cam = 0, 0
        self.hum_at = 0.0
        self.beep_at = 0.0
        self.radio = random.Random(dock.seed)
        self.radio_at = 2.0

    # --- where things are
    def view(self):
        eye, focal = CAMS[self.cam]
        return H.lens(eye, LOOK, focal, 500.0, 320.0)

    def forward(self) -> Tuple[float, float]:
        return math.sin(self.heading), math.cos(self.heading)

    def here(self, k: int) -> bool:
        t = self.dock.trucks[k]
        return t.arrive <= self.t and not self.sent[k]

    def waiting(self) -> List[int]:
        return [k for k in range(len(self.dock.trucks)) if self.here(k)]

    def slot(self, k: int) -> Vec:
        return (slot_x(self.dock.shelf, k), 1.0, SHELF_Z)

    def bed(self, k: int) -> Vec:
        return (BAYS[self.dock.trucks[k].bay], 1.3, TRUCK_Z)

    def lamp(self, k: int) -> Vec:
        return (BAYS[self.dock.trucks[k].bay] + 2.3, 3.3, TRUCK_Z + 0.6)

    def fork(self) -> Vec:
        return (self.p[0], 0.9, self.p[1])

    def near_slot(self, k: int) -> bool:
        s = self.slot(k)
        return math.hypot(self.p[0] - s[0], self.p[1] - (SHELF_Z + 1.6)) \
            <= REACH_SHELF

    def near_truck(self, k: int) -> bool:
        b = self.bed(k)
        return math.hypot(self.p[0] - b[0], self.p[1] - (TRUCK_Z - 1.8)) \
            <= REACH_TRUCK

    def _off(self, point: Vec) -> float:
        """How far the pointer is from *point* on the screen."""
        q = self.view().see(point)
        return 1e9 if q is None else math.hypot(self.hand.x - q[0],
                                                self.hand.y - q[1])

    def _over(self, point: Vec, reach: float = GRAB) -> bool:
        return self._off(point) <= reach

    def stocked(self, k: int) -> bool:
        return self.t >= self.empty_until[k]

    def complete(self, k: int) -> bool:
        return all(self.met[k])

    # --- the hand
    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        # Whatever is nearest the pointer, of the things in reach.
        picks = [(self._off(self.lamp(k)) / LAMP, 'lamp', k)
                 for k in self.waiting()]
        if self.carried:
            picks.append((self._off(self.fork()) / GRAB, 'fork', -1))
        picks += [(self._off(self.slot(k)) / GRAB, 'shelf', k)
                  for k in range(len(self.dock.shelf))
                  if self.stocked(k) and self.near_slot(k)]
        picks = [p for p in picks if p[0] <= 1.0]
        if not picks:
            return
        _d, what, k = min(picks)
        if what == 'lamp':
            self.pressed = k
        elif what == 'fork':
            self.drag = ('fork', self.carried.pop(), -1)
        else:
            self.drag = ('shelf', self.dock.shelf[k], k)
            self.empty_until[k] = 1e9

    def release(self) -> None:
        if not self.hand.down:
            return
        self.hand.down = False
        lamp, self.pressed = self.pressed, None
        drag, self.drag = self.drag, None
        if self.result is not None:
            return
        if lamp is not None:
            if self.here(lamp) and self._over(self.lamp(lamp), LAMP):
                self._send(lamp)
            return
        if drag is None:
            return
        where, kind, k = drag
        if where == 'shelf':
            if len(self.carried) < CARRY and self._over(self.fork()):
                self.carried.append(kind)
                self.empty_until[k] = self.t + 1.5
                self.note(0.1, 170.0, THUD, 0.5)
            else:
                self.empty_until[k] = 0.0
            return
        beds = [(self._off(self.bed(j)), j) for j in self.waiting()
                if self.near_truck(j)]
        if beds and min(beds)[0] <= 60.0:
            return self._load(min(beds)[1], kind)
        for j in range(len(self.dock.shelf)):
            if self.near_slot(j) and self._over(self.slot(j)):
                self.note(0.1, 150.0, THUD, 0.4)     # put back
                return
        self.carried.append(kind)

    def _load(self, k: int, kind: Kind) -> None:
        truck = self.dock.trucks[k]
        for j, need in enumerate(truck.needs):
            if not self.met[k][j] and need.met_by(kind):
                self.met[k][j] = True
                self.loads[k].append(kind)
                self.note(0.12, 130.0, THUD, 0.6)
                return
        self._fail(_('%s did not order that crate') % truck.city)

    def _send(self, k: int) -> None:
        truck = self.dock.trucks[k]
        if not self.complete(k):
            return self._fail(_('%s was sent without its order')
                              % truck.city)
        self.sent[k] = True
        for j, semis in enumerate((0, 7)):
            self.note(0.25, 587.0 * 2 ** (semis / 12.0), DING, 0.5,
                      at=self.t + 0.1 * j)
        if all(self.sent):
            self.result = (True, _('Every truck left with its order'))

    def _fail(self, why: str) -> None:
        self.note(0.4, 100.0, BUZZ, 0.6)
        self.result = (False, why)

    # --- the clock
    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        cuts = self.dock.cuts
        while self.cut_no < len(cuts) and cuts[self.cut_no][0] <= self.t:
            self.cam = cuts[self.cut_no][1]
            self.cut_no += 1
        go, turn = 0.0, 0.0
        if control is not None:
            for port in (control if isinstance(control, (set, frozenset))
                         else (control,)):
                a, b = DRIVE.get(port, (0, 0))
                go += a
                turn += b
        go, turn = max(-1.0, min(1.0, go)), max(-1.0, min(1.0, turn))
        if self.drag is not None:
            go = turn = 0.0                # the brake is on while lifting
        self.heading += math.radians(SPIN) * turn * dt
        self.speed = SPEED * go * (1.0 if go > 0 else 0.6)
        fx, fz = self.forward()
        self.p = (max(-WIDE, min(WIDE, self.p[0] + fx * self.speed * dt)),
                  max(-DEEP, min(DEEP, self.p[1] + fz * self.speed * dt)))
        self._sound(go)
        for k, truck in enumerate(self.dock.trucks):
            if not self.here(k):
                continue
            if not self.horned[k] and self.t >= truck.leave - HORN_AHEAD:
                self.horned[k] = True
                q = self.view().see(self.bed(k))
                pan = 0.0 if q is None else (q[0] - 500.0) / 500.0
                for j in range(2):
                    self.note(0.35, 146.8 * 2 ** (truck.bay * 4 / 12.0),
                              HORN, 0.6, pan=pan, at=self.t + 0.5 * j)
            if self.t >= truck.leave:
                if self.complete(k):
                    self._send(k)
                else:
                    self._fail(_('%s left without its order') % truck.city)
                if self.result is not None:
                    return

    def _sound(self, go: float) -> None:
        if go and self.t >= self.hum_at:
            self.hum_at = self.t + 0.25
            self.note(0.27, 70.0 if go > 0 else 60.0, ENGINE, 0.18)
        if go < 0 and self.t >= self.beep_at:
            self.beep_at = self.t + 0.5
            self.note(0.2, 1000.0, BEEP, 0.2)
        if self.level.busy and self.t >= self.radio_at:
            self.radio_at = self.t + self.radio.uniform(0.8, 2.5)
            if self.radio.random() < 0.5:
                self.note(0.2, 1000.0, BEEP, 0.12,
                          pan=self.radio.uniform(-1, 1))
            else:
                for j in range(self.radio.randint(2, 4)):
                    self.note(0.07, self.radio.choice((330.0, 392.0, 494.0)),
                              RADIO, 0.2, at=self.t + 0.09 * j)

    def other(self) -> Optional[Tuple[float, float, float]]:
        """The other forklift at work, (x, z, heading), if there is one."""
        if not self.level.busy:
            return None
        u = (self.t * 0.09) % 2.0
        x = -WIDE + 2 * WIDE * (u if u < 1 else 2 - u)
        return x, 1.2 * math.sin(self.t * 0.7), \
            math.pi / 2 if u < 1 else -math.pi / 2


def act(run: Run, port: int) -> None:
    if port < H.PRESS:
        run.hand.move(port)
    elif port == H.PRESS:
        run.press()
    elif port == H.RELEASE:
        run.release()


# --- the reference ------------------------------------------------------------------

def _drive(run: Run, x: float, z: float, close: float) -> Optional[int]:
    dx, dz = x - run.p[0], z - run.p[1]
    d = math.hypot(dx, dz)
    if d <= close:
        return None
    fx, fz = run.forward()
    ahead = (dx * fx + dz * fz) / d
    side = (dx * -fz + dz * fx) / d          # to the forklift's right
    off = math.degrees(math.atan2(side, ahead))
    if abs(off) > 35.0:
        return RIGHT if off > 0 else LEFT
    if abs(off) > 7.0:
        return FWD_RIGHT if off > 0 else FWD_LEFT
    return FWD


def autopilot(run: Run) -> List[int]:
    """Serve the truck that leaves first: fetch what it still wants,
    load it, send it. One port a step."""
    if run.result is not None:
        return []
    hand, dock = run.hand, run.dock
    waiting = sorted(run.waiting(), key=lambda k: dock.trucks[k].leave)
    if not waiting:
        return [H.RELEASE] if hand.down else []
    k = waiting[0]
    truck = dock.trucks[k]
    see = run.view().see

    def point(at: Vec, tol: float = 5.0) -> Optional[int]:
        q = see(at)
        return None if q is None else H.toward(hand, q[0], q[1], tol=tol)

    if run.complete(k):
        if run.drag is not None:
            return [H.RELEASE]
        if not hand.down:
            move = point(run.lamp(k))
            return [move] if move is not None else [H.PRESS]
        return [H.RELEASE]
    open_needs = [n for j, n in enumerate(truck.needs) if not run.met[k][j]]
    # Which of the carried crates this truck will take, and what is
    # still to fetch.
    left, useful = list(open_needs), 0
    for kind in run.carried + ([run.drag[1]] if run.drag else []):
        for n in left:
            if n.met_by(kind):
                left.remove(n)
                useful += 1
                break
    if run.drag is not None:
        where = run.drag[0]
        if where == 'shelf':
            move = point(run.fork())
            return [move] if move is not None else [H.RELEASE]
        move = point(run.bed(k), tol=8.0)
        return [move] if move is not None else [H.RELEASE]
    if hand.down:
        return [H.RELEASE]
    if left and len(run.carried) < CARRY:
        need = left[0]
        s = next(j for j, kind in enumerate(dock.shelf) if need.met_by(kind))
        sx = run.slot(s)[0]
        port = _drive(run, sx, SHELF_Z + 2.4, 1.0)
        if port is not None:
            return [port]
        if not run.stocked(s):
            return []
        move = point(run.slot(s))
        return [move] if move is not None else [H.PRESS]
    b = run.bed(k)
    port = _drive(run, b[0], TRUCK_Z - 2.6, 1.2)
    if port is not None:
        return [port]
    move = point(run.fork())
    return [move] if move is not None else [H.PRESS]


def play(dock: Dock, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(dock), pilot, EVENTS, act, dt)
