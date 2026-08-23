# -*- coding: utf-8 -*-
"""Two Hands: Donkey's road stood up into three dimensions, and a sky
over it that wants the other hand.

:mod:`neural_workshop.donkey` is two lanes, one key and a swerve you
cannot take back. This is the same road seen from behind the car
instead of above it, and everything the flat game left out is in it:
three lanes rather than two, nine kinds of thing standing in them, a
jump, a throttle, a deadline that makes the throttle matter, and
targets drifting over the horizon that are shot with the mouse.

The name is the task rather than the fiction. One tick takes **one**
action. The wheel and the sights are the same budget, so a tick spent
nudging the crosshair is a tick not spent steering, and what is being
measured is how a player splits an indivisible attention between two
channels that do not wait for each other.

What the road asks
------------------

Every rule here is a rule about *committing early*, which is what
Donkey was about, and each one commits over a distance the player
chooses rather than a fixed one:

* **The swerve** takes :attr:`Grade.swerve` ticks, cannot be called
  off, and covers both lanes for the whole of it — Donkey's one rule,
  unchanged. What is new is that a tick is worth ``speed`` sub-rows of
  road, so the faster you are going the more road you are exposed over.
* **The jump** takes :attr:`Grade.hang` ticks and clears anything low.
  It clears it only if the car is *off the ground for the whole
  overlap*, which is ``speed * hang`` sub-rows against a hazard's
  :data:`SPAN`. So one jump at a crawl does not clear a log: it takes
  as many hops as the log is long, and every one of them is a tick
  spent on nothing else. Speed is what buys the jump in ticks, which
  is the currency the clock and the sky are both denominated in.
* **The throttle** moves one step a tick and only while the car is
  settled. Faster is worse for the swerve and better for the jump, and
  those two pull opposite ways: this is the whole of what makes the
  speed a decision rather than a slider you push to one end.
* **The deadline** is :attr:`Grade.clock` ticks for the road. Without
  it the safe policy is to crawl at one sub-row a tick and the throttle
  is dead weight; with it a road has to be *driven*.

While the car is crossing or in the air the wheel is deaf — every
driving port is swallowed, exactly as Donkey swallows a second press.
That is what makes the sky nearly free at the right moments and
expensive at the wrong ones, and it is the strategy the task is really
teaching. It is measured in :func:`rehearse` rather than asserted.

What the sky asks
-----------------

Targets drift over the horizon at fixed places on the *road*, so which
ones a run is offered is a property of the deal and not of the driving
— but how many ticks each is aloft for is not, because a fast car
passes the stretch it flies over sooner. Hitting one takes the
crosshair onto it and a press, which is two or more ticks. Nothing in
the sky can touch the car, and that is deliberate: the sky is a
*second* task rather than a second hazard, so what it costs the road is
attention and nothing else, and the cost can be read off one number.

One rule decides every meeting
------------------------------

A hazard blocks :data:`SPAN` sub-rows — the two bodies added together
less the one they share, the same arithmetic Donkey uses — and the car
sweeps every sub-row it passes over, so nothing is ever tunnelled
through. Within that:

* **A crash is any moment of overlap.** Every swept sub-row is checked
  against the lanes the car covers at that tick, so a jump that lands
  half way over a log is a crash, and a swerve that finishes half way
  past a truck is a crash.
* **A clip and a prize are the moment of meeting**, resolved once, at
  the sub-row where the two bodies would first touch. A cone glances
  off; a coin is picked up; there is no second helping of either.

Every road has a clean line through it
--------------------------------------

A road that cannot be driven scores as a failure the player could not
have avoided, so :func:`generate` does not hand one out. Donkey could
maintain that as it laid the road, because its car moved one sub-row a
tick and the surviving set was a function of the sub-row alone. Neither
holds here: the step is the car's own speed and the verdict has a
clock on it, so what survives is a property of the whole road rather
than of a prefix of it.

So this one lays the road and then *solves* it. :func:`line` is a
forward dynamic program over ``(sub-row, lane, commitment, speed)`` —
a DAG, because every tick advances the car — and it returns the fewest
ticks to the far end with no crash and no clip. A road the program
cannot finish inside :attr:`Grade.clock` has a hazard taken out of it
and is solved again. What is dealt is therefore a road with a clean
line through it and a proof of the line, and :func:`line` will hand
you the proof.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import (Dict, List, NamedTuple, Optional, Sequence, Set, Tuple)

# --- the ports -----------------------------------------------------------

#: The wheel. Six, and the first of them is not padding: a tick spent
#: holding the wheel straight is the tick that keeps the car in a lane
#: it is already safe in, and it is also the tick that is *free* for
#: the sights.
HOLD, LEFT, RIGHT, JUMP, FASTER, SLOWER = range(6)

#: The sights. Four nudges and a trigger, which is what a mouse is once
#: it has been made steppable. A person moves the crosshair with the
#: mouse and presses a button; the ports are the same instrument taken
#: a notch at a time, and the crosshair is drawn either way.
AIM_LEFT, AIM_RIGHT, AIM_UP, AIM_DOWN, FIRE = range(6, 11)

#: Ports the ride understands. The rest never touch the car.
WHEEL: Tuple[int, ...] = (HOLD, LEFT, RIGHT, JUMP, FASTER, SLOWER)

#: Ports the sights understand. They cost a tick and nothing else.
SIGHTS: Tuple[int, ...] = (AIM_LEFT, AIM_RIGHT, AIM_UP, AIM_DOWN, FIRE)

PORTS = len(WHEEL) + len(SIGHTS)

#: Lanes. Three, which is the fewest that makes *which* way to go a
#: question — with two, "not here" names the answer.
LANES = 3

#: Sub-rows a drawn row is cut into: the rules' unit, not the screen's.
#: Donkey's four, for Donkey's reason — the car and the hazard each
#: have a length, and a hit should be the two of them overlapping
#: rather than the row the car drove into.
SUB = 4

#: How long the car and a hazard are, in sub-rows.
CAR, BODY = 3, 3

#: Sub-rows a hazard blocks: the two bodies added together, less the
#: one they share. A car whose tail is at ``a`` overlaps a hazard whose
#: run starts at ``b`` exactly when ``b - CAR < a < b + BODY``.
SPAN = CAR + BODY - 1

#: The fastest any rung goes, in sub-rows a tick.
TOP = 4

#: Rows of clear road before the first hazard may stand. The first
#: thing a road asks is whether you were looking.
RUN_IN = 4

#: Clear sub-rows kept after a hazard before the next one may start.
GAP = SUB

#: How far a target drifts across the sky is measured in sub-rows of
#: road gone by, so the sky moves with the road rather than with the
#: wall clock. This is how long one is up for.
ALOFT = 10 * SUB


# --- what can be standing in it ------------------------------------------

class Kind(NamedTuple):
    """One sort of thing on the road, in the two bits that matter.

    *tall* is whether a jump goes over it. *toll* is what meeting it
    costs, and there are five:

    ``fatal``
        the road ends there.
    ``clip``
        a glancing blow: the speed goes back to one and a point is
        lost. Survivable, always avoidable, and the reason a road can
        be *badly* driven as well as crashed.
    ``ramp``
        a gift. Driving over it settled puts the car in the air for
        nothing, which is a jump you did not have to spend a tick on
        — and a jump you may not have wanted.
    ``boost``
        the speed bonus, and it is not free either: it puts the car one
        step faster whether or not the next swerve wanted to be.
    ``coin``
        points, worth the speed they were taken at. The only thing here
        that rewards going fast directly.
    """

    name: str
    tall: bool
    toll: str


#: Nine kinds. Four of them end the road, two cost you, three are for
#: taking — and the two bits above are the whole of what the rules read,
#: so the screen is free to draw nine different things and the rules
#: only ever ask two questions about any of them.
KINDS: Tuple[Kind, ...] = (
    Kind('donkey', True, 'fatal'),
    Kind('truck', True, 'fatal'),
    Kind('barrier', True, 'fatal'),
    Kind('log', False, 'fatal'),
    Kind('rubble', True, 'clip'),
    Kind('cone', False, 'clip'),
    Kind('ramp', False, 'ramp'),
    Kind('pad', False, 'boost'),
    Kind('coin', False, 'coin'),
)

DONKEY, TRUCK, BARRIER, LOG, RUBBLE, CONE, RAMP, PAD, COIN = range(len(KINDS))

#: The ones a line has to get past rather than through.
BLOCKING = frozenset(index for index, kind in enumerate(KINDS)
                     if kind.toll in ('fatal', 'clip'))

#: The ones that end a road. Counted as they go by, which is what the
#: coach pays and what the screen says out loud.
FATAL = frozenset(index for index, kind in enumerate(KINDS)
                  if kind.toll == 'fatal')


class Grade(NamedTuple):
    """One rung: how long the road is, what stands in it, and what a
    commitment costs."""

    name: str
    rows: int                   #: rows of road in one trial
    density: float              #: hazards a row the dice are asked for
    pairs: float                #: chance a hazard comes with a neighbour
    swerve: int                 #: ticks a lane change takes, committed
    hang: int                   #: ticks a jump lasts, committed
    top: int                    #: the fastest this rung will go
    slack: float                #: the clock, as a multiple of the par
    kinds: Tuple[int, ...]      #: what may be dealt onto it
    sky: float                  #: targets a row

    @property
    def length(self) -> int:
        """The road in sub-rows, which is what the car moves through."""
        return self.rows * SUB


#: The road kinds, in the order the ladder lets them out.
_TALL = (DONKEY, TRUCK, BARRIER)
_FLAT = _TALL + (LOG,)
_COST = _FLAT + (RUBBLE, CONE)
_ALL = _COST + (RAMP, PAD, COIN)

#: Ten rungs, and each one adds a single thing so that a run that
#: stalls says which thing it stalled on.
#:
#: One and two are Donkey in three dimensions: tall hazards only, a
#: clock loose enough that the throttle is optional, and a nearly empty
#: sky. Three deals them two abreast, which is where *which* lane
#: starts to matter. Four brings the log, the first thing a swerve
#: cannot answer. Six brings the two that cost without killing. Seven
#: brings the ramp, the pad and the coin, which is where the throttle
#: stops being something you set once. From eight the swerve widens,
#: the clock tightens and the sky fills, and by ten the road and the
#: sky are both asking for more ticks than there are.
#:
#: The clock is written as a multiple of the road's *own* par rather
#: than as a pace, and that is not a convenience. A pace has to be set
#: against the hardest road a rung can deal or it makes some of them
#: impossible, which means it is slack on all the others; a multiple of
#: par asks the same thing of every deal. What :attr:`Grade.slack`
#: says is exactly "how much worse than the best line will do", and
#: 1.70 down to 1.25 is the ladder's second dimension after the
#: hazards.
GRADES: Tuple[Grade, ...] = (
    #     name                 rows dens pair sw hg tp slack kinds  sky
    Grade('a clear road',       28, 0.16, 0.00, 2, 3, 2, 1.70, _TALL, 0.04),
    Grade('one at a time',      32, 0.26, 0.00, 2, 3, 2, 1.62, _TALL, 0.07),
    Grade('and one beside it',  34, 0.30, 0.25, 2, 3, 3, 1.55, _TALL, 0.10),
    Grade('something to jump',  36, 0.34, 0.25, 2, 3, 3, 1.50, _FLAT, 0.12),
    Grade('the long haul',      48, 0.34, 0.30, 2, 3, 3, 1.45, _FLAT, 0.14),
    Grade('cones and rubble',   40, 0.40, 0.30, 2, 3, 3, 1.40, _COST, 0.16),
    Grade('a road that pays',   42, 0.44, 0.35, 2, 3, 4, 1.36, _ALL,  0.18),
    Grade('the wide swerve',    44, 0.44, 0.35, 3, 3, 4, 1.32, _ALL,  0.20),
    Grade('the long night',     56, 0.50, 0.40, 3, 3, 4, 1.28, _ALL,  0.24),
    Grade('both hands',         56, 0.56, 0.45, 3, 4, 4, 1.25, _ALL,  0.28),
)


# --- the road ------------------------------------------------------------

class Hazard(NamedTuple):
    """One thing standing in one lane, at one place on the road."""

    at: int         #: the first sub-row it blocks
    lane: int
    kind: int

    @property
    def end(self) -> int:
        """The last sub-row it blocks: where it is *past*."""
        return self.at + SPAN - 1

    @property
    def body(self) -> int:
        """Where its drawn body begins.

        The blocked run starts a car's length earlier, because that is
        where the two would first overlap. The screen wants the animal.
        """
        return self.at + CAR - 1


class Target(NamedTuple):
    """One thing in the sky, and where it is while the road goes by.

    Pinned to a place on the *road* rather than to the clock, so which
    targets a run is offered is a property of the deal. How many ticks
    each is aloft for is not: a fast car is past the stretch it flies
    over sooner, and that is the second bill the throttle runs up.
    """

    at: int         #: the sub-row the car is at when it appears
    across: float   #: where it starts, as a fraction of the sky's width
    up: float       #: how high, as a fraction of the sky's height
    drift: float    #: how far across it slides before it is gone

    def aloft(self, at: int) -> bool:
        return self.at <= at < self.at + ALOFT

    def where(self, at: int) -> Tuple[float, float]:
        """``(across, up)`` at car position *at*, both in ``0..1``.

        Clamped rather than wrapped: a target that would drift off the
        side stops at the edge, so a crosshair parked there is not
        rewarded for the target having nowhere else to go.
        """
        part = min(1.0, max(0.0, (at - self.at) / float(ALOFT)))
        return (min(1.0, max(0.0, self.across + self.drift * part)),
                self.up)


class Road(NamedTuple):
    """One trial's stretch of road and sky, and the rung that dealt it."""

    grade: Grade
    hazards: Tuple[Hazard, ...]
    #: One entry a sub-row: the hazards overlapping it. Almost always
    #: empty or one long; two when a rung deals them in pairs.
    marks: Tuple[Tuple[int, ...], ...]
    #: One entry a sub-row: the hazards whose run *begins* here. This is
    #: where a clip and a prize are resolved, and it is what makes each
    #: of them happen exactly once — every sub-row is swept exactly once
    #: however fast the car is going.
    heads: Tuple[Tuple[int, ...], ...]
    #: One entry a sub-row: the hazards whose run *ends* here, which is
    #: where one is counted as got by.
    tails: Tuple[Tuple[int, ...], ...]
    sky: Tuple[Target, ...]
    start: int      #: the lane the car starts in
    #: Ticks allowed. Zero means no clock at all, which is what
    #: :func:`line` is handed while it is working out the par the clock
    #: is then set from.
    clock: int = 0
    #: Ticks the clean line takes. Zero until :func:`timed` has run.
    par: int = 0

    @property
    def length(self) -> int:
        return len(self.marks)

    @property
    def rows(self) -> int:
        return self.grade.rows

    def count(self, *kinds: int) -> int:
        wanted = frozenset(kinds)
        return sum(1 for haz in self.hazards if haz.kind in wanted)

    @property
    def deadly(self) -> int:
        return sum(1 for haz in self.hazards if haz.kind in FATAL)

    @property
    def prizes(self) -> int:
        return self.count(COIN, PAD)


