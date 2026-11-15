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
from .rungtask import RungTask
from .spacetask import BUTTON_DARK

CARD = (244, 240, 230)
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
        n = run.level.arms
        t = len(self.chosen)
        shown = t if self.phase == 'judged' else model.seen_after(run, t)
        self._text(_('%d coins     %d pulls left') % (
            self.coins(everything=self.phase == 'judged'),
            run.level.pulls - t), left + width / 2, bottom + height * 0.92,
            calc_fontsize(20), bold=True)
        gap = width * 0.012
        cw = min(width * 0.2, (width - gap * (n - 1)) / n)
        ch = height * 0.75
        x0 = left + (width - (cw * n + gap * (n - 1))) / 2
        y = bottom + height * 0.05
        size = min(calc_fontsize(14), cw * 0.12)
        for k in range(n):
            x = x0 + k * (cw + gap)
            last = bool(self.chosen) and self.chosen[-1] == k
            self._box(x, y, cw, ch, BUTTON_DARK if self.dark else CARD,
                      LAST if last else self.ink, thickness=4 if last else 2)
            self._text(str(k + 1), x + cw / 2, y + ch - size * 1.6,
                       size * 1.8, bold=True)
            pulls = [s for s in range(t) if self.chosen[s] == k]
            self._text(_('pulled %d') % len(pulls), x + cw / 2,
                       y + ch - size * 4, size)
            for row, s in enumerate(reversed(pulls[-6:])):
                words = str(run.pays[s][k]) if s < shown else '?'
                self._text(words, x + cw / 2,
                           y + ch - size * (6.4 + row * 2.1), size * 1.4,
                           bold=row == 0)
            self.hits.append((x, y, cw, ch, lambda k=k: self.pull(k)))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  run %d/%d   par %d') % (
            self.rung, self.trial, self.total_trials, int(round(self.par)))
