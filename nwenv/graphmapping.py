# -*- coding: utf-8 -*-
"""The stepped agent boundary for Graph Mapping.

Two ports: same network, or not. A two-port task is the least
informative shape a boundary can have — a coin gets half of them — so a
run here is worth reading only over enough trials for chance to be ruled
out, and the panel's reward-density figure means less on this task than
on any other in the workshop.

What makes it hard is not the choice but the correspondence. The two
drawings are the same graph under a relabelling and a fresh ring
layout, so nothing about their pictures lines up: the learner has to
decide whether a structure is preserved by a permutation it is not
shown. The 'keeps the degree sequence' option removes the shortcut of
counting lines at each dot, which is the one way to answer without
doing that.

The verdict says whether the answer was right, not what the pair was.
The task's own message says the second — useful to a person, and not a
scalar.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

#: What the task calls its two answers. Spelled out rather than imported
#: because importing a UI module here would pull pyglet's window in
#: before :mod:`nwenv` has set the headless options; ``test_env_tasks``
#: checks the two spellings still agree.
SAME, DIFFERENT = 'same', 'different'


class GraphMappingEnv(TaskEnv):
    """Deterministic, stepped view of one Graph Mapping run."""

    task_class = ('neural_workshop.ui.graphmapping', 'GraphMapping')
    ports = 2
    clocked = True
    action = 'answer'
    #: The task answers in words rather than indices, so the ports carry
    #: the words. Which port is which is still the learner's to find.
    action_table = (SAME, DIFFERENT)
    open_phase = ('asking', 'hidden')
    settled_phase = ('feedback',)
    knobs = {'rung': 'start_nodes', 'trials': 'total_trials',
             'density': 'density', 'subtle': 'subtle',
             'exposure_ms': 'exposure_ms', 'adaptive': 'adaptive'}
    requires = {'feedback': True}


def make_graphmapping_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> GraphMappingEnv:
    """A production environment: the task's own defaults."""
    return GraphMappingEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_graphmapping_outcome = GraphMappingEnv.verifier()

__all__ = ['GraphMappingEnv', 'make_graphmapping_env',
           'verify_graphmapping_outcome']
