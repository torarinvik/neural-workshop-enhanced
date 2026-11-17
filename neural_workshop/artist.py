# -*- coding: utf-8 -*-
"""The Artist: copy a picture with a paint box.

A picture on the left, a blank canvas on the right and the tools of a
plain paint program: pencil, brush, line, box, filled box, filled
round, fill, a colour picker, undo. Draw the picture as closely as you
can, then say it is done.

How alike the two are is measured, not judged by eye. The canvas's
error is the squared difference in colour, pixel by pixel; it is set
against the error of the best a *blank* answer could do -- the whole
canvas in the picture's own average colour:

    alike = 1 - error(canvas) / error(flat average)

So a canvas left blank, or filled with any one colour, scores nought or
less, and a perfect copy scores 1. A rung is passed at its own mark,
which starts at a quarter -- a block roughly the right size in roughly the
right place is enough. On the rungs below 13 both pictures are blurred
a little before they are compared, and the canvas is tried a pixel over
in every direction and the best fit taken, so a pixel's slip costs
little or nothing.

The ladder:

* rungs 1-3: 8 by 8 pixels, one filled block in one of three colours;
* rungs 4-6: 12 by 12, two shapes, two colours;
* rungs 7-9: 16 by 16, three shapes: blocks, rounds, lines;
* rungs 10-12: 24 by 24, four shapes, five colours, outlines too;
* rungs 13-15: 32 by 32, five or six shapes over one another;
* rungs 16-18: 48 by 48, a landscape in twelve flat colours;
* rungs 19-24: 64 by 64, a photograph in sixteen colours;
* rungs 25-29: 96 by 96, in thirty-two;
* from rung 30: 128 by 128 in full colour, any colour to be had by
  picking it from the picture; the mark rises a hundredth a rung from
  four fifths toward nineteen parts in twenty.

Where no photographs are to hand the upper rungs paint their own: a
shaded landscape with texture, never the same twice.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import colorsys
import math
import random
from typing import Callable, List, NamedTuple, Optional, Sequence, Tuple

from .i18n import _

RGB = Tuple[int, int, int]
PAPER: RGB = (255, 255, 255)
TOOLS = ('pencil', 'brush', 'line', 'box', 'block', 'round', 'fill', 'pick')
WIDTHS = (1, 2, 3, 5)
PORTS = 15
(P_LEFT, P_RIGHT, P_DOWN, P_UP, P_LEFT_FAR, P_RIGHT_FAR, P_DOWN_FAR, P_UP_FAR,
 P_PEN, P_TOOL, P_COLOUR, P_PICK, P_UNDO, P_DONE, P_WIDTH) = range(PORTS)


class Grade(NamedTuple):
    rung: int
    size: int            # the canvas is size x size
    colours: int         # in the palette, the paper among them
    kind: str            # 'shapes', 'scene' or 'photo'
    shapes: Tuple[int, int]
    need: float          # how alike passes
    slack: int           # pixels of blur, and of slip forgiven, in comparing
    full: bool           # the picture keeps every colour


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 4:
        return Grade(r, 8, 4, 'shapes', (1, 1), 0.25, 1, False)
    if r < 7:
        return Grade(r, 12, 3, 'shapes', (2, 2), 0.55, 1, False)
    if r < 10:
        return Grade(r, 16, 4, 'shapes', (3, 3), 0.6, 1, False)
    if r < 13:
        return Grade(r, 24, 5, 'shapes', (4, 4), 0.65, 1, False)
    if r < 16:
        return Grade(r, 32, 7, 'shapes', (5, 6), 0.7, 0, False)
    if r < 19:
        return Grade(r, 48, 12, 'scene', (0, 0), 0.6, 0, False)
    if r < 25:
        return Grade(r, 64, 16, 'photo', (0, 0), 0.6, 0, False)
    if r < 30:
        return Grade(r, 96, 32, 'photo', (0, 0), 0.7, 0, False)
    return Grade(r, 128, 24, 'photo', (0, 0), min(0.95, 0.8 + 0.01 * (r - 30)),
                 0, True)


class Op(NamedTuple):
    """One stroke: a tool, a colour, from one pixel to another."""
    tool: str
    colour: RGB
    x0: int
    y0: int
    x1: int
    y1: int
    width: int = 1


class Puzzle(NamedTuple):
    level: Grade
    size: int
    palette: Tuple[RGB, ...]
    target: bytes                # size*size RGB, the bottom row first
    shapes: Tuple[Op, ...]       # how a picture of shapes was made
    question: str


# --- pixels ------------------------------------------------------------------

def blank(size: int, colour: RGB = PAPER) -> bytearray:
    return bytearray(bytes(colour) * (size * size))


def get(pix, size: int, x: int, y: int) -> RGB:
    k = (y * size + x) * 3
    return (pix[k], pix[k + 1], pix[k + 2])


def _dot(pix, size: int, x: int, y: int, colour: RGB, radius: int) -> None:
    for yy in range(max(0, y - radius), min(size, y + radius + 1)):
        for xx in range(max(0, x - radius), min(size, x + radius + 1)):
            if (xx - x) ** 2 + (yy - y) ** 2 <= radius * radius + radius:
                k = (yy * size + xx) * 3
                pix[k:k + 3] = bytes(colour)


def _stroke(pix, size, x0, y0, x1, y1, colour, radius) -> None:
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx - dy
    while True:
        _dot(pix, size, x0, y0, colour, radius)
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def flood(pix, size: int, x: int, y: int, colour: RGB) -> None:
    old = get(pix, size, x, y)
    if old == tuple(colour):
        return
    new, was = bytes(colour), bytes(old)
    todo = [(x, y)]
    while todo:
        x, y = todo.pop()
        k = (y * size + x) * 3
        if pix[k:k + 3] != was:
            continue
        # The whole run this pixel is in, then the rows above and below.
        a = x
        while a > 0 and pix[k - 3:k] == was:
            a -= 1
            k -= 3
        b = x
        k = (y * size + x) * 3
        while b < size - 1 and pix[k + 3:k + 6] == was:
            b += 1
            k += 3
        for xx in range(a, b + 1):
            k = (y * size + xx) * 3
            pix[k:k + 3] = new
            if y > 0 and pix[k - size * 3:k - size * 3 + 3] == was:
                todo.append((xx, y - 1))
            if y < size - 1 and pix[k + size * 3:k + size * 3 + 3] == was:
                todo.append((xx, y + 1))


def paint(pix, size: int, op: Op) -> None:
    """Do one stroke to the pixels."""
    clamp = lambda v: max(0, min(size - 1, int(v)))   # noqa: E731
    x0, y0, x1, y1 = clamp(op.x0), clamp(op.y0), clamp(op.x1), clamp(op.y1)
    c = tuple(op.colour)
    if op.tool == 'pencil':
        _stroke(pix, size, x0, y0, x1, y1, c, 0)
    elif op.tool in ('brush', 'line'):
        _stroke(pix, size, x0, y0, x1, y1, c,
                op.width if op.tool == 'brush' else op.width // 2)
    elif op.tool == 'fill':
        flood(pix, size, x1, y1, c)
    else:
        a, b = min(x0, x1), max(x0, x1)
        lo, hi = min(y0, y1), max(y0, y1)
        if op.tool == 'block':
            row = bytes(c) * (b - a + 1)
            for y in range(lo, hi + 1):
                k = (y * size + a) * 3
                pix[k:k + len(row)] = row
        elif op.tool == 'box':
            for x in range(a, b + 1):
                _dot(pix, size, x, lo, c, 0)
                _dot(pix, size, x, hi, c, 0)
            for y in range(lo, hi + 1):
                _dot(pix, size, a, y, c, 0)
                _dot(pix, size, b, y, c, 0)
        elif op.tool == 'round':
            cx, cy = (a + b) / 2.0, (lo + hi) / 2.0
            rx, ry = (b - a) / 2.0 + 0.5, (hi - lo) / 2.0 + 0.5
            for y in range(lo, hi + 1):
                for x in range(a, b + 1):
                    if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                        k = (y * size + x) * 3
                        pix[k:k + 3] = bytes(c)


# --- how alike ---------------------------------------------------------------

def _blur(pix, size: int, radius: int) -> List[float]:
    vals = [float(v) for v in pix]
    if radius <= 0:
        return vals
    for step in (3, size * 3):
        out = vals[:]
        for y in range(size):
            for x in range(size):
                at = x if step == 3 else y
                k = (y * size + x) * 3
                for ch in range(3):
                    total, n = 0.0, 0
                    for d in range(-radius, radius + 1):
                        if 0 <= at + d < size:
                            total += vals[k + ch + d * step]
                            n += 1
                    out[k + ch] = total / n
        vals = out
    return vals


def error(a, b, size: int, slack: int = 0) -> float:
    fa, fb = _blur(a, size, slack), _blur(b, size, slack)
    return sum((u - v) ** 2 for u, v in zip(fa, fb))


def average(pix) -> RGB:
    n = len(pix) // 3
    return tuple(int(round(sum(pix[ch::3]) / float(n))) for ch in range(3))


def alike(p: Puzzle, pix) -> float:
    """How alike the canvas is to the picture: 1 a perfect copy, nought
    no better than one flat colour."""
    return 1.0 - fit(p, pix) / flat_error(p)


def fit(p: Puzzle, pix) -> float:
    """The canvas's error against the picture -- below rung 13 tried a
    pixel over in every direction, and the best taken."""
    reach = 1 if p.level.slack else 0
    return min(error(shifted(pix, p.size, dx, dy), p.target, p.size,
                     p.level.slack)
               for dx in range(-reach, reach + 1)
               for dy in range(-reach, reach + 1))


def shifted(pix, size: int, dx: int, dy: int):
    """The canvas moved over by (dx, dy), paper where it came from."""
    if not dx and not dy:
        return pix
    out = blank(size)
    for y in range(max(0, dy), min(size, size + dy)):
        a, b = max(0, dx), min(size, size + dx)
        k = (y * size + a) * 3
        j = ((y - dy) * size + a - dx) * 3
        out[k:k + (b - a) * 3] = pix[j:j + (b - a) * 3]
    return out


_FLAT = {}


def flat_error(p: Puzzle) -> float:
    """The least error any canvas of one flat colour can have: the
    picture's average, or whichever colour of the palette does best,
    fitted as any canvas is."""
    key = (p.target, p.level.slack)
    if key not in _FLAT:
        if len(_FLAT) > 64:
            _FLAT.clear()
        _FLAT[key] = max(1e-9, min(
            fit(p, blank(p.size, colour))
            for colour in (average(p.target),) + tuple(p.palette)))
    return _FLAT[key]


# --- the easel ---------------------------------------------------------------

class Easel:
    """A canvas, the tool in hand, and a cursor for whoever has no
    mouse."""

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.size = puzzle.size
        self.pix = blank(self.size)
        self.tool = 'pencil'
        self.colour: RGB = puzzle.palette[1 % len(puzzle.palette)]
        self.width = 1
        self.history: List[bytes] = []
        self.anchor: Optional[Tuple[int, int]] = None
        self.last: Optional[Tuple[int, int]] = None
        self.before: Optional[bytes] = None
        self.cx = self.cy = self.size // 2
        self.pen = False
        self.strokes = 0

    def _inside(self, x: int, y: int) -> Tuple[int, int]:
        return max(0, min(self.size - 1, int(x))), \
            max(0, min(self.size - 1, int(y)))

    def press(self, x: int, y: int) -> None:
        x, y = self._inside(x, y)
        if self.tool == 'pick':
            self.colour = get(self.pix, self.size, x, y)
            return
        self.before = bytes(self.pix)
        self.history.append(self.before)
        del self.history[:-30]
        self.strokes += 1
        self.anchor = self.last = (x, y)
        self.drag(x, y)

    def drag(self, x: int, y: int) -> None:
        if self.anchor is None:
            return
        x, y = self._inside(x, y)
        if self.tool in ('pencil', 'brush'):
            paint(self.pix, self.size, Op(self.tool, self.colour, self.last[0],
                                          self.last[1], x, y, self.width))
        else:
            # A shape is drawn afresh from where it began.
            self.pix[:] = self.before
            paint(self.pix, self.size, Op(self.tool, self.colour,
                                          self.anchor[0], self.anchor[1], x, y,
                                          self.width))
        self.last = (x, y)

    def release(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        if self.anchor is not None and x is not None:
            self.drag(x, y)
        self.anchor = self.last = self.before = None

    def pick_from_picture(self, x: int, y: int) -> None:
        x, y = self._inside(x, y)
        self.colour = get(self.puzzle.target, self.size, x, y)

    def undo(self) -> None:
        self.release()
        self.pen = False
        if self.history:
            self.pix[:] = self.history.pop()

    def clear(self) -> None:
        self.release()
        self.pen = False
        self.history.append(bytes(self.pix))
        self.pix[:] = blank(self.size)

    def do(self, op: Op) -> None:
        """One whole stroke, as a mouse would make it."""
        self.tool, self.colour, self.width = op.tool, tuple(op.colour), op.width
        self.press(op.x0, op.y0)
        self.release(op.x1, op.y1)

    def alike(self) -> float:
        return alike(self.puzzle, self.pix)

    # --- without a mouse -------------------------------------------------

    def far(self) -> int:
        return max(2, self.size // 8)

    def act(self, port: int) -> bool:
        """One port; True when it says the picture is done."""
        moves = {P_LEFT: (-1, 0), P_RIGHT: (1, 0), P_DOWN: (0, -1), P_UP: (0, 1)}
        if port in moves or port - 4 in moves:
            dx, dy = moves[port] if port in moves else moves[port - 4]
            step = 1 if port in moves else self.far()
            self.cx, self.cy = self._inside(self.cx + dx * step,
                                            self.cy + dy * step)
            if self.pen:
                self.drag(self.cx, self.cy)
        elif port == P_PEN:
            if self.pen:
                self.release(self.cx, self.cy)
                self.pen = False
            else:
                self.press(self.cx, self.cy)
                self.pen = self.anchor is not None
        elif port == P_TOOL:
            self.release()
            self.pen = False
            self.tool = TOOLS[(TOOLS.index(self.tool) + 1) % len(TOOLS)]
        elif port == P_COLOUR:
            pal = self.puzzle.palette
            k = pal.index(self.colour) if self.colour in pal else -1
            self.colour = pal[(k + 1) % len(pal)]
        elif port == P_PICK:
            self.pick_from_picture(self.cx, self.cy)
        elif port == P_UNDO:
            self.undo()
        elif port == P_WIDTH:
            self.width = WIDTHS[(WIDTHS.index(self.width) + 1) % len(WIDTHS)]
        elif port == P_DONE:
            self.release()
            self.pen = False
            return True
        return False


def ports_for(easel: Easel, op: Op) -> List[int]:
    """The ports that make *op* from where the easel stands (its pen
    up), for a pilot with no mouse."""
    out: List[int] = []
    out += [P_TOOL] * ((TOOLS.index(op.tool) - TOOLS.index(easel.tool))
                       % len(TOOLS))
    pal = easel.puzzle.palette
    if tuple(op.colour) != tuple(easel.colour):
        if tuple(op.colour) in pal:
            k = pal.index(easel.colour) if easel.colour in pal else -1
            out += [P_COLOUR] * ((pal.index(tuple(op.colour)) - k) % len(pal))
        else:
            raise ValueError('a colour not in the palette')
    out += [P_WIDTH] * ((WIDTHS.index(op.width) - WIDTHS.index(easel.width))
                        % len(WIDTHS))
    far = easel.far()

    def go(x, y, tx, ty):
        steps: List[int] = []
        for at, to, back, on in ((x, tx, P_LEFT, P_RIGHT), (y, ty, P_DOWN, P_UP)):
            d = to - at
            port = on if d > 0 else back
            # Long steps are stopped by the edge, so only where they fit.
            steps += [port + 4] * (abs(d) // far) + [port] * (abs(d) % far)
        return steps

    def trace(x, y, tx, ty):
        # A freehand stroke goes where the cursor goes: so step by step
        # along the straight line, never the long way round the corner.
        steps: List[int] = []
        dx, dy = abs(tx - x), abs(ty - y)
        px = P_RIGHT if tx > x else P_LEFT
        py = P_UP if ty > y else P_DOWN
        err = dx - dy
        while dx or dy:
            if dx and (not dy or err >= 0):
                steps.append(px)
                dx -= 1
                err -= 2 * abs(ty - y)
            else:
                steps.append(py)
                dy -= 1
                err += 2 * abs(tx - x)
        return steps

    out += go(easel.cx, easel.cy, op.x0, op.y0) + [P_PEN]
    way = trace if op.tool in ('pencil', 'brush') else go
    out += way(op.x0, op.y0, op.x1, op.y1) + [P_PEN]
    return out


# --- pictures ----------------------------------------------------------------

def _hue(h: float, s: float = 0.75, v: float = 0.9) -> RGB:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def _shapes(level: Grade, draw: random.Random) -> Tuple[Tuple[RGB, ...],
                                                        Tuple[Op, ...]]:
    n = level.size
    h0 = draw.random()
    inks = [_hue(h0 + k / float(level.colours - 1) + draw.uniform(-0.03, 0.03),
                 draw.uniform(0.6, 0.9), draw.uniform(0.55, 0.95))
            for k in range(level.colours - 1)]
    palette = (PAPER,) + tuple(inks)
    tools = (('block',) if level.rung < 4 else ('block', 'line') if level.rung < 7
             else ('block', 'round', 'line') if level.rung < 10
             else ('block', 'round', 'line', 'box', 'brush'))
    ops: List[Op] = []
    count = draw.randint(*level.shapes)
    for k in range(count):
        tool = draw.choice(tools) if k else tools[0]
        # Low down any of the inks may be the one: which, is part of
        # the looking.
        colour = draw.choice(inks) if count == 1 else inks[k % len(inks)]
        if tool in ('block', 'round', 'box'):
            # Never so small that a pixel out is half of it.
            least = max(4, n // 4)
            w = draw.randint(least, max(least, n * 2 // 3))
            h = draw.randint(least, max(least, n * 2 // 3))
            x = draw.randint(0, n - w)
            y = draw.randint(0, n - h)
            ops.append(Op(tool, colour, x, y, x + w - 1, y + h - 1, 1))
        else:
            width = 1 if n < 16 else draw.choice((1, 2)) if tool == 'line' else 2
            while True:
                x0, y0 = draw.randrange(n), draw.randrange(n)
                x1, y1 = draw.randrange(n), draw.randrange(n)
                if abs(x1 - x0) + abs(y1 - y0) >= n // 2:
                    break
            ops.append(Op(tool, colour, x0, y0, x1, y1, width))
    return palette, tuple(ops)


def landscape(size: int, draw: random.Random, rough: bool = False) -> bytearray:
    """A painted landscape: sky, sun, hills, ground and trees, shaded;
    with texture when *rough*."""
    sky_top, sky_low = _hue(draw.uniform(0.52, 0.66), 0.55, 0.95), \
        _hue(draw.uniform(0.05, 0.6), 0.2, 1.0)
    ground = _hue(draw.uniform(0.2, 0.38), 0.6, 0.6)
    horizon = draw.uniform(0.3, 0.5)
    sun = (draw.uniform(0.15, 0.85), draw.uniform(horizon + 0.2, 0.9),
           draw.uniform(0.06, 0.11))
    hills = [(draw.uniform(0.05, 0.18), draw.uniform(1.5, 4.0),
              draw.uniform(0, 6.3), _hue(draw.uniform(0.25, 0.45), 0.45,
                                         draw.uniform(0.35, 0.6)))
             for _k in range(draw.randint(1, 3))]
    trees = [(draw.random(), draw.uniform(0.05, horizon - 0.05),
              draw.uniform(0.05, 0.1), _hue(draw.uniform(0.25, 0.4), 0.7,
                                            draw.uniform(0.3, 0.5)))
             for _k in range(draw.randint(2, 5))]
    grain = [draw.uniform(-1, 1) for _k in range(257)]

    def mix(a, b, t):
        return tuple(a[k] + (b[k] - a[k]) * t for k in range(3))

    pix = bytearray(size * size * 3)
    for j in range(size):
        y = (j + 0.5) / size
        for i in range(size):
            x = (i + 0.5) / size
            if y > horizon:
                c = mix(sky_low, sky_top, (y - horizon) / (1 - horizon))
                d = math.hypot(x - sun[0], y - sun[1])
                if d < sun[2]:
                    c = (255, 240, 170)
                elif rough:
                    c = mix(c, (255, 240, 200), max(0.0, 1 - d / 0.4) ** 2 * 0.6)
            else:
                c = mix(ground, mix(ground, (255, 255, 200), 0.35),
                        y / horizon)
            for k, (amp, freq, ph, col) in enumerate(hills):
                top = horizon + amp * (0.6 + 0.4 * math.sin(freq * x * 6.28 + ph))
                if horizon - 0.04 * k <= y < top:
                    c = mix(col, mix(col, (0, 0, 0), 0.4),
                            (top - y) / max(top - horizon, 1e-6)) \
                        if rough else col
            for tx, ty, tr, col in trees:
                if abs(x - tx) < tr * 0.12 and ty <= y < ty + tr:
                    c = (95, 65, 40)
                d = math.hypot(x - tx, (y - ty - tr * 1.5))
                if d < tr:
                    c = mix(col, mix(col, (255, 255, 160), 0.5),
                            max(0.0, (y - ty - tr * 1.5) / tr) * 0.6
                            + (0.2 if x < tx else 0.0)) if rough else col
            if rough:
                g = grain[(i * 31 + j * 17) % 257] * 9
                c = tuple(v + g for v in c)
            k = (j * size + i) * 3
            pix[k:k + 3] = bytes(max(0, min(255, int(v))) for v in c)
    return pix


def quantise(pix, colours: int, draw: random.Random
             ) -> Tuple[Tuple[RGB, ...], bytearray]:
    """The picture in *colours* flat colours (found by clustering a
    sample of its pixels), and those colours."""
    n = len(pix) // 3
    sample = [tuple(pix[k * 3:k * 3 + 3])
              for k in draw.sample(range(n), min(n, 1200))]
    centres = [list(c) for c in draw.sample(sample, min(colours, len(sample)))]
    for _round in range(6):
        sums = [[0, 0, 0, 0] for _c in centres]
        for r, g, b in sample:
            best = min(range(len(centres)), key=lambda k: (
                (centres[k][0] - r) ** 2 + (centres[k][1] - g) ** 2
                + (centres[k][2] - b) ** 2))
            s = sums[best]
            s[0] += r
            s[1] += g
            s[2] += b
            s[3] += 1
        for c, s in zip(centres, sums):
            if s[3]:
                c[:] = [s[0] / s[3], s[1] / s[3], s[2] / s[3]]
    palette = []
    for c in centres:
        rgb = tuple(int(round(v)) for v in c)
        if rgb not in palette:
            palette.append(rgb)
    out = bytearray(len(pix))
    memo = {}
    for k in range(n):
        key = bytes(pix[k * 3:k * 3 + 3])
        if key not in memo:
            r, g, b = key
            memo[key] = bytes(min(palette, key=lambda c: (
                (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2)))
        out[k * 3:k * 3 + 3] = memo[key]
    return tuple(palette), out


Photo = Callable[[int, random.Random], Optional[bytes]]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None,
         photo: Optional[Photo] = None) -> Puzzle:
    """A picture to copy. *photo(size, draw)* gives a photograph's
    pixels (size x size RGB, bottom row first) or None; without one the
    upper rungs paint a landscape."""
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    draw = random.Random(seed)
    level = grade(rung)
    n = level.size
    q = _('Copy the picture, then say it is done.')
    if level.kind == 'shapes':
        for _attempt in range(200):
            palette, ops = _shapes(level, draw)
            pix = blank(n)
            for op in ops:
                paint(pix, n, op)
            # Every shape must show, and none fill the whole canvas.
            seen = {bytes(pix[k:k + 3]) for k in range(0, len(pix), 3)}
            if len(seen) == len({bytes(o.colour) for o in ops}) + 1:
                return Puzzle(level, n, palette, bytes(pix), ops, q)
        raise RuntimeError('no picture for rung %d' % rung)
    pix = None
    if level.kind == 'photo' and photo is not None:
        got = photo(n, draw)
        if got is not None and len(got) == n * n * 3:
            pix = bytearray(got)
    if pix is None:
        pix = landscape(n, draw, rough=level.kind == 'photo')
    palette, flat = quantise(pix, level.colours, draw)
    if not level.full:
        pix = flat
    if PAPER not in palette:
        palette = (PAPER,) + palette
    return Puzzle(level, n, palette, bytes(pix), (), q)


def solve(p: Puzzle) -> List[Op]:
    """Strokes that copy the picture: the shapes it was made of, or
    else every row in runs of the nearest colour of the palette."""
    if p.shapes:
        return list(p.shapes)
    n = p.size
    memo = {}

    def near(k):
        key = p.target[k:k + 3]
        if key not in memo:
            r, g, b = key
            memo[key] = min(p.palette, key=lambda c: (
                (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2))
        return memo[key]

    ops = []
    for y in range(n):
        x = 0
        while x < n:
            c = near((y * n + x) * 3)
            x1 = x
            while x1 + 1 < n and near((y * n + x1 + 1) * 3) == c:
                x1 += 1
            if c != PAPER:
                ops.append(Op('pencil', c, x, y, x1, y, 1))
            x = x1 + 1
    return ops


def replay(p: Puzzle, ops: Sequence[Op]) -> Easel:
    easel = Easel(p)
    for op in ops:
        easel.do(op)
    return easel
