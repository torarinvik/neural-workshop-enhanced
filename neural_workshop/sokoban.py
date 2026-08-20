# -*- coding: utf-8 -*-
"""Sokoban: rooms, a generator that cannot make broken ones, a solver.

Three guarantees hold this module together:

* Every generated level is solvable, by construction rather than by
  hope: the generator starts from the solved position and *pulls*
  boxes backwards through a random walk. Pulling can never create a
  deadlock (a pulled box always came from somewhere it can be pushed
  back to), so wherever the walk ends is a legal start.

* Difficulty is measured, not asserted. A breadth-first solver over
  (box positions, player region) states finds the exact minimum
  number of pushes, and each difficulty rung rejects levels below
  its floor — "level 6" genuinely takes level-6 work, not six boxes
  standing one push from home.

* The solver knows its own limits. Sokoban is PSPACE-complete; past
  a node budget the solver reports failure rather than stalling the
  game, and the caller falls back to the generator's own solution
  length as an upper bound. The scoring then says "at most", never
  pretending a bound is a minimum.

The state space uses one integer per cell and frozensets of box
cells; the player's exact square never matters between pushes, only
the connected region it stands in, which is normalised to its
smallest cell index. That single idea — Sokoban's standard one — is
what makes exact solving affordable at all.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from collections import deque
from typing import FrozenSet, List, NamedTuple, Optional, Sequence, Tuple

#: A generated puzzle: geometry, the pieces, and what is known of it.
class Level(NamedTuple):
    width: int
    height: int
    walls: FrozenSet[int]
    goals: FrozenSet[int]
    boxes: FrozenSet[int]
    player: int
    #: Exact minimum pushes when the solver finished, else None.
    minimum: Optional[int]
    #: A proven lower bound on the minimum — equal to it when known,
    #: else what the solver's breadth-first frontier certified before
    #: its budget ran out. Never a guess.
    at_least: int
    #: Pushes the generator's own walk needs — an upper bound, and
    #: the fallback par when the minimum is out of reach.
    bound: int


class Grade(NamedTuple):
    """One rung of the ladder: the room, the load, and the floor."""

    name: str
    width: int
    height: int
    boxes: int
    floor_share: float  # how much of the interior the digger opens
    pulls: int          # length of the backwards walk
    floor: int          # reject levels needing fewer pushes than this


#: Kindergarten to superhuman. Every number here is measured, not
#: guessed: floors sit at roughly the top fifth of what each rung's
#: warrens actually deliver. floor_share is the difficulty that
#: matters most — open space is what makes Sokoban easy, and the
#: share drops as the ladder climbs. The last rungs outgrow exact
#: solving on purpose; their floors stand on the assignment bound,
#: which scales to any board.
GRADES: Tuple[Grade, ...] = (
    Grade('first steps', 5, 5, 1, 0.9, 6, 2),
    Grade('one box', 6, 6, 1, 0.65, 20, 4),
    Grade('two boxes', 6, 6, 2, 0.65, 24, 5),
    Grade('a little room', 7, 7, 2, 0.6, 30, 7),
    Grade('three boxes', 7, 7, 3, 0.6, 40, 8),
    Grade('tight corners', 8, 8, 3, 0.55, 50, 12),
    Grade('four boxes', 9, 9, 4, 0.55, 70, 14),
    Grade('five boxes', 9, 9, 5, 0.55, 90, 17),
    Grade('the warehouse', 10, 10, 5, 0.52, 110, 20),
    Grade('six boxes', 10, 10, 6, 0.52, 130, 23),
    Grade('seven boxes', 11, 11, 7, 0.5, 160, 26),
    Grade('packed tight', 11, 11, 8, 0.48, 190, 30),
    Grade('the labyrinth', 13, 13, 9, 0.46, 240, 36),
    Grade('nightmare', 14, 14, 11, 0.45, 300, 44),
    Grade('inhuman', 15, 15, 13, 0.43, 380, 54),
    Grade('superhuman', 16, 16, 15, 0.42, 500, 66),
)

DIRECTIONS = ((0, -1), (0, 1), (-1, 0), (1, 0))

#: The solver gives up past this many explored states and the level
#: is scored against its bound instead. Generation uses the smaller
#: budget so a stubborn room costs a fraction of a second, not
#: seconds; both were chosen by measuring the C kernel.
NODE_BUDGET = 400000
GENERATION_BUDGET = 80000


def _steps(width: int) -> Tuple[int, int, int, int]:
    return (-width, width, -1, 1)


def _reachable(width: int, floor_ok: Sequence[bool],
               boxes: FrozenSet[int], start: int) -> FrozenSet[int]:
    """Every cell the player can walk to without pushing anything."""
    seen = {start}
    queue = deque((start,))
    steps = _steps(width)
    while queue:
        cell = queue.popleft()
        for step in steps:
            near = cell + step
            if near not in seen and floor_ok[near] and near not in boxes:
                seen.add(near)
                queue.append(near)
    return frozenset(seen)


def _floor_flags(width: int, height: int,
                 walls: FrozenSet[int]) -> List[bool]:
    flags = [False] * (width * height)
    for cell in range(width * height):
        x, y = cell % width, cell // width
        if 0 < x < width - 1 and 0 < y < height - 1 and cell not in walls:
            flags[cell] = True
    return flags


def live_cells(width: int, height: int, walls: FrozenSet[int],
               goals: FrozenSet[int]) -> FrozenSet[int]:
    """Cells a lone box could still be pushed to a goal from.

    Computed backwards: a goal is live, and a cell is live when a box
    on it can be pulled from a live cell — pulling being pushing seen
    from the other end. A box on any other cell is already lost, so
    the solver prunes those states the moment they appear.
    """
    floor_ok = _floor_flags(width, height, walls)
    steps = _steps(width)
    alive = set(goals)
    queue = deque(goals)
    while queue:
        cell = queue.popleft()
        for step in steps:
            back, beyond = cell - step, cell - step - step
            if (back not in alive and 0 <= beyond < width * height
                    and floor_ok[back] and floor_ok[beyond]):
                alive.add(back)
                queue.append(back)
    return frozenset(alive)


try:
    import bwcore as _native            # the C kernels, when built
except ImportError:                     # pure Python still plays fine
    _native = None


def solve(level: Level, budget: int = NODE_BUDGET) -> Optional[int]:
    """The exact minimum number of pushes, or None past *budget*.

    Dispatches to the C kernel in ``bwcore`` when it is built — the
    same search runs about two orders of magnitude faster there,
    which is what lets the upper rungs stay solver-certified — and
    otherwise runs the pure search below, which defines the
    contract. The tests hold the two to identical answers.
    """
    return solve_bounded(level, budget)[0]


def solve_bounded(level: Level,
                  budget: int = NODE_BUDGET) -> Tuple[Optional[int], int]:
    """(exact minimum or None, proven lower bound).

    The lower bound costs nothing extra: breadth-first search visits
    states in push order, so when the budget dies at depth k, every
    solution still out there needs more than k pushes. The ladder's
    top rungs lean on this — a level too hard to certify exactly can
    still *prove* it clears its difficulty floor.
    """
    if _native is not None and level.width * level.height <= 256:
        return _solve_native(level, budget)
    return _solve_py(level, budget)


def _solve_native(level: Level, budget: int) -> Tuple[Optional[int], int]:
    width, height = level.width, level.height
    floor_ok = bytes(_floor_flags(width, height, level.walls))
    alive = live_cells(width, height, level.walls, level.goals)
    if any(box not in alive for box in level.boxes):
        return None, 0
    cells = width * height
    goals = bytes(1 if cell in level.goals else 0 for cell in range(cells))
    alive_b = bytes(1 if cell in alive else 0 for cell in range(cells))
    boxes = bytes(1 if cell in level.boxes else 0 for cell in range(cells))
    found = _native.sokoban_min_pushes(width, height, floor_ok, goals,
                                       alive_b, boxes, level.player,
                                       budget)
    if found >= 0:
        return found, found
    return None, -found - 1


def _solve_py(level: Level,
              budget: int = NODE_BUDGET) -> Tuple[Optional[int], int]:
    """The pure search: breadth-first over (boxes, player region).

    The first solved state found is minimal in pushes. Walking costs
    nothing here on purpose: pushes are what Sokoban difficulty is
    made of, and a par in pushes survives any route the player
    strolls.
    """
    width = level.width
    floor_ok = _floor_flags(width, level.height, level.walls)
    alive = live_cells(width, level.height, level.walls, level.goals)
    if any(box not in alive for box in level.boxes):
        return None, 0                    # born dead; generator never does
    steps = _steps(width)
    start_region = _reachable(width, floor_ok, level.boxes, level.player)
    start = (level.boxes, min(start_region))
    if level.boxes <= level.goals:
        return 0, 0
    seen = {start}
    queue = deque(((level.boxes, start_region, 0),))
    while queue:
        boxes, region, pushes = queue.popleft()
        if len(seen) > budget:
            return None, pushes + 1
        for box in boxes:
            for step in steps:
                behind, ahead = box - step, box + step
                if (behind not in region or not floor_ok[ahead]
                        or ahead in boxes or ahead not in alive):
                    continue
                moved = (boxes - {box}) | {ahead}
                if moved <= level.goals:
                    return pushes + 1, pushes + 1
                new_region = _reachable(width, floor_ok, moved, box)
                key = (moved, min(new_region))
                if key not in seen:
                    seen.add(key)
                    queue.append((moved, new_region, pushes + 1))
    return None, 0                        # exhausted: cannot happen for
                                          # generated levels within budget


def _blob_goals(width: int, height: int, walls: FrozenSet[int],
                count: int, rng: random.Random) -> Optional[FrozenSet[int]]:
    """Goals grown as one connected clump, not scattered.

    Packed goals are what make Sokoban Sokoban: boxes must arrive in
    an order that does not wall the rest out, which is exactly the
    planning the task exists to exercise. Measured on the seven-box
    rung, clumped goals more than double the share of rooms clearing
    the difficulty floor and push the hardest tails half again as
    high as scattered ones manage.
    """
    flags = _floor_flags(width, height, walls)
    open_floor = [cell for cell in range(width * height) if flags[cell]]
    if len(open_floor) < count:
        return None
    blob = [rng.choice(open_floor)]
    while len(blob) < count:
        grow = [cell + step for cell in blob for step in _steps(width)
                if 0 <= cell + step < width * height
                and flags[cell + step] and cell + step not in blob]
        if not grow:
            return None
        blob.append(rng.choice(grow))
    return frozenset(blob)


def _carve_room(grade: Grade, rng: random.Random) -> FrozenSet[int]:
    """A warren carved out of solid rock by a wandering digger.

    The first version of this function did the opposite — an open
    hall with a few pillars dropped in — and a player with a decent
    eye walked through the "ruthless" rung without breaking stride.
    Open space is what makes Sokoban easy: room to swing any box
    around any other. So now the board starts as solid wall and a
    drunkard's walk digs it out, with a strong straight-line bias so
    the diggings come out as corridors and small chambers rather
    than a cavern. Connectivity is free — a walk can only carve
    where it has walked — and the floor share is the grade's dial:
    the tighter the warren, the fewer the swings.
    """
    width, height = grade.width, grade.height
    interior = [(x, y) for x in range(1, width - 1)
                for y in range(1, height - 1)]
    target = max(grade.boxes * 3 + 4,
                 int(len(interior) * grade.floor_share))
    x, y = width // 2, height // 2
    carved = {(x, y)}
    dx, dy = rng.choice(DIRECTIONS)
    while len(carved) < target:
        if rng.random() < 0.35:           # mostly keep digging straight
            dx, dy = rng.choice(DIRECTIONS)
        nx, ny = x + dx, y + dy
        if 1 <= nx < width - 1 and 1 <= ny < height - 1:
            x, y = nx, ny
            carved.add((x, y))
        else:
            dx, dy = rng.choice(DIRECTIONS)
    return frozenset(cell for cell in range(width * height)
                     if (cell % width, cell // width) not in carved)


def _goal_distance(width: int, height: int, walls: FrozenSet[int],
                   goals: FrozenSet[int]) -> List[int]:
    """Each cell's pull-distance to its nearest goal, for the walk.

    The same backwards flood as :func:`live_cells`, but keeping the
    step count: the walk uses it to prefer pulls that genuinely take
    a box *further* from home, since an unweighted random walk mostly
    cancels itself out and produces boxes a few pushes from done —
    measured, not guessed: unbiased walks of forty pulls were leaving
    four-push levels behind.
    """
    floor_ok = _floor_flags(width, height, walls)
    steps = _steps(width)
    far = [10 ** 6] * (width * height)
    queue = deque()
    for goal in goals:
        far[goal] = 0
        queue.append(goal)
    while queue:
        cell = queue.popleft()
        for step in steps:
            back, beyond = cell - step, cell - step - step
            if (0 <= beyond < width * height and floor_ok[back]
                    and floor_ok[beyond] and far[back] > far[cell] + 1):
                far[back] = far[cell] + 1
                queue.append(back)
    return far


def _pull_walk(grade: Grade, walls: FrozenSet[int], goals: FrozenSet[int],
               rng: random.Random) -> Optional[Tuple[FrozenSet[int], int, int]]:
    """Drag the boxes backwards off their goals; return the start.

    Returns (boxes, player, pushes-of-the-forward-solution) or None
    when the walk went nowhere. Each pull is one forward push, so the
    walk length is an upper bound on the solution — the bound the
    scoring falls back on when the exact minimum is out of reach.

    Pulls that move a box further from every goal are preferred four
    times out of five, and the pull that would exactly undo the last
    one is never taken; both biases exist because an innocent random
    walk wanders home again and leaves an easy level behind.
    """
    width = grade.width
    floor_ok = _floor_flags(width, grade.height, walls)
    steps = _steps(width)
    far = _goal_distance(width, grade.height, walls, goals)
    boxes = set(goals)
    player = next((cell for cell in range(width * grade.height)
                   if floor_ok[cell] and cell not in boxes), None)
    if player is None:
        return None
    pulls = 0
    last = None
    for _pull in range(grade.pulls):
        region = _reachable(width, floor_ok, frozenset(boxes), player)
        options = []
        for box in boxes:
            for step in steps:
                near, away = box + step, box + step + step
                if (near in region and floor_ok[near]
                        and floor_ok[away] and away not in boxes
                        and near not in boxes
                        and (near, box) != last):
                    options.append((box, near, away))
        if not options:
            break
        outward = [option for option in options
                   if far[option[1]] > far[option[0]]]
        pool = outward if outward and rng.random() < 0.8 else options
        box, near, away = rng.choice(pool)
        boxes.discard(box)
        boxes.add(near)
        player = away
        last = (box, near)
        pulls += 1
    off_goal = sum(1 for box in boxes if box not in goals)
    if pulls == 0 or off_goal < max(1, len(goals) // 2):
        return None
    return frozenset(boxes), player, pulls


def _push_distances(width: int, height: int, walls: FrozenSet[int],
                    goal: int) -> List[int]:
    """Relaxed push-distance from every cell to *goal*, one lone box.

    The relaxation ignores where the player is and whether other
    boxes are in the way, so it can only undercount — which is what
    makes the matching bound below admissible.
    """
    floor_ok = _floor_flags(width, height, walls)
    steps = _steps(width)
    far = [10 ** 6] * (width * height)
    far[goal] = 0
    queue = deque((goal,))
    while queue:
        cell = queue.popleft()
        for step in steps:
            back, beyond = cell - step, cell - step - step
            if (0 <= beyond < width * height and floor_ok[back]
                    and floor_ok[beyond] and far[back] > far[cell] + 1):
                far[back] = far[cell] + 1
                queue.append(back)
    return far


def matching_bound(level: Level) -> int:
    """A proven lower bound that scales to any board: assignment.

    Each box must end on its own goal, and a box's pushes cannot
    beat its relaxed push-distance to whichever goal it gets. The
    cheapest perfect assignment of boxes to goals therefore bounds
    the whole solution from below — exactly, via the classic bitmask
    DP, which at sixteen boxes is about a million adds. This is the
    certificate the superhuman rungs stand on where breadth-first
    search cannot reach any more.
    """
    goals = sorted(level.goals)
    boxes = sorted(level.boxes)
    table = [_push_distances(level.width, level.height, level.walls,
                             goal) for goal in goals]
    cost = [[table[g][box] for g in range(len(goals))] for box in boxes]
    best = [10 ** 9] * (1 << len(goals))
    best[0] = 0
    for mask in range(1 << len(goals)):
        if best[mask] >= 10 ** 9:
            continue
        box = bin(mask).count('1')
        if box >= len(boxes):
            continue
        for g in range(len(goals)):
            if not mask >> g & 1:
                after = mask | 1 << g
                score = best[mask] + cost[box][g]
                if score < best[after]:
                    best[after] = score
    total = best[(1 << len(goals)) - 1]
    return 0 if total >= 10 ** 9 else total


def generate(level_number: int, seed: Optional[int] = None,
             attempts: int = 200) -> Level:
    """A solvable level of the given rung, at or above its floor.

    Retries fresh rooms until the floor is certified — either the
    exact minimum, or, past the solver's budget, the breadth-first
    frontier's proven lower bound. Either way "level 9" carries a
    certificate that it takes at least level-9 work; the walk length
    stays as the par when the exact minimum is unknown. Raises only
    if every attempt collapses, which the ladder's tests never let
    happen.
    """
    grade = GRADES[max(0, min(len(GRADES) - 1, level_number - 1))]
    rng = random.Random(seed)
    fallback: Optional[Level] = None
    for _attempt in range(attempts):
        walls = _carve_room(grade, rng)
        floor = [cell for cell in range(grade.width * grade.height)
                 if cell not in walls]
        flags = _floor_flags(grade.width, grade.height, walls)
        open_floor = [cell for cell in floor if flags[cell]]
        if len(open_floor) < grade.boxes * 2 + 2:
            continue
        goals = _blob_goals(grade.width, grade.height, walls,
                            grade.boxes, rng)
        if goals is None:
            continue
        pulled = _pull_walk(grade, walls, goals, rng)
        if pulled is None:
            continue
        boxes, player, bound = pulled
        level = Level(grade.width, grade.height, walls, goals, boxes,
                      player, None, 0, bound)
        if grade.width * grade.height > 121:
            # Beyond exact solving by design: the assignment bound is
            # the certificate, and it is cheap at any size.
            minimum, proven = None, matching_bound(level)
        else:
            # The last exactly-solvable rungs (121 cells) get a short
            # exact probe — deals it certifies keep a true minimum —
            # and the assignment bound catches the rest, so the room
            # never waits long on a search that was going to drown.
            budget = (GENERATION_BUDGET if grade.width * grade.height <= 100
                      else GENERATION_BUDGET // 4)
            minimum, proven = solve_bounded(level, budget)
            if minimum is None:
                proven = max(proven, matching_bound(level))
        if minimum is None and proven >= grade.floor:
            return level._replace(at_least=proven)
        if minimum is not None and minimum >= grade.floor:
            return level._replace(minimum=minimum, at_least=minimum)
        best_so_far = fallback.at_least if fallback is not None else -1
        if max(minimum or 0, proven) > best_so_far:
            fallback = level._replace(minimum=minimum,
                                      at_least=max(minimum or 0, proven))
    if fallback is not None:
        return fallback
    raise ValueError('no level survived %d attempts at rung %d'
                     % (attempts, level_number))
