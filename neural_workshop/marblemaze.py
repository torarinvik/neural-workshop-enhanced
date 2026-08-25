# -*- coding: utf-8 -*-
"""The Marble Maze: a tilting tray, a rolling ball, and a hole to miss.

The wooden labyrinth. Two knobs tip a tray, the tray has walls and
holes in it, and a steel marble goes where gravity tells it. This
module is the tray and the marble; :mod:`neural_workshop.ui.marblemaze`
is the picture of them, and it draws in three dimensions because a
tilted board seen flat is not the same task at all — the tilt *is* the
control, and a control you cannot see is a control you cannot learn.

Nothing here imports pyglet. The whole of the simulation is testable
without a GL context and :mod:`tests.test_marblemaze` does exactly that.
The dynamics themselves are MuJoCo's — the one heavyweight dependency
this workshop carries, and it carries it for this task alone.

Three things in here are worth reading before changing anything.

**The five sevenths is derived, not applied.** A solid sphere rolling
without slipping down a plane inclined at θ accelerates at
``g·sinθ / (1 + I/mr²)``, which for ``I = 2/5·mr²`` is ``5/7·g·sinθ``:
two sevenths of gravity goes into spin rather than travel. Nothing here
multiplies by five sevenths — the marble is a rigid sphere in MuJoCo's
contact solver, which resolves the friction at the contact patch every
substep, and five sevenths falls out of that, along with what a marble
does after a wall has broken its roll: skid, until the tray drags it
round. The tests measure the factor rather than restating it. What the
engine cannot say is the *threshold* half of rolling resistance — its
regularised torque lets a marble creep on a slope too shallow to
really start it — so :class:`Simulation` keeps a rest clamp that makes
``atan(Crr)`` a true stall angle. See the class docstring for the full
division of labour between engine and wrapper.

**A hole is not a wall.** A marble whose contact patch crosses the rim
stops being supported and starts to *fall*: no contact, so no friction
and no change of spin, and the whole of gravity rather than five
sevenths of it. It gets out only over the far lip and only by paying
for the climb — its centre has dropped, and ``2·g·drop`` comes out of
its speed squared to put it back. Fast enough and it comes over with
something to spare. That is a real property of the real toy — you can
outrun a small hole — and it is the reason the capture test is on the
marble's height rather than on its position. Treating a hole as a disc
that kills on contact removes it, and with it the only reason to ever
go fast.

**The board is certified passable before it is dealt.** Holes are
proposed one at a time against a cheap analytic clearance test, and
then the whole tray is certified once by a Dijkstra sweep over a grid
of every place the marble's *centre* may legally be. A tray that has
been sealed off by its own holes is not dealt. This matters more than
it sounds: the ladder's upper rungs run corridors two marble-widths
wide with holes bitten out of them, and "unwinnable" and "very hard"
are indistinguishable from the outside. That sweep is also where the
distance field comes from, so the coach in
:mod:`nwenv.marblemaze` and the certificate are the same computation
and cannot disagree.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import heapq
import math
import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

import mujoco

# --- the physical world ----------------------------------------------------
#
# SI throughout: metres, seconds, kilograms. The numbers are the real
# toy's. A Brio labyrinth is a shade over 30cm square and takes a 15mm
# steel marble, and keeping those rather than inventing screen units is
# what lets the constants below be looked up rather than tuned.

#: Standard gravity, m/s².
GRAVITY = 9.80665

#: The reference tray, metres — the real toy is a shade over 305mm
#: across. A rung's tray is built from its corridor width outwards and
#: so is not always this size: see :attr:`Grade.slack`. These are what
#: the renderer falls back to when there is no tray to draw yet.
BOARD_WIDTH = 0.305
BOARD_DEPTH = 0.270

#: The tray's inner lip, metres — how much bare board there is between
#: the maze's outermost wall and the rail around the tray. Small, and
#: deliberately: that strip is walled off from the maze, so nothing can
#: ever be there, and a wide one is dead board that reads as somewhere
#: the marble ought to be able to go.
BOARD_MARGIN = 0.004

#: Wall thickness as a share of the cell it bounds.
WALL_SHARE = 0.11

#: A 15mm steel marble.
MARBLE_RADIUS = 0.0075

#: A solid sphere's moment of inertia, in units of ``m·r²``. The
#: engine derives it from the sphere geom; it is named here because
#: the numbers the tests check against come out of it.
SPHERE_INERTIA = 2.0 / 5.0

#: What the contact patch keeps back, and what is left over for travel.
#: An impulse at the contact point moves the *contact* by
#: ``1 + 1/SPHERE_INERTIA = 7/2`` times what it moves the centre, so
#: the friction holding a roll together is two sevenths of whatever
#: drives the ball and five sevenths reaches the tray as travel.
#: Neither number is used by the physics — the engine produces them —
#: but the tests that measure the engine are written in these terms.
SLIP_SHARE = SPHERE_INERTIA / (1.0 + SPHERE_INERTIA)     # 2/7
ROLL_FACTOR = 1.0 / (1.0 + SPHERE_INERTIA)               # 5/7

#: Coulomb friction at the contact patch, steel on varnished hardwood.
#: Handbook values sit about here. The engine takes one coefficient,
#: not a static/kinetic pair; it only ever bites when something has
#: broken the roll, because gravity alone asks the patch for two
#: sevenths of ``g·sinθ``, a twelfth of what it can hold at this
#: tray's steepest tilt.
FRICTION_STATIC = 0.50

#: Rolling resistance, dimensionless: how far ahead of the contact
#: point the normal force's line of action rides, in ball radii. Steel
#: on varnished hardwood is nearer 0.002; this is four times that,
#: because the real tray's surface is neither flat nor clean. Tuned by
#: play, twice: a slicker board (0.006, with the drag at 0.25) was
#: tried and taken back. With the drag below, a marble at half the
#: cap coasts about 1.2m of open board, which is the feel that won.
#: It enters the engine as its rolling-friction coefficient (scaled
#: by the radius, since MuJoCo's is a length), so the deceleration on
#: the flat is a consequence rather than a line of code. The *stall* half
#: — a slope of ``atan(Crr)`` below which nothing starts — is the
#: wrapper's rest clamp: the engine's regularised torque cannot
#: refuse to move, only resist.
ROLLING_RESISTANCE = 0.008

#: Viscous drag per second — the air, and the varnish. Its visible job
#: is to keep the top end of a long straight run finite, and it is the
#: biggest single term in how far a rolling marble coasts, so it is
#: the first knob to reach for when the board feels sticky or slick.
#: Lower than it reads, because the noslip solver now delivers the
#: whole of the dry rolling resistance that the regularised contact
#: used to shave: at 0.35 beside that, the coast came out a fifth
#: shorter than the board this number was chosen on. 0.22 restores
#: the measured coast — 1.2m of open board from half the cap — that
#: play settled on.
VISCOUS_DRAG = 0.22

#: The engine's torsional friction at the floor contact, a length in
#: MuJoCo's terms. This is what winds down a marble that has come off
#: a wall turning like a top — the turn has only the contact patch to
#: work against, so it dies there.
SPIN_GRIP = 0.005

#: Below this speed a marble nothing is driving is *stopped* rather
#: than slowed. Rolling resistance is a threshold and not a decay, and
#: a tray the player has levelled has to be level rather than nearly
#: so. Six millimetres a second is a tenth of one per frame — well
#: under half a screen pixel — and it is deliberately not smaller:
#: the engine's regularised rolling friction fades with speed, so a
#: lower bar leaves a levelled marble crawling its last centimetre
#: for ten visible seconds, which is the sticky-board lie from the
#: other direction.
REST_SPEED = 0.006

#: Restitution, steel on wood. Measured values for a hardwood rail sit
#: between 0.2 and 0.3; a labyrinth's walls are thin and give a little.
#:
#: This is the *impact* and only the impact. What a player sees a wall
#: do is mostly not this: the marble arrives spinning the way it was
#: going, keeps most of that spin through the blow, and then has to be
#: dragged round to a new roll by the tray — which takes the rebound
#: back out of it, and leaves it near the wall rather than crossing
#: the corridor. The engine's default contact happens to land right in
#: the measured steel-on-wood band, so this number is documentation
#: and a test bound rather than an input.
WALL_RESTITUTION = 0.28

#: Coulomb friction against a wall. Deliberately *low*, and lower than
#: the varnish figure a handbook would give, because it is the knob
#: that decides how much of the marble's roll survives an impact: the
#: friction acts over the finite contact the engine resolves, and at
#: the tray's own 0.5 it eats the spin whole, which turns every wall
#: hit into a slow drift back across the corridor. At this value a
#: graze still puts spin about the normal into the ball — the scuff a
#: corridor wall gives a real marble — while a square hit keeps its
#: roll and settles at the wall.
WALL_FRICTION = 0.08

#: Restitution, steel on steel: the damping ratio of the ball-ball
#: contact pair is set for the textbook figure for a polished pair.
#: Nothing is discounted for the energy a pair sheds into spin — both
#: balls leave the impact skidding, and the tray drags each back to a
#: roll, which is where that third of the striker's speed goes.
BALL_RESTITUTION = 0.92

#: A speed clamp, m/s. Physically it stands in for the terminal speed a
#: marble reaches against resistance on a tray this size — a real one
#: does not pass about 0.8 m/s before it runs out of board. It is also
#: load-bearing for the coach: see :data:`POTENTIAL_QUANTUM`.
SPEED_CAP = 1.0

#: Physics substeps per rendered frame. One substep of a 60Hz step is
#: about 4ms, in which a capped marble moves 4mm — comfortably inside
#: a wall's thickness, so the engine's contacts are never asked to
#: catch a marble that has already passed through.
SUBSTEPS = 4

#: The most the tray tips, radians. Eight degrees. Past about ten the
#: marble spends the whole board accelerating and nothing is steerable.
MAX_TILT = 0.140

#: One nudge of a knob, radians. Full tilt in twenty-three nudges, so a
#: held key reaches the stops in about four tenths of a second.
TILT_STEP = 0.006

#: Knob axes and directions, as the ports and the arrow keys see them.
#:
#: **Named for where the marble goes, not for which edge lifts.**
#: :data:`TILT_NORTH` sends the marble north, which it does by dropping
#: the north edge. The two conventions are equally sayable and the
#: distinction is invisible from the call site, so it is worth being
#: blunt: east and west were always the marble's way round, north and
#: south were once the edge's, and half a compass pointing each way is
#: a trap rather than a convention. :meth:`Simulation.tilt` is where
#: this is turned into a sign and
#: :mod:`tests.test_marblemaze` drives all four knobs to pin it.
TILT_NORTH, TILT_SOUTH, TILT_WEST, TILT_EAST = 'N', 'S', 'W', 'E'

# --- the coach's yardstick -------------------------------------------------

#: How coarse the shaping potential is, metres. The rule the workshop
#: imposes on a dense reward is that one action may change the potential
#: by at most one step; then the sign of the change *is* the
#: potential-based shaping term of Ng et al., every loop of actions
#: telescopes to nought, and the best policy is the one the sparse
#: verdict already wanted.
#:
#: Here that rule is a *geometric* guarantee rather than a hope. The
#: potential is ``floor(d / QUANTUM)`` over a geodesic distance field,
#: and a geodesic distance is 1-Lipschitz — it cannot change by more
#: than the distance actually travelled. A tick moves a marble at most
#: ``SPEED_CAP/60 = 16.7mm``, comfortably under the quantum, so the
#: floor moves by one step or none. :mod:`tests.test_marblemaze`
#: asserts that inequality rather than trusting this paragraph.
#:
#: The margin is a third rather than a hair, because the field is a
#: *grid* geodesic and an eight-connected grid metric overstates a
#: diagonal by a few percent. A quantum only just larger than a
#: tick's travel would be within that error, and the guarantee would
#: hold in the arithmetic while failing on the tray.
POTENTIAL_QUANTUM = 0.025

#: Grid pitch of the clearance sweep, metres. Fine enough that a gap
#: the marble fits through is not closed by rounding — the narrowest
#: corridor on the ladder is still eight cells across — and coarse
#: enough that the sweep stays inside a frame. It is the cost driver
#: when a tray is dealt: halving it quadruples the sweep.
SWEEP_PITCH = MARBLE_RADIUS / 2.5


class Grade(NamedTuple):
    """One rung. Everything that makes a tray harder than the last one."""

    #: Shown to the player.
    name: str
    #: Maze cells across and up.
    cols: int
    rows: int
    #: Corridor width, in marble *diameters*. This is what sizes the
    #: tray: the cell follows from it, and the tray follows from the
    #: cell, so a bigger maze is a bigger tray rather than a tighter
    #: one.
    #:
    #: Tightening instead was the first attempt and it cost the top
    #: rungs their holes. A hole has to sit in a corridor with the
    #: marble still able to squeeze past, which needs
    #: ``2·slack > hole_scale + margin_scale + 1``; on a 305mm tray
    #: with twelve columns that inequality fails, and the placement
    #: answered by shoving the holes out under the walls, where they
    #: are a notch bitten out of a corridor edge rather than a hazard
    #: in the road. :mod:`tests.test_marblemaze` asserts the inequality
    #: for every rung.
    slack: float
    #: Fraction of dead ends opened into loops. Nought is a perfect
    #: maze — one route, no choices. Braiding buys route choice at the
    #: cost of making a wrong turn cheap.
    braid: float
    #: How many holes to bite out of the tray.
    holes: int
    #: Hole radius, as a multiple of the marble's. Under one and a
    #: marble bridges it; the real toy's are about two.
    hole_scale: float
    #: How much room a marble must have to squeeze past a hole, as a
    #: multiple of its own radius. This is the rung's real teeth.
    margin_scale: float
    #: Marbles on the tray at once. They all obey the one tilt, which
    #: is what makes the fourth one worse than the third.
    marbles: int
    #: Seconds allowed.
    seconds: float


#: The ladder. Difficulty comes from four things that move more or less
#: independently: how long the route is (``cols``/``rows``), how much
#: room there is to make a mistake in (``slack``), how many ways there
#: are to lose (``holes``, ``hole_scale``, ``margin_scale``), and how
#: many marbles are obeying the one pair of knobs.
#:
#: Marble counts stay low and arrive late. Two marbles sharing one tilt
#: is a much bigger step than it looks — putting four on rung five made
#: every rung above it unreadable, because the tray was already
#: unwinnable and the rest of the ladder had nothing left to add.
GRADES: Tuple[Grade, ...] = (
    Grade('the tray',        4,  4, 3.40, 0.00,  0, 2.0, 1.60, 1,  45.0),
    Grade('first hole',      4,  4, 3.20, 0.00,  1, 2.0, 1.40, 1,  45.0),
    Grade('three holes',     5,  4, 3.00, 0.10,  3, 2.0, 1.30, 1,  50.0),
    Grade('the long way',    5,  5, 2.85, 0.10,  5, 1.9, 1.20, 1,  55.0),
    Grade('two marbles',     5,  5, 2.85, 0.05,  4, 1.9, 1.30, 2,  70.0),
    Grade('narrow',          6,  5, 2.70, 0.15,  7, 1.8, 1.10, 1,  60.0),
    Grade('narrow, twice',   6,  6, 2.70, 0.15,  8, 1.8, 1.15, 2,  78.0),
    Grade('the sieve',       7,  6, 2.55, 0.20, 11, 1.7, 1.00, 1,  65.0),
    Grade('three marbles',   7,  6, 2.60, 0.10,  9, 1.7, 1.15, 3,  95.0),
    Grade('tight',           8,  7, 2.40, 0.20, 14, 1.6, 0.95, 1,  72.0),
    Grade('tight, in pairs', 8,  7, 2.45, 0.15, 13, 1.6, 1.00, 2,  90.0),
    Grade('the labyrinth',   9,  8, 2.25, 0.25, 18, 1.5, 0.90, 1,  80.0),
    Grade('four marbles',    9,  8, 2.35, 0.10, 14, 1.5, 1.05, 4, 120.0),
    Grade('a hole a cell',  10,  9, 2.10, 0.25, 24, 1.4, 0.85, 1,  88.0),
    Grade('the gauntlet',   11,  9, 2.05, 0.30, 30, 1.4, 0.80, 2, 110.0),
    Grade('inhuman',        12, 10, 1.95, 0.30, 38, 1.3, 0.75, 3, 140.0),
)


def clamped_rung(rung: int) -> int:
    return max(1, min(len(GRADES), int(rung)))


class Wall(NamedTuple):
    """One wall strip, an axis-aligned box on the tray."""

    x0: float
    y0: float
    x1: float
    y1: float


class Hole(NamedTuple):
    """A hole in the tray. *home* means it is the cup rather than a pit."""

    x: float
    y: float
    radius: float
    home: bool


class Tray(NamedTuple):
    """One dealt board: its walls, its holes, and where the marbles start."""

    rung: int
    cols: int
    rows: int
    #: The playing surface, metres. Grows with the maze rather than
    #: subdividing a fixed square: see :attr:`Grade.slack`.
    width: float
    depth: float
    #: Metres per maze cell.
    cell: float
    #: Wall strip thickness and height, metres.
    thickness: float
    height: float
    walls: Tuple[Wall, ...]
    holes: Tuple[Hole, ...]
    starts: Tuple[Tuple[float, float], ...]
    #: Where the cup is, and how wide.
    home: Tuple[float, float, float]
    seconds: float
    #: The geodesic field the cup induces over legal marble centres, and
    #: the sweep that produced it. See :func:`potential_at`.
    field: 'Field'
    #: Shortest legal route from the furthest marble to the cup, metres.
    route: float

    @property
    def corridor(self) -> float:
        return self.cell - self.thickness


class Field(NamedTuple):
    """A geodesic distance-to-cup field over the tray, in metres."""

    #: Grid origin (the centre of cell 0,0) and pitch, metres.
    x0: float
    y0: float
    pitch: float
    cols: int
    rows: int
    #: Row-major, ``None`` where the marble's centre may not be.
    dist: Tuple[Optional[float], ...]

    def strict(self, x: float, y: float) -> Optional[float]:
        """Distance at exactly this point. None means *unreachable*.

        What certification asks. :meth:`at` widens by a ring to stay
        useful for a marble pressed against a wall, and that widening
        would let a start point sitting one grid cell inside a sealed
        pocket borrow its neighbour's answer — which is the one
        question a certificate exists to get right.
        """
        i = int(round((x - self.x0) / self.pitch))
        j = int(round((y - self.y0) / self.pitch))
        if not (0 <= i < self.cols and 0 <= j < self.rows):
            return None
        return self.dist[j * self.cols + i]

    def at(self, x: float, y: float) -> Optional[float]:
        """Distance to the cup from *(x, y)*, or None off the free space."""
        i = int(round((x - self.x0) / self.pitch))
        j = int(round((y - self.y0) / self.pitch))
        if not (0 <= i < self.cols and 0 <= j < self.rows):
            return None
        got = self.dist[j * self.cols + i]
        if got is not None:
            return got
        # A marble resting hard against a wall rounds to a cell its
        # centre may not occupy. Widening by one ring costs eight
        # lookups and stops the coach going blind exactly when the
        # player is doing the sensible thing.
        best: Optional[float] = None
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                a, b = i + di, j + dj
                if 0 <= a < self.cols and 0 <= b < self.rows:
                    near = self.dist[b * self.cols + a]
                    if near is not None and (best is None or near < best):
                        best = near
        return best


def potential_at(tray: Tray, x: float, y: float) -> Optional[int]:
    """The coach's potential: the distance field, quantised.

    Quantised because the shaping rule needs one action to move it by
    at most one step, and :data:`POTENTIAL_QUANTUM` is chosen against
    :data:`SPEED_CAP` so that it does. Returns None off the free space,
    where there is nothing honest to say.
    """
    got = tray.field.at(x, y)
    return None if got is None else int(got / POTENTIAL_QUANTUM)


# --- generating a maze -----------------------------------------------------

#: North, south, west, east as (dcol, drow) with their opposites.
_STEPS = ((0, 1), (0, -1), (-1, 0), (1, 0))
_OPPOSITE = (1, 0, 3, 2)


def _carve(cols: int, rows: int, rng: random.Random) -> List[List[bool]]:
    """A perfect maze by recursive backtracking.

    ``open_[cell][d]`` is whether cell *cell* has a doorway in
    direction *d*. Iterative rather than recursive because a 12x10 tray
    is 120 cells deep in the worst case and the ladder's top rung is
    exactly that shape.
    """
    total = cols * rows
    opened = [[False] * 4 for _ in range(total)]
    seen = [False] * total
    start = rng.randrange(total)
    seen[start] = True
    stack = [start]
    while stack:
        cell = stack[-1]
        col, row = cell % cols, cell // cols
        choices = []
        for d, (dc, dr) in enumerate(_STEPS):
            a, b = col + dc, row + dr
            if 0 <= a < cols and 0 <= b < rows and not seen[b * cols + a]:
                choices.append((d, b * cols + a))
        if not choices:
            stack.pop()
            continue
        d, nxt = rng.choice(choices)
        opened[cell][d] = True
        opened[nxt][_OPPOSITE[d]] = True
        seen[nxt] = True
        stack.append(nxt)
    return opened


def _braid(opened: List[List[bool]], cols: int, rows: int, share: float,
           rng: random.Random) -> None:
    """Open *share* of the dead ends into loops, in place.

    A perfect maze has exactly one route and so exactly one decision
    per junction, which is no decision at all. Braiding buys route
    choice — and on this tray it buys something the flat mazes next
    door do not have, because two routes of equal length are not
    equally easy when one of them turns four times.
    """
    if share <= 0:
        return
    ends = [cell for cell in range(cols * rows)
            if sum(opened[cell]) == 1]
    rng.shuffle(ends)
    for cell in ends[:int(round(len(ends) * share))]:
        col, row = cell % cols, cell // cols
        shut = []
        for d, (dc, dr) in enumerate(_STEPS):
            a, b = col + dc, row + dr
            if 0 <= a < cols and 0 <= b < rows and not opened[cell][d]:
                shut.append((d, b * cols + a))
        if shut:
            d, nxt = rng.choice(shut)
            opened[cell][d] = True
            opened[nxt][_OPPOSITE[d]] = True


def _cell_distances(opened: Sequence[Sequence[bool]], cols: int, rows: int,
                    source: int) -> List[int]:
    """Doorway-counting distance from *source*, for choosing a far cup."""
    far = [-1] * (cols * rows)
    far[source] = 0
    queue = [source]
    at = 0
    while at < len(queue):
        cell = queue[at]
        at += 1
        col, row = cell % cols, cell // cols
        for d, (dc, dr) in enumerate(_STEPS):
            if not opened[cell][d]:
                continue
            a, b = col + dc, row + dr
            nxt = b * cols + a
            if far[nxt] < 0:
                far[nxt] = far[cell] + 1
                queue.append(nxt)
    return far


def _wall_strips(opened: Sequence[Sequence[bool]], cols: int, rows: int,
                 cell: float, thick: float, ox: float, oy: float
                 ) -> Tuple[Wall, ...]:
    """Turn doorway flags into the boxes the marble actually hits.

    Runs of collinear wall are merged, which is worth doing twice over:
    a 12x10 tray goes from about 240 strips to about 90, and the
    renderer draws one box per strip.
    """
    half = thick / 2.0

    def wall_between(col: int, row: int, d: int) -> bool:
        if not (0 <= col < cols and 0 <= row < rows):
            return False
        return not opened[row * cols + col][d]

    strips: List[Wall] = []
    # Horizontal walls: for each lattice row, the runs of columns whose
    # cell below (or the boundary) is closed off upward.
    for line in range(rows + 1):
        run_start: Optional[int] = None
        for col in range(cols + 1):
            solid = False
            if col < cols:
                if line == 0:
                    solid = True
                elif line == rows:
                    solid = True
                else:
                    solid = wall_between(col, line - 1, 0)
            if solid and run_start is None:
                run_start = col
            elif not solid and run_start is not None:
                strips.append(Wall(
                    ox + run_start * cell - half, oy + line * cell - half,
                    ox + col * cell + half, oy + line * cell + half))
                run_start = None
    # Vertical walls, the same sweep turned ninety degrees.
    for line in range(cols + 1):
        run_start: Optional[int] = None
        for row in range(rows + 1):
            solid = False
            if row < rows:
                if line == 0 or line == cols:
                    solid = True
                else:
                    solid = wall_between(line - 1, row, 3)
            if solid and run_start is None:
                run_start = row
            elif not solid and run_start is not None:
                strips.append(Wall(
                    ox + line * cell - half, oy + run_start * cell - half,
                    ox + line * cell + half, oy + row * cell + half))
                run_start = None
    return tuple(strips)


# --- certifying a tray -----------------------------------------------------


def _free_grid(tray_walls: Sequence[Wall], holes: Sequence[Hole],
               radius: float, pitch: float, width: float, depth: float
               ) -> Tuple[int, int, float, float, List[bool]]:
    """Every grid point the marble's centre may legally occupy.

    "Legally" is the whole of the geometry: at least *radius* from every
    wall box, outside every pit by its own radius, and inside the tray.
    A point that fails is not merely bad, it is unreachable, so the
    sweep that follows can be a plain shortest path over what is left.
    """
    x0 = radius
    y0 = radius
    cols = max(2, int((width - 2 * radius) / pitch) + 1)
    rows = max(2, int((depth - 2 * radius) / pitch) + 1)
    free = [True] * (cols * rows)
    for wall in tray_walls:
        # Expand the box by the marble radius and strike out what it
        # covers: a centre inside the expanded box is a marble
        # overlapping the wall.
        lo_i = max(0, int(math.floor((wall.x0 - radius - x0) / pitch)))
        hi_i = min(cols - 1, int(math.ceil((wall.x1 + radius - x0) / pitch)))
        lo_j = max(0, int(math.floor((wall.y0 - radius - y0) / pitch)))
        hi_j = min(rows - 1, int(math.ceil((wall.y1 + radius - y0) / pitch)))
        for j in range(lo_j, hi_j + 1):
            y = y0 + j * pitch
            if not (wall.y0 - radius <= y <= wall.y1 + radius):
                continue
            base = j * cols
            for i in range(lo_i, hi_i + 1):
                x = x0 + i * pitch
                if wall.x0 - radius <= x <= wall.x1 + radius:
                    free[base + i] = False
    for hole in holes:
        if hole.home:
            continue
        reach = hole.radius
        lo_i = max(0, int(math.floor((hole.x - reach - x0) / pitch)))
        hi_i = min(cols - 1, int(math.ceil((hole.x + reach - x0) / pitch)))
        lo_j = max(0, int(math.floor((hole.y - reach - y0) / pitch)))
        hi_j = min(rows - 1, int(math.ceil((hole.y + reach - y0) / pitch)))
        for j in range(lo_j, hi_j + 1):
            y = y0 + j * pitch
            base = j * cols
            for i in range(lo_i, hi_i + 1):
                x = x0 + i * pitch
                if math.hypot(x - hole.x, y - hole.y) < reach:
                    free[base + i] = False
    return cols, rows, x0, y0, free


def _sweep(cols: int, rows: int, x0: float, y0: float, pitch: float,
           free: Sequence[bool], target: Tuple[float, float]
           ) -> Tuple[Optional[float], ...]:
    """Geodesic distance to *target* over the free grid, in metres.

    Eight-connected Dijkstra with true costs, so the field is a metric
    rather than a staircase — which matters, because the coach leans on
    it being 1-Lipschitz.
    """
    dist: List[Optional[float]] = [None] * (cols * rows)
    ti = int(round((target[0] - x0) / pitch))
    tj = int(round((target[1] - y0) / pitch))
    seeds: List[Tuple[float, int]] = []
    # The cup's own grid point is usually struck out — it is a hole, and
    # its rim is inside the marble's exclusion. Seed from the free ring
    # around it instead, at their true distance from the cup's centre.
    span = int(math.ceil(0.03 / pitch))
    for dj in range(-span, span + 1):
        for di in range(-span, span + 1):
            i, j = ti + di, tj + dj
            if not (0 <= i < cols and 0 <= j < rows):
                continue
            if not free[j * cols + i]:
                continue
            gap = math.hypot(di, dj) * pitch
            if gap <= span * pitch:
                at = j * cols + i
                if dist[at] is None or gap < dist[at]:
                    dist[at] = gap
                    seeds.append((gap, at))
    heap = sorted(seeds)
    heapq.heapify(heap)
    diag = math.sqrt(2.0) * pitch
    straight = pitch
    while heap:
        far, at = heapq.heappop(heap)
        if dist[at] is not None and far > dist[at]:
            continue
        i, j = at % cols, at // cols
        for di, dj, step in ((1, 0, straight), (-1, 0, straight),
                             (0, 1, straight), (0, -1, straight),
                             (1, 1, diag), (1, -1, diag),
                             (-1, 1, diag), (-1, -1, diag)):
            a, b = i + di, j + dj
            if not (0 <= a < cols and 0 <= b < rows):
                continue
            nxt = b * cols + a
            if not free[nxt]:
                continue
            through = far + step
            if dist[nxt] is None or through < dist[nxt] - 1e-12:
                dist[nxt] = through
                heapq.heappush(heap, (through, nxt))
    return tuple(dist)


# --- dealing ---------------------------------------------------------------


class Unbuildable(RuntimeError):
    """No tray of this shape could be certified. Raised only after trying."""


def _certify(walls: Sequence[Wall], holes: Sequence[Hole],
             home_x: float, home_y: float, width: float,
             depth: float) -> Field:
    """Sweep the tray and hand back the distance-to-cup field.

    The certificate and the coach's yardstick are the same computation
    on purpose. A separate "is it winnable" check maintained beside a
    separate "how far is it" field is two functions that must agree
    while being edited apart, and the workshop has already paid for
    that mistake once in its verifiers.
    """
    cols, rows, x0, y0, free = _free_grid(walls, holes, MARBLE_RADIUS,
                                          SWEEP_PITCH, width, depth)
    dist = _sweep(cols, rows, x0, y0, SWEEP_PITCH, free, (home_x, home_y))
    return Field(x0, y0, SWEEP_PITCH, cols, rows, dist)


def deal(rung: int, seed: Optional[int] = None, attempts: int = 24) -> Tray:
    """Build one certified tray for *rung*.

    Certified means a Dijkstra sweep found the cup from every marble's
    starting point over the free space, with the holes already bitten
    out. A tray that fails is discarded and another is rolled rather
    than repaired: repairing means removing the hole that sealed it,
    and the hole that sealed it is usually the interesting one.
    """
    rung = clamped_rung(rung)
    grade = GRADES[rung - 1]
    rng = random.Random(seed)
    for _try in range(attempts):
        try:
            return _build(grade, rung, rng)
        except Unbuildable:
            continue
    # Fall back down the ladder rather than fail the run. A rung that
    # cannot be built is a bug in the ladder, not in the player's
    # evening, and the message on screen still says which rung it is.
    if rung > 1:
        return deal(rung - 1, seed=None, attempts=attempts)
    raise Unbuildable('no tray could be certified at the bottom rung')


def _build(grade: Grade, rung: int, rng: random.Random) -> Tray:
    cols, rows = grade.cols, grade.rows
    # The tray is built outwards from the corridor the rung asked for,
    # rather than the corridor being whatever is left after dividing a
    # fixed tray. A denser maze is a bigger board, which is how one
    # would actually be made, and it keeps every physical constant up
    # top meaning what it says: they are all for a 15mm steel marble.
    corridor = 2.0 * MARBLE_RADIUS * grade.slack
    cell = corridor / (1.0 - WALL_SHARE)
    thickness = cell - corridor
    if corridor <= 2.0 * MARBLE_RADIUS:
        raise Unbuildable('corridor narrower than the marble')
    width = cols * cell + 2 * BOARD_MARGIN
    depth = rows * cell + 2 * BOARD_MARGIN
    ox = (width - cols * cell) / 2.0
    oy = (depth - rows * cell) / 2.0

    opened = _carve(cols, rows, rng)
    _braid(opened, cols, rows, grade.braid, rng)
    walls = _wall_strips(opened, cols, rows, cell, thickness, ox, oy)

    def centre(cell_index: int) -> Tuple[float, float]:
        col, row = cell_index % cols, cell_index // cols
        return (ox + (col + 0.5) * cell, oy + (row + 0.5) * cell)

    # Start in a corner-ish cell, cup as far from it as the doorways
    # allow. Furthest-by-doorways rather than furthest-by-ruler,
    # because the route is what the player walks.
    start_cell = rng.choice([0, cols - 1, (rows - 1) * cols,
                             rows * cols - 1])
    from_start = _cell_distances(opened, cols, rows, start_cell)
    reach = max(from_start)
    home_cell = rng.choice([c for c in range(cols * rows)
                            if from_start[c] >= reach - 1])
    home_x, home_y = centre(home_cell)
    home_r = max(MARBLE_RADIUS * 1.5, min(corridor * 0.42,
                                          MARBLE_RADIUS * 2.1))
    # Distance *from the cup*, which is the one every placement below
    # actually wants. Measuring from the start instead put the marbles
    # in the cells adjacent to the cup — the furthest cells from the
    # start are the cup's own neighbours, the cup having been chosen
    # for being furthest from the start. The trays certified, the
    # sweeps agreed, and rung twelve dealt a marble three centimetres
    # from home on a thirty-centimetre tray.
    from_home = _cell_distances(opened, cols, rows, home_cell)

    cup = Hole(home_x, home_y, home_r, True)
    pits = _place_holes(grade, opened, cols, rows, cell, corridor,
                        width, depth, ox, oy, start_cell, home_cell,
                        from_start, from_home, rng)

    # How long a route this tray owes the player. The maze's own
    # doorway count is the honest yardstick — it is what the walls
    # alone would give — and holes are allowed to shorten it by a bit
    # under half before the tray stops being the rung it claims to be.
    #
    # Without a bar here the upper rungs deal *easier* trays than the
    # lower ones, and do it silently. Thirty holes in a nine-by-eleven
    # tray sever it into pockets; the certificate still passes, because
    # the marble is placed in the pocket the cup is in, and "inhuman"
    # deals a marble twelve centimetres from home. The certificate
    # answers "can this be won", which is not the same question.
    owed = 0.45 * from_start[home_cell] * cell

    holes = pits + (cup,)
    field = _certify(walls, holes, home_x, home_y, width, depth)
    starts: Optional[Tuple[Tuple[float, float], ...]] = None
    route = 0.0
    for _relax in range(4):
        try:
            # Marbles are placed *out of the certified field*, not out
            # of the maze's cells: it already knows every legal place a
            # marble may stand and how far each is from home, so the
            # furthest is a lookup rather than a search.
            starts = _place_marbles(grade, field, cell, holes)
            route = max(field.strict(x, y) or 0.0 for (x, y) in starts)
        except Unbuildable:
            starts, route = None, 0.0
        if starts is not None and route >= owed:
            break
        if not pits:
            raise Unbuildable('no holes to give back and the route is short')
        # Give a quarter of the holes back and sweep again, rather than
        # rerolling the whole maze: the maze is rarely the problem and
        # rebuilding it throws away a good one to fix a bad scattering.
        keep = max(0, len(pits) - max(1, len(pits) // 4))
        pits = tuple(rng.sample(pits, keep))
        holes = pits + (cup,)
        field = _certify(walls, holes, home_x, home_y, width, depth)
    if starts is None or route < owed:
        raise Unbuildable('no scattering of holes left a route worth walking')

    return Tray(rung=rung, cols=cols, rows=rows, width=width,
                depth=depth, cell=cell,
                thickness=thickness, height=max(0.008, cell * 0.30),
                walls=walls, holes=holes, starts=starts,
                home=(home_x, home_y, home_r), seconds=grade.seconds,
                field=field, route=route)


def _place_holes(grade: Grade, opened, cols: int, rows: int, cell: float,
                 corridor: float, width: float, depth: float,
                 ox: float, oy: float, start_cell: int,
                 home_cell: int, from_start: Sequence[int],
                 from_home: Sequence[int], rng: random.Random
                 ) -> Tuple[Hole, ...]:
    """Bite holes out of the corridors, each one still passable.

    The test is analytic and local: a marble squeezing past on the far
    side of a corridor gets its centre no further from the hole than
    half the corridor plus the offset minus its own radius, and that
    has to clear the hole's radius by the rung's margin. Cheap enough
    to run on every candidate, which is what lets the placement be
    greedy rather than clever.

    Holes go in *cells*, offset across the corridor, and never in the
    cell a marble starts in or the one the cup is in. A hole in the
    start cell is a trial lost before the player has touched a knob.
    """
    radius = MARBLE_RADIUS * grade.hole_scale
    margin = MARBLE_RADIUS * grade.margin_scale
    half = corridor / 2.0
    # The offset that just satisfies the squeeze, plus whatever room is
    # left over. Solving `offset + half - r - radius >= margin` gives
    # the least offset that works; anything more only makes it easier,
    # so the placement takes the least and spends the slack on variety.
    least = radius + margin + MARBLE_RADIUS - half
    most = half + radius * 0.55
    if least > most:
        return ()

    banned = {start_cell, home_cell}
    candidates = [c for c in range(cols * rows) if c not in banned]
    rng.shuffle(candidates)
    # Prefer the route: a hole in a cul-de-sac nobody visits is not a
    # hazard, it is scenery. A cell lies on *some* shortest route
    # exactly when the two distances through it add up to the whole
    # journey, which is cheaper to test than enumerating the routes and
    # does not have to pick one of several ties.
    whole = from_start[home_cell]
    on_route = [c for c in candidates
                if from_start[c] + from_home[c] == whole]
    order = on_route + [c for c in candidates if c not in set(on_route)]

    placed: List[Hole] = []
    for cell_index in order:
        if len(placed) >= grade.holes:
            break
        col, row = cell_index % cols, cell_index // cols
        cx = ox + (col + 0.5) * cell
        cy = oy + (row + 0.5) * cell
        # Offset across whichever axis the cell's corridor runs.
        vertical = opened[cell_index][0] or opened[cell_index][1]
        offset = rng.uniform(least, most) * rng.choice((-1.0, 1.0))
        hx, hy = (cx + offset, cy) if vertical else (cx, cy + offset)
        if not (radius < hx < width - radius
                and radius < hy < depth - radius):
            continue
        if any(math.hypot(hx - other.x, hy - other.y)
               < radius + other.radius + MARBLE_RADIUS * 1.4
               for other in placed):
            continue
        placed.append(Hole(hx, hy, radius, False))
    return tuple(placed)


#: How far a marble must start from the nearest pit, over and above the
#: pit's own radius, in marble radii.
#:
#: Not nought, and the difference is a whole trial. The free grid rules
#: out points within a hole's radius, so a start taken straight off it
#: can sit *exactly on a rim* — legal, not over the hole, and a
#: millimetre from being over it. Measured before this existed: random
#: play at rung four resolved at a **median of 59 ticks**, because half
#: the trays dropped their marble down the hole it was standing on
#: inside the first second, whatever anyone did with the knobs. That is
#: not a hard trial, it is a trial nobody was given.
START_CLEARANCE = 2.0


def _clear_of_pits(holes: Sequence[Hole], x: float, y: float) -> bool:
    """Whether a marble may *start* here — a stricter test than legality."""
    for hole in holes:
        if hole.home:
            continue
        room = hole.radius + MARBLE_RADIUS * START_CLEARANCE
        if math.hypot(x - hole.x, y - hole.y) < room:
            return False
    return True


def _place_marbles(grade: Grade, field: Field, cell: float,
                   holes: Sequence[Hole]
                   ) -> Tuple[Tuple[float, float], ...]:
    """Line the marbles up along the route, furthest from the cup first.

    The first goes at the furthest legal point on the tray. The rest are
    found by *walking the route down* from it — stepping to whichever
    neighbouring point is nearer the cup, until enough distance has been
    covered — which is what puts them nose to tail in the same corridor
    rather than scattered over the tray.

    That matters because they share one pair of knobs. Marbles in
    corridors at right angles to each other make a tray where steering
    one shoves the others sideways, and while that is the difficulty
    rather than a flaw in it, it is only *fair* if the tilt that serves
    one at least points the rest the right way.
    """
    want = max(1, grade.marbles)

    def centre_of(at: int) -> Tuple[float, float]:
        return (field.x0 + (at % field.cols) * field.pitch,
                field.y0 + (at // field.cols) * field.pitch)

    best: Optional[Tuple[float, int]] = None
    for at, far in enumerate(field.dist):
        if far is None or (best is not None and far <= best[0]):
            continue
        if not _clear_of_pits(holes, *centre_of(at)):
            continue
        best = (far, at)
    if best is None:
        raise Unbuildable('nowhere on this tray is clear enough to start')

    picked = [centre_of(best[1])]
    at = best[1]
    # A marble and a half apart along the route, or a whole cell,
    # whichever is longer: close enough to be one queue, far enough
    # that they are not already touching when the tray is dealt.
    spacing = max(cell, MARBLE_RADIUS * 3.0)
    while len(picked) < want:
        walked = 0.0
        stuck = True
        while walked < spacing:
            here = field.dist[at]
            i, j = at % field.cols, at // field.cols
            step_to = None
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    a, b = i + di, j + dj
                    if di == dj == 0 or not (0 <= a < field.cols
                                             and 0 <= b < field.rows):
                        continue
                    near = field.dist[b * field.cols + a]
                    if near is not None and near < here:
                        if step_to is None or near < field.dist[step_to]:
                            step_to = b * field.cols + a
            if step_to is None:
                break
            walked += math.hypot(step_to % field.cols - i,
                                 step_to // field.cols - j) * field.pitch
            at = step_to
            stuck = False
        if stuck:
            # The route ran out before every marble had a place on it.
            # A shorter tray than the rung wanted is a worse tray than
            # the rung wanted, so it is rejected rather than dealt.
            raise Unbuildable('route too short for %d marbles' % want)
        spot = centre_of(at)
        if not _clear_of_pits(holes, *spot):
            # Walk on rather than park a marble on a rim. The spacing is
            # a preference and the clearance is not, so the spacing is
            # what gives: shorten it and take the next clear place.
            spacing = max(MARBLE_RADIUS * 2.5, spacing * 0.6)
            continue
        picked.append(spot)
    return tuple(picked)


# --- the marble ------------------------------------------------------------


class Marble:
    """One ball: where it is, how fast, how high, and how it is spinning.

    *z* is the height of the centre above the tray's surface, which is
    :data:`MARBLE_RADIUS` for as long as the tray is holding it up. It
    is a real degree of freedom rather than bookkeeping: it is what
    makes a hole something a fast marble can clear.

    Spin is a degree of freedom too, and not bookkeeping either.
    ``wx``/``wy``/``wz`` are the angular velocity in the tray's frame,
    radians a second, and the same contact solve that moves the centre
    integrates them — they are not slaved to the velocity. That is what
    a bounce needs: a marble coming off a wall is still spinning the
    way it *was* going, and the tray has to drag it round before it
    rolls again. A slaved spin cannot say that, and the difference is
    most of what a wall feels like.

    ``qw``/``qx``/``qy``/``qz`` are the orientation those rates
    integrate to, as a unit quaternion, which the renderer turns into a
    matrix. An orientation has to be integrated rather than accumulated
    one angle per axis, because rotations about different axes do not
    commute — and a marble with a photograph of steel wrapped round it
    shows the difference the moment it spins about more than one.
    """

    __slots__ = ('x', 'y', 'vx', 'vy', 'z', 'vz', 'wx', 'wy', 'wz',
                 'qw', 'qx', 'qy', 'qz', 'state', 'over')

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.z = MARBLE_RADIUS
        self.vz = 0.0
        #: Angular velocity in the tray's frame, radians a second.
        self.wx = 0.0
        self.wy = 0.0
        self.wz = 0.0
        #: Orientation, a unit quaternion (w, x, y, z).
        self.qw = 1.0
        self.qx = 0.0
        self.qy = 0.0
        self.qz = 0.0
        #: 'rolling', 'falling' (in a pit, past saving), 'home', 'lost'.
        self.state = 'rolling'
        #: The hole it is currently unsupported over, if any.
        self.over: Optional[Hole] = None

    @property
    def live(self) -> bool:
        return self.state in ('rolling', 'falling')

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    @property
    def slipping(self) -> float:
        """How fast the contact patch is sliding, m/s. Nought is a roll.

        The velocity of the point of the marble that is touching the
        tray: ``v + ω × (-R·n̂)``, which for a tray normal of ``+z``
        comes out as the two terms below. Everything the sphere does
        is this number being driven away from nought and dragged back.
        """
        return math.hypot(self.vx - MARBLE_RADIUS * self.wy,
                          self.vy + MARBLE_RADIUS * self.wx)

    def roll_with_travel(self) -> None:
        """Set the spin that matches the velocity: a clean roll, no skid."""
        self.wy = self.vx / MARBLE_RADIUS
        self.wx = -self.vy / MARBLE_RADIUS


# --- the engine ------------------------------------------------------------


def _quat_rotate(q: Tuple[float, float, float, float],
                 v: Tuple[float, float, float]
                 ) -> Tuple[float, float, float]:
    """Rotate vector *v* by unit quaternion *q*: body frame to tray frame."""
    w, x, y, z = q
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (vx + w * tx + y * tz - z * ty,
            vy + w * ty + z * tx - x * tz,
            vz + w * tz + x * ty - y * tx)


def _quat_unrotate(q: Tuple[float, float, float, float],
                   v: Tuple[float, float, float]
                   ) -> Tuple[float, float, float]:
    """The inverse rotation: tray frame into the body's own."""
    w, x, y, z = q
    return _quat_rotate((w, -x, -y, -z), v)


