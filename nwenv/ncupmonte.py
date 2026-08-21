# -*- coding: utf-8 -*-
"""The stepped agent boundary for N-Cup Monte.

Twenty ports, one to a cup, because twenty is the most cups the task
will ever put on the table. Most rounds use three to eight of them and
the rest do nothing.

The task is a continuous animation and the boundary clocks it: the cups
slide, and a learner that is not watching every frame of the slide has
no way to know where the ball went. That is the whole task, and it is
also why this one cannot be answered from a single frame — the cups are
identical once the ball is under one, so the only evidence is the
motion between frames.

**A round is watched, not played.** A port does something only in the
guess phase; the reveal and the shuffle take no actions at all. That
makes the reward here about as sparse as it gets on this boundary: one
scalar per round, and a round is several hundred ticks of shuffling.

There is no run length. The task deals rounds until it is closed, so
:meth:`finished` is never true and an episode ends when the caller
stops stepping it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class NCupMonteEnv(TaskEnv):
    """Deterministic, stepped view of an N-Cup Monte session."""

    task_class = ('neural_workshop.ui.ncupmonte', 'NCupMonte')
    #: The task's own ceiling, not a round's. On a three-cup round the
    #: other seventeen do nothing.
    ports = 20
    clocked = True
    action = 'choose_cup'
    open_phase = ('guess',)
    settled_phase = ('result',)
    #: Rounds are started rather than dealt; there is no trial counter,
    #: so the same call both opens the session and deals each round.
    start = deal = 'start_round'
    knobs = {'cups': 'start_cups', 'max_cups': 'max_cups',
             'adaptive': 'adaptive', 'swaps': 'swap_count',
             'swap_seconds': 'swap_duration',
             'reveal_seconds': 'reveal_seconds'}


def make_ncupmonte_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> NCupMonteEnv:
    """A production environment: the task's own defaults."""
    return NCupMonteEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_ncupmonte_outcome = NCupMonteEnv.verifier()

__all__ = ['NCupMonteEnv', 'make_ncupmonte_env', 'verify_ncupmonte_outcome']
