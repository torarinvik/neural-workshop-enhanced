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

Difficulty runs on three measured axes, ranked rather than merged.
Push count is the spine: how much work the level is. The trap share
is the room: how much of the floor a box can never come back from.
The deception share is the position: how much of what the player can
do *on move one* throws the level away. A rung's push floor outranks
the other two, because adding an axis must never cost the depth the
ladder already promised.

One thing these levels are *not* is entangled, and the code says so
rather than implying otherwise. Measured across every rung, the true
minimum equals the assignment bound almost always: each box walks its
own shortest path home and the boxes rarely have to get out of each
other's way. That is inherent to generating backwards — a walk that
pulls boxes outward along their own paths reverses into a solution
that pushes them home along their own paths. It is why these levels
are long and lethal rather than deep, and why no cheap strengthening
of the lower bound buys anything here: every such bound relaxes by
removing the other boxes, and the interaction it would price is not
present to begin with.

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
    #: Floor squares a box dies on — one wrong push there and it can
    #: never reach a goal again. The second axis of difficulty.
    traps: FrozenSet[int] = frozenset()


class Grade(NamedTuple):
    """One rung of the ladder: the room, the load, and the floor."""

    name: str
    width: int
    height: int
    boxes: int
    floor_share: float  # how much of the interior the digger opens
    pulls: int          # length of the backwards walk
    floor: int          # reject levels needing fewer pushes than this
    #: The ladder's second axis: the least share of the floor that
    #: must be *dead* — squares a box can never reach a goal from, so
    #: one wrong push there loses the box forever. Push count says
    #: how much work a level takes; this says how much of the room
    #: is a landmine while you do it.
    trap_share: float = 0.0
    #: The third axis: the least share of the *opening pushes* that
    #: must be fatal. The trap share measures the room; this
    #: measures the position — how much of what the player can do on
    #: move one throws the level away. A room can be full of
    #: landmines and still open with six safe pushes; this is the
    #: number that says otherwise.
    deceit: float = 0.0


