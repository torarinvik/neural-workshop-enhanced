# -*- coding: utf-8 -*-
"""Explore or Exploit on screen: a row of machines, coins above.

Each machine's card shows how often it has been pulled and its last six
payouts, newest first; a pull not yet shown is a question mark (from
rung 16 payouts come in fives). Click a machine or press its number.
The coin count only counts what has been shown.

For the agent boundary: ports 0-7 pull machines 1-8.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional

from pyglet.window import key

from .. import bandit as model
from ..geometry import calc_fontsize
from ..i18n import _
from . import polish
from .rungtask import RungTask

LAST = (232, 186, 60)


class ExploreOrExploit(RungTask):
    """Pull the machines that pay -- and find out which those are."""

    instance: Optional['ExploreOrExploit'] = None

    TITLE = 'Explore or Exploit'
    TASK_ID = 'explore_exploit'
    PREFIX = 'EXPLORE_EXPLOIT'
    CATEGORY = 'decisions'
    FEEDBACK = 3.0
    FOOTNOTE = _('click a machine or press its number   Esc: menu')

    def __init__(self) -> None:
        self.run: Optional[model.Run] = None
        self.chosen: List[int] = []
        self.par = 0.0
        super().__init__()

    def _clear_trial(self) -> None:
        self.run = None
        self.chosen = []

    def _deal(self) -> bool:
        self.run = model.deal(self.rung, rng=self.rng)
        self.par = model.par(self.run)
        self.chosen = []
        self.message = _('%d pulls: collect as many coins as you can') \
            % self.run.level.pulls
        return True

    def pull(self, k: int) -> None:
        run = self.run
        if self.phase != self.PLAY or not 0 <= k < run.level.arms:
            return
        self.chosen.append(k)
        if len(self.chosen) >= run.level.pulls:
            coins = self.coins(everything=True)
            self._judge(coins >= self.par - 1e-9,
                        _('%d coins (par %d)')
                        % (coins, int(round(self.par))))
        else:
            self._redraw()

    def coins(self, everything: bool = False) -> int:
        t = len(self.chosen)
        shown = t if everything else model.seen_after(self.run, t)
        return sum(self.run.pays[s][self.chosen[s]] for s in range(shown))

    def steer(self, port: int) -> None:
        self.pull(port)

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._8:
            self.pull(symbol - key._1)

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        pal = polish.palette(self.dark)
        n = run.level.arms
        t = len(self.chosen)
        shown = t if self.phase == 'judged' else model.seen_after(run, t)
        # The purse and the pulls left.
        r = max(10.0, height * 0.03)
        cx = left + width / 2
        words = self._text(_('%d coins     %d pulls left') % (
            self.coins(everything=self.phase == 'judged'),
            run.level.pulls - t), cx + r * 1.2, bottom + height * 0.93,
            calc_fontsize(20), bold=True)
        polish.coin(self.drawn, self.batch,
                    cx + r * 1.2 - words.content_width / 2 - r * 1.6,
                    bottom + height * 0.93, r, group=self.body_group)
        gap = width * 0.018
        cw = min(width * 0.2, (width - gap * (n - 1)) / n)
        ch = height * 0.8
        x0 = left + (width - (cw * n + gap * (n - 1))) / 2
        y = bottom + height * 0.03
        size = min(calc_fontsize(14), cw * 0.12)
        for k in range(n):
            x = x0 + k * (cw + gap)
            last = bool(self.chosen) and self.chosen[-1] == k
            hue = polish.HUES[k % len(polish.HUES)]
            parts = polish.machine(self.drawn, self.batch, x, y, cw, ch, pal,
                                   hue, lit=last, lit_colour=LAST,
                                   header_share=0.14, screen_share=0.62)
            hx, hy, hw, hh = parts.header
            self._text(str(k + 1), hx + hw / 2, hy + hh / 2, size * 1.8,
                       bold=True, colour=(255, 255, 255, 255))
            sx, sy, sw, sh = parts.screen
            pulls = [s for s in range(t) if self.chosen[s] == k]
            rows = 6
            row_h = sh / rows
            for row, s in enumerate(reversed(pulls[-rows:])):
                ry = sy + sh - (row + 1) * row_h
                known = s < shown
                chip = pal.card if known else polish.mix(pal.card, pal.edge,
                                                         0.5)
                polish.rounded(self.drawn, self.batch, sx + sw * 0.12,
                               ry + row_h * 0.12, sw * 0.76, row_h * 0.76,
                               chip, radius=row_h * 0.2,
                               group=self.card_group)
                self._text(str(run.pays[s][k]) if known else '?',
                           sx + sw / 2, ry + row_h / 2, size * 1.3,
                           bold=row == 0,
                           colour=None if known else pal.muted + (255,))
            self._text(_('pulled %d') % len(pulls), x + cw / 2,
                       y + (sy - y) / 2, size,
                       colour=pal.muted + (255,))
            self.hits.append((x, y, cw, ch, lambda k=k: self.pull(k)))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  run %d/%d   par %d') % (
            self.rung, self.trial, self.total_trials, int(round(self.par)))
