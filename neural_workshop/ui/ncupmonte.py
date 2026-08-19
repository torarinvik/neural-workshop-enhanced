# -*- coding: utf-8 -*-
"""N-Cup Monte: watch the ball, track the cups, click the right one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import state
from ..constants import FONTLIST
from ..geometry import calc_fontsize, from_bottom_edge, from_top_edge, width_center
from . import cursor, taskoptions
from ..i18n import _


class NCupMonte:
    """Shell game with a growing cup count. Space starts; Esc returns."""

    instance: Optional['NCupMonte'] = None

    def __init__(self) -> None:
        if NCupMonte.instance is not None:
            NCupMonte.instance.close()
        self.cups = 3
        self._read_options()
        self.ball = 0
        self.order: List[int] = list(range(self.cups))
        self.xs: List[float] = []
        self.targets: List[float] = []
        self.start_xs: List[float] = []
        self.phase = 'ready'
        self.swaps: List[Tuple[int, int]] = []
        self.swap_i = 0
        self.swap_t = 0.0
        self.reveal_until = 0.0
        self.message = _('Press Space to hide the ball')
        self.guess: Optional[int] = None
        self.batch = pyglet.graphics.Batch()
        self.shapes: List[object] = []
        self.cup_labels: List[pyglet.text.Label] = []
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.title = pyglet.text.Label(
            _('N-Cup Monte'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: next round     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(30),
            anchor_x='center', anchor_y='center')
        self._place_cups()
        self._redraw()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        cursor.acquire()
        NCupMonte.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        """Load this task's settings from the config."""
        opts = taskoptions.settings(taskoptions.NCUP_MONTE)
        self.start_cups = int(opts['NCUP_MONTE_START_CUPS'])
        self.max_cups = max(self.start_cups, int(opts['NCUP_MONTE_MAX_CUPS']))
        self.adaptive = bool(opts['NCUP_MONTE_ADAPTIVE'])
        self.swap_count = int(opts['NCUP_MONTE_SWAPS'])
        self.swap_duration = int(opts['NCUP_MONTE_SWAP_MS']) / 1000.
        self.reveal_seconds = int(opts['NCUP_MONTE_REVEAL_MS']) / 1000.
        self.show_numbers = bool(opts['NCUP_MONTE_SHOW_CUP_NUMBERS'])
        self.cups = min(max(3, self.start_cups), self.max_cups)

    def open_options(self) -> None:
        """Show this task's settings screen."""
        taskoptions.open_task_options('ncup_monte', on_apply=self.apply_options)

    def apply_options(self) -> None:
        """Re-read the settings and reset to a fresh round."""
        self._read_options()
        self.phase = 'ready'
        self.guess = None
        self.swaps = []
        self.swap_i = 0
        self.message = _('Press Space to hide the ball')
        self._place_cups()
        self._redraw()

    def _slot_positions(self, count: int) -> List[float]:
        window = state.window
        span = min(window.width * 0.78, 120.0 * count)
        start = (window.width - span) / 2
        step = span / max(1, count)
        return [start + (index + 0.5) * step for index in range(count)]

    def _place_cups(self) -> None:
        self.order = list(range(self.cups))
        self.xs = self._slot_positions(self.cups)
        self.targets = list(self.xs)

    def start_round(self) -> None:
        self._place_cups()
        self.ball = random.randrange(self.cups)
        self.guess = None
        self.phase = 'reveal'
        self.reveal_until = time.time() + self.reveal_seconds
        self.message = _('Watch the ball')
        self._redraw()

    def _plan_swaps(self) -> None:
        count = max(1, self.swap_count + self.cups)
        swaps = []
        for _swap in range(count):
            a, b = random.sample(range(self.cups), 2)
            swaps.append((a, b))
        self.swaps = swaps
        self.swap_i = 0

    def _begin_swap(self) -> None:
        if self.swap_i >= len(self.swaps):
            self.xs = self._slot_positions(self.cups)
            self.targets = list(self.xs)
            self.phase = 'guess'
            self.message = _('Which cup hides the ball?')
            self._redraw()
            return
        self.xs = self._slot_positions(self.cups)
        self.start_xs = list(self.xs)
        a, b = self.swaps[self.swap_i]
        self.targets = list(self.xs)
        self.targets[a], self.targets[b] = self.xs[b], self.xs[a]
        self.swap_t = 0.0
        self.phase = 'shuffle'

    def skip_to_guess(self) -> None:
        """Jump to the clickable state. Used by tests."""
        if self.phase == 'ready':
            self._place_cups()
            self.ball = random.randrange(self.cups)
        self.xs = self._slot_positions(self.cups)
        self.targets = list(self.xs)
        self.phase = 'guess'
        self.message = _('Which cup hides the ball?')
        self._redraw()

    def update(self, dt: float) -> None:
        if self.phase == 'reveal' and time.time() >= self.reveal_until:
            self._plan_swaps()
            self._begin_swap()
            return
        if self.phase != 'shuffle':
            return
        self.swap_t += dt
        progress = min(1.0, self.swap_t / self.swap_duration)
        eased = progress * progress * (3 - 2 * progress)
        origin = self.start_xs
        self.xs = [origin[i] + (self.targets[i] - origin[i]) * eased
                   for i in range(self.cups)]
        if progress >= 1.0:
            a, b = self.swaps[self.swap_i]
            self.order[a], self.order[b] = self.order[b], self.order[a]
            self.xs = self._slot_positions(self.cups)
            self.swap_i += 1
            self._begin_swap()
        self._redraw()

    def cup_at(self, x: float, y: float) -> Optional[int]:
        cup_w, cup_h = self._cup_size()
        base_y = state.window.height * 0.38
        if not (base_y <= y <= base_y + cup_h):
            return None
        for index, cx in enumerate(self.xs):
            if abs(x - cx) <= cup_w / 2:
                return self.order[index]
        return None

    def _cup_size(self) -> Tuple[float, float]:
        width = max(48.0, min(96.0, state.window.width / (self.cups + 2)))
        return width, width * 1.15

    def choose_cup(self, cup_id: int) -> None:
        if self.phase != 'guess':
            return
        self.guess = cup_id
        self.phase = 'result'
        if cup_id == self.ball:
            if self.adaptive:
                self.cups = min(self.max_cups, self.cups + 1)
            self.message = (_('Caught it — now %d cups') % self.cups
                            if self.adaptive else _('Caught it'))
        else:
            if self.adaptive:
                self.cups = max(3, self.cups - 1)
            self.message = (_('Miss — back to %d cups') % self.cups
                            if self.adaptive else _('Miss'))
        self._place_cups()
        self._redraw()

    def _redraw(self) -> None:
        for shape in self.shapes:
            try:
                shape.delete()
            except Exception:
                pass
        self.shapes = []
        for label in self.cup_labels:
            label.delete()
        self.cup_labels = []
        cup_w, cup_h = self._cup_size()
        base_y = state.window.height * 0.38
        show_ball = self.phase in ('ready', 'reveal', 'result')
        for visual_index, cup_id in enumerate(self.order):
            cx = self.xs[visual_index]
            chosen = self.phase == 'result' and cup_id == self.guess
            correct = self.phase == 'result' and cup_id == self.ball
            if correct:
                fill = (46, 170, 92, 255)
            elif chosen:
                fill = (220, 64, 64, 255)
            else:
                fill = (196, 92, 48, 255)
            rect = pyglet.shapes.Rectangle(
                cx - cup_w / 2, base_y, cup_w, cup_h, color=fill,
                batch=self.batch)
            brim = pyglet.shapes.Rectangle(
                cx - cup_w / 2 - 4, base_y + cup_h - 10, cup_w + 8, 12,
                color=(220, 120, 64, 255), batch=self.batch)
            self.shapes.extend([rect, brim])
            if show_ball and cup_id == self.ball:
                ball = pyglet.shapes.Circle(
                    cx, base_y + 16, 11, color=(240, 220, 70, 255),
                    batch=self.batch)
                self.shapes.append(ball)
            if self.show_numbers:
                label = pyglet.text.Label(
                    str(cup_id + 1), font_size=calc_fontsize(14),
                    weight='bold', color=(255, 255, 255, 255),
                    batch=self.batch, x=cx, y=base_y + cup_h / 2,
                    anchor_x='center', anchor_y='center', font_name=FONTLIST)
                self.cup_labels.append(label)
        self.status.text = _('Cups %d — %s') % (self.cups, self.message)

    def close(self) -> None:
        if NCupMonte.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        cursor.release()
        NCupMonte.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='misc')

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'result'):
            self.start_round()
        elif symbol == key.C:
            self.open_options()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        cup_id = self.cup_at(x, y)
        if cup_id is not None:
            self.choose_cup(cup_id)
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