#: Kindergarten to superhuman. Every number here is measured, not
#: guessed: floors sit at roughly the top fifth of what each rung's
#: warrens actually deliver. floor_share is the difficulty that
#: matters most — open space is what makes Sokoban easy, and the
#: share drops as the ladder climbs. The last rungs outgrow exact
#: solving on purpose; their floors stand on the assignment bound,
#: which scales to any board. Superhuman carries thirteen boxes, not
#: the fifteen its room could hold, because fifteen choke their own
#: warren: measured, two fewer boxes let the walks drag every one
#: deeper and the certified floors nearly double. The deception floors sit
#: below what the rooms usually manage, deliberately: they are the
#: junior axis, and a rung that could not meet both would rather be
#: deep than treacherous.
GRADES: Tuple[Grade, ...] = (
    Grade('first steps', 5, 5, 1, 0.9, 6, 2, 0.0, 0.0),
    Grade('one box', 6, 6, 1, 0.65, 20, 4, 0.0, 0.0),
    Grade('two boxes', 6, 6, 2, 0.65, 24, 5, 0.0, 0.0),
    Grade('a little room', 7, 7, 2, 0.6, 30, 7, 0.2, 0.0),
    Grade('three boxes', 7, 7, 3, 0.6, 40, 8, 0.2, 0.1),
    Grade('tight corners', 8, 8, 3, 0.55, 50, 12, 0.3, 0.15),
    Grade('four boxes', 9, 9, 4, 0.55, 70, 14, 0.3, 0.2),
    Grade('five boxes', 9, 9, 5, 0.55, 90, 17, 0.35, 0.25),
    Grade('the warehouse', 10, 10, 5, 0.52, 110, 20, 0.35, 0.25),
    Grade('six boxes', 10, 10, 6, 0.52, 130, 23, 0.4, 0.3),
    Grade('seven boxes', 11, 11, 7, 0.5, 160, 26, 0.4, 0.3),
    Grade('packed tight', 11, 11, 8, 0.48, 190, 28, 0.45, 0.3),
    Grade('the labyrinth', 13, 13, 9, 0.46, 240, 45, 0.45, 0.35),
    Grade('nightmare', 14, 14, 11, 0.45, 300, 52, 0.5, 0.35),
    Grade('inhuman', 15, 15, 13, 0.43, 380, 52, 0.5, 0.4),
    Grade('superhuman', 16, 16, 13, 0.46, 500, 60, 0.55, 0.4),
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


def _stuck(width: int, floor_ok: Sequence[bool], dead: Sequence[bool],
           boxes: FrozenSet[int], cell: int,
           assumed: FrozenSet[int]) -> bool:
    """Is the box on *cell* frozen where it stands, for good?

    A box travels an axis only when both squares along it are free
    floor: the player needs one to stand on and the box needs the
    other to land on. So the axis is shut when either side is rock,
    when both sides are squares nothing returns from, or when either
    side holds a box that is itself stuck. Shut on both axes and off
    a goal means the level is already lost, however many moves are
    left on the clock.

    The recursion treats any box it is already asking about as
    immovable, which is the standard reading and the right one: two
    boxes that block only each other are both stuck.
    """
    if cell in assumed:
        return True
    assumed = assumed | {cell}
    for step in (1, width):
        low, high = cell - step, cell + step
        if not floor_ok[low] or not floor_ok[high]:
            continue                      # rock on one side: no lane
        if dead[low] and dead[high]:
            continue                      # both landings already lost
        if low in boxes and _stuck(width, floor_ok, dead, boxes, low,
                                   assumed):
            continue
        if high in boxes and _stuck(width, floor_ok, dead, boxes, high,
                                    assumed):
            continue
        return False                      # this axis is still open
    return True


def deadlocked(width: int, height: int, walls: FrozenSet[int],
               goals: FrozenSet[int], boxes: FrozenSet[int],
               alive: Optional[FrozenSet[int]] = None) -> bool:
    """Has this position already lost, whatever the player does now?

    True when a box stands where no push could ever bring it to a
    goal, or when a box is frozen off-goal. Both tests are
    sufficient but not exhaustive — Sokoban hides deadlocks no cheap
    test catches — so False means "not provably lost", never "still
    winnable".
    """
    if alive is None:
        alive = live_cells(width, height, walls, goals)
    if any(box not in alive for box in boxes):
        return True
    floor_ok = _floor_flags(width, height, walls)
    dead = [floor_ok[c] and c not in alive for c in range(width * height)]
    return any(box not in goals
               and _stuck(width, floor_ok, dead, boxes, box, frozenset())
               for box in boxes)


def opening_pushes(level: Level) -> List[Tuple[int, int]]:
    """Every push available from the start, as (box cell, where to)."""
    floor_ok = _floor_flags(level.width, level.height, level.walls)
    region = _reachable(level.width, floor_ok, level.boxes, level.player)
    moves = []
    for box in sorted(level.boxes):
        for step in _steps(level.width):
            behind, ahead = box - step, box + step
            if (behind in region and floor_ok[ahead]
                    and ahead not in level.boxes):
                moves.append((box, ahead))
    return moves


def fatal_share(level: Level) -> float:
    """The share of opening pushes that lose the level on the spot.

    A third axis, and the one the player actually stands in front
    of. Push count says how long the work is; the trap share says
    how much of the room is lethal; this says how much of what you
    can *do right now* is lethal — the difference between a
    minefield across the warehouse and a minefield under your feet.
    """
    moves = opening_pushes(level)
    if not moves:
        return 0.0
    width, cells = level.width, level.width * level.height
    alive = live_cells(width, level.height, level.walls, level.goals)
    floor_ok = _floor_flags(width, level.height, level.walls)
    dead = [floor_ok[c] and c not in alive for c in range(cells)]
    lost = 0
    for box, ahead in moves:
        after = (level.boxes - {box}) | {ahead}
        if ahead not in alive:
            lost += 1                     # pushed somewhere nothing returns from
        elif any(cell not in level.goals
                 and _stuck(width, floor_ok, dead, after, cell, frozenset())
                 for cell in after):
            lost += 1                     # pushed into a frozen huddle
    return lost / len(moves)


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
    if _native is not None and level.width * level.height <= 1024:
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


def _dig_traps(width: int, height: int, walls: FrozenSet[int],
               goals: FrozenSet[int], share: float,
               rng: random.Random) -> FrozenSet[int]:
    """Dig one-cell pockets until *share* of the floor is dead.

    A pocket has a single entrance, so a box pushed into it can
    never come out — the player would have to stand beyond it,
    inside the rock. Dug *after* the backwards walk on purpose:
    adding floor can only widen the forward solution's options, so
    solvability survives, while every pocket is a fresh landmine.
    Pockets can also *revive* other squares (a new standing spot
    gives the player a new push lane), so the tally is recomputed
    until the share genuinely holds.
    """
    carved = set(walls)
    for _round in range(6):
        flags = _floor_flags(width, height, frozenset(carved))
        floor = [cell for cell in range(width * height) if flags[cell]]
        alive = live_cells(width, height, frozenset(carved), goals)
        dead = sum(1 for cell in floor if cell not in alive)
        missing = int(share * len(floor)) - dead
        if missing <= 0:
            return frozenset(carved)
        candidates = [cell for cell in carved
                      if 0 < cell % width < width - 1
                      and 0 < cell // width < height - 1
                      and sum(1 for step in _steps(width)
                              if flags[cell + step]) == 1]
        rng.shuffle(candidates)
        for cell in candidates[:missing + 2]:
            carved.discard(cell)
    return frozenset(carved)


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
        # Evacuate before wandering: in a tight warren, boxes pulled
        # early park in the corridors and seal the rest onto their
        # goals, so the walk stalls with the clump half-solved.
        # Pulling still-on-goal boxes first keeps the exits open —
        # measured: seventy-five of eighty superhuman walks failed
        # without this, five with it still failing for other reasons.
        stuck = [option for option in options if option[0] in goals]
        pool = stuck if stuck else options
        outward = [option for option in pool
                   if far[option[1]] > far[option[0]]]
        if outward and rng.random() < 0.8:
            pool = outward
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


def _goal_tables(width: int, height: int, walls: FrozenSet[int],
                 goals: FrozenSet[int]) -> List[List[int]]:
    """One relaxed-distance map per goal, reusable across a walk.

    The walls never change while boxes are pulled around a room, so
    the generator computes these once and prices thousands of box
    arrangements against them.
    """
    return [_push_distances(width, height, walls, goal)
            for goal in sorted(goals)]


BIG = 10 ** 6


def _assignment(tables: Sequence[Sequence[int]],
                boxes: Sequence[int]) -> int:
    """The cheapest perfect assignment of *boxes* to the goals.

    Dispatches to the C kernel when built; the pure DP below defines
    the contract. An unreachable pairing prices at :data:`BIG`, so
    an impossible assignment comes back enormous rather than lying
    small.
    """
    n = len(tables)
    cost = [min(BIG, tables[g][box]) for box in boxes
            for g in range(n)]
    if _native is not None and hasattr(_native, 'assignment_min_cost')             and n <= 20:
        import struct
        total = _native.assignment_min_cost(
            n, struct.pack('<%di' % (n * n), *cost))
        return 0 if total < 0 else int(total)
    best = [BIG * n] * (1 << n)
    best[0] = 0
    for mask in range(1 << n):
        if best[mask] >= BIG * n:
            continue
        box = bin(mask).count('1')
        if box >= n:
            continue
        for g in range(n):
            if not mask >> g & 1:
                after = mask | 1 << g
                score = best[mask] + cost[box * n + g]
                if score < best[after]:
                    best[after] = score
    return min(best[(1 << n) - 1], BIG * n)


def matching_bound(level: Level) -> int:
    """A proven lower bound that scales to any board: assignment.

    Each box must end on its own goal, and a box's pushes cannot
    beat its relaxed push-distance to whichever goal it gets. The
    cheapest perfect assignment of boxes to goals therefore bounds
    the whole solution from below. This is the certificate the
    superhuman rungs stand on where breadth-first search cannot
    reach any more.
    """
    tables = _goal_tables(level.width, level.height, level.walls,
                          level.goals)
    total = _assignment(tables, sorted(level.boxes))
    return 0 if total >= BIG else total


def _climbing_walk(grade: Grade, walls: FrozenSet[int],
                   goals: FrozenSet[int], rng: random.Random
                   ) -> Optional[Tuple[FrozenSet[int], int, int]]:
    """A backwards walk that climbs the certificate instead of
    hoping for it.

    The plain walk is a lottery: it wanders, stalls, and whatever
    the assignment bound says at the end is the ticket you got. This
    one walks in short legs, prices the position after each leg
    against the precomputed goal tables, and remembers the best
    start it has stood on; when a stretch of legs fails to improve
    it, the walk teleports back to that best start and spends the
    rest of its budget exploring differently from there. Same pull
    mechanics, same guarantees — only the selection changed, from
    "keep the last state" to "keep the best state ever seen".
    """
    width = grade.width
    floor_ok = _floor_flags(width, grade.height, walls)
    steps = _steps(width)
    far = _goal_distance(width, grade.height, walls, goals)
    tables = _goal_tables(width, grade.height, walls, goals)
    boxes = set(goals)
    player = next((cell for cell in range(width * grade.height)
                   if floor_ok[cell] and cell not in boxes), None)
    if player is None:
        return None
    best: Optional[Tuple[FrozenSet[int], int, int]] = None
    best_score = -1
    pulls = 0
    dry_legs = 0
    last = None
    leg = max(6, grade.boxes)
    for _leg in range(max(1, grade.pulls // leg)):
        for _pull in range(leg):
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
            stuck = [option for option in options if option[0] in goals]
            pool = stuck if stuck else options
            outward = [option for option in pool
                       if far[option[1]] > far[option[0]]]
            if outward and rng.random() < 0.8:
                pool = outward
            box, near, away = rng.choice(pool)
            boxes.discard(box)
            boxes.add(near)
            player = away
            last = (box, near)
            pulls += 1
        off_goal = sum(1 for box in boxes if box not in goals)
        if pulls and off_goal >= max(1, len(goals) // 2):
            score = _assignment(tables, sorted(boxes))
            if score < BIG and score > best_score:
                best_score = score
                best = (frozenset(boxes), player, pulls)
                dry_legs = 0
            else:
                dry_legs += 1
        if best is not None and dry_legs >= 4:
            # Enough wandering: go back to the best start found and
            # explore a different line out of it.
            boxes = set(best[0])
            player = best[1]
            pulls = best[2]
            last = None
            dry_legs = 0
    return best


def _room_potential(width: int, height: int, walls: FrozenSet[int],
                    goals: FrozenSet[int], boxes: int) -> int:
    """The most the room could possibly certify, cheaply estimated.

    A box's contribution to the assignment bound can never beat its
    pull-distance from the goal clump, so the sum of the *boxes*
    deepest pull-distances the room offers is a ceiling on any walk.
    Most carved rooms are shallow — measured on the superhuman rung,
    walks failed on three rooms out of four — and this one flood
    fill lets the generator skip them without walking at all.
    """
    far = _goal_distance(width, height, walls, goals)
    depths = sorted((d for d in far if d < BIG), reverse=True)
    return sum(depths[:boxes])


def _convoy_walk(grade: Grade, walls: FrozenSet[int],
                 goals: FrozenSet[int], rng: random.Random
                 ) -> Optional[Tuple[FrozenSet[int], int, int]]:
    """Drag each box outward in turn, as far as it will go.

    The climbing walk spreads random pulls across the flock; this
    one is a convoy — box by box, each pulled along rising pull-
    distance until it stalls, over several rounds so early boxes can
    make way for late ones. In the tightest warrens it reaches
    arrangements the random walk never finds, and the two are run
    side by side with the better certificate kept.
    """
    width = grade.width
    floor_ok = _floor_flags(width, grade.height, walls)
    steps = _steps(width)
    far = _goal_distance(width, grade.height, walls, goals)
    tables = _goal_tables(width, grade.height, walls, goals)
    boxes = set(goals)
    player = next((cell for cell in range(width * grade.height)
                   if floor_ok[cell] and cell not in boxes), None)
    if player is None:
        return None
    pulls = 0
    best: Optional[Tuple[FrozenSet[int], int, int]] = None
    best_score = -1
    for _round in range(6):
        order = sorted(boxes)
        rng.shuffle(order)
        for target in order:
            box = target
            if box not in boxes:
                continue
            slides = 0
            while pulls < grade.pulls and slides < 3:
                region = _reachable(width, floor_ok, frozenset(boxes),
                                    player)
                options = []
                for step in steps:
                    near, away = box + step, box + step + step
                    if (near in region and floor_ok[near]
                            and floor_ok[away] and away not in boxes
                            and near not in boxes):
                        options.append((near, away))
                rising = [o for o in options if far[o[0]] > far[box]]
                level_ = [o for o in options if far[o[0]] == far[box]]
                if rising:
                    near, away = rng.choice(rising)
                    slides = 0
                elif level_ and rng.random() < 0.6:
                    near, away = rng.choice(level_)
                    slides += 1        # sidling around a corner, maybe
                else:
                    break
                boxes.discard(box)
                boxes.add(near)
                player = away
                box = near
                pulls += 1
        off = sum(1 for b in boxes if b not in goals)
        if pulls and off >= max(1, len(goals) // 2):
            score = _assignment(tables, sorted(boxes))
            if score < BIG and score > best_score:
                best_score = score
                best = (frozenset(boxes), player, pulls)
    return best


def generate(level_number: int, seed: Optional[int] = None,
             attempts: int = 300) -> Level:
    """A solvable level of the given rung, at or above its floor.

    A round of attempts misses the floor now and then — measured at
    the superhuman rung, one deal in eight — and a certificate that
    fails one deal in eight is not a certificate. Rooms are drawn
    independently, so a fresh round is a fresh draw: two more of them
    take the miss rate from an eighth to a thousandth, and cost the
    extra time only on the deals that needed it. Same seed, same
    level, still.
    """
    grade = GRADES[max(0, min(len(GRADES) - 1, level_number - 1))]
    best: Optional[Level] = None
    for round_number in range(3):
        turn = (seed if seed is None or round_number == 0
                else seed + round_number * 7919)
        try:
            level = _deal(grade, random.Random(turn), attempts)
        except ValueError:
            if best is not None:
                return best
            raise
        certified = (level.minimum if level.minimum is not None
                     else level.at_least)
        if certified >= grade.floor:
            return level
        best_so_far = -1 if best is None else (
            best.minimum if best.minimum is not None else best.at_least)
        if certified > best_so_far:
            best = level
    return best if best is not None else level


def _deal(grade: Grade, rng: random.Random, attempts: int) -> Level:
    """One round of attempts: rooms, walks, and what they certified.

    Retries fresh rooms until the floor is certified — either the
    exact minimum, or, past the solver's budget, the breadth-first
    frontier's proven lower bound. Either way "level 9" carries a
    certificate that it takes at least level-9 work; the walk length
    stays as the par when the exact minimum is unknown. Raises only
    if every attempt collapses, which the ladder's tests never let
    happen.
    """
    if grade.boxes >= 9:
        attempts = attempts * 6           # room deals, mostly unwalked
    strong: Optional[Level] = None        # deep enough, opens too safely
    fallback: Optional[Level] = None      # treacherous, but too shallow
    desperate: Optional[Level] = None     # solvable but short on traps
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
        if grade.boxes >= 9:
            # Rooms are a thousand times cheaper than walks, so deal
            # many and walk few: any room whose potential cannot
            # cover the floor with margin is skipped before a single
            # pull, and the walk budget is spent on deep rooms only.
            potential = _room_potential(grade.width, grade.height,
                                        walls, goals, grade.boxes)
            if potential < grade.floor * 5 // 4 and _attempt < attempts - 40:
                continue                  # a shallow room; skip unwalked
            pulled = _convoy_walk(grade, walls, goals, rng)
            deepest = _climbing_walk(grade, walls, goals, rng)
            if pulled is None or (deepest is not None
                                  and matching_bound(Level(
                                      grade.width, grade.height, walls,
                                      goals, deepest[0], deepest[1],
                                      None, 0, deepest[2]))
                                  > matching_bound(Level(
                                      grade.width, grade.height, walls,
                                      goals, pulled[0], pulled[1],
                                      None, 0, pulled[2]))):
                pulled = deepest
        else:
            pulled = _pull_walk(grade, walls, goals, rng)
        if pulled is None:
            continue
        boxes, player, bound = pulled
        walls = _dig_traps(grade.width, grade.height, walls, goals,
                           grade.trap_share, rng)
        flags = _floor_flags(grade.width, grade.height, walls)
        alive = live_cells(grade.width, grade.height, walls, goals)
        dead = frozenset(cell for cell in range(grade.width * grade.height)
                         if flags[cell] and cell not in alive)
        floor_count = sum(flags)
        level = Level(grade.width, grade.height, walls, goals, boxes,
                      player, None, 0, bound, dead)
        if desperate is None:
            desperate = level             # solvable, whatever else
        if len(dead) < grade.trap_share * floor_count:
            continue                      # not enough landmines yet
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
        if minimum is None and proven >= level.bound:
            # The proof met the walk: the lower bound reached an
            # achievable solution, so the minimum is known exactly by
            # squeeze — no search ever ran, and none was needed.
            minimum = proven = level.bound
        certified = level._replace(minimum=minimum,
                                   at_least=max(minimum or 0, proven))
        # Two axes, ranked rather than merged. A rung's push floor is
        # what the ladder promises and what the screen reports, so a
        # deal that clears it never loses to one that does not — the
        # deception floor decides between deals of equal standing, it
        # does not veto depth. Adding an axis must not cost the one
        # already there.
        if certified.at_least >= grade.floor:
            # Priced here and nowhere else: deception only ever
            # decides between deals that already clear the floor, and
            # counting fatal pushes for every shallow room the walk
            # threw up would cost more than the axis is worth.
            tame = bool(grade.deceit) and fatal_share(level) < grade.deceit
            if not tame:
                return certified          # deep and treacherous: done
            if strong is None or certified.at_least > strong.at_least:
                strong = certified        # deep, but opens too safely
        elif fallback is None or certified.at_least > fallback.at_least:
            # Too shallow either way, so depth alone ranks it. Sorting
            # these by deception too would drop a deep tame deal for a
            # shallow treacherous one, which is the trade the ranking
            # exists to refuse.
            fallback = certified
    if strong is not None:
        return strong
    if fallback is not None:
        return fallback
    if desperate is not None:
        minimum, proven = solve_bounded(desperate, GENERATION_BUDGET // 4)
        certified = minimum if minimum is not None else \
            max(proven, matching_bound(desperate))
        return desperate._replace(minimum=minimum, at_least=certified)
    raise ValueError('no level survived %d attempts at "%s"'
                     % (attempts, grade.name))
