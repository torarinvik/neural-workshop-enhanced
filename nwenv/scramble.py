# -*- coding: utf-8 -*-
"""The stepped agent boundary for Scramble.

Twenty-nine ports: twenty-six letters, a space, a rub-out and a
submit. There is no cursor — the answer is one line typed left to
right — which makes this the plainest port set in the Workshop and
also the least forgiving. Every other task can be nudged towards an
answer; here a trial is scored on one string, and a string that is
one letter wrong is a string that is wrong.

Green means the line typed is the line that was corrupted, letter for
letter once case and punctuation are taken out. Nothing partial is
paid. That is the task and not an oversight: a reconstruction that is
nearly right is a different sentence.

**Random play will never score here** and that is not a defect — the
same is true of the crossword, the sudoku and both mazes. The test in
``tests/test_env_tasks.py`` drives it with a policy that knows the
answer, through these ports, and still reads the verdict off the
frame.

**This one is not shaped, and could not honestly be.** A dense
signal needs a potential that reads only what is drawn, and the only
potential available here — how much of the answer has been typed
correctly so far — is a function of the answer, which is precisely
what is not drawn. Paying a learner for typing the right next letter
is handing it the sentence a letter at a time. So the trial pays
once, at the end, and the sparseness stands.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

LETTERS = 'abcdefghijklmnopqrstuvwxyz'
SPACE, BACK, SUBMIT = len(LETTERS), len(LETTERS) + 1, len(LETTERS) + 2


class ScrambleEnv(TaskEnv):
    """Deterministic, stepped view of one Scramble run."""

    task_class = ('neural_workshop.ui.scramble', 'Scramble')
    ports = SUBMIT + 1
    #: The line waits as long as it is left. Nothing moves on its own.
    clocked = False
    open_phase = ('reading',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'show_count': 'show_count', 'adaptive': 'adaptive'}

    def drive(self, task: Any, port: int) -> None:
        """Four methods, so this one is not declared.

        A space at the front of an empty answer, a rub-out with
        nothing to rub out, and a submit with nothing typed are all
        refused by the task and leave the frame unchanged — the same
        honest silence walking into a wall gets in the Maze.
        """
        if port < len(LETTERS):
            task.write(LETTERS[port])
        elif port == SPACE:
            task.space()
        elif port == BACK:
            task.erase()
        else:
            task.submit()


def make_scramble_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> ScrambleEnv:
    """A production environment: the task's own defaults."""
    return ScrambleEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_scramble_outcome = ScrambleEnv.verifier()

__all__ = ['ScrambleEnv', 'make_scramble_env', 'verify_scramble_outcome']
