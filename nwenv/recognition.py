# -*- coding: utf-8 -*-
"""The stepped agent boundary for Seen It Before?

Two ports: seen it, or new. The task is a long stream of pictures or
clips of which a set share is a repeat of one shown earlier, and the
lag between a thing and its repeat is the difficulty.

**This one is a fair test of a context window and nothing else.** Every
other task on this boundary can in principle be held in a few frames;
this one cannot, by construction. A learner that remembers only the
recent past will catch the short lags and miss the long ones, and the
score separates the two — the run reports hits against repeats and
false alarms separately, so a learner that says "new" to everything
scores well on one and nothing on the other.

The items come from a media pool. A run needs the pool to have items in
it, and :meth:`begin` says so rather than opening a run that shows
nothing and calls it a score of zero.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv

#: What the task calls its two answers. Spelled out rather than imported
#: because importing a UI module here would pull pyglet's window in
#: before :mod:`nwenv` has set the headless options; ``test_env_tasks``
#: checks the two spellings still agree.
SEEN, NEW = 'seen', 'new'


class RecognitionEnv(TaskEnv):
    """Deterministic, stepped view of one Seen It Before? run."""

    task_class = ('neural_workshop.ui.recognition', 'Recognition')
    ports = 2
    clocked = True
    action = 'answer'
    action_table = (SEEN, NEW)
    open_phase = ('showing', 'hidden')
    settled_phase = ('feedback',)
    #: The next item is presented rather than dealt: there is one long
    #: stream here, not a sequence of separate rounds.
    deal = '_present'
    knobs = {'trials': 'total_trials', 'medium': 'medium',
             'repeat_percent': 'repeat_percent', 'min_lag': 'min_lag',
             'study_ms': 'study_ms'}
    requires = {'feedback': True}


def make_recognition_env(seed: int = 0,
                         shm_name: Optional[str] = None) -> RecognitionEnv:
    """A production environment: the task's own defaults."""
    return RecognitionEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_recognition_outcome = RecognitionEnv.verifier()

__all__ = ['RecognitionEnv', 'make_recognition_env',
           'verify_recognition_outcome']
