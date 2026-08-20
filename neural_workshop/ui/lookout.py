# -*- coding: utf-8 -*-
"""Lookout: press the moment the cued thing is on screen.

A flock of coloured shapes drifts and bounces, each changing its
colour or its form every few seconds. A HUD names the thing to watch
for — a colour, a form, or both at once — drawn as the actual glyph
rather than a word, so there is no translating to do. The cued thing
is never on screen when the cue is issued; the churn brings it, and
the task is to press Space while it is there.

The scoring is signal detection, because the world closes its own
windows: a press while a match is on screen is a hit, timed from the
moment the match appeared; a match that churns away unpressed is a
miss; a press with nothing matching is a false alarm. No arbitrary
response timer — the morphing flock decides how long each chance
lasts.

The cue types are graded on purpose. A colour alone "pops out" — the
visual system finds it in parallel, almost for free. A colour *and*
a form is a conjunction search, which takes serial attention: that
distinction (Treisman's) is the whole reason the option exists.

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
from .tracking import bounced
from ..i18n import _

#: Shapes a run may hold. The ceiling is the same as the ball flock's:
#: room on screen, not code.
FEWEST_SHAPES, MOST_SHAPES = 3, 30

#: Okabe-Ito, named for the feedback line. Six is enough variety that
#: the cued colour is genuinely absent now and then, and few enough
#: that every pair stays tellable apart, colour-blind included.
COLORS: Tuple[Tuple[str, Tuple[int, int, int]], ...] = (
    (_('orange'), (230, 159, 0)),
    (_('sky blue'), (86, 180, 233)),
    (_('green'), (0, 158, 115)),
    (_('yellow'), (240, 228, 66)),
    (_('blue'), (0, 114, 178)),
    (_('vermilion'), (213, 94, 0)),
)

FORMS: Tuple[str, ...] = (_('circle'), _('square'), _('triangle'),
                          _('star'))

#: For a form-only cue the glyph still needs some colour; grey reads
#: as "any colour" on both backgrounds.
NEUTRAL = (128, 128, 128)

#: How long the flock may go without offering the cued thing before
#: the next morph is forced to produce it. Vigilance needs droughts,
#: but an unbounded one is a stuck game.
DROUGHT_SECONDS = 6.0

REVEAL_SECONDS = 1.4


class Cue(NamedTuple):
    """What to watch for. ``None`` means "any"."""

    color: Optional[int]
    form: Optional[int]


def matches(color: int, form: int, cue: Cue) -> bool:
    """Does a shape of *color* and *form* satisfy *cue*?"""
    return ((cue.color is None or color == cue.color)
            and (cue.form is None or form == cue.form))


def cue_words(cue: Cue) -> str:
    """The cue said out loud, for the status line."""
    if cue.color is not None and cue.form is not None:
        return _('a %s %s') % (COLORS[cue.color][0], FORMS[cue.form])
    if cue.color is not None:
        return _('anything %s') % COLORS[cue.color][0]
    return _('any %s') % FORMS[cue.form or 0]


class Drifter:
    """One shape: where it goes, what it is, when it changes."""

    __slots__ = ('x', 'y', 'vx', 'vy', 'color', 'form', 'next_morph',
                 'drawn')

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 color: int, form: int, next_morph: float) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.form = form
        self.next_morph = next_morph
        self.drawn: Optional[object] = None


class Lookout:
    """Watch the churn for the cued thing. Esc returns to the hub."""

    instance: Optional['Lookout'] = None

    def __init__(self) -> None:
        if Lookout.instance is not None:
            Lookout.instance.close()
        self.rng = random.Random()
        self.shapes: List[Drifter] = []
        self.cue = Cue(None, None)
        self.cue_number = 0
        self.seen_at: Optional[float] = None
        self.cued_at = 0.0
        self.until = 0.0
        self.hits = 0
        self.misses = 0
        self.false_alarms = 0
        self.reaction_times: List[float] = []
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self._read_options()
        self.count = self.clamped(self.start_count)
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        cursor.acquire()
        display.register_overlay(self)
        Lookout.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.LOOKOUT)
        self.start_count = int(opts['LOOKOUT_SHAPES'])
        self.cue_kind = str(opts['LOOKOUT_CUE'])
        self.speed = int(opts['LOOKOUT_SPEED']) / 100.
        self.morph_gap = int(opts['LOOKOUT_MORPH_MS']) / 1000.
        self.total_cues = int(opts['LOOKOUT_CUES'])
        self.adaptive = bool(opts['LOOKOUT_ADAPTIVE'])

    @staticmethod
    def clamped(count: int) -> int:
        return max(FEWEST_SHAPES, min(MOST_SHAPES, count))

    def open_options(self) -> None:
        taskoptions.open_task_options('lookout', on_apply=self.apply_options)

    def apply_options(self) -> None:
        self._read_options()
        self._reset()
        self._build_chrome()

    # --- layout ----------------------------------------------------------

    def _build_chrome(self) -> None:
        bg = 0 if state.cfg.BLACK_BACKGROUND else 255
        fg = 255 - bg
        self.textcolor = (fg, fg, fg, 255)
        self.batch = pyglet.graphics.Batch()
        self.title = pyglet.text.Label(
            _('Lookout'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start, and press it when you '
              'see the cued thing     C: options'),
            font_size=calc_fontsize(12), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_bottom_edge(26),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.cue_glyph: List[object] = []
        for drifter in self.shapes:
            drifter.drawn = None
        self._sync_cue_glyph()
        self._sync_shapes()
        self._update_status()

    def relayout(self) -> None:
        self._build_chrome()

    def radius(self) -> float:
        return max(7.0, float(scale_to_height(17)))

    def _bounds(self) -> Tuple[float, float, float, float]:
        window = state.window
        edge_x = self.radius() / window.width
        edge_y = self.radius() / window.height
        return (edge_x + 0.01, 1.0 - edge_x - 0.01,
                edge_y + 0.11, 1.0 - edge_y - 0.17)

    # --- a run -----------------------------------------------------------

    def _reset(self) -> None:
        self._drop_shapes()
        self.cue_number = 0
        self.hits = 0
        self.misses = 0
        self.false_alarms = 0
        self.reaction_times = []
        self.seen_at = None
        self.count = self.clamped(self.start_count)
        self.phase = 'ready'
        self.message = _('Press Space to start')

    def start_run(self) -> None:
        self._reset()
        self._spawn_flock()
        self._next_cue()

    def _spawn_flock(self) -> None:
        """Fresh drifters with clear air, varied speeds and headings."""
        self._drop_shapes()
        low_x, high_x, low_y, high_y = self._bounds()
        apart = 2.4 * self.radius() / state.window.height
        now = time.time()
        spots: List[Tuple[float, float]] = []
        while len(spots) < self.count:
            for _attempt in range(self.count * 60):
                spot = (self.rng.uniform(low_x, high_x),
                        self.rng.uniform(low_y, high_y))
                if all((spot[0] - x) ** 2 + (spot[1] - y) ** 2
                       >= apart * apart for x, y in spots):
                    spots.append(spot)
                    if len(spots) == self.count:
                        break
            else:
                apart *= 0.8
        for x, y in spots:
            heading = self.rng.uniform(0.0, 2 * math.pi)
            pace = self.speed * self.rng.uniform(0.5, 1.5)
            self.shapes.append(Drifter(
                x, y, pace * math.cos(heading), pace * math.sin(heading),
                color=self.rng.randrange(len(COLORS)),
                form=self.rng.randrange(len(FORMS)),
                next_morph=now + self.rng.uniform(0.3, self.morph_gap)))

    def _next_cue(self) -> None:
        if self.cue_number >= self.total_cues:
            self._finish()
            return
        self.cue_number += 1
        self.cue = self._absent_cue()
        self.cued_at = time.time()
        self.seen_at = None
        self.phase = 'watching'
        self.message = _('Watch for %s') % cue_words(self.cue)
        self._sync_cue_glyph()
        self._update_status()

    def _cue_kind_now(self) -> str:
        if self.cue_kind == 'mixed':
            return self.rng.choice(('color', 'form', 'both'))
        return self.cue_kind

    def _absent_cue(self) -> Cue:
        """A cue nothing on screen satisfies, so its arrival is real.

        Every episode must begin below the signal: if the cued thing
        were already there, the reaction time would start negative
        and the first press would be a freebie. A big flock can cover
        every colour at once, so when no cue is absent the rarest one
        is taken and its few matching shapes are morphed away — the
        cue clears its own stage rather than starting satisfied.
        """
        kind = self._cue_kind_now()
        if kind == 'color':
            candidates = [Cue(color, None) for color in range(len(COLORS))]
        elif kind == 'form':
            candidates = [Cue(None, form) for form in range(len(FORMS))]
        else:
            candidates = [Cue(color, form)
                          for color in range(len(COLORS))
                          for form in range(len(FORMS))]
        self.rng.shuffle(candidates)
        cue = min(candidates, key=lambda option:
                  sum(1 for s in self.shapes
                      if matches(s.color, s.form, option)))
        for drifter in self.shapes:
            while matches(drifter.color, drifter.form, cue):
                if cue.color is not None:
                    drifter.color = self.rng.randrange(len(COLORS))
                if cue.form is not None:
                    drifter.form = self.rng.randrange(len(FORMS))
                drifter.drawn = None
        return cue

    # --- the churn -------------------------------------------------------

    def _move(self, dt: float) -> None:
        low_x, high_x, low_y, high_y = self._bounds()
        aspect = state.window.height / max(1, state.window.width)
        for drifter in self.shapes:
            drifter.x += drifter.vx * dt * aspect
            drifter.y += drifter.vy * dt
            drifter.x, drifter.vx = bounced(drifter.x, drifter.vx,
                                            low_x, high_x)
            drifter.y, drifter.vy = bounced(drifter.y, drifter.vy,
                                            low_y, high_y)

    def _morph(self, drifter: Drifter, now: float) -> None:
        """Change what *drifter* is — its colour, form, or both.

        In a drought the morph is forced to produce the cued thing,
        so no cue can dangle forever; otherwise the new identity just
        has to differ, or the churn would only pretend to churn.
        """
        drifter.next_morph = now + self.rng.uniform(0.6, 1.4) * self.morph_gap
        drought = (self.phase == 'watching' and self.seen_at is None
                   and now - self.cued_at > DROUGHT_SECONDS)
        if drought:
            if self.cue.color is not None:
                drifter.color = self.cue.color
            if self.cue.form is not None:
                drifter.form = self.cue.form
            drifter.drawn = None
            return
        was = (drifter.color, drifter.form)
        while (drifter.color, drifter.form) == was:
            if self.rng.random() < 0.7:
                drifter.color = self.rng.randrange(len(COLORS))
            else:
                drifter.form = self.rng.randrange(len(FORMS))
        drifter.drawn = None

    def match_on_screen(self) -> bool:
        return any(matches(s.color, s.form, self.cue) for s in self.shapes)

    def update(self, dt: float) -> None:
        now = time.time()
        if self.phase == 'watching':
            self._move(min(dt, 0.1))
            for drifter in self.shapes:
                if now >= drifter.next_morph:
                    self._morph(drifter, now)
            present = self.match_on_screen()
            if present and self.seen_at is None:
                self.seen_at = now
            elif not present and self.seen_at is not None:
                self._miss()
                return
            self._sync_shapes()
        elif self.phase == 'feedback':
            self._move(min(dt, 0.1))
            self._sync_shapes()
            if now >= self.until:
                self._next_cue()

    # --- answering -------------------------------------------------------

    def answer(self) -> None:
        """The press. Hit if the cued thing is here, false alarm if not."""
        if self.phase != 'watching':
            return
        if self.seen_at is not None:
            self.hits += 1
            self.reaction_times.append(time.time() - self.seen_at)
            self.message = _('Hit — %d ms') % int(
                self.reaction_times[-1] * 1000)
            self._adapt(right=True)
        else:
            self.false_alarms += 1
            self.message = _('Nothing %s is on screen') % cue_words(self.cue)
            self._adapt(right=False)
        self._show_feedback()

    def _miss(self) -> None:
        """The match churned away unpressed."""
        self.misses += 1
        self.message = _('It slipped away — %s was there') % \
            cue_words(self.cue)
        self._adapt(right=False)
        self._show_feedback()

    def _adapt(self, right: bool) -> None:
        if not self.adaptive:
            return
        grown = self.count + 1 if right else self.count - 1
        self.count = self.clamped(grown)

    def _show_feedback(self) -> None:
        self.phase = 'feedback'
        self.seen_at = None
        self.until = time.time() + REVEAL_SECONDS
        # The flock churns on through feedback, but grows or shrinks
        # to the adapted count only between cues, quietly at the edge.
        while len(self.shapes) > self.count:
            gone = self.shapes.pop()
            self._drop_one(gone)
        low_x, high_x, low_y, high_y = self._bounds()
        now = time.time()
        while len(self.shapes) < self.count:
            heading = self.rng.uniform(0.0, 2 * math.pi)
            pace = self.speed * self.rng.uniform(0.5, 1.5)
            self.shapes.append(Drifter(
                self.rng.uniform(low_x, high_x),
                self.rng.uniform(low_y, high_y),
                pace * math.cos(heading), pace * math.sin(heading),
                color=self.rng.randrange(len(COLORS)),
                form=self.rng.randrange(len(FORMS)),
                next_morph=now + self.rng.uniform(0.3, self.morph_gap)))
        self._update_status()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d hits, %d slipped away, %d false alarms'
                         ' — %d ms average') % (
            tally['hits'], tally['misses'], tally['false_alarms'],
            tally['mean_ms'])
        self._sync_cue_glyph()
        self._update_status()

    def score(self) -> Dict[str, int]:
        mean = (sum(self.reaction_times) / len(self.reaction_times)
                if self.reaction_times else 0.0)
        return {
            'hits': self.hits, 'misses': self.misses,
            'false_alarms': self.false_alarms,
            'mean_ms': int(round(mean * 1000)),
            'most_shapes': self.count,
        }

    # --- drawing ---------------------------------------------------------

    def _made(self, form: int, x: float, y: float, r: float,
              color: Tuple[int, int, int]) -> object:
        """A new drawable of *form* centred on (x, y)."""
        if FORMS[form] == _('circle'):
            return pyglet.shapes.Circle(x, y, r, color=color,
                                        batch=self.batch)
        if FORMS[form] == _('square'):
            side = r * 1.8
            square = pyglet.shapes.Rectangle(x, y, side, side, color=color,
                                             batch=self.batch)
            square.anchor_position = (side / 2, side / 2)
            return square
        if FORMS[form] == _('triangle'):
            return pyglet.shapes.Triangle(
                x - r, y - r * 0.8, x + r, y - r * 0.8, x, y + r * 1.1,
                color=color, batch=self.batch)
        return pyglet.shapes.Star(x, y, r * 1.25, r * 0.55, num_spikes=5,
                                  color=color, batch=self.batch)

    def _place(self, drawn: object, form: int, x: float, y: float,
               r: float) -> None:
        if FORMS[form] == _('triangle'):
            drawn.x, drawn.y = x - r, y - r * 0.8
            drawn.x2, drawn.y2 = x + r, y - r * 0.8
            drawn.x3, drawn.y3 = x, y + r * 1.1
        else:
            drawn.position = (x, y)

    def _sync_shapes(self) -> None:
        window = state.window
        r = self.radius()
        for drifter in self.shapes:
            x = drifter.x * window.width
            y = drifter.y * window.height
            if drifter.drawn is None:
                drifter.drawn = self._made(
                    drifter.form, x, y, r, COLORS[drifter.color][1])
            else:
                self._place(drifter.drawn, drifter.form, x, y, r)

    def _sync_cue_glyph(self) -> None:
        """The cue drawn as the thing itself, next to the status line.

        A colour-only cue is a swatch circle; a form-only cue is the
        form in grey. Reading a glyph beats reading a word — there is
        no translation step to pay for at the moment of search.
        """
        for drawn in self.cue_glyph:
            try:
                drawn.delete()
            except Exception:
                pass
        self.cue_glyph = []
        if self.phase not in ('watching', 'feedback'):
            return
        color = (COLORS[self.cue.color][1] if self.cue.color is not None
                 else NEUTRAL)
        form = self.cue.form if self.cue.form is not None else 0
        x = width_center() + self.status.content_width / 2 + 34
        self.cue_glyph.append(self._made(
            form, x, from_top_edge(70), self.radius(), color))

    def _drop_one(self, drifter: Drifter) -> None:
        if drifter.drawn is not None:
            try:
                drifter.drawn.delete()
            except Exception:
                pass
            drifter.drawn = None

    def _drop_shapes(self) -> None:
        for drifter in self.shapes:
            self._drop_one(drifter)
        self.shapes = []

    def _update_status(self) -> None:
        parts = [self.message]
        if self.phase in ('watching', 'feedback'):
            parts.append(_('cue %d/%d') % (self.cue_number, self.total_cues))
        self.status.text = '     '.join(parts)
        self._sync_cue_glyph()

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Lookout.instance is not self:
            return
        self._drop_shapes()
        for drawn in self.cue_glyph:
            try:
                drawn.delete()
            except Exception:
                pass
        self.cue_glyph = []
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_draw)
        Lookout.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='attention')

    # --- events ----------------------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> bool:
        if symbol == key.ESCAPE:
            self.return_to_hub()
        elif symbol == key.SPACE:
            if self.phase in ('ready', 'done'):
                self.start_run()
            else:
                self.answer()
        elif symbol == key.C:
            self.open_options()
        elif symbol == key.F11:
            display.toggle_fullscreen()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
