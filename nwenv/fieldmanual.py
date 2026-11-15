# -*- coding: utf-8 -*-
"""The stepped agent boundary for Field Manual.

Twenty-five ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Ports 14-23 type the
digits 0-9. Port 24 is Shift, which counts as held for a quarter of a
second after it is sent, so a Shift then a press then a release is a
shifted click. Dragging anywhere but on a part turns the machine;
dragging a dial sideways turns it; dragging a slider's handle moves it.
The agent hears every click, tick, tock, tone, hum and beep.

Clocked: the clock runs, beeps sound and the machine may turn whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class FieldManualEnv(TaskEnv):
    """Deterministic, stepped view of one Field Manual run."""

    task_class = ('neural_workshop.ui.fieldmanual', 'FieldManual')
    ports = 25
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_field_manual_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> FieldManualEnv:
    """A production environment: the task's own defaults."""
    return FieldManualEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_field_manual_outcome = FieldManualEnv.verifier()

__all__ = ['FieldManualEnv', 'make_field_manual_env',
           'verify_field_manual_outcome']
