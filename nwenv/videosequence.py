# -*- coding: utf-8 -*-
"""The stepped agent boundary for Video Sequence.

Nine ports, one to a position, because nine pieces is the most a clip
is cut into; a four-piece puzzle leaves five doing nothing. A swap is
two ports, as in the jigsaw: the first names a piece, the second the
piece to trade it with, and naming the same one twice puts it down.

The task is clocked although nothing in it is timed against the
learner: the pieces play, and a clip whose pieces were never seen
moving would be four still photographs, which is the jigsaw's
question and not this one's.

Green means the fewest swaps the shuffle could be undone in, exactly.
The clips come from a downloaded library and are decoded with ffmpeg;
without either the task says so on screen rather than dealing.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class VideoSequenceEnv(TaskEnv):
    """Deterministic, stepped view of one Video Sequence run."""

    task_class = ('neural_workshop.ui.videosequence', 'VideoSequence')
    #: The task's own ceiling: nine pieces.
    ports = 9
    clocked = True
    action = '_pick'
    open_phase = ('solving',)
    settled_phase = ('solved',)
    deal = '_next_puzzle'
    knobs = {'pieces': 'start_pieces', 'puzzles': 'total_puzzles',
             'adaptive': 'adaptive', 'mark_placed': 'mark_placed'}


def make_video_sequence_env(seed: int = 0,
                          shm_name: Optional[str] = None) -> VideoSequenceEnv:
    """A production environment: the task's own defaults."""
    return VideoSequenceEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_video_sequence_outcome = VideoSequenceEnv.verifier()

__all__ = ['VideoSequenceEnv', 'make_video_sequence_env',
           'verify_video_sequence_outcome']
