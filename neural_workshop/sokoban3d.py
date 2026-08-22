# -*- coding: utf-8 -*-
"""3D Sokoban: the same warehouse, from inside it, with a plan of it
that was true when you walked in and has been out of date since your
first push.

The plan is pinned to the side of the screen. It shows the walls, the
goals, where you came in, and where every box stood at the moment the
door shut behind you. It is drawn once and never touched again. Two
things it will not tell you, and they are the two things you need:
where on it you currently are, and where the boxes are *now*.

That second one is what makes this a different task from the 3D Maze
next door rather than a reskin of it. There the world stands still and
only you move, so what you have to carry is your own place on a map
that stays true. Here every push falsifies the plan a little further,
and the errors are yours: the plan was right, you are the one who
moved the box, and if you cannot say where you put it then nothing on
screen will tell you. What is held in the head is not a position but a
*position and a world*, updated by arithmetic you do yourself, once
per action, without ever being shown the answer.

Sokoban is the right game to do this to, because Sokoban does not
forgive. A box pushed into a pocket never comes out. From above the
pocket is visible; from inside a corridor you see the wall in front of
the box and not the one behind it, and whether the push you are about
to make is the one that loses the warehouse is a question about a
model you are holding rather than about anything you can look at. The
screen says "stuck" when it happens —
:func:`~neural_workshop.sokoban.deadlocked` is sound rather than
complete, so it fires late rather than wrongly — but by then the push
is spent.

The warehouse itself is not new. It is dealt by
:mod:`neural_workshop.sokoban`, at the same rungs, from the same
generator, so level six here is the very same room level six is there.
What the view costs is measured rather than guessed:

* Turning costs a step, as it does in the 3D Maze, and for the same
  reason: with free turns a player spins on the spot at every cell,
  reads all four corridors and every box within sight of them for
  nothing, and the plan stops being the only account of where things
  are. Paying for a look is what makes looking a decision. So the par
  here is in *steps* rather than in pushes, and :func:`par` is its own
  exact minimum over ``(boxes, cell, facing)``.

* :func:`push_forgetful` is the foil for the half of the state the 3D
  Maze does not ask for. It knows exactly where it is standing and it
  plans perfectly; now and then it loses track of what it has done to
  the boxes and falls back on the plan on the wall, which was true
  when it walked in. It is the player the map is a trap for.

* :func:`push_slipping` is the 3D Maze's own foil brought over to a
  game that does not forgive: a player that plans perfectly from where
  it *believes* it is, and now and then fails to notice that it moved.
  In a maze one dropped update costs steps. Here the plan's next move
  is a push, the push goes in whichever direction the body is actually
  facing, and the wrong direction is often a corner.

The exact minimum is affordable further up the ladder than a plain
search over poses would suggest, because the walking between pushes
contracts away: a run is a sequence of pushes, the pose after a push
is decided by the push, and the cheapest walk between two poses is a
small breadth-first sweep over ``(cell, facing)`` in the box-avoiding
floor. So the search is Dijkstra over the same push-space
:mod:`neural_workshop.sokoban` searches, with the walk priced into
each edge instead of being free. Past its budget it reports its
frontier, which is a proven lower bound and never a guess — the same
contract the flat game keeps, and the screen says which it is holding.

The view is cast rather than rendered, one ray to a screen column, and
it does not care what a cell is made of, only whether it is solid. A
box is a wall that moves.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import heapq
import math
import random
from collections import deque
from typing import (Dict, FrozenSet, List, NamedTuple, Optional, Sequence,
                    Tuple)

from .sokoban import GRADES, Level, deadlocked, generate, live_cells
from .youarehere import (AHEAD, BACK, COLUMNS, FACINGS, FAR, FOV, LEFT,
                         MOVES, RIGHT, Mote, Pose, Sight, look)

#: How many states the step-minimum search settles before it gives up
#: and reports its frontier instead. Far smaller than the flat game's
#: push budget on purpose: every state settled here runs a little
#: breadth-first sweep of its own to price the walking, so one state
#: costs perhaps a thousand times what a push-space state costs. The
#: number is set by measurement — :mod:`tests.test_sokoban3d` sweeps
#: the ladder and is what says how far up exact solving reaches, and
#: how long a deal takes when it does.
STEP_BUDGET = 20000

#: The ladder, re-exported so a screen need not know where it lives.
LADDER = GRADES


class Solid(NamedTuple):
    """A grid with everything that stops a ray in one set.

    The ray caster in :mod:`neural_workshop.youarehere` asks a world
    for three things — how wide, how tall, and which cells are solid —
    and has no opinion about what solid is made of. That is exactly
    the reading this task wants: from inside a corridor a box is a
    wall, and the only difference is that this one will be somewhere
    else after you push it.
    """

    width: int
    height: int
    walls: FrozenSet[int]


class Outcome(NamedTuple):
    """How one foil's attempt at one warehouse ended."""

    #: One of four. ``'solved'`` and ``'stuck'`` are the world's own
    #: verdicts: every box home, or a position
    #: :func:`~neural_workshop.sokoban.deadlocked` can prove is lost.
    #: The other two are the belief's. ``'thinks it is done'`` is a
    #: player standing in a warehouse with boxes still out, holding a
    #: model in which it has finished — the failure this task is built
    #: to produce. ``'adrift'`` is everything else: no plan it can act
    #: on, or patience spent.
    ending: str
    steps: int


