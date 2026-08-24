# -*- coding: utf-8 -*-
"""The stepped agent boundary for N-in-a-row.

One port names one cell in the largest supported board.  Smaller boards
leave their spare ports silent, exactly as Sudoku leaves its unused digits
silent on a smaller grid.  A trial settles when the chosen cell is judged;
the public scalar is still read from the on-screen verdict label.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from neural_workshop.ninarow import MAX_CELLS

from .taskenv import TaskEnv


class NInARowEnv(TaskEnv):
    """Deterministic, stepped view of one N-in-a-row position."""

    task_class = ('neural_workshop.ui.ninarow', 'NInARow')
    ports = MAX_CELLS
    #: The board waits for a cell; no wall-clock movement is involved.
    clocked = False
    action = 'choose'
    open_phase = ('asking',)
    settled_phase = ('judged',)
    knobs = {
        'rung': 'start_rung',
        'trials': 'total_trials',
        'grid': 'grid_size',
        'pellets': 'pellets',
        'adaptive': 'adaptive',
    }


def make_ninarow_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> NInARowEnv:
    """A production environment using the task's own defaults."""
    return NInARowEnv(seed=seed, shm_name=shm_name)


#: Generated from the inherited deriver so the verifier cannot drift from
#: the standard pixel-bound outcome contract.
verify_ninarow_outcome = NInARowEnv.verifier()

__all__ = ['NInARowEnv', 'make_ninarow_env', 'verify_ninarow_outcome']
