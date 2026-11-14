# -*- coding: utf-8 -*-
"""The screen every laddered, trial-by-trial task shares.

Gamble, Bluff, Forms and the rest each carry the same two hundred lines:
a ladder of rungs climbed at par and dropped under it, a run of trials,
the verdict label the agent boundary reads, a title and two lines of
status, click targets rebuilt with every redraw, and the handlers pushed
on and taken off the window. A task built on :class:`RungTask` supplies
only what is its own:

``_deal()``         set up the next trial; False (with :attr:`message`
                    set) when it cannot, which leaves the task waiting
``_draw(...)``      draw the trial into the playing area, adding click
                    targets to :attr:`hits`
``_facts()``        the second status line
``steer(port)``     one agent port
``_key(symbol)``    the task's own keys

and calls :meth:`_judge` when a trial resolves.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Callable, Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key, mouse

from .. import display, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        width_center)
from ..i18n import _
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band

Hit = Tuple[float, float, float, float, Callable[[], None]]


class RungTask:
    """A run of trials on a ladder, judged one at a time."""

    instance: Optional['RungTask'] = None

    TITLE = ''
    TASK_ID = ''
    #: Options are PREFIX_RUNG, PREFIX_TRIALS and PREFIX_ADAPTIVE.
    PREFIX = ''
    CATEGORY = 'reasoning'
    FOOTNOTE = ''
    #: The phase a trial is played in.
    PLAY = 'playing'
    #: Seconds the verdict stays up before the next trial.
    FEEDBACK = 2.5

    def __init__(self) -> None:
        cls = type(self)
        if cls.instance is not None:
            cls.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.rung = 1
        self.trial = 0
        self.started_at = 0.0
        self.feedback_until = 0.0
        self.results: List[Tuple[int, bool]] = []
        self.phase = 'ready'
        self.verdict_shown: Optional[Tuple[bool, str]] = None
        self.drawn: List[object] = []
        self.hits: List[Hit] = []
        self._read_options()
        self.message = _('Press Space or click to start')
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        cls.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        prefix = self.PREFIX
        opts = taskoptions.settings(getattr(taskoptions, prefix))
        self.start_rung = int(opts[prefix + '_RUNG'])
        self.total_trials = int(opts[prefix + '_TRIALS'])
        self.adaptive = bool(opts[prefix + '_ADAPTIVE'])
        self.rung = max(1, self.start_rung)

    def open_options(self) -> None:
        taskoptions.open_task_options(self.TASK_ID,
                                      on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        self.dark = bool(state.cfg.BLACK_BACKGROUND)
        fg = 255 if self.dark else 0
        self.textcolor = (fg, fg, fg, 255)
        self.ink = (fg, fg, fg)
        self.paper = (0, 0, 0) if self.dark else (255, 255, 255)
        self.batch = pyglet.graphics.Batch()
        self.back_group = pyglet.graphics.Group(order=0)
        self.card_group = pyglet.graphics.Group(order=1)
        self.body_group = pyglet.graphics.Group(order=2)
        self.text_group = pyglet.graphics.Group(order=3)
        self.top_group = pyglet.graphics.Group(order=4)

        def label(words, size, y, bold=False):
            return pyglet.text.Label(
                words, font_size=size, color=self.textcolor,
                weight='bold' if bold else 'normal', batch=self.batch,
                x=width_center(), y=y, anchor_x='center',
                anchor_y='center', font_name=FONTLIST)

        self.title = label(_(self.TITLE), calc_fontsize(22),
                           from_top_edge(36), bold=True)
        self.status = label('', calc_fontsize(14), from_top_edge(70))
        self.facts = label('', calc_fontsize(12), from_top_edge(96))
        self.footnote = label(self.FOOTNOTE, calc_fontsize(12),
                              from_bottom_edge(26))
        _fit(self.footnote, calc_fontsize(12))
        # Read by the agent boundary, which pays the trial by this
        # label's colour; rebuilt with the chrome, so a verdict already
        # up is put back.
        self.verdict = VerdictLabel(batch=self.batch, y_from_bottom=60)
        if self.verdict_shown is not None:
            self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _area(self) -> Tuple[float, float, float, float]:
        """Left, bottom, width, height of the playing area."""
        window = state.window
        top = from_top_edge(116)
        bottom = above_the_band(from_bottom_edge(58))
        width = window.width * 0.94
        return ((window.width - width) / 2.0, bottom, width,
                max(40.0, top - bottom))

    def relayout(self) -> None:
        self._build_chrome()

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self.trial = 0
        self.results = []
        self.phase = 'ready'
        self.message = _('Press Space or click to start')
        self.verdict_shown = None
        self._clear_trial()

    def _clear_trial(self) -> None:
        """Drop whatever the last trial held."""

    def start_run(self) -> None:
        self._reset()
        self.rung = max(1, self.start_rung)
        self._next_trial()

    def _next_trial(self) -> None:
        if self.trial >= self.total_trials:
            self._finish()
            return
        self.verdict_shown = None
        self.verdict.clear()
        if not self._deal():
            self.phase = 'ready'
            self._redraw()
            return
        self.trial += 1
        self.started_at = self.clock()
        self.phase = self.PLAY
        self._redraw()

    def _deal(self) -> bool:
        raise NotImplementedError

    def _judge(self, passed: bool, message: str) -> None:
        if self.phase != self.PLAY:
            return
        self.results.append((self.rung, bool(passed)))
        if self.adaptive:
            self.rung = self.rung + 1 if passed else max(1, self.rung - 1)
        self.phase = 'judged'
        self.feedback_until = self.clock() + self.FEEDBACK
        self.message = message
        self.verdict_shown = (bool(passed), message)
        self.verdict.show(*self.verdict_shown)
        self._redraw()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = (_('%d of %d passed   highest rung passed %d')
                        % (tally['passed'], tally['trials'],
                           tally['best_rung']))
        self._clear_trial()
        self._redraw()

    def score(self) -> Dict[str, float]:
        return {
            'trials': len(self.results),
            'passed': sum(1 for _r, ok in self.results if ok),
            'best_rung': max((r for r, ok in self.results if ok),
                             default=0),
        }

    def update(self, dt: float) -> None:
        if self.phase == 'judged' and self.clock() >= self.feedback_until:
            self._next_trial()
        elif self.phase == self.PLAY:
            self._tick()

    def _tick(self) -> None:
        """Called on every frame of play."""

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for item in self.drawn:
            try:
                item.delete()
            except Exception:
                pass
        self.drawn = []
        self.hits = []

    def _text(self, words: str, x: float, y: float, size: float,
              anchor: str = 'center', bold: bool = False, colour=None,
              width: Optional[float] = None, anchor_y: str = 'center',
              group=None) -> pyglet.text.Label:
        kw = {}
        if width is not None:
            kw = dict(width=int(max(20, width)), multiline=True)
        label = pyglet.text.Label(
            words, font_size=max(6.0, size), x=x, y=y, anchor_x=anchor,
            anchor_y=anchor_y, color=colour or self.textcolor,
            weight='bold' if bold else 'normal', batch=self.batch,
            group=group or self.text_group, font_name=FONTLIST, **kw)
        self.drawn.append(label)
        return label

    def _box(self, x, y, w, h, colour, border=None, group=None,
             thickness: float = 2.0) -> None:
        if colour is not None:
            self.drawn.append(pyglet.shapes.Rectangle(
                x, y, w, h, color=colour, batch=self.batch,
                group=group or self.card_group))
        if border is not None:
            self.drawn.append(pyglet.shapes.Box(
                x, y, w, h, thickness=thickness, color=border,
                batch=self.batch, group=self.body_group))

    def _redraw(self) -> None:
        self._clear_drawn()
        if self.phase in (self.PLAY, 'judged'):
            self._draw(*self._area())
        self._update_labels()

    def _draw(self, left, bottom, width, height) -> None:
        raise NotImplementedError

    def _facts(self) -> str:
        return ''

    def _update_labels(self) -> None:
        self.status.text = self.message
        _fit(self.status, calc_fontsize(14))
        self.facts.text = (self._facts()
                           if self.phase in (self.PLAY, 'judged') else '')
        _fit(self.facts, calc_fontsize(12))

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        cls = type(self)
        if cls.instance is not self:
            return
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        self._clear_drawn()
        self._clear_trial()
        cls.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category=self.CATEGORY)

    # --- events ----------------------------------------------------------

    def steer(self, port: int) -> None:
        raise NotImplementedError

    def _key(self, symbol: int, modifiers: int) -> None:
        """The task's own keys, during play."""

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol == key.C and self.phase in ('ready', 'done'):
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif self.phase == self.PLAY:
            self._key(symbol, modifiers)
        return pyglet.event.EVENT_HANDLED

    def _click(self, x: float, y: float, button: int) -> None:
        if button != mouse.LEFT:
            return
        for left, bottom, w, h, action in list(self.hits):
            if left <= x <= left + w and bottom <= y <= bottom + h:
                action()
                break

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase in ('ready', 'done'):
            if button == mouse.LEFT:
                self.start_run()
        elif self.phase == self.PLAY:
            self._click(x, y, button)
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED


def _fit(label: pyglet.text.Label, size: float) -> None:
    """Shrink a one-line label until it fits the window."""
    label.font_size = size
    room = state.window.width * 0.96
    if label.content_width > room:
        label.font_size = max(6.0, size * room / label.content_width)


def ladder_par(rung: int, reference: float, floor: float,
               best: float) -> float:
    """Par from a reference on the identical deal, the house rule.

    Below rung twenty some of the reference's lead over *floor* (what
    play that does not think gets) is given away -- half of it at rung
    one, none at rung twenty. Past twenty a share of the gap from the
    reference up to *best* (what knowing everything gets) is asked for
    on top, rising to four fifths of it by rung thirty -- not all, since
    *best* usually knows things no player can see.
    """
    r = max(1, int(rung))
    if r <= 20:
        give = 0.5 * (20 - r) / 19.0
        return reference - give * max(0.0, reference - floor)
    take = min(0.8, 0.08 * (r - 20))
    return reference + take * max(0.0, best - reference)
