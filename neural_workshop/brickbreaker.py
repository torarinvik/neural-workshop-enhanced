# -*- coding: utf-8 -*-
"""3D Brick Breaker: a ball in a box, a wall of bricks at the far end,
and a paddle across the near one that can be moved and tilted.

The box runs away from the player: x across, y up, z from the paddle's
plane at 0 back to -DEEP. The ball flies straight (until gravity and
wind come in), bounces off the box and the bricks, and is lost if it
gets past the paddle. The paddle slides across the opening and tilts:
a tilted paddle sends the ball off its face like a mirror, which is how
a brick is aimed at -- and, higher up, how the wrong ones are avoided.

What the ladder adds, besides speed and a smaller paddle:

* tough bricks that take two or three hits;
* mines, which cost a life when the ball touches them;
* steel, which never breaks;
* numbered bricks that break only in order;
* coloured bricks that break only for a ball of their colour -- the
  ball takes the paddle's colour each time it is returned, and the
  player chooses that colour;
* bombs, which take their neighbours with them, mines included, safely;
* gravity, a wind that comes and goes, a wall of bricks that slides,
  a ball that quickens with every return, and a second ball.

The first ball is served a second after the paddle is first touched;
nothing is served to a player who does nothing.

A board is cleared when every plain, tough, numbered and coloured brick
is gone; mines, steel and bombs may be left standing.

For the agent boundary: ports 0-7 slide the paddle left, right, up,
down and the four diagonals; 8-11 tilt it to face left, right, up and
down; 12 levels it; 13 changes its colour.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import showing
from .i18n import _

WIDE, HIGH, DEEP = 1.0, 0.7, 3.0     # half-width, half-height, depth
BALL = 0.06                    # the ball's radius
THICK = 0.15                   # half a brick's depth
LAYER = 0.34                   # between layers of bricks
SLIDE = 0.22                   # how far a sliding wall goes each way
PADDLE_SPEED = 2.4             # units a second, by the ports
MOUSE_SPEED = 5.0              # and following the mouse
TILT_RATE = 1.4                # radians a second
TILT_MOST = 0.5
HOLD = 1.0                     # seconds the ball waits on the paddle
GRAVITY = 1.6

(LEFT, RIGHT, UP, DOWN, UP_LEFT, UP_RIGHT, DOWN_LEFT, DOWN_RIGHT,
 FACE_LEFT, FACE_RIGHT, FACE_UP, FACE_DOWN, LEVEL, COLOUR) = range(14)
PORTS = 14
EVENTS = frozenset((LEVEL, COLOUR))
_S = math.sqrt(0.5)
MOVES = {LEFT: (-1, 0), RIGHT: (1, 0), UP: (0, 1), DOWN: (0, -1),
         UP_LEFT: (-_S, _S), UP_RIGHT: (_S, _S), DOWN_LEFT: (-_S, -_S),
         DOWN_RIGHT: (_S, -_S)}
TILTS = {FACE_LEFT: (-1, 0), FACE_RIGHT: (1, 0), FACE_UP: (0, 1),
         FACE_DOWN: (0, -1)}

PLAIN, TOUGH, STEEL, MINE, BOMB = 'plain', 'tough', 'steel', 'mine', 'bomb'


class Grade(NamedTuple):
    rung: int
    across: int          # bricks across
    up: int              # and up
    layers: int
    bricks: int          # that must be broken
    tough: int           # of which so many take more than one hit
    mines: int
    steel: int
    bombs: int
    order: int           # numbered bricks, broken in order
    colours: int         # 0: colour does not matter
    speed: float
    paddle: Tuple[float, float]      # half-width, half-height
    lives: int
    seconds: float
    gravity: bool
    wind: float
    slide: float         # the wall's slides a second; 0 stands still
    quicken: float       # share of speed added each return
    balls: int


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    big, mid, small = (0.30, 0.22), (0.25, 0.18), (0.21, 0.15)
    if r < 4:
        return Grade(r, 3, 2, 1, 3 + r, 0, 0, 0, 0, 0, 0, 1.5, big, 3, 45.0,
                     False, 0.0, 0.0, 0.0, 1)
    if r < 7:
        return Grade(r, 4, 3, 1, 7, r - 3, 0, 0, 0, 0, 0, 1.8, big, 5, 90.0,
                     False, 0.0, 0.0, 0.0, 1)
    if r < 10:
        return Grade(r, 4, 3, 1, 7, 2, r - 6, 0, 0, 0, 0, 2.0, mid, 4, 100.0,
                     False, 0.0, 0.0, 0.0, 1)
    if r < 13:
        return Grade(r, 4, 3, 2, 9, 2, 2, 2, 0, 3, 0, 2.1, mid, 4, 120.0,
                     False, 0.0, 0.0, 0.0, 1)
    if r < 16:
        return Grade(r, 4, 3, 2, 10, 2, 3, 2, 2, 3, 2, 2.2, mid, 4, 140.0,
                     False, 0.0, 0.0, 0.0, 1)
    if r < 19:
        return Grade(r, 4, 3, 2, 10, 3, 3, 2, 2, 4, 2, 2.3, mid, 4, 150.0,
                     True, 0.0, 0.25, 0.0, 1)
    if r < 22:
        return Grade(r, 4, 3, 3, 12, 3, 4, 3, 2, 4, 3, 2.5, small, 4, 160.0,
                     True, 0.9, 0.3, 0.03, 1)
    k = r - 22
    return Grade(r, 4, 3, 3, min(16, 12 + k // 2), 4, min(7, 4 + k // 2), 3,
                 2, 5, 3, min(3.4, 2.6 + 0.05 * k), small, 4, 180.0, True,
                 min(1.6, 1.0 + 0.05 * k), 0.35, 0.04, 2)


class Brick(NamedTuple):
    i: int
    j: int
    k: int               # layer, 0 at the back
    kind: str
    hits: int
    colour: int          # 0 breaks for any ball
    order: int           # -1 unnumbered


class Board(NamedTuple):
    level: Grade
    bricks: Tuple[Brick, ...]
    seed: int
    question: str


def must(b: Brick) -> bool:
    """Whether the board is not cleared while this brick stands."""
    return b.kind in (PLAIN, TOUGH)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Board:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    lv = grade(rung)
    cells = [(i, j, k) for k in range(lv.layers) for j in range(lv.up)
             for i in range(lv.across)]
    for _attempt in range(400):
        draw.shuffle(cells)
        need = lv.bricks + lv.mines + lv.steel + lv.bombs
        spots = cells[:need]
        kinds = ([TOUGH] * lv.tough + [PLAIN] * (lv.bricks - lv.tough)
                 + [MINE] * lv.mines + [STEEL] * lv.steel + [BOMB] * lv.bombs)
        placed = dict(zip(spots, kinds))
        # Nothing that must be broken sits straight behind a mine or
        # steel: there is always a way at it.
        if any(must_kind(kind) and any(
                placed.get((i, j, kk)) in (MINE, STEEL)
                for kk in range(k + 1, lv.layers))
               for (i, j, k), kind in placed.items()):
            continue
        break
    else:
        raise RuntimeError('no board for rung %d' % rung)
    wanted = [s for s in spots if must_kind(placed[s])]
    # A numbered brick never stands in front of one that has to go
    # before it: front to back, a column's numbers only rise.
    numbered: List[Tuple[int, int, int]] = []
    for _attempt in range(300):
        numbered = draw.sample(wanted, min(lv.order, len(wanted)))
        turn = {s: (numbered.index(s) if s in numbered else -1)
                for s in wanted}
        if all(turn[a] <= turn[b] for a in wanted for b in wanted
               if a[:2] == b[:2] and a[2] > b[2]):
            break
    else:
        numbered = []
    bricks = []
    for (i, j, k) in sorted(placed):
        kind = placed[(i, j, k)]
        hits = draw.choice((2, 2, 3)) if kind == TOUGH else 1
        order = numbered.index((i, j, k)) if (i, j, k) in numbered else -1
        colour = 0
        if lv.colours and must_kind(kind) and order < 0 \
                and draw.random() < 0.7:
            colour = draw.randint(1, lv.colours)
        bricks.append(Brick(i, j, k, kind, hits, colour, order))
    return Board(lv, tuple(bricks), seed,
                 _('Break every brick; keep the ball in play'))


def must_kind(kind: str) -> bool:
    return kind in (PLAIN, TOUGH)


class Ball:
    def __init__(self) -> None:
        self.p = [0.0, 0.0, 0.0]
        self.v = [0.0, 0.0, 0.0]
        self.colour = 1
        self.held = HOLD         # seconds until it leaves the paddle


def _on(control) -> frozenset:
    if control is None:
        return frozenset()
    if isinstance(control, int):
        return frozenset((control,))
    return frozenset(control)


class Run:
    """One board, played."""

    def __init__(self, board: Board) -> None:
        self.board = board
        self.level = lv = board.level
        self.draw = random.Random(board.seed + 1)
        self.t = 0.0
        self.bricks: List[Brick] = list(board.bricks)
        self.lives = lv.lives
        self.speed = lv.speed
        self.px = self.py = 0.0
        self.pvx = self.pvy = 0.0
        self.yaw = self.pitch = 0.0
        self.colour = 1
        self.aim: Optional[Tuple[float, float]] = None   # the mouse
        self.balls = [Ball() for _k in range(lv.balls)]
        for n, ball in enumerate(self.balls):
            ball.held = HOLD + 2.5 * n
        self.phase = self.draw.uniform(0.0, 6.28)
        self.notes: List = []
        self.flash = -9.0            # when a life was last lost
        self.burst: List[Tuple[float, Tuple[float, float, float]]] = []
        self.broken = 0
        self.touched = False         # nothing is served to an idle paddle
        self.result: Optional[Tuple[bool, str]] = None

    # --- where things are -------------------------------------------------

    def shift(self, t: Optional[float] = None) -> float:
        """How far the wall of bricks has slid across."""
        lv = self.level
        if not lv.slide:
            return 0.0
        return SLIDE * math.sin(2 * math.pi * lv.slide
                                * (self.t if t is None else t) + self.phase)

    def cell(self) -> Tuple[float, float]:
        lv = self.level
        span = WIDE - (SLIDE if lv.slide else 0.0)
        return 2 * span / lv.across, 2 * HIGH / lv.up

    def box(self, b: Brick, t: Optional[float] = None):
        """A brick's centre and half-sizes."""
        lv = self.level
        cw, ch = self.cell()
        span = WIDE - (SLIDE if lv.slide else 0.0)
        return ((-span + cw * (b.i + 0.5) + self.shift(t),
                 -HIGH + ch * (b.j + 0.5),
                 -DEEP + 0.25 + LAYER * b.k),
                (cw / 2 - 0.015, ch / 2 - 0.015, THICK))

    def normal(self) -> Tuple[float, float, float]:
        """The way the paddle's face looks: into the box."""
        cp = math.cos(self.pitch)
        return (math.sin(self.yaw) * cp, math.sin(self.pitch),
                -math.cos(self.yaw) * cp)

    def frame(self):
        """The paddle's normal, its across and its up."""
        n = self.normal()
        a = (math.cos(self.yaw), 0.0, math.sin(self.yaw))
        b = (a[1] * n[2] - a[2] * n[1], a[2] * n[0] - a[0] * n[2],
             a[0] * n[1] - a[1] * n[0])
        if b[1] < 0:
            b = (-b[0], -b[1], -b[2])
        return n, a, b

    def next_order(self) -> int:
        """The number of the brick that may be broken next, or -1."""
        left = [b.order for b in self.bricks if b.order >= 0]
        return min(left) if left else -1

    def breaks(self, b: Brick, colour: int) -> bool:
        """Whether a ball of this colour would damage this brick now."""
        if b.kind in (STEEL, MINE):
            return False
        if b.order >= 0 and b.order != self.next_order():
            return False
        return not (b.colour and self.level.colours
                    and b.colour != colour)

    def left(self) -> int:
        return sum(must(b) for b in self.bricks)

    def remaining(self) -> float:
        return max(0.0, self.level.seconds - self.t)

    # --- sound ------------------------------------------------------------

    def _note(self, freq: float, dur: float = 0.08, gain: float = 0.5,
              x: float = 0.0) -> None:
        self.notes.append(showing.note(self.t, dur, freq,
                                       max(-1.0, min(1.0, x / WIDE)), gain))

    # --- the play ---------------------------------------------------------

    def press(self, port: int) -> None:
        if self.result is not None:
            return
        self.touched = True
        if port == LEVEL:
            self.yaw = self.pitch = 0.0
        elif port == COLOUR and self.level.colours:
            self.colour = self.colour % self.level.colours + 1

    def point(self, x: float, y: float) -> None:
        """The mouse: where the paddle is to go."""
        self.aim = (x, y)
        self.touched = True

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        on = _on(control)
        if on:
            self.touched = True
        self._paddle(dt, on)
        for ball in self.balls:
            self._ball(ball, dt)
            if self.result is not None:
                return
        self.burst = [b for b in self.burst if self.t - b[0] < 0.4]
        if self.t >= self.level.seconds:
            self.result = (False, _('Out of time: %d left') % self.left())

    def _paddle(self, dt: float, on) -> None:
        pw, ph = self.level.paddle
        dx = dy = 0.0
        for port, (mx, my) in MOVES.items():
            if port in on:
                dx += mx
                dy += my
        x0, y0 = self.px, self.py
        if dx or dy:
            self.aim = None
            self.px += dx * PADDLE_SPEED * dt
            self.py += dy * PADDLE_SPEED * dt
        elif self.aim is not None:
            ex, ey = self.aim[0] - self.px, self.aim[1] - self.py
            far = math.hypot(ex, ey)
            if far > 1e-9:
                go = min(far, MOUSE_SPEED * dt)
                self.px += ex / far * go
                self.py += ey / far * go
        self.px = max(-WIDE + pw, min(WIDE - pw, self.px))
        self.py = max(-HIGH + ph, min(HIGH - ph, self.py))
        self.pvx, self.pvy = (self.px - x0) / dt, (self.py - y0) / dt
        for port, (ty, tp) in TILTS.items():
            if port in on:
                self.yaw += ty * TILT_RATE * dt
                self.pitch += tp * TILT_RATE * dt
        self.yaw = max(-TILT_MOST, min(TILT_MOST, self.yaw))
        self.pitch = max(-TILT_MOST, min(TILT_MOST, self.pitch))

    def _serve(self, ball: Ball) -> None:
        n = self.normal()
        d = [n[0] + self.draw.uniform(-0.05, 0.05),
             n[1] + self.draw.uniform(-0.05, 0.05), n[2]]
        m = math.sqrt(sum(c * c for c in d))
        ball.v = [c / m * self.speed for c in d]
        ball.colour = self.colour
        self._note(440.0, x=ball.p[0])

    def _lose(self, said: str) -> None:
        self.lives -= 1
        self.flash = self.t
        self._note(110.0, 0.3, 0.7)
        if self.lives <= 0:
            self.result = (False, said)

    def _ball(self, ball: Ball, dt: float) -> None:
        lv = self.level
        n, a, b = self.frame()
        if ball.held > 0:
            if self.touched:
                ball.held -= dt
            ball.p = [self.px + n[0] * (BALL + 0.03),
                      self.py + n[1] * (BALL + 0.03), n[2] * (BALL + 0.03)]
            ball.colour = self.colour
            if ball.held <= 0:
                self._serve(ball)
            return
        p, v = ball.p, ball.v
        if lv.gravity:
            v[1] -= GRAVITY * dt
        if lv.wind:
            v[0] += lv.wind * math.sin(0.7 * self.t + self.phase) * dt
        speed = math.sqrt(sum(c * c for c in v))
        if lv.gravity:
            if speed > 1.6 * self.speed:
                v[:] = [c * 1.6 * self.speed / speed for c in v]
        elif speed > 1e-9:
            v[:] = [c * self.speed / speed for c in v]
        for q in range(3):
            p[q] += v[q] * dt
        # The box.
        for q, most in ((0, WIDE), (1, HIGH)):
            if p[q] > most - BALL and v[q] > 0:
                p[q], v[q] = most - BALL, -v[q]
                self._note(220.0, 0.04, 0.25, p[0])
            elif p[q] < -most + BALL and v[q] < 0:
                p[q], v[q] = -most + BALL, -v[q]
                self._note(220.0, 0.04, 0.25, p[0])
        if p[2] < -DEEP + BALL and v[2] < 0:
            p[2], v[2] = -DEEP + BALL, -v[2]
            self._note(200.0, 0.04, 0.25, p[0])
        # The bricks: one a step.
        for brick in self.bricks:
            c, h = self.box(brick)
            d = [p[q] - c[q] for q in range(3)]
            near = [max(-h[q], min(h[q], d[q])) for q in range(3)]
            if sum((d[q] - near[q]) ** 2 for q in range(3)) >= BALL * BALL:
                continue
            over = [h[q] + BALL - abs(d[q]) for q in range(3)]
            q = over.index(min(over))
            side = 1.0 if d[q] >= 0 else -1.0
            p[q] = c[q] + side * (h[q] + BALL)
            v[q] = abs(v[q]) * side
            # A brick's face is not quite true: the ball comes off it a
            # little aside, so that no return is ever the last one over.
            for o in range(2):
                v[o] += self.draw.uniform(-0.12, 0.12) * self.speed
            self._hit(brick, ball)
            break
        if self.result is not None:
            return
        # Never left sliding to and fro across the box for good.
        speed = math.sqrt(sum(c * c for c in v)) or 1.0
        if abs(v[2]) < 0.25 * speed:
            v[2] = (0.25 * speed) * (1.0 if v[2] >= 0 else -1.0)
        # The paddle.
        rel = (p[0] - self.px, p[1] - self.py, p[2])
        ahead = sum(rel[q] * n[q] for q in range(3))
        closing = sum(v[q] * n[q] for q in range(3))
        pw, ph = lv.paddle
        if closing < 0 and -0.12 < ahead <= BALL and \
                abs(sum(rel[q] * a[q] for q in range(3))) <= pw + BALL / 2 \
                and abs(sum(rel[q] * b[q] for q in range(3))) <= ph + BALL / 2:
            for q in range(3):
                v[q] -= 2 * closing * n[q]
                p[q] += (BALL - ahead) * n[q]
            self.speed = min(lv.speed * 1.6,
                             self.speed * (1.0 + lv.quicken))
            m = math.sqrt(sum(c * c for c in v)) or 1.0
            v[:] = [c / m * self.speed for c in v]
            if v[2] > -0.35 * self.speed:
                v[2] = -0.35 * self.speed
            ball.colour = self.colour
            self._note(330.0, 0.06, 0.5, p[0])
        elif p[2] > 0.45:
            ball.held = HOLD
            self._lose(_('The ball got past: %d left') % self.left())

    def _hit(self, brick: Brick, ball: Ball) -> None:
        x = ball.p[0]
        if brick.kind == MINE:
            self._gone(brick)
            self._lose(_('A mine: %d left') % self.left())
            return
        if not self.breaks(brick, ball.colour):
            self._note(150.0 if brick.kind == STEEL else 180.0, 0.05, 0.4, x)
            return
        if brick.hits > 1:
            at = self.bricks.index(brick)
            self.bricks[at] = brick._replace(hits=brick.hits - 1)
            self._note(520.0, 0.06, 0.5, x)
            return
        self._gone(brick)
        self._note(660.0 + 40.0 * (self.broken % 8), 0.09, 0.55, x)
        if brick.kind == BOMB:
            self._blast(brick)
        if not self.left():
            self.result = (True, _('Cleared'))

    def _gone(self, brick: Brick) -> None:
        if brick in self.bricks:
            self.burst.append((self.t, self.box(brick)[0]))
            self.bricks.remove(brick)
            self.broken += 1

    def _blast(self, bomb: Brick) -> None:
        self._note(90.0, 0.35, 0.8)
        for other in list(self.bricks):
            if other.kind != STEEL and abs(other.i - bomb.i) <= 1 and \
                    abs(other.j - bomb.j) <= 1 and abs(other.k - bomb.k) <= 1:
                self._gone(other)
                if other.kind == BOMB:
                    self._blast(other)


