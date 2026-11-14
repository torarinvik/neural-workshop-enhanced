# -*- coding: utf-8 -*-
"""Will It Fall? on screen: the scene above, the answers below.

Towers of lettered blocks on the floor; a plank on a pivot with piles of
boxes and a mark at every whole position; or a table, a ball at its
edge, a trail of dots where it was at equal moments, and numbered bins
on the floor. Click an answer or press its number. When a choice is
judged the truth is drawn in: the block that topples outlined, the
plank tilted, the ball's whole path traced to where it lands.

For the agent boundary: ports 0-7 choose answers 1-8.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
from typing import Optional

import pyglet
from pyglet.window import key

from .. import falls as model
from ..geometry import calc_fontsize
from ..i18n import _
from .rungtask import RungTask

BLOCK = (176, 132, 88)
BLOCK_EDGE = (90, 60, 36)
FLOOR = (110, 114, 124)
TABLE = (150, 110, 70)
BALL = (60, 110, 200)
TRAIL = (120, 150, 210)
PATH = (40, 90, 220)
FELL = (214, 64, 58)
STOOD = (60, 170, 90)
BUTTON_LIGHT = (232, 235, 240)
BUTTON_DARK = (46, 50, 58)
LEVER = (120, 90, 60)
BOX = (200, 160, 90)


class WillItFall(RungTask):
    """Say what a still physical scene does next."""

    instance: Optional['WillItFall'] = None

    TITLE = 'Will It Fall?'
    TASK_ID = 'will_it_fall'
    PREFIX = 'WILL_IT_FALL'
    CATEGORY = 'perception'
    FEEDBACK = 2.8
    FOOTNOTE = _('click an answer or press its number   Esc: menu')

    def __init__(self) -> None:
        self.puzzle: Optional[model.Puzzle] = None
        self.chosen: Optional[int] = None
        super().__init__()

    def _clear_trial(self) -> None:
        self.puzzle = None
        self.chosen = None

    def _deal(self) -> bool:
        self.puzzle = model.deal(self.rung, rng=self.rng)
        self.chosen = None
        self.message = self.puzzle.question
        return True

    # --- actions ---------------------------------------------------------

    def steer(self, port: int) -> None:
        self.choose(port)

    def choose(self, index: int) -> None:
        if self.phase != self.PLAY or self.puzzle is None \
                or not 0 <= index < len(self.puzzle.choices):
            return
        self.chosen = index
        right = index == self.puzzle.answer
        truth = self.puzzle.choices[self.puzzle.answer]
        self._judge(right, (_('Right: %s') if right else
                            _('No: %s')) % truth.lower())

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._8:
            self.choose(symbol - key._1)

    # --- drawing ---------------------------------------------------------

    def _world(self, left, bottom, width, height):
        scale = min(width / model.WORLD_W, height / model.WORLD_H)
        x0 = left + (width - model.WORLD_W * scale) / 2

        def at(x, y):
            return x0 + x * scale, bottom + y * scale
        return at, scale

    def _draw(self, left, bottom, width, height) -> None:
        puzzle = self.puzzle
        buttons = height * 0.16
        scene_bottom = bottom + buttons + height * 0.04
        at, scale = self._world(left, scene_bottom, width,
                                height - buttons - height * 0.04)
        fx, fy = at(0, 0)
        self._box(fx, fy - 4, model.WORLD_W * scale, 4, FLOOR)
        if puzzle.blocks:
            self._draw_tower(at, scale)
        elif puzzle.lever:
            self._draw_lever(at, scale)
        else:
            self._draw_flight(at, scale)
        self._draw_buttons(left, bottom, width, buttons)

    def _draw_tower(self, at, scale) -> None:
        puzzle = self.puzzle
        blocks = list(puzzle.blocks)
        fell = model.first_to_fall(blocks) if self.phase == 'judged' \
            else None
        size = min(calc_fontsize(14), blocks[0].h * scale * 0.45)
        for index, block in enumerate(blocks):
            x, y = at(block.x, block.y)
            edge = BLOCK_EDGE
            if fell is not None and index >= fell:
                edge = FELL
            self._box(x, y, block.w * scale, block.h * scale, BLOCK, edge,
                      thickness=3 if edge == FELL else 2)
            if puzzle.kind == 'first':
                self._text(model.LETTERS[index], x + block.w * scale / 2,
                           y + block.h * scale / 2, size, bold=True,
                           colour=(255, 255, 255, 255))
        if self.phase == 'judged' and fell is None:
            top = blocks[-1]
            x, y = at(top.middle, top.y + top.h)
            self._text(_('stands'), x, y + size, size, bold=True)

    def _draw_lever(self, at, scale) -> None:
        length, pivot, plank_mass, piles = self.puzzle.lever
        unit = 0.9
        mid = model.WORLD_W / 2

        def pos(p):
            return mid + p * unit
        height = 1.6
        tilt = 0.0
        if self.phase == 'judged':
            tilt = {0: 0.12, 1: -0.12, 2: 0.0}[self.puzzle.answer]
        px, py = at(pos(pivot), height)
        bx, by = at(pos(pivot), 0)
        self.drawn.append(pyglet.shapes.Triangle(
            bx - 0.5 * scale, by, bx + 0.5 * scale, by, px, py,
            color=FLOOR, batch=self.batch, group=self.card_group))

        def on_plank(p, up):
            dx = (pos(p) - pos(pivot)) * scale
            return (px + dx * math.cos(tilt) - up * math.sin(tilt),
                    py + dx * math.sin(tilt) + up * math.cos(tilt))
        thick = 0.18 * scale
        a = on_plank(-length / 2, 0)
        b = on_plank(length / 2, 0)
        self.drawn.append(pyglet.shapes.Line(
            a[0], a[1], b[0], b[1], thickness=thick, color=LEVER,
            batch=self.batch, group=self.body_group))
        size = calc_fontsize(10)
        for p in range(-5, 6):
            tx, ty = on_plank(p, -thick)
            self._text('|', tx, ty, size * 0.8, colour=(*FLOOR, 255))
        box = unit * 0.85 * scale
        for p, count in piles:
            for n in range(count):
                cx, cy = on_plank(p, thick / 2 + box * (n + 0.5))
                self._box(cx - box / 2, cy - box / 2, box, box, BOX,
                          BLOCK_EDGE)

    def _draw_flight(self, at, scale) -> None:
        height, edge, speed, lo, hi, dots, bounces = self.puzzle.flight
        tx, ty = at(0, 0)
        ex, ey = at(edge, height)
        self._box(tx, ty, ex - tx, ey - ty, TABLE, BLOCK_EDGE)
        radius = 0.14 * scale
        for k, (x, y) in enumerate(dots):
            cx, cy = at(x, y + 0.14)
            self.drawn.append(pyglet.shapes.Circle(
                cx, cy, radius * (0.6 if k else 1.0),
                color=BALL if k == 0 else TRAIL, batch=self.batch,
                group=self.body_group))
        bins = len(self.puzzle.choices)
        width = (hi - lo) / bins
        size = min(calc_fontsize(13), width * scale * 0.35)
        for i in range(bins + 1):
            x, y = at(lo + i * width, 0)
            self._box(x - 1, y, 2, 0.45 * scale, FLOOR)
        for i in range(bins):
            x, y = at(lo + (i + 0.5) * width, 0.22)
            self._text('%d' % (i + 1), x, y, size, bold=True)
        if self.phase == 'judged':
            self._trace(at, height, edge, speed, bounces)

    def _trace(self, at, height, edge, speed, bounces) -> None:
        points = []
        x, y, up, t = edge, height, 0.0, 0.0
        step = 0.02
        left = bounces
        while len(points) < 2000:
            points.append(at(x, y + 0.14))
            x += speed * step
            up -= model.G * step
            y += up * step
            if y <= 0:
                if left == 0:
                    points.append(at(x, 0.14))
                    break
                left -= 1
                y = 0.0
                up = -up * model.BOUNCE
        for (ax, ay), (bx, by) in zip(points[::3], points[3::3]):
            self.drawn.append(pyglet.shapes.Line(
                ax, ay, bx, by, thickness=2, color=PATH, batch=self.batch,
                group=self.body_group))

    def _draw_buttons(self, left, bottom, width, height) -> None:
        choices = self.puzzle.choices
        n = len(choices)
        gap = width * 0.012
        bw = (width - gap * (n - 1)) / n
        back = BUTTON_DARK if self.dark else BUTTON_LIGHT
        for i, words in enumerate(choices):
            x = left + i * (bw + gap)
            border, thick = self.ink, 2
            if self.phase == 'judged':
                if i == self.puzzle.answer:
                    border, thick = STOOD, 4
                elif i == self.chosen:
                    border, thick = FELL, 4
            self._box(x, bottom, bw, height, back, border, thickness=thick)
            label = self._text('%d  %s' % (i + 1, words), x + bw / 2,
                               bottom + height / 2,
                               min(calc_fontsize(14), height * 0.3))
            if label.content_width > bw * 0.9:
                label.font_size *= bw * 0.9 / label.content_width
            self.hits.append((x, bottom, bw, height,
                              lambda c=i: self.choose(c)))

    def _facts(self) -> str:
        if self.puzzle is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)