# --- the car -------------------------------------------------------------

class Ride(NamedTuple):
    """Where the car is, what it is committed to, and how it is going.

    A value rather than an object, and that is load-bearing: the same
    :func:`roll` advances the car on the screen and the states inside
    :func:`line`, so the solver cannot come to believe in a rule the
    game does not have.
    """

    at: int = 0         #: sub-rows of road behind it
    lane: int = 0       #: the lane it is in, or the one it is leaving
    to: int = 0         #: the lane it is crossing to; ``lane`` when settled
    cross: int = 0      #: ticks of the swerve still owed
    air: int = 0        #: ticks of the jump still owed
    speed: int = 1      #: sub-rows it takes a tick
    ticks: int = 0      #: ticks spent, against the road's clock
    hit: bool = False
    passed: int = 0     #: fatal hazards got by
    clipped: int = 0    #: glancing blows taken
    points: int = 0     #: coins and pads, less what the clips cost

    @property
    def settled(self) -> bool:
        """Is the wheel listening?"""
        return not self.cross and not self.air

    @property
    def covers(self) -> Tuple[int, ...]:
        """The lanes a hazard would have to stand in to be met."""
        return (self.lane,) if not self.cross else (self.lane, self.to)

    @property
    def rows_done(self) -> int:
        return self.at // SUB


