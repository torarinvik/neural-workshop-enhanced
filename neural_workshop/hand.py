# -*- coding: utf-8 -*-
"""A hand on the screen: the pointer that clocked tasks share.

The tasks built on this take the mouse and the keyboard together. The
screen they are played on is always 1000 by 640 units, whatever the
window is, and the pointer is drawn on it, so what a player does with a
mouse and what an agent does with ports write the same two numbers and
the same button, and the picture shows them either way.

Ports 0-11 move the pointer: up, down, left, right, each by a long, a
medium or a short step (80, 20 and 5 units); port 12 presses the button
and port 13 lets it go. A press and a release in one place is a click;
with moves between them, a drag. A task's keys come after, from port 14.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Callable, List, Optional, Tuple

from .drshape import Note
from .ui.lens import Lens                       # noqa: F401  (pure maths)

Vec = Tuple[float, float, float]

W, H = 1000.0, 640.0
STEPS = (80.0, 20.0, 5.0)
DIRS = ((0, 1), (0, -1), (-1, 0), (1, 0))       # up, down, left, right
PRESS, RELEASE = 12, 13
KEYS = 14                                       # the first key port
HAND_EVENTS = tuple(range(KEYS))


class Hand:
    """Where the pointer is and whether its button is down."""

    def __init__(self, x: float = W / 2, y: float = H / 2) -> None:
        self.x, self.y = x, y
        self.down = False

    def to(self, x: float, y: float) -> None:
        self.x = max(0.0, min(W, float(x)))
        self.y = max(0.0, min(H, float(y)))

    def move(self, port: int) -> None:
        dx, dy = DIRS[port // 3]
        s = STEPS[port % 3]
        self.to(self.x + dx * s, self.y + dy * s)


def toward(hand: Hand, x: float, y: float, tol: float = 3.0
           ) -> Optional[int]:
    """The move port that takes the pointer nearest (x, y), or None when
    it is within *tol* on both axes."""
    dx, dy = x - hand.x, y - hand.y
    if max(abs(dx), abs(dy)) <= tol:
        return None
    if abs(dx) >= abs(dy):
        d, way = abs(dx), (3 if dx > 0 else 2)
    else:
        d, way = abs(dy), (0 if dy > 0 else 1)
    size = 2
    for k, s in enumerate(STEPS):
        if s <= d + tol:
            size = k
            break
    return way * 3 + size


def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a: Vec) -> float:
    return math.sqrt(dot(a, a))


def unit(a: Vec) -> Vec:
    d = norm(a) or 1.0
    return (a[0] / d, a[1] / d, a[2] / d)


def lens(eye: Vec, look: Vec, focal: float = 900.0,
         cx: float = W / 2, cy: float = H / 2) -> Lens:
    """A camera onto the 1000 by 640 screen."""
    return Lens(eye, look, focal, cx, cy)


def on_plane(view: Lens, x: float, y: float, point: Vec, normal: Vec
             ) -> Optional[Vec]:
    """Where the screen point (x, y) meets a plane in the world."""
    d = view.ray(x, y)
    den = dot(d, normal)
    if abs(den) < 1e-6:
        return None
    s = dot(sub(point, view.eye), normal) / den
    if s <= 0:
        return None
    return add(view.eye, scale(d, s))


class HandRun:
    """What every run on this screen keeps: the clock, the pointer, the
    sound so far, and keys that count as held for a moment after they
    are sent (an agent sends one port a step, so a key and a click
    cannot arrive together)."""

    LATCH = 0.25

    def __init__(self, seconds: float) -> None:
        self.t = 0.0
        self.end = seconds
        self.hand = Hand()
        self.notes: List[Note] = []
        self.seed = 0
        self.held = {}                          # key port -> held until
        self.result: Optional[Tuple[bool, str]] = None

    def note(self, dur: float, freq: float, voice: int, gain: float = 0.5,
             pan: float = 0.0, bright: float = 0.8,
             at: Optional[float] = None) -> None:
        self.seed += 1
        pan = max(-1.0, min(1.0, pan))
        t = self.t if at is None else at
        n = Note(t, dur, freq, pan, pan, gain, gain, bright, voice,
                 self.seed, -1, 0.0)
        k = len(self.notes)
        while k > 0 and self.notes[k - 1].t > t:
            k -= 1
        self.notes.insert(k, n)

    def hold(self, port: int) -> None:
        self.held[port] = self.t + self.LATCH

    def holding(self, port: int) -> bool:
        return self.held.get(port, -1.0) >= self.t

    def controls(self, control) -> None:
        """Latch whatever controls are on this step."""
        if control is None:
            return
        for port in (control if isinstance(control, (set, frozenset, list,
                                                     tuple)) else (control,)):
            self.hold(port)


def play(run, pilot: Callable, events: Tuple[int, ...], act: Callable,
         dt: float = 1 / 60.0) -> Tuple[bool, str]:
    """Play a run with *pilot*, one port a step as the agent has."""
    while run.result is None:
        ports = pilot(run)
        port = ports[0] if ports else None
        if port is not None and port in events:
            act(run, port)
            port = None
        run.step(dt, port)
    return run.result


def act(run, port: int) -> None:
    """The usual ports: 0-11 move, 12 presses, 13 lets go, and anything
    after goes to the run's ``key``."""
    if port < PRESS:
        run.hand.move(port)
    elif port == PRESS:
        run.press()
    elif port == RELEASE:
        run.release()
    else:
        run.key(port)


def deal(module, rung: int, seed: Optional[int] = None, rng=None,
         tries: int = 80):
    """A round of *module* at *rung* that its reference player finishes."""
    import random
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = module.grade(rung)
    for _try in range(tries):
        dealt = module.build(level, random.Random(draw.getrandbits(32)))
        if dealt is not None and module.play(dealt)[0]:
            return dealt
    raise RuntimeError('%s: no round for rung %d' % (module.__name__, rung))
