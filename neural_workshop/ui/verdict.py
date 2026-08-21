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
from ..geometry import (calc_fontsize, from_bottom_edge, pixel_size,
                        width_center)

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

#: How far above the band a task's own art has to stop, in pixels.
#:
#: Not zero, and the reason is anti-aliasing rather than sloppiness. The
#: Maze drew its doors in Okabe-Ito orange, ``(230, 159, 0)``, which is
#: not a verdict colour: green sits at 159, comfortably over
#: :data:`DIM`. But an orange square on a pale background is edged by
#: every blend between the two, and part of that ramp has green already
#: below 140 while red is still above 180 — which *is* the reader's
#: pattern for a positive verdict. Nine such pixels in a row were being
#: paid as a scored trial.
#:
#: So the rule is not "avoid three colours". Any colour with two
#: channels far apart passes through the window on its way to the
#: background, and a task cannot know which of its blends will. The
#: rule is the simpler one: keep the art out of the band, and leave a
#: few pixels of slack for the edge of the art nearest it.
CLEARANCE = 8


def band_rows(height: Optional[int] = None) -> tuple:
    """The image rows the boundary's reader scans, as ``(first, past)``.

    Row 0 is the top of the captured frame, which is what
    :func:`nwenv.frames.capture_rgba` hands back. Deliberately computed
    the same way :func:`bwaccel.default_band` computes it, and
    ``tests/test_ui_band.py`` fails if the two ever disagree — this
    module is where a task asks where the band is, so it must not be a
    second opinion about it.
    """
    height = pixel_size()[1] if height is None else int(height)
    return int(height * BAND_TOP), height


def above_the_band(y: float = 0.0) -> int:
    """Hold *y* clear of the strip the agent boundary reads.

    The one call a task's layout needs. Pass whatever bottom margin the
    layout wanted and use what comes back::

        bottom = above_the_band(from_bottom_edge(56))

    On a window too short to have a playfield at all this still returns
    the band's ceiling, so the task is laid out badly rather than laid
    out into the band: a cramped screen is a nuisance, a scalar read
    off the scenery is a wrong result.
    """
    height = pixel_size()[1]
    return max(int(y), height - band_rows(height)[0] + CLEARANCE)


class VerdictLabel:
    """A resolved trial's verdict, painted where the boundary can read it."""

    def __init__(self, font_size: float = 16.0, batch=None,
                 y_from_bottom: float = 30.0) -> None:
        self.label = pyglet.text.Label(
            text='', x=width_center(), y=from_bottom_edge(y_from_bottom),
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
