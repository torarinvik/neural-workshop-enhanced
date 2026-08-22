# -*- coding: utf-8 -*-
"""Reflex: hit the targets before they shrink away to nothing.

Images appear at random places and shrink from full size to nothing
over a fixed life. Clicking one scores it; letting it vanish does not.
The attention task is the divided kind — several targets can be on
screen at once, each with its own clock, so the work is deciding what
to go for as much as pointing at it.

Unlike the other games this one animates, so it does not tear its
drawing down and rebuild it every frame. A target owns its sprite from
spawn to death and only its scale and position change, which is what
keeps the motion smooth at sixty frames a second.

Positions are held as fractions of the window rather than pixels, so a
resize moves everything to the same relative place instead of leaving
targets off the edge. They are also held clear of the strip the agent
boundary reads its verdict out of — see :func:`_spawn`, which is where
a photograph low on the screen was being counted as a scored trial.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Tuple

import pyglet
from pyglet.window import key

from .. import display, media, state
from ..constants import FONTLIST
from ..geometry import (calc_fontsize, from_bottom_edge, from_top_edge,
                        scale_to_height, width_center)
from . import cursor, taskoptions
from .verdict import VerdictLabel, above_the_band
from ..i18n import _

#: Smallest a target is drawn before it counts as gone. Below this it
#: is a few pixels and clicking it would be luck rather than reflex.
MIN_SCALE = 0.06

#: How the adaptive life changes per hit and per miss. Gentle enough
#: that a run of forty does not bottom out, and quicker to ease off
#: than to tighten, which is what keeps it near the edge of what you
#: can manage rather than past it.
TIGHTEN_ON_HIT = 0.97
EASE_ON_MISS = 1.08

#: Bounds on the adaptive life. The floor is near human reaction time,
#: so reaching it means the task has nothing harder to offer.
MIN_LIFETIME = 0.30
MAX_LIFETIME_FACTOR = 2.5


class Target:
    """One shrinking image: where it is, and how long it has left."""

    __slots__ = ('path', 'sprite', 'x_frac', 'y_frac', 'born', 'lifetime',
                 'side', 'dead')

    def __init__(self, path: str, x_frac: float, y_frac: float,
                 lifetime: float, born: float) -> None:
        self.path = path
        self.sprite: Optional[pyglet.sprite.Sprite] = None
        self.x_frac = x_frac
        self.y_frac = y_frac
        self.lifetime = lifetime
        self.born = born
        self.side = 0.0
        self.dead = False

    def remaining(self, now: float) -> float:
        """Fraction of life left, 1 at spawn and 0 when it vanishes."""
        if self.lifetime <= 0:
            return 0.0
        return max(0.0, 1.0 - (now - self.born) / self.lifetime)

    def centre(self) -> Tuple[float, float]:
        return (self.x_frac * state.window.width,
                self.y_frac * state.window.height)

    def contains(self, x: float, y: float) -> bool:
        """True if (x, y) is on the target at its current size."""
        centre_x, centre_y = self.centre()
        half = self.side / 2
        return (centre_x - half <= x <= centre_x + half
                and centre_y - half <= y <= centre_y + half)


class Reflex:
    """Click the shrinking targets. Esc returns to the hub."""

    instance: Optional['Reflex'] = None

    def __init__(self) -> None:
        if Reflex.instance is not None:
            Reflex.instance.close()
        self.rng = random.Random()
        #: Swapped out by an agent environment for a virtual clock.
        self.clock = time.time
        self.targets: List[Target] = []
        self.spawned = 0
        self.hits = 0
        self.misses = 0
        self.reaction_times: List[float] = []
        self.next_spawn = 0.0
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self._read_options()
        self.shapes: List[object] = []
        self.extra_labels: List[pyglet.text.Label] = []
        self._build_chrome()
        state.window.push_handlers(self.on_key_press, self.on_mouse_press,
                                   self.on_draw)
        pyglet.clock.schedule_interval(self.update, 1 / 60.)
        cursor.acquire()
        display.register_overlay(self)
        Reflex.instance = self

    # --- options ---------------------------------------------------------

    def _read_options(self) -> None:
        opts = taskoptions.settings(taskoptions.REFLEX)
        self.total_targets = int(opts['REFLEX_TARGETS'])
        self.base_lifetime = int(opts['REFLEX_LIFETIME_MS']) / 1000.
        self.spawn_gap = int(opts['REFLEX_SPAWN_MS']) / 1000.
        self.max_active = int(opts['REFLEX_MAX_ACTIVE'])
        self.start_size = int(opts['REFLEX_SIZE'])
        self.adaptive = bool(opts['REFLEX_ADAPTIVE'])
        self.lifetime = self.base_lifetime
        self.pool = media.image_pool(self.rng)

    def open_options(self) -> None:
        taskoptions.open_task_options('reflex', on_apply=self.apply_options)

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
        self.extra_labels = []
        self.title = pyglet.text.Label(
            _('Reflex'), font_size=calc_fontsize(22), weight='bold',
            color=self.textcolor, batch=self.batch,
            x=width_center(), y=from_top_edge(36),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.status = pyglet.text.Label(
            '', font_size=calc_fontsize(14), color=self.textcolor,
            batch=self.batch, x=width_center(), y=from_top_edge(70),
            anchor_x='center', anchor_y='center', font_name=FONTLIST)
        self.footnote = pyglet.text.Label(
            _('Esc: task menu     Space: start     C: options'),
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
        # Sprites belong to the old batch; give every live target a new
        # one at its current place rather than leaving it invisible.
        for target in self.targets:
            target.sprite = None
        self._sync_sprites(self.clock())
        self._update_status()

    def relayout(self) -> None:
        """Rebuild at the window's current size, mid-run if need be."""
        self._build_chrome()

    def full_side(self) -> float:
        """A target's width at full size, in pixels."""
        return max(16.0, float(scale_to_height(self.start_size)))

    # --- the run ---------------------------------------------------------

    def _reset(self) -> None:
        for target in self.targets:
            self._drop_sprite(target)
        self.targets = []
        self.spawned = 0
        self.hits = 0
        self.misses = 0
        self.reaction_times = []
        self.lifetime = self.base_lifetime
        self.phase = 'ready'
        self.message = _('Press Space to start')
        self.verdict_shown = None

    def start_run(self) -> bool:
        """Begin a run. False when there are no images to show."""
        self._reset()
        self.pool.reload()
        if not self.pool.ready(1):
            self.message = _('No image library yet — see the Readme')
            self._update_status()
            return False
        self.phase = 'running'
        self.message = _('Click them before they go')
        self.next_spawn = self.clock()
        self._update_status()
        return True

    def _spawn(self, now: float) -> None:
        """Put one target on screen at a random place."""
        path = self.pool.take()
        if path is None:                      # library exhausted mid-run
            self.pool.reload()
            path = self.pool.take()
            if path is None:
                return
        # Keep the whole target on screen, clear of the labels, and —
        # the one that matters — clear of the band the agent boundary
        # reads a verdict out of.
        #
        # This used to be ``margin / height + 0.10``, which is a tenth
        # of the way up the screen and therefore inside the bottom
        # quarter. The targets are photographs, so whether a run painted
        # something the reader counted as a scored trial depended on
        # which pictures it happened to draw: check_band.py caught it
        # about one run in three and came up clean the rest of the time,
        # which is the worst way for a defect like this to behave.
        #
        # The floor is the target's *bottom edge at full size*, because
        # a target only ever shrinks towards its centre — clear at spawn
        # is clear for the rest of its life.
        margin = self.full_side() / 2
        window = state.window
        low_x = margin / window.width
        floor = above_the_band(window.height * 0.10) + margin
        low_y = floor / window.height
        high_y = 1.0 - margin / window.height - 0.14
        target = Target(
            path=path,
            x_frac=self.rng.uniform(low_x, 1.0 - low_x),
            y_frac=self.rng.uniform(low_y, max(low_y + 0.01, high_y)),
            lifetime=self.lifetime, born=now)
        self.targets.append(target)
        self.spawned += 1
        # A fresh target is a fresh chance, so the last one's verdict
        # comes down here. There is no gap between rounds in this task
        # to take it down in.
        self.verdict_shown = None
        self.verdict.clear()

    def _drop_sprite(self, target: Target) -> None:
        if target.sprite is not None:
            try:
                target.sprite.delete()
            except Exception:
                pass
            target.sprite = None

    def _sync_sprites(self, now: float) -> None:
        """Size and place every live target's sprite for this frame."""
        full = self.full_side()
        for target in self.targets:
            remaining = target.remaining(now)
            target.side = full * remaining
            if target.sprite is None:
                image = self.pool.item(target.path)
                if image is None:
                    target.dead = True
                    continue
                target.sprite = pyglet.sprite.Sprite(image, batch=self.batch)
            centre_x, centre_y = target.centre()
            scale = target.side / max(1, target.sprite.image.width)
            target.sprite.scale = max(0.001, scale)
            target.sprite.position = (centre_x - target.side / 2,
                                      centre_y - target.side / 2, 0)

    def _adapt(self, hit: bool) -> None:
        if not self.adaptive:
            return
        if hit:
            self.lifetime = max(MIN_LIFETIME, self.lifetime * TIGHTEN_ON_HIT)
        else:
            self.lifetime = min(self.base_lifetime * MAX_LIFETIME_FACTOR,
                                self.lifetime * EASE_ON_MISS)

    def hit(self, target: Target) -> None:
        """Score *target* as clicked. The move a click makes."""
        if target.dead:
            return
        target.dead = True
        self.hits += 1
        self.reaction_times.append(self.clock() - target.born)
        self.verdict_shown = (True, _('%d ms')
                              % int(self.reaction_times[-1] * 1000))
        self.verdict.show(*self.verdict_shown)
        self._adapt(hit=True)

    def _expire(self, target: Target) -> None:
        target.dead = True
        self.misses += 1
        self.verdict_shown = (False, _('Gone'))
        self.verdict.show(*self.verdict_shown)
        self._adapt(hit=False)

    def target_at(self, x: float, y: float) -> Optional[Target]:
        """The smallest live target under the point, so overlaps are fair."""
        under = [t for t in self.targets if not t.dead and t.contains(x, y)]
        return min(under, key=lambda t: t.side) if under else None

    def update(self, dt: float) -> None:
        if self.phase != 'running':
            return
        now = self.clock()
        for target in self.targets:
            if not target.dead and target.remaining(now) <= MIN_SCALE:
                self._expire(target)
        for target in [t for t in self.targets if t.dead]:
            self._drop_sprite(target)
        self.targets = [t for t in self.targets if not t.dead]

        live = len(self.targets)
        if (self.spawned < self.total_targets and live < self.max_active
                and now >= self.next_spawn):
            self._spawn(now)
            self.next_spawn = now + self.spawn_gap
        elif self.spawned >= self.total_targets and not self.targets:
            self._finish()
            return
        self._sync_sprites(now)
        self._update_status()

    def _finish(self) -> None:
        self.phase = 'done'
        tally = self.score()
        self.message = _('%d%% — %d of %d, %d ms average') % (
            tally['accuracy'], tally['hits'], tally['presented'],
            tally['mean_ms'])
        self._update_status()

    def score(self) -> Dict[str, int]:
        """Hits, misses, accuracy and mean reaction time for the run."""
        presented = self.hits + self.misses
        mean = (sum(self.reaction_times) / len(self.reaction_times)
                if self.reaction_times else 0.0)
        return {
            'hits': self.hits, 'misses': self.misses, 'presented': presented,
            'accuracy': int(round(100. * self.hits / presented)) if presented
                        else 0,
            'mean_ms': int(round(mean * 1000)),
        }

    def _update_status(self) -> None:
        parts = [self.message]
        if self.phase == 'running':
            parts.append(_('%d/%d   hit %d   missed %d')
                         % (self.spawned, self.total_targets,
                            self.hits, self.misses))
        self.status.text = '     '.join(parts)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        if Reflex.instance is not self:
            return
        for target in self.targets:
            self._drop_sprite(target)
        self.targets = []
        pyglet.clock.unschedule(self.update)
        cursor.release()
        display.unregister_overlay(self)
        state.window.remove_handlers(self.on_key_press, self.on_mouse_press,
                                     self.on_draw)
        Reflex.instance = None

    def return_to_hub(self) -> None:
        self.close()
        from .taskhub import TaskHub
        TaskHub(category='attention')

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
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int,
                       modifiers: int) -> bool:
        if self.phase == 'running':
            target = self.target_at(x, y)
            if target is not None:
                self.hit(target)
                self._drop_sprite(target)
                self.targets = [t for t in self.targets if not t.dead]
                self._update_status()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self) -> bool:
        display.ensure_laid_out()
        state.window.clear()
        self.batch.draw()
        return pyglet.event.EVENT_HANDLED
