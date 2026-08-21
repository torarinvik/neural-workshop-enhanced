# -*- coding: utf-8 -*-
"""The stepped agent boundary for You Are Here.

The first task wrapped on :class:`nwenv.taskenv.TaskEnv`, and the file is
short because of it. The three written before it came to 628, 680 and 719
lines, of which about 85% was plumbing every one of them had its own copy of,
plus a bespoke pixel deriver and a verifier maintained beside it.

Here there is no deriver and no verifier. The task paints
:class:`neural_workshop.ui.verdict.VerdictLabel` when a maze is solved, and
the boundary's own reader -- the one every other task will share -- turns it
into +1 within par and -1 over it.

By default the wrapper also switches the task's *coach mode* on and declares
itself ``dense``: every move paints warmer(+1)/colder(-1) by Manhattan
distance to the way out, and every action's receipt pays the verdict its own
frame shows.  A move shifts the distance by exactly 1, so the pixel verdict
*is* the potential-based shaping term d - d'; turns and bumps clear the
label and pay zero, so loops telescope to nothing and the shaping cannot be
farmed.  ``coach=False`` restores the sparse solve-only reward.

Two caveats a reader should have, because neither is visible from the
pixels.  Potential-based shaping is *gamma* Phi(s') - Phi(s), and a
two-colour label can only carry +1 or -1, so what is painted is the
gamma=1 term d - d'.  A learner discounting at gamma < 1 is therefore
shaped with an error of (1 - gamma) * d -- smallest at the way out and
largest far from it, which is where a fresh policy spends its time.
Run this task undiscounted, or measure the bias; do not assume it away.

The other is the one episodic shaping usually gets wrong: policy
invariance needs Phi = 0 at every terminal state.  It holds here, but by
luck rather than design -- a trial ends only by reaching the way out,
where the distance, and so the potential, is zero.  There is no step
limit that could end a trial somewhere else.  A *run* still stops after
``trials`` mazes, which truncates mid-maze at a nonzero potential; that
is the ordinary truncation-versus-termination case and is the trainer's
to bootstrap through.

Two things about the task shape the wrapper. It is **turn-based**: nothing
moves unless a key is pressed, so there is no clock to tick and ``clocked``
is False. And a solved maze waits on a keypress before dealing the next one,
which is a menu action rather than a thing to learn, so the driver does it --
but only after the verdict has been on screen for a frame and paid, because
dealing the next maze clears it.

The learner is told none of this. It gets pixels and four opaque ports, and
which port turns which way is not said here.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .taskenv import TaskEnv

#: What the four ports do, in an order the learner has to discover.
WALKS = ('ahead', 'back', 'left', 'right')


class YouAreHereEnv(TaskEnv):
    """Deterministic, stepped view of one You Are Here run."""

    ports = 4
    clocked = False
    dense = True

    def __init__(self, seed: Optional[int] = None,
                 rung: Optional[int] = None,
                 trials: Optional[int] = None,
                 marks: Optional[bool] = None,
                 coach: bool = True,
                 **kwargs: Any) -> None:
        self._rung = rung
        self._trials = trials
        self._marks = marks
        self._coach = bool(coach)
        self._solved_seen = False
        super().__init__(seed=seed, **kwargs)

    def build(self, seed: int, **dials: Any) -> Any:
        from neural_workshop.ui.youarehere import YouAreHere
        return YouAreHere()

    def apply_dials(self, task: Any) -> None:
        if self._rung is not None:
            task.start_rung = int(self._rung)
        if self._trials is not None:
            task.total_trials = int(self._trials)
        if self._marks is not None:
            task.show_marks = bool(self._marks)
        task.coach = self._coach

    def drive(self, task: Any, port: int) -> None:
        task.walk(WALKS[port])

    def trial_open(self, task: Any) -> bool:
        """A maze accepts moves only while it is being walked."""
        return getattr(task, 'phase', None) == 'walking'

    def tick(self, task: Any, dt: float) -> None:
        """Nothing moves on its own; a solved maze needs dealing on.

        The wait is deliberate. Dealing the next maze clears the verdict, so
        going straight there would take the label down on the same frame it
        went up and the outcome would never be derivable. One frame is
        published with it showing first.
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
                'marks': self._marks, 'coach': self._coach}


def make_youarehere_env(seed: int = 0,
                        shm_name: Optional[str] = None) -> YouAreHereEnv:
    """A production environment: the task's own defaults."""
    return YouAreHereEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_youarehere_outcome = YouAreHereEnv.verifier()

__all__ = ['YouAreHereEnv', 'make_youarehere_env',
           'verify_youarehere_outcome']
