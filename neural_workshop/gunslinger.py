# -*- coding: utf-8 -*-
"""Gunslinger: a duel in the street. Your gun is in your hand, but you
may not fire until he goes for his -- and then you must be the quicker.

A dusty street at sundown, a man standing in it, your revolver held out
in front of you with its sight following the pointer. Nothing happens
for a while. Then he goes for his gun, and from that moment you have as
long as he takes to draw and fire: click to shoot. Fire before he moves
and you have shot first, which loses; take too long and he shoots you.
You may aim, and cock the hammer, while you wait.

From rung 4 the hammer has to be cocked before every shot: Space. The
notice at the top says who your man is and what to hit, and from rung 7
there is more than one man in the street: shoot the wrong one and you
hang for it.

The ladder:

* rungs 1-3: one man, three seconds, and the word DRAW when he moves;
* rungs 4-6: cock the hammer (Space) before each shot; no word -- watch
  his hand and listen for the leather;
* rungs 7-9: two men, and the notice says which is yours by his hat; he
  feints, reaching and thinking better of it; your aim sways;
* rungs 10-12: three men, and the others reach too; "shoot his hat off"
  means the hat and nothing else;
* rungs 13-15: the men pace about; the notice names your man by who he
  stands next to;
* rungs 16-19: four men, dust blowing across the street, the camera
  drifting, bells and crows; sometimes the notice only says your man
  is the one who draws;
* from rung 20: he is quicker every rung, the sway is wider, there are
  more men and more feints.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .hand import Vec
from .i18n import _

COCK = H.KEYS                  # port 14: Space
PORTS = H.KEYS + 1
EVENTS = tuple(range(PORTS))

HATS = (_('red'), _('black'), _('white'), _('green'), _('brown'), _('blue'))
REACH = 0.28                   # seconds his hand takes to reach his gun
BULLETS = 6
LEATHER, BANG, CLICK, BELL, CROW, WIND, THUD = range(7)
PATCHES = ('wood', 'growl', 'pluck', 'bell', 'brass', 'pad', 'sub')


class Grade(NamedTuple):
    rung: int
    men: int
    quick: float               # seconds from his draw to his shot
    word: bool                 # DRAW is written up when he moves
    cock: bool
    feints: int
    others: bool               # the other men reach too
    hat: bool                  # the notice may ask for the hat
    sway: float                # how far the aim wanders, in units
    pace: float                # how far the men walk about
    beside: bool               # the man is named by his neighbour
    dust: bool


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r,
        men=(1 if r < 7 else 2 if r < 10 else 3 if r < 16 else 4 if r < 20
             else min(6, 4 + top // 4)),
        quick=(3.0 if r < 4 else 2.2 if r < 7 else 1.8 if r < 10 else 1.5
               if r < 13 else 1.3 if r < 16 else 1.1 if r < 20
               else max(0.4, 1.0 - 0.02 * top)),
        word=r < 4, cock=r >= 4,
        feints=0 if r < 7 else 1 if r < 13 else 2 if r < 20
        else min(5, 3 + top // 5),
        others=r >= 10, hat=r >= 10,
        sway=(0.0 if r < 7 else 6.0 if r < 13 else 10.0 if r < 20
              else min(26.0, 12.0 + 0.5 * top)),
        pace=0.0 if r < 13 else 0.8 if r < 20 else min(2.2, 1.0 + 0.05 * top),
        beside=r >= 13, dust=r >= 16)


class Man(NamedTuple):
    x: float
    z: float                   # how far up the street
    hat: int
    stride: float              # how far he paces
    rate: float
    phase: float


class Reach(NamedTuple):
    t: float
    who: int
    real: bool                 # the draw itself, not a feint


class Duel(NamedTuple):
    level: Grade
    men: Tuple[Man, ...]
    foe: int
    part: str                  # 'man' or 'hat'
    notice: str
    reaches: Tuple[Reach, ...]  # feints, then the draw last
    draw_at: float
    seed: int


def _build(level: Grade, draw: random.Random) -> Duel:
    n = level.men
    hats = draw.sample(range(len(HATS)), n)
    xs = [(k - (n - 1) / 2.0) * (9.0 / max(1, n)) + draw.uniform(-0.5, 0.5)
          for k in range(n)]
    near, far = (9.0, 11.0) if level.rung < 7 else (11.0, 16.0) \
        if level.rung < 13 else (14.0, 21.0)
    men = tuple(Man(xs[k], draw.uniform(near, far), hats[k], level.pace,
                    draw.uniform(0.5, 1.0), draw.uniform(0, 6.28))
                for k in range(n))
    foe = draw.randrange(n)
    part = 'hat' if level.hat and draw.random() < 0.5 else 'man'
    if n == 1:
        who = _('Your man')
    elif level.dust and draw.random() < 0.4:
        who = _('Your man is the one who draws')
    elif level.beside and draw.random() < 0.6:
        side = draw.choice([s for s in (-1, 1) if 0 <= foe + s < n])
        who = (_('Your man stands to the left of the %s hat')
               if side > 0 else
               _('Your man stands to the right of the %s hat')) % \
            HATS[men[foe + side].hat]
    else:
        who = _('Your man wears the %s hat') % HATS[men[foe].hat]
    if n == 1:
        notice = (_('Fire when he draws. Shoot his hat off.')
                  if part == 'hat' else _('Fire when he draws, not before.'))
    else:
        notice = who + (_('. Shoot his hat off.') if part == 'hat' else
                        _('. Fire when he draws.'))
    draw_at = draw.uniform(3.0, 6.0) + 1.2 * level.feints
    reaches: List[Reach] = []
    for k in range(level.feints):
        t = draw.uniform(1.0, draw_at - 1.0)
        if all(abs(t - r.t) > 0.9 for r in reaches):
            who_k = foe if not level.others or draw.random() < 0.4 else \
                draw.choice([m for m in range(n) if m != foe] or [foe])
            reaches.append(Reach(t, who_k, False))
    reaches.sort()
    reaches.append(Reach(draw_at, foe, True))
    return Duel(level, men, foe, part, notice, tuple(reaches), draw_at,
                draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Duel:
    draw = random.Random(seed) if seed is not None else (rng or random)
    level = grade(rung)
    for _try in range(60):
        duel = _build(level, random.Random(draw.getrandbits(32)))
        if play(duel)[0]:
            return duel
    raise RuntimeError('no duel for rung %d' % rung)


class Run(H.HandRun):
    def __init__(self, duel: Duel) -> None:
        super().__init__(duel.draw_at + duel.level.quick)
        self.duel, self.level = duel, duel.level
        self.cocked = not duel.level.cock
        self.bullets = BULLETS
        self.shots: List[Tuple[float, float, float]] = []   # t, x, y
        self.hatless: set = set()
        self.reach_no = 0
        self.extra = random.Random(duel.seed)
        self.extra_at = 0.8
        self.fell: Optional[int] = None
        self.fell_at = 0.0
        self.hat_at = {}

    # --- the street
    def view(self):
        d = 1.2 if self.level.dust else 0.0
        eye = (d * math.sin(self.t * 0.5), 1.6, 0.0)
        return H.lens(eye, (eye[0] * 0.5, 1.3, -18.0), 900.0, 500.0, 300.0)

    def stands(self, k: int) -> Vec:
        m = self.duel.men[k]
        return (m.x + m.stride * math.sin(self.t * m.rate + m.phase), 0.0,
                -m.z)

    def arm(self, k: int) -> float:
        """How far man *k*'s hand has gone for his gun: 0 hanging, 1 out
        and levelled."""
        best = 0.0
        for r in self.duel.reaches:
            if r.who != k or self.t < r.t:
                continue
            u = (self.t - r.t) / REACH
            if r.real:
                best = max(best, min(1.0, u))
            elif u < 2.0:
                best = max(best, 0.55 * (u if u < 1 else 2 - u))
        return best

    def drawn(self) -> bool:
        """Whether he has gone for his gun."""
        return self.t >= self.duel.draw_at

    def sway(self) -> Tuple[float, float]:
        a = self.level.sway
        return (a * math.sin(self.t * 2.3 + 1.0),
                a * math.sin(self.t * 3.1))

    def aim(self) -> Tuple[float, float]:
        s = self.sway()
        return self.hand.x + s[0], self.hand.y + s[1]

    def boxes(self, k: int):
        """Man *k* on the screen: (hat box, body box), each (x0, y0, x1,
        y1), or None if he is out of sight."""
        x, _y, z = self.stands(k)
        view = self.view()
        feet, top = view.see((x, 0.0, z)), view.see((x, 1.85, z))
        if feet is None or top is None:
            return None
        s = view.size(1.0, feet[2])
        cx = feet[0]
        body = (cx - 0.3 * s, feet[1], cx + 0.3 * s, top[1])
        hat = (cx - 0.3 * s, top[1], cx + 0.3 * s, top[1] + 0.3 * s)
        if k in self.hatless:
            hat = (0.0, 0.0, -1.0, -1.0)
        return hat, body

    def target(self) -> Tuple[float, float]:
        """The middle of what the notice says to hit."""
        hat, body = self.boxes(self.duel.foe)
        box = hat if self.duel.part == 'hat' else body
        return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2

    # --- the hand
    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        if not self.drawn():
            self.note(0.35, 70.0, BANG, 0.8)
            self.shots.append((self.t,) + self.aim())
            return self._lose(_('You fired first'))
        self._fire()

    def release(self) -> None:
        self.hand.down = False

    def cock(self) -> None:
        if self.result is not None or self.cocked:
            return
        self.cocked = True
        self.note(0.05, 900.0, CLICK, 0.4)

    def _fire(self) -> None:
        if not self.cocked or self.bullets <= 0:
            self.note(0.04, 500.0, CLICK, 0.3)
            return
        self.cocked = not self.level.cock
        self.bullets -= 1
        ax, ay = self.aim()
        self.shots.append((self.t, ax, ay))
        self.note(0.35, 70.0, BANG, 0.8)
        order = sorted(range(len(self.duel.men)),
                       key=lambda k: self.duel.men[k].z)
        for k in order:
            seen = self.boxes(k)
            if seen is None:
                continue
            hat, body = seen
            in_hat = hat[0] <= ax <= hat[2] and hat[1] <= ay <= hat[3]
            in_body = body[0] <= ax <= body[2] and body[1] <= ay <= body[3]
            if not (in_hat or in_body):
                continue
            if k != self.duel.foe:
                self.fell, self.fell_at = k, self.t
                return self._lose(_('You shot the wrong man'))
            if in_hat:
                self.hatless.add(k)
                self.hat_at[k] = self.t
                if self.duel.part == 'hat':
                    self.result = (True, _('His hat is off and so is he'))
                return                     # a hat is not a man
            self.fell, self.fell_at = k, self.t
            if self.duel.part == 'hat':
                return self._lose(_('The notice said his hat'))
            self.result = (True, _('You were the quicker'))
            return
        if self.bullets <= 0 and self.result is None:
            self.note(0.04, 500.0, CLICK, 0.3)

    def _lose(self, why: str) -> None:
        self.result = (False, why)

    # --- the clock
    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        reaches = self.duel.reaches
        while self.reach_no < len(reaches) and \
                reaches[self.reach_no].t <= self.t:
            r = reaches[self.reach_no]
            self.reach_no += 1
            q = self.view().see(self.stands(r.who))
            pan = 0.0 if q is None else (q[0] - 500.0) / 500.0
            self.note(0.12, 260.0 if r.real else 240.0, LEATHER,
                      0.55 if r.real else 0.4, pan=pan)
            if r.real:
                self.note(0.05, 800.0, CLICK, 0.35, pan=pan,
                          at=self.t + REACH)
        if self.level.rung >= 4 and self.t >= self.extra_at:
            self.extra_at = self.t + self.extra.uniform(0.9, 2.6)
            roll = self.extra.random()
            if roll < 0.4:
                self.note(1.2, 180.0, WIND, 0.15,
                          pan=self.extra.uniform(-1, 1))
            elif self.level.dust and roll < 0.7:
                self.note(0.8, 392.0, BELL, 0.3)
            elif self.level.dust:
                self.note(0.25, 520.0, CROW, 0.25,
                          pan=self.extra.uniform(-1, 1))
        if self.result is None and self.t >= self.end:
            self.note(0.35, 80.0, BANG, 0.9)
            self.note(0.3, 60.0, THUD, 0.6, at=self.t + 0.1)
            self._lose(_('Too slow: he shot you'))

    def dust(self) -> float:
        """How thick the dust across the street is now, 0 to 1."""
        if not self.level.dust:
            return 0.0
        return max(0.0, math.sin(self.t * 0.9 + 2.0)) ** 2 * 0.55


def act(run: Run, port: int) -> None:
    if port < H.PRESS:
        run.hand.move(port)
    elif port == H.PRESS:
        run.press()
    elif port == H.RELEASE:
        run.release()
    elif port == COCK:
        run.cock()


def autopilot(run: Run) -> List[int]:
    """Cock the hammer and hold the sight on him; fire when he draws.
    One port a step."""
    if run.result is not None:
        return []
    hand = run.hand
    if hand.down:
        return [H.RELEASE]
    if not run.cocked:
        return [COCK]
    tx, ty = run.target()
    sx, sy = run.sway()
    move = H.toward(hand, tx - sx, ty - sy, tol=3.0)
    if move is not None:
        return [move]
    return [H.PRESS] if run.drawn() else []


def play(duel: Duel, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(duel), pilot, EVENTS, act, dt)