def blocking(level: Level, boxes: FrozenSet[int]) -> Solid:
    """The room as the eye finds it: rock and boxes, undistinguished."""
    return Solid(level.width, level.height, level.walls | boxes)


def look_around(level: Level, boxes: FrozenSet[int], pose: Pose,
                columns: int = COLUMNS,
                fov: float = FOV) -> Tuple[Sight, ...]:
    """The view from *pose*, one ray to a column, left edge first.

    Which of the cells it found are boxes is left to the caller, who
    has the box set in front of it and wants to colour them
    differently anyway.
    """
    return look(blocking(level, boxes), pose, columns=columns, fov=fov)


# --- standing in a warehouse ---------------------------------------------


def facing_at(level: Level) -> int:
    """Which way a player starts out looking.

    The first direction clockwise from north with floor in it, so a
    room always opens onto somewhere rather than onto rock. Read off
    the walls and not off the boxes, so the same seed always faces the
    same way however the generator's walk left the load.
    """
    for facing in range(len(FACINGS)):
        if step_to(level, level.player, facing) is not None:
            return facing
    return 0


def step_to(level: Level, cell: int, facing: int) -> Optional[int]:
    """The cell one step that way, or None when rock is in the way.

    Knows nothing about boxes — a box is something you may be able to
    move, not something that is not there, and the two want telling
    apart.
    """
    x, y = cell % level.width, cell // level.width
    dx, dy = FACINGS[facing]
    nx, ny = x + dx, y + dy
    if not (0 <= nx < level.width and 0 <= ny < level.height):
        return None
    step = ny * level.width + nx
    return None if step in level.walls else step


def move(level: Level, boxes: FrozenSet[int], pose: Pose, doing: str
         ) -> Tuple[Pose, FrozenSet[int], bool, bool]:
    """Do one thing. Returns the pose, the boxes, whether the player
    actually went anywhere, and whether a box went with it.

    Turning always works. Going forwards or backwards works when there
    is floor there; when a box is standing in it the box goes too, if
    the square beyond it is empty floor, and nothing at all happens if
    it is not.

    Walking *backwards* pushes just as well as walking forwards, which
    is not a flourish. A player who has just pushed a box is facing it,
    and reversing into the box behind them is often the cheapest next
    push there is; the solver knows about both, so the par is a par of
    what the keys can really do.
    """
    if doing == LEFT:
        return Pose(pose.cell, (pose.facing - 1) % 4), boxes, False, False
    if doing == RIGHT:
        return Pose(pose.cell, (pose.facing + 1) % 4), boxes, False, False
    facing = pose.facing if doing == AHEAD else (pose.facing + 2) % 4
    step = step_to(level, pose.cell, facing)
    if step is None:
        return pose, boxes, False, False
    if step in boxes:
        beyond = step_to(level, step, facing)
        if beyond is None or beyond in boxes:
            return pose, boxes, False, False
        return (Pose(step, pose.facing), (boxes - {step}) | {beyond},
                True, True)
    return Pose(step, pose.facing), boxes, True, False


