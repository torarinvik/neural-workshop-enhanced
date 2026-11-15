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

:class:`PlayedProperlyItIsPaid` is for the ones where random play
never earns a green — a sudoku, a jigsaw, a memory board, the two
mazes, and the three word games, where random tiles spell nothing and
random letters are not the answer. Most of those are never paid at
all. Scramble is the exception and is in both classes: one of its
ports is submit, so random play is paid on every trial and every one
of them is a red. Nothing is wrong with those wrappers; the tasks simply have
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
    from nwenv.mrtime import MrTimeEnv
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
    # Paid on every wire and paid nothing but red, and the reason is
    # the clock rather than the ports: a wire ends on its own when the
    # time is up whether or not the loop got anywhere, so the cost of
    # not getting anywhere arrives without anything having to go wrong.
    # Driven with a short clock because the ladder's own is eighteen
    # seconds -- a thousand ticks, which is longer than this sweep.
    # No walk flies a wire, so the green is in PlayedProperlyItIsPaid.
    'buzz_wire': (900, {'rung': 1, 'trials': 4, 'seconds': 4}),
    'out_of_sight': (900, {}),
    'count': (900, {}),
    # Paid on nearly every trial and paid mostly red, for the same
    # reason Scramble is: one port is submit and one port is *now*, so
    # a nonsense answer given is a nonsense answer marked. Measured at
    # the bottom rung, where the band is a quarter of the interval and
    # a random number lands inside it about one time in five — which
    # is why there is a green in the tally at all. The green that
    # means something is in PlayedProperlyItIsPaid, both halves of it.
    'mr_time': (900, {'rung': 1, 'trials': 6}),
    'graph_mapping': (600, {}),
    'matrix_reasoning': (400, {}),
    'crossed_wires': (700, {'rung': 1, 'rounds': 3}),
    'tower_of_hanoi': (2000, {'disks': 3}),
    'salesman': (600, {}),
    'sokoban': (2500, {'rung': 1, 'trials': 3}),
    'sokoban_3d': (1500, {'rung': 1, 'trials': 3}),
    'chain_of_custody': (900, {'rung': 3, 'trials': 4}),
    'cookie_thief': (900, {'rung': 4, 'trials': 4}),
    # Paid on every road, and paid nothing but red on any of them: a
    # press starts a crossing it cannot call off, so a coin a tick is a
    # car across the middle most of the time and the first donkey in
    # either lane ends the road. Zero is a real floor here rather than a
    # gap in the test, and it is measured in tests/test_donkey.py. A
    # longer budget than the other clocked tasks because a road is four
    # ticks a drawn row.
    'donkey': (1500, {'rung': 1, 'trials': 4}),
    # Paid, and paid nothing but red: random tilting walks a marble
    # into a hole or runs the clock out, and neither is a green.
    #
    # A ten-second tray rather than the rung's own fifty-five, which is
    # what makes this reliable rather than merely likely. Random play
    # loses a marble down a hole on about six trays in ten; on the rest
    # the tray is decided by its clock, so a budget past the clock is
    # paid on *every* tray instead of on most of them. The same option
    # is on the player's screen, so this is a shorter tray rather than
    # a different task.
    #
    # The green is in PlayedProperlyItIsPaid, in
    # tests/test_ui_marblemaze.py, where a policy that knows the route
    # flies a tray home through these same four ports.
    'marble_maze': (900, {'rung': 4, 'trials': 2, 'adaptive': False,
                          'seconds': 10}),
    # Paid on every road, and the floor here is not zero: five of the
    # eleven ports do not touch the wheel at all, so a uniform port is
    # a hold five times in eleven and the car spends most of a road
    # going straight in first gear. That clears about a fifth of them
    # on the bottom rung and none from the third, which is measured in
    # tests/test_twohands.py. Driven at the easiest rung, so what this
    # is checking is that the boundary pays rather than that it pays
    # badly.
    'two_hands': (1500, {'rung': 1, 'trials': 4}),
    # Paid on every line and paid nothing but red, for the plainest
    # reason on this list: one port is submit, and a line of gibberish
    # submitted is a line marked. What a learner gets for free here is
    # the cost of a wrong answer; the green is in
    # PlayedProperlyItIsPaid because no walk types a sentence.
    'scramble': (900, {'rung': 1, 'trials': 4}),
    # Same shape as Scramble: one port is submit, so a random string
    # submitted is a random string marked, and every one of them is a
    # red. Arithmetic has no near misses.
    'algebra': (900, {'rung': 1, 'trials': 4}),
    # Paid on every wave and paid nothing but red, and the reason is
    # the clock rather than the ports: a wave ends on its own whether
    # or not anything was typed, so the cost of not keeping up arrives
    # without a submit key to ask for it. Driven at the top rung
    # because that is where a wave is short enough to finish inside the
    # budget — at the first it runs 1,157 ticks and a 900-step sweep
    # reads zero, which is measured in tests/bench_overrun.py. No walk
    # types a sentence, so the green is in PlayedProperlyItIsPaid.
    'overrun': (900, {'rung': 12, 'waves': 6, 'adaptive': False}),
    # Every empty cell is a port and the easiest board has twenty-five
    # cells, so random play is paid often enough to prove the boundary is
    # live while the proper-play test below proves the green path.
    'n_in_a_row': (900, {'rung': 1, 'trials': 4,
                         'grid': 5, 'pellets': 8, 'adaptive': False}),
    # Every port is an answer, so every port a rung offers is a trial
    # settled — and one in three of them is right at the bottom of the
    # ladder. This is the one task on the list where random play gets
    # a green often enough to see, and the rung it is measured at is
    # the reason the ports are a ceiling: twenty-four of the
    # twenty-seven do nothing here.
    'syllogism': (900, {'rung': 1, 'trials': 4}),
    # Every port is an answer here too, and at rung one there are two
    # of them, so random play is a coin and about half its outcomes
    # are green. That is the highest free floor on this list and it is
    # the reason the number is worth writing down: a learning curve
    # drawn on rung-one trivia starts at 50%, and the questions are
    # not answerable from the frame in any case.
    'trivia': (900, {'rung': 1, 'trials': 4}),
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

    def test_mr_time(self):
        self.check('mr_time')

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

    def test_donkey(self):
        self.check('donkey')

    def test_two_hands(self):
        self.check('two_hands')

    def test_scramble(self):
        self.check('scramble')

    def test_algebra(self):
        self.check('algebra')

    def test_syllogism(self):
        self.check('syllogism')

    def test_overrun(self):
        self.check('overrun')

    def test_n_in_a_row(self):
        self.check('n_in_a_row')

    def test_trivia(self):
        self.check('trivia')

    # These six were in BY_LUCK with a measured step budget apiece and
    # no method beside them, so nothing ever played them. Found by the
    # guard below, which is the whole reason it is here.
    def test_monkey_ladder(self):
        self.check('monkey_ladder')

    def test_fog_of_war(self):
        self.check('fog_of_war')

    def test_moving_targets(self):
        self.check('moving_targets')

    def test_pursuit(self):
        self.check('pursuit')

    def test_buzz_wire(self):
        self.check('buzz_wire')

    def test_out_of_sight(self):
        self.check('out_of_sight')

    def test_tower_of_hanoi(self):
        self.check('tower_of_hanoi')

    def test_marble_maze(self):
        self.check('marble_maze')

    def test_every_task_in_by_luck_is_actually_played(self):
        """The list and the methods are two lists, so they can drift.

        They did: an entry added here without a method beside it was
        carried in the table, printed in no report, and ran nothing.
        This is the cheapest possible guard against the next one.
        """
        played_here = {name[len('test_'):] for name in dir(self)
                       if name.startswith('test_')}
        for task_id in BY_LUCK:
            self.assertIn(task_id, played_here,
                          '%s is in BY_LUCK with no test beside it' % task_id)


