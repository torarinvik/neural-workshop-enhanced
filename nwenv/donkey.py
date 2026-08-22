# -*- coding: utf-8 -*-
"""The stepped agent boundary for Donkey.

Two ports: hold the wheel straight, or start a swerve. The original
game had one key, and the second port is the other half of what that
key means rather than padding — a beat spent not pressing is the beat
that keeps the car in a lane it is already safe in.

The task is **clocked**, and here that is the whole of it. The road
comes whether or not anybody steers, and the swerve takes rows the
press cannot buy back. A learner that could stop the road while it
thought would be answering a different question: the question is how
far in front of the donkey you have already committed.

One step is one **sub-row**, which is the unit the rules work in: the
road is cut into :data:`neural_workshop.donkey.SUB` sub-rows a drawn
row, and the car and the donkey have lengths measured in them, so a hit
is the two bodies overlapping rather than the car entering the donkey's
row. That is why ``beat_seconds`` defaults to ``SUB / 60.`` — the dial
is seconds a *row* takes, the task ticks at a quarter of it, and this
value makes one tick exactly one frame and therefore exactly one step.

The task's own default is 0.18 seconds a row; at sixty frames a second
that would give a person eleven presses a sub-row and a learner one,
and then the same rung would be two different games. ``set_seconds``
drops to a frame for the same reason: it is a pause so a person can
read what the rung is asking, and it carries nothing a running frame
does not.

Speed is a dial rather than a rung for exactly this reason, which is
the one place the task departs from the original — where speed was the
*only* difficulty. What carries the ladder instead is the swerve, and
what the swerve costs is measured rather than asserted: swerving on
sight of the donkey clears every road while the crossing is one row
wide and 6%, 3%, 3%, 1% and 6% of them on rungs six to ten.

Random play is paid on every road and paid nothing but red. A coin a
tick starts a crossing it cannot call off, so the car is across the
middle most of the time and the first donkey in either lane ends the
road: the guessing floor here is not small, it is zero. Which is
honest, and it does mean "better than chance" is a low bar to clear
and should not be reported as if it were the finding.

Coach mode
----------

``coach`` paints a verdict on the row a donkey goes by. The wrapper
declares itself ``dense`` so each is paid against its own action's
receipt.

This is **not** potential-based shaping and should not be read as if it
were — there is no potential here and nothing telescopes. It is the
road's own count taken apart: a donkey the car got by is a piece of the
green, and the one it hit is the red the round ends on. Summed over a
road it tracks the donkeys passed, so a learner does not have to reach
the far end to be told anything.

There is nothing for it to leak. The whole road is drawn — every donkey
inside :data:`neural_workshop.ui.donkey.SIGHT` rows of the bonnet is on
the screen — so a coach reading the road is reading what the learner
was already handed. What the task hides is not information; it is
whether you acted on it in time.

The dense reward only arrives under ``neutral_outcomes=True``, which is
how a runtime builds an environment. Built the plain way this task pays
once a road, like every other sparse one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

#: Straight off the model, so the two orders cannot drift apart.
from neural_workshop.donkey import HOLD, SUB, SWITCH  # noqa: E402

PORTS = 2


class DonkeyEnv(TaskEnv):
    """Deterministic, stepped view of one Donkey run."""

    task_class = ('neural_workshop.ui.donkey', 'Donkey')
    #: Hold and swerve. The model's port numbers *are* the task's
    #: actions, so the port index goes straight through.
    ports = PORTS
    clocked = True
    dense = True
    #: The per-row label stays off in any build that will not pay per
    #: row. See :attr:`TaskEnv.dense_only`.
    dense_only = ('coach',)
    action = 'act'
    open_phase = ('running',)
    settled_phase = ('scored',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'beat_seconds': 'beat_seconds', 'set_seconds': 'set_seconds',
             'adaptive': 'adaptive'}

    def __init__(self, seed: Optional[int] = None, coach: bool = True,
                 beat_seconds: float = SUB / 60.,
                 set_seconds: float = 1 / 60., **kwargs: Any) -> None:
        self._coach = bool(coach)
        super().__init__(seed=seed, beat_seconds=beat_seconds,
                         set_seconds=set_seconds, **kwargs)

    def apply_dials(self, task: Any) -> None:
        super().apply_dials(task)
        # Only when the boundary will actually pay it per action. Built
        # the plain way the sparse path reads the first label it finds
        # as the road's own verdict, and a "past one" a few rows in
        # would score the road on one donkey rather than on the drive.
        task.coach = self._coach

    def dials(self):
        knobs = super().dials()
        knobs['coach'] = self._coach
        return knobs


def make_donkey_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> DonkeyEnv:
    """A production environment: the task's own defaults."""
    return DonkeyEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_donkey_outcome = DonkeyEnv.verifier()

__all__ = ['HOLD', 'PORTS', 'SUB', 'SWITCH', 'DonkeyEnv',
           'make_donkey_env', 'verify_donkey_outcome']
