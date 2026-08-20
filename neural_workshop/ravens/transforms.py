# -*- coding: utf-8 -*-
"""The routes a rule takes through the grid.

A rule does not apply to cells in reading order. It starts at a set of
*base* cells and walks from each one, changing the shapes a little at
every step: down the columns, along the rows, along a diagonal, or
outward from the top-left corner. The route is what makes a rule
readable — the player finds it by noticing what changes between
neighbours — so it is kept apart from the change itself, and any rule
can be laid on any route.

Each route answers two questions: which cells does it start from, and
from which cell does a given cell take its input.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Sequence, Tuple


class Location(NamedTuple):
    """A cell, by row and column, counting from the top left."""

    row: int
    column: int


class Route:
    """One way of walking the grid.

    ``bases`` are where the walk starts. ``step`` gives the next cell
    from a cell, and stops when it returns to the base it began at.
    ``source`` gives the cell a cell derives from, which is the step
    run backwards.
    """

    name = 'route'

    def __init__(self, rows: int, columns: int) -> None:
        self.rows = rows
        self.columns = columns

    @property
    def bases(self) -> Sequence[Location]:
        raise NotImplementedError

    def step(self, location: Location) -> Location:
        raise NotImplementedError

    def source(self, location: Location) -> Location:
        raise NotImplementedError

    def walk(self, base: Location) -> List[Location]:
        """Every cell reached from ``base``, in order, excluding it.

        The walk is closed — it comes back round to where it started —
        so it is bounded by the grid rather than by trust in ``step``.
        """
        visited: List[Location] = []
        current = self.step(base)
        while current != base and len(visited) < self.rows * self.columns:
            visited.append(current)
            current = self.step(current)
        return visited


class Vertical(Route):
    """Down each column, wrapping back to the top."""

    name = 'down the columns'

    @property
    def bases(self) -> Sequence[Location]:
        return [Location(0, column) for column in range(self.columns)]

    def step(self, location: Location) -> Location:
        return Location((location.row + 1) % self.rows, location.column)

    def source(self, location: Location) -> Location:
        return Location((location.row - 1) % self.rows, location.column)


class Horizontal(Route):
    """Along each row, wrapping back to the left."""

    name = 'along the rows'

    @property
    def bases(self) -> Sequence[Location]:
        return [Location(row, 0) for row in range(self.rows)]

    def step(self, location: Location) -> Location:
        return Location(location.row, (location.column + 1) % self.columns)

    def source(self, location: Location) -> Location:
        return Location(location.row, (location.column - 1) % self.columns)


class DiagonalDown(Route):
    """Down and to the right, wrapping on both edges.

    Starting on the anti-diagonal means the three walks between them
    cover the grid exactly once. That only works on an odd-sided
    square, which is why the routes on offer depend on the grid.
    """

    name = 'down and to the right'

    @property
    def bases(self) -> Sequence[Location]:
        return [Location(self.rows - 1 - column, column)
                for column in range(self.columns)]

    def step(self, location: Location) -> Location:
        return Location((location.row + 1) % self.rows,
                        (location.column + 1) % self.columns)

    def source(self, location: Location) -> Location:
        return Location((location.row - 1) % self.rows,
                        (location.column - 1) % self.columns)


class DiagonalUp(Route):
    """Up and to the right, wrapping on both edges."""

    name = 'up and to the right'

    @property
    def bases(self) -> Sequence[Location]:
        return [Location(column, column) for column in range(self.columns)]

    def step(self, location: Location) -> Location:
        return Location((location.row - 1) % self.rows,
                        (location.column + 1) % self.columns)

    def source(self, location: Location) -> Location:
        return Location((location.row + 1) % self.rows,
                        (location.column - 1) % self.columns)


class CornerOut(Route):
    """One walk from the top-left corner, sweeping the anti-diagonals.

    Every cell is on the single walk, so the change accumulates across
    the whole grid rather than restarting on each row or column. The
    order is the anti-diagonals taken in turn: (0,0), then (1,0) (0,1),
    then (2,0) (1,1) (0,2), and so on.
    """

    name = 'outward from the top-left corner'

    @property
    def bases(self) -> Sequence[Location]:
        return [Location(0, 0)]

    def _order(self) -> List[Location]:
        order: List[Location] = []
        for diagonal in range(self.rows + self.columns - 1):
            for row in range(min(diagonal, self.rows - 1),
                             max(-1, diagonal - self.columns), -1):
                order.append(Location(row, diagonal - row))
        return order

    def step(self, location: Location) -> Location:
        order = self._order()
        return order[(order.index(location) + 1) % len(order)]

    def source(self, location: Location) -> Location:
        order = self._order()
        return order[order.index(location) - 1]


class LogicRoute(Route):
    """Not a walk at all: the four cells a logic rule is seeded from.

    A logic rule fills the rest of the grid by combining two cells
    above or to the left, so it never steps anywhere; it only needs to
    say which cells are given rather than derived.
    """

    name = 'combined from the cells above and to the left'

    @property
    def bases(self) -> Sequence[Location]:
        return [Location(0, 0), Location(0, 1), Location(1, 0),
                Location(1, 1)]

    def step(self, location: Location) -> Location:
        raise NotImplementedError('a logic rule does not walk the grid')

    def source(self, location: Location) -> Location:
        raise NotImplementedError('a logic rule does not walk the grid')


#: The routes a walking rule can take, by name.
ROUTES: Tuple[type, ...] = (Horizontal, Vertical, CornerOut,
                            DiagonalUp, DiagonalDown)

#: The routes that need an odd-sided square grid to cover it exactly.
DIAGONAL_ROUTES: Tuple[type, ...] = (DiagonalUp, DiagonalDown)


def available_routes(rows: int, columns: int) -> Tuple[type, ...]:
    """The routes that make sense on a grid of this shape."""
    if rows == columns and rows % 2 == 1:
        return ROUTES
    return tuple(route for route in ROUTES
                 if route not in DIAGONAL_ROUTES)


def generate_route(rows: int, columns: int, rng: random.Random,
                   kind: type = None) -> Route:
    """One route, named or picked at random from the ones that fit."""
    if kind is None:
        kind = rng.choice(available_routes(rows, columns))
    return kind(rows, columns)
