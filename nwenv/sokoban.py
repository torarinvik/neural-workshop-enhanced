# -*- coding: utf-8 -*-
"""The stepped agent boundary for Sokoban.

Four ports, one to a direction. Turn-based, so no clock ticks.

The undo key is deliberately not a port, and the reason is the task rather
than the boundary. Sokoban has an undo because a push is irreversible and
seeing that coming is the whole game; handing a learner a way back out of an
irreversible move would remove the thing being measured. A learner that
shoves a box into a corner has to live in the level it just made — which is
exactly what the person at the keyboard is declining to do when they press
``U``.

Restart is out for the same reason as in the Maze next door: it un-spends a
line rather than playing one.

A level pays one scalar when it is solved, green only for a solve at or
under par. Where a level's true minimum is not certified the par is a
*proved lower bound*, so at or under it still means provably optimal — the
screen says "provably at least" in that case and the scalar means the same
thing either way.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

#: What the four ports do, in an order the learner has to discover.
STEPS = ((0, -1), (0, 1), (-1, 0), (1, 0))


class SokobanEnv(TaskEnv):
    """Deterministic, stepped view of one Sokoban run."""

    task_class = ('neural_workshop.ui.sokoban', 'SokobanTask')
    ports = 4
    clocked = False
    action = 'step'
    action_table = STEPS
    open_phase = ('pushing',)
    #: Solved *or lost*, and the second one matters more here than
    #: anywhere else on this boundary. A box pushed into a pocket can
    #: never come out, so a learner that shoves one there is in a
    #: position it cannot win and cannot leave — and before the task
    #: learned to say so, that was an absorbing state with no verdict in
    #: it: the episode ran to its step limit having been paid nothing
    #: since the mistake.
    settled_phase = ('solved', 'lost')
    knobs = {'rung': 'start_rung', 'trials': 'total_trials'}


def make_sokoban_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> SokobanEnv:
    """A production environment: the task's own defaults."""
    return SokobanEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_sokoban_outcome = SokobanEnv.verifier()

__all__ = ['SokobanEnv', 'make_sokoban_env', 'verify_sokoban_outcome']