def share(ride: Ride, grade: Grade) -> float:
    """How far across a swerve is: 0 in the lane left, 1 in the new one.

    A fraction rather than a flag, so the car slides. It is also the
    honest picture: for the whole of a swerve the car is in both lanes,
    and a car drawn in one of them would be the screen telling a lie
    about the oldest rule in the game.

    The rung is passed in rather than carried on the ride, because the
    only thing this is for is drawing and the search has a few hundred
    thousand rides to keep small.
    """
    if not ride.cross:
        return 0.0
    return (grade.swerve - ride.cross + 1) / float(grade.swerve + 1)


def drawn_lane(ride: Ride, grade: Grade) -> float:
    """Where to draw the car, which is a fraction while it crosses."""
    return ride.lane + (ride.to - ride.lane) * share(ride, grade)


def start_ride(road: Road) -> Ride:
    return Ride(lane=road.start, to=road.start, speed=1)


# --- one tick ------------------------------------------------------------

def press(ride: Ride, port: int, grade: Grade) -> Ride:
    """Take one wheel port, if the car is in a position to take it.

    A commitment already under way swallows the port whole — every one
    of them, not just the one that would undo it. That is Donkey's rule
    about a second press, widened to the wheel: while a swerve or a
    jump runs down there is nothing the driver can do about the road,
    and the ticks it costs are the ticks the sights are free in.

    Kept apart from :func:`advance` because on a screen the two happen
    at different moments — the press lands on the frame the key went
    down, the road comes on the clock — and :func:`roll` is the two of
    them in the order the rules put them.
    """
    if not ride.settled:
        return ride
    lane = ride.lane
    if port == LEFT and lane > 0:
        return ride._replace(to=lane - 1, cross=grade.swerve)
    if port == RIGHT and lane < LANES - 1:
        return ride._replace(to=lane + 1, cross=grade.swerve)
    if port == JUMP:
        return ride._replace(air=grade.hang)
    if port == FASTER:
        return ride._replace(speed=min(grade.top, ride.speed + 1))
    if port == SLOWER:
        return ride._replace(speed=max(1, ride.speed - 1))
    return ride


