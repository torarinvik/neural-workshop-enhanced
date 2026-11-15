# -*- coding: utf-8 -*-
"""The stepped agent boundary for Gunslinger.

Fifteen ports. Ports 0-11 move the gun's sight: up, down, left, right,
each by a long, a medium or a short step (80, 20 and 5 units of a 1000
by 640 screen). Port 12 pulls the trigger and port 13 lets it go; port
14 cocks the hammer. The gun is in the hand from the start, and aiming
and cocking are free, but a pull of the trigger before the other man
has gone for his gun loses. The agent hears his hand go to his gun, his
feints, the shots, and from the higher rungs wind, bells and crows.

Clocked: he draws when he draws and fires when he is ready, whether or not the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class GunslingerEnv(TaskEnv):
    """Deterministic, stepped view of one Gunslinger run."""

    task_class = ('neural_workshop.ui.gunslinger', 'Gunslinger')
    ports = 15
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_gunslinger_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> GunslingerEnv:
    """A production environment: the task's own defaults."""
    return GunslingerEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_gunslinger_outcome = GunslingerEnv.verifier()

__all__ = ['GunslingerEnv', 'make_gunslinger_env',
           'verify_gunslinger_outcome']
