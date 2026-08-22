#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The tasks wrapped on TaskEnv, and the one thing that has to be true of each.

A wrapper is worth very little on its own. What matters is that a run
through it produces outcomes a third party could check, so each of these
plays its task and requires that it was actually paid — and that the scalar
it was paid came off the pixels rather than out of the task's own state.

Two classes, because there are two ways to show it and they are not
the same claim.

:class:`RandomPlayIsPaid` walks in and hits ports. That covers most of
the workshop and it is the honest test, because it is what a learner
that has understood nothing does on its first run: if the boundary
only pays a task that is being played well, a learner starting from
nothing is never paid at all and never starts.

:class:`PlayedProperlyItIsPaid` is for the five where random play
genuinely cannot finish — a sudoku, a jigsaw, a memory board, and the
two mazes. Nothing is wrong with those wrappers; the tasks simply have
no accidental solutions. They are driven with a policy that knows the
answer, through the same ports a learner would use, and the outcome is
still read off the frame.

Sokoban gets more than either, because wrapping it turned up something
the task had been quietly doing to people all along: a box pushed into a
pocket can never come out, and until now the screen said nothing. A
learner could sit in a position it could not win and could not leave,
and be paid nothing for the rest of the episode. The deadlock tests are
about that.

These bind shared-memory segments, so they run one environment at a time.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import UI_IMPORT_ERROR, close_overlays, key, reset_window

if UI_IMPORT_ERROR is None:
    from neural_workshop import maze as M
    from neural_workshop import sokoban as S
    from neural_workshop import state
    from neural_workshop import youarehere as Y
    from neural_workshop.ui.sokoban import SokobanTask
    from nwenv import catalog
    from nwenv.crossedwires import CrossedWiresEnv
    from nwenv.frames import capture_rgba
    from nwenv.graphmapping import DIFFERENT, SAME
    from nwenv.inthedark import InTheDarkEnv
    from nwenv.lookout import COLOR_CHANNEL, FORM_CHANNEL
    from nwenv.maze import MazeEnv
    from nwenv.outcome import derive_public_outcome
    from nwenv.recognition import NEW, SEEN
    from nwenv.removals import RemovalsEnv
    from nwenv.sokoban import SokobanEnv

needs_ui = unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))

#: A level that can be killed, and a walk that kills it. Found by
#: tests/find_dead_seed.py rather than guessed at.
LEVEL_SEED, WALK_SEED = 4, 0

#: Tasks a run of random ports reaches a verdict on, and how many steps
#: it takes at the easiest setting each one offers. Measured with
#: tests/drive_env.py rather than guessed at, then given room.
BY_LUCK = {
    'monkey_ladder': (600, {}),
    'in_the_dark': (2000, {'rung': 1, 'trials': 2, 'seconds': 0.2}),
    'fog_of_war': (400, {}),
    'removals': (2000, {'rung': 1, 'trials': 2, 'seconds': 0.2}),
    'recognition': (400, {}),
    'reflex': (400, {}),
    'ncup_monte': (900, {'cups': 3, 'max_cups': 3}),
    'moving_targets': (1500, {}),
    'lookout': (900, {}),
    'pursuit': (1500, {'seconds': 10}),
    'out_of_sight': (900, {}),
    'count': (900, {}),
    'graph_mapping': (600, {}),
    'matrix_reasoning': (400, {}),
    'crossed_wires': (700, {'rung': 1, 'rounds': 3}),
    'tower_of_hanoi': (2000, {'disks': 3}),
    'salesman': (600, {}),
    'sokoban': (2500, {'rung': 1, 'trials': 3}),
    'sokoban_3d': (1500, {'rung': 1, 'trials': 3}),
    'chain_of_custody': (900, {'rung': 3, 'trials': 4}),
    'cookie_thief': (900, {'rung': 4, 'trials': 4}),
}


def played(env, steps, seed=0):
    """Play *env* at random and collect what it paid."""
    rng = random.Random(seed)
    scalars = []
    try:
        for _step in range(steps):
            _obs, events, done = env.step(rng.randrange(env.n_actions))
            scalars += [e['scalar'] for e in events
                        if e.get('type') == 'outcome']
            if done:
                break
    finally:
        env.close()
    return scalars


def driven(env, moves, steps=4000):
    """Play *env* by *moves*, a callable handed the task each step."""
    scalars = []
    try:
        for _step in range(steps):
            _obs, events, done = env.step(moves(env.task))
            scalars += [e['scalar'] for e in events
                        if e.get('type') == 'outcome']
            if done or scalars:
                break
    finally:
        env.close()
    return scalars


