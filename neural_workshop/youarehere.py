# -*- coding: utf-8 -*-
"""You Are Here: the same maze, from inside it, with a map that will not help.

The map is pinned to the side of the screen. It shows the corridors,
where you started, where the way out is, and every door and key in
their colours. It is complete, it is accurate, and it never changes —
not when you move, not when you turn, not when you pick something up.
The one thing it will not tell you is the only thing you actually need
to know, which is where on it you currently are.

So the map is not the task; keeping your place on it is. You know
where you began and you know what you have done since, and between
those two facts your position is entirely determined — by arithmetic
you have to do yourself, once per action, without ever being shown the
answer. Miss one turn thirty moves ago and every corridor still looks
plausible and every decision after it is wrong.

That makes this the spatial reading of what
:mod:`neural_workshop.inthedark` asks in the abstract: hold a small
piece of state, update it exactly, act on it. The difference is that
here the state is a place, the updates are your own movements, and the
maze is quietly full of corridors that look exactly like the one you
think you are in.

The maze itself is not new. It is dealt by
:mod:`neural_workshop.maze`, at the same rungs, from the same
generator — so level nine here is the very same maze level nine is
there, and the only thing that changed is that you are standing in it.
What that costs is measured rather than guessed, in three ways:

* Turning costs a step. Not a stylistic choice: with free turns a
  player can spin on the spot at every cell and read all four
  corridors for nothing, which turns the task into a 2D maze with a
  narrow window. Paying for a look is what makes looking a decision.
  :func:`par` is therefore its own exact minimum over
  ``(cell, facing, keys)`` rather than the flat one on the maze, and
  the gap between the two is the price of the view.

* :func:`walk_hugging` is the foil that never looks at the map at all
  — one hand on the wall, which solves any maze without loops and is
  what a player falls back on when they have lost their place. The
  ladder braids loops into every rung above the first for exactly this
  reason.

* :func:`walk_slipping` is the foil this task is really about: a
  player who plans perfectly from where it *believes* it is, and now
  and then fails to notice that it moved. What one dropped update
  costs, thirty moves later, is the whole point, and it is measured
  rather than asserted.

The view is cast rather than rendered — one ray per screen column,
walls hit square on, distances exact. It lives here beside the
solvers, and not in the screen module, because what can be seen from a
cell is a fact about the maze and wants testing without a window open.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, NamedTuple, Optional, Tuple

from .maze import Maze, generate

#: North, east, south and west, clockwise, on a grid whose y grows
#: downwards — which is the way :mod:`neural_workshop.maze` numbers its
#: cells and the way the map is drawn.
FACINGS: Tuple[Tuple[int, int], ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))

#: The four things a player can do, each costing exactly one step.
AHEAD, BACK, LEFT, RIGHT = 'ahead', 'back', 'left', 'right'
MOVES: Tuple[str, ...] = (AHEAD, BACK, LEFT, RIGHT)

#: Rays cast across the viewport. Blocky on purpose: the view is a
#: thing to read a corridor off, not a thing to admire, and a coarse
#: column is a cheaper and steadier signal for an agent reading pixels
#: than a smooth one.
COLUMNS = 180

#: How wide the view is. A right angle, so that a corridor opening off
#: the cell you are standing in reaches the very edge of the screen
#: instead of falling outside it — at anything narrower a player has
#: to spend a turn to discover a junction they are already in.
FOV = math.pi / 2

#: Far enough to mean "nothing there" without being infinite, which
#: would make the arithmetic that follows awkward for no gain.
FAR = 1e4


class Sight(NamedTuple):
    """What one ray found: how far, in which cell, and on which face."""

    #: Distance to the wall, measured square on rather than along the
    #: ray, which is what stops straight walls bowing outwards.
    distance: float
    cell: int
    #: 0 for a wall facing east or west, 1 for one facing north or
    #: south. Shading the two differently is what makes a corner read
    #: as a corner rather than as one flat surface.
    side: int


class Mote(NamedTuple):
    """Something standing in a cell, seen from where you are.

    Keys and the way out are drawn as marks hanging in the corridor
    rather than as anything on the floor, because a floor mark
    disappears the moment it is more than a few cells off and these
    have to be recognisable from down a passage.
    """

    #: ``'key'`` or ``'way out'``.
    what: str
    #: Which key, for a key; ``-1`` for the way out.
    which: int
    cell: int
    #: Where across the view it sits, from 0 at the left edge to 1 at
    #: the right. Outside that range it is off screen.
    across: float
    distance: float


class Pose(NamedTuple):
    """Where a player is and which way it is looking."""

    cell: int
    facing: int


# --- standing in a maze --------------------------------------------------


def facing_at(maze: Maze) -> int:
    """Which way a player starts out looking.

    The first open direction, clockwise from north, so that a maze
    always opens onto a corridor rather than onto a wall. Derived from
    the maze rather than drawn, so the same seed always faces the same
    way.
    """
    for facing in range(len(FACINGS)):
        if ahead_of(maze, maze.start, facing) is not None:
            return facing
    return 0


def ahead_of(maze: Maze, cell: int, facing: int) -> Optional[int]:
    """The cell one step that way, or None when a wall is in the way.

    Knows nothing about doors — a locked door is a cell you cannot
    enter yet, not a cell that is not there, and the two want telling
    apart: you can see through a doorway and you cannot see through a
    wall.
    """
    x, y = cell % maze.width, cell // maze.width
    dx, dy = FACINGS[facing]
    nx, ny = x + dx, y + dy
    if not (0 <= nx < maze.width and 0 <= ny < maze.height):
        return None
    step = ny * maze.width + nx
    return None if step in maze.walls else step


def locked(maze: Maze, cell: int, held: int) -> Optional[int]:
    """The colour barring *cell*, or None when it may be walked into."""
    for colour, door in enumerate(maze.doors):
        if door == cell and not held >> colour & 1:
            return colour
    return None


def picked_up(maze: Maze, cell: int, held: int) -> int:
    """*held*, plus whatever key is lying in *cell*."""
    for colour, key in enumerate(maze.keys):
        if key == cell:
            held |= 1 << colour
    return held


def move(maze: Maze, pose: Pose, held: int,
         doing: str) -> Tuple[Pose, int, bool]:
    """Do one thing. Returns the new pose, the keys held, and whether
    the player actually went anywhere.

    Turning always works. Going forwards or backwards works when there
    is corridor there and no locked door in it; when there is not,
    nothing happens at all — see :func:`costs` for why a bump is free.
    """
    if doing == LEFT:
        return Pose(pose.cell, (pose.facing - 1) % 4), held, False
    if doing == RIGHT:
        return Pose(pose.cell, (pose.facing + 1) % 4), held, False
    facing = pose.facing if doing == AHEAD else (pose.facing + 2) % 4
    step = ahead_of(maze, pose.cell, facing)
    if step is None or locked(maze, step, held) is not None:
        return pose, held, False
    return Pose(step, pose.facing), picked_up(maze, step, held), True


def costs(doing: str, moved: bool) -> int:
    """What one action is charged: one step, unless it was a bump.

    A turn always costs. A walk costs when it walks. Walking into a
    wall costs nothing, which is what the 2D maze next door does and
    is worth keeping: the wall is plainly visible from where the
    player is standing, so charging for the attempt would be charging
    for a typo rather than for a decision. It also keeps the par
    honest — a minimum that had to reason about wasted bumps would not
    be a minimum of anything a player is actually scored on.
    """
    return 1 if moved or doing in (LEFT, RIGHT) else 0


# --- what a perfect walk costs -------------------------------------------


def par(maze: Maze) -> int:
    """The fewest steps out, turns counted, keys and all.

    An exact minimum and not an estimate, which is what lets a walk be
    scored the way the rest of the planning category is scored. The
    state is the cell, the way the player is looking, and which keys
    it is carrying; every one of the four moves costs one, so a plain
    breadth-first sweep is already the shortest path and there is
    nothing to weigh.
    """
    return _sweep(maze)[0]


def route(maze: Maze) -> List[str]:
    """One shortest way out, as the moves that walk it."""
    return _sweep(maze)[1]


def _tables(maze: Maze) -> Tuple[List[List[int]], Dict[int, int],
                                 Dict[int, int]]:
    """The maze, flattened into what the sweep's inner loop wants.

    Where a step from each cell and facing lands, which bit each
    door wants, and which bits each cell hands over. All three are
    read millions of times by :func:`_sweep` and none of them change,
    so they are worked out once rather than rediscovered by scanning
    the door and key tuples on every edge.
    """
    cells = maze.width * maze.height
    steps = [[-1] * 4 for _cell in range(cells)]
    for cell in range(cells):
        if cell in maze.walls:
            continue
        for facing in range(4):
            landed = ahead_of(maze, cell, facing)
            steps[cell][facing] = -1 if landed is None else landed
    doors: Dict[int, int] = {}
    for colour, door in enumerate(maze.doors):
        doors[door] = doors.get(door, 0) | 1 << colour
    keys: Dict[int, int] = {}
    for colour, key in enumerate(maze.keys):
        keys[key] = keys.get(key, 0) | 1 << colour
    return steps, doors, keys


def _sweep(maze: Maze, pose: Optional[Pose] = None,
           held: Optional[int] = None) -> Tuple[int, List[str]]:
    """Breadth-first over pose and keys, back to front once it lands.

    Every edge costs one, so plain breadth-first is already the
    shortest path and there is nothing to weigh. A state is packed
    into one integer — ``(cell * 4 + facing) * 64 + keys`` — because
    the alternative is several hundred thousand tuples and namedtuple
    constructions, and this loop is the one thing in the task that
    takes long enough to notice.

    :func:`move` remains the definition of what a move does; this is
    the same rules written out flat, and the tests hold the route it
    returns to being walkable by :func:`move` itself.
    """
    if pose is None:
        pose = Pose(maze.start, facing_at(maze))
    if held is None:
        held = picked_up(maze, maze.start, 0)
    steps, doors, keys = _tables(maze)
    way_out = maze.way_out
    first = (pose.cell * 4 + pose.facing) * 64 + held
    came: Dict[int, Optional[Tuple[int, str]]] = {first: None}
    queue = [first]
    while queue:
        nextup: List[int] = []
        for state in queue:
            spun, carried = state >> 6, state & 63
            cell, facing = spun >> 2, spun & 3
            if cell == way_out:
                return _unwind(came, state)
            for doing, turned in ((LEFT, (facing - 1) % 4),
                                  (RIGHT, (facing + 1) % 4)):
                below = ((cell * 4 + turned) << 6) | carried
                if below not in came:
                    came[below] = (state, doing)
                    nextup.append(below)
            for doing, way in ((AHEAD, facing), (BACK, (facing + 2) % 4)):
                landed = steps[cell][way]
                if landed < 0:
                    continue
                shut = doors.get(landed, 0)
                if shut and not carried & shut:
                    continue
                below = ((landed * 4 + facing) << 6) | (
                    carried | keys.get(landed, 0))
                if below not in came:
                    came[below] = (state, doing)
                    nextup.append(below)
        queue = nextup
    return -1, []


def _unwind(came, state) -> Tuple[int, List[str]]:
    walked: List[str] = []
    while came[state] is not None:
        state, doing = came[state]
        walked.append(doing)
    walked.reverse()
    return len(walked), walked


def route_from(maze: Maze, pose: Pose, held: int) -> List[str]:
    """A shortest way out from wherever the player thinks it is.

    What :func:`walk_slipping` plans with. Handed a belief rather than
    the truth, it returns the moves that would get *that* player out —
    which is the whole trouble, because they are carried out by a
    player somewhere else.
    """
    return _sweep(maze, pose, held)[1]


# --- players -------------------------------------------------------------


def walk_perfect(maze: Maze) -> int:
    """Follow the minimum. What the screen scores a walk against."""
    return par(maze)


def walk_hugging(maze: Maze, cap: int = 20000) -> int:
    """One hand on the wall, and no glance at the map at all.

    The fallback of a player who has lost its place, and the reason
    the ladder braids loops into every rung above the first: a hand on
    the wall gets you out of any maze without loops, and can walk a
    maze with them round and round forever. Face right, and if that is
    blocked keep turning left until it is not. Returns the steps it
    spent, or ``-1`` when it never found the way out.
    """
    pose = Pose(maze.start, facing_at(maze))
    held = picked_up(maze, maze.start, 0)
    steps = 0
    while steps < cap:
        if pose.cell == maze.way_out:
            return steps
        pose, held, _turned = move(maze, pose, held, RIGHT)
        steps += 1
        for _try in range(4):
            went, got, moved = move(maze, pose, held, AHEAD)
            steps += costs(AHEAD, moved)
            if moved:
                pose, held = went, got
                break
            pose, held, _turned = move(maze, pose, held, LEFT)
            steps += 1
    return -1


def walk_slipping(maze: Maze, slip: float, rng: random.Random,
                  cap: int = 4000) -> int:
    """Plan perfectly from where you *think* you are, and slip sometimes.

    The foil the whole task is built to punish. It reads the map, it
    solves the maze exactly, and it carries out the answer — but once
    in a while it does not notice that it moved, and its belief about
    where it is quietly parts company with where it is. Nothing tells
    it. Every corridor still looks like a corridor.

    It does not try to recover, deliberately: what is being measured
    is the cost of one dropped update, and a player that reconciled
    would be measuring its reconciler instead. Returns the steps it
    spent, or ``-1`` when it never got out.
    """
    pose = Pose(maze.start, facing_at(maze))
    held = picked_up(maze, maze.start, 0)
    thinks, believes = pose, held
    steps = 0
    while steps < cap:
        if pose.cell == maze.way_out:
            return steps
        plan = route_from(maze, thinks, believes)
        if not plan:
            return -1
        doing = plan[0]
        pose, held, moved = move(maze, pose, held, doing)
        steps += costs(doing, moved)
        if rng.random() >= slip:
            thinks, believes, _m = move(maze, thinks, believes, doing)
    return -1


# --- what can be seen ----------------------------------------------------


def _cast(maze: Maze, from_x: float, from_y: float,
          dir_x: float, dir_y: float) -> Tuple[float, int, int]:
    """One ray, by the usual grid march. Returns distance, cell, side.

    Steps from one cell boundary to the next rather than sampling
    along the ray, so a wall is found exactly where it is and a long
    corridor costs no more accuracy than a short one.

    *dir_x* and *dir_y* are deliberately not a unit vector: they are
    the way the player is looking plus a sideways lean, so the
    distance this marches off is already measured square on to the
    screen and needs no second correction. Normalising first and
    dividing back afterwards gets to the same place by a longer road,
    and gets the sign of the correction wrong if you are not careful.
    """
    map_x, map_y = int(from_x), int(from_y)
    step_x = 1 if dir_x >= 0 else -1
    step_y = 1 if dir_y >= 0 else -1
    delta_x = abs(1.0 / dir_x) if dir_x else FAR
    delta_y = abs(1.0 / dir_y) if dir_y else FAR
    next_x = ((map_x + 1 - from_x) if dir_x >= 0 else
              (from_x - map_x)) * delta_x
    next_y = ((map_y + 1 - from_y) if dir_y >= 0 else
              (from_y - map_y)) * delta_y
    side = 0
    for _march in range(maze.width + maze.height + 2):
        if next_x < next_y:
            map_x += step_x
            side = 0
            walked = next_x
            next_x += delta_x
        else:
            map_y += step_y
            side = 1
            walked = next_y
            next_y += delta_y
        if not (0 <= map_x < maze.width and 0 <= map_y < maze.height):
            return FAR, -1, side
        cell = map_y * maze.width + map_x
        if cell in maze.walls:
            return max(walked, 1e-6), cell, side
    return FAR, -1, side


def look(maze: Maze, pose: Pose, columns: int = COLUMNS,
         fov: float = FOV) -> Tuple[Sight, ...]:
    """The view from *pose*, one ray to a column, left edge first."""
    from_x = pose.cell % maze.width + 0.5
    from_y = pose.cell // maze.width + 0.5
    face_x, face_y = FACINGS[pose.facing]
    seen: List[Sight] = []
    for column in range(columns):
        # The angle is taken across the screen plane rather than swept
        # evenly, so that a flat wall renders flat instead of curved.
        offset = math.tan(fov / 2.0) * (2.0 * (column + 0.5) / columns - 1.0)
        walked, cell, side = _cast(maze, from_x, from_y,
                                   face_x - face_y * offset,
                                   face_y + face_x * offset)
        seen.append(Sight(walked, cell, side))
    return tuple(seen)


def motes(maze: Maze, pose: Pose, held: int, fov: float = FOV
          ) -> Tuple[Mote, ...]:
    """The keys still lying about and the way out, as seen from *pose*.

    A landmark is worth having and worth being sparse. The map already
    says where every key and the way out are, so catching sight of one
    is what lets a player who has been counting corridors check its
    answer — and on the rungs with no doors there is nothing to check
    against but the way out itself, which is the whole of why the
    early rungs are harder than their size suggests.
    """
    from_x = pose.cell % maze.width + 0.5
    from_y = pose.cell // maze.width + 0.5
    face_x, face_y = FACINGS[pose.facing]
    edge = math.tan(fov / 2.0)
    standing: List[Tuple[str, int, int]] = [
        ('key', colour, cell) for colour, cell in enumerate(maze.keys)
        if not held >> colour & 1]
    standing.append(('way out', -1, maze.way_out))
    found: List[Mote] = []
    for what, which, cell in standing:
        at_x = cell % maze.width + 0.5 - from_x
        at_y = cell // maze.width + 0.5 - from_y
        depth = at_x * face_x + at_y * face_y
        if depth <= 0.05:
            continue
        sideways = at_x * -face_y + at_y * face_x
        across = (sideways / depth / edge + 1.0) / 2.0
        if not -0.2 <= across <= 1.2:
            continue
        if not _clear(maze, pose.cell, cell):
            continue
        found.append(Mote(what, which, cell, across, depth))
    found.sort(key=lambda mote: -mote.distance)
    return tuple(found)


def _clear(maze: Maze, here: int, there: int) -> bool:
    """True when nothing walled stands between two cells.

    Only ever asked about cells that share a row or a column, because
    those are the only ones a mark can be seen down: a maze corridor
    is one cell wide and anything off the straight is behind a corner.
    """
    hx, hy = here % maze.width, here // maze.width
    tx, ty = there % maze.width, there // maze.width
    if hx != tx and hy != ty:
        return False
    step = (0, 1 if ty > hy else -1) if hx == tx else (1 if tx > hx else -1, 0)
    x, y = hx, hy
    while (x, y) != (tx, ty):
        x, y = x + step[0], y + step[1]
        if y * maze.width + x in maze.walls:
            return False
    return True


def deal(level_number: int, seed: Optional[int] = None) -> Maze:
    """A maze at *level_number*, from the very same ladder as the 2D one.

    Deliberately not a ladder of its own. Level nine here is the maze
    level nine is there, so what the view costs can be read straight
    off the two pars rather than guessed at across two sets of rungs
    that were tuned separately.
    """
    return generate(level_number, seed=seed)
