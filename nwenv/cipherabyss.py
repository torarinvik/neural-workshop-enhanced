# -*- coding: utf-8 -*-
"""The stepped agent boundary for The Cipher Abyss.

Twenty-three ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Ports 14-19 add symbols 0-5 to the input,
20 takes the last one out, 21 runs the input (or, in the test, gives it
as the answer) and 22 starts the test. The agent hears each symbol it
types and each answer of the machine as a short tune, one note a
symbol.

Clocked: the clock runs whether or not the agent acts, but it is long: the
work is in the thinking.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class CipherAbyssEnv(TaskEnv):
    """Deterministic, stepped view of one The Cipher Abyss run."""

    task_class = ('neural_workshop.ui.cipherabyss', 'CipherAbyss')
    ports = 23
    clocked = True
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_cipher_abyss_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> CipherAbyssEnv:
    """A production environment: the task's own defaults."""
    return CipherAbyssEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_cipher_abyss_outcome = CipherAbyssEnv.verifier()

__all__ = ['CipherAbyssEnv', 'make_cipher_abyss_env',
           'verify_cipher_abyss_outcome']
