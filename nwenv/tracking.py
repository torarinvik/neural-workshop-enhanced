# -*- coding: utf-8 -*-
"""The stepped agent boundary for Moving Targets.

Thirty ports, one to a ball, because thirty is the most balls the task
will ever put on screen. A round with eight leaves twenty-two doing
nothing.

The task is multiple-object tracking: some of the balls are coloured for
a couple of seconds, then everything goes the same colour and they all
bounce around for a while, and at the end the learner picks out the ones
that were coloured. **Nothing in any single frame says which balls those
were.** The identity of a ball is carried only by its path, so this is
the clearest case on the boundary of a task a frame-at-a-time reader
cannot do at all — the same property Out of Sight was built to measure,
here without the occlusion.

A pick is a toggle, and the round scores itself on the pick that brings
the count up to the number asked for. So a learner cannot pick
everything: picking a wrong ball early spends one of the picks it has.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv


class MovingTargetsEnv(TaskEnv):
    """Deterministic, stepped view of one Moving Targets run."""

    task_class = ('neural_workshop.ui.tracking', 'MovingTargets')
    #: The task's own ceiling. A round showing eight balls leaves the
    #: rest of these ports doing nothing.
    ports = 30
    clocked = True
    open_phase = ('picking',)
    knobs = {'balls': 'ball_count', 'targets': 'start_targets',
             'seconds': 'seconds', 'speed': 'speed',
             'rounds': 'total_rounds', 'adaptive': 'adaptive'}

    def drive(self, task: Any, port: int) -> None:
        """Toggle the pick on one ball.

        Not declared, because the task picks a *ball* rather than an
        index — it has to, since the balls are the things that move and
        a position is only a ball for one frame.
        """
        if port < len(task.balls):
            task.pick(task.balls[port])


def make_tracking_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> MovingTargetsEnv:
    """A production environment: the task's own defaults."""
    return MovingTargetsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_tracking_outcome = MovingTargetsEnv.verifier()

__all__ = ['MovingTargetsEnv', 'make_tracking_env', 'verify_tracking_outcome']
