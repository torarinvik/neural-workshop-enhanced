# -*- coding: utf-8 -*-
"""Buzz Wire: carry the cursor along a bent wire without touching it.

The carnival game, flattened: a corridor winds across the screen from a
start pad to an end pad, and the job is to take the cursor the whole way
without touching the walls. One graze and the round buzzes out. There is
nothing to remember and nothing to identify — the entire task is a hand
held steady through a bend, which is the one motor regime nothing else
in the workshop isolates. Pursuit is a chase against something built to
break prediction; this is the opposite: the world stands perfectly
still, and every error on the screen is the learner's own.

The score is where the buzz happened: a cleared round is worth the whole
wire, a touched one is worth the share of it travelled first. That makes
the feedback dense in exactly the way a steering learner needs — a buzz
two bends in and a buzz at the last gate are different numbers — while
what is *paid* remains one verdict per round.

Difficulty is three independent axes, each a rung of the classic game:
how narrow the corridor is, how many bends the wire takes, and how long
the round allows. A wide straight corridor is barely more than holding
still; a narrow eight-bend wire against the clock is the fairground
game with the prize nobody wins. The adaptive option narrows the
corridor five percent on a clear and relaxes it five percent on a buzz,
so a run settles onto a precise width — and the width it settles at is
itself a score.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band
from ..i18n import _

#: The adaptive width multiplier's range and step. Five percent a round
#: settles onto a frontier rather than oscillating over it; the floor is
#: a corridor barely wider than the cursor and the ceiling is a corridor
#: nobody could fall out of.
NARROWEST, WIDEST = 0.35, 2.2
STEP_IN, STEP_OUT = 0.95, 1.05

#: How far one keyboard or port step moves the cursor, in window
#: heights. The same step Pursuit uses, so a learner that mastered
#: nudging there brings the identical motor vocabulary here.
CURSOR_STEP = 0.012

#: The drawn cursor dot, in window heights. Fixed on purpose: corridor
#: width is a difficulty dial and the cursor is not, so narrowing the
#: run changes the track rather than the hand.
CURSOR_RADIUS = 0.008

#: Where the wire may go, as fractions of the window. The lower edge
#: stays clear of the verdict band even at the widest corridor the
#: ladder can deal, and the clamp in :meth:`BuzzWire._wire_pixels` is
#: what enforces that against a resize.
SPAN_X = (0.10, 0.90)
SPAN_Y = (0.36, 0.84)

#: The smallest vertical jog a bend may take, as a fraction of the
#: window height. Below this a "bend" is a wiggle the corridor width
#: swallows and the rung is easier than its number says.
LEAST_JOG = 0.16

#: Arrow keys to cursor steps. Steering without a mouse.
ARROWS = {key.UP: (0.0, 1.0), key.DOWN: (0.0, -1.0),
          key.LEFT: (-1.0, 0.0), key.RIGHT: (1.0, 0.0)}

REVEAL_SECONDS = 1.8

#: Okabe-Ito, and none of it saturated in a verdict channel pattern —
#: the art also never enters the band, which is the actual rule.
WIRE_COLOR = (230, 159, 0)
TRACK_ALPHA = 60
START_COLOR = (86, 180, 233)
END_COLOR = (0, 158, 115)


class BuzzWire:
    """Guide the cursor along the wire without touching. Esc returns."""

    instance: Optional['BuzzWire'] = None

    def __init__(self) -> None:
        if BuzzWire.instance is not None:
            BuzzWire.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.mouse: Tuple[float, float] = (0.0, 0.0)
        #: The wire, as normalized (x, y) vertices. Empty between rounds.
        self.path: List[Tuple[float, float]] = []
        self.round = 0
        self.results: List[Tuple[bool, float, float]] = []
        #                 (cleared, progress share, width multiplier)
        self.progress = 0.0
        self.multiplier = 1.0
        self.until = 0.0
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self._read_options()
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_motion,
                                   self.on_mouse_drag, self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        cursor.acquire()
        display.register_overlay(self)
        BuzzWire.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.BUZZWIRE)
        self.width_pct = int(opts['BUZZWIRE_WIDTH']) / 100.
        self.bends = int(opts['BUZZWIRE_BENDS'])
        self.seconds = int(opts['BUZZWIRE_SECONDS'])
        self.total_rounds = int(opts['BUZZWIRE_ROUNDS'])
        self.adaptive = bool(opts['BUZZWIRE_ADAPTIVE'])

    def open_options(self) -> None:
        taskoptions.open_task_options('buzz_wire', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.title = pyglet.text.Label(
            _('Buzz Wire'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     touch the blue pad, '
              'then follow the wire (mouse or arrows)     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the round by this
        # label's colour. Rebuilt with the chrome, so a verdict already
        # up is put back — a relayout on the frame a round settles would
        # otherwise drop it.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if getattr(self, 'verdict_shown', None) is not None:
            self.verdict.show(*self.verdict_shown)
        self._drawn: List[object] = []
        self._cursor_dot: Optional[object] = None
        self._sync_wire()
        self._update_status()

    def relayout(self) -> None:
        self._build_chrome()

    # --- geometry --------------------------------------------------------

    def half_width(self) -> float:
        """The corridor's half-width right now, in pixels."""
        return 0.5 * self.width_pct * self.multiplier * state.window.height

    def cursor_radius(self) -> float:
        return max(3.0, CURSOR_RADIUS * state.window.height)

    def pad_radius(self) -> float:
        """The start and end pads: exactly the corridor's own width.

        Not wider, though wider would be friendlier to find. A pad
        wider than the corridor can arm the round with the cursor
        already outside the walls, and the round then buzzes on the
        frame it begins — a verdict about the pad's geometry rather
        than the steering.
        """
        return max(self.half_width(), self.cursor_radius() * 2.0)

    def _wire_pixels(self) -> List[Tuple[float, float]]:
        """The wire's vertices in window pixels, held out of the band.

        The clamp is the load-bearing part: the widest adaptive corridor
        around the lowest permitted vertex must still stop above the
        strip the outcome reader scans, whatever the window's height.
        """
        window = state.window
        widest = 0.5 * self.width_pct * WIDEST * window.height
        floor = above_the_band(0) + widest
        return [(x * window.width,
                 max(y * window.height, floor))
                for x, y in self.path]

    def _deal_wire(self) -> None:
        """A fresh wire: bends+1 straights joined by vertical jogs."""
        low_x, high_x = SPAN_X
        low_y, high_y = SPAN_Y
        straights = self.bends + 1
        xs = [low_x + (high_x - low_x) * i / straights
              for i in range(straights + 1)]
        y = self.rng.uniform(low_y, high_y)
        points: List[Tuple[float, float]] = [(xs[0], y)]
        for i in range(straights):
            points.append((xs[i + 1], y))
            if i + 1 < straights:
                jog = self.rng.uniform(LEAST_JOG, 2.5 * LEAST_JOG)
                up = y + jog <= high_y
                down = y - jog >= low_y
                if up and down:
                    up = self.rng.random() < 0.5
                y = min(high_y, y + jog) if up else max(low_y, y - jog)
                points.append((xs[i + 1], y))
        self.path = points

    @staticmethod
    def _nearest(px: float, py: float,
                 a: Tuple[float, float],
                 b: Tuple[float, float]) -> Tuple[float, float]:
        """(distance, fraction along the segment) from a point to a-b."""
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        span = dx * dx + dy * dy
        if span <= 0.0:
            return math.hypot(px - ax, py - ay), 0.0
        t = min(1.0, max(0.0, ((px - ax) * dx + (py - ay) * dy) / span))
        return math.hypot(px - ax - t * dx, py - ay - t * dy), t

    def _trace(self) -> Tuple[float, float]:
        """(distance to the wire, progress share) for the cursor now."""
        points = self._wire_pixels()
        lengths = [math.hypot(b[0] - a[0], b[1] - a[1])
                   for a, b in zip(points, points[1:])]
        total = sum(lengths) or 1.0
        best = (float('inf'), 0.0)
        walked = 0.0
        for a, b, length in zip(points, points[1:], lengths):
            distance, t = self._nearest(self.mouse[0], self.mouse[1], a, b)
            if distance < best[0]:
                best = (distance, (walked + t * length) / total)
            walked += length
        return best

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self._drop_wire()
        self.path = []
        self.round = 0
        self.results = []
        self.multiplier = 1.0
        self.progress = 0.0
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self._next_round()

    def _next_round(self) -> None:
        if self.round >= self.total_rounds:
            self._finish()
            return
        self.round += 1
        self.verdict_shown = None
        self.verdict.clear()
        self.progress = 0.0
        self._deal_wire()
        self.phase = 'arming'
        self.until = self.clock() + self.seconds
        self.message = _('Touch the blue pad to take the wire')
        self._sync_wire()
        self._update_status()

    def _score(self, cleared: bool, note: str) -> None:
        self.results.append((cleared, self.progress, self.multiplier))
        self.message = note
        # Green on a clear, which is also what narrows the corridor, so
        # the bar and the difficulty move together: staying green means
        # the wire keeps tightening until it does not.
        self.verdict_shown = (cleared, note)
        self.verdict.show(*self.verdict_shown)
        if self.adaptive:
            if cleared:
                self.multiplier = max(NARROWEST, self.multiplier * STEP_IN)
            else:
                self.multiplier = min(WIDEST, self.multiplier * STEP_OUT)
        self.phase = 'feedback'
        self.until = self.clock() + REVEAL_SECONDS
        self._update_status()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('Cleared %d of %d wires — corridor settled '
                         'at x%.2f') % (tally['cleared'], tally['rounds'],
                                        tally['multiplier'] / 100.)
        self._update_status()

    def score(self) -> Dict[str, int]:
        shares = [share for _cleared, share, _mult in self.results]
        return {
            'rounds': len(self.results),
            'cleared': sum(1 for cleared, _s, _m in self.results if cleared),
            'progress_percent': int(round(100. * sum(shares) / len(shares)))
                                if shares else 0,
            'multiplier': int(round(self.multiplier * 100)),
        }

    # --- the loop --------------------------------------------------------

    def update(self, dt: float) -> None:
        now = self.clock()
        if self.phase == 'arming':
            points = self._wire_pixels()
            start = points[0]
            # Armed only from inside the corridor, so the first steering
            # frame is on the wire by construction and a buzz can never
            # predate a steering error.
            reach = max(self.half_width() - self.cursor_radius(),
                        self.cursor_radius())
            if (math.hypot(self.mouse[0] - start[0],
                           self.mouse[1] - start[1]) <= reach):
                self.phase = 'steering'
                self.until = now + self.seconds
                self.message = _('Steady, all the way to the green pad')
                self._update_status()
            elif now >= self.until:
                self._score(False, _('Never reached the start pad'))
        elif self.phase == 'steering':
            distance, share = self._trace()
            self.progress = max(self.progress, share)
            points = self._wire_pixels()
            end = points[-1]
            if (math.hypot(self.mouse[0] - end[0],
                           self.mouse[1] - end[1]) <= self.pad_radius()):
                self.progress = 1.0
                self._score(True, _('Cleared it'))
            elif distance + self.cursor_radius() > self.half_width():
                self._score(False, _('Buzz — %d%% of the way') %
                            int(round(self.progress * 100)))
            elif now >= self.until:
                self._score(False, _('Out of time at %d%%') %
                            int(round(self.progress * 100)))
        elif self.phase == 'feedback' and now >= self.until:
            self._drop_wire()
            self._next_round()
        self._sync_cursor()

    # --- drawing ---------------------------------------------------------

    def _sync_wire(self) -> None:
        self._drop_wire()
        if not self.path or self.phase not in ('arming', 'steering',
                                               'feedback'):
            return
        points = self._wire_pixels()
        track = self.half_width() * 2.0
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        for a, b in zip(points, points[1:]):
            self._drawn.append(pyglet.shapes.Line(
                a[0], a[1], b[0], b[1], thickness=track,
                color=(fg, fg, fg, TRACK_ALPHA), batch=self.batch))
        for x, y in points:
            self._drawn.append(pyglet.shapes.Circle(
                x, y, track / 2.0, color=(fg, fg, fg, TRACK_ALPHA),
                batch=self.batch))
        for a, b in zip(points, points[1:]):
            self._drawn.append(pyglet.shapes.Line(
                a[0], a[1], b[0], b[1], thickness=2.0,
                color=WIRE_COLOR + (255,), batch=self.batch))
        self._drawn.append(pyglet.shapes.Circle(
            points[0][0], points[0][1], self.pad_radius(),
            color=START_COLOR + (255,), batch=self.batch))
        self._drawn.append(pyglet.shapes.Circle(
            points[-1][0], points[-1][1], self.pad_radius(),
            color=END_COLOR + (255,), batch=self.batch))

    def _sync_cursor(self) -> None:
        if self.phase not in ('arming', 'steering', 'feedback'):
            if self._cursor_dot is not None:
                try:
                    self._cursor_dot.delete()
                except Exception:
                    pass
                self._cursor_dot = None
            return
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        if self._cursor_dot is None:
            self._cursor_dot = pyglet.shapes.Circle(
                self.mouse[0], self.mouse[1], self.cursor_radius(),
                color=(fg, fg, fg, 255), batch=self.batch)
        else:
            self._cursor_dot.position = self.mouse

    def _drop_wire(self) -> None:
        for drawn in self._drawn:
            try:
                drawn.delete()
            except Exception:
                pass
        self._drawn = []

    def _update_status(self) -> None:
        parts = [self.message]
        if self.phase in ('arming', 'steering', 'feedback'):
            parts.append(_('wire %d/%d') % (self.round, self.total_rounds))
            if self.adaptive:
                parts.append(_('x%.2f') % self.multiplier)
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if BuzzWire.instance is not self:
            return
        self._drop_wire()
        if self._cursor_dot is not None:
            try:
                self._cursor_dot.delete()
            except Exception:
                pass
            self._cursor_dot = None
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press,
                                     self.on_mouse_motion,
                                     self.on_mouse_drag, self.on_draw)
        BuzzWire.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='attention')

    # --- events ----------------------------------------------------------

    def nudge(self, dx: float, dy: float) -> None:
        """Move the cursor one step, in units of the window's height.

        Steering by steps rather than by pointing, exactly as Pursuit
        does it and at the same step size, so the arrow keys work and
        so does the agent boundary, which has no pointer at all.
        """
        window = state.window
        step = window.height * CURSOR_STEP
        self.mouse = (min(max(0.0, self.mouse[0] + dx * step),
                          float(window.width)),
                      min(max(0.0, self.mouse[1] + dy * step),
                          float(window.height)))

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol in ARROWS:
            self.nudge(*ARROWS[symbol])
        return pyglet.event.EVENT_HANDLED

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> bool:
        self.mouse = (float(x), float(y))
        return pyglet.event.EVENT_HANDLED

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int,
                      buttons: int, modifiers: int) -> bool:
        self.mouse = (float(x), float(y))
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
