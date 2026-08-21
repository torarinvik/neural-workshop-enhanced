# -*- coding: utf-8 -*-
"""The stepped agent boundary for Reflex.

Twelve ports, one to a live target, because twelve is the most the task
will have on screen at once. With the usual three, nine do nothing.

**A target is a trial, and it can end without the learner acting.** The
target shrinks from the moment it appears and is gone when it reaches
nothing, so a trial that is never answered resolves anyway and resolves
red — the same shape Lookout has, and for the same reason: a task about
speed cannot let waiting be free.

That is what the trial window is here. It is open while a target is
live and no verdict is up; it closes on the verdict, whichever way the
verdict went; and the next spawn takes the label down and opens the
next one. So the reward is dense by the standards of this boundary —
one scalar per target rather than one per run — and it is dense in both
directions.

The port names a target rather than a place, which drops the aiming the
mouse version has. What is left is the timing, which is what the task is
named for: the ladder tightens the lifetime on every hit, so a learner
that keeps up gets less and less time to notice.

The targets come from an image library, and a run needs one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv


class ReflexEnv(TaskEnv):
    """Deterministic, stepped view of one Reflex run."""

    task_class = ('neural_workshop.ui.reflex', 'Reflex')
    #: The task's own ceiling for targets on screen at once.
    ports = 12
    clocked = True
    knobs = {'targets': 'total_targets', 'lifetime': 'base_lifetime',
             'spawn_gap': 'spawn_gap', 'max_active': 'max_active',
             'size': 'start_size', 'adaptive': 'adaptive'}

    def drive(self, task: Any, port: int) -> None:
        """Strike one live target.

        Not declared, because the task hits a *target* rather than an
        index — targets come and go, so an index is only a target for
        as long as that one is on screen, which is the whole point.
        """
        if port < len(task.targets):
            task.hit(task.targets[port])

    def trial_open(self, task: Any) -> bool:
        """A live target with no verdict standing over it.

        Not declared as a phase, because this task has no phase for it:
        targets overlap and the run never pauses. The window is the
        gap between a spawn and a resolution, and a resolution can
        arrive from the clock rather than from a port.
        """
        return (getattr(task, 'phase', None) == 'running'
                and bool(task.targets)
                and getattr(task, 'verdict_shown', None) is None)


def make_reflex_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> ReflexEnv:
    """A production environment: the task's own defaults."""
    return ReflexEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_reflex_outcome = ReflexEnv.verifier()

__all__ = ['ReflexEnv', 'make_reflex_env', 'verify_reflex_outcome']
