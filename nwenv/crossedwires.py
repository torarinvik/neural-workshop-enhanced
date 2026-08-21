# -*- coding: utf-8 -*-
"""The stepped agent boundary for Crossed Wires.

The task the boundary was always going to suit best, because the thing it
asks of a player is exactly the thing a port already is: press one of these
and find out what it does. The learner is handed eight opaque integers and
told nothing, which is the same position the person in front of the screen
is in — the only difference being that the person can read the label on the
key and be misled by it.

Two things follow from the task's own shape.

It is **turn-based**. Nothing on the grid moves unless a key is pressed, so
there is no clock to tick and ``clocked`` is False — the task has no
``update`` at all, and giving it one to call would be inventing a clock the
task does not have.

And the port count is fixed at eight while the rungs are not. A four-key
rung leaves four ports doing nothing, and the task refuses them itself
rather than the boundary guessing at which. That is deliberate: which ports
act is one more thing the learner has to find out by spending a press, and
on the drifting rungs the answer changes underneath it anyway.

One round pays one scalar, green only for reaching every target. The budget
is the whole difficulty — the shortest trip plus a few spare — so a round
that ran out of presses two targets short is not most of an answer, it is a
wiring the learner never worked out.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class CrossedWiresEnv(TaskEnv):
    """Deterministic, stepped view of one Crossed Wires run."""

    task_class = ('neural_workshop.ui.crossedwires', 'CrossedWires')
    ports = 8
    clocked = False
    action = 'press'
    #: Only while there is budget left to spend.
    open_phase = ('playing',)
    settled_phase = ('scored',)
    knobs = {'rung': 'start_rung', 'rounds': 'total_trials',
             'grid': 'show_grid'}


def make_crossedwires_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> CrossedWiresEnv:
    """A production environment: the task's own defaults."""
    return CrossedWiresEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_crossedwires_outcome = CrossedWiresEnv.verifier()

__all__ = ['CrossedWiresEnv', 'make_crossedwires_env',
           'verify_crossedwires_outcome']
