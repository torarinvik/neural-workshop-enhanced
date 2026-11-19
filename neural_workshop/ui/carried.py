# -*- coding: utf-8 -*-
"""Carried through, on screen: a state, then events a frame at a time;
where does the state stand now?

For the agent boundary: Running Count has four ports, one a card, left
to right; its twin Bead Pile four, one a card, top to bottom. Arrow
Walk has four, one a square, in reading order; its twin Chevron Walk
four, one a square, from the bottom right back to the top left.
Presses before the question is put are ignored, and the cards are
blank until it is.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations


import pyglet

from .. import carried as model
from .. import framed
from .framed import FrameTask

#: Which way each arrow points, as a unit step on screen.
SLANT = 0.7071
POINTS = {'up': (0, 1), 'down': (0, -1), 'left': (-1, 0), 'right': (1, 0),
          'up-left': (-SLANT, SLANT), 'up-right': (SLANT, SLANT),
          'down-left': (-SLANT, -SLANT), 'down-right': (SLANT, -SLANT)}


class CarriedTask(FrameTask):
    """A state, events, and a question about where it stands."""

    FAMILY = model

    def _draw_at(self, left, bottom, width, height, t) -> None:
        getattr(self, '_draw_' + self.KIND)(left, bottom, width, height, t)

    # --- shared pieces ---------------------------------------------------

    def _dots(self, n: int, cx, cy, size, colour) -> None:
        """*n* beads in rows of five, centred on (cx, cy)."""
        per = 5
        rows = max(1, (n + per - 1) // per)
        r = size / (2.6 * max(per, rows))
        gap = r * 2.5
        for i in range(n):
            row, col = divmod(i, per)
            across = min(per, n - row * per)
            x = cx + (col - (across - 1) / 2) * gap
            y = cy + ((rows - 1) / 2 - row) * gap
            self.drawn.append(pyglet.shapes.Circle(
                x, y, r, color=colour, batch=self.batch,
                group=self.text_group))

    def _arrow(self, direction: str, cx, cy, size, colour) -> None:
        dx, dy = POINTS[direction]
        thick = size * 0.12
        if self.puzzle.data['look'] == 0:
            tail = (cx - dx * size * 0.45, cy - dy * size * 0.45)
            neck = (cx + dx * size * 0.1, cy + dy * size * 0.1)
            self.drawn.append(pyglet.shapes.Line(
                *tail, *neck, thickness=thick, color=colour,
                batch=self.batch, group=self.text_group))
            tip = (cx + dx * size * 0.5, cy + dy * size * 0.5)
            px, py = -dy, dx
            self.drawn.append(pyglet.shapes.Triangle(
                *tip, neck[0] + px * size * 0.25, neck[1] + py * size * 0.25,
                neck[0] - px * size * 0.25, neck[1] - py * size * 0.25,
                color=colour, batch=self.batch, group=self.text_group))
            return
        # A pair of chevrons.
        px, py = -dy, dx
        for back in (0.0, 0.35):
            tip = (cx + dx * size * (0.35 - back), cy + dy * size * (0.35 - back))
            for side in (1, -1):
                end = (tip[0] - dx * size * 0.3 + side * px * size * 0.3,
                       tip[1] - dy * size * 0.3 + side * py * size * 0.3)
                self.drawn.append(pyglet.shapes.Line(
                    *tip, *end, thickness=thick, color=colour,
                    batch=self.batch, group=self.text_group))

    def _colour(self):
        if self.puzzle.data['look'] == 0:
            return self._hue()
        return framed.BEADS[(self.puzzle.data['rim'] * 3) % framed.THINGS]

    # --- the count -------------------------------------------------------

    def _draw_count(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        look, data = p.data['look'], p.data
        f, showing = self._frame(t)
        colour = self._colour()
        if look == 0:
            card = min(width * 0.14, height * 0.22)
            pane = min(width * 0.3, height - card * 1.5)
            px, py = self._placed(left, bottom + card * 1.5, width,
                                  height - card * 1.5, pane, pane)
            x0 = left + (width - card * 4.6) / 2
            places = [(x0 + i * card * 1.2, bottom) for i in range(4)]
        else:
            card = min(height * 0.2, width * 0.15)
            pane = min(height * 0.8, width * 0.4)
            px, py = self._placed(left, bottom, width - card * 2,
                                  height, pane, pane)
            x = left + width - card * 1.25
            y0 = bottom + (height - card * 4.6) / 2
            places = [(x, y0 + i * card * 1.2) for i in range(4)]
        self._box(px, py, pane, pane, None, self.ink, thickness=1.5)
        cx, cy = px + pane / 2, py + pane / 2
        if showing is not None:
            if f == 0:
                if look == 0:
                    self._text(str(data['start']), cx, cy, pane * 0.3,
                               bold=True, colour=colour + (255,))
                else:
                    self._dots(data['start'], cx, cy, pane * 0.9, colour)
            else:
                step = data['steps'][f - 1]
                if look == 0:
                    self._text('+1' if step > 0 else '-1', cx, cy,
                               pane * 0.3, bold=True,
                               colour=colour + (255,))
                else:
                    self._dots(1, cx - pane * 0.2, cy, pane * 0.5, colour)
                    self._arrow('down' if step > 0 else 'up',
                                cx + pane * 0.2, cy, pane * 0.5, self.ink)
        order = framed.port_order(look, model.CARDS)
        for port in range(model.CARDS):
            place = order[port]
            x, y = places[place]
            self._card(port, x, y, card, card)
            if self.run is not None and self.run.open:
                value = data['cards'][place]
                if look == 0:
                    self._text(str(value), x + card / 2, y + card * 0.45,
                               card * 0.3, bold=True,
                               colour=colour + (255,))
                else:
                    self._dots(value, x + card / 2, y + card * 0.45,
                               card * 0.8, colour)
        self._asked(left + width * 0.04, bottom + height * 0.6, card * 0.4)

    # --- the arrows ------------------------------------------------------

    def _draw_arrows(self, left, bottom, width, height, t) -> None:
        p = self.puzzle
        look, data = p.data['look'], p.data
        f, showing = self._frame(t)
        side = min(height * 0.9, width * 0.42)
        cell = side / 2
        pane = side * 0.7
        if look == 0:
            bx, by = self._placed(left + width * 0.08, bottom, width * 0.5,
                                  height, side, side)
            ax = left + width * 0.78
        else:
            bx, by = self._placed(left + width * 0.45, bottom,
                                  width * 0.55, height, side, side)
            ax = left + width * 0.24
        ay = bottom + height / 2
        order = framed.port_order(look, model.CARDS)
        for port in range(model.CARDS):
            square = order[port]
            row, col = divmod(square, 2)
            x = bx + col * cell
            y = by + (1 - row) * cell
            self._card(port, x + cell * 0.05, y + cell * 0.05, cell * 0.9,
                       cell * 0.9)
            if showing is not None and f == 0 and square == data['start']:
                if look == 0:
                    self.drawn.append(pyglet.shapes.Circle(
                        x + cell / 2, y + cell / 2, cell * 0.25,
                        color=self._colour(), batch=self.batch,
                        group=self.text_group))
                else:
                    self.drawn.append(pyglet.shapes.Star(
                        x + cell / 2, y + cell / 2, cell * 0.3,
                        cell * 0.13, 6, color=self._colour(),
                        batch=self.batch, group=self.text_group))
        if showing is not None and f > 0:
            self._arrow(model.ARROWS[data['arrows'][f - 1]], ax, ay, pane,
                        self._colour())
        self._asked(left + width * 0.04, bottom + height * 0.85,
                    cell * 0.25)


def _task(cls_name, title, task_id, prefix, kind, look):
    return type(cls_name, (CarriedTask,), {
        'instance': None, 'TITLE': title, 'TASK_ID': task_id,
        'PREFIX': prefix, 'KIND': kind, 'LOOK': look,
        '__doc__': '%s (%s, look %d)' % (title, kind, look)})


RunningCount = _task('RunningCount', 'Running Count', 'running_count',
                     'RUNNINGCOUNT', 'count', 0)
BeadPile = _task('BeadPile', 'Bead Pile', 'bead_pile', 'BEADPILE',
                 'count', 1)
ArrowWalk = _task('ArrowWalk', 'Arrow Walk', 'arrow_walk', 'ARROWWALK',
                  'arrows', 0)
ChevronWalk = _task('ChevronWalk', 'Chevron Walk', 'chevron_walk',
                    'CHEVRONWALK', 'arrows', 1)

