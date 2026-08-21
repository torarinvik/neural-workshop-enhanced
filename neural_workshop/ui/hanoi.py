# -*- coding: utf-8 -*-
"""Tower of Hanoi: move the tower, planning ahead of your hands.

Three pegs, a tower of disks on the first, and two rules: one disk
moves at a time, and a disk never rests on a smaller one. The task is
old and the reason it keeps being used is what it isolates: nothing is
hidden and nothing is uncertain, so the only thing being exercised is
planning — every move either serves a sub-goal you have already formed
or undoes one you had not.

The minimum is exact and famous: a tower of n disks moves in 2^n - 1
moves and no fewer. A round is scored against that, because merely
finishing measures patience. Moving the small disk back and forth
finishes eventually; knowing *why* the small disk must go where it
goes finishes at the minimum, and the gap between the two is the
score.

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
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel

#: Towers a puzzle may hold. Three disks is seven moves, a child's
#: puzzle; twelve disks is 4095 and a siege. The ceiling is visual,
#: not logical: the widths step by widest/16 per disk, and past twelve
#: neighbouring disks stop being tellable apart at a glance, which is
#: the one judgement the game needs the eye to make.
SMALLEST_TOWER, LARGEST_TOWER = 3, 12

#: How efficient a solve has to be before an adaptive run adds a disk,
#: and how far below that it falls before one is taken away.
#: Efficiency is the minimum move count over the moves used.
GROW_AT, SHRINK_AT = 0.8, 0.5

#: Okabe-Ito colours for the disks, biggest first, so neighbouring
#: sizes are never neighbouring hues and the tower reads at a glance.
DISK_COLORS = ((230, 159, 0, 255), (86, 180, 233, 255),
               (0, 158, 115, 255), (240, 228, 66, 255),
               (0, 114, 178, 255), (213, 94, 0, 255),
               (204, 121, 167, 255), (153, 153, 153, 255))


def minimum_moves(disks: int) -> int:
    """The fewest moves that shift a tower of *disks*: 2^n - 1."""
    return (1 << disks) - 1


def fresh_pegs(disks: int) -> List[List[int]]:
    """The starting position: every disk on the first peg, size
    order, biggest at the bottom. Disks are named by size, so the
    list reads bottom to top."""
    return [list(range(disks, 0, -1)), [], []]


def can_move(pegs: List[List[int]], source: int, target: int) -> bool:
    """Whether the top of *source* may go onto *target*."""
    if not pegs[source] or source == target:
        return False
    return not pegs[target] or pegs[source][-1] < pegs[target][-1]


def solved(pegs: List[List[int]], disks: int) -> bool:
    """The tower is rebuilt somewhere it did not start."""
    return any(len(peg) == disks for peg in pegs[1:])


class TowerOfHanoi:
    """Show the pegs, take clicks or keys, score against 2^n - 1."""

    instance: Optional['TowerOfHanoi'] = None

    def __init__(self) -> None:
        if TowerOfHanoi.instance is not None:
            TowerOfHanoi.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.pegs: List[List[int]] = []
        self.disks = SMALLEST_TOWER
        self.trial_disks = SMALLEST_TOWER
        self.picked: Optional[int] = None
        self.moves = 0
        self.par = 0
        self.round = 0
        self.started_at = 0.0
        self.feedback_until = 0.0
        self.results: List[Tuple[int, float, float]] = []
        self.phase = 'ready'
        self.drawn: List[object] = []
        self._read_options()
        self.message = _('Press Space to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        TowerOfHanoi.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.HANOI)
        self.start_disks = int(opts['HANOI_DISKS'])
        self.total_rounds = int(opts['HANOI_ROUNDS'])
        self.adaptive = bool(opts['HANOI_ADAPTIVE'])
        self.disks = self.clamped(self.start_disks)

    @staticmethod
    def clamped(disks: int) -> int:
        return max(SMALLEST_TOWER, min(LARGEST_TOWER, disks))

    def open_options(self) -> None:
        taskoptions.open_task_options('hanoi', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.woodcolor = (fg, fg, fg, 90)
        self.accent = (64, 96, 255, 255)
        self.batch = pyglet.graphics.Batch()
        self.title = pyglet.text.Label(
            _('Tower of Hanoi'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     click or 1-3: pegs'
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

    def _canvas(self) -> Tuple[float, float, float, float]:
        window = state.window
        top = from_top_edge(110)
        bottom = from_bottom_edge(64)
        return (window.width * 0.06, bottom,
                window.width * 0.88, max(40.0, top - bottom))

    def _peg_rects(self) -> List[Tuple[float, float, float, float]]:
        """Each peg's clickable column: left, bottom, width, height."""
        left, bottom, width, height = self._canvas()
        span = width / 3.0
        return [(left + peg * span, bottom, span, height)
                for peg in range(3)]

    def relayout(self) -> None:
        self._build_chrome()

    # --- a round ---------------------------------------------------------

    def _reset(self) -> None:
        self.round = 0
        self.results = []
        self.pegs = []
        self.picked = None
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> None:
        self._reset()
        self.disks = self.clamped(self.start_disks)
        self._next_round()

    def _next_round(self) -> None:
        if self.round >= self.total_rounds:
            self._finish()
            return
        self.round += 1
        self.trial_disks = self.disks
        self.pegs = fresh_pegs(self.trial_disks)
        self.par = minimum_moves(self.trial_disks)
        self.moves = 0
        self.picked = None
        self.verdict_shown = None
        self.verdict.clear()
        self.started_at = self.clock()
        self.phase = 'solving'
        self.message = _('Rebuild the tower on another peg')
        self._redraw()

    def _pick(self, peg: int) -> None:
        """First choice lifts a top disk; the second sets it down."""
        if self.phase != 'solving' or not 0 <= peg < 3:
            return
        if self.picked is None:
            if self.pegs[peg]:
                self.picked = peg
        elif self.picked == peg:
            self.picked = None
        elif can_move(self.pegs, self.picked, peg):
            self.pegs[peg].append(self.pegs[self.picked].pop())
            self.moves += 1
            self.picked = None
            if solved(self.pegs, self.trial_disks):
                self._solved()
        else:
            # An illegal set-down is refused, not scored: the rule is
            # part of the puzzle's furniture, and fat-fingering it
            # should not poison a plan being executed well.
            self.picked = None
        self._redraw()

    def _solved(self) -> None:
        took = self.clock() - self.started_at
        efficiency = self.par / max(self.par, self.moves)
        self.results.append((self.trial_disks, efficiency, took))
        if self.adaptive:
            if efficiency >= GROW_AT:
                self.disks = self.clamped(self.disks + 1)
            elif efficiency < SHRINK_AT:
                self.disks = self.clamped(self.disks - 1)
        self.phase = 'solved'
        self.feedback_until = self.clock() + 1.6
        self.message = (_('Solved in %d moves — the minimum is %d — '
                          'in %.0fs') % (self.moves, self.par, took))
        # Green means the exact minimum, which for this puzzle is
        # known in closed form rather than searched for: the tower is
        # the one task here where "perfect" is a formula.
        self.verdict_shown = (self.moves <= self.par, self.message)
        self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        self.pegs = []
        tally = self.score()
        self.message = _('%d towers, %d%% move efficiency, %.0fs each, '
                         'largest tower %d disks'
                         ) % (tally['rounds'], tally['efficiency'],
                              tally['mean_seconds'], tally['best_disks'])
        self._redraw()

    def score(self) -> Dict[str, float]:
        rounds = len(self.results)
        return {
            'rounds': rounds,
            'efficiency': int(round(100 * sum(eff for _d, eff, _t
                                              in self.results) / rounds)
                              ) if rounds else 0,
            'mean_seconds': (sum(took for _d, _e, took in self.results)
                             / rounds) if rounds else 0.0,
            'best_disks': max((disks for disks, _e, _t in self.results),
                              default=0),
        }

    def update(self, dt: float) -> None:
        if self.phase == 'solved' and self.clock() >= self.feedback_until:
            self._next_round()

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
        if self.phase in ('solving', 'solved') and self.pegs:
            left, bottom, width, height = self._canvas()
            span = width / 3.0
            post_height = min(height * 0.8,
                              (self.trial_disks + 2) * height * 0.11)
            disk_height = post_height / (self.trial_disks + 1.5)
            widest = span * 0.9
            for peg, rect in enumerate(self._peg_rects()):
                centre = rect[0] + span / 2.0
                self.drawn.append(pyglet.shapes.Rectangle(
                    centre - 2, bottom, 4, post_height,
                    color=self.woodcolor, batch=self.batch))
                self.drawn.append(pyglet.shapes.Rectangle(
                    rect[0] + span * 0.05, bottom - 6, span * 0.9, 6,
                    color=self.woodcolor, batch=self.batch))
                if peg == self.picked:
                    self.drawn.append(pyglet.shapes.Box(
                        rect[0] + 2, bottom - 10, span - 4,
                        post_height + 14, thickness=2.5,
                        color=self.accent, batch=self.batch))
                for stacked, disk in enumerate(self.pegs[peg]):
                    share = disk / float(self.trial_disks)
                    disk_width = widest * (0.25 + 0.75 * share)
                    lifted = (peg == self.picked
                              and stacked == len(self.pegs[peg]) - 1)
                    self.drawn.append(pyglet.shapes.Rectangle(
                        centre - disk_width / 2,
                        bottom + stacked * (disk_height + 2)
                        + (14 if lifted else 0),
                        disk_width, disk_height,
                        color=DISK_COLORS[(disk - 1) % len(DISK_COLORS)],
                        batch=self.batch))
        self._update_labels()

    def _update_labels(self) -> None:
        parts = [self.message]
        if self.phase in ('solving', 'solved'):
            parts.append(_('tower %d of %d   moves %d   minimum %d   '
                           '%d disks')
                         % (self.round, self.total_rounds, self.moves,
                            self.par, self.trial_disks))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if TowerOfHanoi.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        self._clear_drawn()
        TowerOfHanoi.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='planning')

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
        elif key._1 <= symbol <= key._3:
            self._pick(symbol - key._1)
        elif key.NUM_1 <= symbol <= key.NUM_3:
            self._pick(symbol - key.NUM_1)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase == 'solving':
            for peg, (left, bottom, width, height) in \
                    enumerate(self._peg_rects()):
                if left <= x <= left + width \
                        and bottom - 12 <= y <= bottom + height:
                    self._pick(peg)
                    break
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