def advance(ride: Ride, road: Road) -> Ride:
    """One tick of road, met by the car the port left behind.

    Order matters and it is the order the screen draws in. The port has
    already been taken, so a swerve started this tick is across the
    middle for the road that arrives — which is exactly why it cannot
    be a dodge. Then ``speed`` sub-rows go by, every one of them
    checked. Then the commitments run down by one.
    """
    grade = road.grade
    lane, to = ride.lane, ride.to
    cross, air, speed = ride.cross, ride.air, ride.speed
    covers = ride.covers
    at, length = ride.at, road.length
    hit, passed = ride.hit, ride.passed
    clipped, points = ride.clipped, ride.points
    # The tick moves the car by the gear it started in, and everything
    # a toll pays out is priced in that gear too. A clip or a pad met
    # half way through the sweep changes the *next* tick and not this
    # one -- which is not a nicety. Advancing by the gear a toll left
    # behind would have re-swept the sub-rows the shortened tick no
    # longer reached, and a cone would have been met twice over: once
    # going in and once again from where it dropped you.
    moved = speed
    for step in range(moved):
        here = at + step
        if here >= length:
            break
        for index in road.marks[here]:
            haz = road.hazards[index]
            kind = KINDS[haz.kind]
            if haz.lane not in covers:
                continue
            if not kind.tall and air:
                continue                    # over the top of it
            if kind.toll == 'fatal':
                # Any moment of overlap, which is why this is checked
                # on every swept sub-row rather than once: a jump that
                # lands half way over a log is a crash.
                hit = True
                break
            if index not in road.heads[here]:
                continue                    # met once, at the meeting
            if kind.toll == 'clip':
                clipped += 1
                points -= 1
                speed = 1
            elif kind.toll == 'ramp':
                if not cross:
                    # Mid-swerve the wheels are not square to it and it
                    # does nothing, which also keeps a ride from being
                    # in the air and across the middle at once.
                    air = grade.hang
            elif kind.toll == 'boost':
                speed = min(grade.top, speed + 1)
                points += 1
            elif kind.toll == 'coin':
                points += moved
        if hit:
            break
        for index in road.tails[here]:
            if road.hazards[index].kind in FATAL:
                passed += 1
    if cross:
        cross -= 1
        if not cross:
            lane, to = to, to
    elif air:
        air -= 1
    return Ride(at=min(at + moved, length), lane=lane, to=to, cross=cross,
                air=air, speed=speed, ticks=ride.ticks + 1, hit=hit,
                passed=passed, clipped=clipped, points=points)