def _mjcf(tray: Tray, count: int) -> str:
    """The tray, as the engine's model description.

    Three classes of contact, each on its own terms:

    * **floor-ball** is an implicit contact — the only one — with
      ``condim="6"``: sliding, torsional *and* rolling friction, which
      is the whole of how a tray talks to a marble. Implicit, because
      it is the one contact the game switches off: a hole is a place
      where the floor stops existing for one marble, done by clearing
      that ball's contact bits.
    * **wall-ball** is an explicit ``<pair>``, which the engine keeps
      active regardless of contact bits — a falling marble still clips
      rims — with the low friction of :data:`WALL_FRICTION`, so a
      marble's roll survives the blow and a square hit settles at the
      wall instead of drifting back across the corridor.
    * **ball-ball** is a ``<pair>`` with an underdamped contact, which
      is what restitution is in this engine: the damping ratio is set
      for steel on steel.

    The timestep and gravity written here are placeholders; every
    substep overwrites both.
    """
    crr = ROLLING_RESISTANCE * MARBLE_RADIUS
    parts = [
        '<mujoco>',
        # noslip: two post-solver passes that enforce the friction
        # cone exactly instead of by regularisation. Without them the
        # engine's rolling friction fades below a couple of
        # centimetres a second and a levelled marble crawls its last
        # stretch forever; with them the deceleration matches the dry
        # figure to one percent and a levelled tray stops. Two is
        # where the behaviour lands; more iterations change nothing
        # but the bill.
        '<option integrator="implicitfast" cone="elliptic" '
        'noslip_iterations="2" '
        'timestep="0.004" gravity="0 0 -%.5f"/>' % GRAVITY,
        '<worldbody>',
        '<geom name="floor" type="plane" size="%.4f %.4f 0.1" '
        'friction="%.3f %.4f %.6f" condim="6" contype="1" conaffinity="1"/>'
        % (max(tray.width, 1.0) * 2, max(tray.depth, 1.0) * 2,
           FRICTION_STATIC, SPIN_GRIP, crr),
    ]
    for index, wall in enumerate(tray.walls):
        parts.append(
            '<geom name="wall%d" type="box" pos="%.6f %.6f %.6f" '
            'size="%.6f %.6f %.6f" contype="0" conaffinity="0"/>'
            % (index, (wall.x0 + wall.x1) / 2.0, (wall.y0 + wall.y1) / 2.0,
               tray.height / 2.0,
               max(1e-4, (wall.x1 - wall.x0) / 2.0),
               max(1e-4, (wall.y1 - wall.y0) / 2.0),
               tray.height / 2.0))
    for i in range(count):
        x, y = tray.starts[i] if i < len(tray.starts) else (10.0 + i, 10.0)
        parts.append(
            '<body name="ball%d" pos="%.6f %.6f %.6f"><freejoint/>'
            '<geom name="ball%d" type="sphere" size="%.4f" density="7800" '
            'friction="%.3f %.4f %.6f" condim="3" contype="1" '
            'conaffinity="1"/></body>'
            % (i, x, y, MARBLE_RADIUS, i, MARBLE_RADIUS,
               FRICTION_STATIC, SPIN_GRIP, crr))
    parts.append('</worldbody>')
    parts.append('<contact>')
    for i in range(count):
        for index in range(len(tray.walls)):
            # Stiff and critically damped, and the stiffness is the
            # point: at the default softness a wall hit is a squeeze
            # spread over three frames, and during a squeeze the floor
            # re-rolls the marble to its shrinking speed — the spin
            # that should carry it back to the wall dies in transit,
            # and the marble drifts eight centimetres back across the
            # corridor. Stiff, the blow is over in a substep, the spin
            # survives it, and the tray drags the marble back to the
            # wall, where it settles. Measured, not reasoned: the
            # sweep lives in the port notes, and the hug is asserted
            # by the tests.
            parts.append(
                '<pair geom1="ball%d" geom2="wall%d" condim="3" '
                'solref="0.009 1.0" '
                'friction="%.3f %.3f 0.0001 0.0001 0.0001"/>'
                % (i, index, WALL_FRICTION, WALL_FRICTION))
        for j in range(i + 1, count):
            # Underdamped: dampratio 0.03 rings back as a restitution
            # of about BALL_RESTITUTION for a steel pair. The time
            # constant stays above twice the substep, as the solver
            # requires of a stable contact.
            parts.append(
                '<pair geom1="ball%d" geom2="ball%d" condim="3" '
                'solref="0.009 0.03" '
                'friction="0.05 0.05 0.0001 0.0001 0.0001"/>' % (i, j))
    parts.append('</contact>')
    parts.append('</mujoco>')
    return ''.join(parts)


