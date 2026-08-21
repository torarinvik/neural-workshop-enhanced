# -*- coding: utf-8 -*-
"""Count: how many shapes are in the tangle?

A field of overlapping outlines — lines by default, or circles,
triangles and rectangles — and the only question is how many there
are. Past four or five, counting stops being a glance and becomes
work: the eye has to track what it has already counted while the
crossings actively mislead it, which is what makes this a perception
task rather than an arithmetic one.

Shapes are generated as fractions of the drawing area and turned into
pyglet shapes at layout time, so a resize redraws the same tangle at
the new size instead of a different one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        scale_to_height, width_center)
from . import cursor, taskoptions
from .verdict import VerdictLabel
from ..i18n import _

#: Shape kinds a run can be made of.
LINES, CIRCLES, TRIANGLES, RECTANGLES, MIXED = (
    'lines', 'circles', 'triangles', 'rectangles', 'mixed')

#: The kinds MIXED draws from.
MIXED_KINDS: Sequence[str] = (LINES, CIRCLES, TRIANGLES, RECTANGLES)

#: Most shapes a trial will ever show, however well the player does.
MAX_SHAPES = 60

#: Fewest, so a wrong answer cannot make the task trivial.
MIN_SHAPES = 2

#: Shortest line worth counting, as a fraction of the drawing area.
#: Two edge points can land close together, and the stub that makes is
#: a dot rather than a line.
MIN_LINE_SPAN = 0.3


class Shape(NamedTuple):
    """One shape, in fractions of the drawing area.

    Held as fractions rather than pixels so the same tangle can be
    drawn at any window size — a resize mid-trial must not quietly
    become a different puzzle.
    """

    kind: str
    points: Tuple[Tuple[float, float], ...]
    radius: float = 0.0


class Counting:
    """Show a tangle of shapes, take a number, say whether it was right."""

    instance: Optional['Counting'] = None

    def __init__(self) -> None:
        if Counting.instance is not None:
            Counting.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.shapes_data: List[Shape] = []
        self.answer_text = ''
        self.count = 0
        self.trial = 0
        self.correct = 0
        self.results: List[Tuple[int, int]] = []     # (shown, answered)
        self.phase = 'ready'
        self.shown_at = 0.0
        self.feedback_until = 0.0
        self.message = _('Press Space to start')
        self._read_options()
        self.drawn: List[object] = []
        self.extra_labels: List[pyglet.text.Label] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_text,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        Counting.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.COUNTING)
        self.kind = str(opts['COUNT_SHAPE'])
        self.start_count = int(opts['COUNT_START'])
        self.total_trials = int(opts['COUNT_TRIALS'])
        self.exposure_ms = int(opts['COUNT_EXPOSURE_MS'])
        self.adaptive = bool(opts['COUNT_ADAPTIVE'])
        self.show_answer = bool(opts['COUNT_SHOW_ANSWER'])
        self.count = max(MIN_SHAPES, min(MAX_SHAPES, self.start_count))

    def open_options(self) -> None:
        taskoptions.open_task_options('count', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        """Create the batch, the colours and the fixed labels."""
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.inkcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.drawn = []
        self.extra_labels = []
        self.title = pyglet.text.Label(
            _('Count'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.answer = pyglet.text.Label(
            '', font_size=calc_fontsize(26), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_bottom_edge(86),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     digits then Enter'
              '     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(30),
            anchor_x='center', anchor_y='center')
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
        self._redraw()

    def relayout(self) -> None:
        """Rebuild at the window's current size, keeping the same tangle."""
        self._build_chrome()

    def canvas(self) -> Tuple[float, float, float, float]:
        """The rectangle the shapes are drawn in: left, bottom, w, h."""
        window = state.window
        width = window.width * 0.78
        height = window.height * 0.56
        return ((window.width - width) / 2,
                from_bottom_edge(150), width, height)

    def _to_pixels(self, point: Tuple[float, float]) -> Tuple[float, float]:
        left, bottom, width, height = self.canvas()
        return left + point[0] * width, bottom + point[1] * height

    # --- generating a tangle ---------------------------------------------

    def _perimeter_point(self, side: int) -> Tuple[float, float]:
        """A point on one edge of the drawing area."""
        along = self.rng.uniform(0.0, 1.0)
        return ((along, 0.0), (1.0, along), (along, 1.0), (0.0, along))[side]

    def _random_line(self) -> Shape:
        """A chord from one edge to another, ends drawn back inside.

        Spanning the area is what makes the lines cross each other
        instead of huddling, and starting from the edges keeps every
        one of them inside it — a line generated from a centre and a
        length runs off the canvas and over the labels. Both ends are
        then pulled in a little, so they float clear of the border the
        way a hand-drawn tangle does.
        """
        for _attempt in range(20):
            first = self.rng.randrange(4)
            second = (first + 1 + self.rng.randrange(3)) % 4  # another edge
            start = self._perimeter_point(first)
            end = self._perimeter_point(second)
            head = self.rng.uniform(0.02, 0.16)
            tail = 1.0 - self.rng.uniform(0.02, 0.16)
            span = (end[0] - start[0], end[1] - start[1])
            points = (
                (start[0] + span[0] * head, start[1] + span[1] * head),
                (start[0] + span[0] * tail, start[1] + span[1] * tail))
            if math.dist(points[0], points[1]) >= MIN_LINE_SPAN:
                return Shape(LINES, points)
        return Shape(LINES, ((0.05, 0.5), (0.95, 0.5)))

    def _random_circle(self) -> Shape:
        radius = self.rng.uniform(0.06, 0.18)
        return Shape(CIRCLES, ((self.rng.uniform(radius, 1 - radius),
                                self.rng.uniform(radius, 1 - radius)),),
                     radius=radius)

    def _random_triangle(self) -> Shape:
        # Size first, so the centre can be kept a whole radius from the
        # edge and no vertex lands outside the drawing area.
        size = self.rng.uniform(0.07, 0.17)
        centre = (self.rng.uniform(size, 1 - size),
                  self.rng.uniform(size, 1 - size))
        turn = self.rng.uniform(0, math.tau)
        points = tuple(
            (centre[0] + size * math.cos(turn + i * math.tau / 3),
             centre[1] + size * math.sin(turn + i * math.tau / 3))
            for i in range(3))
        return Shape(TRIANGLES, points)

    def _random_rectangle(self) -> Shape:
        width = self.rng.uniform(0.08, 0.26)
        height = self.rng.uniform(0.08, 0.26)
        left = self.rng.uniform(0, 1 - width)
        bottom = self.rng.uniform(0, 1 - height)
        return Shape(RECTANGLES, ((left, bottom), (left + width,
                                                   bottom + height)))

    def _random_shape(self, kind: str) -> Shape:
        if kind == CIRCLES:
            return self._random_circle()
        if kind == TRIANGLES:
            return self._random_triangle()
        if kind == RECTANGLES:
            return self._random_rectangle()
        return self._random_line()

    def generate(self, count: int) -> List[Shape]:
        """*count* shapes of the configured kind."""
        shapes = []
        for _index in range(count):
            kind = (self.rng.choice(MIXED_KINDS) if self.kind == MIXED
                    else self.kind)
            shapes.append(self._random_shape(kind))
        return shapes

    # --- a trial ---------------------------------------------------------

    def _reset(self) -> None:
        self.shapes_data = []
        self.answer_text = ''
        self.trial = 0
        self.correct = 0
        self.results = []
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        """Begin a run of trials."""
        self._reset()
        self.count = max(MIN_SHAPES, min(MAX_SHAPES, self.start_count))
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        self.answer_text = ''
        self.shapes_data = self.generate(self.count)
        self.verdict_shown = None
        self.verdict.clear()
        self.shown_at = self.clock()
        self.phase = 'showing'
        self.message = _('How many?')
        self._redraw()

    def submit(self) -> None:
        """Take the typed answer and score it."""
        if self.phase not in ('showing', 'hidden') or not self.answer_text:
            return
        answered = int(self.answer_text)
        right = answered == self.count
        self.results.append((self.count, answered))
        if right:
            self.correct += 1
        self._adapt(right)
        if self.show_answer:
            self.phase = 'feedback'
            self.feedback_until = self.clock() + 0.8
            self.message = (_('Yes, %d') % self.count if right
                            else _('No — there were %d') % self.count)
            self.verdict_shown = (right, self.message)
            self.verdict.show(*self.verdict_shown)
            self._redraw()
        else:
            self.message = _('Yes') if right else _('No')
            self._next_trial()

    def _adapt(self, right: bool) -> None:
        if not self.adaptive:
            return
        self.count = (min(MAX_SHAPES, self.count + 1) if right
                      else max(MIN_SHAPES, self.count - 1))

    def _finish(self) -> None:
        self.phase = 'done'
        self.shapes_data = []
        tally = self.score()
        self.message = _('%d%% — %d of %d, average error %.1f') % (
            tally['accuracy'], tally['correct'], tally['trials'],
            tally['mean_error'])
        self._redraw()

    def score(self) -> Dict[str, float]:
        """Correct answers, accuracy, and how far off the rest were."""
        trials = len(self.results)
        errors = [abs(shown - answered) for shown, answered in self.results]
        return {
            'trials': trials, 'correct': self.correct,
            'accuracy': int(round(100. * self.correct / trials)) if trials
                        else 0,
            'mean_error': (sum(errors) / len(errors)) if errors else 0.0,
            'hardest': max((shown for shown, _a in self.results), default=0),
        }

    def type_digit(self, digit: str) -> None:
        """Add a digit to the answer, within reason."""
        if self.phase not in ('showing', 'hidden'):
            return
        if len(self.answer_text) < 3:
            self.answer_text = (self.answer_text + digit).lstrip('0') or '0'
            self._update_labels()

    def backspace(self) -> None:
        if self.answer_text:
            self.answer_text = self.answer_text[:-1]
            self._update_labels()

    def update(self, dt: float) -> None:
        now = self.clock()
        if self.phase == 'feedback' and now >= self.feedback_until:
            self._next_trial()
        elif (self.phase == 'showing' and self.exposure_ms > 0
                and now - self.shown_at >= self.exposure_ms / 1000.):
            # The tangle goes away; the question stands.
            self.phase = 'hidden'
            self._redraw()

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []
        for label in self.extra_labels:
            label.delete()
        self.extra_labels = []

    def _thickness(self) -> float:
        return max(1.0, scale_to_height(1.4))

    def _build_shape(self, shape: Shape) -> Optional[object]:
        """One pyglet shape for *shape*, at the current canvas size."""
        thickness = self._thickness()
        points = [self._to_pixels(point) for point in shape.points]
        if shape.kind == CIRCLES:
            _left, _bottom, width, height = self.canvas()
            radius = shape.radius * min(width, height)
            return pyglet.shapes.Arc(
                points[0][0], points[0][1], radius, thickness=thickness,
                closed=True, color=self.inkcolor, batch=self.batch)
        if shape.kind == TRIANGLES:
            return pyglet.shapes.MultiLine(
                *points, closed=True, thickness=thickness,
                color=self.inkcolor, batch=self.batch)
        if shape.kind == RECTANGLES:
            (left, bottom), (right, top) = points
            return pyglet.shapes.Box(
                left, bottom, right - left, top - bottom, thickness=thickness,
                color=self.inkcolor, batch=self.batch)
        return pyglet.shapes.Line(
            points[0][0], points[0][1], points[1][0], points[1][1],
            thickness=thickness, color=self.inkcolor, batch=self.batch)

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.phase in ('showing', 'feedback'):
            for shape in self.shapes_data:
                built = self._build_shape(shape)
                if built is not None:
                    self.drawn.append(built)
        self._update_labels()

    def _update_labels(self) -> None:
        parts = [self.message]
        if self.phase in ('showing', 'hidden', 'feedback'):
            parts.append(_('%d of %d   right %d')
                         % (self.trial, self.total_trials, self.correct))
        self.status.text = '     '.join(parts)
        if self.phase in ('showing', 'hidden'):
            self.answer.text = self.answer_text or '_'
        else:
            self.answer.text = ''

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Counting.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_text,
                                     self.on_draw)
        Counting.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='perception')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol in (key.RETURN, key.ENTER):
            self.submit()
        elif symbol in (key.BACKSPACE, key.DELETE):
            self.backspace()
        elif symbol in _DIGITS:
            self.type_digit(_DIGITS[symbol])
        return pyglet.event.EVENT_HANDLED

    def on_text(self, text: str) -> bool:
        # Swallowed so digits do not reach anything underneath.
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


#: Digit keys, main row and keypad.
_DIGITS: Dict[int, str] = {}
for _digit in range(10):
    _DIGITS[getattr(key, '_%i' % _digit)] = str(_digit)
    _DIGITS[getattr(key, 'NUM_%i' % _digit)] = str(_digit)
