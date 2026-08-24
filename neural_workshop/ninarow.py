# -*- coding: utf-8 -*-
"""Five-in-a-row positions with one winning move to find.

This is not a game against an opponent.  A position is dealt with both
colours already on the board and the player has one move.  The move is
right when it completes a line of five; every dealt position has exactly
one such cell.  That makes the task a compact visual search rather than a
reaction game, and lets the ladder spend its difficulty on what a person
has to hold in view: the size of the board, the number of pellets, and the
number of nearly-complete lines competing for attention.

The generator is deliberately independent of pyglet.  A position can be
dealt, checked, and used by an agent without a window.  The UI paints the
same flat board the rules module describes, while the environment exposes
one opaque port per cell.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Sequence, Tuple

EMPTY = 0
PLAYER = 1
OPPONENT = -1
WIN_LENGTH = 5
MAX_SIZE = 19
MAX_CELLS = MAX_SIZE * MAX_SIZE

# Four orientations are enough: every line has one of these directions.
DIRECTIONS: Tuple[Tuple[int, int], ...] = (
    (1, 0), (0, 1), (1, 1), (1, -1))

_LINES: dict = {}


class Grade(NamedTuple):
    """One rung of the visual-search ladder."""

    name: str
    size: int
    pellets: int
    #: Number of random board constructions tried before falling back to a
    #: lower-density version of the same rung.
    attempts: int = 80


# The board grows from a tiny tactical pattern to a crowded nineteen.  The
# last three rungs are intentionally much larger: reading every possible
# five-line there is a combinatorial visual search even though the answer is
# still one cell and the rules remain human-readable.
GRADES: Tuple[Grade, ...] = (
    Grade('a line in the open', 5, 8),
    Grade('a second look', 6, 14),
    Grade('two lines crossing', 7, 22),
    Grade('the crowded corner', 9, 34),
    Grade('a board of threats', 11, 48),
    Grade('the long board', 13, 66),
    Grade('the blind side', 15, 86),
    Grade('superhuman', 19, 112),
)


class Puzzle(NamedTuple):
    """A dealt position and its one correct cell."""

    size: int
    pellets: int
    cells: Tuple[int, ...]
    answer: int
    rung: int

    @property
    def area(self) -> int:
        return self.size * self.size

    @property
    def winning_moves(self) -> Tuple[int, ...]:
        """All immediate winning cells, normally the singleton answer."""
        return tuple(winning_moves(self.cells, self.size, PLAYER))


def grade_at(rung: int) -> Grade:
    """Return the nearest grade, clamping values outside the ladder."""
    return GRADES[max(1, min(len(GRADES), int(rung))) - 1]


def _index(size: int, row: int, col: int) -> int:
    return row * size + col


def _inside(size: int, row: int, col: int) -> bool:
    return 0 <= row < size and 0 <= col < size


def line_cells(size: int, row: int, col: int, dr: int, dc: int,
               length: int = WIN_LENGTH) -> Optional[Tuple[int, ...]]:
    """Return one in-bounds line, or ``None`` if it leaves the board."""
    cells = []
    for step in range(length):
        rr, cc = row + dr * step, col + dc * step
        if not _inside(size, rr, cc):
            return None
        cells.append(_index(size, rr, cc))
    return tuple(cells)


def all_lines(size: int, length: int = WIN_LENGTH
              ) -> Tuple[Tuple[int, ...], ...]:
    """Every possible five-cell line on a square board."""
    key = (int(size), int(length))
    if key in _LINES:
        return _LINES[key]
    found = []
    for row in range(size):
        for col in range(size):
            for dr, dc in DIRECTIONS:
                line = line_cells(size, row, col, dr, dc, length)
                if line is not None:
                    found.append(line)
    _LINES[key] = tuple(found)
    return _LINES[key]


def winner(cells: Sequence[int], size: int, player: int = PLAYER,
           length: int = WIN_LENGTH) -> bool:
    """Whether *player* occupies a complete line."""
    return any(all(cells[cell] == player for cell in line)
               for line in all_lines(size, length))


def winning_moves(cells: Sequence[int], size: int, player: int = PLAYER,
                  length: int = WIN_LENGTH) -> List[int]:
    """Every empty cell that gives *player* an immediate line."""
    found = set()
    for line in all_lines(size, length):
        if sum(cells[cell] == player for cell in line) != length - 1:
            continue
        empty = [cell for cell in line if cells[cell] == EMPTY]
        if len(empty) == 1:
            found.add(empty[0])
    return sorted(found)


def _safe(cells: Sequence[int], size: int, target: int) -> bool:
    """True when the target is the sole immediate player win."""
    return (not winner(cells, size, PLAYER)
            and not winner(cells, size, OPPONENT)
            and winning_moves(cells, size, PLAYER) == [target])


def _candidate_patterns(size: int) -> List[Tuple[Tuple[int, ...], int, int]]:
    """Patterns with four player pellets and a blocked back end.

    The blocked end matters.  Without it, ``XXXX_`` has the target and the
    empty cell on the other side of the four as two equivalent answers.
    """
    found = []
    for row in range(size):
        for col in range(size):
            for dr, dc in DIRECTIONS:
                line = line_cells(size, row, col, dr, dc)
                before = (row - dr, col - dc)
                after = (row + dr * WIN_LENGTH,
                         col + dc * WIN_LENGTH)
                if line is None:
                    continue
                # On a five-by-five board the line fills the whole axis, so
                # neither end has an in-board blocker.  That is still a
                # unique answer: the other end of XXXX_ is outside the
                # board.  On larger boards block whichever end is available.
                if _inside(size, *before):
                    blocked = _index(size, *before)
                elif _inside(size, *after):
                    blocked = _index(size, *after)
                else:
                    blocked = -1
                found.append((line, blocked, line[-1]))
    return found


def _try_deal(size: int, pellets: int, rng: random.Random,
              patterns: Sequence[Tuple[Tuple[int, ...], int, int]]) \
        -> Optional[Puzzle]:
    line, blocked, target = rng.choice(patterns)
    cells = [EMPTY] * (size * size)
    if blocked >= 0:
        cells[blocked] = OPPONENT
    for cell in line[:-1]:
        cells[cell] = PLAYER

    # The pattern itself accounts for four player pellets and one blocker.
    # Add noise one pellet at a time, retaining only positions that cannot
    # accidentally create a winner or a second answer.
    want = max(5, min(int(pellets), size * size - 1))
    order = list(range(size * size))
    rng.shuffle(order)
    placed = sum(value != EMPTY for value in cells)
    for cell in order:
        if placed >= want:
            break
        if cells[cell] != EMPTY or cell == target:
            continue
        # Prefer the opponent at the hard end: it creates visual threats
        # without making the player's answer a trivial four-in-a-row count.
        value = OPPONENT if rng.random() < 0.62 else PLAYER
        cells[cell] = value
        if winner(cells, size, value) or (
                value == PLAYER and winning_moves(cells, size, PLAYER)
                != [target]):
            cells[cell] = EMPTY
            continue
        placed += 1

    if placed < want or not _safe(cells, size, target):
        return None
    return Puzzle(size, placed, tuple(cells), target, 0)


def generate(rung: int, seed: Optional[int] = None,
             size: Optional[int] = None,
             pellets: Optional[int] = None) -> Optional[Puzzle]:
    """Deal a deterministic position with exactly one winning cell.

    ``size`` and ``pellets`` are optional overrides used by experiments and
    tests.  Normal play takes both from the rung.  A very crowded arbitrary
    board may not admit a unique answer; in that case the function returns
    ``None`` rather than quietly dealing a position with a different rule.
    """
    grade = grade_at(rung)
    board_size = max(WIN_LENGTH, min(MAX_SIZE,
                                     int(grade.size if size is None else size)))
    count = grade.pellets if pellets is None else int(pellets)
    count = max(5, min(board_size * board_size - 1, count))
    rng = random.Random(seed)
    patterns = _candidate_patterns(board_size)
    for _attempt in range(max(1, grade.attempts)):
        made = _try_deal(board_size, count, rng, patterns)
        if made is not None:
            return Puzzle(made.size, made.pellets, made.cells, made.answer,
                          max(1, min(len(GRADES), int(rung))))
    return None


def cell_row_col(cell: int, size: int) -> Tuple[int, int]:
    """Convert a flat cell id to ``(row, column)``."""
    return divmod(int(cell), int(size))


def cell_index(row: int, col: int, size: int) -> int:
    """Convert ``(row, column)`` to a flat cell id."""
    return _index(int(size), int(row), int(col))


def render_symbol(value: int) -> str:
    """Human-readable board symbol, useful to text diagnostics."""
    return 'X' if value == PLAYER else 'O' if value == OPPONENT else '.'


def board_text(puzzle: Puzzle) -> str:
    """Render a puzzle as compact ASCII for tests and debugging."""
    return '\n'.join(''.join(render_symbol(value)
                      for value in puzzle.cells[row * puzzle.size:
                                                (row + 1) * puzzle.size])
                     for row in range(puzzle.size))


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Print one dealt position when run as a small diagnostic."""
    args = list(argv or ())
    rung = int(args[0]) if args else 1
    puzzle = generate(rung, seed=1)
    if puzzle is None:
        print('could not deal a unique position')
        return 1
    print(board_text(puzzle))
    print('answer=%d row=%d col=%d' % (
        puzzle.answer, puzzle.answer // puzzle.size,
        puzzle.answer % puzzle.size))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
