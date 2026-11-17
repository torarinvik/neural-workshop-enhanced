# -*- coding: utf-8 -*-
"""Heavier on screen: the crates side on, each in its own lane.

Hold the mouse on a crate -- or hold 1-4 -- to push it toward the wall;
let go and watch it slide. Answer with the button at the end of a lane,
or with Z / X / C / V.

For the agent boundary: ports 0-3 push crate 1-4; ports 4-7 answer
crate 1-4.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from pyglet.window import key, mouse

from .. import heavier as model
from ..i18n import _
from .livetask import LiveTask

PUSH_KEYS = (key._1, key._2, key._3, key._4)


class Heavier(LiveTask):
    """Tell the crates apart by pushing them."""

    instance: Optional['Heavier'] = None

    TITLE = 'Heavier'
    TASK_ID = 'heavier'
    PREFIX = 'HEAVY'
    CATEGORY = 'reasoning'
    MODEL = model
    BACK = (36, 38, 46)
    EVENT_KEYS = {key.Z: model.PICK[0], key.X: model.PICK[1],
                  key.C: model.PICK[2], key.V: model.PICK[3]}
    FOOTNOTE = _('Hold a crate or 1-4: push   Click its button or Z / X / '
                 'C / V: answer   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        self._lanes = []
        self._ask()
        return ok

    def _ask(self) -> None:
        run = self.run
        if run is None or run.result is not None:
            return
        if run.now.ask == model.HEAVY:
            self.message = _('Board %d of %d: which crate is heaviest?') % (
                run.board + 1, len(run.rnd.boards))
        else:
            self.message = _('Board %d of %d: under which crate is the '
                             'floor slipperiest?') % (
                run.board + 1, len(run.rnd.boards))

    def _held(self):
        run = self.run
        if run is None:
            return None
        n = run.level.crates
        for k in range(n):
            if self.keys[PUSH_KEYS[k]]:
                return model.PUSH[k]
        if self.buttons & mouse.LEFT and self.pointer is not None:
            px, py = self.pointer
            for k, (x0, y0, x1, y1) in enumerate(getattr(self, '_lanes', [])):
                if x0 <= px <= x1 and y0 <= py <= y1:
                    return model.PUSH[k]
        return None

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        if getattr(self, '_shown', None) != (id(run), run.board):
            self._shown = (id(run), run.board)
            self._ask()
        self.frame(left, bottom, width, height)
        b = run.now
        n = run.level.crates
        lane_h = (height - 40) / n
        x0, x1 = left + 70, left + width - 150
        per = (x1 - x0) / model.LANE
        self._lanes = []
        for k in range(n):
            g = self.layer()
            y = bottom + height - 20 - (k + 1) * lane_h
            floor = y + lane_h * 0.18
            self.rect(x0 - 10, floor - 8, x1 - x0 + 10, 8, (120, 110, 100), g)
            self.rect(x1, floor - 8, 12, lane_h * 0.75, (90, 80, 74), g)
            self.say(str(k + 1), left + 34, floor + lane_h * 0.3, 18,
                     (220, 224, 240, 255), bold=True)
            # square, fitted to the lane; its front edge where it really is
            side = b.size[k] * min(per * 0.95, lane_h * 0.62 / 0.9)
            cx = x0 + (run.x[k] + b.size[k]) * per - side
            moving = run.v[k] > 0.02
            self.rect(cx, floor, side, side, (120, 84, 50), g)
            self.rect(cx + 4, floor + 4, side - 8, side - 8,
                      (196, 150, 96) if not moving else (214, 168, 110), g)
            self.line((cx + 4, floor + 4), (cx + side - 4, floor + side - 4),
                      3, (150, 108, 64), g)
            self.line((cx + 4, floor + side - 4), (cx + side - 4, floor + 4),
                      3, (150, 108, 64), g)
            # the push: an arrow behind the crate while it is pushed
            if run.result is None and self.control_now() == model.PUSH[k]:
                self.poly([(cx - 26, floor + side / 2 + 10),
                           (cx - 6, floor + side / 2),
                           (cx - 26, floor + side / 2 - 10)],
                          (250, 220, 90), g)
            self._lanes.append((x0 - 10, floor - 8, x1, floor + lane_h * 0.75))
            # the answer button
            bx, bw, bh = x1 + 26, 104, 34
            by = floor + lane_h * 0.25
            self.rect(bx, by, bw, bh, (88, 100, 140), g)
            self.say(_('this one'), bx + bw / 2, by + bh / 2, 12,
                     (240, 242, 250, 255), bold=True)
            self.hits.append((bx, by, bw, bh,
                              lambda k=k: self.steer(model.PICK[k])))

    def _click(self, x, y, button) -> None:
        # a press on a lane starts the push at once; the release ends it
        self.pointer = (float(x), float(y))
        self.buttons = button
        super()._click(x, y, button)

    def control_now(self):
        return self._held()

    def _facts(self) -> str:
        if self.run is None:
            return ''
        return _('rung %d  %d/%d   board %d of %d   %.0f s left') % (
            self.rung, self.trial, self.total_trials, self.run.board + 1,
            len(self.run.rnd.boards),
            max(0.0, self.run.level.seconds - (self.run.t - self.run.started)))
