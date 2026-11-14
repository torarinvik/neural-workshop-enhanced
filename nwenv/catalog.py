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
    Wrapped('trivia', 'Trivia',
            'nwenv.trivia', 'TriviaEnv',
            'neural_workshop.ui.trivia', 'Trivia'),
    Wrapped('notebook', 'Notebook',
            'nwenv.notebook', 'NotebookEnv',
            'neural_workshop.ui.notebook', 'Notebook'),
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
    Wrapped('buzz_wire', 'Buzz Wire',
            'nwenv.buzzwire', 'BuzzWireEnv',
            'neural_workshop.ui.buzzwire', 'BuzzWire'),
    Wrapped('out_of_sight', 'Out of Sight',
            'nwenv.sight', 'OutOfSightEnv',
            'neural_workshop.ui.outofsight', 'OutOfSight'),
    Wrapped('donkey', 'Donkey',
            'nwenv.donkey', 'DonkeyEnv',
            'neural_workshop.ui.donkey', 'Donkey'),
    Wrapped('two_hands', 'Two Hands',
            'nwenv.twohands', 'TwoHandsEnv',
            'neural_workshop.ui.twohands', 'Twohands'),
    Wrapped('overrun', 'Overrun',
            'nwenv.overrun', 'OverrunEnv',
            'neural_workshop.ui.overrun', 'Overrun'),
    Wrapped('marble_maze', 'Marble Maze',
            'nwenv.marblemaze', 'MarbleMazeEnv',
            'neural_workshop.ui.marblemaze', 'MarbleMaze'),
    Wrapped('count', 'Count',
            'nwenv.counting', 'CountingEnv',
            'neural_workshop.ui.counting', 'Counting'),
    Wrapped('mr_time', 'Mr. Time',
            'nwenv.mrtime', 'MrTimeEnv',
            'neural_workshop.ui.mrtime', 'MrTime'),
    Wrapped('camera', 'Camera',
            'nwenv.camera', 'CameraEnv',
            'neural_workshop.ui.camera', 'CameraTask'),
    Wrapped('what_next', 'What Happens Next',
            'nwenv.whatnext', 'WhatNextEnv',
            'neural_workshop.ui.whatnext', 'WhatNext'),
    Wrapped('will_it_fall', 'Will It Fall?',
            'nwenv.falls', 'WillItFallEnv',
            'neural_workshop.ui.falls', 'WillItFall'),
    Wrapped('graph_mapping', 'Graph Mapping',
            'nwenv.graphmapping', 'GraphMappingEnv',
            'neural_workshop.ui.graphmapping', 'GraphMapping'),
    Wrapped('matrix_reasoning', 'Matrix Reasoning',
            'nwenv.ravens', 'MatrixReasoningEnv',
            'neural_workshop.ui.ravens', 'MatrixReasoning'),
    Wrapped('hidden_rule', 'Hidden Rule',
            'nwenv.hiddenrule', 'HiddenRuleEnv',
            'neural_workshop.ui.hiddenrule', 'HiddenRule'),
    Wrapped('wiring', 'Hidden Wiring',
            'nwenv.wiring', 'WiringEnv',
            'neural_workshop.ui.wiring', 'Wiring'),
    Wrapped('jigsaw', 'Jigsaw Puzzle',
            'nwenv.jigsaw', 'JigsawEnv',
            'neural_workshop.ui.jigsaw', 'JigsawPuzzle'),
    Wrapped('video_jigsaw', 'Video Jigsaw',
            'nwenv.videojigsaw', 'VideoJigsawEnv',
            'neural_workshop.ui.videojigsaw', 'VideoJigsaw'),
    Wrapped('video_sequence', 'Video Sequence',
            'nwenv.videosequence', 'VideoSequenceEnv',
            'neural_workshop.ui.videosequence', 'VideoSequence'),
    Wrapped('sudoku', 'Sudoku',
            'nwenv.sudoku', 'SudokuEnv',
            'neural_workshop.ui.sudoku', 'Sudoku'),
    Wrapped('go_winning_move', 'Find the Winning Move',
            'nwenv.go', 'GoEnv',
            'neural_workshop.ui.go', 'GoWinningMove'),
    Wrapped('crossed_wires', 'Crossed Wires',
            'nwenv.crossedwires', 'CrossedWiresEnv',
            'neural_workshop.ui.crossedwires', 'CrossedWires'),
    Wrapped('crossword', 'Crossword',
            'nwenv.crossword', 'CrosswordEnv',
            'neural_workshop.ui.crossword', 'Crossword'),
    Wrapped('scrabble', 'Scrabble',
            'nwenv.scrabble', 'ScrabbleEnv',
            'neural_workshop.ui.scrabble', 'Scrabble'),
    Wrapped('scramble', 'Scramble',
            'nwenv.scramble', 'ScrambleEnv',
            'neural_workshop.ui.scramble', 'Scramble'),
    Wrapped('algebra', 'Algebra',
            'nwenv.algebra', 'AlgebraEnv',
            'neural_workshop.ui.algebra', 'Algebra'),
    Wrapped('numberology', 'Numberology',
            'nwenv.numberology', 'NumberologyEnv',
            'neural_workshop.ui.numberology', 'Numberology'),
    Wrapped('syllogism', 'Syllogisms',
            'nwenv.syllogism', 'SyllogismEnv',
            'neural_workshop.ui.syllogism', 'Syllogism'),
    Wrapped('chess', 'Winning Move',
            'nwenv.chess', 'ChessEnv',
            'neural_workshop.ui.chess', 'Chess'),
    Wrapped('verbal_reasoning', 'Verbal Reasoning',
            'nwenv.verbal', 'VerbalReasoningEnv',
            'neural_workshop.ui.verbal', 'VerbalReasoning'),
    Wrapped('signals', 'Signals',
            'nwenv.signals', 'SignalsEnv',
            'neural_workshop.ui.signals', 'Signals'),
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
    Wrapped('you_are_here', '3D Maze',
            'nwenv.youarehere', 'YouAreHereEnv',
            'neural_workshop.ui.youarehere', 'YouAreHere'),
    Wrapped('sokoban_3d', '3D Sokoban',
            'nwenv.sokoban3d', 'Sokoban3DEnv',
            'neural_workshop.ui.sokoban3d', 'Sokoban3D'),
    Wrapped('tetris', 'Freeform Tetris',
            'nwenv.tetris', 'FreeformTetrisEnv',
            'neural_workshop.ui.tetris', 'FreeformTetris'),
    Wrapped('n_in_a_row', 'N-in-a-row',
            'nwenv.ninarow', 'NInARowEnv',
            'neural_workshop.ui.ninarow', 'NInARow'),
    Wrapped('cookie_thief', 'Cookie Thief',
            'nwenv.cookiethief', 'CookieThiefEnv',
            'neural_workshop.ui.cookiethief', 'CookieThief'),
    Wrapped('sonar', 'Sonar',
            'nwenv.sonar', 'SonarEnv',
            'neural_workshop.ui.sonar', 'Sonar'),
    Wrapped('dispatch', 'Dispatch',
            'nwenv.dispatch', 'DispatchEnv',
            'neural_workshop.ui.dispatch', 'Dispatch'),
    Wrapped('gamble', 'Gamble',
            'nwenv.gamble', 'GambleEnv',
            'neural_workshop.ui.gamble', 'Gamble'),
    Wrapped('bluff', 'Bluff',
            'nwenv.bluff', 'BluffEnv',
            'neural_workshop.ui.bluff', 'Bluff'),
    Wrapped('triage', 'Triage',
            'nwenv.triage', 'TriageEnv',
            'neural_workshop.ui.triage', 'Triage'),
    Wrapped('desktop', 'Desktop',
            'nwenv.desktop', 'DesktopEnv',
            'neural_workshop.ui.desktop', 'Desktop'),
    Wrapped('forms', 'Forms',
            'nwenv.forms', 'FormsEnv',
            'neural_workshop.ui.forms', 'Forms'),
    Wrapped('manual', 'Manual',
            'nwenv.manual', 'ManualEnv',
            'neural_workshop.ui.manual', 'Manual'),
    Wrapped('browser', 'Browser',
            'nwenv.browser', 'BrowserEnv',
            'neural_workshop.ui.browser', 'Browser'),
    Wrapped('errands', 'Errands',
            'nwenv.errands', 'ErrandsEnv',
            'neural_workshop.ui.errands', 'Errands'),
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
