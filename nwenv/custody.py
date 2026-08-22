# -*- coding: utf-8 -*-
"""The stepped agent boundary for Chain of Custody.

Four ports: two to slide the claw round the ring, one that picks up or
puts down, and one that does nothing at all.

The waiting port is not padding. **A claw cannot chase a box** — both
move one slot a step, so a claw behind a box stays behind it forever,
and the only way to pick something up is to stand where it is going to
be and let the ring bring it. Doing nothing is therefore a real move
here, in a way it is nowhere else on this boundary, and a learner that
never uses it can never pick anything up on a moving belt.

The task is **clocked**: the belt runs whether or not anyone acts, and
one step is one tick. That is not a cost to be optimised away. A
learner that could freeze the belt while it thought would be answering
a question it had not been asked, because the whole of the question is
whether an identity survives the motion.

Charge and heat live on the boxes and are drawn on them, so nothing the
learner needs is hidden — except the one thing that is meant to be:
which box was ringed at the start.

Coach mode
----------

``coach`` paints a verdict after every claw move that carried the held
box nearer or further from where it next has to be, and the wrapper
declares itself ``dense`` so each of those is paid against its own
action's receipt. One move changes that distance by exactly one, so the
label is the potential-based shaping term ``d - d'`` of Ng et al., every
closed loop of moves telescopes to nothing, and the optimal policy is
unchanged. Picking up, putting down and waiting clear the label and pay
zero, which is what stops a learner farming it on the spot.

**The shaping is blind to the Core.** It reads the held box's charge,
heat and position and the machines' positions — every one of them
already on the screen — and never ``layout.core``. That is deliberate
and it is the whole reason coach mode is safe to leave on: it makes the
routing easier to learn and the identity no easier at all. A potential
that knew which box was the Core would have handed over the answer to
the only question this task asks, and every number taken under it would
have been about routing while claiming to be about custody.

The dense reward only arrives under ``neutral_outcomes=True``, which is
how a runtime builds an environment. Built the plain way this task pays
once a round, like every other sparse one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

#: What the four ports do, in an order the learner has to discover.
LEFT, RIGHT, TAKE, WAIT = 0, 1, 2, 3
PORTS = 4


class CustodyEnv(TaskEnv):
    """Deterministic, stepped view of one Chain of Custody run."""

    task_class = ('neural_workshop.ui.custody', 'ChainOfCustody')
    #: Four: two to slide, one to take or place, and exactly one that
    #: does nothing. Two ports that both did nothing would be two the
    #: learner must tell apart and cannot, which is noise rather than
    #: difficulty — and this said five for a while, which meant it had
    #: two of them.
    ports = PORTS
    clocked = True
    dense = True
    #: The per-move label stays off in any build that will not pay
    #: per move. See :attr:`TaskEnv.dense_only`.
    dense_only = ('coach',)
    open_phase = ('running',)
    settled_phase = ('scored',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'belt_seconds': 'belt_seconds', 'mark_seconds': 'mark_seconds',
             'adaptive': 'adaptive'}

    def __init__(self, seed: Optional[int] = None, coach: bool = True,
                 belt_seconds: float = 1 / 60., **kwargs: Any) -> None:
        # One belt step per tick, so one action is one beat of the
        # round and the budget means the same number of moves it means
        # for a person. The task's own default is 0.40 seconds, which
        # at sixty frames a second gives a person twenty-four presses a
        # beat; a learner stepping the clock itself would get one, and
        # then the same budget would be two different rounds.
        self._coach = bool(coach)
        super().__init__(seed=seed, belt_seconds=belt_seconds, **kwargs)

    def apply_dials(self, task: Any) -> None:
        super().apply_dials(task)
        # Only when the boundary will actually pay it per action. Built
        # the plain way the sparse path reads the first label it finds
        # as the round's own verdict, and a warmer/colder one there
        # scores the round on a claw move rather than on the delivery.
        task.coach = self._coach

    def dials(self):
        knobs = super().dials()
        knobs['coach'] = self._coach
        return knobs

    def drive(self, task: Any, port: int) -> None:
        """Slide the claw, work it, or stand still.

        Standing still calls nothing, and it needs to call nothing: the
        round's budget is spent by the clock rather than by the action,
        so letting a beat pass costs a beat whether a port asked for it
        or not. There is nothing here for the boundary to account for.
        """
        if port == LEFT:
            task.move(-1)
        elif port == RIGHT:
            task.move(1)
        elif port == TAKE:
            task.take_or_place()


def make_custody_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> CustodyEnv:
    """A production environment: the task's own defaults."""
    return CustodyEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_custody_outcome = CustodyEnv.verifier()

__all__ = ['CustodyEnv', 'LEFT', 'PORTS', 'RIGHT', 'TAKE', 'WAIT',
           'make_custody_env', 'verify_custody_outcome']
