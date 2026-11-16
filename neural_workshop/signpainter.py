# -*- coding: utf-8 -*-
"""Sign Painter: paint a word on a hanging board, stroke by stroke.

A board hangs on two chains. The job is written above it -- "Paint
EXIT in red" -- and the letters are made of straight strokes: put the
brush down at the start of a stroke, draw it along to the end, lift.
Paint only goes on while the brush stays on the stroke; wander off it
with the brush down and you have smudged the sign. Three smudges and
it is ruined.

Keys: R, G, B and Y take up red, green, blue and yellow; Space dips the
brush when it runs dry.

The ladder:

* rungs 1-3: two or three letters, drawn faintly on the board to paint
  over; a wide brush; any colour;
* rungs 4-6: the colour named in the job;
* rungs 7-9: only the corners of each letter are marked; the brush
  runs dry and has to be dipped;
* rungs 10-12: four letters; the board swings on its chains;
* rungs 13-15: nothing is marked: you know your letters;
* rungs 16-19: five letters, and a brush that drags behind the hand;
* from rung 20: a finer brush, a wider swing, less paint on the brush
  and less time every rung.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, NamedTuple, Optional, Tuple

from . import hand as H
from .hand import Vec
from .i18n import _

RED, DIP = H.KEYS, H.KEYS + 4  # ports 14-17 colours, 18 dips
PORTS = H.KEYS + 5
EVENTS = tuple(range(PORTS))
COLOURS = (_('red'), _('green'), _('blue'), _('yellow'))
BOARD = (9.0, 3.6)             # wide and tall
STEP = 0.25                    # between the points a stroke is made of
BRUSH, SMUDGE, DONE, DRY, SPLASH = range(5)
PATCHES = ('pad', 'growl', 'bell', 'wood', 'glass')

#: Each letter as strokes on a grid two wide and three tall.
LETTERS = {
    'I': (((1, 3), (1, 0)),),
    'L': (((0, 3), (0, 0), (2, 0)),),
    'T': (((0, 3), (2, 3)), ((1, 3), (1, 0))),
    'V': (((0, 3), (1, 0), (2, 3)),),
    'N': (((0, 0), (0, 3), (2, 0), (2, 3)),),
    'Z': (((0, 3), (2, 3), (0, 0), (2, 0)),),
    'M': (((0, 0), (0, 3), (1, 1.5), (2, 3), (2, 0)),),
    'W': (((0, 3), (0.5, 0), (1, 1.5), (1.5, 0), (2, 3)),),
    'E': (((2, 3), (0, 3), (0, 0), (2, 0)), ((0, 1.5), (1.5, 1.5))),
    'F': (((2, 3), (0, 3), (0, 0)), ((0, 1.5), (1.5, 1.5))),
    'H': (((0, 3), (0, 0)), ((2, 3), (2, 0)), ((0, 1.5), (2, 1.5))),
    'X': (((0, 3), (2, 0)), ((2, 3), (0, 0))),
    'A': (((0, 0), (1, 3), (2, 0)), ((0.5, 1.5), (1.5, 1.5))),
    'K': (((0, 3), (0, 0)), ((2, 3), (0, 1.5), (2, 0))),
    'Y': (((0, 3), (1, 1.5), (2, 3)), ((1, 1.5), (1, 0))),
    'O': (((0.5, 3), (1.5, 3), (2, 2.3), (2, 0.7), (1.5, 0), (0.5, 0),
           (0, 0.7), (0, 2.3), (0.5, 3)),),
}
WORDS = (('IT', 'AT', 'INN', 'ALE', 'HAY', 'TEA', 'HAT', 'WAX'),
         ('EXIT', 'TENT', 'MILK', 'MINE', 'TAXI', 'FEET', 'HALT'),
         ('ANVIL', 'HOTEL', 'KNIFE', 'MELON', 'WHEAT'))


class Grade(NamedTuple):
    rung: int
    length: int                # 0, 1 or 2: which list of words
    brush: float               # how near the stroke the brush must stay
    colour: bool
    guide: str                 # 'outline', 'corners' or 'none'
    load: int                  # points a dip paints, 0 for no limit
    swing: float               # degrees
    drag: float                # seconds the brush lags
    seconds: float             # per point


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    top = max(0, r - 20)
    return Grade(
        rung=r, length=0 if r < 10 else 1 if r < 16 else 2,
        brush=(0.34 if r < 7 else 0.28 if r < 13 else 0.24 if r < 20
               else max(0.16, 0.23 - 0.002 * top)),
        colour=r >= 4,
        guide='outline' if r < 7 else 'corners' if r < 13 else 'none',
        load=0 if r < 7 else 26 if r < 20 else max(12, 24 - top // 2),
        swing=0.0 if r < 10 else 9.0 if r < 20 else min(22.0, 10.0
                                                       + 0.4 * top),
        drag=0.0 if r < 16 else 0.08,
        seconds=(0.9 if r < 7 else 0.75 if r < 13 else 0.65 if r < 20
                 else max(0.36, 0.6 - 0.008 * top)))


class Sign(NamedTuple):
    level: Grade
    word: str
    colour: int                # -1 for any
    strokes: Tuple[Tuple[Tuple[float, float], ...], ...]   # points, on
    #                                                        the board
    corners: Tuple[Tuple[float, float], ...]
    order: str
    seconds: float
    seed: int


def lay_out(word: str):
    """The strokes of *word* on the board, as points STEP apart, and
    the corners of its letters."""
    n = len(word)
    size = min(1.0, (BOARD[0] - 1.0) / (2.8 * n - 0.8))
    left = (BOARD[0] - size * (2.8 * n - 0.8)) / 2
    low = (BOARD[1] - 3 * size) / 2
    strokes, corners = [], []
    for k, ch in enumerate(word):
        ox = left + 2.8 * size * k
        for line in LETTERS[ch]:
            pts = [(ox + x * size, low + y * size) for x, y in line]
            corners += pts
            out = [pts[0]]
            for a, b in zip(pts, pts[1:]):
                d = math.hypot(b[0] - a[0], b[1] - a[1])
                steps = max(1, int(round(d / STEP)))
                out += [(a[0] + (b[0] - a[0]) * j / steps,
                         a[1] + (b[1] - a[1]) * j / steps)
                        for j in range(1, steps + 1)]
            strokes.append(tuple(out))
    return tuple(strokes), tuple(corners)


def build(level: Grade, draw: random.Random) -> Optional[Sign]:
    word = draw.choice(WORDS[level.length])
    colour = draw.randrange(len(COLOURS)) if level.colour else -1
    strokes, corners = lay_out(word)
    order = (_('Paint %s in %s.') % (word, COLOURS[colour]) if colour >= 0
             else _('Paint %s.') % word)
    points = sum(len(s) for s in strokes)
    return Sign(level, word, colour, strokes, corners, order,
                8.0 + points * level.seconds + 1.2 * len(strokes),
                draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Sign:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng)


class Run(H.HandRun):
    def __init__(self, sign: Sign) -> None:
        super().__init__(sign.seconds)
        self.sign, self.level = sign, sign.level
        self.stroke = 0
        self.point = 0                 # the next point of it to paint
        self.colour = -1 if sign.level.colour else 0
        self.paint = sign.level.load or 10 ** 6
        self.smudges = 0
        self.brush: Optional[Tuple[float, float]] = None   # on the board
        self.smudged_now = False
        self.sound_at = 0.0

    # --- the board
    def swing(self) -> float:
        return math.radians(self.level.swing) * math.sin(self.t * 1.25)

    def frame(self) -> Tuple[Vec, Vec]:
        a = self.swing()
        return (math.cos(a), 0.0, -math.sin(a)), (math.sin(a), 0.0,
                                                  math.cos(a))

    def world(self, u: float, v: float, out: float = 0.0) -> Vec:
        r, n = self.frame()
        u -= BOARD[0] / 2
        return (u * r[0] + out * n[0], v, u * r[2] + out * n[2])

    def view(self):
        return H.lens((0.0, 1.8, 10.0), (0.0, 1.8, 0.0), 900.0, 500.0, 290.0)

    def see(self, u: float, v: float, out: float = 0.0):
        return self.view().see(self.world(u, v, out))

    def under(self) -> Optional[Tuple[float, float]]:
        r, n = self.frame()
        p = H.on_plane(self.view(), self.hand.x, self.hand.y,
                       (0.0, 0.0, 0.0), n)
        if p is None:
            return None
        return H.dot(p, r) + BOARD[0] / 2, p[1]

    @property
    def goal(self) -> Optional[Tuple[float, float]]:
        strokes = self.sign.strokes
        if self.stroke >= len(strokes):
            return None
        return strokes[self.stroke][self.point]

    # --- the hand
    def press(self) -> None:
        if self.result is None and not self.hand.down:
            self.hand.down = True
            self.brush = self.under()
            self.smudged_now = False

    def release(self) -> None:
        self.hand.down = False
        self.brush = None

    def key(self, port: int) -> None:
        if self.result is not None or self.hand.down:
            return
        if RED <= port < RED + 4:
            self.colour = port - RED
        elif port == DIP:
            self.paint = self.level.load or 10 ** 6
            self.note(0.15, 600.0, SPLASH, 0.4)

    def _smudge(self, why: str) -> None:
        self.smudges += 1
        self.smudged_now = True
        self.note(0.25, 120.0, SMUDGE, 0.5)
        if self.smudges >= 3:
            self.result = (False, why)

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        level = self.level
        goal = self.goal
        at = self.under() if self.hand.down else None
        if at is not None and goal is not None:
            if self.brush is None or not level.drag:
                self.brush = at
            else:
                k = min(1.0, dt / level.drag)
                self.brush = (self.brush[0] + (at[0] - self.brush[0]) * k,
                              self.brush[1] + (at[1] - self.brush[1]) * k)
            bx, by = self.brush
            on_board = 0 <= bx <= BOARD[0] and 0 <= by <= BOARD[1]
            line = self.sign.strokes[self.stroke]
            last = line[max(0, self.point - 1)]
            off = _from_segment((bx, by), last, goal)
            if on_board and not self.smudged_now:
                if self.paint <= 0 or self.colour < 0:
                    if self.t >= self.sound_at:
                        self.sound_at = self.t + 0.3
                        self.note(0.08, 900.0, DRY, 0.3)
                elif self.point and off > 2.5 * level.brush:
                    self._smudge(_('The sign is a mess'))
                elif self.sign.colour >= 0 and \
                        self.colour != self.sign.colour:
                    self._smudge(_('That was the wrong colour'))
                elif math.hypot(bx - goal[0], by - goal[1]) <= level.brush:
                    self.point += 1
                    self.paint -= 1
                    if self.t >= self.sound_at:
                        self.sound_at = self.t + 0.1
                        self.note(0.12, 240.0 + 20.0 * self.point, BRUSH,
                                  0.25)
                    if self.point >= len(line):
                        self.stroke, self.point = self.stroke + 1, 0
                        self.note(0.1, 880.0, DONE, 0.3)
                        if self.stroke >= len(self.sign.strokes):
                            self.result = (True, _('A handsome sign'))
        if self.result is None and self.t >= self.end:
            self.result = (False, _('The paint dried on the brush'))


def _from_segment(p, a, b) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    d2 = vx * vx + vy * vy
    u = 0.0 if d2 < 1e-9 else max(0.0, min(1.0, (
        (p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / d2))
    return math.hypot(p[0] - a[0] - u * vx, p[1] - a[1] - u * vy)


act = H.act


def autopilot(run: Run) -> List[int]:
    """Take the colour, keep the brush wet, and draw each stroke from
    its start: one port a step."""
    goal = run.goal
    if run.result is not None or goal is None:
        return []
    hand, sign = run.hand, run.sign
    want = sign.colour if sign.colour >= 0 else 0
    if run.colour != want or run.paint <= 0:
        if hand.down:
            return [H.RELEASE]
        return [RED + want] if run.colour != want else [DIP]
    q = run.see(*goal)
    if not hand.down:
        if run.point:                           # pick the stroke up again
            q = run.see(*sign.strokes[run.stroke][run.point - 1])
        move = H.toward(hand, q[0], q[1], tol=3.0)
        return [move] if move is not None else [H.PRESS]
    if run.smudged_now:
        return [H.RELEASE]
    move = H.toward(hand, q[0], q[1], tol=2.6)
    return [move] if move is not None else []


def play(sign: Sign, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(sign), pilot, EVENTS, act, dt)
