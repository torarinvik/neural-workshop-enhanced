# -*- coding: utf-8 -*-
"""The screens for tasks that describe their picture as a scene.

:class:`SceneChoice` is a choice task and :class:`SceneShow` one that
unfolds in time; both draw whatever list of primitives the model's
``scene(puzzle, t, judged)`` gives (see :mod:`neural_workshop.scenes`),
fitted into the playing area. A subclass names the model and itself.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import pyglet

from .. import scenes
from . import polish
from .showtask import ShowTask
from .spacetask import ChoiceTask


def paint(task, prims, left, bottom, width, height, paper) -> None:
    s = min(width / scenes.W, height)
    w, h = scenes.W * s, s
    x0, y0 = left + (width - w) / 2, bottom + (height - h) / 2
    polish.card(task.drawn, task.batch, x0, y0, w, h, paper, radius=12,
                group=task.card_group)
    order = 0
    for prim in prims:
        kind = prim[0]
        order += 1
        group = pyglet.graphics.Group(order=order, parent=task.body_group)
        if kind == 'rect':
            _k, x, y, rw, rh, colour = prim
            task.drawn.append(pyglet.shapes.Rectangle(
                x0 + x * s, y0 + y * s, rw * s, rh * s, color=colour,
                batch=task.batch, group=group))
        elif kind == 'disc':
            _k, x, y, r, colour = prim
            task.drawn.append(pyglet.shapes.Circle(
                x0 + x * s, y0 + y * s, max(0.8, r * s), color=colour,
                batch=task.batch, group=group))
        elif kind == 'ring':
            _k, x, y, r, rw, colour = prim
            task.drawn.append(pyglet.shapes.Arc(
                x0 + x * s, y0 + y * s, r * s, segments=96,
                thickness=max(1.0, rw * s), color=colour, batch=task.batch,
                group=group))
        elif kind == 'poly':
            _k, pts, colour = prim
            task.drawn.append(pyglet.shapes.Polygon(
                *[(x0 + x * s, y0 + y * s) for x, y in pts], color=colour,
                batch=task.batch, group=group))
        elif kind == 'line':
            _k, xa, ya, xb, yb, lw, colour = prim
            task.drawn.append(pyglet.shapes.Line(
                x0 + xa * s, y0 + ya * s, x0 + xb * s, y0 + yb * s,
                thickness=max(1.0, lw * s), color=colour, batch=task.batch,
                group=group))
        elif kind == 'text':
            _k, x, y, size, words, colour = prim
            task._text(words, x0 + x * s, y0 + y * s, max(7.0, size * s),
                       bold=True, colour=tuple(colour) + (255,),
                       group=task.top_group)
        elif kind == 'hit':
            _k, x, y, hw, hh, choice = prim
            border, thick = task._mark(choice)
            if thick > 2:
                task.drawn.append(pyglet.shapes.Box(
                    x0 + x * s, y0 + y * s, hw * s, hh * s, thickness=thick,
                    color=border, batch=task.batch, group=task.top_group))
            task.hits.append((x0 + x * s, y0 + y * s, hw * s, hh * s,
                              lambda c=choice: task.choose(c)))


class SceneChoice(ChoiceTask):
    """A still scene and its answers."""

    MODEL = None

    def _make(self):
        return self.MODEL.deal(self.rung, rng=self.rng)

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        paint(self, self.MODEL.scene(p, 0.0, self.phase == 'judged'), left,
              bottom, width, height, getattr(p, 'paper', scenes.PAPER))


class SceneShow(ShowTask):
    """A scene that plays, and its answers."""

    SCENES = None

    def _make(self):
        return self.SCENES.deal(self.rung, rng=self.rng)

    def _draw_at(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        paint(self, self.SCENES.scene(p, t, self.phase == 'judged'), left,
              bottom, width, height, getattr(p, 'paper', scenes.PAPER))