def act(run: Run, port: int) -> None:
    run.press(port)


def patches(board: Board) -> tuple:
    return (showing.patch('pluck', board.seed),)


# --- a pilot ---------------------------------------------------------------

def _arrival(run: Run, ball: Ball):
    """Where and how the ball next reaches the paddle's plane, the
    bricks left out of it: (x, y, the way it is going, seconds)."""
    lv = run.level
    p, v = list(ball.p), list(ball.v)
    dt, t = 1 / 90.0, 0.0
    while t < 6.0:
        if lv.gravity:
            v[1] -= GRAVITY * dt
        if lv.wind:
            v[0] += lv.wind * math.sin(0.7 * (run.t + t) + run.phase) * dt
        for q in range(3):
            p[q] += v[q] * dt
        for q, most in ((0, WIDE), (1, HIGH)):
            if p[q] > most - BALL and v[q] > 0:
                p[q], v[q] = most - BALL, -v[q]
            elif p[q] < -most + BALL and v[q] < 0:
                p[q], v[q] = -most + BALL, -v[q]
        if p[2] < -DEEP + BALL and v[2] < 0:
            p[2], v[2] = -DEEP + BALL, -v[2]
        t += dt
        if p[2] >= -BALL and v[2] > 0:
            break
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return p[0], p[1], [c / m for c in v], t


