# -*- coding: utf-8 -*-
"""The stepped agent boundary for the Marble Maze.

Four ports, one to each way a knob turns. Nothing else — no port
levels the tray, no port restarts it, and none of the keys a person
gets for convenience is on the boundary. A learner tips the tray and
watches, which is the whole of what the toy offers.

**This is the second task here whose action does not name a thing.**
Pursuit is the other, and the two are different problems wearing the
same shape. Pursuit's control is first-order — a nudge moves the
cursor, and a policy that corrects every frame keeps up in a straight
line. Here it is second-order and then some: a port changes the tray's
*angle*, the angle sets the marble's *acceleration*, and the marble
carries momentum through it. Tilting towards the cup when the marble is
already rolling towards the cup is how you lose it down the next hole.
Nothing on this boundary rewards reacting; the only thing that works is
getting ahead of it.

**The frame carries the state and the frame carries all of it.** Where
the marbles are, where the holes are, where the cup is, and — the part
a flat rendering would have thrown away — what the tray's angle
currently is, legible from its silhouette and from the shadows swinging
under the walls. That last one is why
:mod:`neural_workshop.ui.marblemaze` is a real perspective pipeline
rather than a plan view. A learner that cannot see the tilt is being
asked to integrate its own action history to recover the control it is
holding, which is a different and much worse task.

**Two floors, and which one applies depends on the rung.** Random play
tips the tray at random, which on a low rung wanders a marble around
and eventually drops it down something: measured over nine hundred
steps it is paid, and paid red nearly every time. That is the honest
floor and it is the same shape as Scramble's — what a learner gets for
free is what a mistake costs, and the green needs the knowing-answer
test in :mod:`tests.test_env_tasks`. On the upper rungs random play
does not reliably reach even that, because the clock runs out first,
and a run of trials can come back with nothing but timeouts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from neural_workshop.marblemaze import (TILT_EAST, TILT_NORTH, TILT_SOUTH,
                                        TILT_WEST)

from .taskenv import TaskEnv


class MarbleMazeEnv(TaskEnv):
    """Deterministic, stepped view of one Marble Maze run."""

    task_class = ('neural_workshop.ui.marblemaze', 'MarbleMaze')
    #: Two knobs, two ways each. In an order the learner has to find
    #: out, which here takes a few frames rather than one: a nudge
    #: changes an acceleration, so the first visible consequence of a
    #: port is a marble that has begun to move somewhat later.
    ports = 4
    clocked = True
    action = 'tilt'
    action_table = (TILT_NORTH, TILT_SOUTH, TILT_WEST, TILT_EAST)
    open_phase = ('rolling',)
    #: Not declared as settled. The tray resolves on the task's own
    #: clock — which under this boundary is the driver's — and deals
    #: the next one after the verdict has been up for a couple of
    #: seconds, so there is nothing for the one-frame wait to fix.
    dense = True
    #: The warmer/colder label stays off in any build that will not pay
    #: per action. See :attr:`TaskEnv.dense_only`.
    dense_only = ('coach',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive', 'seconds': 'time_limit'}

    def __init__(self, seed: Optional[int] = None, coach: bool = True,
                 **kwargs: Any) -> None:
        self._coach = bool(coach)
        super().__init__(seed=seed, **kwargs)

    def apply_dials(self, task: Any) -> None:
        super().apply_dials(task)
        # Only when the boundary will actually pay it per action. Built
        # the plain way, the sparse path reads the first label it finds
        # as the tray's own verdict, and a "warmer" a few ticks in
        # would score a tray nobody had finished.
        #
        # The task gates this a second time, on the marble count: the
        # shaping guarantee is that one tick moves the potential by at
        # most one step, and that argument is about one marble. Three
        # of them can each cross a boundary in the same tick. So the
        # several-marble rungs are sparse however this is set, and
        # :meth:`neural_workshop.ui.marblemaze.MarbleMaze.paying` is
        # where that is decided rather than here.
        task.coach = self._coach

    def dials(self) -> Dict[str, Any]:
        knobs = super().dials()
        knobs['coach'] = self._coach
        return knobs


def make_marble_maze_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> MarbleMazeEnv:
    """A production environment: the task's own defaults."""
    return MarbleMazeEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_marble_maze_outcome = MarbleMazeEnv.verifier()

__all__ = ['MarbleMazeEnv', 'make_marble_maze_env',
           'verify_marble_maze_outcome']
