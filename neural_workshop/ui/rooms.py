# -*- coding: utf-8 -*-
"""Where Was It? on screen: the rooms one by one, then the test.

While studying, a room fills the playing area with its name above and a
Next room button below (Space or Enter too); the last one's button says
Ready. Then one room comes back changed: click the square -- or the
thing standing on it -- the question asks for. After the verdict the
right squares are outlined green, and a wrong click red.

For the agent boundary: ports 0-29 click squares, counted across each
row from the front left corner and then row by row away from the eye
(as the room is first shown); port 30 is Next room / Ready.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional

from pyglet.window import key, mouse

from .. import rooms as model, space
from ..geometry import calc_fontsize
from ..i18n import _
from . import spacepaint
from .rungtask import RungTask
from .spacetask import BUTTON_DARK, BUTTON_LIGHT, RIGHT, WRONG

NEXT = 30
SKY = (238, 240, 244)
SKY_DARK = (28, 30, 36)


class WhereWasIt(RungTask):
    """Remember where everything stood; spot what changed."""

    instance: Optional['WhereWasIt'] = None

    TITLE = 'Where Was It?'
    TASK_ID = 'where_was_it'
    PREFIX = 'WHERE_WAS_IT'
    CATEGORY = 'long_term_memory'
    FEEDBACK = 3.0
    FOOTNOTE = _('Space: next room   then click where it changed   '
                 'Esc: menu')

    def __init__(self) -> None:
        self.puzzle: Optional[model.Puzzle] = None
        self.stage = 0
        self.chosen: Optional[int] = None
        self.painted: List[space.Painted] = []
        self.place = None
        self.unplace = None
        super().__init__()

    def _clear_trial(self) -> None:
        self.puzzle = None
        self.stage = 0
        self.chosen = None
        self.painted = []

    def _deal(self) -> bool:
        self.puzzle = model.deal(self.rung, rng=self.rng)
        self.stage = 0
        self.chosen = None
        self._say()
        return True

    @property
    def testing(self) -> bool:
        return self.puzzle is not None and \
            self.stage >= len(self.puzzle.rooms)

    def _say(self) -> None:
        puzzle = self.puzzle
        if self.testing:
            self.message = puzzle.question
        else:
            self.message = _('Room %d of %d: %s -- remember where '
                             'everything is') % (
                self.stage + 1, len(puzzle.rooms),
                puzzle.rooms[self.stage].name)

    # --- actions ---------------------------------------------------------

    def next_room(self) -> None:
        if self.phase != self.PLAY or self.testing:
            return
        self.stage += 1
        self._say()
        self._redraw()

    def choose(self, cell: int) -> None:
        puzzle = self.puzzle
        if self.phase != self.PLAY or not self.testing or \
                not 0 <= cell < puzzle.cols * puzzle.rows:
            return
        self.chosen = cell
        right = cell in puzzle.answer
        words = {'moved': _('the thing that moved'),
                 'gone': _('where the missing thing stood'),
                 'swapped': _('the two that swapped'),
                 'recoloured': _('the thing that changed colour')}
        self._judge(right, (_('Right: that is %s') if right else
                            _('No: %s is outlined')) %
                    words[puzzle.change])

    def steer(self, port: int) -> None:
        if port == NEXT:
            self.next_room()
        else:
            self.choose(port)

    def _key(self, symbol: int, modifiers: int) -> None:
        if symbol in (key.SPACE, key.ENTER, key.RETURN, key.N):
            self.next_room()

    def _click(self, x: float, y: float, button: int) -> None:
        if button != mouse.LEFT:
            return
        for left, bottom, w, h, action in list(self.hits):
            if left <= x <= left + w and bottom <= y <= bottom + h:
                action()
                return
        if self.testing and self.unplace is not None:
            cell = model.pick(self.painted, *self.unplace(x, y))
            if cell is not None:
                self.choose(cell)

    # --- drawing ---------------------------------------------------------

    def _draw(self, left, bottom, width, height) -> None:
        spacepaint.begin(self)
        puzzle = self.puzzle
        button_h = 0.0 if self.testing else height * 0.1
        if button_h:
            bw = width * 0.24
            bx = left + (width - bw) / 2
            back = BUTTON_DARK if self.dark else BUTTON_LIGHT
            self._box(bx, bottom, bw, button_h, back, self.ink)
            last = self.stage == len(puzzle.rooms) - 1
            self._text(_('Ready') if last else _('Next room'),
                       bx + bw / 2, bottom + button_h / 2,
                       min(calc_fontsize(14), button_h * 0.35))
            self.hits.append((bx, bottom, bw, button_h, self.next_room))
            bottom += button_h * 1.3
            height -= button_h * 1.3
        if self.testing:
            room, angle = puzzle.changed, puzzle.angle
        else:
            room, angle = puzzle.rooms[self.stage], 0.0
        self._box(left, bottom, width, height,
                  SKY_DARK if self.dark else SKY)
        x0, y0, x1, y1 = model.bounds(puzzle.cols, puzzle.rows, angle)
        scale = 0.9 * min(width / (x1 - x0), height / (y1 - y0))
        cx = left + width / 2 - (x0 + x1) / 2 * scale
        cy = bottom + height / 2 - (y0 + y1) / 2 * scale
        self.place = lambda x, y: (cx + x * scale, cy + y * scale)
        self.unplace = lambda x, y: ((x - cx) / scale, (y - cy) / scale)
        self.painted = model.scene(puzzle.cols, puzzle.rows, room, angle)
        spacepaint.paint(self, self.painted, self.place, rim_px=1.3)
        if self.phase == 'judged':
            cam = model.camera(puzzle.cols, puzzle.rows, angle)
            marks = [(c, RIGHT) for c in puzzle.answer]
            if self.chosen is not None and self.chosen not in puzzle.answer:
                marks.append((self.chosen, WRONG))
            for cell, colour in marks:
                pts = [self.place(*cam.project(p))
                       for p in model.cell_corners(cell, puzzle.cols)]
                for k in range(4):
                    (ax, ay), (bx_, by) = pts[k - 1], pts[k]
                    self._line(ax, ay, bx_, by, colour)

    def _line(self, ax, ay, bx, by, colour) -> None:
        import pyglet
        self.drawn.append(pyglet.shapes.Line(
            ax, ay, bx, by, thickness=5, color=colour, batch=self.batch,
            group=self.top_group))

    def _facts(self) -> str:
        if self.puzzle is None:
            return ''
        return _('rung %d  %d/%d') % (self.rung, self.trial,
                                      self.total_trials)
