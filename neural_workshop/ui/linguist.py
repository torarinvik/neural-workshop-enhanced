# -*- coding: utf-8 -*-
"""The Linguist on screen: the examples above, the question below.

Each example is a picture and, under it, what the language says for
it. In a picture an arrow runs from the doer to the done-to, and its
kind -- plain, dashed, doubled -- is the deed; three of a thing is
more than one; a large one is big; grey has no colour said.

Click an answer or press its number. To build a sentence, click the
word tiles in order (or press 1-9 and 0 for the tenth); Backspace
takes the last one back; Enter says it is done.

For the agent boundary: ports 0-7 pick an answer; to build, ports 0-9
take a tile, port 10 takes the last one back, port 11 is done.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Optional

from pyglet.window import key

from .. import linguist as model
from ..i18n import _
from .scenetask import SceneChoice, paint


class Linguist(SceneChoice):
    """Work out a language from a few examples, and use it."""

    instance: Optional['Linguist'] = None

    TITLE = 'The Linguist'
    TASK_ID = 'the_linguist'
    PREFIX = 'LINGUIST'
    CATEGORY = 'reasoning'
    MODEL = model
    BUTTONS = 0
    FEEDBACK = 3.0
    FOOTNOTE = _('click an answer or press its number   building: click '
                 'the words, Backspace, Enter   Esc: menu')

    def __init__(self) -> None:
        self.taken: List[int] = []
        super().__init__()

    def _clear_trial(self) -> None:
        super()._clear_trial()
        self.taken = []

    def _deal(self) -> bool:
        self.taken = []
        return super()._deal()

    def choose(self, index: int) -> None:
        p = self.puzzle
        if self.phase != self.PLAY or p is None:
            return
        if p.kind != 'build':
            if 0 <= index < len(p.options):
                self.chosen = index
                right = index == p.answer
                self._judge(right, self._verdict(right))
            return
        if index == model.DONE:
            if self.taken:
                right = model.check(p, self.taken)
                self._judge(right, self._verdict(right))
            return
        if index == model.UNDO:
            if self.taken:
                self.taken.pop()
        elif 0 <= index < len(p.options) and index not in self.taken:
            self.taken.append(index)
        self._redraw()

    def _verdict(self, right: bool) -> str:
        p = self.puzzle
        said = _('Right') if right else _('No')
        if p.kind != 'build':
            said += ': %d' % (p.answer + 1)
        return said

    def _key(self, symbol: int, modifiers: int) -> None:
        if key._1 <= symbol <= key._9:
            self.choose(symbol - key._1)
        elif symbol == key._0:
            self.choose(9)
        elif symbol == key.BACKSPACE:
            self.choose(model.UNDO)
        elif symbol in (key.RETURN, key.ENTER):
            self.choose(model.DONE)

    def _mark(self, index: int):
        p = self.puzzle
        if p is not None and p.kind == 'build':
            return self.ink, 2
        return super()._mark(index)

    def _draw_scene(self, left, bottom, width, height) -> None:
        p = self.puzzle
        paint(self, model.scene(p, tuple(self.taken),
                                self.phase == 'judged'),
              left, bottom, width, height, (248, 247, 242))

    def _facts(self) -> str:
        said = super()._facts()
        p = self.puzzle
        if p is not None and self.phase == 'judged' and p.said:
            said += '   ' + p.said
        elif p is not None and p.examples:
            said += '   ' + _('%d examples') % len(p.examples)
        return said
