# -*- coding: utf-8 -*-
"""The stepped agent boundary for Scrabble.

Fourteen ports: four to steer the cursor, seven to lay the tile in
that rack position, one to take the last tile back, one to turn the
cursor between across and down, one to play what is laid.

**The rack positions are positions and not letters.** Port five lays
whatever the fifth tile happens to be, and what that is changes every
trial. A learner cannot bind a port to a letter; it has to read the
rack off the frame, which is drawn under the board for exactly that
reason. This is the one place the ports are deliberately not a stable
vocabulary, and it is what makes the task about the board rather than
about the keyboard.

**Playing is the only thing that settles a trial**, and only a legal
play does it. Tiles that spell nothing come back refused with the
frame unchanged, which costs an action and pays nothing — the same
deal a wall gives in the Maze. So a learner cannot end a trial to
escape a hard board; the only way out is a word.

Green means this rung's share of the best play that existed on that
board, computed exactly by the task. Not "a legal play", which every
settled trial is by construction, and not a number of points, which
would mean something different on every board.

Random play will not settle a trial here. Laying tiles at random and
pressing play produces a legal word about as often as it produces one
by accident, which is to say almost never, so this is one of the
handful of tasks whose boundary is tested by a policy that knows the
answer rather than by the random driver.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from typing import Any, Optional

from .taskenv import TaskEnv

#: Four ways to steer, then a port per rack position.
STEPS = ((0, -1), (0, 1), (-1, 0), (1, 0))
RACK = 7
BACK, TURN, PLAY = (len(STEPS) + RACK, len(STEPS) + RACK + 1,
                    len(STEPS) + RACK + 2)


class ScrabbleEnv(TaskEnv):
    """Deterministic, stepped view of one Scrabble run."""

    task_class = ('neural_workshop.ui.scrabble', 'Scrabble')
    ports = PLAY + 1
    #: Nothing moves on its own; the board waits as long as it is left.
    clocked = False
    open_phase = ('playing',)
    settled_phase = ('scored',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'show_premiums': 'show_premiums', 'adaptive': 'adaptive'}

    def drive(self, task: Any, port: int) -> None:
        """Four methods, so this one is not declared."""
        if port < len(STEPS):
            task.move(*STEPS[port])
        elif port < len(STEPS) + RACK:
            task.lay(port - len(STEPS))
        elif port == BACK:
            task.take_back()
        elif port == TURN:
            task.turn()
        else:
            task.submit()


def make_scrabble_env(seed: int = 0,
                      shm_name: Optional[str] = None) -> ScrabbleEnv:
    """A production environment: the task's own defaults."""
    return ScrabbleEnv(seed=seed, shm_name=shm_name)


#: The verifier, generated from the inherited deriver so the two cannot drift.
verify_scrabble_outcome = ScrabbleEnv.verifier()

__all__ = ['ScrabbleEnv', 'make_scrabble_env', 'verify_scrabble_outcome']