def roll(ride: Ride, port: int, road: Road) -> Ride:
    """The press and the road it is met by, in that order. One tick."""
    return advance(press(ride, port, road.grade), road)


def over(ride: Ride, road: Road) -> bool:
    """Crashed, home, or out of time."""
    return (ride.hit or ride.at >= road.length
            or (road.clock and ride.ticks >= road.clock))


def cleared(ride: Ride, road: Road) -> bool:
    """The road's verdict: the far end of it, on four wheels, in time."""
    return not ride.hit and ride.at >= road.length


def late(ride: Ride, road: Road) -> bool:
    """Ran out of clock with road still to go."""
    return (not ride.hit and ride.at < road.length
            and bool(road.clock) and ride.ticks >= road.clock)


def drive(road: Road, ports: Sequence[int]) -> Ride:
    """Run *ports* down *road* and hand back the ride that comes out."""
    ride = start_ride(road)
    for port in ports:
        if over(ride, road):
            break
        ride = roll(ride, port, road) if port in WHEEL else roll(
            ride, HOLD, road)
    return ride


# --- the sights ----------------------------------------------------------

#: How far the crosshair moves on one nudge, as a fraction of the sky.
NUDGE = 0.10

#: How near the crosshair has to be for a shot to tell. In the sky's own
#: units, where 1.0 is its full width, and generous on purpose: what is
#: being measured is whether a player *went* to the target, not whether
#: they can hold a mouse still.
RETICLE = 0.11


def sighted(road: Road, at: int, cross_x: float, cross_y: float,
            downed: Set[int] = frozenset()) -> Optional[int]:
    """Which target a shot from *(cross_x, cross_y)* would take, if any.

    The nearest one aloft and still up, inside :data:`RETICLE`. Ties go
    to the lower index, which is the older target, so a shot is never
    ambiguous.
    """
    best, best_gap = None, RETICLE
    for index, target in enumerate(road.sky):
        if index in downed or not target.aloft(at):
            continue
        across, up = target.where(at)
        gap = math.hypot(across - cross_x, up - cross_y)
        if gap < best_gap:
            best, best_gap = index, gap
    return best


def aloft(road: Road, at: int, downed: Set[int] = frozenset()) -> List[int]:
    """Every target that is up and has not been taken, at position *at*."""
    return [index for index, target in enumerate(road.sky)
            if index not in downed and target.aloft(at)]


# --- what a road can be driven in ----------------------------------------

def _rest(ride: Ride) -> Tuple[int, int, int, int, int]:
    """The part of a ride the search has to remember.

    Five numbers, and the reason there are only five is the rule that
    the wheel is deaf mid-commitment: crossing and airborne cannot both
    be non-zero, so the three of them together are one small phase.
    """
    return (ride.lane, ride.to, ride.cross, ride.air, ride.speed)


def _revive(at: int, rest: Tuple[int, int, int, int, int]) -> Ride:
    lane, to, cross, air, speed = rest
    return Ride(at=at, lane=lane, to=to, cross=cross, air=air, speed=speed)


def line(road: Road) -> Optional[List[int]]:
    """The fewest ticks to the far end with no crash and no clip.

    A forward dynamic program over ``(sub-row, lane, commitment,
    speed)``. It is a DAG rather than a graph with cycles in it,
    because every tick moves the car at least one sub-row, so the
    states can be settled in one pass in order of sub-row and there is
    no queue to keep.

    Returns the ports, or ``None`` when the road cannot be driven clean
    inside its clock. :func:`generate` never hands out one of those;
    the ``None`` is for roads written by hand, which the tests do.

    The transitions are :func:`roll`, not a copy of it. That is the
    whole reason to build it this way: a solver with its own idea of
    the rules is a solver that certifies roads the game does not agree
    are drivable, and the disagreement shows up as a player losing a
    road that was provably fine.
    """
    length, clock = road.length, road.clock
    #: sub-row -> rest -> (ticks, (previous sub-row, previous rest, port))
    layers: List[Dict[Tuple[int, int, int, int, int], Tuple[int, Optional[
        Tuple[int, Tuple[int, int, int, int, int], int]]]]]
    layers = [{} for _step in range(length + 1)]
    begin = start_ride(road)
    layers[0][_rest(begin)] = (0, None)
    for at in range(length):
        for rest, (ticks, _back) in list(layers[at].items()):
            if clock and ticks >= clock:
                continue
            ride = _revive(at, rest)
            ports = WHEEL if ride.settled else (HOLD,)
            for port in ports:
                went = roll(ride, port, road)
                if went.hit or went.clipped:
                    continue
                key = _rest(went)
                cell = layers[went.at].get(key)
                if cell is None or cell[0] > ticks + 1:
                    layers[went.at][key] = (ticks + 1, (at, rest, port))
    if not layers[length]:
        return None
    rest = min(layers[length], key=lambda key: layers[length][key][0])
    at = length
    ports: List[int] = []
    while True:
        _ticks, back = layers[at][rest]
        if back is None:
            break
        at, rest, port = back
        ports.append(port)
    ports.reverse()
    return ports


def drivable(road: Road) -> bool:
    """Is there a clean line through this road inside its clock?"""
    return line(road) is not None


# --- the deal ------------------------------------------------------------