def costs(doing: str, moved: bool) -> int:
    """What one action is charged: one step, unless it was a bump.

    A turn always costs, which is the whole reason the par here is not
    the flat game's push count. A walk costs when it walks, and a push
    is a walk. Walking into rock, or shoving a box that will not go,
    costs nothing — as in both mazes: what is in front of you is
    plainly visible from where you stand, so charging for the attempt
    would be charging for a typo. It also keeps the par honest, since a
    minimum that had to reason about wasted bumps would not be a
    minimum of anything a player is scored on.
    """
    return 1 if moved or doing in (LEFT, RIGHT) else 0


def solved(level: Level, boxes: FrozenSet[int]) -> bool:
    """Every box home."""
    return boxes <= level.goals


def stuck(level: Level, boxes: FrozenSet[int]) -> bool:
    """Provably lost, by the flat game's own test."""
    return deadlocked(level.width, level.height, level.walls, level.goals,
                      boxes)


# --- what a perfect run costs --------------------------------------------


def floor_of(level: Level) -> List[bool]:
    """Which cells a player or a box may stand on."""
    flags = [False] * (level.width * level.height)
    for cell in range(level.width * level.height):
        x, y = cell % level.width, cell // level.width
        if (0 < x < level.width - 1 and 0 < y < level.height - 1
                and cell not in level.walls):
            flags[cell] = True
    return flags


def walk_cost(level: Level, boxes: FrozenSet[int], pose: Pose,
              floor_ok: Optional[Sequence[bool]] = None) -> List[int]:
    """The cheapest walk from *pose* to every ``(cell, facing)``.

    Indexed ``cell * 4 + facing``, ``-1`` where there is no way at all.
    Turning and walking each cost one and a bump costs nothing, so
    plain breadth-first is already the shortest walk and there is
    nothing to weigh. Boxes are obstacles here rather than things to
    push: this is the walking *between* pushes, and a push is priced
    separately by the edge it opens.
    """
    if floor_ok is None:
        floor_ok = floor_of(level)
    reach = [-1] * (level.width * level.height * 4)
    first = pose.cell * 4 + pose.facing
    reach[first] = 0
    queue = deque((first,))
    while queue:
        state = queue.popleft()
        cell, facing = state >> 2, state & 3
        spent = reach[state] + 1
        for turned in ((facing - 1) % 4, (facing + 1) % 4):
            below = cell * 4 + turned
            if reach[below] < 0:
                reach[below] = spent
                queue.append(below)
        for way in (facing, (facing + 2) % 4):
            step = step_to(level, cell, way)
            if step is None or step in boxes or not floor_ok[step]:
                continue
            below = step * 4 + facing
            if reach[below] < 0:
                reach[below] = spent
                queue.append(below)
    return reach


def _pushes_from(level: Level, boxes: FrozenSet[int], reach: Sequence[int],
                 floor_ok: Sequence[bool], alive: FrozenSet[int]):
    """Every push open from a pose, with what the walk to it cost.

    Yields ``(cost, boxes after, pose after)``. A box goes one way when
    the player can stand behind it and the square beyond is empty
    floor; the player may face along the push and walk forward, or face
    away from it and reverse, and the two leave them facing opposite
    ways for one and the same price of a step. So both are real edges
    and both are offered.

    Boxes pushed somewhere no push could ever bring them home are
    dropped here rather than explored, which is the flat game's own
    pruning and a large part of why either search finishes at all.
    """
    width, cells = level.width, level.width * level.height
    for box in boxes:
        for facing, (dx, dy) in enumerate(FACINGS):
            stride = dy * width + dx
            behind, beyond = box - stride, box + stride
            if not (0 <= behind < cells and 0 <= beyond < cells):
                continue
            if not floor_ok[behind] or behind in boxes:
                continue
            if not floor_ok[beyond] or beyond in boxes:
                continue
            if beyond not in alive:
                continue
            moved = (boxes - {box}) | {beyond}
            for standing in (facing, (facing + 2) % 4):
                walked = reach[behind * 4 + standing]
                if walked < 0:
                    continue
                yield walked + 1, moved, Pose(box, standing)


