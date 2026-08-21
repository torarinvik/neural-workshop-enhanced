# -*- coding: utf-8 -*-
"""The stepped agent boundary for the 2D Maze.

Four ports, one to a direction, in an order the learner has to discover.
Turn-based — nothing in a maze moves unless a key is pressed — so there is
no clock to tick and ``clocked`` is False.

Worth knowing before reading a run: **walking into a wall costs nothing and
changes no pixel**. A learner that has not yet worked out which port is
which will spend actions that leave the frame byte-identical, and that is
the task being honest rather than the boundary losing them. It also means
the frame-change rate on this task understates how much is happening, in a
way it does not on a task that animates.

Restart is deliberately not a port. ``R`` sends the walker back to the start
with the step count, which is a way of un-spending a bad line rather than a
move in the maze; a learner given it would be handed an undo for the one
thing being scored.

A maze pays one scalar when it is walked out of, green only for a walk at or
under the exact minimum. The solver is exact at every size the ladder
offers, so unlike Sokoban next door this is a task where "perfect" means it
rather than "no worse than the best anyone has proved".

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .taskenv import TaskEnv

#: What the four ports do, in an order the learner has to discover.
STEPS = ((0, -1), (0, 1), (-1, 0), (1, 0))


class MazeEnv(TaskEnv):
    """Deterministic, stepped view of one Maze run."""

    ports = 4
    clocked = False

    def __init__(self, seed: Optional[int] = None,
                 rung: Optional[int] = None,
                 trials: Optional[int] = None,
                 trail: Optional[bool] = None,
                 **kwargs: Any) -> None:
        self._rung = rung
        self._trials = trials
        self._trail = trail
        self._solved_seen = False
        super().__init__(seed=seed, **kwargs)

    def build(self, seed: int, **dials: Any) -> Any:
        from neural_workshop.ui.maze import MazeTask
        return MazeTask()

    def apply_dials(self, task: Any) -> None:
        if self._rung is not None:
            task.start_rung = int(self._rung)
        if self._trials is not None:
            task.total_trials = int(self._trials)
        if self._trail is not None:
            task.show_trail = bool(self._trail)

    def drive(self, task: Any, port: int) -> None:
        task.step(*STEPS[port])

    def trial_open(self, task: Any) -> bool:
        """Only while a maze is being walked."""
        return getattr(task, 'phase', None) == 'walking'

    def tick(self, task: Any, dt: float) -> None:
        """Nothing moves on its own; a solved maze needs dealing on.

        The wait before dealing is the one every task on this boundary
        needs: dealing clears the verdict, so going straight there
        would take the label down on the frame it went up and the
        outcome would never be derivable.
        """
        if getattr(task, 'phase', None) != 'solved':
            self._solved_seen = False
            return
        if self._solved_seen:
            self._solved_seen = False
            task._next_trial()
        else:
            self._solved_seen = True

    def dials(self) -> Dict[str, Any]:
        return {'rung': self._rung, 'trials': self._trials,
                'trail': self._trail}


def make_maze_env(seed: int = 0,
                  shm_name: Optional[str] = None) -> MazeEnv:
    """A production environment: the task's own defaults."""
    return MazeEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_maze_outcome = MazeEnv.verifier()

__all__ = ['MazeEnv', 'make_maze_env', 'verify_maze_outcome']
