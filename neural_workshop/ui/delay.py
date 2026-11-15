# -*- coding: utf-8 -*-
"""Delay on screen: two offers, a coin count, the run's time.

Take the small reward now (A or Left) or wait for the large one (D or
Right); while waiting, the left button gives up. The time waited so far
counts up -- how long is left is not shown unless the rung shows waits
-- and a bar along the bottom is the run's time.

For the agent boundary: port 0 takes the small reward or gives up;
port 1 waits.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key

from .. import delay as model
from ..geometry import calc_fontsize
from ..i18n import _
from .rungtask import RungTask
from .spacetask import BUTTON_DARK, BUTTON_LIGHT

COIN = (232, 186, 60)
BAR = (90, 140, 220)


class Delay(RungTask):
    """A little now, or more later."""

    instance: Optional['Delay'] = None

    TITLE = 'Delay'
    TASK_ID = 'delay'
    PREFIX = 'DELAY'
    CATEGORY = 'self_control'
    FEEDBACK = 3.0
    FOOTNOTE = _('A or Left: take it now / give up   D or Right: wait   '
                 'Esc: menu')

    def __init__(self) -> None:
        self.run: Optional[model.Run] = None
        self.k = 0
        self.coins = 0
        self.mode = 'offer'
        self.since = 0.0
        self.until = 0.0
        self.began = 0.0
        self.par = 0.0
        super().__init__()

    def _clear_trial(self) -> None:
        self.run = None

    def _deal(self) -> bool:
        self.run = model.deal(self.rung, rng=self.rng)
        self.par = model.par(self.run)
        self.k = 0
        self.coins = 0
        self.mode = 'offer'
        self.began = self.clock()
        self.message = _('Collect as many coins as you can')
        return True

    @property
    def offer(self) -> model.Offer:
        return self.run.offers[self.k]

    def _left(self) -> float:
        return self.run.level.seconds - (self.clock() - self.began)

    # --- choosing --------------------------------------------------------

    def take(self) -> None:
        if self.phase != self.PLAY:
            return
        now = self.clock()
        if self.mode == 'offer':
            self.coins += self.offer.small
            self._pause(now, model.COLLECT)
        elif self.mode == 'waiting':
            self._pause(now, model.GIVE_UP)

    def wait(self) -> None:
        if self.phase == self.PLAY and self.mode == 'offer':
            self.mode = 'waiting'
            self.since = self.clock()
            self._redraw()

    def _pause(self, now: float, seconds: float) -> None:
        self.mode = 'pause'
        self.until = now + seconds
        self.k += 1
        self._redraw()

    def steer(self, port: int) -> None:
        if port == 0:
            self.take()
        elif port == 1:
            self.wait()

    def _key(self, symbol: int, modifiers: int) -> None:
        if symbol in (key.A, key.LEFT):
            self.take()
        elif symbol in (key.D, key.RIGHT):
            self.wait()

    def _tick(self) -> None:
        now = self.clock()
        if self._left() <= 0:
            passed = self.coins >= self.par - 1e-9
            self.mode = 'over'
            self._judge(passed, _('%d coins (par %d)')
                        % (self.coins, int(round(self.par))))
            return
        if self.mode == 'waiting' and now - self.since >= self.offer.wait:
            self.coins += self.offer.large
            self._pause(now, model.COLLECT)
        elif self.mode == 'pause' and now >= self.until:
            self.mode = 'offer'
            self._redraw()
        elif self.mode == 'waiting':
            self._redraw()
        elif int(self._left() * 4) != int((self._left() + 0.02) * 4):
            self._redraw()

    # --- drawing ---------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        cx = left + width / 2
        bw, bh = width * 0.3, height * 0.28
        y = bottom + height * 0.38
        back = BUTTON_DARK if self.dark else BUTTON_LIGHT
        size = calc_fontsize(18)
        self._text(_('%d coins') % self.coins, cx, bottom + height * 0.88,
                   calc_fontsize(24), bold=True)
        if self.mode in ('offer', 'waiting') and self.k < len(run.offers):
            offer = self.offer
            lx, rx = cx - bw - width * 0.03, cx + width * 0.03
            waiting = self.mode == 'waiting'
            self._box(lx, y, bw, bh, back, self.ink)
            self._text(_('Give up') if waiting else
                       _('Take %d now') % offer.small, lx + bw / 2,
                       y + bh / 2, size, bold=True)
            self.hits.append((lx, y, bw, bh, self.take))
            self._box(rx, y, bw, bh, COIN if waiting else back, self.ink)
            if run.level.shown:
                words = _('Wait %.1f s for %d') % (offer.wait, offer.large)
            else:
                words = _('Wait for %d') % offer.large
            self._text(words, rx + bw / 2, y + bh * 0.62, size, bold=True)
            if waiting:
                self._text(_('waited %.1f s') % (self.clock() - self.since),
                           rx + bw / 2, y + bh * 0.3, calc_fontsize(14))
            else:
                self.hits.append((rx, y, bw, bh, self.wait))
        else:
            self._text('...', cx, y + bh / 2, size)
        # The run's time.
        full = width * 0.8
        left_frac = max(0.0, self._left() / run.level.seconds)
        self._box(cx - full / 2, bottom + height * 0.12, full, height * 0.04,
                  (220, 222, 228))
        self._box(cx - full / 2, bottom + height * 0.12, full * left_frac,
                  height * 0.04, BAR)
        self._text(_('%d s left') % max(0, int(self._left() + 0.99)), cx,
                   bottom + height * 0.07, calc_fontsize(12))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  run %d/%d   par %d') % (
            self.rung, self.trial, self.total_trials, int(round(self.par)))
