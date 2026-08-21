# -*- coding: utf-8 -*-
"""The stepped agent boundary for Pursuit.

Four ports, one to a direction, each moving the cursor one step.

**This is the only task here whose action does not name a target.**
Everywhere else a port picks a thing — a card, a cup, a peg, an answer.
Here a port moves a point, and whether that point is on the quarry is
decided by where the quarry got to in the same frame. There is nothing
to identify and nothing to remember; there is only a control loop,
running at the frame rate, against something built to break prediction.

The task was a mouse task and now steers by steps as well, on the arrow
keys — a real key binding rather than a hook the boundary alone can
reach, because inventing an interface only the agent has would make the
two versions different tasks. A step is sized against the quarry's
default pace: about what it covers in a frame, so nudging every frame
keeps up in a straight line and the swerves have to be anticipated.

The score is a share of the round spent on target, which makes this the
densest signal on the boundary — but it is *reported* once a round, so
what the learner is paid is still one scalar. Green at seventy percent,
the same share the ladder speeds the quarry up at, so staying green
means it keeps getting faster until it does not.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class PursuitEnv(TaskEnv):
    """Deterministic, stepped view of one Pursuit run."""

    task_class = ('neural_workshop.ui.pursuit', 'Pursuit')
    ports = 4
    clocked = True
    action = 'nudge'
    #: Up, down, left, right — in an order the learner has to discover,
    #: which on this task it can discover in one step, because a nudge
    #: moves something visible immediately.
    action_table = ((0.0, 1.0), (0.0, -1.0), (-1.0, 0.0), (1.0, 0.0))
    open_phase = ('chasing',)
    #: Not declared as settled: the round's feedback window closes on
    #: the task's own clock, which under this boundary is the driver's.
    knobs = {'speed': 'speed', 'surge': 'surge_depth',
             'turn_seconds': 'turn_gap', 'size': 'base_radius',
             'wobble': 'wobble', 'morph_seconds': 'morph_gap',
             'seconds': 'seconds', 'rounds': 'total_rounds',
             'adaptive': 'adaptive'}


def make_pursuit_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> PursuitEnv:
    """A production environment: the task's own defaults."""
    return PursuitEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_pursuit_outcome = PursuitEnv.verifier()

__all__ = ['PursuitEnv', 'make_pursuit_env', 'verify_pursuit_outcome']
