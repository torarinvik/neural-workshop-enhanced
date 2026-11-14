# -*- coding: utf-8 -*-
"""The stepped agent boundary for Camera.

Thirty-one ports. Ten moves -- forward, back, left, right, turn left,
turn right, look up, look down, rise, sink -- each at three sizes: a
whole step (a metre, fifteen degrees, half a metre up), an eighth of
one, and the finest step, which is half the rung's own tolerance. The
last port says "this is it" and is the only one that settles a trial.

The finest step follows the rung so that no rung is out of reach by
construction: a ladder whose top could not be reached by any sequence
of ports would be measuring the port table. What makes the top rungs
hard is knowing where to stop, which no port can do for the learner.

Turn-based: the field holds still until a port is pressed, so a run can
carry the think clock, and on this task that is a real choice -- study
the photograph longer, or walk sooner.

Green means the eye was within the rung's distance and the line of
sight within its angle when the learner said so.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

#: Ten moves at three sizes each, then the port that submits.
ACTIONS = tuple((move, size) for move in range(10) for size in range(3))
SUBMIT = len(ACTIONS)


class CameraEnv(TaskEnv):
    """Deterministic, stepped view of one Camera run."""

    task_class = ('neural_workshop.ui.camera', 'CameraTask')
    ports = SUBMIT + 1
    clocked = False
    action = 'press'
    action_table = ACTIONS + ((10, 0),)
    open_phase = ('searching',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_camera_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> CameraEnv:
    """A production environment: the task's own defaults."""
    return CameraEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_camera_outcome = CameraEnv.verifier()

__all__ = ['ACTIONS', 'CameraEnv', 'SUBMIT', 'make_camera_env',
           'verify_camera_outcome']
