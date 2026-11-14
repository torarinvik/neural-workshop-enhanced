# -*- coding: utf-8 -*-
"""The stepped agent boundary for Errands.

Fifteen ports, Browser's: ports 0-11 move the drawn pointer (up, down,
left, right, each by 80, 20 or 5 units of a 1000 by 640 screen), port 12
clicks, ports 13 and 14 scroll the shop. Every click counts against par;
moving and scrolling are free.

Green means that when Done was pressed exactly what the mail asked for
had been bought, each on its own order, every order had one claim with
its number, total and category, nothing else was claimed -- and the
clicks came in at or under par.

Turn-based, so it takes the think clock.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

CLICK, SCROLL_UP, SCROLL_DOWN = 12, 13, 14


class ErrandsEnv(TaskEnv):
    """Deterministic, stepped view of one Errands run."""

    task_class = ('neural_workshop.ui.errands', 'Errands')
    ports = 15
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_errands_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> ErrandsEnv:
    """A production environment: the task's own defaults."""
    return ErrandsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_errands_outcome = ErrandsEnv.verifier()

__all__ = ['CLICK', 'ErrandsEnv', 'SCROLL_DOWN', 'SCROLL_UP',
           'make_errands_env', 'verify_errands_outcome']
