# -*- coding: utf-8 -*-
"""The world behind the fog: corridors, a place to stand, and what is seen.

A fog-of-war world is a braided maze with the dead ends mostly opened
back up, which is what turns a puzzle into somewhere to walk around:
loops mean there is more than one way anywhere, so exploring is a
matter of covering ground rather than of solving a tree.

What the module is careful about is the *seeing*. :func:`visible`
answers only "which cells are within reach of the eye from here", and
it answers it from the grid alone — never from where the walker has
been, never from anything the walker knows. Everything about
remembering what was seen belongs to the screen, and everything about
what it was worth belongs to the pixels.

The grid and the walls are indexed the same way
:mod:`neural_workshop.maze` indexes them, and the corridor helpers are
taken from there rather than written again; the only thing this module
carves for itself is a rectangle, because a fog world is wider than it
is tall and a maze is square.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import FrozenSet, NamedTuple, Optional, Set, Tuple

from .maze import DIRECTIONS, adjacency, braid, cell_of, reachable

#: Rooms across and down, which lay out a ``2n+1`` grid: 25 by 15.
#: Wider than tall because a screen is, and because a walker that can
#: get lost in two directions unequally has more to remember.
ROOMS_ACROSS, ROOMS_DOWN = 12, 7

#: How many of the dead ends are opened back into the world. Far higher
#: than the maze uses, and for the opposite reason: a maze wants the
#: route to be a choice, and a world wants there to be no route at all
#: to speak of — just ground, connected every which way.
OPENNESS = 0.85

#: How far the eye reaches, in cells. Small enough that most of the
#: world is dark at any moment, large enough that a step is worth
#: taking: at two cells the eye holds thirteen of the three hundred
#: and seventy five.
DEFAULT_RADIUS = 2


class World(NamedTuple):
    """A grid, its walls, and where the walker starts."""

    width: int
    height: int
    walls: FrozenSet[int]
    start: int

    def open_cells(self) -> FrozenSet[int]:
        """Every cell that is floor rather than wall."""
        return frozenset(cell for cell in range(self.width * self.height)
                         if cell not in self.walls)

    def walkable(self, cell: int) -> bool:
        """Whether *cell* is on the grid and not a wall."""
        return (0 <= cell < self.width * self.height
                and cell not in self.walls)


def carve(rooms_x: int, rooms_y: int,
          rng: random.Random) -> Tuple[int, int, Set[int]]:
    """A perfect maze on a *rooms_x* by *rooms_y* lattice of corridors.

    The depth-first backtracker, as in :mod:`neural_workshop.maze`, and
    rectangular where that one is square. Returns the grid size and the
    cells that came out as corridor.
    """
    width, height = 2 * rooms_x + 1, 2 * rooms_y + 1
    open_cells: Set[int] = set()
    here = (rng.randrange(rooms_x), rng.randrange(rooms_y))
    seen = {here}
    open_cells.add(cell_of(width, 2 * here[0] + 1, 2 * here[1] + 1))
    stack = [here]
    while stack:
        x, y = stack[-1]
        fresh = [(x + dx, y + dy) for dx, dy in DIRECTIONS
                 if 0 <= x + dx < rooms_x and 0 <= y + dy < rooms_y
                 and (x + dx, y + dy) not in seen]
        if not fresh:
            stack.pop()
            continue
        nx, ny = rng.choice(fresh)
        seen.add((nx, ny))
        open_cells.add(cell_of(width, x + nx + 1, y + ny + 1))   # the wall
        open_cells.add(cell_of(width, 2 * nx + 1, 2 * ny + 1))
        stack.append((nx, ny))
    return width, height, open_cells


def visible(world: World, at: int, radius: int) -> FrozenSet[int]:
    """The cells the eye reaches from *at*, walls among them.

    A plain disc: a cell is in view when it is within *radius* cells as
    the crow flies. Walls do not cast shadows, which is a real choice
    and not an oversight — a walker can see the far side of a wall it
    cannot reach, so seeing a place and getting to it stay separate
    problems, and the only way to see *more* is still to go somewhere.
    """
    if not 0 <= at < world.width * world.height:
        return frozenset()
    at_x, at_y = at % world.width, at // world.width
    reach = max(0, int(radius))
    seen = set()
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            if dx * dx + dy * dy > reach * reach:
                continue
            x, y = at_x + dx, at_y + dy
            if 0 <= x < world.width and 0 <= y < world.height:
                seen.add(y * world.width + x)
    return frozenset(seen)


def generate(seed: Optional[int] = None, rooms_x: int = ROOMS_ACROSS,
             rooms_y: int = ROOMS_DOWN, openness: float = OPENNESS) -> World:
    """A world under *seed*: same seed, same walls, same starting cell.

    The walker is stood on a floor cell that can reach every other one.
    Braiding this hard almost always leaves the floor in one piece, but
    "almost always" is not a guarantee worth resting a run on, so the
    largest connected piece is what the walker is put in and what the
    rest of the world is measured against.
    """
    rng = random.Random(seed)
    width, height, open_set = carve(rooms_x, rooms_y, rng)
    braid(width, height, open_set, openness, rng)
    open_cells = frozenset(open_set)
    links = adjacency(width, height, open_cells)

    start = rng.choice(sorted(open_cells))
    room = reachable(links, start)
    if len(room) < len(open_cells):
        # Whatever the braiding left stranded is walled off again, so
        # the world the walker sees is the world the walker can walk.
        open_cells = room
    walls = frozenset(cell for cell in range(width * height)
                      if cell not in open_cells)
    return World(width=width, height=height, walls=walls, start=start)


def coverage(world: World, seen: FrozenSet[int]) -> float:
    """What share of the walkable world *seen* covers."""
    floor = world.open_cells()
    if not floor:
        return 0.0
    return len(seen & floor) / float(len(floor))
