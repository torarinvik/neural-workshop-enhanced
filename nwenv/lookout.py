# -*- coding: utf-8 -*-
"""The stepped agent boundary for Lookout.

Two ports, one to a channel: "something of the cued colour is on
screen" and "something of the cued form is on screen". On a run watching
only one channel the other port does nothing.

**This is the one task on the boundary where doing nothing is an
action.** Everywhere else a trial ends because the learner ended it.
Here the world closes its own windows: a match drifts in, and if it
churns away unpressed that is a miss, paid the same as a false alarm.
So a learner cannot wait for certainty, and cannot press on every frame
either — pressing with nothing there costs exactly what missing does.
That symmetry is the task, and it is why the reward here can go
negative without the learner having acted at all.

The episode ends at its first resolution on any live channel, so a
'watching' phase is an open trial that may be closed by the flock
rather than by a port.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

#: What the task calls its two channels. Spelled out rather than
#: imported because importing a UI module here would pull pyglet's
#: window in before :mod:`nwenv` has set the headless options;
#: ``test_env_tasks`` checks the two spellings still agree.
COLOR_CHANNEL, FORM_CHANNEL = 'color', 'form'


class LookoutEnv(TaskEnv):
    """Deterministic, stepped view of one Lookout run."""

    task_class = ('neural_workshop.ui.lookout', 'Lookout')
    ports = 2
    clocked = True
    action = 'answer'
    action_table = (COLOR_CHANNEL, FORM_CHANNEL)
    open_phase = ('watching',)
    #: Not declared as settled: the feedback window closes on the
    #: task's own clock, which under this boundary is the driver's, so
    #: the next cue is dealt by ``update`` at a rate the learner can
    #: watch rather than on the frame after the verdict.
    #: ``watching`` is one of 'color', 'form' or 'both'. The task's own
    #: default is 'color', which leaves the second port dead — a caller
    #: measuring divided attention wants 'both' and has to ask for it.
    knobs = {'shapes': 'start_count', 'watching': 'watching',
             'speed': 'speed', 'morph_seconds': 'morph_gap',
             'cues': 'total_cues', 'adaptive': 'adaptive'}


def make_lookout_env(seed: int = 0,
                     shm_name: Optional[str] = None) -> LookoutEnv:
    """A production environment: the task's own defaults."""
    return LookoutEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_lookout_outcome = LookoutEnv.verifier()

__all__ = ['LookoutEnv', 'make_lookout_env', 'verify_lookout_outcome']