@needs_ui
class RandomPlayIsPaid(unittest.TestCase):
    """A run through the boundary produces outcomes, and they are +1/-1."""

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def check(self, task_id):
        steps, dials = BY_LUCK[task_id]
        env = catalog.env_class(task_id)(seed=0, **dials)
        scalars = played(env, steps)
        self.assertTrue(scalars, '%s was never paid in %d steps'
                                 % (task_id, steps))
        for scalar in scalars:
            self.assertIn(scalar, (1.0, -1.0), task_id)

    def test_removals(self):
        self.check('removals')

    def test_in_the_dark(self):
        self.check('in_the_dark')

    def test_crossed_wires(self):
        self.check('crossed_wires')

    def test_sokoban(self):
        self.check('sokoban')

    def test_sokoban_3d(self):
        self.check('sokoban_3d')

    def test_recognition(self):
        self.check('recognition')

    def test_reflex(self):
        self.check('reflex')

    def test_ncup_monte(self):
        self.check('ncup_monte')

    def test_lookout(self):
        self.check('lookout')

    def test_count(self):
        self.check('count')

    def test_graph_mapping(self):
        self.check('graph_mapping')

    def test_matrix_reasoning(self):
        self.check('matrix_reasoning')

    def test_salesman(self):
        self.check('salesman')

    def test_chain_of_custody(self):
        self.check('chain_of_custody')

    def test_cookie_thief(self):
        self.check('cookie_thief')


