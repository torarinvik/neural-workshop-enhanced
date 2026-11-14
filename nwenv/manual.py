# -*- coding: utf-8 -*-
"""The stepped agent boundary for Manual.

Twenty-one ports, and they name places on the panel rather than
controls: ports 0-5 flip the switches in the order they are drawn,
ports 6-13 turn the knobs a step (two to a knob, down then up), ports
14-19 press the buttons, port 20 is Finish. From rung 17 the labels are
shuffled along each row, so which switch a port flips has to be read
off the screen. A port for a place the panel does not have does nothing.

Green means every control stood where following the written procedure
leaves it when Finish was pressed. There is no par.

Turn-based, so it takes the think clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

KNOB, BUTTON, FINISH = 6, 14, 20


class ManualEnv(TaskEnv):
    """Deterministic, stepped view of one Manual run."""

    task_class = ('neural_workshop.ui.manual', 'Manual')
    ports = 21
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_manual_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> ManualEnv:
    """A production environment: the task's own defaults."""
    return ManualEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_manual_outcome = ManualEnv.verifier()

__all__ = ['BUTTON', 'FINISH', 'KNOB', 'ManualEnv', 'make_manual_env',
           'verify_manual_outcome']
