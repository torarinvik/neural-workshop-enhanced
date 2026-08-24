#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The procedural chess task and its engine contract."""
from __future__ import annotations

import random
import unittest

import chess

from neural_workshop.chess import generate, mating_moves, validate
from uisupport import Chess, close_overlays, needs_ui


class ChessGeneratorTests(unittest.TestCase):
    def test_every_level_generates_unique_legal_mates(self):
        rng = random.Random(9182)
        for level in range(1, 11):
            for _ in range(12):
                puzzle = generate(level, rng)
                board = chess.Board(puzzle.fen)
                mates = mating_moves(board)
                self.assertTrue(validate(puzzle), (level, puzzle))
                self.assertEqual([move.uci() for move in mates],
                                 [puzzle.move])
                board.push(mates[0])
                self.assertTrue(board.is_checkmate())

    def test_generation_is_reproducible_from_the_agent_seed(self):
        first = [generate(level, random.Random(42))
                 for level in range(1, 11)]
        second = [generate(level, random.Random(42))
                  for level in range(1, 11)]
        self.assertEqual(first, second)

    def test_upper_levels_are_materially_denser(self):
        low_rng = random.Random(71)
        high_rng = random.Random(72)
        low = [len(chess.Board(generate(1, low_rng).fen).piece_map())
               for _ in range(12)]
        high = [len(chess.Board(generate(10, high_rng).fen).piece_map())
                for _ in range(12)]
        self.assertGreater(min(high), max(low))

    def test_generation_varies_positions_and_the_side_to_move(self):
        rng = random.Random(88)
        puzzles = [generate(10, rng) for _ in range(30)]
        self.assertEqual(len({puzzle.fen for puzzle in puzzles}), 30)
        self.assertEqual(
            {chess.Board(puzzle.fen).turn for puzzle in puzzles},
            {chess.WHITE, chess.BLACK})


@needs_ui
class ChessScreenTests(unittest.TestCase):
    def setUp(self):
        self.task = Chess()
        self.task.start_run()

    def tearDown(self):
        close_overlays()

    def test_illegal_move_does_not_spend_the_puzzle(self):
        before = self.task.position.fen()
        mover = next(square for square in chess.SQUARES
                     if self.task.position.color_at(square)
                     == self.task.position.turn)
        self.assertFalse(self.task.answer(mover, mover))
        self.assertEqual(self.task.phase, 'solving')
        self.assertEqual(self.task.position.fen(), before)
        self.assertEqual(self.task.results, [])

    def test_engine_verified_move_really_checkmates(self):
        move = chess.Move.from_uci(self.task.puzzle.move)
        self.assertTrue(self.task.answer(move.from_square, move.to_square))
        self.assertEqual(self.task.phase, 'solved')
        self.assertTrue(self.task.position.is_checkmate())


if __name__ == '__main__':
    unittest.main()
