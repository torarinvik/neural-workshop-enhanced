# -*- coding: utf-8 -*-
"""The stepped agent boundary for Two Hands.

Eleven ports out of one budget, and that is the task rather than a
detail of the wrapper. Six go to the wheel — hold, left, right, jump,
faster, slower — and five to the sights: four nudges of the crosshair
and a trigger. One step spends exactly one of them, so a step given to
the crosshair is a step the wheel did not get, and how a learner splits
an indivisible attention between two channels that do not wait for each
other is the whole of what is being measured.

The five sights ports are a mouse made steppable, and they are not a
weaker instrument than the one a person has. A person moves the
crosshair continuously and clicks; a learner moves it a notch at a time
and pulls. Both write the same two numbers, the screen paints the same
cross from them, and :func:`neural_workshop.twohands.sighted` decides a
hit the same way for both. Nothing about the sights is a private
channel — which matters, because a task whose second channel could not
be seen in the frame would be a task whose second channel could not be
learned from the frame either.

The task is **clocked**, and here it is clocked twice over. The road
comes on the clock whether or not anybody steers, as it does in Donkey;
and the road *itself* has a deadline, :attr:`Road.clock`, which is what
makes the throttle a decision rather than a slider to leave at one. A
learner that crawled would be safe and would lose every road: measured
over forty deals a rung, the aimed dodge held in first gear runs out of
time on all forty at the bottom of the ladder and on thirty-eight of
forty at the top, and crashes on the rest.

One step is one **tick**, and a tick is not a fixed distance. The road
is cut into :data:`neural_workshop.twohands.SUB` sub-rows a drawn row
and the car takes ``speed`` of them a tick, one to four. That is why
``beat_seconds`` defaults to ``SUB / 60.``: the dial is seconds a row
takes *in first gear*, the task ticks at a quarter of it, and this
value makes one tick exactly one frame and therefore exactly one step.
The task's own default is 0.30 seconds a row, which at sixty frames a
second would give a person eighteen presses a tick and a learner one,
and then the same rung would be two different games.

What random play is worth
-------------------------

Not nothing, unlike Donkey, and the reason is worth having written
down: five of the eleven ports do not touch the wheel, so a uniform
port is a hold five times in eleven and the car spends most of a road
going straight in first gear. Measured over sixty deals a rung that
clears about a fifth of the roads on the bottom rung and none at all
from the third — the floor is real at the bottom of the ladder and
vanishes by the middle of it. Anything read off the first two rungs
should be read against a fifth rather than against zero.

Coach mode
----------

``coach`` paints a verdict on the tick something resolves: a hazard got
by, a coin or a pad taken, a target shot, a clip taken. The wrapper
declares itself ``dense`` so each is paid against its own action's
receipt.

This is **not** potential-based shaping and should not be read as if it
were — there is no potential here and nothing telescopes. It is the
road's own haul taken apart, which is what Cookie Thief does. Summed
over a road it tracks what the road was worth, so a learner does not
have to reach the far end to be told anything. It diverges from the
verdict in the one way that shape always does: the verdict is
all-or-nothing and the sum is graded, so a learner paid this way
tolerates a little more risk than the verdict rewards.

There is nothing for it to leak. Every hazard inside
:data:`neural_workshop.ui.twohands.SIGHT` rows of the bonnet is drawn,
every target aloft is drawn, and the crosshair is drawn. What the task
hides is not information; it is whether you had a tick to spare.

The dense reward only arrives under ``neutral_outcomes=True``, which is
how a runtime builds an environment. Built the plain way this task pays
once a road, like every other sparse one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

#: Straight off the model, so the two orders cannot drift apart.
from neural_workshop.twohands import (  # noqa: E402
    AIM_DOWN, AIM_LEFT, AIM_RIGHT, AIM_UP, FASTER, FIRE, HOLD, JUMP, LEFT,
    PORTS, RIGHT, SLOWER, SUB)


class TwoHandsEnv(TaskEnv):
    """Deterministic, stepped view of one Two Hands run."""

    task_class = ('neural_workshop.ui.twohands', 'Twohands')
    #: Eleven, and the model's port numbers *are* the task's actions,
    #: so the port index goes straight through. They are deliberately
    #: one flat list rather than two: a boundary that offered "a wheel
    #: action and a sights action" every step would be handing over the
    #: answer to the only question the task asks.
    ports = PORTS
    clocked = True
    dense = True
    #: The per-tick label stays off in any build that will not pay per
    #: tick. See :attr:`TaskEnv.dense_only`.
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
        # would score the road on one hazard rather than on the drive.
        task.coach = self._coach

    def dials(self):
        knobs = super().dials()
        knobs['coach'] = self._coach
        return knobs


def make_two_hands_env(seed: int = 0,
                       shm_name: Optional[str] = None) -> TwoHandsEnv:
    """A production environment: the task's own defaults."""
    return TwoHandsEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_two_hands_outcome = TwoHandsEnv.verifier()

__all__ = ['AIM_DOWN', 'AIM_LEFT', 'AIM_RIGHT', 'AIM_UP', 'FASTER', 'FIRE',
           'HOLD', 'JUMP', 'LEFT', 'PORTS', 'RIGHT', 'SLOWER', 'SUB',
           'TwoHandsEnv', 'make_two_hands_env', 'verify_two_hands_outcome']
