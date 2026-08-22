# -*- coding: utf-8 -*-
"""The stepped agent boundary for 3D Sokoban.

Four ports: walk on, reverse, turn left, turn right — in an order the
learner has to discover. Turn-based, so no clock ticks.

Two keys the person at the screen has are deliberately not ports, and both
refusals are the ones the flat Sokoban makes next door. **Undo** exists
because a push is irreversible and seeing that coming is the whole game;
handing a learner a way back out of an irreversible move would remove the
thing being measured. **Restart** un-spends a line rather than playing one.
A learner that shoves a box into a corner has to live in the warehouse it
just made.

What is different here is worth stating, because it changes what a run
means rather than only what it looks like. The flat game is scored in
*pushes* and the walking between them is free; this one is scored in
*steps*, turns included, because a first-person view with free turning is a
top-down view that takes a moment longer to read. So the par is its own
exact minimum over ``(boxes, cell, facing)`` — Dijkstra over the same
push-space the flat solver walks, with the walk priced into every edge —
and where that outgrows its budget the par is the search's own frontier: a
proven lower bound, so at or under it still means provably optimal. The
screen says which of the two it is holding and the scalar means the same
thing either way.

Levels settle on ``solved`` *or* ``lost``, and the second one matters more
here than anywhere else on this boundary. A box pushed into a pocket can
never come out, and from inside a corridor a learner can be several pushes
past the mistake before anything in the view looks wrong. Without a verdict
on that position the episode would run to its step limit having been paid
nothing since the error.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

#: What the four ports do, in an order the learner has to discover.
WALKS = ('ahead', 'back', 'left', 'right')


class Sokoban3DEnv(TaskEnv):
    """Deterministic, stepped view of one 3D Sokoban run."""

    task_class = ('neural_workshop.ui.sokoban3d', 'Sokoban3D')
    ports = 4
    clocked = False
    action = 'walk'
    action_table = WALKS
    open_phase = ('pushing',)
    settled_phase = ('solved', 'lost')
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'marks': 'show_marks', 'traps': 'show_traps'}


def make_sokoban3d_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> Sokoban3DEnv:
    """A production environment: the task's own defaults."""
    return Sokoban3DEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_sokoban3d_outcome = Sokoban3DEnv.verifier()

__all__ = ['Sokoban3DEnv', 'make_sokoban3d_env', 'verify_sokoban3d_outcome']
