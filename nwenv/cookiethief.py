# -*- coding: utf-8 -*-
"""The stepped agent boundary for Cookie Thief.

Four ports: grab, leave, reach for the golden one, and wait. Every one
of them is worth pressing, which is not something this boundary can
usually say about four ports.

**A grab is instant.** The cookie is in the count on the beat it was
asked for; nothing is queued and nothing is in flight. There is exactly
one thing a learner can be wrong about and it is *whether* to press,
never when the press will arrive.

**Waiting and leaving are both real.** Waiting lets the noise a quick
hand made die back down, so it is what buys the grab after next;
leaving banks the haul and ends the round, and it is the only move that
cannot go wrong and the only one that stops the count going up. A
learner that never leaves is caught on every rung above the fifth, and
one that never waits runs the door up on itself and comes home short.

The task is **clocked**, and that is the whole of the difficulty rather
than an implementation detail. The kitchen beats whether or not anyone
acts, so a learner that could freeze the world while it thought would
be answering a question nobody asked: the question is what you do with
momentum you have already committed to, and momentum you can pause is
not momentum.

One step is one beat, which is why ``beat_seconds`` defaults to a
frame. The task's own default is 0.16 seconds; at sixty frames a second
that gives a person ten presses a beat and a learner one, and then the
same round would be two different games.

``set_seconds`` is dropped to a frame for the same reason and a
different one. It is a pause before the first beat so a person can read
what the round is asking for, and it carries nothing a running frame
does not — unlike Chain of Custody's ringing, which is the only moment
the answer is on screen and therefore has to survive into the
boundary's clock. Left at nine tenths of a second it would have been
fifty-four ticks of nothing at the head of every round.

Coach mode
----------

``coach`` paints a verdict on the beat a cookie lands, and on the beat
she has her eyes on a grab. The wrapper declares itself ``dense`` so
each is paid against its own action's receipt.

This is **not** the potential-based shaping the maze and the belt got,
and it should not be read as if it were. There is no potential here and
nothing telescopes. What it is instead is the round's *haul* taken
apart — see :func:`neural_workshop.cookiethief.haul`. A cookie he got
away with is a piece of the green; a grab she had her eyes on is the
red. Summed over a round it tracks the haul, and a learner does not
have to reach the end of a round to be told anything.

Every safe cookie pays, including the ones past the quota, and that was
not the first rule here. Capped at the quota, a cookie past it was
worth exactly nothing on this channel while the score on the screen
still counted it, so the two halves of the same game wanted different
things. They want the same thing now.

Where it diverges from the *verdict* is worth saying plainly, because
it does. The round's scalar is a bar — the quota, cleanly, all or
nothing — and the dense sum is the margin. They agree on the ordering
that matters (a clean rich round beats a clean thin one beats a caught
one) and they disagree about how much a cookie past the quota is worth,
because one bit cannot carry a margin. Measured: pushing the door a
little way into the shaded range is worth about a point of haul on
every rung above the fifth and costs a few per cent of clean rounds;
pushing it the whole way is worth a third of the haul and loses every
round. So the marginal cookie turns negative somewhere in between, and
where it turns is a property of the rung rather than of the accounting.

**The coach is blind to both hidden things.** It reads the jar, the
pips, the boy's speed and the doorway — every one of them drawn — and
never the trigger or the deadline. Those two are the whole of what the
task hides, and a coach that knew when she was coming would have handed
over the answer to the only question it asks.

The dense reward only arrives under ``neutral_outcomes=True``, which is
how a runtime builds an environment. Built the plain way this task pays
once a round, like every other sparse one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

#: Straight off the model, so the two orders cannot drift apart.
from neural_workshop.cookiethief import (GRAB, LEAVE,  # noqa: E402
                                         LUNGE, WAIT)

PORTS = 4


class CookieThiefEnv(TaskEnv):
    """Deterministic, stepped view of one Cookie Thief run."""

    task_class = ('neural_workshop.ui.cookiethief', 'CookieThief')
    #: Grab, leave, lunge and wait. The lunge does nothing on the
    #: seven rungs with no golden cookie, which is the task refusing it
    #: rather than the wrapper — the same way a rung with four choices
    #: out of eight leaves four ports idle.
    ports = PORTS
    clocked = True
    dense = True
    #: The per-move label stays off in any build that will not pay
    #: per move. See :attr:`TaskEnv.dense_only`.
    dense_only = ('coach',)
    #: One port, one press: the task takes the port index straight,
    #: because the model's port numbers *are* the task's actions.
    action = 'act'
    open_phase = ('running',)
    settled_phase = ('scored',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'beat_seconds': 'beat_seconds', 'set_seconds': 'set_seconds',
             'adaptive': 'adaptive'}

    def __init__(self, seed: Optional[int] = None, coach: bool = True,
                 beat_seconds: float = 1 / 60.,
                 set_seconds: float = 1 / 60., **kwargs: Any) -> None:
        self._coach = bool(coach)
        super().__init__(seed=seed, beat_seconds=beat_seconds,
                         set_seconds=set_seconds, **kwargs)

    def apply_dials(self, task: Any) -> None:
        super().apply_dials(task)
        # Only when the boundary will actually pay it per action. Built
        # the plain way the sparse path reads the first label it finds
        # as the round's own verdict, and a "got one" on the first beat
        # would score the round on one cookie rather than on the escape.
        task.coach = self._coach

    def dials(self):
        knobs = super().dials()
        knobs['coach'] = self._coach
        return knobs


def make_cookiethief_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> CookieThiefEnv:
    """A production environment: the task's own defaults."""
    return CookieThiefEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_cookiethief_outcome = CookieThiefEnv.verifier()

__all__ = ['GRAB', 'LEAVE', 'LUNGE', 'PORTS', 'WAIT', 'CookieThiefEnv',
           'make_cookiethief_env', 'verify_cookiethief_outcome']
