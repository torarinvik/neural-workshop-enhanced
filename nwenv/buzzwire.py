# -*- coding: utf-8 -*-
"""The stepped agent boundary for Buzz Wire.

Four ports, one to a direction, each moving the cursor one step — the
same steps, at the same size, as Pursuit, so the motor vocabulary
transfers whole. What changed is what the world does with them: in
Pursuit the target flees and the errors are the quarry's doing; here
the wire stands perfectly still, and every buzz on the screen was
caused by a port this learner pressed. It is the workshop's purest
self-generated-error task, which is what a steering curriculum has to
start from.

A round is a trip: touch the start pad, take the corridor, reach the
end pad, and one graze anywhere ends it. The verdict carries where the
buzz happened — a cleared wire is green, a touched one is red with the
share of the wire travelled first — so the single scalar a round pays
still ranks a near miss above an early one.

The difficulty is three axes and each is one rung of the classic
fairground game: corridor width, bends, and the clock. Width zero-bends
wide is barely more than holding a line; the adaptive option then
narrows the corridor five percent per clear, so a run settles onto a
width — and the width it settles at is itself a score.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class BuzzWireEnv(TaskEnv):
    """Deterministic, stepped view of one Buzz Wire run."""

    task_class = ('neural_workshop.ui.buzzwire', 'BuzzWire')
    ports = 4
    clocked = True
    action = 'nudge'
    #: Up, down, left, right — in an order the learner has to discover,
    #: which here it can discover in one step, because a nudge moves
    #: the drawn cursor immediately.
    action_table = ((0.0, 1.0), (0.0, -1.0), (-1.0, 0.0), (1.0, 0.0))
    open_phase = ('arming', 'steering')
    #: Not declared as settled: the feedback window closes on the
    #: task's own clock, which under this boundary is the driver's.
    knobs = {'width': 'width_pct', 'bends': 'bends',
             'seconds': 'seconds', 'rounds': 'total_rounds',
             'adaptive': 'adaptive'}


def make_buzzwire_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> BuzzWireEnv:
    """A production environment: the task's own defaults."""
    return BuzzWireEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_buzzwire_outcome = BuzzWireEnv.verifier()

__all__ = ['BuzzWireEnv', 'make_buzzwire_env', 'verify_buzzwire_outcome']