def _target(run: Run, start, colour: int) -> Optional[Brick]:
    """The brick to send the ball at: one that would break, near the
    straight line, with no mine on the way."""
    mines = [run.box(b)[0] for b in run.bricks if b.kind == MINE]
    best, best_cost = None, 1e9
    for b in run.bricks:
        if not must(b) and b.kind != BOMB:
            continue
        if b.order >= 0 and b.order != run.next_order():
            continue
        if any(o.i == b.i and o.j == b.j and o.k > b.k
               and not run.breaks(o, colour) and
               (o.kind in (STEEL, MINE) or o.order >= 0)
               for o in run.bricks):
            continue                 # shut in, for now
        c = run.box(b)[0]
        d = [c[q] - start[q] for q in range(3)]
        far = math.sqrt(sum(x * x for x in d)) or 1.0
        cost = math.hypot(d[0], d[1]) / far - 0.1 * b.k
        if b.kind == BOMB:
            cost += 0.3 - 0.25 * sum(
                1 for o in run.bricks if o.kind == MINE
                and abs(o.i - b.i) <= 1 and abs(o.j - b.j) <= 1
                and abs(o.k - b.k) <= 1)
        if b.colour and run.level.colours and b.colour != colour:
            cost += 0.15
        for mine in mines:
            w = [mine[q] - start[q] for q in range(3)]
            along = max(0.0, min(far, sum(w[q] * d[q] for q in range(3))
                                 / far))
            off = math.sqrt(sum((w[q] - d[q] / far * along) ** 2
                                for q in range(3)))
            if off < 0.32:
                cost += 2.0
        if cost < best_cost:
            best, best_cost = b, cost
    return best


