# -*- coding: utf-8 -*-
"""The stepped agent boundary for Tower of Hanoi.

Three ports, one to a peg, and **a move is two ports**: the first names
the peg to lift from, the second the peg to set down on. Naming the same
peg twice puts the disk back.

That two-step shape is the interesting part of this wrapper. Everywhere
else on the boundary one port is one move; here a port is half of one,
and the half that matters — which peg to lift from — is paid nothing on
its own. It is also the only task here where a port's meaning depends on
what the last port was, so a learner reading each frame independently
cannot tell a lift from a set-down.

An illegal set-down is refused rather than scored, which is the task's
own rule: the size rule is furniture, and the thing being measured is
the plan, not whether the learner has memorised which disk is on top.

Green means the exact minimum, ``2**n - 1``. This is the one task in the
workshop where "perfect" is a closed form rather than a search or a
proved bound.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class HanoiEnv(TaskEnv):
    """Deterministic, stepped view of one Tower of Hanoi run."""

    task_class = ('neural_workshop.ui.hanoi', 'TowerOfHanoi')
    ports = 3
    #: Nothing moves on its own. The task's feedback window runs on a
    #: clock, but under this boundary the settled phase is dealt on
    #: rather than waited out.
    clocked = False
    action = '_pick'
    open_phase = ('solving',)
    settled_phase = ('solved',)
    deal = '_next_round'
    knobs = {'disks': 'start_disks', 'rounds': 'total_rounds',
             'adaptive': 'adaptive'}


def make_hanoi_env(seed: int = 0,
                   shm_name: Optional[str] = None) -> HanoiEnv:
    """A production environment: the task's own defaults."""
    return HanoiEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_hanoi_outcome = HanoiEnv.verifier()

__all__ = ['HanoiEnv', 'make_hanoi_env', 'verify_hanoi_outcome']
