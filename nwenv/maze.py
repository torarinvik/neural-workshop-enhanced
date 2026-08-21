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

from typing import Optional

from .taskenv import TaskEnv


class MazeEnv(TaskEnv):
    """Deterministic, stepped view of one Maze run."""

    task_class = ('neural_workshop.ui.maze', 'MazeTask')
    ports = 4
    clocked = False
    action = 'step'
    #: What the four ports do, in an order the learner has to discover.
    action_table = ((0, -1), (0, 1), (-1, 0), (1, 0))
    open_phase = ('walking',)
    settled_phase = ('solved',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'trail': 'show_trail'}


def make_maze_env(seed: int = 0,
                  shm_name: Optional[str] = None) -> MazeEnv:
    """A production environment: the task's own defaults."""
    return MazeEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_maze_outcome = MazeEnv.verifier()

__all__ = ['MazeEnv', 'make_maze_env', 'verify_maze_outcome']