@needs_ui
class PlayedProperlyItIsPaid(unittest.TestCase):
    """The five with no accidental solutions, driven by one that knows.

    Every one of these goes in through the same ports a learner uses.
    The policy knows the answer; the boundary does not, and still reads
    the verdict off the frame.
    """

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_a_solved_maze_is_paid(self):
        env = MazeEnv(seed=0, rung=1, trials=2)
        plan = []

        def moves(task):
            if not plan:
                # The route names cells, starting with the one already
                # stood on, so the walk is the gaps between them.
                plan.extend(M.route(task.maze))
            here = task.walker
            while plan and plan[0] == here:
                plan.pop(0)
            step = plan.pop(0) if plan else here
            wide = task.maze.width
            return MazeEnv.action_table.index(
                (step % wide - here % wide, step // wide - here // wide))

        self.assertEqual(driven(env, moves), [1.0])

    def test_a_walked_first_person_maze_is_paid(self):
        env = catalog.env_class('you_are_here')(seed=0, rung=1, trials=2)
        plan = []

        def moves(task):
            if not plan:
                plan.extend(Y.route(task.maze))
            return (Y.AHEAD, Y.BACK, Y.LEFT, Y.RIGHT).index(plan.pop(0))

        self.assertEqual(driven(env, moves), [1.0])

    def test_a_solved_sudoku_is_paid(self):
        """Steered to each blank and filled in with the right digit."""
        from nwenv import sudoku as sudoku_env
        env = catalog.env_class('sudoku')(seed=0, rung=1, trials=2)

        def moves(task):
            size = task.size()
            wanted = next((cell for cell, value in enumerate(task.filled)
                           if value != task.puzzle.solution[cell]), None)
            if wanted is None:
                return 0
            if task.at != wanted:
                dx = wanted % size - task.at % size
                dy = wanted // size - task.at // size
                if dy:
                    return sudoku_env.STEPS.index((0, 1 if dy > 0 else -1))
                return sudoku_env.STEPS.index((1 if dx > 0 else -1, 0))
            return len(sudoku_env.STEPS) + task.puzzle.solution[wanted] - 1

        self.assertEqual(driven(env, moves), [1.0])

    def test_a_solved_jigsaw_is_paid(self):
        """Swapped tile by tile into place, which is also the minimum."""
        env = catalog.env_class('jigsaw')(seed=0, side=2, puzzles=2)

        def moves(task):
            wrong = next((where for where, tile in enumerate(task.order)
                          if tile != where), 0)
            if task.picked is None:
                return wrong
            return task.order.index(task.picked)

        self.assertEqual(driven(env, moves), [1.0])

    def test_the_right_box_delivered_right_is_paid(self):
        """Driven by one that knows which box was ringed."""
        import oracle_custody as O
        from neural_workshop import custody as C
        env = catalog.env_class('chain_of_custody')(seed=0, rung=5, trials=2)

        def moves(task):
            core = C.core_of(task.boxes, task.layout)
            action = O.choose(task.boxes, core, task.held, task.claw,
                              task.layout)
            return {O.LEFT: 0, O.RIGHT: 1, O.GRAB: 2,
                    O.DROP: 2, O.WAIT: 3}[action]

        self.assertEqual(driven(env, moves), [1.0])

    def test_a_cleared_memory_board_is_paid(self):
        """Played by one that remembers, which is what green means here."""
        env = catalog.env_class('concentration')(seed=0, pairs=4, peek_ms=0)

        def moves(task):
            if task.flipped:
                first = task.flipped[0]
                return next(where for where, card in enumerate(task.cards)
                            if card is not first and card.index == first.index)
            return next(where for where, card in enumerate(task.cards)
                        if not card.matched)

        self.assertEqual(driven(env, moves), [1.0])


@needs_ui
class TheWordsTheTasksUseAreTheWordsTheWrappersUse(unittest.TestCase):
    """Three wrappers spell an answer rather than index one.

    They spell it out rather than importing it, because importing a UI
    module from the boundary pulls pyglet's window in before the
    headless options are set. That leaves two spellings of one string,
    and two spellings drift.
    """

    def test_graph_mapping(self):
        from neural_workshop.ui import graphmapping
        self.assertEqual((SAME, DIFFERENT),
                         (graphmapping.SAME, graphmapping.DIFFERENT))

    def test_recognition(self):
        from neural_workshop.ui import recognition
        self.assertEqual((SEEN, NEW), (recognition.SEEN, recognition.NEW))

    def test_lookout(self):
        from neural_workshop.ui import lookout
        self.assertEqual((COLOR_CHANNEL, FORM_CHANNEL),
                         (lookout.COLOR_CHANNEL, lookout.FORM_CHANNEL))


@needs_ui
class TheBoundaryKnowsWhichTasksHaveAClock(unittest.TestCase):
    """Ticking a task with no clock would be inventing one."""

    def clocked(self, task_id):
        return bool(catalog.env_class(task_id).clocked)

    def test_the_turn_based_ones_are_not_ticked(self):
        for task_id in ('crossed_wires', 'maze', 'sokoban', 'sudoku',
                        'tower_of_hanoi', 'salesman', 'jigsaw',
                        'you_are_here', 'sokoban_3d'):
            self.assertFalse(self.clocked(task_id), task_id)

    def test_the_ones_that_move_on_their_own_are(self):
        for task_id in ('removals', 'in_the_dark', 'ncup_monte',
                        'moving_targets', 'lookout', 'pursuit', 'reflex',
                        'count', 'recognition', 'matrix_reasoning',
                        'graph_mapping', 'concentration',
                        'chain_of_custody', 'cookie_thief'):
            self.assertTrue(self.clocked(task_id), task_id)

    def test_the_ports_are_the_ones_the_task_has(self):
        self.assertEqual(MazeEnv.ports, 4)
        self.assertEqual(SokobanEnv.ports, 4)
        self.assertEqual(RemovalsEnv.ports, 5)
        self.assertEqual(InTheDarkEnv.ports, 5)
        self.assertEqual(CrossedWiresEnv.ports, 8)


@needs_ui
class DenseShapingOnlyPaintsWhereItIsPaid(unittest.TestCase):
    """A per-move label must not be read as the trial's own verdict.

    Two tasks paint a consequence after every move, and the accounting
    that pays one per action is the neutral-outcomes one. Built the
    plain way, the sparse path pays the *first* verdict it finds and
    calls it the trial's — so a warmer/colder label a few steps into a
    round scored the round, and a run of random actions came out
    looking like a run of skilled ones.

    Measured before the gate existed: Chain of Custody scored 44%
    against a 38% guessing floor, all of it earned by claw moves that
    happened to close a distance, and the 3D Maze was paid a +1 on a
    maze random play had not solved.
    """

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def dense_tasks(self):
        return [row.task_id for row in catalog.CATALOG
                if getattr(catalog.env_class(row.task_id), 'dense', False)]

    def test_there_are_some(self):
        """Or the rest of this class is checking nothing."""
        for task_id in ('you_are_here', 'chain_of_custody', 'cookie_thief',
                        'maze', 'concentration'):
            self.assertIn(task_id, self.dense_tasks())

    def test_the_plain_build_leaves_the_per_move_label_off(self):
        for task_id in self.dense_tasks():
            env = catalog.env_class(task_id)(seed=0)
            try:
                self.assertFalse(env.paying_densely, task_id)
                self.assertFalse(env.task.coach, task_id)
            finally:
                env.close()

    def test_a_runtime_build_turns_it_on(self):
        for task_id in self.dense_tasks():
            env = catalog.env_class(task_id)(seed=0, neutral_outcomes=True)
            try:
                self.assertTrue(env.paying_densely, task_id)
                self.assertTrue(env.task.coach, task_id)
            finally:
                env.close()

    def test_asking_for_it_off_keeps_it_off(self):
        for task_id in self.dense_tasks():
            env = catalog.env_class(task_id)(seed=0, neutral_outcomes=True,
                                             coach=False)
            try:
                self.assertFalse(env.task.coach, task_id)
            finally:
                env.close()

    def test_random_play_is_not_paid_for_a_maze_it_did_not_solve(self):
        """The symptom, on the task where it is unmistakable."""
        env = catalog.env_class('you_are_here')(seed=0, rung=4, trials=2)
        self.assertEqual(played(env, 900), [])


@needs_ui
class SokobanSaysWhenALevelIsDead(unittest.TestCase):
    """The thing wrapping it turned up, which was a bug for people too."""

    def setUp(self):
        # Hermetic, like every other UI class here: an overlay left
        # registered by an earlier test draws its batch over this
        # one's, and a stale verdict on top of a fresh level is
        # exactly the failure these tests are about.
        close_overlays()
        self.task = SokobanTask()
        self.task.total_trials = 3
        self.task.adaptive = False
        self.task.start_rung = self.task.rung = 3
        # Pinned, because the task deals from an unseeded generator and
        # only some levels can be pushed into a pocket at all. Under
        # this pair the walk below kills it in fourteen actions; left
        # random, half these tests would pass on the luck of the deal.
        self.task.rng.seed(LEVEL_SEED)
        self.task.start_run()

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def scalar(self):
        """What a third party holding only the frame would derive."""
        window = state.window
        window.switch_to()
        window.dispatch_events()
        self.task.on_draw()
        width, height, rgba = capture_rgba(window)
        outcome = derive_public_outcome(rgba, width, height, ['x'], 1)
        return None if outcome is None else outcome['scalar']

    def kill_it(self):
        """Push at random until the level is provably lost."""
        rng = random.Random(WALK_SEED)
        for _try in range(4000):
            if self.task.phase == 'lost':
                return True
            if self.task.phase != 'pushing':
                return False
            self.task.step(*((0, -1), (0, 1), (-1, 0),
                             (1, 0))[rng.randrange(4)])
        return False

    def test_a_fresh_level_is_not_called_dead(self):
        level = self.task.level
        self.assertFalse(S.deadlocked(level.width, level.height, level.walls,
                                      level.goals, level.boxes))
        self.assertEqual(self.task.phase, 'pushing')

    def test_a_level_pushed_into_a_pocket_says_so(self):
        self.assertTrue(self.kill_it(), 'no seed reached a dead position')
        self.assertEqual(self.task.phase, 'lost')
        level = self.task.level
        self.assertTrue(S.deadlocked(level.width, level.height, level.walls,
                                     level.goals, self.task.boxes))

    def test_a_dead_level_reads_as_a_loss_off_the_pixels(self):
        """Which is the whole point: the scalar comes from the frame."""
        self.assertTrue(self.kill_it())
        self.assertEqual(self.scalar(), -1.0)

    def test_a_dead_level_is_not_counted_as_solved(self):
        self.assertTrue(self.kill_it())
        tally = self.task.score()
        self.assertEqual(tally['solved'], 0)
        self.assertEqual(tally['lost'], 1)

    def test_space_deals_on_from_a_dead_level(self):
        """Otherwise it is an absorbing state, which is what it was."""
        self.assertTrue(self.kill_it())
        was = self.task.level
        self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.phase, 'pushing')
        self.assertIsNot(self.task.level, was)

    def test_the_verdict_goes_down_when_the_next_level_opens(self):
        self.assertTrue(self.kill_it())
        self.assertEqual(self.scalar(), -1.0)
        self.task.on_key_press(key.SPACE, 0)
        self.assertIsNone(self.scalar())


if __name__ == '__main__':
    unittest.main()
