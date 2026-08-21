# -*- coding: utf-8 -*-
"""Recognition: have you met this one before?

The old/new recognition task. A run is a stream of items, some never
seen and some shown again after a gap, and the only question is which
is which. Unlike n-back there is nothing to rehearse — by the time an
item comes back it is far past anything working memory would hold, so
the answer has to come from having actually laid it down.

Answering "seen it" to everything scores 50%, so the run is scored on
both halves: catching the repeats (hits) and not claiming the new ones
(false alarms). The summary reports them apart, because a run can be
wrong in two quite different ways.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, NamedTuple, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import display, media, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        height_center, width_center)
from . import cursor, taskoptions
from .verdict import VerdictLabel
from ..i18n import _


class Trial(NamedTuple):
    """One presentation: an item, and whether it has been shown before."""

    path: str
    repeat: bool


#: Answer keys, and what they mean.
SEEN, NEW = 'seen', 'new'


class Recognition:
    """Old/new recognition over photographs or environmental sounds."""

    instance: Optional['Recognition'] = None

    def __init__(self) -> None:
        if Recognition.instance is not None:
            Recognition.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.trials: List[Trial] = []
        self.index = 0
        self.answers: List[Tuple[Trial, str]] = []
        self.phase = 'ready'
        self.shown_at = 0.0
        self.feedback_until = 0.0
        self.last_correct: Optional[bool] = None
        self.message = _('Press Space to begin')
        self.player: Optional[object] = None
        self.buttons: List[Tuple[float, float, float, float, str]] = []
        self._read_options()
        self.shapes: List[object] = []
        self.sprites: List[object] = []
        self.extra_labels: List[pyglet.text.Label] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 30.)
        cursor.acquire()
        display.register_overlay(self)
        Recognition.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.RECOGNITION)
        self.total_trials = int(opts['RECOGNITION_TRIALS'])
        self.medium = str(opts['RECOGNITION_MEDIUM'])
        self.repeat_percent = int(opts['RECOGNITION_REPEAT_PERCENT'])
        self.min_lag = int(opts['RECOGNITION_MIN_LAG'])
        self.study_ms = int(opts['RECOGNITION_STUDY_MS'])
        self.feedback = bool(opts['RECOGNITION_FEEDBACK'])
        self.pool = media.pool_for(self.medium, self.rng)

    def open_options(self) -> None:
        taskoptions.open_task_options('recognition',
                                      on_apply=self.apply_options)

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
        self.batch = pyglet.graphics.Batch()
        self.shapes = []
        self.sprites = []
        self.extra_labels = []
        self.title = pyglet.text.Label(
            _('Seen it before?'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     ← seen / new →'
              '     R: replay     C: options'),
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
        """Rebuild at the window's current size, mid-run if need be."""
        self._build_chrome()

    def _stage_rect(self) -> Tuple[float, float, float]:
        """Centre and side of the square the item is presented in."""
        window = state.window
        side = min(window.width * 0.5, window.height * 0.5)
        return width_center(), height_center() + window.height * 0.04, side

    def _button_rects(self) -> List[Tuple[float, float, float, float, str]]:
        window = state.window
        width = min(window.width * 0.24, window.width / 3.2)
        height = max(40.0, window.height * 0.075)
        gap = window.width * 0.04
        bottom = from_bottom_edge(90)
        left = (window.width - (width * 2 + gap)) / 2
        return [(left, bottom, width, height, SEEN),
                (left + width + gap, bottom, width, height, NEW)]

    # --- building a run --------------------------------------------------

    def needed_items(self) -> int:
        """Distinct items a full run consumes, worst case.

        The worst case is a run with no repeats at all: whether a
        trial repeats is a coin flip, and no trial can repeat until
        ``min_lag`` trials have passed, so budgeting for the average
        share of repeats runs the fresh list dry on long runs and
        quietly truncates them. The pool hands back only what it has,
        so asking for everything costs nothing when there is less.
        """
        return max(2, self.total_trials)

    def build_run(self) -> List[Trial]:
        """Plan the whole stream up front.

        A trial repeats an item only once it is at least ``min_lag``
        trials old and has not been repeated already, so every "seen
        it" really is a second showing and never a third.
        """
        self.pool.reload()
        fresh = self.pool.take_many(self.needed_items())
        if len(fresh) < 2:
            return []
        trials: List[Trial] = []
        shown: List[Tuple[int, str]] = []      # (trial number, path)
        repeated: set = set()
        next_fresh = 0
        for position in range(self.total_trials):
            eligible = [path for when, path in shown
                        if position - when >= self.min_lag
                        and path not in repeated]
            wants_repeat = self.rng.randrange(100) < self.repeat_percent
            if wants_repeat and eligible:
                path = self.rng.choice(eligible)
                repeated.add(path)
                trials.append(Trial(path, True))
            elif next_fresh < len(fresh):
                path = fresh[next_fresh]
                next_fresh += 1
                shown.append((position, path))
                trials.append(Trial(path, False))
            elif eligible:
                path = self.rng.choice(eligible)
                repeated.add(path)
                trials.append(Trial(path, True))
            else:
                break
        return trials

    def start_run(self) -> bool:
        """Plan and present a run. False when the library is too small."""
        trials = self.build_run()
        if not trials:
            self.phase = 'ready'
            self.message = _('No %s library yet — see the Readme') % self.medium
            self._redraw()
            return False
        self.trials = trials
        self.index = 0
        self.answers = []
        self.last_correct = None
        self._present()
        return True

    # --- presenting ------------------------------------------------------

    def current(self) -> Optional[Trial]:
        if 0 <= self.index < len(self.trials):
            return self.trials[self.index]
        return None

    def _stop_sound(self) -> None:
        if self.player is not None:
            try:
                self.player.pause()
            except Exception:
                pass
            self.player = None

    def _present(self) -> None:
        trial = self.current()
        if trial is None:
            self._finish()
            return
        self.phase = 'showing'
        self.verdict_shown = None
        self.verdict.clear()
        self.shown_at = self.clock()
        self.message = _('Seen it, or new?')
        if self.medium == 'sound':
            self.replay()
        self._redraw()

    def replay(self) -> None:
        """Play the current clip again. Sound runs only."""
        trial = self.current()
        if trial is None or self.medium != 'sound':
            return
        source = self.pool.item(trial.path)
        if source is None:
            return
        self._stop_sound()
        try:
            self.player = source.play()
        except Exception:
            self.player = None

    def answer(self, choice: str) -> None:
        """Record *choice* for the current trial and move on."""
        trial = self.current()
        if trial is None or self.phase not in ('showing', 'hidden'):
            return
        self.answers.append((trial, choice))
        self.last_correct = (choice == SEEN) == trial.repeat
        self._stop_sound()
        self.index += 1
        if self.feedback:
            self.phase = 'feedback'
            self.feedback_until = self.clock() + 0.35
            self.message = _('Yes') if self.last_correct else _('No')
            self.verdict_shown = (self.last_correct, self.message)
            self.verdict.show(*self.verdict_shown)
            self._redraw()
        else:
            self._present()

    def _finish(self) -> None:
        self.phase = 'done'
        self._stop_sound()
        tally = self.score()
        self.message = _('%d%% — caught %d/%d repeats, %d false alarms') % (
            tally['accuracy'], tally['hits'], tally['repeats'],
            tally['false_alarms'])
        self._redraw()

    def score(self) -> Dict[str, int]:
        """Hits, misses, false alarms and overall accuracy for the run."""
        hits = misses = false_alarms = correct_rejections = 0
        for trial, choice in self.answers:
            if trial.repeat:
                if choice == SEEN:
                    hits += 1
                else:
                    misses += 1
            elif choice == SEEN:
                false_alarms += 1
            else:
                correct_rejections += 1
        answered = len(self.answers)
        correct = hits + correct_rejections
        return {
            'hits': hits, 'misses': misses, 'false_alarms': false_alarms,
            'correct_rejections': correct_rejections,
            'repeats': hits + misses, 'answered': answered,
            'accuracy': int(round(100. * correct / answered)) if answered else 0,
        }

    def _reset(self) -> None:
        self._stop_sound()
        self.trials = []
        self.answers = []
        self.index = 0
        self.phase = 'ready'
        self.message = _('Press Space to begin')
        self.verdict_shown = None

    def update(self, dt: float) -> None:
        now = self.clock()
        if self.phase == 'feedback' and now >= self.feedback_until:
            self._present()
        elif (self.phase == 'showing' and self.study_ms > 0
                and self.medium != 'sound'
                and now - self.shown_at >= self.study_ms / 1000.):
            # The item goes away but the question stands.
            self.phase = 'hidden'
            self._redraw()

    # --- drawing ---------------------------------------------------------

    def _clear_drawn(self) -> None:
        for item in self.shapes + self.sprites:
            try:
                item.delete()
            except Exception:
                pass
        self.shapes = []
        self.sprites = []
        for label in self.extra_labels:
            label.delete()
        self.extra_labels = []

    def _draw_stage(self) -> None:
        """The item itself, or a placeholder for a sound."""
        trial = self.current()
        if trial is None or self.phase not in ('showing', 'hidden'):
            return
        centre_x, centre_y, side = self._stage_rect()
        if self.medium == 'sound':
            plate = pyglet.shapes.Rectangle(
                centre_x - side / 2, centre_y - side / 2, side, side,
                color=((40, 46, 60, 255) if state.cfg.BLACK_BACKGROUND
                       else (226, 231, 240, 255)), batch=self.batch)
            self.shapes.append(plate)
            glyph = pyglet.text.Label(
                '♪', font_size=max(12, calc_fontsize(side * 0.30)),
                weight='bold', color=self.textcolor, batch=self.batch,
                x=centre_x, y=centre_y, anchor_x='center', anchor_y='center',
                font_name=FONTLIST)
            self.extra_labels.append(glyph)
            return
        if self.phase == 'hidden':
            return
        image = self.pool.item(trial.path)
        if image is None:
            return
        sprite = pyglet.sprite.Sprite(
            image, x=centre_x - side / 2, y=centre_y - side / 2,
            batch=self.batch)
        sprite.scale = side / max(1, image.width)
        self.sprites.append(sprite)

    def _draw_buttons(self) -> None:
        self.buttons = []
        if self.phase not in ('showing', 'hidden'):
            return
        self.buttons = self._button_rects()
        for left, bottom, width, height, choice in self.buttons:
            fill = ((58, 74, 110, 255) if state.cfg.BLACK_BACKGROUND
                    else (222, 228, 240, 255))
            rect = pyglet.shapes.Rectangle(left, bottom, width, height,
                                           color=fill, batch=self.batch)
            self.shapes.append(rect)
            label = pyglet.text.Label(
                _('Seen it') if choice == SEEN else _('New'),
                font_size=calc_fontsize(15), weight='bold',
                color=self.textcolor, batch=self.batch,
                x=left + width / 2, y=bottom + height / 2,
                anchor_x='center', anchor_y='center', font_name=FONTLIST)
            self.extra_labels.append(label)

    def _redraw(self) -> None:
        self._clear_drawn()
        self._draw_stage()
        self._draw_buttons()
        parts = [self.message]
        if self.trials and self.phase != 'done':
            parts.append(_('%d of %d')
                         % (min(self.index + 1, len(self.trials)),
                            len(self.trials)))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Recognition.instance is not self:
            return
        self._stop_sound()
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        Recognition.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='long_term_memory')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE and self.phase in ('ready', 'done'):
            self.start_run()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        elif symbol == key.R:
            self.replay()
        elif symbol in (key.LEFT, key.S, key.Y):
            self.answer(SEEN)
        elif symbol in (key.RIGHT, key.N):
            self.answer(NEW)
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        for left, bottom, width, height, choice in self.buttons:
            if left <= x <= left + width and bottom <= y <= bottom + height:
                self.answer(choice)
                break
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
