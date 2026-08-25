"""Rules, ladder, and generation checks for Find the Winning Move."""
import unittest

from uisupport import close_overlays, key, needs_ui, reset_window

from neural_workshop import display, state
from neural_workshop.go import (DIFFICULTIES, capture_moves,
                                generate_problem, legal_position, play)
from neural_workshop.ui import taskoptions
from neural_workshop.ui.go import GoWinningMove
from neural_workshop.ui.taskoptions import TaskOptions
from nwenv.go import GoEnv


class GoRulesTests(unittest.TestCase):
    def test_suicide_is_illegal(self):
        board = ((0, 2, 0), (2, 0, 2), (0, 2, 0))
        self.assertIsNone(play(board, (1, 1), 1))

    def test_a_capture_that_would_otherwise_be_suicide_is_legal(self):
        board = ((0, 1, 0), (1, 2, 1), (0, 0, 0))
        after = play(board, (1, 2), 1)
        self.assertIsNotNone(after)
        self.assertEqual(after[1][1], 0)

    def test_occupied_and_out_of_bounds_moves_are_illegal(self):
        board = ((1, 0), (0, 0))
        self.assertIsNone(play(board, (0, 0), 2))
        self.assertIsNone(play(board, (-1, 0), 1))
        self.assertIsNone(play(board, (2, 0), 1))


class GoProblemTests(unittest.TestCase):
    def test_the_ladder_reaches_nineteen_with_near_tied_decoys(self):
        easiest, hardest = DIFFICULTIES[0], DIFFICULTIES[-1]
        self.assertEqual((easiest.size, easiest.target_size), (5, 1))
        self.assertTrue(easiest.show_move)
        self.assertEqual(hardest.size, 19)
        self.assertFalse(hardest.show_target)
        self.assertEqual(hardest.target_size - hardest.decoy_sizes[0], 1)
        self.assertGreaterEqual(len(hardest.decoy_sizes), 6)

    def test_every_level_is_legal_and_has_one_best_move(self):
        for difficulty in range(1, 11):
            for seed in range(12):
                problem = generate_problem(1000 * difficulty + seed,
                                           difficulty)
                captures = capture_moves(problem.board)
                self.assertTrue(legal_position(problem.board))
                self.assertEqual(problem.size,
                                 DIFFICULTIES[difficulty - 1].size)
                self.assertEqual(captures[problem.winning_move],
                                 problem.capture_goal)
                best = max(captures.values())
                self.assertEqual(
                    [point for point, count in captures.items()
                     if count == best],
                    [problem.winning_move])
                self.assertEqual(problem.capture_options, len(captures))

    def test_difficulty_is_clamped(self):
        self.assertEqual(generate_problem(1, -99).difficulty, 1)
        self.assertEqual(generate_problem(1, 99).difficulty, 10)


class GoEnvironmentTests(unittest.TestCase):
    def test_the_environment_difficulty_reaches_the_dealer(self):
        env = GoEnv(seed=7, difficulty=10, trials=1)
        try:
            self.assertEqual(env.task.problem.difficulty, 10)
            self.assertEqual(env.task.problem.size, 19)
        finally:
            env.close()

    def test_the_winning_port_paints_a_positive_outcome(self):
        env = GoEnv(seed=8, difficulty=6, trials=1)
        try:
            problem = env.task.problem
            x, y = problem.winning_move
            observation, _events, _done = env.step(
                y * problem.size + x)
            self.assertEqual(observation['outcome']['scalar'], 1.0)
        finally:
            env.close()