def build(grade: Grade, hazards: Sequence[Hazard],
          sky: Sequence[Target] = (), start: int = 1,
          clock: int = 0) -> Road:
    """A road from a list of hazards, with the three indexes built.

    Comes back with no clock on it unless one is given. Put one on with
    :func:`timed`, which works out the road's own par first.
    """
    length = grade.length
    marks: List[List[int]] = [[] for _step in range(length)]
    heads: List[List[int]] = [[] for _step in range(length)]
    tails: List[List[int]] = [[] for _step in range(length)]
    kept: List[Hazard] = []
    for haz in hazards:
        if not 0 <= haz.at < length:
            continue
        index = len(kept)
        kept.append(haz)
        for step in range(SPAN):
            if haz.at + step < length:
                marks[haz.at + step].append(index)
        heads[haz.at].append(index)
        tails[min(length - 1, haz.end)].append(index)
    return Road(grade=grade, hazards=tuple(kept),
                marks=tuple(tuple(row) for row in marks),
                heads=tuple(tuple(row) for row in heads),
                tails=tuple(tuple(row) for row in tails),
                sky=tuple(sky), start=start, clock=clock)


def timed(road: Road) -> Optional[Road]:
    """Solve *road* and hand it back with its own clock on it.

    The clock is the road's par times the rung's :attr:`Grade.slack`,
    so what a rung demands is the same demand on every deal it makes:
    "within this much of the best line there is". Returns ``None`` for
    a road with no clean line through it at all, which is what tells
    :func:`generate` to take something out of it.
    """
    ports = line(road)
    if ports is None:
        return None
    return road._replace(par=len(ports),
                         clock=int(math.ceil(len(ports) * road.grade.slack)))


def generate(level: int, seed: int = 0) -> Road:
    """Lay one road and one sky for *level*. Deterministic in *seed*.

    Hazards go down at a rate the rung asks for, in ones and — from the
    third rung — in pairs, with a drawn row of clear road kept after
    each so that two never draw as one long thing. Then the road is
    solved. A road the program cannot finish clean inside its clock has
    a blocking hazard taken out of it at random and is solved again,
    until it can be.

    That loop is short in practice — measured over the whole ladder it
    takes out nothing at all on most deals — because the generator
    already keeps the road sparse enough to breathe. It is the
    *guarantee* that matters rather than the cost: what comes back has
    a clean line through it and :func:`line` will produce it.
    """
    grade = GRADES[max(0, min(len(GRADES) - 1, level - 1))]
    rng = random.Random(seed)
    hazards = _lay(grade, rng)
    sky = _fly(grade, rng)
    start = rng.randrange(LANES)
    road = build(grade, hazards, sky, start)
    while True:
        solved = timed(road)
        if solved is not None:
            return solved
        blocking = [index for index, haz in enumerate(road.hazards)
                    if haz.kind in BLOCKING]
        if not blocking:
            # Nothing left that can be in the way. A road with no
            # blocking hazard on it is drivable at a crawl, so this is
            # unreachable rather than a fallback -- but a generator
            # that could loop forever is worse than one that stops.
            return timed(build(grade, [], sky, start))
        dropped = rng.choice(blocking)
        road = build(grade, [haz for index, haz in enumerate(road.hazards)
                             if index != dropped], sky, start)


def _lay(grade: Grade, rng: random.Random) -> List[Hazard]:
    """Hazards down the road, one place at a time.

    A pair is two hazards in different lanes at the same sub-row, and
    never more than two: with three lanes a third would be a wall, and
    a wall is not a hazard the player failed to avoid.
    """
    length = grade.length
    chance = grade.density / float(SUB)
    free_from = RUN_IN * SUB
    hazards: List[Hazard] = []
    for at in range(length):
        if at < free_from or at + SPAN > length:
            continue
        if rng.random() >= chance:
            continue
        lanes = list(range(LANES))
        rng.shuffle(lanes)
        wanted = 2 if rng.random() < grade.pairs else 1
        for lane in lanes[:wanted]:
            hazards.append(Hazard(at, lane, rng.choice(grade.kinds)))
        free_from = at + SPAN + GAP
    if not any(haz.kind in FATAL for haz in hazards):
        # A road with nothing on it that can end you is a free verdict.
        hazards.append(Hazard(RUN_IN * SUB, rng.randrange(LANES),
                              rng.choice([kind for kind in grade.kinds
                                          if kind in FATAL])))
    return hazards


def _fly(grade: Grade, rng: random.Random) -> List[Target]:
    """Targets over the horizon, at fixed places on the road."""
    length = grade.length
    chance = grade.sky / float(SUB)
    sky: List[Target] = []
    for at in range(length):
        if rng.random() < chance:
            across = rng.uniform(0.10, 0.90)
            drift = rng.uniform(-0.35, 0.35)
            if not 0.0 <= across + drift <= 1.0:
                drift = -drift
            sky.append(Target(at=at, across=across,
                              up=rng.uniform(0.18, 0.86), drift=drift))
    return sky


# --- what the shallow policies are worth ---------------------------------

class Play(NamedTuple):
    """How one policy got on with one road."""

    ride: Ride
    home: bool
    shot: int           #: targets taken out of the sky
    ports: Tuple[int, ...]


