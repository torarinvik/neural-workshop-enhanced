# -*- coding: utf-8 -*-
"""The stepped agent boundary for The Artist.

Fifteen ports: 0-3 move the cursor a pixel left, right, down, up and
4-7 an eighth of the canvas; 8 puts the pen down or lifts it; 9 the
next tool; 10 the next palette colour; 11 takes the colour of the
picture under the cursor; 12 undo; 13 done; 14 the next width. Green
means the canvas was as like the picture as the rung asks.

Turn-based, so it takes the think clock: nothing moves until the agent acts.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class ArtistEnv(TaskEnv):
    """Deterministic, stepped view of one The Artist run."""

    task_class = ('neural_workshop.ui.artist', 'Artist')
    ports = 15
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_the_artist_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> ArtistEnv:
    """A production environment: the task's own defaults."""
    return ArtistEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_the_artist_outcome = ArtistEnv.verifier()

__all__ = ['ArtistEnv', 'make_the_artist_env',
           'verify_the_artist_outcome']
