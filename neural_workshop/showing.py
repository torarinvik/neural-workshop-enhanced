# -*- coding: utf-8 -*-
"""A question that unfolds in time, then waits for its answer.

Some questions cannot be a still picture: a flash too brief to count, a
tone that lasts a little longer than another, things going behind a
screen, a scene flickering with one change in it. A task like that
deals a puzzle that says, besides its ``choices`` and ``answer``:

``open_at``   seconds into the trial before an answer counts (earlier
              presses are ignored -- the question has not been put yet)
``limit``     seconds after which the trial fails unanswered
``notes``     the sound it makes, Dr Shape's notes (may be empty)
``patches``   the instruments those notes are played on

and :class:`Run` keeps its time. The task draws the scene for the
run's time ``t``.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional, Tuple

from .i18n import _

#: Every port is an answer, acted on once.
EVENTS = frozenset(range(64))


class Run:
    """One trial's clock and verdict."""

    def __init__(self, puzzle: Any) -> None:
        self.puzzle = puzzle
        self.t = 0.0
        self.chosen: Optional[int] = None
        self.result: Optional[Tuple[bool, str]] = None

    @property
    def open(self) -> bool:
        return self.t >= self.puzzle.open_at

    def step(self, dt: float, control: Optional[int] = None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t >= self.puzzle.limit:
            self.result = (False, _('Too slow: %s') % self.truth())

    def truth(self) -> str:
        return self.puzzle.choices[self.puzzle.answer]

    def answer(self, k: int) -> None:
        if self.result is not None or not self.open \
                or not 0 <= k < len(self.puzzle.choices):
            return
        self.chosen = k
        right = k == self.puzzle.answer
        self.result = (right, (_('Right: %s') if right else _('No: %s'))
                       % self.truth())


def act(run: Run, port: int) -> None:
    run.answer(port)


# --- sound -------------------------------------------------------------------

def note(t: float, dur: float, freq: float, pan: float = 0.0,
         gain: float = 0.8, voice: int = 0, bright: float = 0.8):
    """One plain note standing still between the ears."""
    from . import drshape
    return drshape.Note(t, dur, freq, pan, pan, gain, gain, bright, voice,
                        0, -1, 0.0)


def patch(name: str, seed: int = 1):
    """An instrument: 'sine', 'flute', 'organ' and the rest of Dr
    Shape's."""
    import random
    from . import drshape
    return drshape.make_patch(name, random.Random(seed))


def semitones(base: float, steps: float) -> float:
    return base * 2.0 ** (steps / 12.0)
