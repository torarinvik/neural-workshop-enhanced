# -*- coding: utf-8 -*-
"""The stepped agent boundary for the held-in-mind tasks: the answer
is how the frame showing stands to one no longer showing.

Clocked: the frames go by, and the time to answer runs, whether or not
the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .framed import SlowFrames
from .taskenv import TaskEnv


class _Rung(SlowFrames, TaskEnv):
    """What every wrapper here shares. May be driven a shown frame a
    step, as an opt-in (see :class:`nwenv.framed.SlowFrames`)."""

    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


class ChangedTileEnv(_Rung):
    """Changed Tile: Four ports, one a tile, in reading order.
    Presses before the question is put are ignored."""

    task_class = ('neural_workshop.ui.inmind', 'ChangedTile')
    ports = 4


class SwappedBoxesEnv(_Rung):
    """Swapped Boxes: Four ports, one a box, in reading order.
    Presses before the question is put are ignored."""

    task_class = ('neural_workshop.ui.inmind', 'SwappedBoxes')
    ports = 4


verify_changed_tile_outcome = ChangedTileEnv.verifier()
verify_swapped_boxes_outcome = SwappedBoxesEnv.verifier()

__all__ = ['ChangedTileEnv', 'SwappedBoxesEnv']
