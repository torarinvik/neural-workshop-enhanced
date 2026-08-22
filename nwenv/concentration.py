# -*- coding: utf-8 -*-
"""The stepped agent boundary for Concentration.

A hundred ports, one to a card, because fifty pairs is the biggest board
the task will lay. A board of eight pairs leaves eighty-four of them
doing nothing.

**What is scored is not turns.** An unlucky deal costs turns nobody
could have saved, and counting them would pay the deal rather than the
player. What a board is scored on is *lapses*: leaving a pair on the
table when both its cards have already been turned over once, or
turning over a card already seen in the hope of a match it has been
shown is not there. Neither is possible for a player who forgets
nothing, so a board cleared with none of them was played the way
perfect memory would have played it, whatever the deal gave.

That makes the verdict here a direct read on the only thing the task
tests, and it makes the green achievable on every deal rather than on
the lucky ones.

The reward is as sparse as anything on this boundary: one scalar per
board, and a board of eight pairs is at least sixteen flips. Nothing is
paid in between, and a single lapse anywhere in that run of flips turns
the whole board red — which is severe, and is the same severity
Removals and In the Dark use for the same reason.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv


class ConcentrationEnv(TaskEnv):
    """Deterministic, stepped view of one Concentration board."""

    task_class = ('neural_workshop.ui.concentration', 'Concentration')
    #: The task's own ceiling: fifty pairs.
    ports = 100
    clocked = True
    dense = True
    open_phase = ('playing',)
    settled_phase = ('done',)
    #: A board is dealt rather than a run started, and the same call
    #: does both.
    start = deal = 'deal'
    knobs = {'pairs': 'pairs', 'medium': 'medium', 'peek_ms': 'peek_ms',
             'hide_ms': 'hide_ms', 'coach': 'coach'}
    #: Coach mode on unless the caller says otherwise. One scalar per
    #: board is the sparsest reward on this boundary -- eight pairs is
    #: sixteen flips with nothing in between -- and random play cleared
    #: no board at all in 400 ticks, so the trainer saw nothing.
    #:
    #: In both tables for the same reason as the Maze: requires sets the
    #: default on, knobs lets an experiment turn it off. Here that matters
    #: more than elsewhere, because coach names a lapse and a run meant to
    #: measure memory rather than coached memory wants it off.
    requires = {'coach': True}

    def drive(self, task: Any, port: int) -> None:
        """Turn over one card.

        Not declared, because the task flips a *card* rather than an
        index, and because a card that is already up or already matched
        refuses the flip — which is the task's own rule and means a
        learner cannot spend a turn on a card it can see is gone.
        """
        if port < len(task.cards):
            task.flip(task.cards[port])

    def finished(self, task: Any) -> bool:
        """Never: a board is followed by another board.

        The task's ``done`` is a cleared board, not a finished run, and
        it is the settled phase here rather than the end of one.
        """
        return False


def make_concentration_env(seed: int = 0,
                           shm_name: Optional[str] = None) -> ConcentrationEnv:
    """A production environment: the task's own defaults."""
    return ConcentrationEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_concentration_outcome = ConcentrationEnv.verifier()

__all__ = ['ConcentrationEnv', 'make_concentration_env',
           'verify_concentration_outcome']
