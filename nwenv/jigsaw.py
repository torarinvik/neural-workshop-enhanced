# -*- coding: utf-8 -*-
"""The stepped agent boundary for Jigsaw Puzzle.

A hundred ports, one to a board position, because ten by ten is the
biggest grid the task will cut. A three-by-three puzzle leaves
ninety-one of them doing nothing.

**A swap is two ports**, as a move is in Hanoi: the first names a tile,
the second names the tile to trade it with. Naming the same one twice
puts it back down. So, as there, the port that costs is the second one
and the port that decided is the first.

Green means the fewest swaps the scramble could be undone in, which is
exact rather than approximate: the minimum is the tile count less the
number of cycles in the permutation. A learner that swaps its way to the
picture is not thereby doing well — almost any sequence of swaps gets
there eventually, and only the shortest one is paid.

The pictures come from a photograph library. A run needs one, and the
task says so on screen rather than dealing an empty puzzle.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from .taskenv import TaskEnv


class JigsawEnv(TaskEnv):
    """Deterministic, stepped view of one Jigsaw Puzzle run."""

    task_class = ('neural_workshop.ui.jigsaw', 'JigsawPuzzle')
    #: The task's own ceiling: ten tiles a side.
    ports = 100
    clocked = False
    action = '_pick'
    open_phase = ('solving',)
    settled_phase = ('solved',)
    deal = '_next_puzzle'
    knobs = {'side': 'start_side', 'puzzles': 'total_puzzles',
             'adaptive': 'adaptive', 'preview': 'preview',
             'mark_placed': 'mark_placed'}


def make_jigsaw_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> JigsawEnv:
    """A production environment: the task's own defaults."""
    return JigsawEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_jigsaw_outcome = JigsawEnv.verifier()

__all__ = ['JigsawEnv', 'make_jigsaw_env', 'verify_jigsaw_outcome']