def _blocked(road: Road, lane: int, first: int, past: int) -> Optional[int]:
    """The first blocking hazard in *lane* over ``[first, past)``, or None."""
    length = road.length
    for at in range(max(0, first), min(length, past)):
        for index in road.marks[at]:
            haz = road.hazards[index]
            if haz.lane == lane and haz.kind in BLOCKING:
                return index
    return None


def _sky_port(road: Road, ride: Ride, cross: List[float],
              downed: Set[int]) -> Optional[int]:
    """Take the crosshair to the nearest target, and pull when it is there.

    Four nudges and a trigger is a coarse instrument on purpose: it is
    the same instrument the mouse is, sampled at the rate the boundary
    steps, and what it costs in ticks is the thing being measured.
    """
    up = aloft(road, ride.at, downed)
    if not up:
        return None
    wants = min(up, key=lambda index: math.hypot(
        road.sky[index].where(ride.at)[0] - cross[0],
        road.sky[index].where(ride.at)[1] - cross[1]))
    across, high = road.sky[wants].where(ride.at)
    gap_x, gap_y = across - cross[0], high - cross[1]
    if math.hypot(gap_x, gap_y) <= RETICLE * 0.8:
        return FIRE
    if abs(gap_x) >= abs(gap_y):
        return AIM_RIGHT if gap_x > 0 else AIM_LEFT
    return AIM_UP if gap_y > 0 else AIM_DOWN


def _take_sky(road: Road, ride: Ride, port: int, cross: List[float],
              downed: Set[int]) -> int:
    """Apply a sights port. Returns 1 if it took a target down."""
    if port == AIM_LEFT:
        cross[0] = max(0.0, cross[0] - NUDGE)
    elif port == AIM_RIGHT:
        cross[0] = min(1.0, cross[0] + NUDGE)
    elif port == AIM_DOWN:
        cross[1] = max(0.0, cross[1] - NUDGE)
    elif port == AIM_UP:
        cross[1] = min(1.0, cross[1] + NUDGE)
    elif port == FIRE:
        found = sighted(road, ride.at, cross[0], cross[1], downed)
        if found is not None:
            downed.add(found)
            return 1
    return 0


def _wheel_port(road: Road, ride: Ride, want: int, look: float) -> int:
    """One shallow driving decision: is the lane ahead going to be clear?

    *look* is the whole of the policy. At ``1.0`` the window it checks
    is the road the car would be committed over if it swerved *now*,
    which is the aimed press Donkey measures; below that it is the
    press a person makes on sight and it arrives too late to be a
    dodge.
    """
    grade = road.grade
    reach = max(1, int(round(look * grade.swerve * ride.speed))) + ride.speed
    trouble = _blocked(road, ride.lane, ride.at, ride.at + reach)
    if trouble is None:
        if ride.speed < want:
            return FASTER
        if ride.speed > want:
            return SLOWER
        return HOLD
    haz = road.hazards[trouble]
    if not KINDS[haz.kind].tall:
        # Off the ground for the whole overlap, or not at all: the jump
        # covers speed * hang sub-rows and the run is SPAN long.
        if ride.speed * grade.hang >= (haz.end - ride.at) + 1:
            return JUMP
    swerve_over = grade.swerve * ride.speed + ride.speed
    for side, port in ((-1, LEFT), (1, RIGHT)):
        lane = ride.lane + side
        if not 0 <= lane < LANES:
            continue
        if _blocked(road, lane, ride.at, ride.at + swerve_over) is None:
            return port
    return SLOWER if ride.speed > 1 else HOLD


def play(road: Road, want: int = TOP, look: float = 1.0,
         shoot: str = 'never', rng: Optional[random.Random] = None) -> Play:
    """Drive *road* with one of the shallow policies and report how it went.

    ``rng`` makes it the coin: every port uniform, which is the floor.
    Otherwise it holds *want* where it can and dodges on a window
    *look* wide. *shoot* is the whole of the second channel and it is
    written as a setting on the *same* driver rather than as a second
    function, because that is the only fair way to ask what the sky
    costs the road:

    ``never``
        the sky is not looked at.
    ``spare``
        the sights get the ticks the wheel had no use for — a tick that
        would have been a hold, and every tick of a swerve or a jump,
        because the wheel is deaf for those anyway.
    ``always``
        a target aloft is taken now, whatever the road was about to
        ask for.
    """
    grade = road.grade
    want = min(want, grade.top)
    ride = start_ride(road)
    cross: List[float] = [0.5, 0.5]
    downed: Set[int] = set()
    ports: List[int] = []
    shot = 0
    while not over(ride, road):
        port = HOLD
        if rng is not None:
            port = rng.randrange(PORTS)
        elif not ride.settled:
            # The wheel is deaf while a commitment runs down, so these
            # ticks are the sky's for nothing. Whether a policy notices
            # that is most of the difference between the rows below.
            if shoot != 'never':
                port = _sky_port(road, ride, cross, downed) or HOLD
        else:
            wheel = _wheel_port(road, ride, want, look)
            eyes = (_sky_port(road, ride, cross, downed)
                    if shoot != 'never' else None)
            if eyes is not None and (shoot == 'always' or wheel == HOLD):
                port = eyes
            else:
                port = wheel
        ports.append(port)
        if port in SIGHTS:
            shot += _take_sky(road, ride, port, cross, downed)
            ride = roll(ride, HOLD, road)
        else:
            ride = roll(ride, port, road)
    return Play(ride=ride, home=cleared(ride, road), shot=shot,
                ports=tuple(ports))


