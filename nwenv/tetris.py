# -*- coding: utf-8 -*-
"""The stepped agent boundary for Freeform Tetris.

Eleven ports, and they are not all of one kind. Five steer the piece
that is falling — left, right, spin one way, spin the other, drop —
and six arm a slot of the tray, which is the choice a person makes
with the mouse. A tray narrower than six leaves the rest doing
nothing, which is the task refusing a port rather than the wrapper
inventing one.

**The spin ports step where the keyboard holds.** A person winds the
piece round by holding a key and a stepped boundary has no holding, so
one press is a fifteenth of a turn. The whole circle is twenty-four
presses and every quarter turn falls on one exactly, so nothing a
person can reach is out of a learner's reach — which is the rule this
boundary keeps everywhere, that the two are playing the same game.

**A trial is one placement.** The piece lands, the verdict says
whether it buried anything, and the next piece is dealt.

The floor is unusually high and it is worth knowing why before
reading anything off a curve drawn on it. Measured over 900 steps of
uniform random play: 25 outcomes at the first rung, 12 green and 13
red. That is not a defect and it is not the task being easy — it is
the first rung cutting rectangles, and a rectangle that falls on its
own onto level ground lands flush whichever column it is over. The
same sweep at the fourth rung reads 8 green to 19 red, and at the
seventh 3 green to 15. So the floor is a property of the rung rather
than of the boundary, and a learner that improved at the first rung
has shown nothing until it holds at the seventh.

What the task can promise, which is rare on this boundary, is that
the green was always *available*: the queue is re-checked after every
placement and any piece left with nowhere gapless to go is cut again,
so no trial here is one that could not have been won.

**The ladder is shape, not speed.** Every rung falls at whatever
gravity the run was built with, so a run that climbs is not a run that
sped up, and a learning curve drawn across the rungs is about packing
throughout.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class FreeformTetrisEnv(TaskEnv):
    """Deterministic, stepped view of one Freeform Tetris run."""

    task_class = ('neural_workshop.ui.tetris', 'FreeformTetris')
    #: Five controls and six tray slots. The task's ceiling, not a
    #: run's: a run with a tray of three leaves three ports idle.
    ports = 11
    clocked = True
    action = 'press'
    open_phase = ('falling',)
    #: One placement is one trial. The task pauses on the verdict for
    #: half a second of its own clock, which under this boundary is the
    #: driver's, and the driver waits a published frame in this phase
    #: before dealing — so the outcome is read off a frame the learner
    #: was actually handed.
    settled_phase = ('landed',)
    deal = '_next_piece'
    knobs = {'rung': 'start_rung', 'pieces': 'total_pieces',
             'columns': 'cols', 'rows': 'rows', 'queue': 'queue_size',
             'gravity': 'fall_rate', 'spin': 'spin_rate',
             'adaptive': 'adaptive', 'ghost': 'show_ghost'}


def make_tetris_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> FreeformTetrisEnv:
    """A production environment: the task's own defaults."""
    return FreeformTetrisEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_tetris_outcome = FreeformTetrisEnv.verifier()

__all__ = ['FreeformTetrisEnv', 'make_tetris_env', 'verify_tetris_outcome']