@needs_ui
class PlayedProperlyItIsPaid(unittest.TestCase):
    """The ones with no accidental solutions, driven by one that knows.

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

    def test_a_flown_buzz_wire_is_paid(self):
        """Flown by the reference pilot, through the same eleven ports.

        Random play never finishes a wire -- eleven ports shoved at
        random leave the loop wandering by the near post -- so the green
        on this task needs a policy that can actually hold a line. The
        pilot reads the true state, which is what makes it a yardstick;
        it presses the same ports a learner would and the boundary still
        reads the verdict off the pixels.
        """
        from neural_workshop import buzzwire as bw
        env = catalog.env_class('buzz_wire')(seed=0, rung=1, trials=2)

        def moves(task):
            if task.hand is None or task.phase != 'flying':
                return 0
            return bw.pilot_port(task.hand)

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
        env = catalog.env_class('jigsaw')(seed=0, pieces=4, puzzles=2)

        def moves(task):
            wrong = next((where for where, tile in enumerate(task.order)
                          if tile != where), 0)
            if task.picked is None:
                return wrong
            return task.order.index(task.picked)

        self.assertEqual(driven(env, moves), [1.0])

    def test_a_solved_crossword_is_paid(self):
        """Steered to each blank and filled in with the right letter."""
        from nwenv import crossword as crossword_env
        env = catalog.env_class('crossword')(seed=0, rung=1, trials=2)

        def moves(task):
            size = task.size()
            wanted = next((cell for cell, letter in enumerate(task.filled)
                           if task.puzzle.solution[cell]
                           and letter != task.puzzle.solution[cell]), None)
            if wanted is None:
                return 0
            if task.at != wanted:
                dx = wanted % size - task.at % size
                dy = wanted // size - task.at // size
                if dy:
                    return crossword_env.STEPS.index((0, 1 if dy > 0 else -1))
                return crossword_env.STEPS.index((1 if dx > 0 else -1, 0))
            return (len(crossword_env.STEPS)
                    + crossword_env.LETTERS.index(
                        task.puzzle.solution[wanted]))

        self.assertEqual(driven(env, moves), [1.0])

    def test_a_reconstructed_sentence_is_paid(self):
        """Typed out one letter at a time, which is all the ports are.

        There is no cursor here and nothing to steer, so a policy that
        knows the sentence has only to spell it — and that is the
        point of the test: twenty-nine ports, forty-odd of them in the
        right order, and one verdict at the end of it.
        """
        from nwenv import scramble as scramble_env
        env = catalog.env_class('scramble')(seed=0, rung=1, trials=2)

        def moves(task):
            wanted = task.deal.answer
            if task.typed == wanted:
                return scramble_env.SUBMIT
            if not wanted.startswith(task.typed):
                return scramble_env.BACK
            following = wanted[len(task.typed)]
            if following == ' ':
                return scramble_env.SPACE
            return scramble_env.LETTERS.index(following)

        self.assertEqual(driven(env, moves), [1.0])

    def test_a_line_typed_away_before_it_runs_out_is_paid(self):
        """The one green in this task, and it is on the top rung.

        Rung twelve rather than rung one on purpose. A policy that can
        read the line types a letter a tick, which is sixty characters
        a second against the 6.95 the hardest rung asks for, so the
        rung it is driven at says nothing about how hard the rung is —
        what it says is that the *clock* cannot stop a boundary that is
        wired up, which is the thing a wrapper for a moving task can
        get wrong and a wrapper for a still one cannot.
        """
        from nwenv import overrun as overrun_env
        env = catalog.env_class('overrun')(seed=0, rung=12, waves=2,
                                           adaptive=False)

        def moves(task):
            word = task._target()
            if not word or not word.startswith(task.typed):
                return overrun_env.BACK
            return overrun_env.LETTERS.index(word[len(task.typed)])

        self.assertEqual(driven(env, moves), [1.0])

    def test_the_winning_cell_is_paid(self):
        """The policy that reads the scenario can answer through one port."""
        env = catalog.env_class('n_in_a_row')(
            seed=0, rung=1, trials=2, grid=5, pellets=8, adaptive=False)
        self.assertEqual(driven(env, lambda task: task.puzzle.answer), [1.0])

    def test_a_worked_out_answer_is_paid(self):
        """Typed a character at a time, on a rung that wants a polynomial.

        Rung seven rather than rung one on purpose: it puts the whole
        marking chain through the ports — parse what was typed, compare
        by canonical form, and check it was actually gathered up — where
        rung one would only prove that two digits arrive.
        """
        from nwenv import algebra as algebra_env
        env = catalog.env_class('algebra')(seed=0, rung=7, trials=2)

        def moves(task):
            # Spaces are not ports and the parser does not need them.
            wanted = task.problem.shown_answer.replace(' ', '')
            if task.typed == wanted:
                return algebra_env.SUBMIT
            if not wanted.startswith(task.typed):
                return algebra_env.BACK
            return algebra_env.KEYS.index(wanted[len(task.typed)])

        self.assertEqual(driven(env, moves), [1.0])

    def test_the_answer_that_follows_is_paid(self):
        """Answered through the ports, on a rung with nine of them live.

        Rung six rather than rung one on purpose: a three-answer rung
        would be passed by a policy that always presses zero one time
        in three, and this one has to find the right index among nine
        that change place with every deal.
        """
        env = catalog.env_class('syllogism')(seed=0, rung=6, trials=2)
        self.assertEqual(driven(env, lambda task: task.question.answer),
                         [1.0])

    def test_the_answer_the_dataset_gives_is_paid(self):
        """Answered through the ports, on a rung with eight of them live.

        Rung seven rather than rung one on purpose: two options would
        be passed half the time by a policy that always presses zero,
        and this one has to find the right index among eight that
        change place with every deal.
        """
        env = catalog.env_class('trivia')(seed=0, rung=7, trials=2)
        self.assertEqual(driven(env, lambda task: task.round.answer), [1.0])

    def test_the_naming_is_a_knob_like_the_others(self):
        """An environment that wants the same task without the belief."""
        from neural_workshop import syllogism
        if not syllogism._pool():
            self.skipTest('no word index on this machine')
        env = catalog.env_class('syllogism')(seed=0, rung=1, trials=1,
                                             real_words=False)
        try:
            env.reset()
            self.assertFalse(env.task.real_words)
            said = ' '.join(env.task.question.lines).split()
            self.assertFalse(set(said) & set(syllogism._pool()), said)
        finally:
            env.close()

    def test_an_answer_no_rung_offers_does_nothing(self):
        """The ports are a ceiling, and the spare ones are silent."""
        env = catalog.env_class('syllogism')(seed=0, rung=1, trials=2)
        try:
            env.reset()
            before = env.task.phase, env.task.choice
            _obs, events, _done = env.step(env.n_actions - 1)
            self.assertEqual((env.task.phase, env.task.choice), before)
            self.assertFalse([one for one in events
                              if one.get('type') == 'outcome'])
        finally:
            env.close()

    def test_the_best_scrabble_play_is_paid(self):
        """Laid tile by tile, in the one order the ports allow.

        The rack ports are positions rather than letters, so a policy
        that knows the word still has to find which slot is holding
        each of its letters — which is the whole reason those ports are
        positions.
        """
        from nwenv import scrabble as scrabble_env
        env = catalog.env_class('scrabble')(seed=0, rung=1, trials=2)

        def moves(task):
            best = task.deal.best
            wanted = [(cell, letter) for cell, letter in best.laid
                      if cell not in dict(task.laid)]
            if not wanted:
                if task.down != best.down:
                    return scrabble_env.TURN
                return scrabble_env.PLAY
            cell, letter = wanted[0]
            size = task.size()
            if task.at != cell:
                dx = cell % size - task.at % size
                dy = cell // size - task.at // size
                if dy:
                    return scrabble_env.STEPS.index((0, 1 if dy > 0 else -1))
                return scrabble_env.STEPS.index((1 if dx > 0 else -1, 0))
            slot = next(at for at, held in enumerate(task.deal.rack)
                        if held == letter and at not in task.spent)
            return len(scrabble_env.STEPS) + slot

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

    def test_an_interval_that_was_actually_timed_is_paid(self):
        """The recall half, answered off the task's own clock.

        The policy reads the interval; the boundary does not, and still
        pays it off the verdict painted on the frame. Typed one digit a
        step through the same ports a learner has — this is the task
        where the composed answer and the timing are the same problem.
        """
        env = MrTimeEnv(seed=0, mode='recall', rung=1, trials=3,
                        adaptive=False)
        plan = []

        def moves(task):
            if task.phase != 'asking':
                del plan[:]
                return 11                       # backspace: a no-op here
            if not plan:
                for character in '%.3f' % task.interval:
                    plan.append(10 if character == '.' else int(character))
                plan.append(12)
            return plan.pop(0)

        self.assertEqual(driven(env, moves), [1.0])

    def test_a_duration_laid_down_on_cue_is_paid(self):
        """The produce half: the action is not what, it is when.

        Nothing on screen changes while the duration runs, so the
        policy counts the driver's own ticks — which is exactly what a
        learner has to do here, and the reason this task cannot be
        played off a single frame.
        """
        env = MrTimeEnv(seed=0, mode='produce', rung=2, trials=3,
                        adaptive=False)

        def moves(task):
            if task.phase != 'counting':
                return 11
            gone = task.clock() - task.appeared_at
            return 13 if gone >= task.target else 11

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
                        'you_are_here', 'sokoban_3d', 'crossword',
                        'scrabble', 'scramble', 'algebra',
                        'n_in_a_row', 'verbal_reasoning', 'camera',
                        'sonar', 'hidden_rule', 'bluff', 'forms', 'wiring', 'gamble', 'triage', 'manual', 'notebook', 'browser', 'will_it_fall', 'signals', 'errands', 'same_or_mirror', 'fold_it', 'point_of_view', 'who_knows_what', 'where_was_it', 'explore_exploit', 'spreadsheet', 'desktop'):
            self.assertFalse(self.clocked(task_id), task_id)

    def test_the_ones_that_move_on_their_own_are(self):
        for task_id in ('removals', 'in_the_dark', 'ncup_monte',
                        'moving_targets', 'lookout', 'pursuit', 'reflex',
                        'buzz_wire',
                        'count', 'recognition', 'matrix_reasoning',
                        'graph_mapping', 'concentration',
                        'chain_of_custody', 'cookie_thief', 'donkey',
                        'two_hands', 'tetris', 'overrun', 'marble_maze',
                        'video_sequence', 'video_jigsaw', 'what_next',
                        'which_is_nearer', 'shape_from_motion', 'stop_and_switch', 'delay', 'lander', 'dispatch'):
            self.assertTrue(self.clocked(task_id), task_id)

    def test_the_ports_are_the_ones_the_task_has(self):
        self.assertEqual(MazeEnv.ports, 4)
        self.assertEqual(SokobanEnv.ports, 4)
        self.assertEqual(RemovalsEnv.ports, 5)
        self.assertEqual(InTheDarkEnv.ports, 5)
        self.assertEqual(CrossedWiresEnv.ports, 8)
        self.assertEqual(catalog.env_class('crossword').ports, 32)
        self.assertEqual(catalog.env_class('scrabble').ports, 14)
        self.assertEqual(catalog.env_class('scramble').ports, 29)
        # Two fewer than Scramble: the words clear themselves, so there
        # is no submit, and the gaps come back with the word before
        # them, so there is no space either.
        self.assertEqual(catalog.env_class('overrun').ports, 27)
        self.assertEqual(catalog.env_class('n_in_a_row').ports, 128 * 128)
        self.assertEqual(catalog.env_class('algebra').ports, 21)
        self.assertEqual(catalog.env_class('verbal_reasoning').ports, 5)
        # Two knobs, two ways each, and nothing else on the boundary.
        self.assertEqual(catalog.env_class('marble_maze').ports, 4)
        # Six for the wheel and five for the sights, out of one budget.
        self.assertEqual(catalog.env_class('two_hands').ports, 11)


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
        for task_id in ('you_are_here', 'chain_of_custody', 'donkey',
                        'cookie_thief', 'two_hands', 'overrun',
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
