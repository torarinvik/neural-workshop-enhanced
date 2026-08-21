# -*- coding: utf-8 -*-
"""The Removals screen: one move at a time, and never the yard.

The thinking lives in :mod:`neural_workshop.removals`; this module is
the walk drawn on screen and the keys that answer it. Three decisions
matter here, and they are the same three In the Dark makes, for the
same reasons:

* The vans are drawn as empty bays and never filled, and no box is
  ever drawn with anything in it. Everything on screen is derived from
  the move alone, so two rounds whose yards differ but whose moves
  agree are the same picture pixel for pixel. That is not a stylistic
  choice — it is the property the floor rests on, and
  :mod:`tests.test_removals` checks it by rendering two such rounds
  and comparing the bytes.

* Every question is asked before any of them is answered aloud.
  Saying "that one went in van two" between questions would leak,
  because chains share boxes: pinning one thing down can pin another.
  The verdicts therefore wait until the last question has been taken.

* There is no going back through the moves and no pausing on one. A
  move is shown for its time and then it is gone. What the yard looks
  like is recoverable only from having watched it being built, which
  is the whole of the task.

The one thing the screen adds over In the Dark's is a shape it has to
carry: a pack is drawn as the thing, an arrow, and the holder, and
when the holder is a van the arrow runs down into that van's bay. So
the picture says "this goes in there" and never "and there is where
that is", which is the sentence the player has to supply.

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
from ..removals import (GRADES, MOST_VANS, PACK, Move, Round, Yard, generate)
from . import cursor, taskoptions
from ..i18n import _

#: Okabe-Ito again, but used differently from In the Dark. There a
#: colour *was* the answer, so two that could be confused would have
#: turned the task into an eye test and the palette was cut to five.
#: Here every thing carries its number as well, and colour is only a
#: second way of telling two of them apart — so the whole chromatic
#: set is used, near neighbours and all, with a neutral to make eight.
ITEM_COLORS: Tuple[Tuple[int, int, int], ...] = (
    (230, 159, 0),      # orange
    (86, 180, 233),     # sky blue
    (0, 158, 115),      # bluish green
    (240, 228, 66),     # yellow
    (0, 114, 178),      # blue
    (213, 94, 0),       # vermillion
    (204, 121, 167),    # reddish purple
    (140, 140, 140),    # neutral
)

#: What the answer keys are, in van order.
ANSWER_KEYS = (key._1, key._2, key._3, key._4, key._5)
PAD_KEYS = (key.NUM_1, key.NUM_2, key.NUM_3, key.NUM_4, key.NUM_5)

#: How long the verdicts stay up before the next round can be called.
VERDICT_SECONDS = 0.8

#: Answer this share of a round's questions and an adaptive run climbs;
#: answer fewer than half and it drops. A round is all-or-nothing to
#: play but not to score, because one slip in forty moves should cost
#: a rung rather than a run.
CLIMB_AT = 1.0
DROP_BELOW = 0.5


class Removals:
    """Watch the moves, carry the yard. Esc returns to the hub."""

    instance: Optional['Removals'] = None

    def __init__(self) -> None:
        if Removals.instance is not None:
            Removals.instance.close()
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
        Removals.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.REMOVALS)
        self.start_rung = int(opts['REMOVALS_LEVEL'])
        self.total_trials = int(opts['REMOVALS_TRIALS'])
        self.move_seconds = float(opts['REMOVALS_SECONDS'])
        self.adaptive = bool(opts['REMOVALS_ADAPTIVE'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('removals', on_apply=self.apply_options)

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
            _('Removals'), font_size=calc_fontsize(22), weight='bold',
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
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def _stage(self) -> Tuple[float, float, float, float]:
        window = state.window
        top = from_top_edge(105)
        bottom = from_bottom_edge(60)
        return (window.width * 0.1, bottom,
                window.width * 0.8, max(60.0, top - bottom))

    def yard(self) -> Yard:
        return self.round.yard if self.round is not None else Yard(1, 1, 1)

    def _van_rect(self, van: int) -> Tuple[float, float, float, float]:
        """The bay one van stands in: left, bottom, width, height."""
        left, bottom, width, height = self._stage()
        vans = self.yard().vans
        span = width / vans
        pad = span * 0.12
        return (left + span * van + pad, bottom + height * 0.06,
                span - pad * 2, height * 0.17)

    def _size(self) -> float:
        """How big a thing or a box is drawn."""
        _left, _bottom, width, height = self._stage()
        return min(width / 9.0, height * 0.15)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.round = None
        self.rung = self.clamped(self.start_rung)
        self.phase = 'ready'
        self.message = _('Press Space to start')

    def start_run(self) -> None:
        self._reset()
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        self.round = generate(self.rung, seed=self.rng.randrange(1 << 30))
        self.cursor = 0
        self.given = []
        self.asking_at = 0
        self.phase = 'moving'
        self.until = self.clock() + self.move_seconds
        grade = GRADES[self.rung - 1]
        self.message = _('%s — %d vans, %d moves') % (
            _(grade.name), self.round.yard.vans, len(self.round.moves))
        self._redraw()

    def move_now(self) -> Optional[Move]:
        """The move being shown, or None when none is."""
        if self.phase != 'moving' or self.round is None:
            return None
        return self.round.moves[self.cursor]

    def asked_now(self) -> Optional[int]:
        """The thing being asked about, or None when none is."""
        if self.phase != 'asking' or self.round is None:
            return None
        return self.round.asked[self.asking_at]

    def update(self, dt: float) -> None:
        if self.phase != 'moving':
            return
        if self.clock() < self.until:
            return
        self.cursor += 1
        if self.cursor >= len(self.round.moves):
            self._start_asking()
        else:
            self.until = self.clock() + self.move_seconds
        self._redraw()

    def _start_asking(self) -> None:
        self.phase = 'asking'
        self.asking_at = 0
        self.message = _('The doors close')

    def answer(self, van: int) -> None:
        """Take one answer. Verdicts wait for the last of them."""
        if self.phase != 'asking' or van >= self.round.yard.vans:
            return
        self.given.append(van)
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
        if self.round is not None and self.phase in ('moving', 'asking',
                                                     'scored'):
            self._draw_vans()
            if self.phase == 'moving':
                self._draw_move(self.round.moves[self.cursor])
            elif self.phase == 'asking':
                self._draw_question()
            else:
                self._draw_verdicts()
        self._update_status()

    def _outline(self, x: float, y: float, width: float, height: float,
                 thick: float) -> None:
        """A hollow rectangle: ink, with the background punched out."""
        self.drawn.append(pyglet.shapes.Rectangle(
            x, y, width, height, color=self.ink, batch=self.batch))
        self.drawn.append(pyglet.shapes.Rectangle(
            x + thick, y + thick, max(1.0, width - thick * 2),
            max(1.0, height - thick * 2), color=self.background,
            batch=self.batch))

    def _draw_vans(self) -> None:
        """The vans: empty bays, drawn from their number and nothing else."""
        for van in range(self.yard().vans):
            x, y, width, height = self._van_rect(van)
            self._outline(x, y, width, height, max(2.0, height * 0.1))
            self.drawn.append(pyglet.text.Label(
                str(van + 1), font_size=calc_fontsize(15), weight='bold',
                color=self.textcolor, batch=self.batch,
                x=x + width / 2, y=y + height / 2, anchor_x='center',
                anchor_y='center', font_name=FONTLIST))

    def _glyph(self, node: int, x: float, y: float, size: float) -> None:
        """One thing or one box, drawn at its own middle.

        A thing is a filled disc in its colour, a box a hollow square.
        Both carry their number, because the number is what the moves
        are about and the colour is only there to make two of them
        easier to keep apart.
        """
        yard = self.yard()
        if yard.is_item(node):
            which = node - yard.vans - yard.boxes
            self.drawn.append(pyglet.shapes.Circle(
                x, y, size * 0.5, color=self.ink, batch=self.batch))
            self.drawn.append(pyglet.shapes.Circle(
                x, y, size * 0.42,
                color=ITEM_COLORS[which % len(ITEM_COLORS)],
                batch=self.batch))
            label, shade = str(which + 1), (0, 0, 0, 255)
        else:
            self._outline(x - size * 0.5, y - size * 0.5, size, size,
                          max(2.0, size * 0.09))
            label, shade = str(node - yard.vans + 1), self.textcolor
        self.drawn.append(pyglet.text.Label(
            label, font_size=calc_fontsize(14), weight='bold',
            color=shade, batch=self.batch, x=x, y=y,
            anchor_x='center', anchor_y='center', font_name=FONTLIST))

    def _arrow(self, from_x: float, from_y: float, to_x: float, to_y: float,
               thick: float, heads: int = 1) -> None:
        """A line with an arrowhead on one end, or on both."""
        self.drawn.append(pyglet.shapes.Line(
            from_x, from_y, to_x, to_y, thickness=thick, color=self.ink,
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
                color=self.ink, batch=self.batch))

    def _draw_move(self, move: Move) -> None:
        """What this move does, over the row of bays.

        Drawn from the move alone. A pack is the thing, an arrow, and
        the holder; when the holder is a van the arrow runs on down
        into its bay instead, which is the only time the row is
        pointed at and still says nothing about what is in it.
        """
        _left, bottom, _width, height = self._stage()
        middle = width_center()
        band = bottom + height * 0.58
        size = self._size()
        thick = max(2.0, size * 0.12)
        gap = size * 1.9
        yard = self.yard()
        if move.kind == PACK and yard.is_van(move.other):
            self._glyph(move.thing, middle, band, size)
            x, y, width, van_height = self._van_rect(move.other)
            self._arrow(middle, band - size * 0.6,
                        x + width / 2, y + van_height * 1.15, thick)
            return
        self._glyph(move.thing, middle - gap, band, size)
        self._glyph(move.other, middle + gap, band, size)
        self._arrow(middle - gap + size * 0.62, band,
                    middle + gap - size * 0.62, band, thick,
                    heads=1 if move.kind == PACK else 2)

    def _draw_question(self) -> None:
        """The thing being asked about, over the bays it might be in."""
        _left, bottom, _width, height = self._stage()
        size = self._size()
        self._glyph(self.round.asked[self.asking_at], width_center(),
                    bottom + height * 0.58, size * 1.3)
        self.drawn.append(pyglet.text.Label(
            _('which van?'), font_size=calc_fontsize(15),
            color=self.textcolor, batch=self.batch, x=width_center(),
            y=bottom + height * 0.40, anchor_x='center', anchor_y='center',
            font_name=FONTLIST))

    def _draw_verdicts(self) -> None:
        """What was said and what was so, one thing to a column."""
        _left, bottom, _width, height = self._stage()
        size = self._size()
        asked = self.round.asked
        span = (state.window.width * 0.8) / max(len(asked), 1)
        for spot, item in enumerate(asked):
            x = state.window.width * 0.1 + span * (spot + 0.5)
            self._glyph(item, x, bottom + height * 0.72, size)
            mine = self.given[spot] if spot < len(self.given) else -1
            truth = self.round.answers[spot]
            said = _('%s  →  %d') % (
                str(mine + 1) if mine >= 0 else '-', truth + 1)
            self.drawn.append(pyglet.text.Label(
                said, font_size=calc_fontsize(14),
                weight='bold' if mine == truth else 'normal',
                color=self.textcolor, batch=self.batch, x=x,
                y=bottom + height * 0.52, anchor_x='center',
                anchor_y='center', font_name=FONTLIST))

    def _update_status(self) -> None:
        parts = [self.message]
        if self.round is not None and self.phase == 'moving':
            parts.append(_('round %d/%d   move %d/%d')
                         % (self.trial, self.total_trials, self.cursor + 1,
                            len(self.round.moves)))
        elif self.round is not None and self.phase == 'asking':
            yard = self.round.yard
            thing = self.round.asked[self.asking_at]
            parts.append(_('thing %d — which van?')
                         % (thing - yard.vans - yard.boxes + 1))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Removals.instance is not self:
            return
        self._clear_drawn()
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        Removals.instance = None

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
            for van in range(MOST_VANS):
                if symbol in (ANSWER_KEYS[van], PAD_KEYS[van]):
                    self.answer(van)
                    break
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
