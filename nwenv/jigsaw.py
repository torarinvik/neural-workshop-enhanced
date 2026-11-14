# -*- coding: utf-8 -*-
"""The stepped agent boundary for Jigsaw Puzzle.

A puzzle is as many pieces as it is asked to be -- two, or hundreds --
so no row of ports can name every position. The first hundred ports
name the first hundred positions outright, which is the whole board up
to ten by ten; the last five are a cursor (up, down, left, right,
pick), which reaches any board whatever its size and is drawn on it.

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
    #: A hundred positions and a five-port cursor.
    ports = 105
    clocked = False
    action = 'steer'
    open_phase = ('solving',)
    settled_phase = ('solved',)
    deal = '_next_puzzle'
    knobs = {'pieces': 'start_pieces', 'puzzles': 'total_puzzles',
             'adaptive': 'adaptive', 'preview': 'preview',
             'mark_placed': 'mark_placed'}


def make_jigsaw_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> JigsawEnv:
    """A production environment: the task's own defaults."""
    return JigsawEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_jigsaw_outcome = JigsawEnv.verifier()

__all__ = ['JigsawEnv', 'make_jigsaw_env', 'verify_jigsaw_outcome']
