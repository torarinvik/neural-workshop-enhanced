# -*- coding: utf-8 -*-
"""Mr. Time: how long ago was that, and can you do it again on cue?

A shape appears somewhere on the page, holds for a moment and goes
away. Some interval later — anything from nothing at all up to the
gap you configured — the question arrives: *how long ago did the shape
appear?* You answer in seconds and the clock you were reading was your
own, because nothing on screen was counting.

That is the *recall* half. The *produce* half asks the same question
from the other end: the shape appears with a duration written under
it, and the whole task is to click it when that much time has gone by.
One reads an interval that has already happened, the other lays one
down. They are not the same skill and the task keeps them apart, with
a third setting that shuffles the two so neither can be prepared for.

The ladder is precision
-----------------------

Every rung asks the same question and marks it harder. What changes is
the **unit the error is reported in** and, with it, the band an answer
has to land in:

    rung 1  seconds       within 25% of the interval
    rung 2  deciseconds   within 10%
    rung 3  centiseconds  within 4%
    rung 4  milliseconds  within 1.5%
    rung 5  microseconds  within 0.5%
    rung 6  nanoseconds   within 0.2%

The band is a *share of the interval* rather than a fixed number of
milliseconds, and that is not decoration. Human interval timing obeys
Weber's law — the spread of repeated estimates grows roughly in
proportion to what is being timed — so a fixed band would make a
half-second trial and an eight-second trial two different tasks
wearing one name, and a run's score would mostly report which
intervals it happened to deal. A proportional band makes every deal
equally hard, and the number that comes out of a run is a Weber
fraction: :meth:`MrTime.score` reports it, and it is the honest
summary of what a person or a learner can actually do here.

**The top of the ladder cannot be climbed, and it is there anyway.**
A well-practised person sits somewhere around 5-15% on this, which is
rungs two and three; rung four is very hard and rung five is past
anything the literature reports. Rung six asks for two parts in a
thousand of a three-second gap — six milliseconds — which is less than
half of one frame at sixty hertz, so it is beyond the *instrument* as
well as beyond the hand: an agent stepping the boundary sees time
quantised to 16.7 ms and cannot express an answer that fine, however
well it has learned. Nanoseconds are the ceiling of the ladder in the
same way :data:`neural_workshop.ui.reflex.MIN_LIFETIME` is Reflex's:
the rung above the last one anybody reaches, kept so that reaching the
last one still means something.

The answer is typed in seconds
------------------------------

The unit names the precision; it is not the entry format. Typing
``2.47`` at the nanosecond rung is a complete and exact answer of
2 470 000 000 ns, and the eight zeros nobody typed are the eight
zeros nobody could have controlled anyway. Making the player spell
them out would have added keystrokes and no timing.

What the screen must not say
----------------------------

Nothing here draws a clock, and nothing prints the tolerance before
the answer is in. The second of those is less obvious than it looks:
the band is a fixed share of the interval, so a tolerance shown up
front is the interval divided by a constant, and the whole question
would be sitting on the page in different units.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List, NamedTuple, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        scale_to_height, width_center)
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band
from ..i18n import _

#: The two halves, and the setting that shuffles them.
RECALL, PRODUCE, BOTH = 'recall', 'produce', 'both'


class Rung(NamedTuple):
    """One step of the precision ladder.

    *share* is the whole of the difficulty: an answer counts when it
    lands within that fraction of the interval being asked about. The
    unit is what the error is written in, so a rung is legible on
    screen as well as in the arithmetic.
    """

    unit: str
    short: str
    per_second: float
    share: float


#: The ladder. See the module docstring for why the last two rungs are
#: past what anybody reaches, and why they are here regardless.
RUNGS: Tuple[Rung, ...] = (
    Rung(_('seconds'), _('s'), 1.0, 0.25),
    Rung(_('deciseconds'), _('ds'), 10.0, 0.10),
    Rung(_('centiseconds'), _('cs'), 100.0, 0.04),
    Rung(_('milliseconds'), _('ms'), 1000.0, 0.015),
    Rung(_('microseconds'), _('µs'), 1000000.0, 0.005),
    Rung(_('nanoseconds'), _('ns'), 1000000000.0, 0.002),
)

MIN_RUNG, MAX_RUNG = 1, len(RUNGS)

#: Shape kinds a trial deals from. Which one it is carries nothing —
#: the shape is a marker for an instant, not a thing to remember — and
#: it varies so that a trial is not the same picture every time.
CIRCLE, TRIANGLE, SQUARE, PENTAGON, STAR, CROSS = (
    'circle', 'triangle', 'square', 'pentagon', 'star', 'cross')

#: Six outlines that stay six outlines once a random turn is put on
#: them. A diamond was here too until it was noticed that a diamond is
#: a square that has been turned, which is the one thing every shape
#: here already has done to it.
KINDS: Tuple[str, ...] = (CIRCLE, TRIANGLE, SQUARE, PENTAGON, STAR, CROSS)

#: Shortest duration the produce half will ever ask for. A target of
#: nothing is not a duration to lay down, it is a reaction test, and
#: Reflex is already that.
MIN_PRODUCE = 0.3

#: How long a settled trial holds its verdict before the next is dealt.
FEEDBACK_SECONDS = 1.2

#: Longest an unanswered produce trial waits past its target before it
#: is marked as never answered. Without it a run can hang on a player
#: who has walked away, and a stepped driver would tick for ever.
LATE_GRACE = 2.0

#: Most characters the answer field will take. Six significant figures
#: of a gap measured in seconds is already past every rung.
MAX_ANSWER = 12

#: Floating-point slack when comparing an error against its band, so an
#: answer that is exactly on the edge is not refused by the last bit.
EPSILON = 1e-9


class Mark(NamedTuple):
    """The shape one trial shows, in fractions of the drawing area.

    Held as fractions rather than pixels for the reason every other
    task here holds them that way: a resize mid-trial must redraw the
    same picture at the new size instead of a different one.
    """

    kind: str
    x: float
    y: float
    radius: float
    turn: float


def rung_at(number: int) -> Rung:
    """The rung *number* names, counting from one and clamped to the ladder."""
    return RUNGS[max(MIN_RUNG, min(MAX_RUNG, int(number))) - 1]


def tolerance(interval: float, number: int) -> float:
    """How far off an answer may be, in seconds, at rung *number*.

    A share of the interval rather than a fixed window — see the module
    docstring on Weber's law, which is the whole reason for it.
    """
    return abs(float(interval)) * rung_at(number).share


def quantity(seconds: float, number: int) -> str:
    """*seconds* written in rung *number*'s own unit.

    Small values keep two decimals so that a fifth of a second at the
    seconds rung reads as ``0.20 s`` rather than as ``0 s``; large ones
    are grouped, which is the only thing that makes a nanosecond figure
    readable at all.
    """
    rung = rung_at(number)
    value = abs(float(seconds)) * rung.per_second
    if value < 10:
        return '%.2f %s' % (value, rung.short)
    return '{:,} {}'.format(int(round(value)), rung.short)


class MrTime:
    """Time an interval you have just seen, or lay one down on cue."""

    instance: Optional['MrTime'] = None

    def __init__(self) -> None:
        if MrTime.instance is not None:
            MrTime.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.mark: Optional[Mark] = None
        self.answer_text = ''
        self.trial = 0
        self.correct = 0
        #: (mode, interval, answered, band, rung) per settled trial.
        self.results: List[Tuple[str, float, Optional[float], float, int]] = []
        self.phase = 'ready'
        self.trial_mode = RECALL
        self.appeared_at = 0.0
        self.ask_at = 0.0
        self.deadline = 0.0
        self.feedback_until = 0.0
        self.interval = 0.0
        self.target = 0.0
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.message = _('Press Space to start')
        self._read_options()
        self.drawn: List[object] = []
        self.extra_labels: List[pyglet.text.Label] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_text,
                                   self.on_mouse_press, self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        cursor.acquire()
        display.register_overlay(self)
        MrTime.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.MR_TIME)
        self.mode = str(opts['MRTIME_MODE'])
        self.start_rung = int(opts['MRTIME_RUNG'])
        self.total_trials = int(opts['MRTIME_TRIALS'])
        self.max_gap_ms = int(opts['MRTIME_MAX_GAP_MS'])
        self.flash_ms = int(opts['MRTIME_FLASH_MS'])
        self.adaptive = bool(opts['MRTIME_ADAPTIVE'])
        self.rung = max(MIN_RUNG, min(MAX_RUNG, self.start_rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('mr_time', on_apply=self.apply_options)

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
        self.muted = (fg, fg, fg, 170)
        self.batch = pyglet.graphics.Batch()
        self.drawn = []
        self.extra_labels = []
        self.title = pyglet.text.Label(
            _('Mr. Time'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.question = pyglet.text.Label(
            '', font_size=calc_fontsize(20), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_bottom_edge(148),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.prompt = pyglet.text.Label(
            '', font_size=calc_fontsize(12), color=self.muted,
            batch=self.batch, x=width_center(), y=from_bottom_edge(120),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.answer = pyglet.text.Label(
            '', font_size=calc_fontsize(26), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_bottom_edge(88),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     digits . then Enter'
              '     Space or click: act     C: options'),
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
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def relayout(self) -> None:
        """Rebuild at the window's current size, keeping the same trial."""
        self._build_chrome()

    def canvas(self) -> Tuple[float, float, float, float]:
        """Where a shape may be drawn: left, bottom, width, height.

        The floor is :func:`above_the_band`, so the shape cannot reach
        into the strip the agent boundary reads a verdict out of. The
        margin is folded in before that call rather than after, because
        a shape is placed by its centre and drawn outwards.
        """
        window = state.window
        width = window.width * 0.78
        bottom = above_the_band(from_bottom_edge(176))
        top = from_top_edge(104)
        height = max(float(scale_to_height(80)), top - bottom)
        return (window.width - width) / 2, float(bottom), width, height

    def _to_pixels(self, x: float, y: float) -> Tuple[float, float]:
        left, bottom, width, height = self.canvas()
        return left + x * width, bottom + y * height

    def _radius_pixels(self, mark: Mark) -> float:
        _left, _bottom, width, height = self.canvas()
        return mark.radius * min(width, height)

    # --- dealing a trial -------------------------------------------------

    def _random_mark(self) -> Mark:
        """One shape, placed a whole radius clear of the drawing area's edge."""
        radius = self.rng.uniform(0.10, 0.20)
        return Mark(kind=self.rng.choice(KINDS),
                    x=self.rng.uniform(radius, 1.0 - radius),
                    y=self.rng.uniform(radius, 1.0 - radius),
                    radius=radius, turn=self.rng.uniform(0.0, math.tau))

    def _deal_mode(self) -> str:
        """Which half this trial is. ``both`` shuffles rather than alternates.

        Alternating would be a pattern to learn instead of a task to
        do: a player who knows the next one is a production trial has
        already started counting when the shape lands.
        """
        if self.mode == BOTH:
            return self.rng.choice((RECALL, PRODUCE))
        return PRODUCE if self.mode == PRODUCE else RECALL

    def _reset(self) -> None:
        self.mark = None
        self.answer_text = ''
        self.trial = 0
        self.correct = 0
        self.results = []
        self.phase = 'ready'
        self.rung = max(MIN_RUNG, min(MAX_RUNG, self.start_rung))
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        """Begin a run of trials."""
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        self.answer_text = ''
        self.mark = self._random_mark()
        self.trial_mode = self._deal_mode()
        self.verdict_shown = None
        self.verdict.clear()
        now = self.clock()
        self.appeared_at = now
        if self.trial_mode == PRODUCE:
            # A whole number of the rung's units, so the duration on
            # screen is the duration being marked rather than a
            # rounding of it — and at least one unit, because rung one
            # rounds a third of a second to no seconds at all and a
            # target of nothing is not a duration to lay down.
            per = rung_at(self.rung).per_second
            raw = self.rng.uniform(0.0, self.max_gap_ms / 1000.)
            units = max(1, int(round(raw * per)))
            if units / per < MIN_PRODUCE:
                units = int(math.ceil(MIN_PRODUCE * per))
            self.target = units / per
            self.interval = self.target
            self.deadline = now + self.target + LATE_GRACE
            self.phase = 'counting'
            self.message = _('Wait for it')
        else:
            self.target = 0.0
            # The gap is the "0 to n" the options name; the flash in
            # front of it is fixed, so the interval asked about is the
            # two together and only one of them is hidden.
            gap = self.rng.uniform(0.0, self.max_gap_ms / 1000.)
            self.ask_at = now + self.flash_ms / 1000. + gap
            self.interval = 0.0
            self.phase = 'showing'
            self.message = _('Watch')
        self._redraw()

    def _ask(self, now: float) -> None:
        """Put the question up and freeze the interval it asks about.

        Frozen here rather than read again at submit, so that thinking
        about the answer and typing it are free. Otherwise the task
        would be timing the answer as well as asking for one, and a
        slow typist would be marked for their hands.
        """
        self.interval = now - self.appeared_at
        self.phase = 'asking'
        self.message = _('How long ago?')
        self._redraw()

    # --- answering -------------------------------------------------------

    def type_digit(self, digit: str) -> None:
        """Add a digit to the answer. Recall trials only."""
        if self.phase != 'asking' or len(self.answer_text) >= MAX_ANSWER:
            return
        if self.answer_text == '0' and digit != '0':
            self.answer_text = digit
        elif self.answer_text == '0' and digit == '0':
            return
        else:
            self.answer_text += digit
        self._update_labels()

    def type_point(self) -> None:
        """Add the decimal point, if the answer has not got one already."""
        if self.phase != 'asking' or len(self.answer_text) >= MAX_ANSWER:
            return
        if '.' in self.answer_text:
            return
        self.answer_text = (self.answer_text or '0') + '.'
        self._update_labels()

    def backspace(self) -> None:
        if self.phase != 'asking' or not self.answer_text:
            return
        self.answer_text = self.answer_text[:-1]
        self._update_labels()

    def answer_seconds(self) -> Optional[float]:
        """The typed answer as seconds, or None when there is not one yet."""
        text = self.answer_text
        if not text or text in ('.', '0.'):
            return None
        try:
            return float(text)
        except ValueError:                 # pragma: no cover - entry guards it
            return None

    def submit(self) -> None:
        """Mark the typed answer against the interval. Recall trials only."""
        if self.phase != 'asking':
            return
        answered = self.answer_seconds()
        if answered is None:
            return
        self._settle(answered)

    def act_now(self) -> None:
        """Take the produce trial's action: this is the moment claimed."""
        if self.phase != 'counting':
            return
        self._settle(self.clock() - self.appeared_at)

    # --- scoring ---------------------------------------------------------

    def _settle(self, answered: Optional[float]) -> None:
        """Score the trial *answered* closed, paint it, and pause on it."""
        band = tolerance(self.interval, self.rung)
        right = (answered is not None
                 and abs(answered - self.interval) <= band + EPSILON)
        self.results.append((self.trial_mode, self.interval, answered,
                             band, self.rung))
        if right:
            self.correct += 1
        self.phase = 'feedback'
        self.feedback_until = self.clock() + FEEDBACK_SECONDS
        self.message = self._verdict_text(answered, right)
        self.verdict_shown = (right, self.message)
        self.verdict.show(*self.verdict_shown)
        # Drawn before the ladder moves, so the line under the verdict
        # still names the unit the trial was actually marked in. The
        # next trial picks the new rung up when it is dealt.
        self._redraw()
        self._adapt(right)

    def _verdict_text(self, answered: Optional[float], right: bool) -> str:
        """What the label says. For the person; the colour is the scalar."""
        if answered is None:
            return _('Never answered')
        delta = answered - self.interval
        if delta == 0:
            return _('Exactly')
        size = quantity(delta, self.rung)
        if self.trial_mode == PRODUCE:
            which = _('%s late') % size if delta > 0 else _('%s early') % size
        else:
            which = _('%s over') % size if delta > 0 else _('%s under') % size
        if right:
            return which
        return _('%s — it was %.3f s') % (which, self.interval)

    def _adapt(self, right: bool) -> None:
        """A right answer asks for a finer unit; a wrong one gives one back."""
        if not self.adaptive:
            return
        self.rung = (min(MAX_RUNG, self.rung + 1) if right
                     else max(MIN_RUNG, self.rung - 1))

    def _finish(self) -> None:
        self.phase = 'done'
        self.mark = None
        tally = self.score()
        self.message = _('%d%% — %d of %d, typically %.1f%% out, best rung %d') % (
            tally['accuracy'], tally['correct'], tally['trials'],
            100. * tally['weber'], tally['best_rung'])
        self._redraw()

    def score(self) -> Dict[str, float]:
        """What the run came to.

        ``weber`` is the mean of ``|error| / interval`` over the trials
        that were answered, which is the number this task exists to
        measure: it is comparable across runs that happened to deal
        different intervals, and it is what the rung shares are written
        in, so it says directly which rung a player belongs on.
        """
        trials = len(self.results)
        answered = [row for row in self.results if row[2] is not None]
        shares = [abs(row[2] - row[1]) / row[1]
                  for row in answered if row[1] > 0]
        errors = [abs(row[2] - row[1]) for row in answered]
        return {
            'trials': trials,
            'correct': self.correct,
            'accuracy': int(round(100. * self.correct / trials)) if trials
                        else 0,
            'weber': (sum(shares) / len(shares)) if shares else 0.0,
            'mean_error_ms': (1000. * sum(errors) / len(errors)) if errors
                             else 0.0,
            'best_rung': max((row[4] for row in self.results), default=0),
        }

    # --- the clock -------------------------------------------------------

    def update(self, dt: float) -> None:
        now = self.clock()
        if self.phase == 'showing' and now - self.appeared_at >= self.flash_ms / 1000.:
            # The shape goes away. The question is still to come.
            self.phase = 'waiting'
            self._redraw()
        if self.phase == 'waiting' and now >= self.ask_at:
            # Not elif: a gap of zero asks on the tick the shape goes.
            self._ask(now)
        elif self.phase == 'counting' and now >= self.deadline:
            self._settle(None)
        elif self.phase == 'feedback' and now >= self.feedback_until:
            self._next_trial()

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
        return max(1.5, scale_to_height(2.2))

    def _points(self, mark: Mark) -> List[Tuple[float, float]]:
        """The outline of *mark*, in pixels, as a closed run of points."""
        centre_x, centre_y = self._to_pixels(mark.x, mark.y)
        radius = self._radius_pixels(mark)

        def around(index: float, scale: float = 1.0, sides: int = 4):
            angle = mark.turn + index * math.tau / sides
            return (centre_x + radius * scale * math.cos(angle),
                    centre_y + radius * scale * math.sin(angle))

        if mark.kind == TRIANGLE:
            return [around(i, sides=3) for i in range(3)]
        if mark.kind == SQUARE:
            return [around(i, sides=4) for i in range(4)]
        if mark.kind == PENTAGON:
            return [around(i, sides=5) for i in range(5)]
        if mark.kind == STAR:
            return [around(i, 1.0 if i % 2 == 0 else 0.45, sides=10)
                    for i in range(10)]
        # A cross, drawn as its own twelve-cornered outline.
        arm, waist = 1.0, 0.34
        corners = ((waist, arm), (-waist, arm), (-waist, waist),
                   (-arm, waist), (-arm, -waist), (-waist, -waist),
                   (-waist, -arm), (waist, -arm), (waist, -waist),
                   (arm, -waist), (arm, waist), (waist, waist))
        turned = []
        for across, up in corners:
            angle, reach = math.atan2(up, across), math.hypot(across, up)
            turned.append((centre_x + radius * reach * math.cos(angle + mark.turn),
                           centre_y + radius * reach * math.sin(angle + mark.turn)))
        return turned

    def _build_mark(self, mark: Mark) -> object:
        """One drawable outline for *mark*, at the current canvas size."""
        thickness = self._thickness()
        if mark.kind == CIRCLE:
            centre_x, centre_y = self._to_pixels(mark.x, mark.y)
            return pyglet.shapes.Arc(
                centre_x, centre_y, self._radius_pixels(mark),
                thickness=thickness, closed=True, color=self.inkcolor,
                batch=self.batch)
        return pyglet.shapes.MultiLine(
            *self._points(mark), closed=True, thickness=thickness,
            color=self.inkcolor, batch=self.batch)

    def mark_showing(self) -> bool:
        """Whether the shape is on screen this frame."""
        return (self.mark is not None
                and self.phase in ('showing', 'counting'))

    def mark_at(self, x: float, y: float) -> bool:
        """Whether (x, y) is on the shape, for a click that claims a moment."""
        if not self.mark_showing():
            return False
        centre_x, centre_y = self._to_pixels(self.mark.x, self.mark.y)
        return math.hypot(x - centre_x, y - centre_y) <= self._radius_pixels(
            self.mark)

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.mark_showing():
            self.drawn.append(self._build_mark(self.mark))
        self._update_labels()

    def _update_labels(self) -> None:
        rung = rung_at(self.rung)
        parts = [self.message]
        if self.phase not in ('ready', 'done'):
            parts.append(_('%d of %d   right %d   to the nearest %s')
                         % (self.trial, self.total_trials, self.correct,
                            rung.unit))
        self.status.text = '     '.join(parts)

        if self.phase == 'counting':
            self.question.text = _('Click the shape %s from now') % quantity(
                self.target, self.rung)
            self.prompt.text = _('Space or a click on the shape is the moment')
            self.answer.text = ''
        elif self.phase == 'asking':
            self.question.text = _('How long ago did the shape appear?')
            self.prompt.text = _('Answer in seconds, right to the nearest %s'
                                 ) % rung.unit
            self.answer.text = (self.answer_text or '_') + _(' s')
        else:
            # Watching, waiting, settled or between runs: the middle of
            # the page says nothing, because everything it could say
            # would be a clock.
            self.question.text = ''
            self.prompt.text = ''
            self.answer.text = ''

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if MrTime.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_text,
                                     self.on_mouse_press, self.on_draw)
        MrTime.instance = None

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
        elif symbol == key.SPACE and self.phase == 'counting':
            self.act_now()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol in (key.RETURN, key.ENTER):
            self.submit()
        elif symbol in (key.BACKSPACE, key.DELETE):
            self.backspace()
        elif symbol in (key.PERIOD, key.NUM_DECIMAL, key.COMMA):
            self.type_point()
        elif symbol in _DIGITS:
            self.type_digit(_DIGITS[symbol])
        return pyglet.event.EVENT_HANDLED

    def on_text(self, text: str) -> bool:
        # Swallowed so digits do not reach anything underneath.
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase == 'counting' and self.mark_at(x, y):
            self.act_now()
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