def solve_bounded(level: Level, budget: int = STEP_BUDGET,
                  boxes: Optional[FrozenSet[int]] = None,
                  pose: Optional[Pose] = None
                  ) -> Tuple[Optional[int], int, List[str]]:
    """(exact minimum steps or None, proven lower bound, the route).

    Dijkstra over ``(boxes, cell, facing)``, contracted so that one
    edge is "walk to somewhere you can push from, and push". The walk
    is priced by :func:`walk_cost` and the push costs one on top, so
    the total is exactly what a player at the keyboard would spend.

    The lower bound costs nothing extra. States settle in order of
    cost, so when the budget dies every run still out there costs at
    least what the frontier is holding — and the flat game's certified
    push count is a second lower bound for free, since every push is a
    step. The larger of the two is reported and neither is a guess.

    *boxes* and *pose* are for the foils: handed a belief rather than
    the truth it returns the moves that would finish *that* warehouse,
    which is the whole trouble, because they are carried out in this
    one.
    """
    if boxes is None:
        boxes = level.boxes
    if pose is None:
        pose = Pose(level.player, facing_at(level))
    floor_ok = floor_of(level)
    alive = live_cells(level.width, level.height, level.walls, level.goals)
    pushes_at_least = (level.minimum if level.minimum is not None
                       else level.at_least)
    if solved(level, boxes):
        return 0, 0, []
    if any(box not in alive for box in boxes):
        return None, 0, []              # already lost; nothing to certify
    start = (boxes, pose)
    best: Dict[Tuple[FrozenSet[int], Pose], int] = {start: 0}
    came: Dict[Tuple[FrozenSet[int], Pose],
               Optional[Tuple[FrozenSet[int], Pose]]] = {start: None}
    queue: List[Tuple[int, int, Tuple[FrozenSet[int], Pose]]] = [
        (0, 0, start)]
    tick = 0
    settled = 0
    while queue:
        spent, _order, state = heapq.heappop(queue)
        if spent > best.get(state, -1):
            continue                    # a cheaper way there already went
        held, at = state
        # Settled, not merely reached. Edges here cost anything from one
        # step to a walk across the room, so the first solved position
        # the search *generates* is routinely not the cheapest one --
        # measured on the ladder, taking it cost up to a fifth over the
        # true minimum. A position is only known to be minimal when it
        # comes off the heap.
        if solved(level, held):
            return spent, spent, _unwind(level, came, state, floor_ok)
        settled += 1
        if settled > budget:
            return None, max(spent, pushes_at_least), []
        reach = walk_cost(level, held, at, floor_ok)
        for walked, moved, landed in _pushes_from(level, held, reach,
                                                  floor_ok, alive):
            below = (moved, landed)
            total = spent + walked
            if total >= best.get(below, 1 << 30):
                continue
            best[below] = total
            came[below] = state
            tick += 1
            heapq.heappush(queue, (total, tick, below))
    return None, pushes_at_least, []    # exhausted: generated levels do not


def _unwind(level: Level, came, state, floor_ok) -> List[str]:
    """The route, as the moves that walk it.

    Each edge is rebuilt rather than remembered. The walk from one pose
    to the next pushing position is the same breadth-first sweep the
    search already ran, and re-running a handful of them on the way
    back is cheaper than keeping every one of them alive throughout.

    Which push an edge was is read off the two box sets rather than
    guessed from the pose it landed in, because the pose does not say:
    a player facing north at a cell may have walked into the box ahead
    of it or reversed into the one behind, and those are two different
    pushes of two different boxes that happen to leave the body in the
    same place.
    """
    chain: List[Tuple[Tuple[FrozenSet[int], Pose],
                      Tuple[FrozenSet[int], Pose]]] = []
    walk = state
    while came[walk] is not None:
        chain.append((came[walk], walk))
        walk = came[walk]
    chain.reverse()
    walked_out: List[str] = []
    for (held, at), (moved, landed) in chain:
        (origin,) = held - moved
        (target,) = moved - held
        stride = target - origin
        doing = AHEAD if FACINGS[landed.facing] == _way(level, stride) \
            else BACK
        steps = _walk_route(level, held, at,
                            Pose(origin - stride, landed.facing), floor_ok)
        if steps is None:               # cannot happen: the edge existed
            return walked_out
        walked_out += steps + [doing]
    return walked_out


def _way(level: Level, stride: int) -> Tuple[int, int]:
    """The compass step one cell offset means."""
    if stride == 1:
        return (1, 0)
    if stride == -1:
        return (-1, 0)
    return (0, 1) if stride > 0 else (0, -1)


