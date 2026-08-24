# -*- coding: utf-8 -*-
"""Go rules and generated one-move tactical problems.

The first four rungs teach the last-liberty pattern on a marked group. The
upper six remove the mark and put several White groups in atari: only the
move capturing the largest group wins. Every generated board is checked for
legal groups, legal solutions, and a unique best move before it is returned.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

Point = Tuple[int, int]
Board = Tuple[Tuple[int, ...], ...]


@dataclass(frozen=True)
class Difficulty:
    size: int
    target_size: int
    decoy_sizes: Tuple[int, ...]
    clutter: float
    show_target: bool
    show_move: bool = False


# Near ties at the top turn a local atari scan into a whole-board comparison.
DIFFICULTIES: Tuple[Difficulty, ...] = (
    Difficulty(5, 1, (), .00, True, True),
    Difficulty(5, 2, (), .03, True),
    Difficulty(7, 3, (), .06, True),
    Difficulty(9, 5, (1,), .08, True),
    Difficulty(9, 6, (4, 2), .10, False),
    Difficulty(13, 8, (6, 3), .13, False),
    Difficulty(13, 10, (8, 6, 3), .16, False),
    Difficulty(19, 12, (10, 8, 6, 3), .18, False),
    Difficulty(19, 15, (14, 11, 8, 5, 2), .20, False),
    Difficulty(19, 24, (23, 20, 16, 12, 8, 4), .23, False),
)


@dataclass(frozen=True)
class GoProblem:
    size: int
    board: Board
    target: frozenset[Point]
    winning_move: Point
    difficulty: int
    capture_goal: int
    capture_options: int
    show_target: bool
    show_move: bool

    @property
    def objective(self) -> str:
        return 'marked' if self.show_target else 'largest'


def neighbours(point: Point, size: int) -> Iterator[Point]:
    x, y = point
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if 0 <= nx < size and 0 <= ny < size:
            yield nx, ny


def group(board: Sequence[Sequence[int]], start: Point) -> Set[Point]:
    size = len(board)
    x, y = start
    if not (0 <= x < size and 0 <= y < size):
        return set()
    colour = board[y][x]
    if colour not in (1, 2):
        return set()
    found = {start}
    todo = [start]
    while todo:
        point = todo.pop()
        for nxt in neighbours(point, size):
            if nxt not in found and board[nxt[1]][nxt[0]] == colour:
                found.add(nxt)
                todo.append(nxt)
    return found


def liberties(board: Sequence[Sequence[int]], stones: Iterable[Point]) -> Set[Point]:
    size = len(board)
    return {nxt for stone in stones for nxt in neighbours(stone, size)
            if board[nxt[1]][nxt[0]] == 0}


def groups(board: Sequence[Sequence[int]], colour: Optional[int] = None
           ) -> Iterator[Set[Point]]:
    seen: Set[Point] = set()
    for y, row in enumerate(board):
        for x, held in enumerate(row):
            point = (x, y)
            if not held or point in seen or (colour and held != colour):
                continue
            stones = group(board, point)
            seen.update(stones)
            yield stones


def legal_position(board: Sequence[Sequence[int]]) -> bool:
    """Whether every stone belongs to a group with at least one liberty."""
    size = len(board)
    return (size > 0 and all(len(row) == size for row in board)
            and all(value in (0, 1, 2) for row in board for value in row)
            and all(liberties(board, stones) for stones in groups(board)))


def play(board: Sequence[Sequence[int]], point: Point,
         colour: int = 1) -> Optional[Board]:
    """Return the board after a legal move, or ``None``.

    Ko is irrelevant to these static one-move positions. Occupancy, captures,
    and suicide use normal Go rules.
    """
    if colour not in (1, 2) or not board:
        return None
    size = len(board)
    x, y = point
    if not (0 <= x < size and 0 <= y < size) or board[y][x]:
        return None
    result = [list(row) for row in board]
    result[y][x] = colour
    opponent = 3 - colour
    checked: Set[Point] = set()
    for nxt in neighbours(point, size):
        if result[nxt[1]][nxt[0]] != opponent or nxt in checked:
            continue
        enemy = group(result, nxt)
        checked.update(enemy)
        if not liberties(result, enemy):
            for ex, ey in enemy:
                result[ey][ex] = 0
    own = group(result, point)
    if not liberties(result, own):
        return None
    return tuple(tuple(row) for row in result)


def stone_count(board: Sequence[Sequence[int]], colour: int) -> int:
    return sum(row.count(colour) for row in board)


def capture_moves(board: Sequence[Sequence[int]], colour: int = 1
                  ) -> Dict[Point, int]:
    """All legal capturing moves, mapped to the number removed."""
    before = stone_count(board, 3 - colour)
    found: Dict[Point, int] = {}
    for y, row in enumerate(board):
        for x, held in enumerate(row):
            if held:
                continue
            after = play(board, (x, y), colour)
            if after is None:
                continue
            captured = before - stone_count(after, 3 - colour)
            if captured:
                found[(x, y)] = captured
    return found


def _grown_shape(rng: random.Random, size: int, amount: int) -> Set[Point]:
    """A compact but irregular connected polyomino."""
    start = (rng.randrange(size), rng.randrange(size))
    shape = {start}
    frontier = list(neighbours(start, size))
    while len(shape) < amount and frontier:
        # Prefer points with more neighbours in the shape, with enough noise
        # to keep the groups winding and visually unlike one another.
        scored = [(sum(n in shape for n in neighbours(p, size))
                   + rng.random() * 1.4, p) for p in frontier]
        point = max(scored)[1]
        frontier.remove(point)
        shape.add(point)
        for nxt in neighbours(point, size):
            if nxt not in shape and nxt not in frontier:
                frontier.append(nxt)
    return shape


def _place_atari_group(rng: random.Random, board: List[List[int]],
                       amount: int, forbidden: Set[Point]
                       ) -> Optional[Tuple[Set[Point], Point]]:
    size = len(board)
    for _ in range(700):
        shape = _grown_shape(rng, size, amount)
        if len(shape) != amount or shape & forbidden:
            continue
        boundary = {n for stone in shape for n in neighbours(stone, size)
                    if n not in shape}
        if len(boundary) < 2 or boundary & forbidden:
            continue
        liberty = rng.choice(tuple(boundary))
        footprint = shape | boundary
        if any(board[y][x] for x, y in footprint):
            continue
        for x, y in shape:
            board[y][x] = 2
        for x, y in boundary - {liberty}:
            board[y][x] = 1
        forbidden.update(footprint)
        return shape, liberty
    return None


def _add_clutter(rng: random.Random, board: List[List[int]],
                 forbidden: Set[Point], density: float) -> None:
    size = len(board)
    wanted = int(size * size * density)
    choices = [(x, y) for y in range(size) for x in range(size)
               if not board[y][x] and (x, y) not in forbidden]
    rng.shuffle(choices)
    added = 0
    for point in choices:
        if added >= wanted:
            break
        x, y = point
        # Isolated stones add noise without merging two sized candidates.
        if any(board[ny][nx] for nx, ny in neighbours(point, size)):
            continue
        board[y][x] = rng.choice((1, 2))
        added += 1


def generate_problem(seed: int, difficulty: int = 1) -> GoProblem:
    """Generate and fully validate one problem for *difficulty* (1..10)."""
    rng = random.Random(seed)
    difficulty = max(1, min(len(DIFFICULTIES), int(difficulty)))
    profile = DIFFICULTIES[difficulty - 1]
    candidate_sizes = (profile.target_size,) + profile.decoy_sizes
    for _ in range(300):
        board = [[0] * profile.size for _ in range(profile.size)]
        forbidden: Set[Point] = set()
        placed: List[Tuple[Set[Point], Point]] = []
        for amount in candidate_sizes:
            made = _place_atari_group(rng, board, amount, forbidden)
            if made is None:
                break
            placed.append(made)
        if len(placed) != len(candidate_sizes):
            continue
        _add_clutter(rng, board, forbidden, profile.clutter)
        frozen: Board = tuple(tuple(row) for row in board)
        if not legal_position(frozen):
            continue
        captures = capture_moves(frozen)
        winning = placed[0][1]
        if captures.get(winning) != profile.target_size:
            continue
        best = max(captures.values(), default=0)
        best_moves = [point for point, amount in captures.items()
                      if amount == best]
        if best != profile.target_size or best_moves != [winning]:
            continue
        if difficulty <= 3 and len(captures) != 1:
            continue
        if difficulty >= 5 and len(captures) < len(candidate_sizes):
            continue
        return GoProblem(
            profile.size, frozen, frozenset(placed[0][0]), winning,
            difficulty, best, len(captures), profile.show_target,
            profile.show_move)
    raise RuntimeError('could not generate a valid Go problem')


__all__ = [
    'Board', 'DIFFICULTIES', 'Difficulty', 'GoProblem', 'Point',
    'capture_moves', 'generate_problem', 'group', 'groups', 'legal_position',
    'liberties', 'neighbours', 'play', 'stone_count',
]