def autopilot(run: Run) -> List[int]:
    """Gets under the ball, and tilts the paddle so that it leaves for
    a brick worth hitting; changes colour when that brick wants it."""
    if run.result is not None:
        return []
    lv = run.level
    flying = [b for b in run.balls if b.held <= 0 and b.v[2] > 0]
    held = [b for b in run.balls if b.held > 0]
    if flying:
        timed = [(_arrival(run, b), b) for b in flying]
        (x, y, way, when), ball = min(timed, key=lambda item: item[0][3])
    elif held:
        ball = min(held, key=lambda b: b.held)
        x, y, way, when = run.px, run.py, None, ball.held
    else:
        ball = max(run.balls, key=lambda b: b.p[2])
        x, y, way, when = ball.p[0], ball.p[1], None, 9.0
    pw, ph = lv.paddle
    x = max(-WIDE + pw, min(WIDE - pw, x))
    y = max(-HIGH + ph, min(HIGH - ph, y))
    ex, ey = x - run.px, y - run.py
    # Where to send it.
    target = _target(run, (x, y, 0.0), run.colour)
    want_yaw = want_pitch = 0.0
    if target is not None and (way is not None or held):
        travel = (DEEP - 0.25 - LAYER * target.k) / max(0.5, run.speed)
        c = run.box(target, run.t + when + travel)[0]
        d = [c[0] - x, c[1] - y, c[2]]
        if lv.gravity:
            d[1] += 0.5 * GRAVITY * travel * travel
        m = math.sqrt(sum(q * q for q in d)) or 1.0
        d = [q / m for q in d]
        n = d if way is None else [d[q] - way[q] for q in range(3)]
        m = math.sqrt(sum(q * q for q in n)) or 1.0
        n = [q / m for q in n]
        want_pitch = math.asin(max(-1.0, min(1.0, n[1])))
        want_yaw = math.atan2(n[0], -n[2])
        want_yaw = max(-TILT_MOST, min(TILT_MOST, want_yaw))
        want_pitch = max(-TILT_MOST, min(TILT_MOST, want_pitch))
    ty, tp = want_yaw - run.yaw, want_pitch - run.pitch
    # One port a step: whichever is the more pressing.
    reach = math.hypot(ex, ey) / PADDLE_SPEED       # seconds to get there
    turn = max(abs(ty), abs(tp)) / TILT_RATE
    slack = when - reach - turn
    close = 0.35 * min(pw, ph)
    if math.hypot(ex, ey) > close and (slack < 0.25 or turn < 0.02):
        return [_way(ex, ey)]
    if lv.colours and target is not None and target.colour \
            and target.colour != run.colour and when > 0.15:
        return [COLOUR]
    if turn > 0.015:
        if abs(ty) >= abs(tp):
            return [FACE_RIGHT if ty > 0 else FACE_LEFT]
        return [FACE_UP if tp > 0 else FACE_DOWN]
    if math.hypot(ex, ey) > 0.02:
        return [_way(ex, ey)]
    return [] if run.touched else [LEVEL]     # anything, to be served


def _way(ex: float, ey: float) -> int:
    """The move port nearest a direction."""
    best, most = LEFT, -9.0
    far = math.hypot(ex, ey) or 1.0
    for port, (mx, my) in MOVES.items():
        along = (mx * ex + my * ey) / far
        if along > most:
            best, most = port, along
    return best


def play(board: Board, pilot=autopilot, dt: float = 1 / 60.0) -> Run:
    """A whole board played by *pilot*, one port a step."""
    run = Run(board)
    while run.result is None:
        ports = pilot(run)
        port = ports[0] if ports else None
        if port in EVENTS:
            act(run, port)
            port = None
        for _k in range(2):
            run.step(dt / 2, port)
            if run.result is not None:
                break
    return run
