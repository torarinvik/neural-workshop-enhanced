# -*- coding: utf-8 -*-
"""The stepped agent boundary for Video Jigsaw.

The jigsaw's ports: a hundred that name the first hundred board
positions outright, and a five-port cursor (up, down, left, right,
pick) that reaches a board of any size. A swap is two picks.

The task is clocked although nothing in it is timed against the
learner: the tiles play, and what joins two of them is as often a
movement that crosses the seam as an edge that lines up. Stepped
without a clock it would be the photograph jigsaw with a small
photograph.

Green means the fewest swaps the shuffle could be undone in, exactly.
The clips come from a downloaded library and are decoded with ffmpeg;
without either the task says so on screen rather than dealing.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class VideoJigsawEnv(TaskEnv):
    """Deterministic, stepped view of one Video Jigsaw run."""

    task_class = ('neural_workshop.ui.videojigsaw', 'VideoJigsaw')
    #: A hundred positions and a five-port cursor.
    ports = 105
    clocked = True
    action = 'steer'
    open_phase = ('solving',)
    settled_phase = ('solved',)
    deal = '_next_puzzle'
    knobs = {'pieces': 'start_pieces', 'puzzles': 'total_puzzles',
             'adaptive': 'adaptive', 'preview': 'preview',
             'mark_placed': 'mark_placed'}


def make_video_jigsaw_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> VideoJigsawEnv:
    """A production environment: the task's own defaults."""
    return VideoJigsawEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_video_jigsaw_outcome = VideoJigsawEnv.verifier()

__all__ = ['VideoJigsawEnv', 'make_video_jigsaw_env',
           'verify_video_jigsaw_outcome']
