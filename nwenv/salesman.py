# -*- coding: utf-8 -*-
"""The stepped agent boundary for Traveling Salesman.

Eighteen ports, one to a city, because eighteen is the most the task
will scatter. A round with nine leaves nine doing nothing.

Picking a city extends the tour; picking the one just picked takes it
back. So the learner builds a permutation one action at a time, and the
round scores itself the moment the last city goes in — there is no
submit, and nothing to reconsider once the tour is complete. A plan has
to be made before it is entered, not repaired while it is.

Green means **the shortest route there is**, found exactly rather than
approximated. Eighteen cities is inside what an exact solver can do, so
unlike Sokoban next door this task's "perfect" is the real optimum and
not a proved bound on one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class SalesmanEnv(TaskEnv):
    """Deterministic, stepped view of one Traveling Salesman run."""

    task_class = ('neural_workshop.ui.salesman', 'TravelingSalesman')
    #: The task's own ceiling: eighteen cities.
    ports = 18
    clocked = False
    action = '_pick'
    open_phase = ('touring',)
    settled_phase = ('toured',)
    deal = '_next_round'
    knobs = {'cities': 'start_cities', 'rounds': 'total_rounds',
             'adaptive': 'adaptive'}


def make_salesman_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> SalesmanEnv:
    """A production environment: the task's own defaults."""
    return SalesmanEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_salesman_outcome = SalesmanEnv.verifier()

__all__ = ['SalesmanEnv', 'make_salesman_env', 'verify_salesman_outcome']
