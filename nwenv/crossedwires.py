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

from typing import Any, Dict, Optional

from .taskenv import TaskEnv


class CrossedWiresEnv(TaskEnv):
    """Deterministic, stepped view of one Crossed Wires run."""

    ports = 8
    clocked = False

    def __init__(self, seed: Optional[int] = None,
                 rung: Optional[int] = None,
                 rounds: Optional[int] = None,
                 grid: Optional[bool] = None,
                 **kwargs: Any) -> None:
        self._rung = rung
        self._rounds = rounds
        self._grid = grid
        self._scored_seen = False
        super().__init__(seed=seed, **kwargs)

    def build(self, seed: int, **dials: Any) -> Any:
        from neural_workshop.ui.crossedwires import CrossedWires
        return CrossedWires()

    def apply_dials(self, task: Any) -> None:
        if self._rung is not None:
            task.start_rung = int(self._rung)
        if self._rounds is not None:
            task.total_trials = int(self._rounds)
        if self._grid is not None:
            task.show_grid = bool(self._grid)

    def drive(self, task: Any, port: int) -> None:
        task.press(port)

    def trial_open(self, task: Any) -> bool:
        """Only while there is budget left to spend."""
        return getattr(task, 'phase', None) == 'playing'

    def tick(self, task: Any, dt: float) -> None:
        """Nothing moves on its own; a scored round needs dealing on.

        The wait is the same one every task on this boundary needs:
        dealing the next round clears the verdict, so going straight
        there would take the label down on the frame it went up and the
        outcome would never be derivable.
        """
        if getattr(task, 'phase', None) != 'scored':
            self._scored_seen = False
            return
        if self._scored_seen:
            self._scored_seen = False
            task._next_trial()
        else:
            self._scored_seen = True

    def dials(self) -> Dict[str, Any]:
        return {'rung': self._rung, 'rounds': self._rounds,
                'grid': self._grid}


def make_crossedwires_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> CrossedWiresEnv:
    """A production environment: the task's own defaults."""
    return CrossedWiresEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_crossedwires_outcome = CrossedWiresEnv.verifier()

__all__ = ['CrossedWiresEnv', 'make_crossedwires_env',
           'verify_crossedwires_outcome']
