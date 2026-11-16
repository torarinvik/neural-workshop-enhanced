# -*- coding: utf-8 -*-
"""The stepped agent boundary for The Cipher Abyss.

Thirty-seven ports. Ports 0-11 move the drawn pointer: up, down, left, right, each by a
long, a medium or a short step (80, 20 and 5 units of a 1000 by 640
screen). Port 12 presses its button and port 13 lets it go: both in one
place is a click, with moves between them a drag. Ports 14-21 add symbols 0-7 to the input,
22 takes the last one out, 23 runs the input (or, in the test, gives it
as the answer) and 24 starts the test.

The hypothesis board is reached through ports too, so an agent can write
down a rule and test it against its notebook just as a person does:
25 and 26 move down and up the block menu (only blocks that fit the
next slot are offered), 27 adds the chosen block, 28 takes the last one
off, 29 checks the hypothesis against every row of the notebook, and 30
submits it as the answer (from rung 10: judged by behaving alike on a
large hidden probe set, longer rows included). 31 turns "predict before
you run" on or off: with it on, the first row typed is the input and the
second the predicted output. 32 and 33 scroll the notebook, 34 marks
its last row, 35 shows or hides the numbers on symbols and 36 sorts the
notebook by time or by input. The agent hears each symbol it
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
    ports = 37
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
