# -*- coding: utf-8 -*-
"""Pure, window-free checks for Numberology's procedural puzzle contract."""
import unittest

from neural_workshop.numberology import generate, is_correct, sequence_length


class NumberologyGeneratorTests(unittest.TestCase):
    def test_tutorial_sequence(self):
        puzzle = generate(1, seed=123)
        self.assertNotEqual(puzzle.terms, (0, 1, 2, 3))
        self.assertEqual(len(puzzle.terms), 4)
        self.assertEqual(puzzle.answer,
                         puzzle.terms[-1] + (puzzle.terms[1] - puzzle.terms[0]))

    def test_length_grows_with_difficulty(self):
        self.assertLess(sequence_length(1), sequence_length(100))
        self.assertLess(sequence_length(100), sequence_length(10000))
        self.assertEqual(sequence_length(5, requested=17), 17)

    def test_seed_and_difficulty_are_reproducible(self):
        self.assertEqual(generate(37, seed=8), generate(37, seed=8))
        self.assertNotEqual(generate(7, seed=8), generate(37, seed=8))

    def test_answers_are_exact(self):
        puzzle = generate(1000, seed=9)
        self.assertTrue(is_correct(puzzle, str(puzzle.answer)))
        self.assertFalse(is_correct(puzzle, str(puzzle.answer + 1)))
        self.assertFalse(is_correct(puzzle, 'not a number'))

    def test_complexity_grows_across_rule_families(self):
        levels = (1, 2, 3, 4, 5, 6, 7, 12, 40, 1000, 10000)
        complexities = [generate(level, seed=4).complexity
                        for level in levels]
        self.assertEqual(complexities, sorted(complexities))


if __name__ == '__main__':
    unittest.main()
