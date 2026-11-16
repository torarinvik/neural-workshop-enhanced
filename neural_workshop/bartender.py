# -*- coding: utf-8 -*-
"""Bartender: pour what was ordered and slide it down the bar.

You stand at the near end of a long bar with bottles on the shelf
behind you and a glass in front of you. Customers sit along the bar
and their orders come up in words: "Seat 3: a double red on the
rocks."

Pour by dragging a bottle over the glass and holding it there: the
glass fills while the bottle is over it, and sings a higher note the
fuller it gets. A single is half a glass, a double a full one; pour
over the brim and it is spilt. I puts ice in. Then send it: take hold
of the glass, draw it back, push it forward and let go -- it slides on
four times as far as you pushed it. It has to stop in front of the
customer who ordered it. Too long a push and it goes off the end.

A wrong drink, a spill, a glass off the end or a customer kept waiting
too long is a strike; three and you are out.

The ladder:

* rungs 1-3: one customer, two bottles, singles;
* rungs 4-6: two customers; doubles;
* rungs 7-9: three customers; ice;
* rungs 10-12: the glass is pewter -- the level has to be heard; only
  two strikes;
* rungs 13-15: four customers, and regulars who ask for "the usual":
  what that hat had last time;
* rungs 16-19: five customers, less patient;
* from rung 20: more customers, more bottles, less patience.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .hand import Vec
from .i18n import _

ICE = H.KEYS
PORTS = H.KEYS + 1
EVENTS = tuple(range(PORTS))
DRINKS = (_('red'), _('green'), _('blue'), _('amber'), _('violet'))
HATS = (_('black'), _('white'), _('brown'), _('grey'), _('green'))
TOP = 1.0                      # the height of the bar top
STATION = (-2.2, 1.2)          # how far the glass may be carried
HOME = 0.0                     # where a fresh glass stands
SEATS = tuple(3.0 + 1.5 * k for k in range(5))
END = 10.4
SLIDE = 4.0                    # how far a glass slides for its push
POUR = 0.4                     # glasses a second
SINGLE, DOUBLE = (0.38, 0.62), (0.78, 1.0)
NEAR, OVER = 44.0, 50.0        # grabbing, and holding a bottle over
VIEW = H.lens((3.2, 5.2, 9.5), (4.0, 0.9, 0.0), 640.0, 500.0, 300.0)
POURING, DING, CRASH, SLIDING, CLINK, GRUMBLE = range(6)
PATCHES = ('sine', 'bell', 'metal', 'pad', 'glass', 'growl')


class Grade(NamedTuple):
    rung: int
    customers: int
    bottles: int
    doubles: bool
    ice: bool
    pewter: bool
    usual: bool
    strikes: int
    patience: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        customers=(1 if r < 4 else 2 if r < 7 else 3 if r < 13 else 4
                   if r < 16 else 5 if r < 20 else 6 + top // 3),
        bottles=2 if r < 4 else 3 if r < 10 else 4 if r < 20 else 5,
        doubles=r >= 4, ice=r >= 7, pewter=r >= 10, usual=r >= 13,
        strikes=3 if r < 10 else 2,
        patience=(30.0 if r < 4 else 26.0 if r < 10 else 22.0 if r < 16
                  else 18.0 if r < 20 else max(10.0, 17.0 - 0.2 * top)))


class Order(NamedTuple):
    seat: int
    hat: int
    drink: int
    double: bool
    ice: bool
    arrive: float
    leave: float
    text: str


class Night(NamedTuple):
    level: Grade
    orders: Tuple[Order, ...]
    seed: int


def build(level: Grade, draw: random.Random) -> Optional[Night]:
    orders: List[Order] = []
    usual = {}
    t = 1.0
    for k in range(level.customers):
        seat = draw.randrange(len(SEATS))
        hat = draw.randrange(len(HATS))
        if hat in usual and level.usual:
            drink, double, ice = usual[hat]
            text = _('Seat %d, %s hat: the usual.') % (seat + 1, HATS[hat])
        else:
            drink = draw.randrange(level.bottles)
            double = level.doubles and draw.random() < 0.5
            ice = level.ice and draw.random() < 0.5
            usual[hat] = (drink, double, ice)
            what = (_('a double %s') if double else _('a %s')) % DRINKS[drink]
            if ice:
                what += _(' on the rocks')
            text = (_('Seat %d, %s hat: %s.') % (seat + 1, HATS[hat], what)
                    if level.usual else _('Seat %d: %s.') % (seat + 1, what))
        orders.append(Order(seat, hat, drink, double, ice, t,
                            t + level.patience, text))
        t += level.patience * 0.75
    return Night(level, tuple(orders), draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Night:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng)


def bottle_at(k: int) -> Vec:
    return (-1.6 + 0.75 * k, 1.9, -1.3)


class Run(H.HandRun):
    def __init__(self, night: Night) -> None:
        super().__init__(night.orders[-1].leave + 1.0)
        self.night, self.level = night, night.level
        self.served = [False] * len(night.orders)
        self.gone = [False] * len(night.orders)
        self.strikes = 0
        self.glass_x = HOME
        self.level_in = 0.0
        self.drink = -1                # what is in the glass; -2 a mix
        self.ice = False
        self.held: Optional[Tuple[str, int]] = None   # ('bottle', k) or
        #                                                ('glass', 0)
        self.trail: List[Tuple[float, float]] = []    # (t, x) of the glass
        self.sliding: Optional[Tuple[float, float]] = None   # to, speed
        self.pour_at = 0.0

    # --- where things are
    def glass(self) -> Vec:
        return (self.glass_x, TOP + 0.3, 0.4)

    def waiting(self) -> List[int]:
        return [k for k, o in enumerate(self.night.orders)
                if o.arrive <= self.t and not self.served[k]
                and not self.gone[k]]

    def _off(self, point: Vec) -> float:
        q = VIEW.see(point)
        return 1e9 if q is None else math.hypot(self.hand.x - q[0],
                                                self.hand.y - q[1])

    def bar_x(self) -> Optional[float]:
        """Where along the bar the pointer is."""
        p = H.on_plane(VIEW, self.hand.x, self.hand.y, (0.0, TOP + 0.3, 0.4),
                       (0.0, 0.0, 1.0))
        return None if p is None else p[0]

    def _strike(self, why: str) -> None:
        self.strikes += 1
        self.note(0.3, 100.0, GRUMBLE, 0.5)
        if self.strikes >= self.level.strikes:
            self.result = (False, why)

    def _fresh(self) -> None:
        self.glass_x, self.level_in, self.drink, self.ice = HOME, 0.0, -1, \
            False
        self.sliding = None
        self.trail = []

    # --- the hand
    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        if self.sliding is not None:
            return
        picks = [(self._off(bottle_at(k)), ('bottle', k))
                 for k in range(self.level.bottles)]
        picks.append((self._off(self.glass()), ('glass', 0)))
        d, what = min(picks)
        if d <= NEAR:
            self.held = what
            self.trail = []

    def release(self) -> None:
        if not self.hand.down:
            return
        self.hand.down = False
        held, self.held = self.held, None
        if self.result is not None or held is None or held[0] != 'glass':
            return
        push = self.glass_x - self.was()
        if push > 0.05:
            self.sliding = (self.glass_x + push * SLIDE, 3.0 + 3.0 * push)
            self.note(0.4, 200.0, SLIDING, 0.3)

    def was(self) -> float:
        """How far back the held glass has been drawn."""
        return min([x for _t, x in self.trail] or [self.glass_x])

    def key(self, port: int) -> None:
        if self.result is None and port == ICE and self.sliding is None:
            self.ice = not self.ice
            self.note(0.06, 1500.0, CLINK, 0.4)

    # --- the clock
    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        held = self.held
        if held is not None and held[0] == 'glass':
            x = self.bar_x()
            if x is not None:
                self.glass_x = max(STATION[0], min(STATION[1], x))
            self.trail = [(self.t, min(self.glass_x, self.was()))]
        elif held is not None and self.sliding is None and \
                self._off(self.glass()) <= OVER:
            k = held[1]
            self.drink = k if self.drink in (-1, k) else -2
            self.level_in += POUR * dt
            if self.t >= self.pour_at:
                self.pour_at = self.t + 0.09
                self.note(0.1, 300.0 * 2 ** (1.5 * self.level_in), POURING,
                          0.35)
            if self.level_in > 1.04:
                self._fresh()
                self._strike(_('Too much spilt'))
        if self.sliding is not None:
            to, speed = self.sliding
            self.glass_x = min(to, self.glass_x + max(2.0, speed) * 2.0 * dt)
            if self.glass_x >= END:
                self.note(0.5, 900.0, CRASH, 0.6)
                self._fresh()
                self._strike(_('Too many glasses on the floor'))
            elif self.glass_x >= to:
                self._arrive()
        for k, o in enumerate(self.night.orders):
            if not self.served[k] and not self.gone[k] and self.t >= o.leave:
                self.gone[k] = True
                self._strike(_('Too many customers walked out'))
        if self.result is None and all(
                a or b for a, b in zip(self.served, self.gone)):
            self.result = ((True, _('Last orders: a good night'))
                           if all(self.served) else
                           (False, _('Not everyone got their drink')))

    def _arrive(self) -> None:
        x = self.glass_x
        got = (self.drink, self.level_in, self.ice)
        self._fresh()
        for k in self.waiting():
            o = self.night.orders[k]
            if abs(SEATS[o.seat] - x) <= 0.55:
                lo, hi = DOUBLE if o.double else SINGLE
                if got[0] == o.drink and lo <= got[1] <= hi and \
                        got[2] == o.ice:
                    self.served[k] = True
                    self.note(0.3, 880.0, DING, 0.5)
                else:
                    self._strike(_('Too many wrong drinks'))
                return
        self._strike(_('Too many drinks sent to nobody'))


act = H.act


def autopilot(run: Run) -> List[int]:
    """Serve whoever leaves first: pour, ice, and send it just hard
    enough. One port a step."""
    if run.result is not None or run.sliding is not None:
        return [H.RELEASE] if run.hand.down and run.result is None else []
    hand = run.hand
    waiting = sorted(run.waiting(), key=lambda k: run.night.orders[k].leave)
    if not waiting:
        return [H.RELEASE] if hand.down else []
    o = run.night.orders[waiting[0]]
    lo, hi = DOUBLE if o.double else SINGLE
    want = (lo + hi) / 2

    def point(at: Vec, tol: float = 6.0) -> Optional[int]:
        q = VIEW.see(at)
        return H.toward(hand, q[0], q[1], tol=tol)

    held = run.held
    if run.level_in < want - 0.03:
        if held is not None and held != ('bottle', o.drink):
            return [H.RELEASE]
        if held is None:
            if hand.down:
                return [H.RELEASE]
            move = point(bottle_at(o.drink))
            return [move] if move is not None else [H.PRESS]
        move = point(run.glass(), tol=12.0)
        return [move] if move is not None else []
    if held is not None and held[0] == 'bottle':
        return [H.RELEASE]
    if run.ice != o.ice:
        return [ICE]
    if held is None:
        if hand.down:
            return [H.RELEASE]
        move = point(run.glass())
        return [move] if move is not None else [H.PRESS]
    # Holding the glass: back to the left, stand still, then push
    # until letting go now would stop it at the seat.
    start = STATION[0] + 0.1
    seat = SEATS[o.seat]
    a, b = VIEW.see((0.0, TOP + 0.3, 0.4)), VIEW.see((1.0, TOP + 0.3, 0.4))
    per = b[0] - a[0]                           # units a metre of bar
    x, was = run.glass_x, run.was()
    if x <= was + 1e-6:
        gap = (x - start) * per
        if gap > 12.0:
            return [2 * 3 + (0 if gap > 85 else 1 if gap > 22 else 2)]
    stop = x + (x - was) * SLIDE
    for size, units in enumerate(H.STEPS):       # the longest safe push
        if stop + units / per * (1.0 + SLIDE) <= seat + 0.2:
            return [3 * 3 + size]
    return [H.RELEASE]


def play(night: Night, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(night), pilot, EVENTS, act, dt)
