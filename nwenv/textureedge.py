# -*- coding: utf-8 -*-
"""The stepped agent boundary for Texture Edge.

Four ports: 0 says left and 1 right; with four parts, port k picks
part k in reading order.

Turn-based, so it takes the think clock: the picture stands still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class TextureEdgeEnv(TaskEnv):
    """Deterministic, stepped view of one Texture Edge run."""

    task_class = ('neural_workshop.ui.textureedge', 'TextureEdge')
    ports = 4
    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


def make_texture_edge_env(seed: int = 0,
                            shm_name: Optional[str] = None) -> TextureEdgeEnv:
    """A production environment: the task's own defaults."""
    return TextureEdgeEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_texture_edge_outcome = TextureEdgeEnv.verifier()

__all__ = ['TextureEdgeEnv', 'make_texture_edge_env',
           'verify_texture_edge_outcome']
