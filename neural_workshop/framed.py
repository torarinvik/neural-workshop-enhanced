# -*- coding: utf-8 -*-
"""What the frame-by-frame families share: a frame clock that can be
stepped a frame at a time, the things they show, and their two looks.

The held-in-mind tasks put the answer in how the frame showing stands
to one no longer showing. The families built on this module do the
same in more ways: what moved or went missing between two showings
(:mod:`nowthen`), a state carried through a run of events
(:mod:`carried`), a mark far back behind look-alikes (:mod:`farcue`),
and the same in sound (:mod:`heardback`).

Every task here comes in two looks, so that each rule has a twin:
look 0 draws plain shapes in one hue, laid out on a square grid, with
the ports in reading order; look 1 draws coloured beads, laid out round
a ring, with the ports the other way round. The two looks share no
colour.

A frame lasts :data:`FRAME` seconds. A run of these tasks may be
stepped at one step a frame (two frames a second): :class:`Run` and
:func:`frame_at` read the clock with a little give, so that a time
summed from many small steps lands in the frame it means.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import List, Tuple

from . import showing
from .lookback import ANSWER, FRAME, SHOWN, Puzzle  # noqa: F401

#: How close to a frame's start a summed clock counts as being there.
GIVE = 1e-6

LOOKS = (0, 1)

#: Look 0: plain shapes, all in the trial's hue; hollow ones count as
#: other things.
SHAPES = (('circle', False), ('square', False), ('triangle', False),
          ('diamond', False), ('star', False), ('cross', False),
          ('circle', True), ('square', True))
HUES_A = ((36, 104, 196), (122, 70, 170), (20, 124, 132),
          (176, 110, 20), (150, 70, 110))
#: Look 1: beads told apart by colour.
BEADS = ((214, 48, 49), (238, 160, 20), (60, 160, 60), (30, 120, 220),
         (140, 70, 200), (240, 120, 180), (0, 176, 176), (40, 40, 40))
#: Look 1's rims, one drawn a trial.
RIMS = ((150, 150, 160), (120, 120, 120), (176, 168, 150))
THINGS = len(SHAPES)
assert len(BEADS) == THINGS


class Run(showing.Run):
    """A trial's clock, open from the frame the question is put on."""

    @property
    def open(self) -> bool:
        return self.t + GIVE >= self.puzzle.open_at


def frame_at(puzzle: Puzzle, t: float) -> Tuple[int, bool]:
    """Which frame *t* falls in, and whether it is showing."""
    f = min(len(puzzle.frames) - 1, int(t / FRAME + GIVE))
    last = f == len(puzzle.frames) - 1
    return f, last or t - f * FRAME < SHOWN


def port_order(look: int, n: int) -> Tuple[int, ...]:
    """Which place each port stands for: reading order in look 0, the
    other way round in look 1."""
    places = tuple(range(n))
    return places if look == 0 else places[::-1]


def spots(look: int) -> List[Tuple[float, float]]:
    """The nine places a board has, as fractions of its square: a
    three-by-three grid in look 0, eight round a ring and its middle in
    look 1."""
    if look == 0:
        return [((c + 0.5) / 3, 1 - (r + 0.5) / 3)
                for r in range(3) for c in range(3)]
    import math
    ring = [(0.5 + 0.38 * math.cos(math.pi / 2 - k * math.pi / 4),
             0.5 + 0.38 * math.sin(math.pi / 2 - k * math.pi / 4))
            for k in range(8)]
    return ring + [(0.5, 0.5)]


def opened(frames: int) -> float:
    """When the question is put: on the last of *frames* frames."""
    return (frames - 1) * FRAME


def puzzle(kind, k, frames, choices, answer, data, question, notes=(),
           patches=()) -> Puzzle:
    """A trial asked on its last frame, with the usual time to answer."""
    open_at = opened(len(frames))
    return Puzzle(kind, k, tuple(frames), tuple(choices), answer, open_at,
                  open_at + ANSWER, tuple(notes), tuple(patches), data,
                  question)
