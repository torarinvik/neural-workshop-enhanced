# -*- coding: utf-8 -*-
"""Moving Targets: keep your eyes on the right balls.

A handful of balls flash a colour, then turn just like all the others
and everything starts bouncing. When the motion stops, the question is
which balls were the flashed ones — nothing marks them any more, so
the only way to know is to have followed them the whole way round.

This is the classic multiple-object-tracking paradigm, and it earns
its place in the attention category the same way N-Cup Monte does:
the memory load is trivial, a few identities, but holding them takes
sustained, divided attention for the whole trial, and one glance away
loses a ball for good.

Like Reflex this task animates, so a ball owns its circle from cue to
feedback and only its position and colour change between frames.
Positions and speeds live in fractions of the window, so a resize
moves the flock to the same relative place instead of ejecting it.

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
from .verdict import VerdictLabel
from ..i18n import _

#: Balls a trial may hold, and targets among them. The ceilings are
#: room, not code: past thirty balls of this size the flock is more
#: collision than motion, and a target count must leave at least one
#: ball that is not a target or the question answers itself.
FEWEST_BALLS, MOST_BALLS = 3, 30

#: How the trial phases pace themselves, in seconds. The cue is long
#: enough to find every flashed ball once; the reveal is long enough
#: to see what was missed before the next trial begins.
CUE_SECONDS = 2.0
REVEAL_SECONDS = 1.8

#: The flock keeps a little clear air at spawn so no two balls begin
#: as one blob; the separation is relaxed when a crowded count leaves
#: no room, the same bargain the salesman's scatter makes.
SPAWN_APART = 2.4

#: Okabe-Ito, safe on both backgrounds and for the colour-blind.
PLAIN = (86, 180, 233)          # every ball, most of the time
CUED = (230, 159, 0)            # the balls to follow, and your picks
CAUGHT = (0, 158, 115)          # a pick that really was a target
MISSED = (213, 94, 0)           # a target that got away


class Ball:
    """One ball: where it is, where it is going, and what it was."""

    __slots__ = ('x', 'y', 'vx', 'vy', 'target', 'picked', 'circle')

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 target: bool) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.target = target
        self.picked = False
        self.circle: Optional[pyglet.shapes.Circle] = None


def bounced(position: float, velocity: float, low: float,
            high: float) -> Tuple[float, float]:
    """One axis of wall bounce: reflect off *low* and *high*.

    The overshoot is folded back inside rather than clamped, so a
    fast ball does not stick to the wall it hit.
    """
    if position < low:
        return low + (low - position), abs(velocity)
    if position > high:
        return high - (position - high), -abs(velocity)
    return position, velocity


class MovingTargets:
    """Follow the flashed balls through the motion. Esc returns."""

    instance: Optional['MovingTargets'] = None

    def __init__(self) -> None:
        if MovingTargets.instance is not None:
            MovingTargets.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.balls: List[Ball] = []
        self.round = 0
        self.results: List[Tuple[int, int, int]] = []  # (balls, asked, caught)
        self.phase = 'ready'
        self.until = 0.0
        self.message = _('Press Space to start')
        self._read_options()
        self.tracked = self.clamped_targets(self.start_targets)
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        cursor.acquire()
        display.register_overlay(self)
        MovingTargets.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.TRACKING)
        self.ball_count = int(opts['TRACK_BALLS'])
        self.start_targets = int(opts['TRACK_TARGETS'])
        self.seconds = int(opts['TRACK_SECONDS'])
        self.speed = int(opts['TRACK_SPEED']) / 100.  # screen heights / s
        self.total_rounds = int(opts['TRACK_ROUNDS'])
        self.adaptive = bool(opts['TRACK_ADAPTIVE'])

    def clamped_targets(self, count: int) -> int:
        """At least one target, and at least one ball that is not."""
        return max(1, min(self.ball_count - 1, count))

    def open_options(self) -> None:
        taskoptions.open_task_options('moving_targets',
                                      on_apply=self.apply_options)

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
            _('Moving Targets'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     click the balls you '
              'followed     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the trial by this
        # label's colour; tests/check_band.py is what says nothing else
        # this task draws puts a saturated colour in the bottom quarter.
        # Rebuilt with the chrome, so a verdict already up is put back —
        # a relayout on the frame a trial settles would otherwise drop
        # it, and an outcome only sometimes derivable is worse than one
        # that never is.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if getattr(self, 'verdict_shown', None) is not None:
            self.verdict.show(*self.verdict_shown)
        # Circles belong to the old batch; let them be remade.
        for ball in self.balls:
            ball.circle = None
        self._sync_balls()
        self._update_status()

    def relayout(self) -> None:
        self._build_chrome()

    def radius(self) -> float:
        return max(8.0, float(scale_to_height(21)))

    def _bounds(self) -> Tuple[float, float, float, float]:
        """low x, high x, low y, high y — in fractions, ball centre."""
        window = state.window
        edge_x = self.radius() / window.width
        edge_y = self.radius() / window.height
        return (edge_x + 0.01, 1.0 - edge_x - 0.01,
                edge_y + 0.11, 1.0 - edge_y - 0.15)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self._drop_balls()
        self.round = 0
        self.results = []
        self.tracked = self.clamped_targets(self.start_targets)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self._next_round()

    def _scattered(self) -> List[Tuple[float, float]]:
        """Spawn spots with clear air between them, relaxed if crowded."""
        low_x, high_x, low_y, high_y = self._bounds()
        apart = SPAWN_APART * self.radius() / state.window.height
        while True:
            spots: List[Tuple[float, float]] = []
            for _attempt in range(self.ball_count * 60):
                spot = (self.rng.uniform(low_x, high_x),
                        self.rng.uniform(low_y, high_y))
                if all((spot[0] - x) ** 2 + (spot[1] - y) ** 2
                       >= apart * apart for x, y in spots):
                    spots.append(spot)
                    if len(spots) == self.ball_count:
                        return spots
            apart *= 0.8

    def _next_round(self) -> None:
        if self.round >= self.total_rounds:
            self._finish()
            return
        self.round += 1
        self.verdict_shown = None
        self.verdict.clear()
        self._drop_balls()
        count = self.clamped_targets(self.tracked)
        chosen = set(self.rng.sample(range(self.ball_count), count))
        balls = []
        for index, (x, y) in enumerate(self._scattered()):
            heading = self.rng.uniform(0.0, 2 * math.pi)
            balls.append(Ball(
                x, y,
                vx=self.speed * math.cos(heading),
                vy=self.speed * math.sin(heading),
                target=index in chosen))
        self.balls = balls
        self.phase = 'cueing'
        self.until = self.clock() + CUE_SECONDS
        self.message = _('Follow the %s') % (
            _('coloured ball') if count == 1 else
            _('%d coloured balls') % count)
        self._sync_balls()
        self._update_status()

    def update(self, dt: float) -> None:
        now = self.clock()
        if self.phase == 'cueing' and now >= self.until:
            self.phase = 'tracking'
            self.until = now + self.seconds
            self.message = _('Keep watching')
        elif self.phase == 'tracking':
            self._move(min(dt, 0.1))
            if now >= self.until:
                self.phase = 'picking'
                self.message = _('Click the %s you followed') % (
                    _('ball') if self.tracked_now() == 1 else _('balls'))
        elif self.phase == 'revealing' and now >= self.until:
            self._next_round()
            return
        else:
            return
        self._sync_balls()
        self._update_status()

    def _move(self, dt: float) -> None:
        """Advance the flock, bouncing off the walls.

        The balls pass through each other on purpose: two identical
        balls crossing is exactly the moment tracking is hard, and
        making them bounce apart would delete the task's difficulty
        in the name of physics.
        """
        low_x, high_x, low_y, high_y = self._bounds()
        aspect = state.window.height / max(1, state.window.width)
        for ball in self.balls:
            ball.x += ball.vx * dt * aspect
            ball.y += ball.vy * dt
            ball.x, ball.vx = bounced(ball.x, ball.vx, low_x, high_x)
            ball.y, ball.vy = bounced(ball.y, ball.vy, low_y, high_y)

    def tracked_now(self) -> int:
        return sum(1 for ball in self.balls if ball.target)

    # --- answering -------------------------------------------------------

    def ball_at(self, x: float, y: float) -> Optional[Ball]:
        window = state.window
        reach = self.radius() * 1.3       # a forgiving fingertip
        near = [ball for ball in self.balls
                if (ball.x * window.width - x) ** 2
                + (ball.y * window.height - y) ** 2 <= reach * reach]
        if not near:
            return None
        return min(near, key=lambda ball:
                   (ball.x * window.width - x) ** 2
                   + (ball.y * window.height - y) ** 2)

    def pick(self, ball: Ball) -> None:
        """Toggle a pick; the last pick of the set scores the round."""
        if self.phase != 'picking':
            return
        ball.picked = not ball.picked
        picked = sum(1 for b in self.balls if b.picked)
        if picked >= self.tracked_now():
            self._score()
        self._sync_balls()
        self._update_status()

    def _score(self) -> None:
        asked = self.tracked_now()
        caught = sum(1 for ball in self.balls
                     if ball.picked and ball.target)
        self.results.append((self.ball_count, asked, caught))
        if caught == asked:
            self.message = _('All %d — perfect') % asked
        else:
            self.message = _('%d of %d') % (caught, asked)
        if self.adaptive:
            grown = self.tracked + 1 if caught == asked else self.tracked - 1
            self.tracked = self.clamped_targets(grown)
        self.verdict_shown = (caught == asked, self.message)
        self.verdict.show(*self.verdict_shown)
        self.phase = 'revealing'
        self.until = self.clock() + REVEAL_SECONDS

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d%% — %d of %d balls held over %d rounds') % (
            tally['accuracy'], tally['caught'], tally['asked'],
            tally['rounds'])
        self._update_status()

    def score(self) -> Dict[str, int]:
        asked = sum(asked for _balls, asked, _caught in self.results)
        caught = sum(caught for _balls, _asked, caught in self.results)
        return {
            'rounds': len(self.results), 'asked': asked, 'caught': caught,
            'accuracy': int(round(100. * caught / asked)) if asked else 0,
            'most_tracked': max((asked for _b, asked, caught in self.results
                                 if caught == asked), default=0),
        }

    # --- drawing ---------------------------------------------------------

    def _colour(self, ball: Ball) -> Tuple[int, int, int]:
        if self.phase == 'cueing':
            return CUED if ball.target else PLAIN
        if self.phase == 'picking':
            return CUED if ball.picked else PLAIN
        if self.phase == 'revealing':
            if ball.picked and ball.target:
                return CAUGHT
            if ball.target:
                return MISSED
            if ball.picked:
                return CUED
        return PLAIN

    def _sync_balls(self) -> None:
        window = state.window
        for ball in self.balls:
            if ball.circle is None:
                ball.circle = pyglet.shapes.Circle(
                    0, 0, self.radius(), color=PLAIN, batch=self.batch)
            ball.circle.position = (ball.x * window.width,
                                    ball.y * window.height)
            ball.circle.color = self._colour(ball)

    def _drop_balls(self) -> None:
        for ball in self.balls:
            if ball.circle is not None:
                try:
                    ball.circle.delete()
                except Exception:
                    pass
                ball.circle = None
        self.balls = []

    def _update_status(self) -> None:
        parts = [self.message]
        if self.phase not in ('ready', 'done') and self.total_rounds:
            parts.append(_('round %d/%d') % (self.round, self.total_rounds))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if MovingTargets.instance is not self:
            return
        self._drop_balls()
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        MovingTargets.instance = None

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

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase == 'picking':
            ball = self.ball_at(x, y)
            if ball is not None:
                self.pick(ball)
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
