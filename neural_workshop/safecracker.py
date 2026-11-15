# -*- coding: utf-8 -*-
"""Safecracker: open a vault door by ear, by hand and by reading.

A vault door with three things on it. A dial, turned by dragging the
pointer round it: it ticks at every number and gives a low thunk as it
passes the number the next tumbler wants -- clockwise for the first,
back the other way for the second, and so on. Stop on the thunk and let
go and the tumbler sets. A word lock, typed on the keyboard: the answer
to the clue along the top, which may be a plain word, something to read
off the door, or a small riddle. And a handle, dragged down once both
locks are done. All of it before the alarm.

The ladder:

* rungs 1-3: one tumbler, a wide mark and a lamp that turns green on
  the number; the clue is the word itself;
* rungs 4-6: two tumblers, no lamp -- the thunk is all there is; the
  clue has to be read off the door (the colour of a lamp);
* rungs 7-9: three tumblers; the camera drifts; opposites to type;
* rungs 10-12: false thunks at a higher pitch, words backwards, and
  mistakes now count: three strikes sets off the alarm;
* rungs 13-15: the door swings on its hinge; things to count;
* rungs 16-19: four tumblers, a quieter thunk, clues in two parts;
* from rung 20: more tumblers, a finer mark, more false thunks, a wider
  swing and less time every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .hand import Vec
from .i18n import _

LETTER = H.KEYS                # ports 14-39 type A-Z
BACKSPACE = H.KEYS + 26
PORTS = H.KEYS + 27
EVENTS = tuple(range(PORTS))

NUMBERS = 40                   # round the dial
PER = 360.0 / NUMBERS
DIAL = (2.0, 2.5, 0.85)        # centre on the door, and radius
HANDLE = (3.45, 2.5)
THROW = 0.8                    # how far down the handle goes
DOOR = (4.0, 4.6)
LAMPS = ((0.45, 4.15), (3.55, 4.15))
TICK, THUNK, CLACK, KEY, BUZZ, RATTLE, OPEN = range(7)
PATCHES = ('wood', 'pluck', 'bell', 'glass', 'growl', 'metal', 'organ')

WORDS = ('OPEN', 'GOLD', 'SAFE', 'LOCK', 'DOOR', 'KEYS', 'COIN', 'RING',
         'VAULT', 'STEEL')
OPPOSITES = (('HOT', 'COLD'), ('UP', 'DOWN'), ('IN', 'OUT'),
             ('DAY', 'NIGHT'), ('OPEN', 'SHUT'), ('WET', 'DRY'),
             ('FAST', 'SLOW'), ('HIGH', 'LOW'))
COLOURS = ('RED', 'GREEN', 'BLUE', 'WHITE')
COUNTS = ('ZERO', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN',
          'EIGHT', 'NINE')


class Grade(NamedTuple):
    rung: int
    tumblers: int
    mark: float                # how near the number counts, in numbers
    glow: bool
    clue: Tuple[str, ...]      # the kinds of clue this rung may ask
    drift: float               # how far the camera wanders
    swing: float               # degrees the door swings
    decoys: int
    strict: bool
    thunk: float               # how loud the thunk is
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    tumblers = (1 if r < 4 else 2 if r < 7 else 3 if r < 16 else 4
                if r < 20 else 5 + top // 4)
    clue = (('word',) if r < 4 else ('lamp',) if r < 7 else
            ('lamp', 'opposite') if r < 10 else
            ('opposite', 'backwards') if r < 13 else
            ('backwards', 'count') if r < 16 else ('two',))
    return Grade(
        rung=r, tumblers=tumblers,
        mark=(1.3 if r < 4 else 1.0 if r < 10 else 0.8 if r < 16 else 0.6
              if r < 20 else max(0.4, 0.6 - 0.01 * top)),
        glow=r < 4, clue=clue,
        drift=0.0 if r < 7 else 0.8 if r < 20 else min(2.2, 1.0 + 0.05 * top),
        swing=0.0 if r < 13 else 10.0 if r < 20 else min(28.0, 12.0 + top),
        decoys=0 if r < 10 else 2 if r < 20 else min(10, 3 + top // 2),
        strict=r >= 10,
        thunk=0.8 if r < 16 else 0.55 if r < 20 else max(0.3,
                                                         0.5 - 0.01 * top),
        seconds=(14.0 + tumblers * (11.0 if r < 10 else 9.0 if r < 20
                                    else max(5.5, 8.5 - 0.1 * top))))


class Safe(NamedTuple):
    level: Grade
    combo: Tuple[int, ...]     # tumbler k wants combo[k], turning way(k)
    decoys: Tuple[int, ...]
    clue: str
    answer: str
    lamps: Tuple[int, int]     # colours of the two lamps
    bolts: int
    seed: int


def way(k: int) -> int:
    """Which way tumbler *k* is found: 1 clockwise, -1 back."""
    return 1 if k % 2 == 0 else -1


def _clue(level: Grade, draw: random.Random, lamps, bolts
          ) -> Tuple[str, str]:
    kind = draw.choice(level.clue)
    if kind == 'word':
        w = draw.choice(WORDS)
        return _('Type the word %s.') % w, w
    if kind == 'lamp':
        side = draw.randrange(2)
        return (_('Type the colour of the lamp on the %s.')
                % (_('left'), _('right'))[side]), COLOURS[lamps[side]]
    if kind == 'opposite':
        a, b = draw.choice(OPPOSITES)
        if draw.random() < 0.5:
            a, b = b, a
        return _('Type the opposite of %s.') % a, b
    if kind == 'backwards':
        w = draw.choice(WORDS)
        return _('Type %s backwards.') % w, w[::-1]
    if kind == 'count':
        return _('Type how many bolts the door has, as a word.'), \
            COUNTS[bolts]
    if draw.random() < 0.5:
        a, b = draw.choice(OPPOSITES)
        return _('Type the opposite of %s backwards.') % a, b[::-1]
    side = draw.randrange(2)
    return (_('Type the colour of the lamp on the %s backwards.')
            % (_('left'), _('right'))[side]), COLOURS[lamps[side]][::-1]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Safe:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _try in range(60):
        d = random.Random(draw.getrandbits(32))
        combo, at = [], 0
        for k in range(level.tumblers):
            at = (at + way(k) * d.randint(7, 30)) % NUMBERS
            combo.append(at)
        spare = [n for n in range(NUMBERS)
                 if all(min((n - c) % NUMBERS, (c - n) % NUMBERS) >= 4
                        for c in combo)]
        decoys = tuple(d.sample(spare, min(level.decoys, len(spare))))
        lamps = tuple(d.sample(range(len(COLOURS)), 2))
        bolts = d.randint(3, 9)
        clue, answer = _clue(level, d, lamps, bolts)
        safe = Safe(level, tuple(combo), decoys, clue, answer, lamps, bolts,
                    d.randrange(1 << 30))
        if play(safe)[0]:
            return safe
    raise RuntimeError('no safe for rung %d' % rung)


def between(a: float, b: float) -> float:
    """The shortest way round the dial from a to b, signed."""
    return (b - a + NUMBERS / 2) % NUMBERS - NUMBERS / 2


class Run(H.HandRun):
    def __init__(self, safe: Safe) -> None:
        super().__init__(safe.level.seconds)
        self.safe, self.level = safe, safe.level
        self.reading = 0.0             # the number under the mark
        self.set = 0                   # tumblers set
        self.typed = ''
        self.worded = False
        self.lever = 0.0               # 0 up .. 1 down
        self.strikes = 0
        self.grab: Optional[str] = None
        self.angle = 0.0               # the pointer's, round the dial
        self.last_way = 0
        self.travel = 0.0              # numbers since the dial last turned back
        self.pulled = 0.0              # where the lever was grabbed
        self.rattled = -1.0
        self.phase = random.Random(safe.seed).uniform(0, 6.28)

    # --- where things are
    def swing(self) -> float:
        return math.radians(self.level.swing) * (
            0.5 - 0.5 * math.cos(self.t * 1.1))

    def view(self):
        d = self.level.drift
        eye = (2.0 + d * math.sin(self.t * 0.6 + self.phase),
               2.3 + 0.4 * d * math.sin(self.t * 0.43), 9.0)
        return H.lens(eye, (2.0, 2.3, 0.0), 880.0, 500.0, 285.0)

    def frame(self) -> Tuple[Vec, Vec]:
        a = self.swing()
        return (math.cos(a), 0.0, -math.sin(a)), (math.sin(a), 0.0,
                                                  math.cos(a))

    def door(self, u: float, v: float, out: float = 0.0) -> Vec:
        r, n = self.frame()
        return (u * r[0] + out * n[0], v, u * r[2] + out * n[2])

    def see(self, u: float, v: float, out: float = 0.0):
        return self.view().see(self.door(u, v, out))

    def under(self) -> Optional[Tuple[float, float]]:
        """Where on the door the pointer is."""
        r, n = self.frame()
        p = H.on_plane(self.view(), self.hand.x, self.hand.y,
                       (0.0, 0.0, 0.0), n)
        if p is None:
            return None
        return H.dot(p, r), p[1]

    def knob(self) -> Tuple[float, float]:
        return HANDLE[0], HANDLE[1] - THROW * self.lever

    @property
    def unlocked(self) -> bool:
        return self.worded and self.set >= len(self.safe.combo)

    # --- the hand
    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        at = self.under()
        if at is None:
            return
        u, v = at
        if math.hypot(u - DIAL[0], v - DIAL[1]) <= DIAL[2]:
            self.grab = 'dial'
            self.angle = math.atan2(v - DIAL[1], u - DIAL[0])
            self.last_way, self.travel = 0, 0.0
        else:
            ku, kv = self.knob()
            if math.hypot(u - ku, v - kv) <= 0.4:
                self.grab = 'lever'
                self.pulled = v + THROW * self.lever

    def release(self) -> None:
        if not self.hand.down:
            return
        self.hand.down = False
        grab, self.grab = self.grab, None
        if self.result is not None:
            return
        if grab == 'lever':
            self.lever = 0.0
        if grab != 'dial' or self.set >= len(self.safe.combo) or \
                self.travel < 0.5:
            return
        k = self.set
        off = abs(between(self.reading, self.safe.combo[k]))
        if off <= self.level.mark and self.last_way == way(k) and \
                self.travel >= 1.0:
            self.set += 1
            self.note(0.3, 520.0 * 2 ** (k / 6.0), CLACK, 0.6)
        elif self.level.strict:
            self._strike()

    def key(self, port: int) -> None:
        if self.result is not None or self.worded:
            return
        self.note(0.05, 900.0, KEY, 0.3)
        if port == BACKSPACE:
            self.typed = self.typed[:-1]
            return
        want = self.safe.answer
        if len(self.typed) >= len(want):
            return
        self.typed += chr(ord('A') + port - LETTER)
        if self.typed == want:
            self.worded = True
            self.note(0.4, 784.0, CLACK, 0.6)
        elif len(self.typed) == len(want) and self.level.strict:
            self.typed = ''
            self._strike()

    def _strike(self) -> None:
        self.strikes += 1
        self.note(0.35, 95.0, BUZZ, 0.6)
        if self.strikes >= 3:
            self.result = (False, _('Three mistakes: the alarm went off'))

    # --- the clock
    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        at = self.under() if self.grab else None
        if self.grab == 'dial' and at is not None:
            a = math.atan2(at[1] - DIAL[1], at[0] - DIAL[0])
            turn = -math.degrees((a - self.angle + math.pi) % (2 * math.pi)
                                 - math.pi)          # clockwise is positive
            self.angle = a
            if abs(turn) > 1e-6 and abs(turn) < 120.0:
                self._turn(turn / PER)
        elif self.grab == 'lever' and at is not None:
            limit = 1.0 if self.unlocked else 0.12
            want = (self.pulled - at[1]) / THROW
            if want > limit + 0.05 and not self.unlocked and \
                    self.t - self.rattled > 0.5:
                self.rattled = self.t
                self.note(0.15, 300.0, RATTLE, 0.45)
            self.lever = max(0.0, min(limit, want))
            if self.lever >= 1.0:
                for j, semis in enumerate((0, 4, 7, 12)):
                    self.note(0.4, 262.0 * 2 ** (semis / 12.0), OPEN, 0.4,
                              at=self.t + 0.09 * j)
                self.result = (True, _('The door is open'))
        if self.result is None and self.t >= self.end:
            self.note(0.6, 95.0, BUZZ, 0.6)
            self.result = (False, _('The alarm went off'))

    def _turn(self, by: float) -> None:
        """Turn the dial *by* numbers, clockwise positive."""
        sign = 1 if by > 0 else -1
        if sign != self.last_way:
            self.last_way, self.travel = sign, 0.0
        self.travel += abs(by)
        old = self.reading
        self.reading = (old + by) % NUMBERS
        if int(math.floor(old)) != int(math.floor(self.reading)):
            self.note(0.03, 1300.0, TICK, 0.22)
        k = self.set
        if k < len(self.safe.combo) and sign == way(k):
            gap = ((self.safe.combo[k] - old) * sign) % NUMBERS
            if 0 < gap <= abs(by):
                self.note(0.25, 98.0, THUNK, self.level.thunk)
        for n in self.safe.decoys:
            gap = ((n - old) * sign) % NUMBERS
            if 0 < gap <= abs(by):
                self.note(0.2, 196.0, THUNK, self.level.thunk)

    def on_mark(self) -> bool:
        k = self.set
        return k < len(self.safe.combo) and abs(between(
            self.reading, self.safe.combo[k])) <= self.level.mark


def act(run: Run, port: int) -> None:
    if port < H.PRESS:
        run.hand.move(port)
    elif port == H.PRESS:
        run.press()
    elif port == H.RELEASE:
        run.release()
    elif port < PORTS:
        run.key(port)


# --- the reference ------------------------------------------------------------------

def autopilot(run: Run) -> List[int]:
    """Type the word, set each tumbler, pull the handle: one port a
    step."""
    if run.result is not None:
        return []
    hand, safe = run.hand, run.safe
    if not run.worded:
        if hand.down:
            return [H.RELEASE]
        want = safe.answer
        if not want.startswith(run.typed):
            return [BACKSPACE]
        return [LETTER + ord(want[len(run.typed)]) - ord('A')]
    if run.set < len(safe.combo):
        if hand.down and run.grab != 'dial':
            return [H.RELEASE]
        if not hand.down:
            q = run.see(DIAL[0], DIAL[1] + 0.7)
            move = H.toward(hand, q[0], q[1], tol=4.0)
            return [move] if move is not None else [H.PRESS]
        k, mark = run.set, run.level.mark
        rem = ((safe.combo[k] - run.reading) * way(k)) % NUMBERS
        near = min(rem, NUMBERS - rem)
        if near <= 0.6 * mark and run.last_way == way(k) and \
                run.travel >= 1.0:
            return [H.RELEASE]
        backing = run.last_way == -way(k) or run.last_way == 0
        if rem > NUMBERS - 4.0 or near <= 0.6 * mark or \
                backing and rem < 2.0:
            want = -way(k) * 1.5                     # back off, come again
        else:
            want = way(k) * min(2.5, rem)
        # The move that turns the dial most nearly that far.
        at = run.under()
        if at is None:
            return [H.RELEASE]
        a0 = math.atan2(at[1] - DIAL[1], at[0] - DIAL[0])
        r, n = run.frame()
        view = run.view()
        best, score = None, 1e9
        for port in range(H.PRESS):
            dx, dy = H.DIRS[port // 3]
            size = H.STEPS[port % 3]
            p = H.on_plane(view, hand.x + dx * size, hand.y + dy * size,
                           (0.0, 0.0, 0.0), n)
            if p is None:
                continue
            u, v = H.dot(p, r) - DIAL[0], p[1] - DIAL[1]
            rho = math.hypot(u, v)
            if not 0.9 <= rho <= 1.9:
                continue
            turn = -math.degrees((math.atan2(v, u) - a0 + math.pi)
                                 % (2 * math.pi) - math.pi) / PER
            miss = abs(turn - want) + (5.0 if turn * want <= 0 else 0.0) \
                + 0.3 * abs(rho - 1.4)
            if abs(turn) > abs(want) + 0.4 * mark:
                miss += 5.0                          # never overshoot
            if miss < score:
                best, score = port, miss
        if best is None:
            q = run.see(DIAL[0] + 1.4 * math.cos(a0),
                        DIAL[1] + 1.4 * math.sin(a0))
            best = H.toward(hand, q[0], q[1], tol=3.0)
        return [best] if best is not None else []
    if hand.down and run.grab != 'lever':
        return [H.RELEASE]
    ku, kv = run.knob()
    if not hand.down:
        q = run.see(ku, kv)
        move = H.toward(hand, q[0], q[1], tol=4.0)
        return [move] if move is not None else [H.PRESS]
    q = run.see(ku, kv - 0.5)
    move = H.toward(hand, q[0], q[1], tol=3.0)
    return [move] if move is not None else []


def play(safe: Safe, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(safe), pilot, EVENTS, act, dt)
