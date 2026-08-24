"""Rules and generation checks for the Go winning-move task."""
import unittest

from neural_workshop.go import generate_problem, play


class GoProblemTests(unittest.TestCase):
    def test_each_difficulty_has_a_legal_unique_capture(self):
        for difficulty in range(1, 11):
            problem = generate_problem(9000 + difficulty, difficulty)
            self.assertIn(problem.size, (5, 9, 13, 19))
            after = play(problem.board, problem.winning_move, 1)
            self.assertIsNotNone(after)
            self.assertTrue(all(after[y][x] == 0
                                for x, y in problem.target))
            captures = []
            for y, row in enumerate(problem.board):
                for x, stone in enumerate(row):
                    if not stone and play(problem.board, (x, y), 1):
                        result = play(problem.board, (x, y), 1)
                        if sum(r.count(2) for r in result) < sum(r.count(2) for r in problem.board):
                            captures.append((x, y))
            self.assertEqual(captures, [problem.winning_move])

    def test_suicide_is_illegal(self):
        board = ((0, 1, 0), (1, 0, 1), (0, 1, 0))
        self.assertIsNone(play(board, (1, 1), 1))


if __name__ == '__main__':
    unittest.main()
