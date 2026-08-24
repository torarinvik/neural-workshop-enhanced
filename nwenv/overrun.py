# -*- coding: utf-8 -*-
"""The stepped agent boundary for Overrun.

Twenty-seven ports: twenty-six letters and a rub-out. There is no
submit and no space — a word clears itself the moment the letters under
it match, and the gaps between words are handed back with the word
before them — so this is the smallest port set of the three word games
and the only one where the task is still moving between actions.

**A trial is one wave, which is one sentence.** Green means the whole
line was typed away before its end reached the margin; red means it
was not. Both are also a life, and a run ends when the lives do or when
the waves do, whichever comes first.

**Random play scores nothing here, and it is worth knowing why it
nearly did.** The first version of the task ignored a wrong key, so a
correct prefix could only ever grow — and at sixty ports a second a
uniform walk lands 2.3 characters a second that way. Played out in
``tests/bench_overrun.py`` rather than left as arithmetic, that rule
gives a walk every wave to the fifth rung and one in eight as high as
the tenth: two thirds of the ladder, cleared by mashing. With a
wrong letter staying
where it was put, a wave is cleared only by a buffer that matches the
word exactly, and no walk types a sentence — so the floor is zero
greens at every rung, the same floor Scramble and the crossword have,
and the green that means anything is in ``tests/test_env_tasks.py``
under a policy that can read the line.

The red is not zero, and that is the free signal a learner gets here
that it does not get in Scramble: a wave ends on its own clock whether
or not anything was typed, so the cost of not keeping up arrives
without having to be asked for. Measured over 900 steps of uniform
random play, three seeds apiece: one red at the fourth rung, one at
the eighth, three at the twelfth, and none at all at the first — where
a wave lasts nineteen seconds, which is longer than the budget. The
difference across the ladder is entirely the clock; the ports are the
same at every rung.

**Shaped densely, and it is a haul rather than a potential.** With
``coach`` on, a letter that lands pays the green a cleared wave would
have been and a letter that misses pays the red, which is the wave's
own outcome taken apart the way Cookie Thief's round is. A rub-out
pays nothing: one that paid would make typing a wrong letter worth
doing for the credit of taking it back. It is gated the usual way —
:attr:`dense_only` turns ``coach`` off in any build that will not pay
per action — because the sparse path reads the first verdict it finds
as the trial's own, and a per-key label a few presses into a wave
would score the wave.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .taskenv import TaskEnv

LETTERS = 'abcdefghijklmnopqrstuvwxyz'
BACK = len(LETTERS)


class OverrunEnv(TaskEnv):
    """Deterministic, stepped view of one Overrun run."""

    task_class = ('neural_workshop.ui.overrun', 'Overrun')
    ports = BACK + 1
    #: The line moves whether or not anyone touches it. That is the task.
    clocked = True
    open_phase = ('typing',)
    #: One wave is one trial. The task holds the verdict for a moment of
    #: its own clock, which under this boundary is the driver's, and the
    #: driver waits a published frame here before dealing — so the
    #: outcome is read off a frame the learner was actually handed.
    settled_phase = ('settled',)
    #: A verdict per key, for a task that would otherwise pay once a
    #: sentence. See the docstring: a haul taken apart, not shaping.
    dense = True
    dense_only = ('coach',)
    knobs = {'rung': 'start_rung', 'waves': 'total_waves',
             'adaptive': 'adaptive'}

    def __init__(self, seed: Optional[int] = None, coach: bool = True,
                 **kwargs: Any) -> None:
        self._coach = bool(coach)
        super().__init__(seed=seed, **kwargs)

    def apply_dials(self, task: Any) -> None:
        super().apply_dials(task)
        # Only where the boundary will actually pay it per action.
        # :attr:`dense_only` puts it back off in any build that will
        # not, which is the guard that matters — the sparse path reads
        # the first label it finds as the wave's own verdict, and a
        # "yes" three letters into a sentence would score the sentence.
        task.coach = self._coach

    def dials(self) -> Dict[str, Any]:
        knobs = super().dials()
        knobs['coach'] = self._coach
        return knobs

    def drive(self, task: Any, port: int) -> None:
        """Two methods, so this one is not declared.

        A rub-out with nothing to rub out is refused by the task and
        leaves the frame unchanged — the same honest silence walking
        into a wall gets in the Maze. So is a letter offered to a
        buffer that is already the width of its word, which is the one
        state in this task a learner has to get itself out of rather
        than wait out.
        """
        if port < len(LETTERS):
            task.write(LETTERS[port])
        else:
            task.erase()


def make_overrun_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> OverrunEnv:
    """A production environment: the task's own defaults."""
    return OverrunEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_overrun_outcome = OverrunEnv.verifier()

__all__ = ['BACK', 'LETTERS', 'OverrunEnv', 'make_overrun_env',
           'verify_overrun_outcome']