def _walk_route(level: Level, boxes: FrozenSet[int], pose: Pose,
                want: Pose, floor_ok) -> Optional[List[str]]:
    """The moves that walk from *pose* to *want*, or None when there is
    no way at all. Breadth-first over ``(cell, facing)``, as above."""
    first = pose.cell * 4 + pose.facing
    target = want.cell * 4 + want.facing
    came: Dict[int, Optional[Tuple[int, str]]] = {first: None}
    queue = deque((first,))
    while queue:
        at = queue.popleft()
        if at == target:
            walked: List[str] = []
            while came[at] is not None:
                at, doing = came[at]
                walked.append(doing)
            walked.reverse()
            return walked
        cell, facing = at >> 2, at & 3
        for doing, turned in ((LEFT, (facing - 1) % 4),
                              (RIGHT, (facing + 1) % 4)):
            below = cell * 4 + turned
            if below not in came:
                came[below] = (at, doing)
                queue.append(below)
        for doing, way in ((AHEAD, facing), (BACK, (facing + 2) % 4)):
            step = step_to(level, cell, way)
            if step is None or step in boxes or not floor_ok[step]:
                continue
            below = step * 4 + facing
            if below not in came:
                came[below] = (at, doing)
                queue.append(below)
    return None


def par(level: Level, budget: int = STEP_BUDGET) -> int:
    """What a run is judged against: the exact step minimum, or the
    proven lower bound where the search could not afford one."""
    found, bound, _route = solve_bounded(level, budget)
    return bound if found is None else found


def route(level: Level, budget: int = STEP_BUDGET) -> List[str]:
    """One cheapest run, as the moves that walk it. Empty past budget."""
    return solve_bounded(level, budget)[2]


def certified(level: Level, budget: int = STEP_BUDGET) -> bool:
    """Whether the par is a minimum rather than a proven lower bound."""
    return solve_bounded(level, budget)[0] is not None


# --- what can be seen ----------------------------------------------------


def marks(level: Level, boxes: FrozenSet[int], pose: Pose,
          fov: float = FOV) -> Tuple[Mote, ...]:
    """The goals still wanting a box, as seen from *pose*.

    The plan already says where every goal is, so catching sight of one
    is what lets a player who has been counting corridors check its
    answer. Boxes are not marks: they are solid, they are in the view
    already, and a box drawn as a hovering ring as well as a block
    would say twice over what the eye can see once.
    """
    solid = blocking(level, boxes)
    from_x = pose.cell % level.width + 0.5
    from_y = pose.cell // level.width + 0.5
    face_x, face_y = FACINGS[pose.facing]
    edge = math.tan(fov / 2.0)
    found: List[Mote] = []
    for goal in sorted(level.goals - boxes):
        at_x = goal % level.width + 0.5 - from_x
        at_y = goal // level.width + 0.5 - from_y
        depth = at_x * face_x + at_y * face_y
        if depth <= 0.05:
            continue
        sideways = at_x * -face_y + at_y * face_x
        across = (sideways / depth / edge + 1.0) / 2.0
        if not -0.2 <= across <= 1.2:
            continue
        if not clear_between(solid, pose.cell, goal):
            continue
        found.append(Mote('goal', -1, goal, across, depth))
    found.sort(key=lambda mote: -mote.distance)
    return tuple(found)


def clear_between(solid: Solid, here: int, there: int) -> bool:
    """True when nothing solid stands between two cells.

    Only ever asked about cells sharing a row or a column, because
    those are the only ones a mark can be seen down: a warren corridor
    is one cell wide and anything off the straight is behind a corner.
    A box counts as solid, so a goal behind a box is out of sight —
    which is right, and is one of the ways a player finds out that the
    plan and the room have parted company.
    """
    hx, hy = here % solid.width, here // solid.width
    tx, ty = there % solid.width, there // solid.width
    if hx != tx and hy != ty:
        return False
    step = (0, 1 if ty > hy else -1) if hx == tx else (1 if tx > hx else -1, 0)
    x, y = hx, hy
    while (x, y) != (tx, ty):
        x, y = x + step[0], y + step[1]
        if y * solid.width + x in solid.walls:
            return False
    return True


# --- players -------------------------------------------------------------


