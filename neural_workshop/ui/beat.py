# -*- coding: utf-8 -*-
"""Keep the Beat on screen: a wooden metronome on a stage, and a drum.

The metronome's arm swings, its lamp flashes and a wood block clicks on
every beat (the first of each cycle a brighter bell). When it is time to
carry the beat alone, a velvet curtain drops over it and it falls
silent. Each tap thumps the drum and leaves a mark on the strip below;
after the verdict, the strip shows where the beats fell and which taps
found them.

For the agent boundary: port 0 taps. Each frame carries the clicks
heard since the last one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import beat as model
from ..i18n import _
from . import polish
from .clocked import ClockedTask
from .tones import Tones, note, patch


class KeepTheBeat(Tones, ClockedTask):
    """Carry the beat on after the metronome stops."""

    instance: Optional['KeepTheBeat'] = None
    thumps: list = []

    TITLE = 'Keep the Beat'
    TASK_ID = 'keep_the_beat'
    PREFIX = 'BEAT'
    CATEGORY = 'attention'
    FEEDBACK = 3.0
    MODEL = model
    SUBSTEP = 1 / 240.0
    EVENT_KEYS = {key.SPACE: model.TAP, key.J: model.TAP, key.F: model.TAP}
    FOOTNOTE = _('Space: tap   tap along, then keep the beat going when the '
                 'curtain falls   Esc: menu')

    def _deal(self) -> bool:
        ok = super()._deal()
        song = self.run.song
        self.message = _('Tap along -- then keep it going on your own')
        self.thumps = []
        notes = []
        n = len(song.level.pattern)
        for k, (b, heard) in enumerate(zip(song.beats, song.heard)):
            if heard:
                first = k % n == 0
                notes.append(note(b, 0.08, 880.0 if first else 660.0,
                                  gain=0.9 if first else 0.7,
                                  voice=0 if first else 1, seed=k))
        self._tones_start(notes, [patch('glass'), patch('wood')], song.end)
        return ok

    def steer(self, port: int) -> None:
        super().steer(port)
        if port == model.TAP and self.run is not None:
            self.thumps.append(self.run.t)

    def _build_scenery(self) -> None:
        left, bottom, width, height = self._area()
        out, batch = self.scenery, self.batch
        g0 = pyglet.graphics.Group(order=-14)
        polish.card(out, batch, left, bottom, width, height, (40, 20, 30),
                    radius=16, shade=(0, 0, 0, 60), group=polish.STAGE)
        polish.gradient(out, batch, left, bottom, width, height,
                        (70, 30, 40), (24, 14, 30), bands=20, group=g0)
        # Floorboards.
        fy = bottom + height * 0.24
        polish.gradient(out, batch, left, bottom, width, fy - bottom,
                        (110, 70, 40), (150, 100, 60), bands=6, group=g0)
        for k in range(14):
            x = left + width * k / 14
            out.append(pyglet.shapes.Line(x, bottom, x + width * 0.02, fy,
                                          thickness=1, color=(90, 56, 30),
                                          batch=batch, group=g0))
        polish.glow(out, batch, left + width * 0.32, fy + height * 0.3,
                    height * 0.45, (255, 220, 160), strength=60, group=g0)

    def _draw(self, left, bottom, width, height) -> None:
        run = self.run
        if run is None:
            return
        self._scenery_fresh(self._area())
        d, batch = self.drawn, self.batch
        song = run.song
        t = run.t
        fy = bottom + height * 0.24
        mx, my = left + width * 0.32, fy
        mh = height * 0.55
        # Where in the beat are we: the last beat at or before now.
        last = max([k for k, b in enumerate(song.beats) if b <= t],
                   default=-1)
        since = t - song.beats[last] if last >= 0 else 9.0
        hidden = run.curtain() and t > model.LEAD
        # The metronome: a wooden pyramid with a swinging arm.
        base_w = mh * 0.55
        d.append(pyglet.shapes.Polygon(
            (mx - base_w / 2, my), (mx + base_w / 2, my),
            (mx + base_w * 0.16, my + mh), (mx - base_w * 0.16, my + mh),
            color=(150, 84, 44), batch=batch, group=self.card_group))
        d.append(pyglet.shapes.Polygon(
            (mx - base_w * 0.32, my + mh * 0.12),
            (mx + base_w * 0.32, my + mh * 0.12),
            (mx + base_w * 0.1, my + mh * 0.88),
            (mx - base_w * 0.1, my + mh * 0.88),
            color=(236, 220, 190), batch=batch, group=self.body_group))
        if last >= 0 and last + 1 < len(song.beats):
            span = song.beats[last + 1] - song.beats[last]
            phase = since / span
            side = 1 if last % 2 else -1
            ang = side * math.cos(phase * math.pi) * 0.42
        else:
            ang = 0.0
        px, py = mx, my + mh * 0.18
        tip = (px + math.sin(ang) * mh * 0.7, py + math.cos(ang) * mh * 0.7)
        d.append(pyglet.shapes.Line(px, py, tip[0], tip[1], thickness=5,
                                    color=(60, 50, 60), batch=batch,
                                    group=self.text_group))
        d.append(pyglet.shapes.Rectangle(
            px + math.sin(ang) * mh * 0.45 - 9,
            py + math.cos(ang) * mh * 0.45 - 6, 18, 12,
            color=(200, 170, 80), batch=batch, group=self.top_group))
        flash = max(0.0, 1.0 - since / 0.15) if not hidden else 0.0
        first = last >= 0 and last % len(song.level.pattern) == 0
        lamp = (255, 230, 120) if first else (255, 140, 90)
        lx, ly = mx, my + mh + 18
        polish.glow(d, batch, lx, ly, 40 + 30 * flash, lamp,
                    strength=int(40 + 160 * flash), group=self.body_group)
        d.append(pyglet.shapes.Circle(lx, ly, 11, color=polish.mix(
            (90, 60, 50), lamp, flash), batch=batch, group=self.top_group))
        if hidden:
            cw = base_w * 1.5
            for k in range(7):
                x = mx - cw / 2 + cw * k / 7
                d.append(pyglet.shapes.Rectangle(
                    x, fy, cw / 7 + 1, mh + 50,
                    color=polish.mix((120, 16, 36), (170, 30, 52),
                                     0.5 + 0.5 * math.sin(k * 1.7)),
                    batch=batch, group=pyglet.graphics.Group(order=6)))
            self._text(_('keep it going'), mx, fy + mh * 0.5, 16, bold=True,
                       colour=(255, 230, 200, 230),
                       group=pyglet.graphics.Group(order=7))
        # The drum.
        dx, dy = left + width * 0.7, fy + height * 0.12
        dr = min(width, height) * 0.14
        hit = max([b for b in self.thumps if b <= t], default=-9)
        boom = max(0.0, 1.0 - (t - hit) / 0.2)
        d.append(pyglet.shapes.Ellipse(dx, dy - dr * 0.5, dr, dr * 0.4,
                                       color=(160, 40, 40), batch=batch,
                                       group=self.card_group))
        d.append(pyglet.shapes.Rectangle(dx - dr, dy - dr * 0.5, dr * 2,
                                         dr * 0.5, color=(190, 50, 50),
                                         batch=batch, group=self.body_group))
        d.append(pyglet.shapes.Ellipse(dx, dy, dr, dr * 0.4,
                                       color=polish.mix((240, 230, 210),
                                                        (255, 255, 255),
                                                        boom),
                                       batch=batch, group=self.text_group))
        if boom:
            d.append(pyglet.shapes.Arc(dx, dy, dr * (1.1 + 0.5 * (1 - boom)),
                                       thickness=3,
                                       color=(255, 230, 160,
                                              int(220 * boom)),
                                       batch=batch, group=self.top_group))
        self._strip(left, bottom, width, fy, run)

    def _strip(self, left, bottom, width, fy, run) -> None:
        """Taps along a strip; beats too, once judged."""
        d, batch = self.drawn, self.batch
        song = run.song
        first = song.beats[song.judged[0]] - 1.5
        span = song.end - first
        sx, sw = left + width * 0.06, width * 0.88
        sy = bottom + (fy - bottom) * 0.35
        polish.rounded(d, batch, sx, sy - 8, sw, 16, (60, 34, 24),
                       radius=8, group=self.card_group)

        def at(t):
            return sx + sw * max(0.0, min(1.0, (t - first) / span))
        if run.result is not None:
            w = song.level.window
            for k in song.judged:
                b = song.beats[k]
                d.append(pyglet.shapes.Rectangle(
                    at(b - w), sy - 8, max(2.0, at(b + w) - at(b - w)), 16,
                    color=(90, 200, 120, 150), batch=batch,
                    group=self.body_group))
                d.append(pyglet.shapes.Line(at(b), sy - 11, at(b), sy + 11,
                                            thickness=2,
                                            color=(140, 255, 170),
                                            batch=batch,
                                            group=self.text_group))
        for tp in run.taps:
            if tp < first:
                continue
            d.append(pyglet.shapes.Circle(at(tp), sy, 5,
                                          color=(255, 220, 120), batch=batch,
                                          group=self.top_group))

    def _facts(self) -> str:
        if self.run is None:
            return ''
        song = self.run.song
        return _('rung %d  %d/%d   %d beats to keep   %d taps') % (
            self.rung, self.trial, self.total_trials, len(song.judged),
            len(self.run.taps))
