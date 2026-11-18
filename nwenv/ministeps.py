# -*- coding: utf-8 -*-
"""The stepped agent boundary for the short walks: a maze, a tower,
tiles, a box to push and an open grid, each a few presses from done.

Turn-based, so these take the think clock: nothing moves until a port
is pressed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from .taskenv import TaskEnv


class _Rung(TaskEnv):
    """What every wrapper here shares."""

    clocked = False
    action = 'steer'
    open_phase = ('playing',)
    settled_phase = ('judged',)
    knobs = {'rung': 'start_rung', 'trials': 'total_trials',
             'adaptive': 'adaptive'}


class ShortMazeEnv(_Rung):
    """Short Maze: Four ports: up, down, left, right. Green means
    the way out was reached with no wrong step."""

    task_class = ('neural_workshop.ui.ministeps', 'ShortMaze')
    ports = 4


class ShortTowerEnv(_Rung):
    """Short Tower: Six ports, peg to peg: 1-2, 1-3, 2-1, 2-3, 3-1,
    3-2. Green means the tower was stacked with no wrong move."""

    task_class = ('neural_workshop.ui.ministeps', 'ShortTower')
    ports = 6


class TurnedTilesEnv(_Rung):
    """Turned Tiles: Sixteen ports, one a tile, along the rows from the
    top left; a board with fewer tiles leaves the rest doing nothing.
    Green means every turned tile was turned back and no other was
    pressed."""

    task_class = ('neural_workshop.ui.ministeps', 'TurnedTiles')
    ports = 16


class ShortPushEnv(_Rung):
    """Short Push: Four ports: up, down, left, right. Green means
    the box reached its mark with no wrong press."""

    task_class = ('neural_workshop.ui.ministeps', 'ShortPush')
    ports = 4


class ShortMazeStepsEnv(_Rung):
    """Short Maze, Step by Step: Four ports: up, down, left, right.
    Green means the way out was reached with no wrong step; built to
    pay by the press, each right step is marked green as well."""

    task_class = ('neural_workshop.ui.ministeps', 'ShortMazeSteps')
    ports = 4
    #: Pays by the press when a runtime builds it; built the plain
    #: way the per-step mark stays off and it is Short Maze.
    dense = True
    dense_only = ('coach',)
    knobs = dict(_Rung.knobs, coach='coach')
    requires = {'coach': True}


class MarkerWalkEnv(_Rung):
    """Marker Walk: Four ports: up, down, left, right. Green means
    the marked square was reached with no wasted move."""

    task_class = ('neural_workshop.ui.ministeps', 'MarkerWalk')
    ports = 4


class MarkerWalkShuffledEnv(_Rung):
    """Marker Walk, Shuffled: Four ports, each moving the marker one
    way; which way is dealt when the run starts and holds for the
    run. Green means the marked square was reached with no wasted
    move."""

    task_class = ('neural_workshop.ui.ministeps', 'MarkerWalkShuffled')
    ports = 4


verify_short_maze_outcome = ShortMazeEnv.verifier()
verify_short_tower_outcome = ShortTowerEnv.verifier()
verify_turned_tiles_outcome = TurnedTilesEnv.verifier()
verify_short_push_outcome = ShortPushEnv.verifier()
verify_short_maze_steps_outcome = ShortMazeStepsEnv.verifier()
verify_marker_walk_outcome = MarkerWalkEnv.verifier()
verify_marker_walk_shuffled_outcome = MarkerWalkShuffledEnv.verifier()

__all__ = ['ShortMazeEnv', 'ShortTowerEnv', 'TurnedTilesEnv', 'ShortPushEnv', 'ShortMazeStepsEnv', 'MarkerWalkEnv', 'MarkerWalkShuffledEnv']
