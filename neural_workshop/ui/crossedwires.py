# -*- coding: utf-8 -*-
"""The Crossed Wires screen: the keys are labelled, and the labels lie.

The thinking lives in :mod:`neural_workshop.crossedwires`; this module
is the grid drawn on screen and the keys that drive it. Three
decisions matter here:

* Nothing on screen says what any key does, at any point, ever. There
  is no legend, no readout of what has been worked out so far, and no
  mark on the key just pressed. A player who wants to know what a key
  does presses it and watches, and a player who wants to remember what
  it did remembers — putting either on the screen would hand over the
  whole task.

* The keys are the ones whose meaning is obvious. Arrows and ``WASD``
  on the four-key rungs, the ring ``Q W E / A D / Z X C`` and the
  numeric keypad on the eight. Labelling them plainly is the joke and
  also the point: the difficulty is not in an unfamiliar control, it
  is in a familiar one that has been quietly rewired, which is a
  harder thing to hold in mind than an arbitrary one.

* What is left is drawn as a bar as well as a number. An agent reads
  this screen as pixels, and a budget it can only find out by parsing
  a glyph is a budget it effectively cannot see — so the one quantity
  a player must act on is shown as a length.

The grid wraps, and the marker crossing an edge and appearing at the
other one is drawn exactly as it happens, with no animation between.
That looks abrupt and is meant to: a wrapped step is one step, and
drawing it as a long slide across the board would say otherwise.

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
from ..crossedwires import GRADES, Bench, deal
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from . import cursor, taskoptions
from .verdict import VerdictLabel
from ..i18n import _

#: The four keys, clockwise from north, three ways of naming them.
FOUR_KEYS: Tuple[Tuple[int, ...], ...] = (
    (key.UP, key.W, key.NUM_8),
    (key.RIGHT, key.D, key.NUM_6),
    (key.DOWN, key.S, key.NUM_2),
    (key.LEFT, key.A, key.NUM_4),
)

#: The eight, clockwise from north: the ring of letters round ``S``,
#: and the keypad, which has the same shape under the fingers.
EIGHT_KEYS: Tuple[Tuple[int, ...], ...] = (
    (key.W, key.NUM_8, key.UP),
    (key.E, key.NUM_9),
    (key.D, key.NUM_6, key.RIGHT),
    (key.C, key.NUM_3),
    (key.X, key.NUM_2, key.DOWN),
    (key.Z, key.NUM_1),
    (key.A, key.NUM_4, key.LEFT),
    (key.Q, key.NUM_7),
)

#: Okabe-Ito. The marker is the reddish purple and the target the
#: bluish green, which are the two furthest apart in the set for
#: anybody who cannot tell red from green.
MARKER = (204, 121, 167)
TARGET = (0, 158, 115)
GRID = (128, 128, 128)

#: How long the tally stays up before the next round can be called.
VERDICT_SECONDS = 0.8

#: Reach every target and an adaptive run climbs; reach fewer than
#: half and it drops.
CLIMB_AT = 1.0
DROP_BELOW = 0.5


def keys_for(count: int) -> Tuple[Tuple[int, ...], ...]:
    """Which keys drive a rung with this many of them."""
    return EIGHT_KEYS if count == 8 else FOUR_KEYS


class CrossedWires:
    """Find out what the keys do by doing it. Esc returns to the hub."""

    instance: Optional['CrossedWires'] = None

    def __init__(self) -> None:
        if CrossedWires.instance is not None:
            CrossedWires.instance.close()
        self.rng = random.Random()
        #: Swapped out by the agent environment for a virtual clock.
        self.clock = time.time
        self.bench: Optional[Bench] = None
        self.until = 0.0
        self.trial = 0
        self.results: List[Tuple[int, int, int]] = []   # (rung, got, asked)
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self._read_options()
        self.rung = self.clamped(self.start_rung)
        self.drawn: List[object] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        cursor.acquire()
        display.register_overlay(self)
        CrossedWires.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.CROSSED_WIRES)
        self.start_rung = int(opts['WIRES_LEVEL'])
        self.total_trials = int(opts['WIRES_ROUNDS'])
        self.adaptive = bool(opts['WIRES_ADAPTIVE'])
        self.show_grid = bool(opts['WIRES_GRID'])

    @staticmethod
    def clamped(rung: int) -> int:
        return max(1, min(len(GRADES), rung))

    def open_options(self) -> None:
        taskoptions.open_task_options('crossed_wires',
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
            _('Crossed Wires'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     O: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        # Read by the agent boundary, which pays the round by its
        # colour. The budget bar is the one other thing this task draws
        # low down, and its reddish purple misses being read as a
        # verdict by 27 on the blue channel — close enough that
        # tests/check_band.py exists to say so rather than a comment
        # claiming it. Rebuilt with the chrome, so a verdict already up
        # is put back: a relayout on the frame a round settles would
        # otherwise drop it, and an outcome that is only sometimes
        # derivable is worse than one that never is.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if getattr(self, 'verdict_shown', None) is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def relayout(self) -> None:
        self._build_chrome()

    def grade(self):
        return GRADES[self.rung - 1]

    def _board(self) -> Tuple[float, float, float]:
        """Left, bottom and the side of one cell, for a square board."""
        window = state.window
        top = from_top_edge(100)
        bottom = from_bottom_edge(78)
        grade = self.grade()
        side = min((top - bottom) / grade.down, window.width * 0.8
                   / grade.across)
        side = max(4.0, side)
        return (width_center() - side * grade.across / 2.0,
                bottom + ((top - bottom) - side * grade.down) / 2.0, side)

    def _cell_rect(self, spot: Tuple[int, int]) -> Tuple[float, float, float]:
        left, bottom, side = self._board()
        return (left + spot[0] * side, bottom + spot[1] * side, side)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.bench = None
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
        self.bench = Bench(deal(self.rung, seed=self.rng.randrange(1 << 30)))
        self.phase = 'playing'
        grade = self.grade()
        self.message = _('%s — %d keys, %d targets') % (
            _(grade.name), grade.keys, grade.targets)
        self._redraw()

    def press(self, keyed: int) -> None:
        """Press one key, and settle the round when it is spent."""
        if self.phase != 'playing' or self.bench is None:
            return
        self.bench.press(keyed)
        if self.bench.over():
            self._settle()
        self._redraw()

    def _settle(self) -> None:
        got = self.bench.reached
        asked = len(self.bench.bout.goals)
        self.results.append((self.rung, got, asked))
        if got == asked:
            self.message = _('All %d reached') % asked
        else:
            self.message = _('%d of %d reached, out of presses') % (got, asked)
        share = got / float(asked)
        if self.adaptive:
            if share >= CLIMB_AT:
                self.rung = self.clamped(self.rung + 1)
            elif share < DROP_BELOW:
                self.rung = self.clamped(self.rung - 1)
        self.phase = 'scored'
        self.until = self.clock() + VERDICT_SECONDS
        # Only now: the budget is spent or every target is reached, and
        # no further press can change what this says.
        self.verdict_shown = (got == asked, self.message)
        self.verdict.show(*self.verdict_shown)

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d rounds, %d%% of targets reached, highest '
                         'rung %d') % (tally['rounds'], tally['accuracy'],
                                       tally['best_rung'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        got = sum(hit for _r, hit, _a in self.results)
        asked = sum(count for _r, _g, count in self.results)
        return {
            'rounds': len(self.results),
            'accuracy': int(round(100. * got / asked)) if asked else 0,
            'best_rung': max((rung for rung, _g, _a in self.results),
                             default=0),
            'perfect': sum(1 for _r, hit, count in self.results
                           if hit == count),
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
        if self.bench is not None and self.phase in ('playing', 'scored'):
            self._draw_board()
            self._draw_target()
            self._draw_marker()
            self._draw_budget()
        self._update_status()

    def _draw_board(self) -> None:
        """The floor, and the lines that make the steps countable."""
        left, bottom, side = self._board()
        grade = self.grade()
        width, height = side * grade.across, side * grade.down
        thick = max(1.0, side * 0.06)
        self.drawn.append(pyglet.shapes.Rectangle(
            left, bottom, width, height, color=self.ink, batch=self.batch))
        self.drawn.append(pyglet.shapes.Rectangle(
            left + thick, bottom + thick, width - thick * 2,
            height - thick * 2, color=self.background, batch=self.batch))
        if not self.show_grid:
            return
        for column in range(1, grade.across):
            self.drawn.append(pyglet.shapes.Line(
                left + column * side, bottom, left + column * side,
                bottom + height, thickness=1.0, color=GRID,
                batch=self.batch))
        for row in range(1, grade.down):
            self.drawn.append(pyglet.shapes.Line(
                left, bottom + row * side, left + width, bottom + row * side,
                thickness=1.0, color=GRID, batch=self.batch))

    def _draw_target(self) -> None:
        """The target: a ring, so the marker on top of it still reads."""
        x, y, side = self._cell_rect(self.bench.goal())
        middle = (x + side / 2, y + side / 2)
        self.drawn.append(pyglet.shapes.Circle(
            middle[0], middle[1], side * 0.46, color=TARGET,
            batch=self.batch))
        self.drawn.append(pyglet.shapes.Circle(
            middle[0], middle[1], side * 0.30, color=self.background,
            batch=self.batch))

    def _draw_marker(self) -> None:
        x, y, side = self._cell_rect(self.bench.at)
        self.drawn.append(pyglet.shapes.Circle(
            x + side / 2, y + side / 2, side * 0.28, color=MARKER,
            batch=self.batch))

    def _draw_budget(self) -> None:
        """What is left, as a length as well as a number.

        The number is for a person and the bar is for an agent reading
        pixels — the one quantity a player has to act on should not
        have to be read out of a glyph.
        """
        left, bottom, side = self._board()
        grade = self.grade()
        width = side * grade.across
        height = max(4.0, side * 0.3)
        foot = bottom - height * 2.2
        self.drawn.append(pyglet.shapes.Rectangle(
            left, foot, width, height, color=GRID, batch=self.batch))
        share = self.bench.left() / float(max(1, self.bench.bout.budget))
        if share > 0:
            self.drawn.append(pyglet.shapes.Rectangle(
                left, foot, width * share, height, color=MARKER,
                batch=self.batch))

    def _update_status(self) -> None:
        parts = [self.message]
        if self.bench is not None and self.phase == 'playing':
            parts.append(_('round %d/%d   target %d/%d   %d presses left')
                         % (self.trial, self.total_trials,
                            min(self.bench.goal_at + 1,
                                len(self.bench.bout.goals)),
                            len(self.bench.bout.goals), self.bench.left()))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if CrossedWires.instance is not self:
            return
        self._clear_drawn()
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        CrossedWires.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='reasoning')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            elif self.phase == 'scored' and self.clock() >= self.until:
                self._next_trial()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.F11:
            display.toggle_fullscreen()
            return pyglet.event.EVENT_HANDLED
        if symbol == key.O:
            # Options open on O rather than the usual C, because on
            # the eight-key rungs C is south-east. A settings screen
            # that vanishes at level six would be worse than an
            # unfamiliar shortcut.
            self.open_options()
            return pyglet.event.EVENT_HANDLED
        for keyed, named in enumerate(keys_for(self.grade().keys)):
            if symbol in named:
                self.press(keyed)
                return pyglet.event.EVENT_HANDLED
        if symbol == key.C:
            self.open_options()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
