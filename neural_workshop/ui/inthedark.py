# -*- coding: utf-8 -*-
"""The In the Dark screen: rooms go by, lamps do not.

The thinking lives in :mod:`neural_workshop.inthedark`; this module is
the walk drawn on screen and the keys that answer it. Three decisions
matter here:

* The lamps are drawn as empty sockets and never filled. Everything
  the screen shows is derived from the room alone, so two runs with
  different colours behind them are the same picture pixel for pixel.
  That is not a stylistic choice — it is the property the whole task
  rests on, and :mod:`tests.test_inthedark` checks it by rendering two
  such runs and comparing the bytes.

* Every question is asked before any of them is answered aloud.
  Saying "that one was blue" between questions would leak: the lamps
  all come from one unseen starting arrangement, so pinning any of
  them down narrows what the others can be. The verdicts therefore
  wait until the last question has been taken.

* There is no going back through the rooms and no pausing on one.
  A room is shown for its time and then it is gone, because the task
  is holding the register, not reading it off. What the rooms did is
  recoverable only from having watched them.

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
from ..inthedark import (GRADES, MOST_COLOURS, PAINT, SWAP, TURN, Room,
                         Round, generate)
from . import cursor, taskoptions
from .verdict import VerdictLabel
from ..i18n import _

#: Okabe-Ito, as everywhere else in the workshop. Five lamp colours,
#: chosen for how far apart they are rather than for how many the
#: palette holds: vermilion is left out because it sits too near the
#: orange, and the plain blue because it sits too near the sky blue,
#: and a task about remembering a colour must never turn into a task
#: about telling two of them apart.
LAMP_COLORS: Tuple[Tuple[int, int, int], ...] = (
    (230, 159, 0),      # orange
    (86, 180, 233),     # sky blue
    (0, 158, 115),      # bluish green
    (240, 228, 66),     # yellow
    (204, 121, 167),    # reddish purple
)

#: What the answer keys are, in colour order.
ANSWER_KEYS = (key._1, key._2, key._3, key._4, key._5)
PAD_KEYS = (key.NUM_1, key.NUM_2, key.NUM_3, key.NUM_4, key.NUM_5)

#: How long the verdicts stay up before the next round can be called.
VERDICT_SECONDS = 0.8

#: Answer this share of a round's questions and an adaptive run climbs;
#: answer fewer than half and it drops. A round is all-or-nothing to
#: play but not to score, because one slip in thirty rooms should cost
#: a rung rather than a run.
CLIMB_AT = 1.0
DROP_BELOW = 0.5


class InTheDark:
    """Watch the rooms, hold the lamps. Esc returns to the hub."""

    instance: Optional['InTheDark'] = None

    def __init__(self) -> None:
        if InTheDark.instance is not None:
            InTheDark.instance.close()
        self.rng = random.Random()
        #: Swapped out by the agent environment for a virtual clock.
        self.clock = time.time
        self.round: Optional[Round] = None
        self.cursor = 0
        self.until = 0.0
        self.given: List[int] = []
        self.asking_at = 0
        self.trial = 0
        self.results: List[Tuple[int, int, int]] = []   # (rung, right, asked)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        InTheDark.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.IN_THE_DARK)
        self.start_rung = int(opts['DARK_LEVEL'])
        self.total_trials = int(opts['DARK_TRIALS'])
        self.room_seconds = float(opts['DARK_SECONDS'])
        self.adaptive = bool(opts['DARK_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('in_the_dark',
                                      on_apply=self.apply_options)

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
            _('In the Dark'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     1-5: answer'
              '     C: options'),
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
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _stage(self) -> Tuple[float, float, float, float]:
        window = state.window
        top = from_top_edge(105)
        bottom = from_bottom_edge(60)
        return (window.width * 0.1, bottom,
                window.width * 0.8, max(60.0, top - bottom))

    def lamp_count(self) -> int:
        return self.round.lamps if self.round is not None else 1

    def _socket(self, lamp: int) -> Tuple[float, float, float]:
        """Middle and radius of one lamp's socket on screen."""
        left, bottom, width, height = self._stage()
        lamps = self.lamp_count()
        radius = min(width / lamps * 0.22, height * 0.11)
        return (left + width * (lamp + 0.5) / lamps,
                bottom + height * 0.22, radius)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.round = None
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
        self.round = generate(self.rung, seed=self.rng.randrange(1 << 30))
        self.cursor = 0
        self.given = []
        self.asking_at = 0
        self.phase = 'walking'
        self.until = self.clock() + self.room_seconds
        grade = GRADES[self.rung - 1]
        self.message = _('%s — %d lamps, %d rooms') % (
            _(grade.name), self.round.lamps, len(self.round.rooms))
        self._redraw()

    def room_now(self) -> Optional[Room]:
        """The room being shown, or None when none is."""
        if self.phase != 'walking' or self.round is None:
            return None
        return self.round.rooms[self.cursor]

    def asked_now(self) -> Optional[int]:
        """The lamp being asked about, or None when none is."""
        if self.phase != 'asking' or self.round is None:
            return None
        return self.round.asked[self.asking_at]

    def update(self, dt: float) -> None:
        if self.phase != 'walking':
            return
        if self.clock() < self.until:
            return
        self.cursor += 1
        if self.cursor >= len(self.round.rooms):
            self._start_asking()
        else:
            self.until = self.clock() + self.room_seconds
        self._redraw()

    def _start_asking(self) -> None:
        self.phase = 'asking'
        self.asking_at = 0
        self.message = _('The lights come up')

    def answer(self, colour: int) -> None:
        """Take one answer. Verdicts wait for the last of them."""
        if self.phase != 'asking' or colour >= self.round.colours:
            return
        self.given.append(colour)
        self.asking_at += 1
        if self.asking_at >= len(self.round.asked):
            self._settle()
        self._redraw()

    def _settle(self) -> None:
        got = sum(1 for mine, truth in zip(self.given, self.round.answers)
                  if mine == truth)
        asked = len(self.round.asked)
        self.results.append((self.rung, got, asked))
        if got == asked:
            self.message = _('All %d right') % asked
        else:
            self.message = _('%d of %d right') % (got, asked)
        share = got / float(asked)
        if self.adaptive:
            if share >= CLIMB_AT:
                self.rung = self.clamped(self.rung + 1)
            elif share < DROP_BELOW:
                self.rung = self.clamped(self.rung - 1)
        self.phase = 'scored'
        self.until = self.clock() + VERDICT_SECONDS
        self.verdict_shown = (got == asked, self.message)
        self.verdict.show(*self.verdict_shown)

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d rounds, %d%% of questions right, highest '
                         'rung %d') % (tally['rounds'], tally['accuracy'],
                                       tally['best_rung'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        right = sum(got for _r, got, _a in self.results)
        asked = sum(count for _r, _g, count in self.results)
        return {
            'rounds': len(self.results),
            'accuracy': int(round(100. * right / asked)) if asked else 0,
            'best_rung': max((rung for rung, _g, _a in self.results),
                             default=0),
            'perfect': sum(1 for _r, got, count in self.results
                           if got == count),
        }

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for shape in self.drawn:
            try:
                shape.delete()
            except Exception:
                pass
        self.drawn = []

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.round is not None and self.phase in ('walking', 'asking',
                                                     'scored'):
            self._draw_sockets()
            if self.phase == 'walking':
                self._draw_room(self.round.rooms[self.cursor])
            elif self.phase == 'asking':
                self._draw_question()
            else:
                self._draw_verdicts()
        self._update_status()

    def _draw_sockets(self) -> None:
        """The lamps: rims and holes, never a colour.

        Drawn from the lamp *count* alone, which is why the picture
        cannot depend on the lamps themselves.
        """
        for lamp in range(self.round.lamps):
            x, y, radius = self._socket(lamp)
            self.drawn.append(pyglet.shapes.Circle(
                x, y, radius, color=self.ink, batch=self.batch))
            self.drawn.append(pyglet.shapes.Circle(
                x, y, radius * 0.82, color=self.background, batch=self.batch))
            self.drawn.append(pyglet.text.Label(
                str(lamp + 1), font_size=calc_fontsize(13), weight='bold',
                color=self.textcolor, batch=self.batch,
                x=x, y=y - radius * 2.0, anchor_x='center',
                anchor_y='center', font_name=FONTLIST))

    def _arrow(self, from_x: float, from_y: float, to_x: float, to_y: float,
               shade: Tuple[int, int, int], thick: float,
               heads: int = 1) -> None:
        """A line with an arrowhead on one end, or on both."""
        self.drawn.append(pyglet.shapes.Line(
            from_x, from_y, to_x, to_y, thickness=thick, color=shade,
            batch=self.batch))
        span = math.hypot(to_x - from_x, to_y - from_y) or 1.0
        step_x, step_y = (to_x - from_x) / span, (to_y - from_y) / span
        size = thick * 2.4
        for tip_x, tip_y, way_x, way_y in (
                (to_x, to_y, step_x, step_y),
                (from_x, from_y, -step_x, -step_y))[:heads]:
            back_x, back_y = tip_x - way_x * size, tip_y - way_y * size
            self.drawn.append(pyglet.shapes.Triangle(
                tip_x, tip_y, back_x - way_y * size * 0.6,
                back_y + way_x * size * 0.6,
                back_x + way_y * size * 0.6, back_y - way_x * size * 0.6,
                color=shade, batch=self.batch))

    def _draw_room(self, room: Room) -> None:
        """What this room does to the lamps, over the socket row."""
        _left, bottom, _width, height = self._stage()
        x, y, radius = self._socket(room.lamp)
        band = bottom + height * 0.62
        thick = max(2.0, radius * 0.16)
        if room.kind == PAINT:
            shade = LAMP_COLORS[room.other % len(LAMP_COLORS)]
            self.drawn.append(pyglet.shapes.Circle(
                x, band + radius * 1.2, radius * 0.95, color=self.ink,
                batch=self.batch))
            self.drawn.append(pyglet.shapes.Circle(
                x, band + radius * 1.2, radius * 0.8, color=shade,
                batch=self.batch))
            self._arrow(x, band, x, y + radius * 1.25, self.ink, thick)
        elif room.kind == TURN:
            # A ring broken at the right, with the loose end swept
            # round: one colour along, whichever colour it was.
            self.drawn.append(pyglet.shapes.Arc(
                x, band + radius * 1.2, radius, thickness=thick,
                color=self.ink, angle=math.radians(300),
                start_angle=math.radians(-60), batch=self.batch))
            self._arrow(x + radius * 0.75, band + radius * 1.75,
                        x + radius * 1.15, band + radius * 1.2,
                        self.ink, thick)
            self._arrow(x, band, x, y + radius * 1.25, self.ink, thick)
        else:
            # Swap and copy both move a colour between two
            # sockets; the difference is only whether it comes back,
            # so a swap gets a head on each end and a copy one.
            other_x, _oy, _or = self._socket(room.other)
            top = band + radius * 1.1
            self._arrow(other_x, top, x, top, self.ink, thick,
                        heads=2 if room.kind == SWAP else 1)
            for foot_x in (x, other_x):
                self.drawn.append(pyglet.shapes.Line(
                    foot_x, top, foot_x, y + radius * 1.25,
                    thickness=thick * 0.7, color=self.ink, batch=self.batch))

    def _mark(self, lamp: int, shade: Tuple[int, int, int],
              lift: float = 1.9) -> None:
        """A pip under one socket, to point at the lamp being asked."""
        x, y, radius = self._socket(lamp)
        self.drawn.append(pyglet.shapes.Circle(
            x, y - radius * lift, radius * 0.26, color=shade,
            batch=self.batch))

    def _legend(self, y: float) -> None:
        """The colours and the keys that name them."""
        left, _b, width, _h = self._stage()
        colours = self.round.colours
        radius = min(width / max(colours, 1) * 0.08, 16.0)
        for colour in range(colours):
            x = left + width * (colour + 0.5) / colours
            self.drawn.append(pyglet.shapes.Circle(
                x, y, radius * 1.16, color=self.ink, batch=self.batch))
            self.drawn.append(pyglet.shapes.Circle(
                x, y, radius, color=LAMP_COLORS[colour % len(LAMP_COLORS)],
                batch=self.batch))
            self.drawn.append(pyglet.text.Label(
                str(colour + 1), font_size=calc_fontsize(12), weight='bold',
                color=self.textcolor, batch=self.batch,
                x=x, y=y - radius * 2.2, anchor_x='center',
                anchor_y='center', font_name=FONTLIST))

    def _draw_question(self) -> None:
        _left, bottom, _width, height = self._stage()
        self._mark(self.round.asked[self.asking_at], self.ink)
        self._legend(bottom + height * 0.72)

    def _draw_verdicts(self) -> None:
        """What was said and what was so, one row under the other."""
        _left, bottom, _width, height = self._stage()
        for spot, lamp in enumerate(self.round.asked):
            x, y, radius = self._socket(lamp)
            mine = self.given[spot] if spot < len(self.given) else -1
            truth = self.round.answers[spot]
            for row, colour in enumerate((mine, truth)):
                at = bottom + height * (0.78 - row * 0.13)
                if colour < 0:
                    continue
                self.drawn.append(pyglet.shapes.Circle(
                    x, at, radius * 0.5, color=self.ink, batch=self.batch))
                self.drawn.append(pyglet.shapes.Circle(
                    x, at, radius * 0.4,
                    color=LAMP_COLORS[colour % len(LAMP_COLORS)],
                    batch=self.batch))
            self._mark(lamp, self.ink if mine == truth else self.background)

    def _update_status(self) -> None:
        parts = [self.message]
        if self.round is not None and self.phase == 'walking':
            parts.append(_('round %d/%d   room %d/%d')
                         % (self.trial, self.total_trials, self.cursor + 1,
                            len(self.round.rooms)))
        elif self.round is not None and self.phase == 'asking':
            parts.append(_('lamp %d — which colour?')
                         % (self.round.asked[self.asking_at] + 1))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if InTheDark.instance is not self:
            return
        self._clear_drawn()
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        InTheDark.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='working_memory')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase == 'scored' and self.clock() >= self.until:
                self._next_trial()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        else:
            for colour in range(MOST_COLOURS):
                if symbol in (ANSWER_KEYS[colour], PAD_KEYS[colour]):
                    self.answer(colour)
                    break
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
