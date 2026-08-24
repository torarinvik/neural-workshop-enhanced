# -*- coding: utf-8 -*-
"""Small Go engine and guaranteed one-move capture problems.

The task is deliberately a tsumego-style question, not a full game: the
position is already in progress and Black must find the move that captures
the marked White group immediately.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple

Point = Tuple[int, int]


@dataclass(frozen=True)
class GoProblem:
    size: int
    board: Tuple[Tuple[int, ...], ...]
    target: frozenset[Point]
    winning_move: Point
    difficulty: int


def neighbours(point: Point, size: int) -> Iterable[Point]:
    x, y = point
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if 0 <= nx < size and 0 <= ny < size:
            yield nx, ny


def group(board: Sequence[Sequence[int]], start: Point) -> Set[Point]:
    size = len(board)
    colour = board[start[1]][start[0]]
    if not colour:
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


def liberties(board: Sequence[Sequence[int]], stones: Set[Point]) -> Set[Point]:
    size = len(board)
    return {nxt for stone in stones for nxt in neighbours(stone, size)
            if board[nxt[1]][nxt[0]] == 0}


def play(board: Sequence[Sequence[int]], point: Point,
         colour: int = 1) -> Optional[Tuple[Tuple[int, ...], ...]]:
    """Return the position after a legal move, or ``None`` for suicide."""
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


def generate_problem(seed: int, difficulty: int = 1) -> GoProblem:
    """Generate a legal, solvable position with one marked group in atari.

    Difficulty increases the board, target size, and amount of distracting
    legal play. The target is always the only opponent group with one liberty,
    so there is exactly one winning point to discover.
    """
    rng = random.Random(seed)
    difficulty = max(1, min(10, int(difficulty)))
    size = 5 if difficulty <= 2 else 9 if difficulty <= 5 else 13 if difficulty <= 8 else 19
    target_size = 1 if difficulty <= 2 else min(2 + difficulty // 3, 5)
    for _ in range(500):
        board = [[0] * size for _ in range(size)]
        # Start with a compact target group and a single empty liberty.
        tx = rng.randrange(1, size - 1)
        ty = rng.randrange(1, size - 1)
        target = {(tx, ty)}
        for _ in range(target_size - 1):
            options = [p for stone in target for p in neighbours(stone, size)
                       if not board[p[1]][p[0]] and p not in target]
            if not options:
                break
            target.add(rng.choice(options))
        if len(target) != target_size:
            continue
        for x, y in target:
            board[y][x] = 2
        target_libs = liberties(board, target)
        if len(target_libs) < 2:
            continue
        winning = rng.choice(tuple(target_libs))
        # Fill the target's other liberties with Black, but retain enough
        # breathing room that these stones do not accidentally self-capture.
        for x, y in target_libs - {winning}:
            board[y][x] = 1
        # Add neutral clutter away from the target. Harder rungs are denser.
        density = 0.05 + difficulty * 0.025
        for y in range(size):
            for x in range(size):
                if board[y][x] or (x, y) == winning:
                    continue
                if rng.random() < density:
                    board[y][x] = rng.choice((1, 2))
        board[winning[1]][winning[0]] = 0
        result = play(board, winning, 1)
        if result is None or any(result[y][x] for x, y in target):
            continue
        # Keep generated positions unambiguous: only the target may be in
        # atari, and no other move may capture any White stone.
        captures = []
        for y in range(size):
            for x in range(size):
                if board[y][x] or (x, y) == winning:
                    continue
                after = play(board, (x, y), 1)
                if after is not None and sum(row.count(2) for row in after) < sum(row.count(2) for row in board):
                    captures.append((x, y))
        if captures:
            continue
        return GoProblem(size, tuple(tuple(row) for row in board),
                         frozenset(target), winning, difficulty)
    raise RuntimeError('could not generate a Go capture problem')


__all__ = ['GoProblem', 'Point', 'generate_problem', 'group', 'liberties',
           'neighbours', 'play']
