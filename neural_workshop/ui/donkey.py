# -*- coding: utf-8 -*-
"""Donkey: two lanes, one key, and a swerve that starts before you see why.

The 1981 original, which is a car, a two-lane road, donkeys standing in
it and the space bar. Hit one and the round is over.

What is different is the swerve. Crossing takes a fixed number of rows
and cannot be called off, and while the car is across the middle a
donkey in *either* lane hits it. So the row a donkey arrives on is a row
you have to be clear of already: press when you see it and you swerve
into it. From the sixth rung the crossing is two rows wide and from the
tenth it is three, and the press has to be thrown that far in front of
what it is aimed at.

The road marches a row at a time rather than sliding, which is what the
original did — it redrew in text lines — and it is also what makes one
beat one step at the agent boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..donkey import (GRADES, SWITCH, Car, beat, cleared, generate, over,
                      rehearse, steer)
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: Okabe-Ito. The car is blue and the donkey is vermillion, which is
#: the colour the rest of the workshop already spends on the thing you
#: must not touch.
CAR = (0, 114, 178)
DONKEY = (213, 94, 0)
PASSED = (0, 158, 115)

#: The road surface and the lane markings, as opacities on the ink.
ROAD_ALPHA, MARK_ALPHA = 24, 90

#: How many rows of road are drawn ahead of the bonnet.
#:
#: More than the widest swerve by a good margin, so the press is never
#: aimed at something off the top of the screen: the task is how early
#: you commit, not whether the road told you in time.
SIGHT = 10

#: How long a row takes, and how long the road sits still first.
BEAT_SECONDS = 0.18
SET_SECONDS = 0.8

#: How long a verdict stays up before the next road can be called.
VERDICT_SECONDS = 1.0

#: Clear this share of the last four roads and an adaptive run climbs;
#: fewer than this and it drops.
CLIMB_AT, DROP_BELOW = 0.75, 0.4


class Donkey:
    """The road, the car and whatever is standing in it. Esc returns to the hub."""

    instance: Optional['Donkey'] = None

    def __init__(self) -> None:
        if Donkey.instance is not None:
            Donkey.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        #: Coach mode: paint a verdict on the beat a donkey goes by.
        #: Off for people — it changes the game — and switched on by the
        #: agent boundary. It reads the road, which is drawn, and
        #: nothing else.
        self.coach = False
        self.road = None
        self.car: Optional[Car] = None
        self.trial = 0
        self.results: List[Tuple[int, bool]] = []      # (rung, cleared)
        self.passed = 0
        self.until = 0.0
        self.beat_at = 0.0
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        Donkey.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.DONKEY)
        self.start_rung = int(opts['DONKEY_LEVEL'])
        self.total_trials = int(opts['DONKEY_TRIALS'])
        self.beat_seconds = float(opts['DONKEY_BEAT_SECONDS'])
        self.set_seconds = float(opts['DONKEY_SET_SECONDS'])
        self.adaptive = bool(opts['DONKEY_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('donkey', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.background = (bg, bg, bg)
        self.textcolor = (fg, fg, fg, 255)
        self.ink = (fg, fg, fg)
        self.batch = pyglet.graphics.Batch()
        self.drawn = []
        self.title = pyglet.text.Label(
            _('Donkey'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch, x=width_center(),
            y=from_top_edge(36), anchor_x='center', anchor_y='center',
            font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.asked = pyglet.text.Label(
            '', font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(94),
            width=int(state.window.width * 0.78), multiline=True,
            align='center', anchor_x='center', anchor_y='top',
            font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: menu   Space: start, then swerve   C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the road by this
        # label's colour. Rebuilt with the chrome so a verdict already
        # up is put back: a relayout on the frame a road settles would
        # otherwise drop it, and an outcome only sometimes derivable is
        # worse than one that never is.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if getattr(self, 'verdict_shown', None) is not None:
            self.verdict.show(*self.verdict_shown)
        self._update_asked()
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _stage(self) -> Tuple[float, float, float, float]:
        """Where the road lives: left, bottom, width, height.

        Held clear of the strip the agent boundary reads. The donkey is
        vermillion, ``(213, 94, 0)``, which is a negative verdict
        outright rather than merely a blend that passes for one — a
        donkey drawn down there would pay the road a ``-1`` for
        standing in it.
        """
        window = state.window
        top = from_top_edge(140)
        bottom = above_the_band(from_bottom_edge(60))
        return (window.width * 0.10, bottom,
                window.width * 0.80, max(60.0, top - bottom))

    def _road_rect(self) -> Tuple[float, float, float, float]:
        """The tarmac itself: a column down the middle of the stage."""
        left, bottom, width, height = self._stage()
        wide = min(width * 0.34, height * 0.62)
        return (left + (width - wide) / 2.0, bottom, wide, height)

    def _row_height(self) -> float:
        return self._road_rect()[3] / float(SIGHT + 1)

    def _row_y(self, index: float) -> float:
        """Where the row *index* rows in front of the bonnet is drawn.

        Index ``0`` is the row that arrives on the next beat. Index
        ``-1`` is the row the car has just met, and it is drawn on the
        car's **own** slot rather than a row above it, because that is
        where it is: :func:`~neural_workshop.donkey.beat` checks the
        arriving row against the car, so once the beat has run the two
        are in the same place and a hit has to look like one.

        Leaving that row out was the first version of this, and it made
        the game feel wrong in exactly the way it was wrong: a donkey
        the car had hit vanished from a position a full row-height
        ahead of the bumper, so every collision looked like a
        collision with nothing.
        """
        _left, bottom, _wide, _tall = self._road_rect()
        return bottom + self._row_height() * (index + 1.5)

    def _lane_x(self, lane: float) -> float:
        """Centre of *lane*, which may be a half for a car mid-crossing."""
        left, _bottom, wide, _tall = self._road_rect()
        return left + wide * (0.25 + 0.5 * lane)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.road = None
        self.car = None
        self.trial = 0
        self.results = []
        self.passed = 0
        self.rung = self.clamped(self.start_rung)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        self.verdict_shown = None
        self.verdict.clear()
        self.road = generate(self.rung, seed=self.rng.randrange(1 << 30))
        self.car = Car(self.road.start, self.road.grade.swerve)
        self.phase = 'setting'
        self.until = self.clock() + self.set_seconds
        self.beat_at = self.clock() + self.set_seconds
        self.message = _('Road ahead')
        self._update_asked()
        self._redraw()

    def _update_asked(self) -> None:
        """What the rung is asking, said in words above the road."""
        if self.road is None:
            self.asked.text = ''
            return
        grade = self.road.grade
        said = [_('Rung %d, %s.') % (self.rung, _(grade.name)),
                _('%d rows of road, %d donkeys in it.')
                % (self.road.length, self.road.donkeys)]
        said.append(_('The swerve takes one row, so press on the row '
                      'before the donkey.') if grade.swerve == 1 else
                    _('The swerve takes %d rows and cannot be called off, '
                      'so press %d rows before the donkey — on sight is '
                      'already too late.') % (grade.swerve, grade.swerve))
        self.asked.text = ' '.join(said)

    # --- what the player does --------------------------------------------

    def act(self, port: int) -> bool:
        """One press. It starts a swerve, or it is swallowed by one.

        Redrawn here rather than left to the next row, so the wheel
        turns on the frame the key went down. What the press cannot do
        is change the row that is already arriving.
        """
        if self.phase != 'running' or self.car is None:
            return False
        did = steer(self.car, port)
        self._update_status()
        self._redraw()
        return did

    def swerve(self) -> None:
        self.act(SWITCH)

    # --- the clock --------------------------------------------------------

    def update(self, dt: float) -> None:
        """One row of road, on the clock rather than on a press.

        The road comes whether or not anybody steers, which is the
        point: a driver who could stop the road while he thought would
        be playing a different game, and the game is about committing
        early rather than about choosing correctly.
        """
        now = self.clock()
        if self.phase == 'setting' and now >= self.until:
            self.phase = 'running'
            self.message = _('Go')
            self._redraw()
        elif self.phase == 'running' and now >= self.beat_at:
            self.beat_at = now + self.beat_seconds
            got = beat(self.car, self.road)
            self._coach_verdict(got)
            if over(self.car, self.road):
                self._settle()
                return
            self._update_status()
            self._redraw()

    def _coach_verdict(self, got: int) -> None:
        """Paint what the row just past did, a row at a time.

        Not shaping: there is no potential here and nothing telescopes.
        It is the road's own count taken apart — a donkey the car got by
        is a piece of the green and the one it hit is the red — so the
        sum over a road tracks the donkeys passed, and a learner does
        not have to reach the far end to be told anything.

        It reads the road and the car, both drawn. There is nothing
        hidden in this task for it to leak: the whole road is on the
        screen, and what it asks is whether you acted on it in time.
        """
        if not self.coach or self.car is None:
            return
        if self.car.hit:
            return          # the round's own verdict, painted by _settle
        if got:
            self.verdict_shown = (True, _('Past one'))
            self.verdict.show(*self.verdict_shown)
        else:
            self.verdict_shown = None
            self.verdict.clear()

    # --- how it ends ------------------------------------------------------

    def _settle(self) -> None:
        """Score the road: the far end of it, on four wheels."""
        car, road = self.car, self.road
        right = cleared(car, road)
        self.results.append((self.rung, right))
        self.passed += car.passed
        if right:
            self.message = _('Home, %d donkeys behind you') % car.passed
        else:
            self.message = _('Hit one after %d rows, %d behind you'
                             ) % (car.row, car.passed)
        if self.adaptive:
            share = sum(1 for _r, ok in self.results[-4:] if ok) / float(
                min(4, len(self.results)))
            if share >= CLIMB_AT:
                self.rung = self.clamped(self.rung + 1)
            elif share < DROP_BELOW:
                self.rung = self.clamped(self.rung - 1)
        self.phase = 'scored'
        self.until = self.clock() + VERDICT_SECONDS
        self.verdict_shown = (right, self.message)
        self.verdict.show(*self.verdict_shown)
        self._update_status()
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.road = None
        self.car = None
        self.message = _('%d of %d roads cleared, %d donkeys behind you, '
                         'highest rung %d — swerving on sight clears about '
                         '%d%% of these, and a coin about %d%%'
                         ) % (tally['clean'], tally['roads'], tally['passed'],
                              tally['best_rung'], tally['on_sight'],
                              tally['floor'])
        self.asked.text = ''
        self._update_status()
        self._redraw()

    def score(self) -> Dict[str, int]:
        """How the run went, and what the two shallow policies were worth.

        Both comparisons are measured rather than derived. The coin is
        the usual floor. The other one is the interesting number: it is
        the same run played by swerving the moment the donkey is on the
        row ahead, which is what the game looks like it is asking for
        and is a perfect policy for the first five rungs.
        """
        roads = len(self.results)
        clean = sum(1 for _r, ok in self.results if ok)
        best = max((rung for rung, _ok in self.results), default=0)
        floors = [rehearse(rung) for rung, _ok in self.results]
        sighted = [rehearse(rung, policy='reactive')
                   for rung, _ok in self.results]
        return {
            'roads': roads,
            'clean': clean,
            'passed': self.passed,
            'accuracy': int(round(100.0 * clean / roads)) if roads else 0,
            'best_rung': best,
            'floor': int(round(100.0 * sum(floors) / len(floors)))
                     if floors else 0,
            'on_sight': int(round(100.0 * sum(sighted) / len(sighted)))
                        if sighted else 0,
        }

    # --- drawing ----------------------------------------------------------

    def _clear_drawn(self) -> None:
        for shape in self.drawn:
            try:
                shape.delete()
            except Exception:
                pass
        self.drawn = []

    def _rect(self, x, y, wide, tall, colour, opacity=255):
        shape = pyglet.shapes.Rectangle(x, y, max(1.0, wide), max(1.0, tall),
                                        color=colour, batch=self.batch)
        shape.opacity = opacity
        self.drawn.append(shape)
        return shape

    def _label(self, text, x, y, size=11):
        label = pyglet.text.Label(
            text, font_size=calc_fontsize(size), color=self.textcolor,
            batch=self.batch, x=x, y=y, anchor_x='center',
            anchor_y='center', font_name=FONTLIST)
        self.drawn.append(label)
        return label

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.road is not None and self.phase in ('setting', 'running',
                                                    'scored'):
            self._draw_road()
            self._draw_donkeys()
            self._draw_car()
            # Last, and on top of the car, so a hit is a donkey over a
            # bonnet rather than a donkey that disappeared.
            self._draw_met()
            self._draw_left()
        self._update_status()

    def _draw_road(self) -> None:
        """The tarmac, its verges and the dashes down the middle."""
        left, bottom, wide, tall = self._road_rect()
        self._rect(left, bottom, wide, tall, self.ink, opacity=ROAD_ALPHA)
        verge = max(2.0, wide * 0.03)
        self._rect(left, bottom, verge, tall, self.ink, opacity=MARK_ALPHA)
        self._rect(left + wide - verge, bottom, verge, tall, self.ink,
                   opacity=MARK_ALPHA)
        # Dashes, one a row and offset by the row count, so the road is
        # visibly moving even down a stretch with nothing standing in it.
        step = self._row_height()
        thick = max(2.0, wide * 0.02)
        for index in range(SIGHT + 1):
            if (index + self.car.row) % 2:
                continue
            self._rect(left + wide / 2 - thick / 2,
                       bottom + step * (index + 0.25), thick, step * 0.5,
                       self.ink, opacity=MARK_ALPHA)

    def _draw_donkeys(self) -> None:
        """Whatever is standing in the road ahead, out to :data:`SIGHT` rows.

        The road the car has not met yet, which is the road the press is
        aimed at. The row it *has* met is :meth:`_draw_met`.
        """
        _left, _bottom, wide, _tall = self._road_rect()
        step = self._row_height()
        for index in range(SIGHT):
            row = self.car.row + index
            if row >= self.road.length:
                break
            lane = self.road.blocked[row]
            if lane is None:
                continue
            self._draw_donkey(self._lane_x(lane), self._row_y(index),
                              wide, step)

    def _draw_met(self) -> None:
        """The row the car has just been through, drawn where the car is.

        This is the frame's whole account of what the last beat did. A
        donkey in the far lane slides past the window; a donkey in the
        car's lane is drawn over the bonnet, which is the crash. Both
        are the same row in the same place — the only difference is
        which lane it was standing in, and that is the only difference
        the rules make either.
        """
        row = self.car.row - 1
        if row < 0 or row >= self.road.length:
            return
        lane = self.road.blocked[row]
        if lane is None:
            return
        _left, _bottom, wide, _tall = self._road_rect()
        self._draw_donkey(self._lane_x(lane), self._row_y(-1), wide,
                          self._row_height())

    def _draw_donkey(self, x, y, wide, step) -> None:
        """A body, a head and two ears. It is not much of a donkey.

        Drawn in vermillion, which is the workshop's colour for the
        thing you must not touch, and the reason :meth:`_stage` stops
        where it does.
        """
        body = min(wide * 0.30, step * 0.62)
        self._rect(x - body / 2, y - body * 0.32, body, body * 0.62, DONKEY)
        head = body * 0.34
        self._rect(x + body * 0.34, y + body * 0.10, head, head, DONKEY)
        for side in (0.40, 0.66):
            self._rect(x + body * side, y + body * 0.34, head * 0.22,
                       head * 0.55, DONKEY)
        for side in (-0.34, 0.20):
            self._rect(x + body * side, y - body * 0.62, body * 0.12,
                       body * 0.34, DONKEY)

    def _draw_car(self) -> None:
        """The car, and where it is between lanes when it is between them.

        A swerve under way is drawn part of the way across rather than
        in one lane or the other, because that is exactly what it is:
        the car covers both lanes for as long as the crossing lasts, and
        a car drawn in a lane it is not safely in would be the screen
        telling a lie about the only rule in the game.
        """
        _left, _bottom, wide, _tall = self._road_rect()
        step = self._row_height()
        car = self.car
        if car.crossing:
            gone = (car.swerve - car.crossing + 1) / float(car.swerve + 1)
            lane = car.lane + (1 - 2 * car.lane) * gone
        else:
            lane = float(car.lane)
        x = self._lane_x(lane)
        body = min(wide * 0.28, step * 0.70)
        y = self._row_y(-1)
        self._rect(x - body / 2, y - body * 0.42, body, body * 0.84, CAR)
        # A roof, so which way it is pointing is never in question.
        self._rect(x - body * 0.30, y - body * 0.10, body * 0.60,
                   body * 0.34, self.background)
        for side in (-1, 1):
            self._rect(x + side * body * 0.54 - body * 0.10,
                       y - body * 0.34, body * 0.20, body * 0.26,
                       self.ink, opacity=200)

    def _draw_left(self) -> None:
        """How much road is behind, and how many donkeys are in it.

        A bar rather than a number, and it fills from the left, because
        what a driver wants at a glance is how much of this is left
        rather than how much of it happened.
        """
        left, bottom, width, height = self._stage()
        span = width * 0.16
        thick = max(3.0, height * 0.020)
        y = bottom + height * 0.5
        share = min(1.0, self.car.row / float(max(1, self.road.length)))
        self._rect(left, y, span, thick, self.ink, opacity=40)
        self._rect(left, y, span * share, thick, PASSED)
        self._label(_('%d of %d rows') % (self.car.row, self.road.length),
                    left + span / 2, y + height * 0.06)
        self._label(_('%d of %d donkeys') % (self.car.passed,
                                             self.road.donkeys),
                    left + span / 2, y - height * 0.06)

    def _update_status(self) -> None:
        if self.road is None or self.car is None:
            self.status.text = self.message
            return
        self.status.text = _('Road %d of %d     %s'
                             ) % (self.trial, self.total_trials, self.message)

    # --- housekeeping -----------------------------------------------------

    def close(self) -> None:
        if Donkey.instance is not self:
            return
        self._clear_drawn()
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        Donkey.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='attention')

    # --- events -----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        """Space does both jobs, and the phases keep them apart.

        The original had one key and it was the space bar, so this one
        does too: it starts the run when there is no road under the car
        and it swerves when there is.
        """
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase == 'scored' and self.clock() >= self.until:
                self._next_trial()
            else:
                self.swerve()
        elif symbol in (key.X, key.LEFT, key.RIGHT, key.UP):
            self.swerve()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


__all__ = ['BEAT_SECONDS', 'CAR', 'DONKEY', 'Donkey', 'SET_SECONDS', 'SIGHT']
