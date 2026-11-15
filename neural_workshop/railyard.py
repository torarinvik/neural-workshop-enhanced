# -*- coding: utf-8 -*-
"""Rail Yard: route every train to its own station, in real time.

Trains leave a tunnel portal and run through a tree of points to a row
of stations; each train is painted its station's colour. The player
throws points and works the portal signals. Three rules make it hard:

* **points take time to throw**, and points that are moving when a
  train reaches them derail it -- so a set of points must be thrown
  after one train has cleared it and before the next arrives;
* **two trains closer than a train's length on one stretch of track
  collide** -- a fast train catching a slow one, or two trains meeting
  at the junction where two portals' lines merge;
* **the signals hold trains in the tunnel**, which is the only way to
  make room -- and every second held is a second off the clock.

The ladder:

* rungs 1-3: one portal, two stations, slow trains well apart;
* rungs 4-6: four stations;
* rungs 7-9: the points take a second to throw;
* rungs 10-12: eight stations, trains closer together;
* rungs 13-15: a second portal, merging into the first line;
* rungs 16-19: express trains, half again as fast, catch up;
* from rung 20: sixteen stations, and faster, denser traffic every
  rung.

A trial passes with no collision, no derailment, and every train at its
own station before the time runs out (one wrong station forgiven below
rung 10). Clocked: the trains run.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from .i18n import _

WORLD_W, WORLD_H = 160.0, 100.0
#: Two trains on one stretch closer than this collide (world units).
GAP = 7.0
#: A drawn train's length.
LENGTH = 5.0
MOST_SWITCHES = 15
MOST_PORTALS = 2
#: Agent ports: one per set of points, then one per portal signal.
SIGNAL_PORT = MOST_SWITCHES
PORTS = MOST_SWITCHES + MOST_PORTALS


class Grade(NamedTuple):
    rung: int
    depth: int
    portals: int
    trains: int
    headway: float
    speed: float
    throw: float
    express: float
    forgive: int


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    depth = 1 if r < 4 else (2 if r < 10 else (3 if r < 20 else 4))
    return Grade(
        rung=r, depth=depth,
        portals=2 if r >= 13 else 1,
        trains=(5 if r < 4 else 7 if r < 10 else 10 if r < 20
                else min(18, 12 + top)),
        headway=(9.0 if r < 4 else 7.0 if r < 7 else 6.0 if r < 10
                 else 5.0 if r < 20 else max(2.6, 4.2 - 0.15 * top)),
        speed=(14.0 if r < 4 else 16.0 if r < 10 else 18.0 if r < 20
               else min(26.0, 20.0 + 0.6 * top)),
        throw=0.0 if r < 7 else (1.0 if r < 20 else min(1.6, 1.1 + 0.05 * top)),
        express=0.0 if r < 16 else 0.3,
        forgive=1 if r < 10 else 0)


class Node(NamedTuple):
    kind: str            # 'portal', 'merge', 'switch', 'station'
    x: float
    y: float
    #: Station number for a station, switch number for a switch.
    index: int


class Segment(NamedTuple):
    start: int
    end: int
    points: Tuple[Tuple[float, float], ...]
    length: float


class Layout(NamedTuple):
    nodes: Tuple[Node, ...]
    segments: Tuple[Segment, ...]
    #: Out segments of each node: one, or two for a switch (0 and 1).
    out: Tuple[Tuple[int, ...], ...]
    #: The first segment from each portal.
    starts: Tuple[int, ...]
    #: Node of each switch and of each station, by number.
    switch_nodes: Tuple[int, ...]
    station_nodes: Tuple[int, ...]


class TrainPlan(NamedTuple):
    portal: int
    station: int
    due: float
    speed: float
    express: bool


class Yard(NamedTuple):
    rung: int
    level: Grade
    layout: Layout
    plans: Tuple[TrainPlan, ...]
    seconds: float


def _polyline(a: Tuple[float, float], b: Tuple[float, float]
              ) -> Tuple[Tuple[float, float], ...]:
    """Straight out of *a*, a slant, straight into *b* -- track shape."""
    if abs(a[1] - b[1]) < 1e-6:
        return (a, b)
    dx = b[0] - a[0]
    return (a, (a[0] + dx * 0.25, a[1]), (a[0] + dx * 0.75, b[1]), b)


def _length(points: Sequence[Tuple[float, float]]) -> float:
    return sum(math.hypot(q[0] - p[0], q[1] - p[1])
               for p, q in zip(points, points[1:]))


def layout(depth: int, portals: int) -> Layout:
    """The track: portals, a merge when there are two, a binary tree of
    points, and 2**depth stations down the right-hand side."""
    nodes: List[Node] = []
    segments: List[Segment] = []
    stations = 2 ** depth
    margin = 8.0
    span = WORLD_H - 2 * margin

    def leaf_y(i: int) -> float:
        return WORLD_H - margin - span * (i + 0.5) / stations

    x_root = 36.0
    x_station = WORLD_W - 12.0
    step = (x_station - x_root) / depth
    switch_nodes: List[int] = []
    # Heap-numbered switches 1 .. 2**depth - 1; children 2k, 2k+1.
    heap_node: Dict[int, int] = {}
    for k in range(1, stations):
        level_k = int(math.log2(k))
        first = k - 2 ** level_k
        width = stations // (2 ** level_k)
        lo, hi = first * width, (first + 1) * width - 1
        y = (leaf_y(lo) + leaf_y(hi)) / 2
        heap_node[k] = len(nodes)
        switch_nodes.append(len(nodes))
        nodes.append(Node('switch', x_root + level_k * step, y, k - 1))
    station_nodes: List[int] = []
    for i in range(stations):
        station_nodes.append(len(nodes))
        nodes.append(Node('station', x_station, leaf_y(i), i))
    out: List[List[int]] = [[] for _n in nodes]

    def connect(a: int, b: int) -> int:
        pa, pb = (nodes[a].x, nodes[a].y), (nodes[b].x, nodes[b].y)
        pts = _polyline(pa, pb)
        segments.append(Segment(a, b, pts, _length(pts)))
        out[a].append(len(segments) - 1)
        return len(segments) - 1

    for k in range(1, stations):
        for child in (2 * k, 2 * k + 1):
            target = heap_node[child] if child < stations else \
                station_nodes[child - stations]
            connect(heap_node[k], target)
    root = heap_node[1]
    root_y = nodes[root].y
    starts: List[int] = []
    if portals == 1:
        p = len(nodes)
        nodes.append(Node('portal', 6.0, root_y, 0))
        out.append([])
        starts.append(connect(p, root))
    else:
        m = len(nodes)
        nodes.append(Node('merge', 22.0, root_y, 0))
        out.append([])
        connect(m, root)
        for j, dy in enumerate((16.0, -16.0)):
            p = len(nodes)
            nodes.append(Node('portal', 4.0, root_y + dy, j))
            out.append([])
            starts.append(connect(p, m))
    return Layout(tuple(nodes), tuple(segments), tuple(tuple(o) for o in out),
                  tuple(starts), tuple(switch_nodes), tuple(station_nodes))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Yard:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    lay = layout(level.depth, level.portals)
    stations = 2 ** level.depth
    plans: List[TrainPlan] = []
    for portal in range(level.portals):
        t = draw.uniform(1.0, 3.0) + portal * level.headway / 2
        count = level.trains // level.portals + (
            1 if portal < level.trains % level.portals else 0)
        for _k in range(count):
            express = draw.random() < level.express
            plans.append(TrainPlan(
                portal, draw.randrange(stations), round(t, 2),
                level.speed * (1.5 if express else 1.0), express))
            t += level.headway * draw.uniform(0.8, 1.25) * level.portals
    plans.sort(key=lambda p: p.due)
    last = max(p.due for p in plans)
    longest = max(_route_length(lay, p) for p in plans)
    seconds = last + 2.2 * longest / level.speed + 12.0
    return Yard(level.rung, level, lay, tuple(plans), round(seconds, 1))


def route(lay: Layout, portal: int, station: int) -> List[Tuple[int, int]]:
    """(segment, switch setting needed at its end or -1) from a portal
    to a station."""
    target = lay.station_nodes[station]
    seg = lay.starts[portal]
    path: List[Tuple[int, int]] = []
    for _guard in range(64):
        end = lay.segments[seg].end
        node = lay.nodes[end]
        if end == target:
            path.append((seg, -1))
            return path
        if node.kind == 'switch':
            for way, nxt in enumerate(lay.out[end]):
                if _reaches(lay, nxt, target):
                    path.append((seg, way))
                    seg = nxt
                    break
        else:
            path.append((seg, -1))
            seg = lay.out[end][0]
    raise ValueError('no route')


def _reaches(lay: Layout, seg: int, target: int) -> bool:
    end = lay.segments[seg].end
    if end == target:
        return True
    return any(_reaches(lay, nxt, target) for nxt in lay.out[end])


def _route_length(lay: Layout, plan: TrainPlan) -> float:
    return sum(lay.segments[s].length
               for s, _w in route(lay, plan.portal, plan.station))


class Train:
    def __init__(self, number: int, plan: TrainPlan) -> None:
        self.number = number
        self.plan = plan
        self.state = 'due'          # due, waiting, running, right, wrong, lost
        self.segment = -1
        self.distance = 0.0
        self.left_at = 0.0

    @property
    def done(self) -> bool:
        return self.state in ('right', 'wrong', 'lost')


class Points:
    """One set of points: where it lies, and where it is going."""

    def __init__(self) -> None:
        self.way = 0
        self.target = 0
        self.moving = 0.0           # seconds of throw still to go


class Run:
    """The yard in motion."""

    def __init__(self, yard: Yard) -> None:
        self.yard = yard
        lay = yard.layout
        self.t = 0.0
        self.trains = [Train(i, p) for i, p in enumerate(yard.plans)]
        self.points = [Points() for _s in lay.switch_nodes]
        self.signals = [True] * yard.level.portals
        self.result: Optional[Tuple[bool, str]] = None
        self.crash: Optional[Tuple[float, float]] = None
        self.events: List[Tuple[float, str, int]] = []

    # --- controls --------------------------------------------------------

    def throw(self, k: int) -> None:
        if not 0 <= k < len(self.points) or self.result is not None:
            return
        p = self.points[k]
        p.target = 1 - p.target
        if self.yard.level.throw <= 0:
            p.way = p.target
            p.moving = 0.0
        elif p.target != p.way:
            p.moving = self.yard.level.throw
        else:
            p.moving = 0.0          # thrown back before it got there

    def signal(self, k: int) -> None:
        if 0 <= k < len(self.signals) and self.result is None:
            self.signals[k] = not self.signals[k]

    # --- the clock -------------------------------------------------------

    def step(self, dt: float) -> None:
        if self.result is not None:
            return
        self.t += dt
        lay = self.yard.layout
        for p in self.points:
            if p.moving > 0:
                p.moving -= dt
                if p.moving <= 0:
                    p.moving = 0.0
                    p.way = p.target
        for train in self.trains:
            if train.state == 'due' and self.t >= train.plan.due:
                train.state = 'waiting'
        for portal in range(len(self.signals)):
            if not self.signals[portal]:
                continue
            start = lay.starts[portal]
            if any(o.state == 'running' and o.segment == start
                   and o.distance < GAP + 1.0 for o in self.trains):
                continue
            queue = [o for o in self.trains if o.state == 'waiting'
                     and o.plan.portal == portal]
            if queue:
                o = min(queue, key=lambda o: o.plan.due)
                o.state = 'running'
                o.segment = start
                o.distance = 0.0
                o.left_at = self.t
        for train in self.trains:
            if train.state == 'running':
                self._advance(train, dt)
                if self.result is not None:
                    return
        self._collisions()
        if self.result is None:
            self._check_end()

    def _advance(self, train: Train, dt: float) -> None:
        lay = self.yard.layout
        train.distance += train.plan.speed * dt
        while train.state == 'running':
            seg = lay.segments[train.segment]
            if train.distance < seg.length:
                return
            train.distance -= seg.length
            node = lay.nodes[seg.end]
            if node.kind == 'station':
                right = node.index == train.plan.station
                train.state = 'right' if right else 'wrong'
                self.events.append((self.t, train.state, train.number))
                return
            if node.kind == 'switch':
                p = self.points[node.index]
                if p.moving > 0:
                    train.state = 'lost'
                    self.crash = (node.x, node.y)
                    self.result = (False, _('Train %d derailed on points '
                                            'that were still moving')
                                   % (train.number + 1))
                    return
                train.segment = lay.out[seg.end][p.way]
            else:
                train.segment = lay.out[seg.end][0]

    def _collisions(self) -> None:
        running = [o for o in self.trains if o.state == 'running']
        for i, a in enumerate(running):
            for b in running[i + 1:]:
                if a.segment == b.segment and \
                        abs(a.distance - b.distance) < GAP:
                    a.state = b.state = 'lost'
                    self.crash = position(self.yard.layout, a.segment,
                                          max(a.distance, b.distance))[:2]
                    self.result = (False, _('Trains %d and %d collided')
                                   % (a.number + 1, b.number + 1))
                    return

    def _check_end(self) -> None:
        trains = self.trains
        if all(o.done for o in trains) or self.t >= self.yard.seconds:
            right = sum(1 for o in trains if o.state == 'right')
            need = len(trains) - self.yard.level.forgive
            missed = len(trains) - sum(1 for o in trains if o.done)
            ok = right >= need
            if missed:
                words = _('Time: %d of %d trains home') % (right,
                                                          len(trains))
            else:
                words = _('%d of %d trains at their own station') % (
                    right, len(trains))
            self.result = (ok, words)

    def right_count(self) -> int:
        return sum(1 for o in self.trains if o.state == 'right')


def position(lay: Layout, segment: int, distance: float
             ) -> Tuple[float, float, float]:
    """x, y and heading (radians) of a point *distance* along a segment."""
    pts = lay.segments[segment].points
    left = distance
    for p, q in zip(pts, pts[1:]):
        piece = math.hypot(q[0] - p[0], q[1] - p[1])
        if left <= piece or q is pts[-1]:
            f = 0.0 if piece == 0 else max(0.0, min(1.0, left / piece))
            return (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f,
                    math.atan2(q[1] - p[1], q[0] - p[0]))
        left -= piece
    p, q = pts[-2], pts[-1]
    return q[0], q[1], math.atan2(q[1] - p[1], q[0] - p[0])


# --- a reference controller ----------------------------------------------

def _etas(run: Run, train: Train, depart: float
          ) -> List[Tuple[int, float, int]]:
    """(node, time the train reaches it, way it needs there) along its
    route, from the moment it would depart (or where it is now)."""
    lay = run.yard.layout
    path = route(lay, train.plan.portal, train.plan.station)
    out = []
    if train.state == 'running':
        t = run.t
        idx = next((i for i, (s, _w) in enumerate(path)
                    if s == train.segment), None)
        if idx is None:
            return []               # off its route: nothing to plan for
        travelled = -train.distance
    else:
        t = depart
        idx = 0
        travelled = 0.0
    for s, way in path[idx:]:
        travelled += lay.segments[s].length
        out.append((lay.segments[s].end,
                    t + travelled / train.plan.speed, way))
    return out


def autopilot(run: Run) -> List[int]:
    """Ports a careful dispatcher sends now: throws each set of points
    for the next train that needs it, and lets a train out of its
    tunnel only when its whole route is clear of every other train's,
    with time to throw the points between them."""
    yard = run.yard
    lay = yard.layout
    level = yard.level
    spacing = (GAP + 3.0) / min(p.speed for p in yard.plans)
    throw = level.throw + 0.35
    ports: List[int] = []
    committed = [o for o in run.trains if o.state == 'running']
    etas = {o.number: _etas(run, o, run.t) for o in committed}
    # Points: lie right for the next train to reach them.
    for k, node in enumerate(lay.switch_nodes):
        p = run.points[k]
        nxt = None
        for o in committed:
            for n, when, way in etas[o.number]:
                if n == node and when >= run.t - 1e-6:
                    if nxt is None or when < nxt[0]:
                        nxt = (when, way)
        if nxt is None:
            # No train on the way: lie right for the next one waiting.
            for portal in range(level.portals):
                queue = [o for o in run.trains if o.state == 'waiting'
                         and o.plan.portal == portal]
                if not queue:
                    continue
                head = min(queue, key=lambda o: o.plan.due)
                for n, when, way in _etas(run, head, run.t):
                    if n == node and (nxt is None or when < nxt[0]):
                        nxt = (when, way)
            if nxt is not None and p.target != nxt[1] and p.moving <= 0:
                ports.append(k)
            continue
        if p.target != nxt[1] and nxt[0] - run.t > level.throw + 0.05:
            ports.append(k)
    # Signals: open only for a train whose route is clear.
    for portal in range(level.portals):
        queue = [o for o in run.trains if o.state == 'waiting'
                 and o.plan.portal == portal]
        start = lay.starts[portal]
        blocked_start = any(o.state == 'running' and o.segment == start
                            and o.distance < GAP + 1.0 for o in run.trains)
        want = False
        if queue and not blocked_start:
            cand = min(queue, key=lambda o: o.plan.due)
            mine = _etas(run, cand, run.t + 0.05)
            want = True
            # Points it needs thrown must have time to get there.
            for n, when, way in mine:
                node = lay.nodes[n]
                if node.kind == 'switch' and way >= 0 and \
                        run.points[node.index].target != way and \
                        when - run.t < level.throw + 0.4:
                    want = False
                if node.kind == 'switch' and \
                        when - run.t < run.points[node.index].moving + 0.4:
                    want = False
            for o in committed:
                theirs = {n: (w, way) for n, w, way in etas[o.number]}
                order = None
                for n, when, way in mine:
                    if n not in theirs:
                        continue
                    w, their_way = theirs[n]
                    gap = when - w
                    need = spacing
                    if way != their_way and way >= 0 and their_way >= 0:
                        need = max(need, throw)
                    if abs(gap) < need:
                        want = False
                    sign = gap > 0
                    if order is not None and sign != order:
                        want = False        # one would overtake the other
                    order = sign
                if not want:
                    break
            if want:
                committed.append(cand)
                etas[cand.number] = mine
        if want != run.signals[portal]:
            ports.append(SIGNAL_PORT + portal)
    return ports


def play(yard: Yard, pilot=autopilot, dt: float = 1 / 30.0
         ) -> Tuple[bool, str]:
    run = Run(yard)
    while run.result is None:
        for port in pilot(run):
            if port < SIGNAL_PORT:
                run.throw(port)
            else:
                run.signal(port - SIGNAL_PORT)
        run.step(dt)
    return run.result
