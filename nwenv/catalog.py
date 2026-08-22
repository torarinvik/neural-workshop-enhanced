# -*- coding: utf-8 -*-
"""Every task the learner can reach, in one table.

There were four of these lists. The task hub had the playable tasks,
``tests/drive_env.py`` had the wrapped ones, ``tests/check_band.py`` had
a hand-written driver per task, and the exports in :mod:`nwenv` had a
fourth. Four lists of the same thing drift, and the way they drift is
the quiet one: a task gets added to the hub, nobody adds it here, and
the sweep that checks nothing paints in the verdict band goes on
reporting "clean" about the twenty-three tasks it knows.

So this is the list, and ``tests/test_env_catalog.py`` fails the build
if the hub holds a task this does not. Adding a task means adding a row
here, and everything that walks the tasks — the band sweep, the random
driver, the exports — picks it up without being told.

Nothing here imports a task. The rows are module paths and class names,
resolved on demand by :func:`env_class` and :func:`ui_class`, because
importing a UI module pulls in pyglet's window and :mod:`nwenv` has to
set its headless options first.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import importlib
from typing import Any, Dict, List, NamedTuple, Tuple


class Wrapped(NamedTuple):
    """One task, and where both halves of it live."""

    task_id: str        # what the task hub calls it
    label: str          # what a person calls it
    env_module: str
    env_class: str
    ui_module: str
    ui_class: str


#: In the hub's order, which is by category rather than by name.
CATALOG: Tuple[Wrapped, ...] = (
    Wrapped('nback', 'N-Back',
            'nwenv.env', 'NeuralWorkshopEnv',
            'neural_workshop.ui.trialui', ''),
    Wrapped('monkey_ladder', 'Monkey Ladder',
            'nwenv.ladder', 'MonkeyLadderEnv',
            'neural_workshop.ui.monkeyladder', 'MonkeyLadder'),
    Wrapped('in_the_dark', 'In the Dark',
            'nwenv.inthedark', 'InTheDarkEnv',
            'neural_workshop.ui.inthedark', 'InTheDark'),
    Wrapped('fog_of_war', 'Fog of War',
            'nwenv.fog', 'FogOfWarEnv',
            'neural_workshop.ui.fogofwar', 'FogOfWar'),
    Wrapped('removals', 'Removals',
            'nwenv.removals', 'RemovalsEnv',
            'neural_workshop.ui.removals', 'Removals'),
    Wrapped('chain_of_custody', 'Chain of Custody',
            'nwenv.custody', 'CustodyEnv',
            'neural_workshop.ui.custody', 'ChainOfCustody'),
    Wrapped('concentration', 'Concentration',
            'nwenv.concentration', 'ConcentrationEnv',
            'neural_workshop.ui.concentration', 'Concentration'),
    Wrapped('recognition', 'Seen It Before?',
            'nwenv.recognition', 'RecognitionEnv',
            'neural_workshop.ui.recognition', 'Recognition'),
    Wrapped('reflex', 'Reflex',
            'nwenv.reflex', 'ReflexEnv',
            'neural_workshop.ui.reflex', 'Reflex'),
    Wrapped('ncup_monte', 'N-Cup Monte',
            'nwenv.ncupmonte', 'NCupMonteEnv',
            'neural_workshop.ui.ncupmonte', 'NCupMonte'),
    Wrapped('moving_targets', 'Moving Targets',
            'nwenv.tracking', 'MovingTargetsEnv',
            'neural_workshop.ui.tracking', 'MovingTargets'),
    Wrapped('lookout', 'Lookout',
            'nwenv.lookout', 'LookoutEnv',
            'neural_workshop.ui.lookout', 'Lookout'),
    Wrapped('pursuit', 'Pursuit',
            'nwenv.pursuit', 'PursuitEnv',
            'neural_workshop.ui.pursuit', 'Pursuit'),
    Wrapped('out_of_sight', 'Out of Sight',
            'nwenv.sight', 'OutOfSightEnv',
            'neural_workshop.ui.outofsight', 'OutOfSight'),
    Wrapped('count', 'Count',
            'nwenv.counting', 'CountingEnv',
            'neural_workshop.ui.counting', 'Counting'),
    Wrapped('graph_mapping', 'Graph Mapping',
            'nwenv.graphmapping', 'GraphMappingEnv',
            'neural_workshop.ui.graphmapping', 'GraphMapping'),
    Wrapped('matrix_reasoning', 'Matrix Reasoning',
            'nwenv.ravens', 'MatrixReasoningEnv',
            'neural_workshop.ui.ravens', 'MatrixReasoning'),
    Wrapped('jigsaw', 'Jigsaw Puzzle',
            'nwenv.jigsaw', 'JigsawEnv',
            'neural_workshop.ui.jigsaw', 'JigsawPuzzle'),
    Wrapped('sudoku', 'Sudoku',
            'nwenv.sudoku', 'SudokuEnv',
            'neural_workshop.ui.sudoku', 'Sudoku'),
    Wrapped('crossed_wires', 'Crossed Wires',
            'nwenv.crossedwires', 'CrossedWiresEnv',
            'neural_workshop.ui.crossedwires', 'CrossedWires'),
    Wrapped('tower_of_hanoi', 'Tower of Hanoi',
            'nwenv.hanoi', 'HanoiEnv',
            'neural_workshop.ui.hanoi', 'TowerOfHanoi'),
    Wrapped('salesman', 'Traveling Salesman',
            'nwenv.salesman', 'SalesmanEnv',
            'neural_workshop.ui.salesman', 'TravelingSalesman'),
    Wrapped('sokoban', 'Sokoban',
            'nwenv.sokoban', 'SokobanEnv',
            'neural_workshop.ui.sokoban', 'SokobanTask'),
    Wrapped('maze', 'Maze',
            'nwenv.maze', 'MazeEnv',
            'neural_workshop.ui.maze', 'MazeTask'),
    Wrapped('you_are_here', 'You Are Here',
            'nwenv.youarehere', 'YouAreHereEnv',
            'neural_workshop.ui.youarehere', 'YouAreHere'),
    Wrapped('cookie_thief', 'Cookie Thief',
            'nwenv.cookiethief', 'CookieThiefEnv',
            'neural_workshop.ui.cookiethief', 'CookieThief'),
)

BY_ID: Dict[str, Wrapped] = {row.task_id: row for row in CATALOG}


def task_ids() -> List[str]:
    """Every wrapped task, in the hub's order."""
    return [row.task_id for row in CATALOG]


def env_class(task_id: str) -> Any:
    """The environment class for *task_id*, imported now."""
    row = BY_ID[task_id]
    return getattr(importlib.import_module(row.env_module), row.env_class)


def ui_class(task_id: str) -> Any:
    """The UI task class for *task_id*, imported now.

    The n-back workshop has none: it is the original game rather than
    an overlay, and it is driven through :mod:`nwenv.env` instead.
    """
    row = BY_ID[task_id]
    if not row.ui_class:
        raise KeyError('%s has no standalone UI class' % task_id)
    return getattr(importlib.import_module(row.ui_module), row.ui_class)


def overlays() -> List[Wrapped]:
    """The tasks that are overlays, so have a UI class to open."""
    return [row for row in CATALOG if row.ui_class]


__all__ = ['BY_ID', 'CATALOG', 'Wrapped', 'env_class', 'overlays',
           'task_ids', 'ui_class']