class Simulation:
    """The tray, the marbles on it, and the engine that moves them.

    The dynamics are MuJoCo's. The tray's geometry — floor, wall
    strips, one body per marble — is compiled into an engine model when
    the first step needs it, and every substep syncs the plain
    :class:`Marble` objects into the engine, steps it once, and syncs
    them back out. The marbles stay plain Python data on purpose: the
    renderer, the boundary and the tests all read and write them
    directly, and none of them should know an engine exists.

    What the engine owns: rolling and its five sevenths, sliding
    friction, rolling and torsional resistance, wall impacts, and
    marble-on-marble impacts. What this wrapper still owns, because
    the game's guarantees live there rather than in mechanics:

    * **Tilt** enters as a rotated gravity vector, exactly as before —
      the tray never moves, the world leans.
    * **Holes.** The floor is a plane; a hole is a place where that
      plane stops existing for one marble. Wall and marble contacts
      are explicit ``<pair>`` entries, which the engine keeps active
      regardless of the mask, so a falling marble still clips rims and
      rails. Capture, and the energy toll for climbing the far lip,
      are the same code they always were.
    * **The rest clamp.** The engine's rolling friction is a smooth
      regularised torque, not a dry threshold: left alone, a marble
      creeps on a tray tilted below the stall angle instead of
      refusing to start. The clamp restores ``atan(Crr)`` as a real
      threshold, which is what makes levelling the tray a move.
    * **The speed cap**, because the coach's one-step-per-tick
      guarantee is an inequality about travel per tick, and it has to
      hold whatever the contact solver does.

    Stepped at a fixed rate by whoever owns the clock — a real one for
    a player, a virtual one for the agent boundary — so a run is the
    same run either way. Nothing in here reads the wall clock, and the
    engine is deterministic: the same actions replay the same run.
    """

    def __init__(self, tray: Tray) -> None:
        self.tray = tray
        self.marbles = [Marble(x, y) for (x, y) in tray.starts]
        self.pitch = 0.0
        self.roll = 0.0
        self.elapsed = 0.0
        #: Set when something happened this step worth a noise or a label.
        self.cupped_this_step = 0
        self.lost_this_step = 0
        self.struck_this_step = 0.0
        self._model = None
        self._data = None
        self._ball_geoms: Tuple[int, ...] = ()
        self._built_for = -1

    # --- the knobs -------------------------------------------------------

    def tilt(self, which: str) -> None:
        """One nudge of one knob, named for the way the marble then goes.

        The pitch signs are the ones to look at. Gravity in the tray's
        frame is ``gy = -g·cos(roll)·sin(pitch)``, so a marble goes
        *north* — towards larger y — on a *negative* pitch, and the
        knob called north has to subtract. Roll needs no such care:
        ``gx = g·sin(roll)`` already sends the marble east on a
        positive one.
        """
        if which == TILT_NORTH:
            self.pitch = max(-MAX_TILT, self.pitch - TILT_STEP)
        elif which == TILT_SOUTH:
            self.pitch = min(MAX_TILT, self.pitch + TILT_STEP)
        elif which == TILT_EAST:
            self.roll = min(MAX_TILT, self.roll + TILT_STEP)
        elif which == TILT_WEST:
            self.roll = max(-MAX_TILT, self.roll - TILT_STEP)

    def level(self) -> None:
        self.pitch = self.roll = 0.0

    # --- the engine ------------------------------------------------------

    def _ensure_engine(self) -> None:
        """Compile the tray for the number of marbles it currently has.

        Rebuilt when the marble count changes, which in play is never
        and in tests is whenever one replaces ``sim.marbles`` to stage
        a scene. The count is baked into the model because bodies are.
        """
        count = len(self.marbles)
        if self._model is not None and count == self._built_for:
            return
        model = mujoco.MjModel.from_xml_string(_mjcf(self.tray, count))
        self._model = model
        self._data = mujoco.MjData(model)
        self._ball_geoms = tuple(
            mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, 'ball%d' % i)
            for i in range(count))
        self._built_for = count

    # --- one step --------------------------------------------------------

    def step(self, dt: float) -> None:
        """Advance by *dt*, in :data:`SUBSTEPS` equal pieces."""
        self.cupped_this_step = 0
        self.lost_this_step = 0
        self.struck_this_step = 0.0
        self.elapsed += dt
        piece = dt / SUBSTEPS
        for _ in range(SUBSTEPS):
            self._substep(piece)

    def _substep(self, dt: float) -> None:
        self._ensure_engine()
        model, data = self._model, self._data
        # Gravity resolved into the tray's own frame. The tray is
        # R_y(roll)·R_x(pitch) from the world, so world (0,0,-g) becomes
        # (g·sin roll, -g·cos roll·sin pitch, -g·cos roll·cos pitch).
        sin_r, cos_r = math.sin(self.roll), math.cos(self.roll)
        sin_p, cos_p = math.sin(self.pitch), math.cos(self.pitch)
        gx = GRAVITY * sin_r
        gy = -GRAVITY * cos_r * sin_p
        gn = GRAVITY * cos_r * cos_p          # into the tray, holds it up
        model.opt.gravity[:] = (gx, gy, -gn)
        model.opt.timestep = dt

        # In: decide support, set each ball's floor mask, write state.
        for i, marble in enumerate(self.marbles):
            geom = self._ball_geoms[i]
            if marble.state == 'rolling':
                hole = self._hole_under(marble)
                if hole is not None:
                    # Unsupported: the floor stops existing for this
                    # marble until it is swallowed or over the far lip.
                    marble.state = 'falling'
                    marble.over = hole
            if marble.live:
                grounded = 1 if marble.state == 'rolling' else 0
                model.geom_contype[geom] = grounded
                model.geom_conaffinity[geom] = grounded
                base, vbase = i * 7, i * 6
                data.qpos[base:base + 3] = (marble.x, marble.y, marble.z)
                data.qpos[base + 3:base + 7] = (marble.qw, marble.qx,
                                                marble.qy, marble.qz)
                data.qvel[vbase:vbase + 3] = (marble.vx, marble.vy,
                                              marble.vz)
                data.qvel[vbase + 3:vbase + 6] = _quat_unrotate(
                    (marble.qw, marble.qx, marble.qy, marble.qz),
                    (marble.wx, marble.wy, marble.wz))
            else:
                # Done marbles are parked out of everyone's way. The
                # park is rewritten every substep, so nothing drifts.
                model.geom_contype[geom] = 0
                model.geom_conaffinity[geom] = 0
                data.qpos[i * 7:i * 7 + 7] = (10.0 + i, 10.0, 1.0,
                                              1.0, 0.0, 0.0, 0.0)
                data.qvel[i * 6:i * 6 + 6] = 0.0

        before = [(m.vx, m.vy) if m.live else None for m in self.marbles]
        mujoco.mj_step(model, data)

        # Out: read the engine back into the plain marbles.
        for i, marble in enumerate(self.marbles):
            if not marble.live:
                continue
            base, vbase = i * 7, i * 6
            marble.x = float(data.qpos[base])
            marble.y = float(data.qpos[base + 1])
            marble.z = float(data.qpos[base + 2])
            marble.qw = float(data.qpos[base + 3])
            marble.qx = float(data.qpos[base + 4])
            marble.qy = float(data.qpos[base + 5])
            marble.qz = float(data.qpos[base + 6])
            marble.vx = float(data.qvel[vbase])
            marble.vy = float(data.qvel[vbase + 1])
            marble.vz = float(data.qvel[vbase + 2])
            # The engine keeps a free joint's spin in the body's own
            # frame; everything here speaks the tray's.
            marble.wx, marble.wy, marble.wz = _quat_rotate(
                (marble.qw, marble.qx, marble.qy, marble.qz),
                (float(data.qvel[vbase + 3]),
                 float(data.qvel[vbase + 4]),
                 float(data.qvel[vbase + 5])))

        # A falling marble ends its fall here, one way or the other.
        for marble in self.marbles:
            if marble.state != 'falling':
                continue
            over = self._hole_under(marble)
            if over is None:
                self._over_the_lip(marble, gn)
            else:
                marble.over = over
                if marble.z <= 0.0:
                    self._swallow(marble, over)

        # The wrapper's own guarantees: drag, the cap, the rest clamp.
        resting_tilt = math.hypot(gx, gy) <= ROLLING_RESISTANCE * gn
        for i, marble in enumerate(self.marbles):
            if not marble.live:
                continue
            # The thin drag the engine does not model: air, varnish.
            keep = 1.0 - VISCOUS_DRAG * dt
            marble.vx *= keep
            marble.vy *= keep
            speed = marble.speed
            if speed > SPEED_CAP:
                # Load-bearing for the coach: see POTENTIAL_QUANTUM.
                # The spin comes down with the travel, so a capped
                # marble is still rolling rather than skating.
                scale = SPEED_CAP / speed
                marble.vx *= scale
                marble.vy *= scale
                marble.wx *= scale
                marble.wy *= scale
            if marble.state == 'rolling':
                if abs(marble.wz) < REST_SPEED / MARBLE_RADIUS:
                    marble.wz = 0.0
                if (resting_tilt and marble.speed < REST_SPEED
                        and math.hypot(marble.wx, marble.wy)
                        < REST_SPEED / MARBLE_RADIUS):
                    # Below the stall angle nothing can start it, and
                    # the engine's regularised rolling friction cannot
                    # say so — it would creep across a levelled tray.
                    marble.vx = marble.vy = 0.0
                    marble.wx = marble.wy = 0.0
            was = before[i]
            if was is not None and marble.live:
                # A jolt is a change of velocity gravity cannot explain.
                jolt = math.hypot(marble.vx - was[0] - gx * dt,
                                  marble.vy - was[1] - gy * dt)
                if jolt > 0.02:
                    self.struck_this_step = max(self.struck_this_step,
                                                min(1.0, jolt * 1.6))

    # --- holes -----------------------------------------------------------

    def _hole_under(self, marble: Marble) -> Optional[Hole]:
        """The hole whose rim the marble's contact patch is inside, if any."""
        for hole in self.tray.holes:
            if math.hypot(marble.x - hole.x, marble.y - hole.y) < hole.radius:
                return hole
        return None

    def _over_the_lip(self, marble: Marble, gn: float) -> None:
        """Past the rim of the pit it was falling into: out, or in.

        Reached the moment the contact point is over solid tray again,
        whatever height the marble is at, which is what makes the fall
        terminate. There is no state in which a marble is neither
        supported nor over a hole: an earlier design could leave one
        skating about at nought height for the rest of the trial,
        never settling and never letting the coach read a potential
        again.

        The toll is energy: the centre dropped, and ``2·g·drop`` comes
        out of the speed squared to put it back on the tray. Graded by
        the drop, so a marble that barely dipped pays almost nothing
        and one that nearly went in pays nearly all of it.
        """
        hole = marble.over
        drop = MARBLE_RADIUS - marble.z
        if hole is not None and drop > 0.0:
            have = marble.vx * marble.vx + marble.vy * marble.vy
            need = 2.0 * gn * drop
            if have <= need:
                # It reached the far side without the speed to climb
                # back out of the throat. It is in the hole.
                self._swallow(marble, hole)
                return
            keep = math.sqrt((have - need) / have)
            marble.vx *= keep
            marble.vy *= keep
            self.struck_this_step = max(self.struck_this_step,
                                        min(1.0, drop / MARBLE_RADIUS))
        marble.z = MARBLE_RADIUS
        marble.vz = 0.0
        marble.over = None
        marble.state = 'rolling'
        # Coming over the lip is a contact, and it leaves the marble
        # rolling on whatever speed it has left.
        marble.roll_with_travel()

    def _swallow(self, marble: Marble, hole: Hole) -> None:
        if hole.home:
            marble.state = 'home'
            self.cupped_this_step += 1
        else:
            marble.state = 'lost'
            self.lost_this_step += 1

    # --- reading the run -------------------------------------------------

    @property
    def home(self) -> int:
        return sum(1 for m in self.marbles if m.state == 'home')

    @property
    def lost(self) -> int:
        return sum(1 for m in self.marbles if m.state == 'lost')

    @property
    def settled(self) -> bool:
        return not any(m.live for m in self.marbles)

    @property
    def won(self) -> bool:
        return all(m.state == 'home' for m in self.marbles)

    def potential(self) -> Optional[int]:
        """The coach's potential: quantised distance summed over live marbles.

        None as soon as any live marble is somewhere the field cannot
        read, which is the honest answer rather than a number that
        happens to be available. A marble in mid-fall is one such
        place.
        """
        total = 0
        for marble in self.marbles:
            if marble.state == 'home':
                continue
            if marble.state == 'lost' or marble.state == 'falling':
                return None
            got = potential_at(self.tray, marble.x, marble.y)
            if got is None:
                return None
            total += got
        return total


