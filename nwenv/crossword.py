# -*- coding: utf-8 -*-
"""The stepped agent boundary for the Crossword.

Thirty-two ports: four to steer the cursor, twenty-six to write a
letter, one to rub out, one to turn the cursor between across and
down. The same cursor problem Sudoku has — a write goes wherever the
cursor happens to be, so an action's meaning depends on a piece of
state that is a few pixels of highlight — with one more thing on top
of it. The clue on the screen is the clue for the entry the cursor is
*facing*, so turning the cursor changes what is being asked without
moving anything, and a learner that never turns sees half the clues in
the grid.

Green means solved **without ever writing a letter that was not the
answer's**. Finishing is not the measure: the phase only settles once
the grid is full and right, so every solved grid finished. What
separates them is whether the learner read the clue or ran the
alphabet.

**This one needs the words fetched.** With no clue file on disk the
task refuses to deal and says so on its own screen, and an environment
built on it will step through a run that never opens a trial. That is
a real state and not a crash, and it is the same shape as a memory
game with an empty photograph library.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

#: Four ways to steer, then the alphabet, then rub out and turn.
STEPS = ((0, -1), (0, 1), (-1, 0), (1, 0))
LETTERS = 'abcdefghijklmnopqrstuvwxyz'
ERASE, TURN = len(STEPS) + len(LETTERS), len(STEPS) + len(LETTERS) + 1


class CrosswordEnv(TaskEnv):
    """Deterministic, stepped view of one Crossword run."""

    task_class = ('neural_workshop.ui.crossword', 'Crossword')
    ports = TURN + 1
    #: Nothing moves on its own; the grid waits as long as it is left.
    clocked = False
    open_phase = ('solving',)
    settled_phase = ('solved',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'show_mistakes': 'show_mistakes', 'adaptive': 'adaptive'}

    def drive(self, task: Any, port: int) -> None:
        """Four methods, so this one is not declared.

        A write into a given, or into a block, is refused by the task
        and leaves the frame unchanged — the same honest silence
        walking into a wall gets in the Maze.
        """
        if port < len(STEPS):
            task.move(*STEPS[port])
        elif port < len(STEPS) + len(LETTERS):
            task.write(LETTERS[port - len(STEPS)])
        elif port == ERASE:
            task.erase()
        else:
            task.turn()


def make_crossword_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> CrosswordEnv:
    """A production environment: the task's own defaults."""
    return CrosswordEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_crossword_outcome = CrosswordEnv.verifier()

__all__ = ['CrosswordEnv', 'make_crossword_env', 'verify_crossword_outcome']
