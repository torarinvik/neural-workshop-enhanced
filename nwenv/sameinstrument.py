# -*- coding: utf-8 -*-
"""The stepped agent boundary for Same Instrument.

Three ports: 0 says the same and 1 different; with three notes, port
k says note k was the odd one. The notes reach the agent only as
sound.

Clocked: the sounds play and the time runs whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SameInstrumentEnv(TaskEnv):
    """Deterministic, stepped view of one Same Instrument run."""

    task_class = ('neural_workshop.ui.sameinstrument', 'SameInstrument')
    ports = 3
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_same_instrument_env(seed: int = 0,
                               shm_name: Optional[str] = None) -> SameInstrumentEnv:
    """A production environment: the task's own defaults."""
    return SameInstrumentEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_same_instrument_outcome = SameInstrumentEnv.verifier()

__all__ = ['SameInstrumentEnv', 'make_same_instrument_env',
           'verify_same_instrument_outcome']
