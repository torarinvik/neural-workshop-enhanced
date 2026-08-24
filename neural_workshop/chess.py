# -*- coding: utf-8 -*-
"""Procedural, engine-verified mate-in-one positions.

Every returned puzzle passes three checks in :mod:`python-chess`: the
position is legal, the advertised move is legal, and it is the position's
only move that gives checkmate. Difficulty adds both material and legal
alternatives, so the upper rungs are visually and tactically denser.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import List, Optional, Tuple

import chess as chesslib


@dataclass(frozen=True)
class Puzzle:
    fen: str
    move: str
    hint: str
    alternatives: int


# Small legal mating motifs. These are seeds, not dealt puzzles: generation
# reflects/transposes them, may swap the players, and adds independently
# validated decoy material.
MOTIFS: Tuple[str, ...] = (
    '7k/8/5KQ1/8/8/8/8/8 w - - 0 1',
    '6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1',
    '4k3/8/5K2/8/1Q6/8/8/8 w - - 0 1',
    '6k1/8/6K1/8/8/8/8/R7 w - - 0 1',
    '6k1/3R4/6K1/8/8/B7/8/8 w - - 0 1',
    '7k/7B/6K1/6N1/8/8/8/8 w - - 0 1',
    '8/8/8/5QK1/8/8/4N3/7k w - - 0 1',
)

TRANSFORMS: Tuple[Tuple, ...] = (
    (),
    (chesslib.flip_horizontal,),
    (chesslib.flip_vertical,),
    (chesslib.flip_diagonal,),
    (chesslib.flip_anti_diagonal,),
    (chesslib.flip_diagonal, chesslib.flip_horizontal),
    (chesslib.flip_diagonal, chesslib.flip_vertical),
    (chesslib.flip_horizontal, chesslib.flip_vertical),
)

DECOYS: Tuple[int, ...] = (
    chesslib.PAWN, chesslib.PAWN, chesslib.KNIGHT, chesslib.BISHOP,
    chesslib.ROOK, chesslib.QUEEN,
)


def mating_moves(board: chesslib.Board) -> List[chesslib.Move]:
    """All legal moves that end the game immediately by checkmate."""
    mates: List[chesslib.Move] = []
    for move in board.legal_moves:
        board.push(move)
        if board.is_checkmate():
            mates.append(move)
        board.pop()
    return mates


def _transformed(rng: random.Random) -> chesslib.Board:
    board = chesslib.Board(rng.choice(MOTIFS))
    for transform in rng.choice(TRANSFORMS):
        board = board.transform(transform)
    if rng.randrange(2):
        # mirror() swaps colours and ranks, producing a Black-to-move puzzle.
        board = board.mirror()
    board.clear_stack()
    return board


def _add_decoy(board: chesslib.Board, rng: random.Random) -> bool:
    """Try to add one piece without changing the unique mating answer."""
    if len(mating_moves(board)) != 1:
        return False
    empty = list(chesslib.SquareSet(~board.occupied & chesslib.BB_ALL))
    rng.shuffle(empty)
    for square in empty[:24]:
        piece_type = rng.choice(DECOYS)
        if (piece_type == chesslib.PAWN
                and chesslib.square_rank(square) in (0, 7)):
            continue
        color = bool(rng.randrange(2))
        candidate = board.copy(stack=False)
        candidate.set_piece_at(square, chesslib.Piece(piece_type, color))
        if (not candidate.is_valid() or candidate.is_check()
                or candidate.is_game_over()):
            continue
        mates = mating_moves(candidate)
        if len(mates) != 1 or mates[0].promotion is not None:
            continue
        board.set_piece_at(square, chesslib.Piece(piece_type, color))
        return True
    return False


def _candidate(level: int, rng: random.Random) -> Optional[Puzzle]:
    board = _transformed(rng)
    if not board.is_valid() or board.is_check() or board.is_game_over():
        return None
    mates = mating_moves(board)
    if len(mates) != 1:
        return None

    # The first two levels stay sparse. At level ten as many as fourteen
    # independently checked decoys surround the mating pattern.
    wanted = max(0, round((level - 1) * 14 / 9))
    added = 0
    attempts = 0
    while added < wanted and attempts < wanted * 10 + 8:
        attempts += 1
        if _add_decoy(board, rng):
            added += 1

    mates = mating_moves(board)
    if len(mates) != 1:
        return None
    move = mates[0]
    return Puzzle(
        fen=board.fen(),
        move=move.uci(),
        hint=board.san(move),
        alternatives=board.legal_moves.count(),
    )


def generate(level: int, rng: Optional[random.Random] = None) -> Puzzle:
    """Generate a legal position with exactly one mate in one.

    Several candidates are sampled and the denser search tree is preferred
    on higher rungs. Generation is deterministic when *rng* is seeded.
    """
    rng = rng or random.Random()
    level = max(1, min(10, int(level)))
    wanted = 2 + level // 3
    candidates: List[Puzzle] = []
    attempts = 0
    while len(candidates) < wanted and attempts < 64:
        attempts += 1
        puzzle = _candidate(level, rng)
        if puzzle is not None:
            candidates.append(puzzle)
    if not candidates:
        raise RuntimeError('could not generate a unique legal mate in one')
    candidates.sort(key=lambda p: p.alternatives)
    span = max(1, len(candidates) // 2)
    pool = candidates[:span] if level <= 3 else candidates[-span:]
    return rng.choice(pool)


def validate(puzzle: Puzzle) -> bool:
    """Whether a generated puzzle fulfils the public one-move promise."""
    board = chesslib.Board(puzzle.fen)
    mates = mating_moves(board)
    return (
        board.is_valid()
        and len(mates) == 1
        and mates[0].uci() == puzzle.move
        and puzzle.alternatives == board.legal_moves.count()
    )


__all__ = ['MOTIFS', 'Puzzle', 'generate', 'mating_moves', 'validate']
