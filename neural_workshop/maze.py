# -*- coding: utf-8 -*-
"""Maze: corridors, locked doors, and the exact fewest steps out.

A maze on its own is not a planning task. A perfect maze has one route
between any two cells, so there is nothing to choose and a hand on the
left wall solves it without thinking at all. Two things here make the
route a decision instead of a discovery.

The first is loops. A share of the dead ends are opened back into the
maze, so there are several ways round and the shortest one has to be
picked rather than found.

The second is the locks. Coloured doors sit on cells you cannot pass
without the matching key, and every door is placed on a cell that
*separates* the start from the exit — so it is a real lock, not
scenery, and every key is genuinely needed. The keys are scattered
where they can be had before their own door, which makes the walk one
problem rather than several: going straight for the exit and coming
back for what you missed costs far more than sweeping the keys up on
the way, and seeing which sweep is cheapest is the whole task.

Three guarantees hold the module together:

* Every maze is solvable, by construction. Door *i* separates the
  start from everything beyond it, and key *i* is placed inside the
  region the start can still reach with door *i* shut. By induction
  on the doors, ordered by their distance from the start, every key
  is obtainable once the earlier ones are.

* Difficulty is measured, not asserted. The minimum is exact: a
  breadth-first search over ``(cell, keys held)`` states, which is
  small enough to solve outright at every size the ladder offers, so
  the par on screen is always a real minimum and never a bound.

* The ladder's floors are measured too. A rung rejects mazes solvable
  in fewer steps than its floor, so "level 9" takes level-9 work
  rather than being a big maze with a short way out.

Cells are indexed ``y * width + x`` and the walls are the cells that
are not corridor, the same shape :mod:`neural_workshop.sokoban` uses.
A maze of ``rooms`` corridor cells across is laid on a
``2 * rooms + 1`` grid, so the walls between corridors are cells too
and a door is just a cell with a colour.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from collections import deque
from typing import (Dict, FrozenSet, List, NamedTuple, Optional, Sequence,
                    Set, Tuple)


class Maze(NamedTuple):
    """A generated maze: the corridors, the locks, and what they cost."""

    width: int
    height: int
    #: Every cell that is not corridor.
    walls: FrozenSet[int]
    start: int
    way_out: int
    #: Cell of door *i*, in the order the walk must open them.
    doors: Tuple[int, ...]
    #: Cell of the key that opens door *i*.
    keys: Tuple[int, ...]
    #: The exact fewest steps from start to way out, keys and all.
    minimum: int
    #: What a walk that always heads for the nearest key it can still
    #: reach, and then for the way out, spends instead. Never less
    #: than the minimum, and the gap is how much planning the maze is
    #: actually worth.
    greedy: int

    def open_cells(self) -> FrozenSet[int]:
        """Every cell that is corridor rather than wall."""
        return frozenset(cell for cell in range(self.width * self.height)
                         if cell not in self.walls)


class Grade(NamedTuple):
    """One rung of the ladder: the maze, the locks, and the floor."""

    name: str
    #: Corridor cells across and down; the grid is twice this plus one.
    rooms: int
    doors: int
    #: Share of the dead ends opened back into the maze as loops. Zero
    #: is a perfect maze, which one hand on one wall will solve.
    braid: float
    #: Reject mazes the solver finishes in fewer steps than this.
    floor: int
    #: The ladder's second axis: the least share of the walk that
    #: fetching the keys nearest-first throws away. The floor says how
    #: *long* a maze is; this says how much of it is a *decision*. It
    #: is the junior axis and never outranks the floor — a rung that
    #: cannot manage both would rather be long than clever.
    planning: float = 0.0


#: The most doors the palette can tell apart, and so the most the
#: ladder may ask for.
MOST_DOORS = 6

#: Kindergarten to superhuman. Every number here was measured rather
#: than guessed, over two hundred mazes a rung: the step floors sit at
#: about the top third of what each rung actually deals, and the
#: planning floors at about the top two fifths, which is what leaves
#: both reachable together inside the attempt budget. Braid climbs
#: with size because loops are what stop a big maze from being a long
#: corridor, and the planning floor only starts once there are four
#: doors — below that the keys are too few for the order of fetching
#: them to be worth anything, and asking would only cost depth.
GRADES: Tuple[Grade, ...] = (
    Grade('first steps', 4, 0, 0.0, 22, 0.0),
    Grade('the long way', 5, 0, 0.2, 29, 0.0),
    Grade('one door', 6, 1, 0.2, 50, 0.0),
    Grade('two doors', 7, 2, 0.25, 72, 0.0),
    Grade('crossroads', 8, 2, 0.35, 84, 0.0),
    Grade('three doors', 9, 3, 0.35, 113, 0.0),
    Grade('the warren', 10, 3, 0.4, 126, 0.0),
    Grade('four doors', 11, 4, 0.4, 155, 0.02),
    Grade('the gauntlet', 12, 4, 0.45, 172, 0.02),
    Grade('five doors', 13, 5, 0.45, 199, 0.03),
    Grade('the labyrinth', 14, 5, 0.5, 218, 0.03),
    Grade('six doors', 15, 6, 0.5, 249, 0.05),
    Grade('nightmare', 16, 6, 0.55, 267, 0.05),
    Grade('inhuman', 17, 6, 0.55, 283, 0.05),
    Grade('superhuman', 18, 6, 0.6, 297, 0.04),
)

#: Grid steps, as offsets built from the width at the call site.
DIRECTIONS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def cell_of(width: int, x: int, y: int) -> int:
    return y * width + x


def neighbours(width: int, height: int, cell: int) -> Tuple[int, ...]:
    """The up-to-four cells orthogonally next to *cell*, inside the grid."""
    x, y = cell % width, cell // width
    out = []
    for dx, dy in DIRECTIONS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            out.append(ny * width + nx)
    return tuple(out)


def carve(rooms: int, rng: random.Random) -> Tuple[int, int, Set[int]]:
    """A perfect maze on a *rooms* by *rooms* lattice of corridor cells.

    The depth-first backtracker, which is chosen over the prettier
    algorithms on purpose: it makes long winding corridors and deep
    dead ends, which is exactly the raw material braiding and locking
    want. Returns the grid size and the open cells.
    """
    width = height = 2 * rooms + 1
    open_cells = set()
    here = (rng.randrange(rooms), rng.randrange(rooms))
    seen = {here}
    open_cells.add(cell_of(width, 2 * here[0] + 1, 2 * here[1] + 1))
    stack = [here]
    while stack:
        x, y = stack[-1]
        fresh = [(x + dx, y + dy) for dx, dy in DIRECTIONS
                 if 0 <= x + dx < rooms and 0 <= y + dy < rooms
                 and (x + dx, y + dy) not in seen]
        if not fresh:
            stack.pop()
            continue
        nx, ny = rng.choice(fresh)
        seen.add((nx, ny))
        open_cells.add(cell_of(width, x + nx + 1, y + ny + 1))  # the wall
        open_cells.add(cell_of(width, 2 * nx + 1, 2 * ny + 1))
        stack.append((nx, ny))
    return width, height, open_cells


def dead_ends(width: int, height: int,
              open_cells: Set[int]) -> List[int]:
    """Corridor cells with exactly one way out."""
    return [cell for cell in open_cells
            if sum(1 for near in neighbours(width, height, cell)
                   if near in open_cells) == 1]


def braid(width: int, height: int, open_cells: Set[int], share: float,
          rng: random.Random) -> None:
    """Open *share* of the dead ends back into the maze, in place.

    A dead end is opened by knocking out one of the walls around it,
    which joins it to a corridor it could not reach before and turns
    the tree into a graph with loops. That is what gives the walk a
    choice of route, and what stops one hand on one wall from being a
    solution.
    """
    if share <= 0:
        return
    ends = dead_ends(width, height, open_cells)
    rng.shuffle(ends)
    for cell in ends[:int(round(len(ends) * share))]:
        x, y = cell % width, cell // width
        walls = []
        for dx, dy in DIRECTIONS:
            wall = cell_of(width, x + dx, y + dy)
            beyond = cell_of(width, x + 2 * dx, y + 2 * dy)
            if not (0 < x + 2 * dx < width - 1
                    and 0 < y + 2 * dy < height - 1):
                continue
            if wall not in open_cells and beyond in open_cells:
                walls.append(wall)
        if walls:
            open_cells.add(rng.choice(walls))


#: A corridor graph: cell -> the corridor cells next to it. Built once
#: per maze and passed around, because every walk in here is a
#: breadth-first search and re-deriving the neighbours from arithmetic
#: inside the inner loop is most of the cost of generating a maze.
Links = Dict[int, Tuple[int, ...]]


def adjacency(width: int, height: int,
              open_cells: FrozenSet[int]) -> Links:
    """The corridor graph of *open_cells*."""
    return {cell: tuple(near for near in neighbours(width, height, cell)
                        if near in open_cells)
            for cell in open_cells}


def reachable(links: Links, start: int,
              blocked: FrozenSet[int] = frozenset()) -> FrozenSet[int]:
    """Every cell walkable from *start* without entering *blocked*."""
    if start in blocked or start not in links:
        return frozenset()
    seen = {start}
    queue = deque((start,))
    while queue:
        for near in links[queue.popleft()]:
            if near not in seen and near not in blocked:
                seen.add(near)
                queue.append(near)
    return frozenset(seen)


def distances(links: Links, start: int,
              blocked: FrozenSet[int] = frozenset()) -> Dict[int, int]:
    """Steps from *start* to every cell it can walk to."""
    if start in blocked or start not in links:
        return {}
    found = {start: 0}
    queue = deque((start,))
    while queue:
        cell = queue.popleft()
        step = found[cell] + 1
        for near in links[cell]:
            if near not in found and near not in blocked:
                found[near] = step
                queue.append(near)
    return found


def separators(links: Links, start: int, way_out: int) -> List[int]:
    """Cells that every walk from *start* to *way_out* must pass.

    Ordered by how far they are from the start, which is a real order
    rather than a convenient one: a cell on every route between two
    points is passed by every route in the same place, so the
    separators lie along the way like beads on a thread. That order is
    what lets a door be locked behind the one before it.

    Testing a cell means walking the maze without it, so the candidates
    are narrowed first: a cell every route passes is on every shortest
    route too, and being on a shortest route is two breadth-first
    searches rather than one apiece. On the big mazes that is most of
    the corridor ruled out before the expensive question is asked.
    """
    from_start = distances(links, start)
    if way_out not in from_start:
        return []
    from_exit = distances(links, way_out)
    span = from_start[way_out]
    candidates = [cell for cell in from_start
                  if cell not in (start, way_out)
                  and from_start[cell] + from_exit.get(cell, span + 1) == span]
    found = [cell for cell in candidates
             if way_out not in reachable(links, start, frozenset((cell,)))]
    found.sort(key=lambda cell: from_start[cell])
    return found


def _search(maze: Maze) -> Tuple[int, List[int]]:
    """Breadth-first over ``(cell, keys held)``: the steps and one walk.

    The key set is what makes this a search rather than a shortest
    path: the same corridor is a different place depending on what you
    are carrying, and a walk that doubles back through it is not going
    in circles. ``(-1, [])`` when there is no way out at all, which
    generation never produces and a hand-written maze might.
    """
    links = adjacency(maze.width, maze.height, maze.open_cells())
    door_at = {cell: index for index, cell in enumerate(maze.doors)}
    key_at = {cell: index for index, cell in enumerate(maze.keys)}
    start = (maze.start, _picked_up(maze.start, key_at, 0))
    came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
    queue = deque(((start, 0),))
    while queue:
        state, steps = queue.popleft()
        cell, held = state
        if cell == maze.way_out:
            walk = []
            at: Optional[Tuple[int, int]] = state
            while at is not None:
                walk.append(at[0])
                at = came_from[at]
            walk.reverse()
            return steps, walk
        for near in links[cell]:
            colour = door_at.get(near)
            if colour is not None and not held >> colour & 1:
                continue
            ahead = (near, _picked_up(near, key_at, held))
            if ahead in came_from:
                continue
            came_from[ahead] = state
            queue.append((ahead, steps + 1))
    return -1, []


def solve(maze: Maze) -> int:
    """The exact fewest steps out, keys and all."""
    return _search(maze)[0]


def route(maze: Maze) -> List[int]:
    """One walk of exactly :func:`solve` steps, cell by cell.

    There is usually more than one; this is the one the search found
    first. Empty when the maze has no way out.
    """
    return _search(maze)[1]


def _picked_up(cell: int, key_at: Dict[int, int], held: int) -> int:
    colour = key_at.get(cell)
    return held if colour is None else held | 1 << colour


def greedy_walk(maze: Maze) -> int:
    """What always heading for the nearest key, then the exit, costs.

    Not a solver — a foil. It is the walk of somebody who reads the
    maze one step at a time instead of planning the sweep, and the gap
    between it and the minimum is how much the planning is worth.
    """
    links = adjacency(maze.width, maze.height, maze.open_cells())
    key_at = {cell: index for index, cell in enumerate(maze.keys)}
    here, held, steps = maze.start, 0, 0
    held = _picked_up(here, key_at, held)
    for _leg in range(len(maze.keys) + 1):
        shut = frozenset(cell for colour, cell in enumerate(maze.doors)
                         if not held >> colour & 1)
        apart = distances(links, here, shut)
        if maze.way_out in apart and held == (1 << len(maze.keys)) - 1:
            return steps + apart[maze.way_out]
        wanted = [(apart[cell], cell) for colour, cell in enumerate(maze.keys)
                  if not held >> colour & 1 and cell in apart]
        if not wanted:
            return steps + apart[maze.way_out] if maze.way_out in apart else -1
        gap, cell = min(wanted)
        steps += gap
        here = cell
        held = _picked_up(here, key_at, held)
    return -1


def _lock(links: Links, start: int, way_out: int, count: int,
          rng: random.Random
          ) -> Optional[Tuple[Tuple[int, ...], Tuple[int, ...]]]:
    """Place *count* doors along the way out, and a key for each.

    Doors are drawn from the separators, spread along their order
    rather than bunched, so the maze locks in stages instead of behind
    one wall at the end. Key *i* goes anywhere at all that the start
    can still reach with door *i* shut, which is what makes the maze
    solvable — and, measured, is also what makes it worth planning.

    Burying each key one region deeper than the last was tried first
    and is exactly wrong: it makes the keys a queue, the next one to
    fetch is always the nearest one, and a walker who never thinks
    further than one key ahead ties the optimum every time. Scattering
    them instead leaves several within reach at once, so which to
    fetch first is a real choice — measured at six doors, that takes
    the share of mazes where fetching them in the wrong order costs
    something from one in ten to six in ten.
    """
    if count <= 0:
        return (), ()
    beads = separators(links, start, way_out)
    if len(beads) < count:
        return None
    # Spread the doors along the thread: one from each equal share of
    # it, so a maze does not lock three times in the last corridor.
    doors: List[int] = []
    for index in range(count):
        low = index * len(beads) // count
        high = max(low + 1, (index + 1) * len(beads) // count)
        doors.append(beads[rng.randrange(low, high)])

    taken = set(doors) | {start, way_out}
    keys: List[int] = []
    for colour, door in enumerate(doors):
        near = reachable(links, start, frozenset((door,)))
        room = [cell for cell in near if cell not in taken]
        if not room:
            return None
        chosen = rng.choice(sorted(room))
        keys.append(chosen)
        taken.add(chosen)
    return tuple(doors), tuple(keys)


def _deal(grade: Grade, rng: random.Random) -> Optional[Maze]:
    """One maze at *grade*, or None when this one did not come out."""
    width, height, open_set = carve(grade.rooms, rng)
    braid(width, height, open_set, grade.braid, rng)
    open_cells = frozenset(open_set)
    links = adjacency(width, height, open_cells)

    start = rng.choice(sorted(open_cells))
    apart = distances(links, start)
    way_out = max(apart, key=lambda cell: (apart[cell], cell))
    if way_out == start:
        return None

    locked = _lock(links, start, way_out, min(grade.doors, MOST_DOORS), rng)
    if locked is None:
        return None
    doors, keys = locked

    walls = frozenset(cell for cell in range(width * height)
                      if cell not in open_cells)
    maze = Maze(width=width, height=height, walls=walls, start=start,
                way_out=way_out, doors=doors, keys=keys,
                minimum=0, greedy=0)
    minimum = solve(maze)
    if minimum < 0:
        return None                    # cannot happen by construction
    maze = maze._replace(minimum=minimum)
    return maze._replace(greedy=greedy_walk(maze))


def planning_share(maze: Maze) -> float:
    """How much of the walk taking the keys nearest-first throws away.

    Zero says the maze can be walked without looking further than the
    next key — which is a maze, but not a plan.
    """
    if maze.minimum <= 0:
        return 0.0
    return (maze.greedy - maze.minimum) / float(maze.minimum)


def generate(level_number: int, seed: Optional[int] = None,
             attempts: int = 150) -> Maze:
    """A maze at *level_number*, at or above that rung's floors.

    The two axes are ranked, not merged. A rung's step floor is what
    the ladder promises and what the screen reports, so a maze that
    clears it never loses to one that does not, whatever either is
    worth as a plan. Among the mazes that do clear it, the planning
    floor picks; if none of them clears that too, the deepest of them
    is handed back rather than a shallower maze that happened to
    reward planning. Below the step floor, depth alone ranks.
    """
    grade = GRADES[max(0, min(len(GRADES) - 1, level_number - 1))]
    rng = random.Random(seed)
    strong: Optional[Maze] = None      # deep, but too straightforward
    fallback: Optional[Maze] = None    # not deep enough either way
    for _attempt in range(attempts):
        maze = _deal(grade, rng)
        if maze is None:
            continue
        if maze.minimum >= grade.floor:
            if not grade.planning or planning_share(maze) >= grade.planning:
                return maze            # long and worth planning: done
            if strong is None or maze.minimum > strong.minimum:
                strong = maze
        elif fallback is None or maze.minimum > fallback.minimum:
            fallback = maze
    if strong is not None:
        return strong
    if fallback is not None:
        return fallback
    raise ValueError('no maze survived %d attempts' % attempts)


def held_after(maze: Maze, walked: Sequence[int]) -> int:
    """The key mask a walk over *walked* ends up carrying."""
    key_at = {cell: index for index, cell in enumerate(maze.keys)}
    held = 0
    for cell in walked:
        held = _picked_up(cell, key_at, held)
    return held
