# -*- coding: utf-8 -*-
"""The stepped agent boundary for Dispatch.

Eighteen ports. Four name a unit -- the crews, then the scout; a low
rung fields fewer and the rest do nothing. Eight name an incident
slot, the letters on the map. Three name a station to wait at, and
three more name the same stations as somewhere to be refitted, which
does nothing below rung eight, to the scout, or to a crew that has had
its refit. An order is two ports, as a swap is in the jigsaw: a unit,
then where it goes. Naming a unit twice puts it down again.

The task is **clocked**, and here that is the subject rather than a
detail. Incidents grow and crews drive whether or not a port is
pressed, so a step spent thinking is a twentieth of a second the town
did not wait for. That is why this task refuses the think clock: it
already has one, and it is the town.

Coach mode
----------

A round lasts a minute or two and settles into one verdict, which is
very little to learn from. With ``coach`` the task paints a verdict on
the tick an incident is saved and on the tick one is lost, and the
wrapper declares itself ``dense`` so each is paid against its own
action's receipt.

This is the round's own result taken apart, as Cookie Thief's is, and
not potential-based shaping: nothing telescopes. It orders policies
the way the round's verdict does -- more saved and fewer lost is less
damage -- and it diverges in one way worth saying. The round's verdict
also counts how *long* incidents waited, and the per-incident sum does
not, so a learner paid this way is indifferent between saving an
incident early and saving it at the last moment. The round verdict,
which is still paid at the end, is what tells it otherwise.

A finished refit is deliberately not one of the events paid. Whether
the twelve seconds were well spent is exactly what the round's verdict
is there to say, and paying for the refit itself would teach a learner
to refit whether or not the town could spare the crew.

The dense reward only arrives under ``neutral_outcomes=True``. Built
the plain way this task pays once a round.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

#: Units, then incident slots, then stations to wait at, then the same
#: stations to be refitted at.
UNITS, SLOTS, STATIONS = 4, 8, 3
FIRST_SLOT = UNITS
FIRST_STATION = UNITS + SLOTS
FIRST_REFIT = FIRST_STATION + STATIONS
PORTS = FIRST_REFIT + STATIONS


class DispatchEnv(TaskEnv):
    """Deterministic, stepped view of one Dispatch run."""

    task_class = ('neural_workshop.ui.dispatch', 'Dispatch')
    ports = PORTS
    clocked = True
    dense = True
    #: The per-incident label stays off in any build that will not pay
    #: per action. See :attr:`TaskEnv.dense_only`.
    dense_only = ('coach',)
    action = 'press'
    open_phase = ('running',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}

    def __init__(self, seed: Optional[int] = None, coach: bool = True,
                 **kwargs: Any) -> None:
        self._coach = bool(coach)
        super().__init__(seed=seed, **kwargs)

    def apply_dials(self, task: Any) -> None:
        super().apply_dials(task)
        task.coach = self._coach

    def dials(self):
        knobs = super().dials()
        knobs['coach'] = self._coach
        return knobs


def make_dispatch_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> DispatchEnv:
    """A production environment: the task's own defaults."""
    return DispatchEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_dispatch_outcome = DispatchEnv.verifier()

__all__ = ['DispatchEnv', 'FIRST_REFIT', 'FIRST_SLOT', 'FIRST_STATION',
           'PORTS', 'make_dispatch_env', 'verify_dispatch_outcome']
