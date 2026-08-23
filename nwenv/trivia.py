# -*- coding: utf-8 -*-
"""The stepped agent boundary for Trivia.

Eight ports: one an answer. That is the widest rung of the ladder, and
it is the task's ceiling rather than any rung's — on rung one two
ports are live and six are inert. **A port the rung does not offer
does nothing**, and leaves the frame exactly as it was, which is the
same honest silence walking into a wall gets in the Maze.

Green means the option picked was the one TriviaQA gives. There is
nothing partial to be nearly right about: an answer here is an index.

**What this task is for is worth saying, because it is not what the
rest of the workshop is for.** Every other wrapped task is solvable
from its own frames — the premises are on the page, the board is on
the page, the thing to remember was shown a moment ago. This one is
not. *Which American-born Sinclair won the Nobel Prize for Literature
in 1930?* is not answerable from the pixels of that sentence by
anything that does not already know, and no amount of looking at the
frame will make it so. It is a probe of what a learner brought with
it, not of what it can work out, and a learning curve drawn on it is
a curve about a prior.

**Random play is paid here, and paid mostly red** — one port in two at
the bottom of the ladder and one in eight at the top, which at rung
one is a coin and worth knowing before reading anything off a curve.
That is the same shape Syllogisms has. The green needs no special
test: a policy that reads the frame is not required to get one, and
``tests/test_env_trivia.py`` gets one by answering through these ports
with the index the deal used.

**Not shaped, and could not honestly be.** There is one action a
trial, and the only potential available before it is which option is
right, which is the answer.

The pool is a knob like the rung and the trial count only in the
negative sense: there is no dial for it here, because which questions
exist is a property of what has been fetched onto the machine rather
than of how an environment was built. With nothing fetched the deal
comes from the hundred and twenty questions written into
:mod:`neural_workshop.trivia`, and an experiment that cares which pool
it ran against should record :func:`neural_workshop.trivia.fetched`
alongside its numbers.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Optional

from neural_workshop.trivia import MOST_OPTIONS

from .taskenv import TaskEnv


class TriviaEnv(TaskEnv):
    """Deterministic, stepped view of one Trivia run."""

    task_class = ('neural_workshop.ui.trivia', 'Trivia')
    ports = MOST_OPTIONS
    #: Nothing moves on its own; the question waits as long as it is left.
    clocked = False
    action = 'choose'
    open_phase = ('asking',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'show_answer': 'show_answer', 'adaptive': 'adaptive'}


def make_trivia_env(seed: int = 0,
                    shm_name: Optional[str] = None) -> TriviaEnv:
    """A production environment: the task's own defaults."""
    return TriviaEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_trivia_outcome = TriviaEnv.verifier()

__all__ = ['TriviaEnv', 'make_trivia_env', 'verify_trivia_outcome']
