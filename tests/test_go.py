"""Rules, ladder, and generation checks for Find the Winning Move."""
import unittest

from neural_workshop.go import (DIFFICULTIES, capture_moves,
                                generate_problem, legal_position, play)
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


if __name__ == '__main__':
    unittest.main()
