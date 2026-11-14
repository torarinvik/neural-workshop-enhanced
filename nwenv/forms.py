# -*- coding: utf-8 -*-
"""The stepped agent boundary for Forms.

Forty-six ports, one per key: a to z, 0 to 9, space, @ . - /, then
Backspace, Tab, Enter, Up and Down. Every one costs a key. This is the
keyboard half of operating a computer, as Desktop is the pointer half:
what a key does depends on the field in focus -- a letter types into a
text box, filters a list, or does nothing to a radio button.

Green means every value was right when the last page was sent and keys
plus penalties for pages sent back came to no more than par: the keys a
reference typist pressed on the identical form, with room below rung
twenty and none from it.

Turn-based, so it takes the think clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class FormsEnv(TaskEnv):
    """Deterministic, stepped view of one Forms run."""

    task_class = ('neural_workshop.ui.forms', 'Forms')
    ports = 46
    clocked = False
    action = 'steer'
    open_phase = ('filling',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_forms_env(seed: int = 0,
                   shm_name: Optional[str] = None) -> FormsEnv:
    """A production environment: the task's own defaults."""
    return FormsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_forms_outcome = FormsEnv.verifier()

__all__ = ['FormsEnv', 'make_forms_env', 'verify_forms_outcome']
