# -*- coding: utf-8 -*-
"""Sonar: ping to learn where the target is, dig to claim it.

The grid hides one target. Click a cell to ping it: it costs a point
and shows how far the target is, in bands. Shift-click (or right-click)
to dig: right, and the round is won; wrong, and it costs the rung's
penalty. The round passes if what it cost comes in at or under par —
what a Bayesian reference player paid on the identical deal, plus or
minus the rung's slack. :mod:`neural_workshop.sonar` has the rules,
the ladder and the reference; this module draws the board.

A ping's reading stays on its cell and fades as actions pass, because
on a drifting rung an old reading is worth less than a new one and the
board should say so. Readings are shades of one blue, darker for
nearer, and the number is printed on the cell, so the board reads the
same for someone who cannot tell the shades apart.

For the agent boundary the board is steered, as Sudoku's is: four
ports move a cursor, which costs nothing, one pings under it and one
digs under it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import display, sonar as rules, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

#: Seconds the verdict stays up before the next round.
FEEDBACK = 1.8

#: The cursor's moves, as the agent's first four ports.
STEPS = ((0, -1), (0, 1), (-1, 0), (1, 0))

UNKNOWN_LIGHT = (226, 230, 236)
UNKNOWN_DARK = (46, 50, 58)
MISSED = (150, 150, 150)
FOUND = (238, 196, 64)
CURSOR = (40, 90, 220)


def reading_colour(reading: int, bands: int, age: int,
                   dark: bool) -> Tuple[int, int, int]:
    """One blue, darker for nearer, faded towards the board with age."""
    near = 1.0 - reading / float(max(1, bands - 1))
    base = (int(200 - 150 * near), int(222 - 132 * near),
            int(250 - 40 * near))
    fade = min(0.75, age * 0.07)
    back = UNKNOWN_DARK if dark else UNKNOWN_LIGHT
    return tuple(int(c + (b - c) * fade) for c, b in zip(base, back))


class Sonar:
    """Find the hidden target for less than the reference paid."""

    instance: Optional['Sonar'] = None

    def __init__(self) -> None:
        if Sonar.instance is not None:
            Sonar.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.round: Optional[rules.Round] = None
        self.par = 0.0
        self.rung = 1
        self.trial = 0
        self.at = (0, 0)
        self.feedback_until = 0.0
        self.started_at = 0.0
        self.results: List[Tuple[int, bool, float, float]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.drawn: List[object] = []
        self._read_options()
        self.message = _('Press Space to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        Sonar.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.SONAR)
        self.start_rung = int(opts['SONAR_RUNG'])
        self.total_trials = int(opts['SONAR_TRIALS'])
        self.adaptive = bool(opts['SONAR_ADAPTIVE'])
        self.rung = max(1, self.start_rung)

    def open_options(self) -> None:
        taskoptions.open_task_options('sonar', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        self.dark = bool(state.cfg.BLACK_BACKGROUND)
        fg = 255 if self.dark else 0
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.cell_group = pyglet.graphics.Group(order=0)
        self.mark_group = pyglet.graphics.Group(order=1)
        self.text_group = pyglet.graphics.Group(order=2)
        self.title = pyglet.text.Label(
            _('Sonar'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.prices = pyglet.text.Label(
            '', font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(96),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('click: ping    Shift-click or right-click: dig    '
              'arrows + P / D    Esc: menu    C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _board(self) -> Tuple[float, float, float]:
        """Left, bottom and size of the square board."""
        window = state.window
        top = from_top_edge(116)
        bottom = above_the_band(from_bottom_edge(58))
        size = max(40.0, min(window.width * 0.9, top - bottom))
        return ((window.width - size) / 2.0,
                bottom + (top - bottom - size) / 2.0, size)

    def _cell_rect(self, cell: rules.Cell) -> Tuple[float, float, float]:
        left, bottom, size = self._board()
        side = self.round.level.side
        span = size / side
        x, y = cell
        return (left + x * span, bottom + size - (y + 1) * span, span)

    def _at(self, x: float, y: float) -> Optional[rules.Cell]:
        if self.round is None:
            return None
        left, bottom, size = self._board()
        side = self.round.level.side
        if not (left <= x < left + size and bottom <= y < bottom + size):
            return None
        span = size / side
        return (int((x - left) / span),
                int((bottom + size - y) / span))

    def relayout(self) -> None:
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.round = None
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self.rung = max(1, self.start_rung)
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.trial += 1
        dealt = rules.deal(self.rung, rng=self.rng)
        self.round = rules.Round(dealt)
        self.par = rules.par(dealt)
        side = dealt.level.side
        self.at = (side // 2, side // 2)
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'searching'
        self.message = _('Find it for %s or less') % _points(self.par)
        self._redraw()

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        """One agent port: four cursor moves, then ping, then dig."""
        if self.phase != 'searching' or self.round is None:
            return
        if port < len(STEPS):
            dx, dy = STEPS[port]
            side = self.round.level.side
            self.at = (max(0, min(side - 1, self.at[0] + dx)),
                       max(0, min(side - 1, self.at[1] + dy)))
            self._redraw()
        elif port == len(STEPS):
            self.ping(self.at)
        else:
            self.dig(self.at)

    def ping(self, cell: rules.Cell) -> None:
        if self.phase != 'searching' or self.round is None:
            return
        self.at = cell
        self.round.ping(cell)
        self._after()

    def dig(self, cell: rules.Cell) -> None:
        if self.phase != 'searching' or self.round is None:
            return
        self.at = cell
        self.round.dig(cell)
        self._after()

    def _after(self) -> None:
        play = self.round
        if play.over:
            self._judge()
        else:
            self._redraw()

    def _judge(self) -> None:
        play = self.round
        passed = play.found and play.cost <= self.par + 1e-9
        took = self.clock() - self.started_at
        self.results.append((play.level.rung, passed, play.cost, took))
        if self.adaptive:
            self.rung = self.rung + 1 if passed else max(1, self.rung - 1)
        self.phase = 'judged'
        self.feedback_until = self.clock() + FEEDBACK
        if not play.found:
            self.message = _('Out of moves after spending %s') % \
                _points(play.cost)
        else:
            self.message = (_('Found for %s; par was %s')
                            % (_points(play.cost), _points(self.par)))
        self.verdict_shown = (passed, self.message)
        self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        self.round = None
        tally = self.score()
        self.message = (_('%d of %d under par   highest rung passed %d')
                        % (tally['passed'], tally['trials'],
                           tally['best_rung']))
        self._redraw()

    def score(self) -> Dict[str, float]:
        trials = len(self.results)
        return {
            'trials': trials,
            'passed': sum(1 for r in self.results if r[1]),
            'best_rung': max((r[0] for r in self.results if r[1]),
                             default=0),
            'mean_cost': (sum(r[2] for r in self.results) / trials
                          if trials else 0.0),
        }

    def update(self, dt: float) -> None:
        if self.phase == 'judged' and self.clock() >= self.feedback_until:
            self._next_trial()

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []

    def _redraw(self) -> None:
        self._clear_drawn()
        play = self.round
        if self.phase in ('searching', 'judged') and play is not None:
            level = play.level
            back = UNKNOWN_DARK if self.dark else UNKNOWN_LIGHT
            gap = 1.0
            latest: Dict[rules.Cell, Tuple[int, int]] = {}
            for index, (cell, reading) in enumerate(play.pings):
                latest[cell] = (reading, index)
            # An action index for each ping, so age is in actions taken.
            ping_actions = self._ping_action_indices()
            for y in range(level.side):
                for x in range(level.side):
                    cell = (x, y)
                    left, bottom, span = self._cell_rect(cell)
                    colour = back
                    text = ''
                    if cell in play.misses:
                        colour, text = MISSED, '×'
                    elif cell in latest:
                        reading, index = latest[cell]
                        age = play.actions - ping_actions[index]
                        colour = reading_colour(reading, level.bands, age,
                                                self.dark)
                        text = str(reading)
                    if self.phase == 'judged' and play.found \
                            and cell == play.target:
                        colour, text = FOUND, '★'
                    self.drawn.append(pyglet.shapes.Rectangle(
                        left + gap, bottom + gap, span - 2 * gap,
                        span - 2 * gap, color=colour, batch=self.batch,
                        group=self.cell_group))
                    if text and span >= 14:
                        shade = 255 if sum(colour) < 380 else 20
                        self.drawn.append(pyglet.text.Label(
                            text, font_size=max(6.0, span * 0.32),
                            color=(shade, shade, shade, 255),
                            x=left + span / 2, y=bottom + span / 2,
                            anchor_x='center', anchor_y='center',
                            batch=self.batch, group=self.text_group,
                            font_name=FONTLIST))
            if self.phase == 'searching':
                left, bottom, span = self._cell_rect(self.at)
                self.drawn.append(pyglet.shapes.Box(
                    left, bottom, span, span, thickness=3, color=CURSOR,
                    batch=self.batch, group=self.mark_group))
        self._update_labels()

    def _ping_action_indices(self) -> List[int]:
        """The action number each ping was, so age counts digs too."""
        return [index for index, kind in enumerate(self.round.log)
                if kind == 'ping']

    def _update_labels(self) -> None:
        self.status.text = self.message
        play = self.round
        if self.phase in ('searching', 'judged') and play is not None:
            level = play.level
            parts = [_('rung %d  %d/%d') % (level.rung, self.trial,
                                            self.total_trials),
                     _('spent %s') % _points(play.cost),
                     _('wrong dig %s') % _points(level.penalty),
                     (_('reading = cells away') if level.width == 1
                      else _('reading = cells away ÷ %d') % level.width)]
            if level.noise:
                parts.append(_('noise %d%%') % round(level.noise * 100))
            if level.drift:
                parts.append(_('drift %d%%') % round(level.drift * 100))
            self.prices.text = '   '.join(parts)
        else:
            self.prices.text = ''

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Sonar.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        self._clear_drawn()
        Sonar.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='decisions')

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
        elif self.phase == 'searching':
            moves = {key.UP: 0, key.DOWN: 1, key.LEFT: 2, key.RIGHT: 3}
            if symbol in moves:
                self.steer(moves[symbol])
            elif symbol in (key.P, key.SPACE):
                self.ping(self.at)
            elif symbol in (key.D, key.RETURN, key.ENTER):
                self.dig(self.at)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase != 'searching':
            return pyglet.event.EVENT_HANDLED
        cell = self._at(x, y)
        if cell is None:
            return pyglet.event.EVENT_HANDLED
        if button == mouse.RIGHT or modifiers & key.MOD_SHIFT:
            self.dig(cell)
        else:
            self.ping(cell)
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


def _points(value: float) -> str:
    return ('%d' % value) if float(value).is_integer() else ('%.1f' % value)
