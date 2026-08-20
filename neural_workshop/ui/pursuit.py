# -*- coding: utf-8 -*-
"""Pursuit: keep the mouse on a thing that does not want it there.

One shape wanders the screen, and the job is to hold the cursor on
it. The shape does not move like a ball: it breaks direction without
warning, surges and dawdles, swells and shrinks, and now and then
becomes a different shape entirely. Smooth pursuit is easy — the eye
and hand are built for it — so everything this quarry does is aimed
at the moment prediction fails and the hand has to catch up.

The score is continuous, not hit-or-miss: every frame either has the
cursor on the quarry or off it, and the tally is the share of the
round spent on, plus the average distance in pixels for the frames
spent off. That dense signal is deliberate — the task was asked for
as a training ground for real-time ability, human or artificial, and
a percentage per round is a far better gradient than a pass/fail.

For the same reason the difficulty is not one dial but six, each an
independent axis of awkwardness: base speed, surge depth, how often
the direction breaks, how sharp the breaks are, size wobble, and
shape morphing. The adaptive option then multiplies speed and break
rate together in five-percent steps, so a run settles onto a precise
frontier — and the multiplier it settles at is itself a score.

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
                        scale_to_height, width_center)
from . import cursor, taskoptions
from .lookout import COLORS, FORMS, make_glyph, place_glyph
from .tracking import bounced
from ..i18n import _

#: The adaptive multiplier's range and step. Five percent a round is
#: fine enough to settle on a frontier rather than oscillate over it.
SLOWEST, FASTEST = 0.4, 3.0
STEP_UP, STEP_DOWN = 1.05, 0.95

#: On-target shares that move the multiplier. Between them the round
#: was at the frontier already and the difficulty holds still.
RAISE_AT, LOWER_AT = 0.7, 0.4

#: The cursor counts as "on" within this much of the drawn radius —
#: a fingertip of forgiveness, since the shapes are not all round.
GRACE = 1.15

REVEAL_SECONDS = 1.8


class Quarry:
    """The pursued shape: motion state and its scheduled surprises."""

    __slots__ = ('x', 'y', 'heading', 'surge', 'radius', 'form', 'color',
                 'next_turn', 'next_surge', 'next_resize', 'next_morph',
                 'drawn')

    def __init__(self, x: float, y: float, heading: float, radius: float,
                 form: int, color: int) -> None:
        self.x = x
        self.y = y
        self.heading = heading
        self.surge = 1.0
        self.radius = radius
        self.form = form
        self.color = color
        self.next_turn = 0.0
        self.next_surge = 0.0
        self.next_resize = 0.0
        self.next_morph = 0.0
        self.drawn: Optional[object] = None


class Pursuit:
    """Hold the mouse on the wandering shape. Esc returns."""

    instance: Optional['Pursuit'] = None

    def __init__(self) -> None:
        if Pursuit.instance is not None:
            Pursuit.instance.close()
        self.rng = random.Random()
        self.quarry: Optional[Quarry] = None
        self.mouse: Tuple[float, float] = (0.0, 0.0)
        self.round = 0
        self.results: List[Tuple[float, float, float]] = []
        #                 (on share, mean off distance, multiplier)
        self.on_time = 0.0
        self.run_time = 0.0
        self.off_sum = 0.0
        self.off_samples = 0
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
        Pursuit.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.PURSUIT)
        self.speed = int(opts['PURSUIT_SPEED']) / 100.
        self.surge_depth = int(opts['PURSUIT_SURGE']) / 100.
        self.turn_gap = int(opts['PURSUIT_TURN_MS']) / 1000.
        self.sharpness = math.radians(int(opts['PURSUIT_TURN_DEGREES']))
        self.base_radius = int(opts['PURSUIT_SIZE'])
        self.wobble = int(opts['PURSUIT_SIZE_WOBBLE']) / 100.
        self.morph_gap = int(opts['PURSUIT_MORPH_MS']) / 1000.
        self.seconds = int(opts['PURSUIT_SECONDS'])
        self.total_rounds = int(opts['PURSUIT_ROUNDS'])
        self.adaptive = bool(opts['PURSUIT_ADAPTIVE'])

    def open_options(self) -> None:
        taskoptions.open_task_options('pursuit', on_apply=self.apply_options)

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
            _('Pursuit'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     keep the mouse on '
              'the shape     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        if self.quarry is not None:
            self.quarry.drawn = None
        self._sync_quarry()
        self._update_status()

    def relayout(self) -> None:
        self._build_chrome()

    def drawn_radius(self) -> float:
        if self.quarry is None:
            return 0.0
        return max(6.0, float(scale_to_height(self.quarry.radius)))

    def _bounds(self) -> Tuple[float, float, float, float]:
        window = state.window
        edge_x = self.drawn_radius() / max(1, window.width)
        edge_y = self.drawn_radius() / max(1, window.height)
        return (edge_x + 0.01, 1.0 - edge_x - 0.01,
                edge_y + 0.11, 1.0 - edge_y - 0.17)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self._drop_quarry()
        self.round = 0
        self.results = []
        self.multiplier = 1.0
        self.phase = 'ready'
        self.message = _('Press Space to start')

    def start_run(self) -> None:
        self._reset()
        self._next_round()

    def _next_round(self) -> None:
        if self.round >= self.total_rounds:
            self._finish()
            return
        self.round += 1
        self.on_time = 0.0
        self.run_time = 0.0
        self.off_sum = 0.0
        self.off_samples = 0
        now = time.time()
        self._drop_quarry()
        self.quarry = Quarry(
            x=0.5, y=0.5, heading=self.rng.uniform(0.0, 2 * math.pi),
            radius=self.base_radius,
            form=self.rng.randrange(len(FORMS)),
            color=self.rng.randrange(len(COLORS)))
        for stamp in ('next_turn', 'next_surge', 'next_resize',
                      'next_morph'):
            setattr(self.quarry, stamp, now + self._gap())
        self.phase = 'chasing'
        self.until = now + self.seconds
        self.message = _('Stay on it')
        self._sync_quarry()
        self._update_status()

    def _gap(self) -> float:
        """The next surprise, drawn around the configured mean gap.

        Exponential-ish spacing (a uniform spread around the mean)
        rather than a metronome: a rhythm can be learned, and the
        whole point of the quarry is that it cannot.
        """
        pace = max(0.05, self.turn_gap / max(0.1, self.multiplier))
        return self.rng.uniform(0.3, 1.7) * pace

    # --- the quarry's habits ---------------------------------------------

    def _swerve(self, quarry: Quarry, now: float) -> None:
        """An abrupt break of direction, up to the configured angle."""
        turn = self.rng.uniform(0.35, 1.0) * self.sharpness
        quarry.heading += turn if self.rng.random() < 0.5 else -turn
        quarry.next_turn = now + self._gap()

    def _lurch(self, quarry: Quarry, now: float) -> None:
        """A new surge factor: dawdle to sprint, around the base pace."""
        quarry.surge = max(0.15, self.rng.uniform(1.0 - self.surge_depth,
                                                  1.0 + self.surge_depth))
        quarry.next_surge = now + self._gap()

    def _swell(self, quarry: Quarry, now: float) -> None:
        quarry.radius = self.base_radius * self.rng.uniform(
            1.0 - self.wobble, 1.0 + self.wobble)
        quarry.drawn = None
        quarry.next_resize = now + self._gap()

    def _shift(self, quarry: Quarry, now: float) -> None:
        was = quarry.form
        while quarry.form == was:
            quarry.form = self.rng.randrange(len(FORMS))
        quarry.drawn = None
        quarry.next_morph = now + self._gap()

    def _move(self, dt: float) -> None:
        quarry = self.quarry
        low_x, high_x, low_y, high_y = self._bounds()
        pace = self.speed * self.multiplier * quarry.surge
        aspect = state.window.height / max(1, state.window.width)
        vx = pace * math.cos(quarry.heading)
        vy = pace * math.sin(quarry.heading)
        quarry.x += vx * dt * aspect
        quarry.y += vy * dt
        quarry.x, folded_vx = bounced(quarry.x, vx, low_x, high_x)
        quarry.y, folded_vy = bounced(quarry.y, vy, low_y, high_y)
        if (folded_vx, folded_vy) != (vx, vy):
            quarry.heading = math.atan2(folded_vy, folded_vx)

    def update(self, dt: float) -> None:
        now = time.time()
        if self.phase == 'chasing':
            quarry = self.quarry
            if now >= quarry.next_turn:
                self._swerve(quarry, now)
            if self.surge_depth and now >= quarry.next_surge:
                self._lurch(quarry, now)
            if self.wobble and now >= quarry.next_resize:
                self._swell(quarry, now)
            if self.morph_gap and now >= quarry.next_morph:
                self._shift(quarry, now)
            self._move(min(dt, 0.1))
            self._sample(min(dt, 0.1))
            self._sync_quarry()
            if now >= self.until:
                self._score()
        elif self.phase == 'feedback' and now >= self.until:
            self._next_round()

    # --- scoring ---------------------------------------------------------

    def distance(self) -> float:
        """Cursor to quarry centre, in pixels."""
        window = state.window
        return math.hypot(self.mouse[0] - self.quarry.x * window.width,
                          self.mouse[1] - self.quarry.y * window.height)

    def on_target(self) -> bool:
        return self.distance() <= self.drawn_radius() * GRACE

    def _sample(self, dt: float) -> None:
        self.run_time += dt
        if self.on_target():
            self.on_time += dt
        else:
            self.off_sum += self.distance()
            self.off_samples += 1

    def _score(self) -> None:
        share = self.on_time / self.run_time if self.run_time else 0.0
        drift = (self.off_sum / self.off_samples if self.off_samples
                 else 0.0)
        self.results.append((share, drift, self.multiplier))
        self.message = _('On it %d%% of the time') % int(round(share * 100))
        if self.adaptive:
            if share >= RAISE_AT:
                self.multiplier = min(FASTEST, self.multiplier * STEP_UP)
            elif share < LOWER_AT:
                self.multiplier = max(SLOWEST, self.multiplier * STEP_DOWN)
        self.phase = 'feedback'
        self.until = time.time() + REVEAL_SECONDS
        self._update_status()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('On target %d%% over %d rounds — difficulty '
                         'settled at x%.2f') % (
            tally['on_percent'], tally['rounds'],
            tally['multiplier'] / 100.)
        self._update_status()

    def score(self) -> Dict[str, int]:
        shares = [share for share, _drift, _mult in self.results]
        drifts = [drift for _share, drift, _mult in self.results]
        return {
            'rounds': len(self.results),
            'on_percent': int(round(100. * sum(shares) / len(shares)))
                          if shares else 0,
            'mean_off_px': int(round(sum(drifts) / len(drifts)))
                           if drifts else 0,
            'multiplier': int(round(self.multiplier * 100)),
        }

    # --- drawing ---------------------------------------------------------

    def _sync_quarry(self) -> None:
        if self.quarry is None or self.phase not in ('chasing', 'feedback'):
            return
        window = state.window
        quarry = self.quarry
        x = quarry.x * window.width
        y = quarry.y * window.height
        r = self.drawn_radius()
        if quarry.drawn is None:
            quarry.drawn = make_glyph(quarry.form, x, y, r,
                                      COLORS[quarry.color][1], self.batch)
        else:
            place_glyph(quarry.drawn, quarry.form, x, y, r)

    def _drop_quarry(self) -> None:
        if self.quarry is not None and self.quarry.drawn is not None:
            try:
                self.quarry.drawn.delete()
            except Exception:
                pass
            self.quarry.drawn = None
        self.quarry = None

    def _update_status(self) -> None:
        parts = [self.message]
        if self.phase in ('chasing', 'feedback'):
            parts.append(_('round %d/%d') % (self.round, self.total_rounds))
            if self.adaptive:
                parts.append(_('x%.2f') % self.multiplier)
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Pursuit.instance is not self:
            return
        self._drop_quarry()
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press,
                                     self.on_mouse_motion,
                                     self.on_mouse_drag, self.on_draw)
        Pursuit.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='attention')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
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
