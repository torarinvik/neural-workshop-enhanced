# -*- coding: utf-8 -*-
"""The stepped agent boundary for Buzz Wire.

Eleven ports: six that shove the loop, four that turn the wrist and one
that braces the hand — in an order the learner has to discover, and with
four of them doing nothing at all below the seventh rung, where the loop
still aims itself along the wire. That is the same deal every task here
gives a port a rung does not use.

Clocked, and this is the task on the boundary where that matters most.
The wire does not wait: the hand sags, the tremor drifts and the clock
runs whether or not a port is pressed, so a tick spent deciding is a
tick the loop spent falling. One port a tick is also the binding
constraint on how well it can be flown, because steering and turning the
wrist compete for the same tick — measured in ``tests/bench_buzzwire.py``,
that trade is most of what separates the top four rungs from the rest.

**There is no restart and no undo — not withheld from the learner, but
absent from the game.** Several tasks here have a key a person may press
and a port the boundary does not offer, and this is not one of them: a
buzz is the whole of what is being measured and a way back out of one
would remove it, so nobody gets it. There is no speed control either.
The loop moves because it is pushed, and how fast it is going is a state
the learner put it in rather than a mode it can select.

What a run is paid for is plain. A wire run from post to post inside the
clock is a green; a wire that buzzes past its allowance, or that runs out
of clock, is a red. That is one scalar a wire, and on the bottom rung a
wire is twelve hundred ticks — so the sparse signal alone is thin
enough that the coach below is not a nicety.

**Random play is paid, and paid red.** Eleven ports shoved at random
leave the loop wandering near the near post until the clock runs out,
and the clock running out is a verdict. So the floor here is not zero
and it is not luck: what a learner gets for free is the cost of not
getting anywhere, which is the honest shape for a task whose green has
to be flown for. The green needs a policy that can fly, and
``tests/test_env_tasks.py`` uses the reference pilot for exactly that —
through these eleven ports, reading the verdict off the frame like
anything else.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from neural_workshop.buzzwire import PORTS, SLOWEST_HZ

from .taskenv import TaskEnv


class BuzzWireEnv(TaskEnv):
    """Deterministic, stepped view of one Buzz Wire run."""

    task_class = ('neural_workshop.ui.buzzwire', 'BuzzWire')
    ports = len(PORTS)
    clocked = True
    dense = True
    action = 'press'
    open_phase = ('flying',)
    settled_phase = ('won', 'lost')
    #: The physics is integrated once a tick and the tremor is a process
    #: with a correlation time of a tenth of a second, so a boundary
    #: driven slower than this would be sampling a disturbance it cannot
    #: see. :meth:`Hand.advance` clamps a long frame to the same figure,
    #: so what a slow driver gets is slow motion rather than a loop
    #: through a wire.
    #:
    #: Between here and any faster rate the ladder is the *same* ladder,
    #: which was measured rather than assumed: the reference pilot flies
    #: rungs one, five and nine six times out of six at thirty, sixty
    #: and a hundred and twenty ticks a second alike. What does move is
    #: the top rung, and it moves the way physics says it should — fifty
    #: buzzes a metre at thirty ticks against twenty-six at a hundred
    #: and twenty, because a controller sampling a tenth-of-a-second
    #: disturbance four times has less to say about it than one
    #: sampling it twelve times. That is the task being honest about the
    #: rate it is driven at, not the rate changing the task.
    slowest_frame_hz = SLOWEST_HZ
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'seconds': 'seconds', 'meter': 'show_meter',
             'beads': 'show_beads', 'sight': 'show_sight',
             'coach': 'coach'}
    #: Coach mode on unless the caller says otherwise, for the reason
    #: the Maze gives next door: a wire has no accidental completions,
    #: so the sparse reward pays a random policy nothing but the cost of
    #: the clock -- once a wire, and a wire on the bottom rung is twelve
    #: hundred ticks. Named in both tables on purpose: ``requires`` runs
    #: first and sets the default, and naming it in ``knobs`` as well
    #: lets the unshaped control arm of an experiment about shaping
    #: turn it off.
    requires = {'coach': True}
    #: And off again in any build that will not pay per tick, whatever
    #: `requires` just said. See :attr:`TaskEnv.dense_only`.
    dense_only = ('coach',)


def make_buzzwire_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> BuzzWireEnv:
    """A production environment: the task's own defaults."""
    return BuzzWireEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_buzzwire_outcome = BuzzWireEnv.verifier()

__all__ = ['BuzzWireEnv', 'make_buzzwire_env', 'verify_buzzwire_outcome']
