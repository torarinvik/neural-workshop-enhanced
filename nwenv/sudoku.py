# -*- coding: utf-8 -*-
"""The stepped agent boundary for Sudoku.

Twenty-two ports: four to move the cursor, sixteen to write a digit, one
to rub out, one to switch between writing and pencilling. Sixteen
because the top of the ladder is a sixteen-by-sixteen grid; on a nine
the last seven digits do nothing, and on a four the last twelve.

**The cursor is the interesting part.** Every other task on this
boundary names its target directly — a card, a cup, a peg. Here the
learner has a position it has to steer, and a write goes wherever the
cursor happens to be, so an action's meaning depends on a piece of state
that is only three pixels of highlight on screen. Getting a digit into
the right cell is a small navigation problem sitting on top of the
deduction.

Green means solved **without ever writing a digit that clashed with one
already on the board**. Finishing is not the measure: the phase only
settles once the grid is full and correct, so every solved puzzle
finished. What separates them is whether the learner deduced or tried.

Pencil marks cost actions and pay nothing, which is right: they are the
learner's own notes, and a task that paid for taking notes would be paying
for something other than the solution.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

#: Four ways to steer, then the digits, then rub out and pencil.
STEPS = ((0, -1), (0, 1), (-1, 0), (1, 0))
DIGITS = 16
ERASE, PENCIL = len(STEPS) + DIGITS, len(STEPS) + DIGITS + 1


class SudokuEnv(TaskEnv):
    """Deterministic, stepped view of one Sudoku run."""

    task_class = ('neural_workshop.ui.sudoku', 'Sudoku')
    ports = PENCIL + 1
    #: Nothing moves on its own; the grid waits as long as it is left.
    clocked = False
    open_phase = ('solving',)
    settled_phase = ('solved',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'show_clashes': 'show_clashes', 'adaptive': 'adaptive'}

    def drive(self, task: Any, port: int) -> None:
        """Four methods, so this one is not declared.

        A digit above the grid's size is refused by the task, as is a
        write into a given. Both are the task's own rules and both
        leave the frame unchanged, so a learner working out what the
        ports do will spend actions that show it nothing — the same
        honest silence walking into a wall gets in the Maze.
        """
        if port < len(STEPS):
            task.move(*STEPS[port])
        elif port < len(STEPS) + DIGITS:
            task.write(port - len(STEPS) + 1)
        elif port == ERASE:
            task.erase()
        else:
            task.toggle_pencil()


def make_sudoku_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> SudokuEnv:
    """A production environment: the task's own defaults."""
    return SudokuEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_sudoku_outcome = SudokuEnv.verifier()

__all__ = ['SudokuEnv', 'make_sudoku_env', 'verify_sudoku_outcome']