#: Measured shares, kept so a screen may quote them without paying for
#: them twice. Keyed by everything that changes the answer, the seed
#: included — a cache that ignores the seed hands the first sample back
#: for every one asked for after it, and a sweep over seeds comes out
#: looking suspiciously stable.
_SCORES: Dict[Tuple[int, int, int, str], Tuple[float, float]] = {}

#: The roads a measurement was taken on, kept so the *next* policy
#: measured on the same rung does not deal them again. Dealing is the
#: expensive half — every road is solved before it is handed out — and
#: the policies are compared on identical roads anyway, which is what
#: makes the comparison a comparison rather than two samples.
_DEALT: Dict[Tuple[int, int, int], Tuple[Road, ...]] = {}

#: The policies :func:`rehearse` knows, and what each one is.
POLICIES = ('random', 'crawl', 'reactive', 'aimed', 'gunner', 'sniper',
            'exact')


def dealt(level: int, deals: int, seed: int = 0) -> Tuple[Road, ...]:
    """The roads a measurement at *level* is taken on, dealt once."""
    key = (level, deals, seed)
    if key not in _DEALT:
        dice = random.Random(seed)
        _DEALT[key] = tuple(generate(level, seed=dice.randrange(1 << 30))
                            for _deal in range(deals))
    return _DEALT[key]


def rehearse(level: int, deals: int = 30, seed: int = 0,
             policy: str = 'aimed') -> float:
    """The share of roads *policy* gets to the far end of, measured.

    ``random``
        a uniform port a tick over all eleven. It clears nothing, for
        Donkey's reason and one of its own: a press starts a swerve it
        cannot call off, and five of the eleven ports do not touch the
        wheel at all.
    ``crawl``
        the aimed dodge at one sub-row a tick. It is *safe* — almost
        nothing on the road can catch a car going that slowly — and it
        is the policy the clock exists to refuse.
    ``reactive``
        the aimed dodge with the window cut to a third, which is the
        swerve a person makes on sight of the thing.
    ``aimed``
        the dodge thrown at the road the swerve will actually cover.
    ``gunner``
        the same driver, shooting on the ticks the wheel had no use
        for.
    ``sniper``
        the same driver again, shooting the moment anything is up
        there. The gap between these two is what the second channel
        costs when it is taken at the wrong moment, and it is the
        number this task exists to produce.
    ``exact``
        :func:`line`, which is 1.0 by construction and is here so the
        others have something to be a share of.

    Every policy is measured on the *same* roads, dealt once by
    :func:`dealt` and kept, which is what makes the rows above a
    comparison rather than four samples.

    Returns the share cleared. :func:`sky_toll` reports the rest of it.
    """
    return sky_toll(level, deals, seed, policy)[0]


def sky_toll(level: int, deals: int = 30, seed: int = 0,
             policy: str = 'aimed') -> Tuple[float, float]:
    """``(share of roads cleared, targets shot a road)`` for *policy*.

    Thirty deals by default, which is what a screen can afford to ask
    for while somebody is waiting: every road is solved before it is
    dealt, so a hundred of them at the top of the ladder is several
    seconds of nothing happening. The numbers written down in the
    documentation are taken over sixty, and the tests take their own
    over forty — a default is a budget rather than a claim about how
    many deals a claim needs.
    """
    key = (level, deals, seed, policy)
    if key in _SCORES:
        return _SCORES[key]
    dice = random.Random(seed + 1)
    home, shot = 0, 0
    for road in dealt(level, deals, seed):
        if policy == 'exact':
            ride = drive(road, line(road) or [])
            home += 1 if cleared(ride, road) else 0
            continue
        if policy == 'random':
            done = play(road, rng=random.Random(dice.randrange(1 << 30)))
        elif policy == 'crawl':
            done = play(road, want=1)
        elif policy == 'reactive':
            done = play(road, look=0.34)
        elif policy == 'gunner':
            done = play(road, shoot='spare')
        elif policy == 'sniper':
            done = play(road, shoot='always')
        else:
            done = play(road)
        home += 1 if done.home else 0
        shot += done.shot
    _SCORES[key] = (home / float(deals), shot / float(deals))
    return _SCORES[key]


__all__ = ['AIM_DOWN', 'AIM_LEFT', 'AIM_RIGHT', 'AIM_UP', 'ALOFT', 'BARRIER',
           'BLOCKING', 'BODY', 'CAR', 'COIN', 'CONE', 'DONKEY', 'FASTER',
           'FATAL', 'FIRE', 'GAP', 'GRADES', 'Grade', 'HOLD', 'Hazard',
           'JUMP', 'KINDS', 'Kind', 'LANES', 'LEFT', 'LOG', 'NUDGE', 'PAD',
           'POLICIES', 'PORTS', 'Play', 'RAMP', 'RETICLE', 'RIGHT', 'RUBBLE',
           'RUN_IN', 'Ride', 'Road', 'SIGHTS', 'SLOWER', 'SPAN', 'SUB', 'TOP',
           'TRUCK', 'Target', 'WHEEL', 'advance', 'aloft', 'build', 'cleared',
           'dealt', 'drawn_lane', 'drivable', 'drive', 'generate', 'late',
           'line',
           'over', 'play', 'press', 'rehearse', 'roll', 'share', 'sighted',
           'sky_toll', 'start_ride', 'timed']