def push_perfect(level: Level, budget: int = STEP_BUDGET) -> int:
    """Follow the minimum. What the screen scores a run against."""
    return par(level, budget)


def _run(level: Level, forget: float, slip: float, rng: random.Random,
         cap: int, budget: int) -> Outcome:
    """The body both foils share: plan from a belief, act on the world.

    One loop rather than two because the two differ in one line each —
    which part of the belief goes wrong — and writing it twice would
    invite the two to drift into measuring different things.

    Re-planning happens only when the plan runs out or the belief is
    disturbed, and that is not an optimisation with a hole in it: while
    the belief advances along its own plan the remaining plan is still
    the cheapest run from it, so re-planning every step would return
    the same tail. When the belief *is* disturbed the plan is thrown
    away and made again, which is exactly re-planning every step would
    have done.
    """
    boxes, pose = level.boxes, Pose(level.player, facing_at(level))
    believes, thinks = boxes, pose
    steps, acted = 0, 0
    plan: List[str] = []
    while acted < cap:
        if solved(level, boxes):
            return Outcome('solved', steps)
        if stuck(level, boxes):
            return Outcome('stuck', steps)
        if not plan:
            if solved(level, believes):
                return Outcome('thinks it is done', steps)
            plan = solve_bounded(level, budget, believes, thinks)[2]
            if not plan:
                return Outcome('adrift', steps)
        doing = plan.pop(0)
        acted += 1
        pose, boxes, moved, pushed = move(level, boxes, pose, doing)
        steps += costs(doing, moved)
        if rng.random() < slip:
            plan = []                   # never noticed it moved at all
            continue
        thinks, believes, _m, _p = move(level, believes, thinks, doing)
        if pushed and rng.random() < forget:
            # It has lost track of what it did to the load, so it does
            # what a person does: looks at the plan on the wall again.
            believes = level.boxes
            plan = []
    return Outcome('adrift', steps)


def push_forgetful(level: Level, forget: float, rng: random.Random,
                   cap: int = 400, budget: int = STEP_BUDGET) -> Outcome:
    """Knows exactly where it is; loses track of what it moved.

    The foil for the half of the state the 3D Maze does not ask for.
    Its own position is tracked perfectly and it never once walks into
    the wrong corridor. What it drops is the load: after a push, with
    probability *forget*, it can no longer say where the boxes are and
    falls back on the plan pinned to the wall — which was true when it
    walked in and has not been true since.

    It does not reconcile what it sees with what it believes,
    deliberately: what is being measured is what the boxes are worth to
    remember, and a player that looked again would be measuring its
    looking.
    """
    return _run(level, forget, 0.0, rng, cap, budget)


def push_slipping(level: Level, slip: float, rng: random.Random,
                  cap: int = 400, budget: int = STEP_BUDGET) -> Outcome:
    """Plans perfectly from where it *thinks* it is, and slips sometimes.

    The 3D Maze's own foil, brought over to a game that does not
    forgive. There, one dropped update costs steps and the maze is
    still winnable. Here the plan's next move is a push, the push goes
    in whichever direction the body is actually facing, and a box
    shoved the wrong way is often a box in a corner.

    Its belief covers the whole world — its pose and the boxes — and
    the update it drops is the whole update, which is what makes this
    the same foil rather than a second one.
    """
    return _run(level, 0.0, slip, rng, cap, budget)


def deal(level_number: int, seed: Optional[int] = None) -> Level:
    """A warehouse at *level_number*, from the flat game's own ladder.

    Deliberately not a ladder of its own. Level six here is the room
    level six is there, so what the view costs can be read off the two
    pars rather than guessed at across two sets of rungs that were
    tuned separately.
    """
    return generate(level_number, seed=seed)


__all__ = ['AHEAD', 'BACK', 'COLUMNS', 'FACINGS', 'FAR', 'FOV', 'LADDER',
           'LEFT', 'MOVES', 'Mote', 'Outcome', 'Pose', 'RIGHT', 'Sight',
           'STEP_BUDGET', 'Solid', 'blocking', 'certified', 'clear_between',
           'costs', 'deal', 'facing_at', 'floor_of', 'look_around', 'marks',
           'move', 'par', 'push_forgetful', 'push_perfect', 'push_slipping',
           'route', 'solve_bounded', 'solved', 'step_to', 'stuck',
           'walk_cost']