@needs_ui
class GoOptionsTests(unittest.TestCase):
    """The settings screen, which this task shipped without.

    It was in the hub from the day it was added and in ``TASK_SPECS``
    from nowhere, so ``C`` did nothing, the level could only be set
    with the number keys on the ready screen, and the run length could
    not be set at all. ``test_ui_tasks`` caught the registry half of
    that; these cover the half a registry cannot see — that the rows
    are wired to the attributes the task and the boundary both use.
    """

    def setUp(self):
        close_overlays()
        self.saved = (state.cfg.GO_LEVEL, state.cfg.GO_TRIALS)

    def tearDown(self):
        close_overlays()
        reset_window()
        state.cfg.GO_LEVEL, state.cfg.GO_TRIALS = self.saved

    def test_the_hub_can_open_a_settings_screen_for_it(self):
        self.assertTrue(taskoptions.has_options('go_winning_move'))

    def test_the_rows_reach_the_task(self):
        state.cfg.GO_LEVEL, state.cfg.GO_TRIALS = 4, 3
        task = GoWinningMove()
        self.assertEqual(task.start_difficulty, 4)
        self.assertEqual(task.total_trials, 3)
        task.start_run()
        self.assertEqual(task.difficulty, 4)

    def test_c_opens_it_and_applying_lands_on_the_task(self):
        state.cfg.GO_LEVEL, state.cfg.GO_TRIALS = 2, 5
        task = GoWinningMove()
        task.start_run()
        task.on_key_press(key.C, 0)
        panels = [screen for screen in display.open_overlays()
                  if isinstance(screen, TaskOptions)]
        self.assertTrue(panels, 'C did not open the options screen')
        state.cfg.GO_LEVEL, state.cfg.GO_TRIALS = 7, 15
        panels[0].applied = True
        panels[0].close()
        self.assertEqual(task.start_difficulty, 7)
        self.assertEqual(task.total_trials, 15)
        # Applying puts the run back rather than leaving a position up
        # that was dealt at the old level.
        self.assertEqual(task.phase, 'ready')

    def test_the_rows_write_what_the_boundary_reads(self):
        """The options screen and the agent boundary aim at one pair.

        ``GoEnv.knobs`` and this screen both set ``start_difficulty``
        and ``total_trials``. Renaming one without the other leaves a
        row that silently does nothing, which is the shape of the bug
        this whole class is here about.
        """
        state.cfg.GO_LEVEL, state.cfg.GO_TRIALS = 6, 2
        task = GoWinningMove()
        for attribute in GoEnv.knobs.values():
            self.assertTrue(hasattr(task, attribute), attribute)
        self.assertEqual(set(GoEnv.knobs.values()),
                         {'start_difficulty', 'total_trials'})

    def test_the_level_row_covers_the_whole_ladder(self):
        rows = {option.key: option
                for option in taskoptions.GO_WINNING_MOVE.options}
        self.assertEqual(tuple(rows['GO_LEVEL'].values),
                         tuple(range(1, len(DIFFICULTIES) + 1)))

    def test_the_note_reads_at_every_level(self):
        note = taskoptions.GO_WINNING_MOVE.note
        for level in range(1, len(DIFFICULTIES) + 1):
            text = note({'GO_LEVEL': level, 'GO_TRIALS': 10})
            self.assertTrue(text)
            self.assertNotIn('None', text)

    def test_the_note_fits_on_a_small_window(self):
        """A note is only useful if you can read the end of it.

        The screen puts the note under the rows and lets it wrap, with
        nothing below it to stop it running off the bottom edge. At
        640x480 that budget is about 370 characters, and the first
        draft of this note spent 430 at the top of the ladder — the
        last line and a half were simply not on the screen.

        Asserted for this task rather than for all of them because it
        is *not* currently true of all of them: measured at 640x480,
        ten shipping notes overflow, 3D Sokoban's by 139 pixels. That
        is a layout limitation older than this task and a wider fix
        than this test; what is in scope here is not adding an
        eleventh.
        """
        from neural_workshop import geometry
        for wide, tall in ((640, 480), (800, 600), (1024, 768)):
            geometry.set_window_size(wide, tall)
            for level in range(1, len(DIFFICULTIES) + 1):
                state.cfg.GO_LEVEL, state.cfg.GO_TRIALS = level, 10
                panel = taskoptions.open_task_options('go_winning_move')
                try:
                    bottom = panel.note.y - panel.note.content_height
                finally:
                    panel.close()
                self.assertGreaterEqual(
                    bottom, 0,
                    'at %dx%d the level %d note runs %d pixels off the '
                    'bottom' % (wide, tall, level, -bottom))

    def test_the_footnote_says_the_key_exists(self):
        task = GoWinningMove()
        self.assertIn('C', task.footnote.text)


if __name__ == '__main__':
    unittest.main()
