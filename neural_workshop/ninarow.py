# -*- coding: utf-8 -*-
"""Five-in-a-row positions with one winning move to find.

This is not a game against an opponent.  A position is dealt with both
colours already on the board and the player has one move.  The move is
right when it completes the dealt line length; every dealt position has
exactly one such cell. That makes the task a compact visual search rather
than a reaction game, and lets the ladder spend its difficulty on what a person
has to hold in view: the size of the board, the number of pellets, and the
number of nearly-complete lines competing for attention.

The generator is deliberately independent of pyglet.  A position can be
dealt, checked, and used by an agent without a window.  The UI paints the
same flat board the rules module describes, while the environment exposes
one opaque port per cell.  Early rungs are approachable three-in-a-row; the
middle returns to classic five-in-a-row, while the upper rungs make both
dimensions large and the required line long, ending in a 100-in-a-row search
that is intended for a program rather than a glance.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Sequence, Tuple

EMPTY = 0
PLAYER = 1
OPPONENT = -1
MIN_LENGTH = 3
WIN_LENGTH = 5
MAX_SIZE = 128
MAX_CELLS = MAX_SIZE * MAX_SIZE

# Four orientations are enough: every line has one of these directions.
DIRECTIONS: Tuple[Tuple[int, int], ...] = (
    (1, 0), (0, 1), (1, 1), (1, -1))

_LINES: dict = {}
_LINES_THROUGH: dict = {}


class Grade(NamedTuple):
    """One rung of the visual-search ladder."""

    name: str
    size: int
    pellets: int
    length: int
    #: Number of random board constructions tried before falling back to a
    #: lower-density version of the same rung.
    attempts: int = 80


# The first rungs are approachable three- and four-in-a-row patterns.  The
# middle is recognisable five-in-a-row. Then the objective itself grows:
# finding the one cell that completes fifteen, forty, or one hundred in a
# row is a different class of search from spotting XXX_.
GRADES: Tuple[Grade, ...] = (
    Grade('three in the open', 5, 7, 3),
    Grade('a second look', 6, 12, 3),
    Grade('four to find', 8, 22, 4),
    Grade('the crowded corner', 12, 45, 5),
    Grade('a board of threats', 16, 80, 5),
    Grade('the long board', 24, 150, 8),
    Grade('the blind side', 32, 300, 15),
    Grade('search horizon', 64, 1200, 40),
    Grade('superhuman', 128, 6000, 100),
)


class Puzzle(NamedTuple):
    """A dealt position and its one correct cell."""

    size: int
    pellets: int
    length: int
    cells: Tuple[int, ...]
    answer: int
    rung: int

    @property
    def area(self) -> int:
        return self.size * self.size

    @property
    def winning_moves(self) -> Tuple[int, ...]:
        """All immediate winning cells, normally the singleton answer."""
        return tuple(winning_moves(self.cells, self.size, PLAYER,
                                   self.length))


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
    """Every possible line of *length* on a square board."""
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


def lines_through(size: int, length: int, cell: int
                  ) -> Tuple[Tuple[int, ...], ...]:
    """The possible lines of *length* that contain one cell.

    The generator uses this local view while adding pellets.  Rechecking
    every line after every pellet is needlessly expensive on the large
    machine-facing rungs; a new winner can only be created on a line that
    contains the newly occupied cell.
    """
    size, length, cell = int(size), int(length), int(cell)
    key = (size, length)
    indexed = _LINES_THROUGH.get(key)
    if indexed is None:
        indexed_lists = [[] for _ in range(size * size)]
        for line in all_lines(size, length):
            for line_cell in line:
                indexed_lists[line_cell].append(line)
        indexed = tuple(tuple(lines) for lines in indexed_lists)
        _LINES_THROUGH[key] = indexed
    return indexed[cell]


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


def _winner_through(cells: Sequence[int], size: int, cell: int,
                    player: int, length: int) -> bool:
    """Whether a move at *cell* has just completed a line."""
    return any(all(cells[line_cell] == player for line_cell in line)
               for line in lines_through(size, length, cell))


def _winning_moves_through(cells: Sequence[int], size: int, cell: int,
                           player: int, length: int) -> List[int]:
    """New immediate wins on lines touched by a newly placed pellet."""
    found = set()
    for line in lines_through(size, length, cell):
        if sum(cells[line_cell] == player for line_cell in line) != length - 1:
            continue
        empty = [line_cell for line_cell in line
                 if cells[line_cell] == EMPTY]
        if len(empty) == 1:
            found.add(empty[0])
    return sorted(found)


def _safe(cells: Sequence[int], size: int, target: int,
          length: int = WIN_LENGTH) -> bool:
    """True when the target is the sole immediate player win."""
    return (not winner(cells, size, PLAYER, length)
            and not winner(cells, size, OPPONENT, length)
            and winning_moves(cells, size, PLAYER, length) == [target])


def _candidate_patterns(size: int, length: int
                        ) -> List[Tuple[Tuple[int, ...], int, int]]:
    """Patterns with ``length - 1`` player pellets and a blocked back end.

    The blocked end matters.  Without it, a line can have two equivalent
    answers at its ends.
    """
    found = []
    for row in range(size):
        for col in range(size):
            for dr, dc in DIRECTIONS:
                line = line_cells(size, row, col, dr, dc, length)
                before = (row - dr, col - dc)
                after = (row + dr * length, col + dc * length)
                if line is None:
                    continue
                # If neither end is on the board, the board edge itself is
                # the blocker. Otherwise block whichever end is available.
                if _inside(size, *before):
                    blocked = _index(size, *before)
                elif _inside(size, *after):
                    blocked = _index(size, *after)
                else:
                    blocked = -1
                found.append((line, blocked, line[-1]))
    return found


def _try_deal(size: int, pellets: int, length: int, rng: random.Random,
              patterns: Sequence[Tuple[Tuple[int, ...], int, int]]) \
        -> Optional[Puzzle]:
    line, blocked, target = rng.choice(patterns)
    cells = [EMPTY] * (size * size)
    if blocked >= 0:
        cells[blocked] = OPPONENT
    for cell in line[:-1]:
        cells[cell] = PLAYER
    want = max(length, min(int(pellets), size * size - 1))

    # A short line can participate in several crossing three- or four-line
    # threats. Close those accidental alternatives before adding noise. The
    # long-line rungs almost never need this, but keeping it here makes the
    # beginner generator honest too: every deal really has one answer.
    placed = sum(value != EMPTY for value in cells)
    for _repair in range(size * size):
        extras = [move for move in winning_moves(cells, size, PLAYER, length)
                  if move != target]
        if not extras:
            break
        repaired = False
        for extra in extras:
            for candidate_line in lines_through(size, length, extra):
                if sum(cells[line_cell] == PLAYER
                       for line_cell in candidate_line) != length - 1:
                    continue
                for blocker_cell in candidate_line:
                    if cells[blocker_cell] != EMPTY or blocker_cell == target:
                        continue
                    cells[blocker_cell] = OPPONENT
                    if not _winner_through(cells, size, blocker_cell,
                                           OPPONENT, length):
                        repaired = True
                        placed += 1
                        break
                    cells[blocker_cell] = EMPTY
                if repaired:
                    break
            if repaired:
                break
        if not repaired:
            return None
    if placed > want:
        return None

    # The pattern itself accounts for length - 1 player pellets and, when
    # needed, one blocker. Add noise one pellet at a time, retaining only
    # positions that cannot accidentally create a winner or a second answer.
    order = list(range(size * size))
    rng.shuffle(order)
    for cell in order:
        if placed >= want:
            break
        if cells[cell] != EMPTY or cell == target:
            continue
        # Prefer the opponent at the hard end: it creates visual threats
        # without making the player's answer a trivial four-in-a-row count.
        value = OPPONENT if rng.random() < 0.62 else PLAYER
        cells[cell] = value
        if _winner_through(cells, size, cell, value, length) or (
                value == PLAYER and any(
                    move != target
                    for move in _winning_moves_through(
                        cells, size, cell, PLAYER, length))):
            cells[cell] = EMPTY
            continue
        placed += 1

    if placed < want or not _safe(cells, size, target, length):
        return None
    return Puzzle(size, placed, length, tuple(cells), target, 0)


def generate(rung: int, seed: Optional[int] = None,
             size: Optional[int] = None,
             pellets: Optional[int] = None,
             length: Optional[int] = None) -> Optional[Puzzle]:
    """Deal a deterministic position with exactly one winning cell.

    ``size``, ``pellets`` and ``length`` are optional overrides used by
    experiments and tests. Normal play takes all three from the rung. A very
    crowded arbitrary board may not admit a unique answer; in that case the
    function returns ``None`` rather than quietly changing the rule.
    """
    grade = grade_at(rung)
    target_length = max(MIN_LENGTH, min(MAX_SIZE,
                                       int(grade.length if length is None
                                           else length)))
    board_size = max(target_length, min(MAX_SIZE,
                                     int(grade.size if size is None else size)))
    count = grade.pellets if pellets is None else int(pellets)
    count = max(MIN_LENGTH, min(board_size * board_size - 1, count))
    count = max(target_length, count)
    rng = random.Random(seed)
    patterns = _candidate_patterns(board_size, target_length)
    for _attempt in range(max(1, grade.attempts)):
        made = _try_deal(board_size, count, target_length, rng, patterns)
        if made is not None:
            return Puzzle(made.size, made.pellets, made.length, made.cells,
                          made.answer,
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
