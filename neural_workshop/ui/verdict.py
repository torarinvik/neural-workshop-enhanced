# -*- coding: utf-8 -*-
"""The one thing a task must paint for the agent boundary to read it.

The boundary already knows how to derive a public scalar from pixels:
:func:`nwenv.outcome.derive_public_outcome` counts runs of the standard label
colours in the bottom quarter of the frame, and it is what
:func:`nwenv.outcome.verify_public_outcome` falls back to when a task passes
no reader of its own. Both halves are written, tested and natively
accelerated.

Three tasks were wrapped before this existed and none of them used that path.
Fog counts world colours, Monkey Ladder counts tile colours, Out of Sight
counts ring colours -- so each carries a bespoke 46-59 line deriver and a
36-40 line verifier maintained beside it. That is roughly a hundred lines per
task, and two functions that must agree while being edited separately.

A task that paints this label instead needs **neither**. It inherits the
deriver and the verifier that already exist, and they are the same ones every
other task uses, so there is one pixel reader in the programme to get right
rather than one per task.

**When to show it.** Only once the trial has resolved and its action window
has closed. Painted a frame early this stops being a verdict and becomes an
answer key: a learner that can see the verdict while it can still act will
read the label instead of the task, and every result gathered afterwards is
about the label.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

import pyglet

from .. import state
from ..geometry import calc_fontsize, from_bottom_edge, width_center

#: Where the label sits. The reader looks at rows from three quarters of
#: the way down to the bottom edge, so anything painted here is in the band
#: whatever the window size.
BAND_TOP = 0.75

#: What the reader treats as a verdict colour. It is deliberately tolerant --
#: a channel at or above :data:`BRIGHT` with the other two at or below
#: :data:`DIM` -- because anti-aliased glyph edges never land on an exact
#: value. The tolerance is also the constraint on task art: **nothing else
#: in the bottom quarter of the frame may be a saturated red, green or
#: blue**, or it will be read as a verdict. Measured on a bare application
#: window, the persistent furniture already contributes one blue run, so a
#: task that paints here must own the band.
BRIGHT, DIM = 180, 140


class VerdictLabel:
    """A resolved trial's verdict, painted where the boundary can read it."""

    def __init__(self, font_size: float = 16.0, batch=None) -> None:
        self.label = pyglet.text.Label(
            text='', x=width_center(), y=from_bottom_edge(30),
            anchor_x='center', anchor_y='center',
            batch=state.batch if batch is None else batch,
            font_size=calc_fontsize(font_size))
        self.label.visible = False

    def show(self, good: bool, text: Optional[str] = None) -> None:
        """Paint the verdict for a trial that has already resolved.

        *good* is the whole of the public scalar: green reads +1 and red
        reads -1. *text* is for the person playing and does not change what
        is derived, so it can say whatever the task wants.
        """
        cfg = state.cfg
        self.label.color = (cfg.COLOR_LABEL_CORRECT if good
                            else cfg.COLOR_LABEL_INCORRECT)
        self.label.text = text if text is not None else ('Correct' if good
                                                         else 'Incorrect')
        self.label.visible = True

    def clear(self) -> None:
        """Take the verdict down. Call this when the next trial opens.

        A verdict left up spans two trials, and the second one derives the
        first one's scalar.
        """
        self.label.text = ''
        self.label.visible = False

    def delete(self) -> None:
        self.label.delete()
