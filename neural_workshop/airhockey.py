# -*- coding: utf-8 -*-
"""Air Hockey: two hands, one puck.

A table seen from your end. Your mallet goes where the pointer is on
your half of the table; hit the puck into the far goal. Your own goal
is kept by a short bar that slides along its mouth on the keys (Left /
A and Right / D), so one hand attacks and the other defends. First to
the goals wanted wins; let in too many and you have lost.

The ladder:

* rungs 1-3: one goal wins and three lose; a slow puck and a slow
  opponent;
* rungs 4-6: two goals to win; a quicker puck;
* rungs 7-9: a wider goal to keep and a quicker opponent;
* rungs 10-12: three goals to win, two lose;
* rungs 13-15: the camera swings from side to side over the table;
* rungs 16-19: and at times looks from the far end;
* from rung 20: a faster puck and opponent every rung, and one goal
  against loses.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .i18n import _

LEFT, RIGHT = H.KEYS, H.KEYS + 1          # held: the keeper
PORTS = H.KEYS + 2
EVENTS = H.HAND_EVENTS
PUCK, MALLET, BAR = 0.06, 0.11, 0.17      # radius, radius, half a bar
THEIRS = 0.34                             # half their goal mouth
REACH = 7.0                               # how fast a mallet can go
KEEP = 2.2                                # how fast the keeper slides
CLACK, WALL, GOAL, LOST, HUM = range(5)
PATCHES = ('wood', 'pluck', 'bell', 'growl', 'pad')


class Grade(NamedTuple):
    rung: int
    need: int
    allow: int                 # goals against that lose
    pace: float                # the puck's top speed
    rival: float               # how fast the other mallet moves
    mouth: float               # half your goal mouth
    swing: float               # degrees the camera swings
    flips: bool
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    need = 1 if r < 4 else 2 if r < 10 else 3
    return Grade(
        rung=r, need=need,
        allow=3 if r < 10 else 2 if r < 20 else 1,
        pace=(2.2 if r < 4 else 2.8 if r < 10 else 3.3 if r < 20
              else min(6.0, 3.5 + 0.06 * top)),
        rival=(0.7 if r < 7 else 1.0 if r < 13 else 1.25 if r < 20
               else min(2.4, 1.3 + 0.03 * top)),
        mouth=0.34 if r < 7 else 0.42 if r < 20 else min(0.6, 0.44
                                                         + 0.004 * top),
        swing=0.0 if r < 13 else 22.0,
        flips=r >= 16,
        seconds=45.0 + 25.0 * need)


class Game(NamedTuple):
    level: Grade
    serve: float               # the angle the first puck leaves at
    flips: Tuple[Tuple[float, float], ...]   # when the view is from the
    #                                           far end: (from, to)
    seed: int


def build(level: Grade, draw: random.Random) -> Optional[Game]:
    flips, t = [], 0.0
    while level.flips and t < level.seconds:
        t += draw.uniform(6.0, 10.0)
        flips.append((t, t + draw.uniform(2.5, 4.0)))
        t = flips[-1][1]
    return Game(level, draw.uniform(-0.5, 0.5), tuple(flips),
                draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Game:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng)


class Run(H.HandRun):
    def __init__(self, game: Game) -> None:
        super().__init__(game.level.seconds)
        self.game, self.level = game, game.level
        self.mine = (0.0, 0.3)         # mallets, on the table
        self.mine_v = (0.0, 0.0)
        self.theirs = (0.0, 1.7)
        self.theirs_v = (0.0, 0.0)
        self.keeper = 0.0
        self.score = [0, 0]            # yours, theirs
        self.draw = random.Random(game.seed)
        self.wait = 0.8                # before the puck is served
        self.puck = (0.0, 1.0)
        self.v = (0.0, 0.0)
        self.to_me = True
        self.angle = game.serve
        self.clack_at = 0.0

    # --- the picture
    def far_end(self) -> bool:
        return any(a <= self.t < b for a, b in self.game.flips)

    def view(self):
        a = math.radians(self.level.swing) * math.sin(self.t * 0.5)
        if self.far_end():
            a += math.pi
        d = 2.5
        eye = (d * math.sin(a), 2.0, -1.0 + d * math.cos(a))
        return H.lens(eye, (0.0, 0.0, -1.0), 720.0, 500.0, 330.0)

    @staticmethod
    def world(p: Tuple[float, float], up: float = 0.0):
        return (p[0], up, -p[1])

    def see(self, p: Tuple[float, float], up: float = 0.0):
        return self.view().see(self.world(p, up))

    def under(self) -> Optional[Tuple[float, float]]:
        spot = self.view().on_floor(self.hand.x, self.hand.y)
        return None if spot is None else (spot[0], -spot[1])

    def press(self) -> None:
        self.hand.down = True

    def release(self) -> None:
        self.hand.down = False

    def key(self, port: int) -> None:
        pass

    # --- the table
    def _serve(self) -> None:
        self.puck = (0.0, 1.0)
        way = -1.0 if self.to_me else 1.0
        a = self.angle
        self.v = (0.9 * math.sin(a), 0.9 * way * math.cos(a))
        self.angle = self.draw.uniform(-0.6, 0.6)

    def _mallet(self, at, vel, want, top, dt):
        dx, dy = want[0] - at[0], want[1] - at[1]
        d = math.hypot(dx, dy)
        go = min(d, top * dt)
        if d > 1e-9:
            dx, dy = dx / d * go, dy / d * go
        return (at[0] + dx, at[1] + dy), (dx / dt, dy / dt)

    def _hit(self, at, vel, forward: bool = False) -> None:
        px, py = self.puck
        nx, ny = px - at[0], py - at[1]
        d = math.hypot(nx, ny)
        if d >= PUCK + MALLET or d < 1e-9:
            return
        nx, ny = nx / d, ny / d
        rvx, rvy = self.v[0] - vel[0], self.v[1] - vel[1]
        along = rvx * nx + rvy * ny
        if along < 0:
            # a still mallet deadens the puck; only a struck one flies
            spring = 1.25 + 0.65 * min(1.0, math.hypot(*vel) / 1.5)
            rvx, rvy = rvx - spring * along * nx, rvy - spring * along * ny
            self.v = (rvx + vel[0], rvy + vel[1])
            if forward and self.v[1] > 0:       # they never play it back
                self.v = (self.v[0], -0.6 * self.v[1])
            if self.t >= self.clack_at:
                self.clack_at = self.t + 0.08
                self.note(0.05, 500.0, CLACK, 0.5, pan=px)
        self.puck = (at[0] + nx * (PUCK + MALLET + 0.002),
                     at[1] + ny * (PUCK + MALLET + 0.002))

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.controls(control)
        self.t += dt
        level = self.level
        slide = (self.holding(RIGHT) - self.holding(LEFT)) * KEEP * dt
        if self.far_end():
            slide = -slide                      # right on the screen
        self.keeper = max(-level.mouth, min(level.mouth,
                                            self.keeper + slide))
        want = self.under() or self.mine
        want = (max(-1 + MALLET, min(1 - MALLET, want[0])),
                max(0.14, min(0.95, want[1])))
        self.mine, self.mine_v = self._mallet(self.mine, self.mine_v, want,
                                              REACH, dt)
        px, py = self.puck
        if py > self.theirs[1] and math.hypot(*self.v) < 0.4:
            # behind them: stand aside and let it slide out
            goal = (px + (0.5 if self.theirs[0] >= px else -0.5), 1.5)
            self.v = (self.v[0], self.v[1] - 1.2 * dt)
        elif py > 1.05 and self.v[1] > -0.3 and py < self.theirs[1] + 0.05:
            goal = (px, py + 0.02)              # they go for it
        else:
            goal = (max(-THEIRS, min(THEIRS, px)), 1.72)
        self.theirs, self.theirs_v = self._mallet(
            self.theirs, self.theirs_v,
            (max(-1 + MALLET, min(1 - MALLET, goal[0])),
             max(1.08, min(1.86, goal[1]))),
            level.rival * (1.0 if goal[1] < 1.7 else 1.5), dt)
        if self.wait > 0:
            self.wait -= dt
            if self.wait <= 0:
                self._serve()
            return
        vx, vy = self.v
        speed = math.hypot(vx, vy)
        if speed > level.pace:
            vx, vy = vx / speed * level.pace, vy / speed * level.pace
        vx, vy = vx * (1 - 0.12 * dt), vy * (1 - 0.12 * dt)
        px, py = px + vx * dt, py + vy * dt
        if abs(px) > 1 - PUCK:
            px = math.copysign(1 - PUCK, px)
            vx = -0.8 * vx
            self.note(0.04, 300.0, WALL, 0.3, pan=px)
        self.puck, self.v = (px, py), (vx, vy)
        self._hit(self.mine, self.mine_v)
        self._hit(self.theirs, self.theirs_v, True)
        px, py = self.puck
        vx, vy = self.v
        if py < PUCK + 0.06 and vy < 0 and abs(px - self.keeper) <= BAR:
            self.v = (vx + 1.5 * (px - self.keeper), abs(vy))
            self.puck = (px, PUCK + 0.06)
            self.note(0.05, 420.0, CLACK, 0.45, pan=px)
        elif py < PUCK:
            if abs(px) < level.mouth:
                return self._goal(1)
            self.puck, self.v = (px, PUCK), (vx, abs(vy))
        elif py > 2 - PUCK:
            if abs(px) < THEIRS:
                return self._goal(0)
            self.puck, self.v = (px, 2 - PUCK), (vx, -abs(vy))
        if math.hypot(*self.v) < 0.12 and 0.9 < py < 1.1:
            self.v = (self.v[0], self.v[1] - 0.3)   # never stuck in the middle
        if self.t >= self.end:
            self.result = (False, _('Time: no winner'))

    def _goal(self, who: int) -> None:
        self.score[who] += 1
        self.note(0.4, 880.0 if who == 0 else 110.0, GOAL if who == 0
                  else LOST, 0.6)
        self.to_me = who == 0
        self.wait = 0.9
        self.puck, self.v = (0.0, 1.0), (0.0, 0.0)
        if self.score[0] >= self.level.need:
            self.result = (True, _('You win %d-%d') % tuple(self.score))
        elif self.score[1] >= self.level.allow:
            self.result = (False, _('You lose %d-%d') % tuple(self.score))


act = H.act


def autopilot(run: Run) -> List[int]:
    """Keep the bar in front of a puck coming in; otherwise get behind
    the puck and drive it at the open side of their goal. One port a
    step."""
    if run.result is not None:
        return []
    px, py = run.puck
    vx, vy = run.v
    if vy < -0.2 and py < 1.2:                  # where will it cross?
        t = (py - PUCK - 0.06) / -vy
        x = px + vx * t
        while abs(x) > 1 - PUCK:
            x = math.copysign(2 * (1 - PUCK), x) - x
        if abs(x) < run.level.mouth + BAR and abs(x - run.keeper) > 0.06 \
                and t < 0.6:
            right = x > run.keeper
            if run.far_end():
                right = not right
            port = RIGHT if right else LEFT
            if not run.holding(port):
                return [port]
    if run.wait > 0 or py > 1.0 + 0.25 * (vy < 0):
        want = (0.5 * px, 0.32)
    else:
        aim = (-0.7 * THEIRS if run.theirs[0] > 0 else 0.7 * THEIRS, 2.0)
        dx, dy = aim[0] - px, aim[1] - py
        d = math.hypot(dx, dy)
        dx, dy = dx / d, dy / d
        back = (px - dx * 0.24, py - dy * 0.24)
        mx, my = run.mine
        want = back
        if my < py - 0.08:                      # where would it go?
            lands = px + (px - mx) / (py - my) * (2.0 - py)
            if abs(lands) < 0.8 * THEIRS:
                ux, uy = px - mx, py - my
                u = math.hypot(ux, uy)
                want = (px + ux / u * 0.3, py + uy / u * 0.3)
        elif my > py - 0.02:                    # go round, not through
            want = (px + (0.3 if mx > px else -0.3), max(0.14, py - 0.3))
    q = run.see((max(-0.9, min(0.9, want[0])), max(0.14, min(0.95,
                                                             want[1]))))
    if q is None:
        return []
    move = H.toward(run.hand, q[0], q[1], tol=4.0)
    return [move] if move is not None else []


def play(game: Game, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(game), pilot, EVENTS, act, dt)
