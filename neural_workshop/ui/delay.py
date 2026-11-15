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

import pyglet
from pyglet.window import key

from .. import delay as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import polish
from .rungtask import RungTask

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

    def _coins(self, x: float, y: float, count: int, r: float) -> None:
        """*count* coins in a little pile centred on x, y: rows of up to
        four, each row nudged up and over."""
        per_row = 4
        rows = (count + per_row - 1) // per_row
        for k in range(count):
            row, col = divmod(k, per_row)
            in_row = min(per_row, count - row * per_row)
            cx = x + (col - (in_row - 1) / 2.0) * r * 1.7 + row * r * 0.4
            cy = y - (rows - 1) * r * 0.55 + row * r * 1.1
            polish.coin(self.drawn, self.batch, cx, cy, r,
                        group=pyglet.graphics.Group(order=2 + row * 4))

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        pal = polish.palette(self.dark)
        cx = left + width / 2
        bw, bh = width * 0.3, height * 0.46
        y = bottom + height * 0.24
        size = calc_fontsize(18)
        # The purse.
        r = max(10.0, height * 0.035)
        words = self._text(_('%d coins') % self.coins, cx + r * 1.4,
                           bottom + height * 0.88, calc_fontsize(24),
                           bold=True)
        polish.coin(self.drawn, self.batch,
                    cx + r * 1.4 - words.content_width / 2 - r * 1.8,
                    bottom + height * 0.88, r, group=self.body_group)
        if self.mode in ('offer', 'waiting') and self.k < len(run.offers):
            offer = self.offer
            lx, rx = cx - bw - width * 0.03, cx + width * 0.03
            waiting = self.mode == 'waiting'
            coin_r = max(8.0, min(bw, bh) * 0.075)
            # Now.
            polish.card(self.drawn, self.batch, lx, y, bw, bh, pal.card,
                        radius=16, edge=pal.edge, shade=pal.shadow)
            self._text(_('Give up') if waiting else _('Take it now'),
                       lx + bw / 2, y + bh * 0.82, size, bold=True)
            self._coins(lx + bw / 2, y + bh * 0.48, offer.small, coin_r)
            self._text(_('%d now') % offer.small, lx + bw / 2,
                       y + bh * 0.14, calc_fontsize(14),
                       colour=pal.muted + (255,))
            self.hits.append((lx, y, bw, bh, self.take))
            # Later.
            face = polish.mix(pal.card, COIN, 0.22) if waiting else pal.card
            polish.card(self.drawn, self.batch, rx, y, bw, bh, face,
                        radius=16, edge=COIN if waiting else pal.edge,
                        shade=pal.shadow)
            if run.level.shown:
                words = _('Wait %.1f s') % offer.wait
            else:
                words = _('Wait for it')
            self._text(words, rx + bw / 2, y + bh * 0.82, size, bold=True)
            if waiting:
                waited = self.clock() - self.since
                ring = min(bw, bh) * 0.2
                mx, my = rx + bw / 2, y + bh * 0.45
                self.drawn.append(pyglet.shapes.Arc(
                    mx, my, ring, thickness=ring * 0.22,
                    color=polish.mix(face, pal.muted, 0.35),
                    batch=self.batch, group=self.body_group))
                share = (waited / offer.wait if run.level.shown
                         else (waited % 10.0) / 10.0)
                self.drawn.append(pyglet.shapes.Arc(
                    mx, my, ring, thickness=ring * 0.22,
                    angle=-360.0 * min(1.0, share), start_angle=90.0,
                    color=polish.darker(COIN, 0.1), batch=self.batch,
                    group=self.text_group))
                self._text(_('%.1f s') % waited, mx, my, calc_fontsize(14),
                           bold=True)
            else:
                self._coins(rx + bw / 2, y + bh * 0.48, offer.large, coin_r)
                self.hits.append((rx, y, bw, bh, self.wait))
            self._text(_('%d later') % offer.large, rx + bw / 2,
                       y + bh * 0.14, calc_fontsize(14),
                       colour=pal.muted + (255,))
        else:
            self._text(_('next offer ...'), cx, y + bh / 2, size,
                       colour=pal.muted + (255,))
        # The run's time.
        full = width * 0.8
        bar_h = max(8.0, height * 0.035)
        left_frac = max(0.0, self._left() / run.level.seconds)
        polish.rounded(self.drawn, self.batch, cx - full / 2,
                       bottom + height * 0.1, full, bar_h,
                       polish.mix(pal.stage, pal.edge, 0.5),
                       radius=bar_h / 2, group=self.card_group)
        if left_frac > 0:
            polish.rounded(self.drawn, self.batch, cx - full / 2,
                           bottom + height * 0.1, max(bar_h, full * left_frac),
                           bar_h, BAR, radius=bar_h / 2,
                           group=self.body_group)
        self._text(_('%d s left') % max(0, int(self._left() + 0.99)), cx,
                   bottom + height * 0.05, calc_fontsize(12),
                   colour=pal.muted + (255,))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  run %d/%d   par %d') % (
            self.rung, self.trial, self.total_trials, int(round(self.par)))