def par_seconds(tray: Tray) -> float:
    """A generous estimate of how long a good line takes.

    The route at a speed a player can actually hold through corners —
    a quarter of the speed cap — plus a fixed cost per marble for
    getting it into the cup. Used for the "well done" threshold rather
    than for anything that ends a trial, so erring long is cheap and
    erring short would make every green a lie.
    """
    pace = SPEED_CAP * 0.25
    return tray.route / pace + 2.5 * len(tray.starts)


__all__ = [
    'BALL_RESTITUTION', 'BOARD_DEPTH', 'BOARD_WIDTH',
    'FRICTION_STATIC', 'GRADES', 'GRAVITY', 'Grade', 'Hole',
    'MARBLE_RADIUS', 'MAX_TILT', 'Marble', 'POTENTIAL_QUANTUM',
    'REST_SPEED', 'ROLLING_RESISTANCE', 'ROLL_FACTOR', 'SLIP_SHARE',
    'SPEED_CAP', 'SPHERE_INERTIA', 'SPIN_GRIP', 'SUBSTEPS', 'Simulation',
    'TILT_EAST', 'TILT_NORTH', 'TILT_SOUTH', 'TILT_STEP', 'TILT_WEST',
    'Tray', 'Unbuildable', 'VISCOUS_DRAG', 'WALL_FRICTION',
    'WALL_RESTITUTION', 'Wall', 'clamped_rung', 'deal', 'par_seconds',
    'potential_at',
]
