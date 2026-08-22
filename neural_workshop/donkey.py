# -*- coding: utf-8 -*-
"""Donkey's model: two lanes, one key, and a swerve you cannot take back.

The 1981 original is four hundred lines of BASIC and one idea. A car
runs up a two-lane road, donkeys stand in it, and the space bar puts
you in the other lane. Hit one and the round is over. That is the whole
game, and the whole of its difficulty was that the road got faster.

Speed is a **dial** here and not a rung, which is the one place this
departs from the original and it departs on purpose. One tick is one
step at the agent boundary, so a rung that ran the road faster would be
a rung a person feels and a learner cannot, and the two would be
playing different ladders while reporting the same number.

What replaces it is **the swerve**. Crossing takes :attr:`Grade.swerve`
rows and cannot be called off, and while the car is across the middle
it is in *both* lanes, so a donkey in either one hits it. That single
rule is what turns the classic into a task with something in it:

* You cannot dodge at the last moment. The road a donkey arrives on is
  road you must already be clear of, so the press has to come
  ``swerve`` rows early — which is exactly the opposite of what a
  reaction test rewards, and the reason this is not Reflex with a car.
* From the sixth rung the swerve is two rows wide and from the tenth
  three, so the press has to be thrown further and further in front of
  the thing it is aimed at. Measured over two hundred deals a rung, the
  swerve-on-sight dodge clears every road while the swerve is one row
  wide and 6%, 3%, 3%, 1% and 6% of them on rungs six to ten. The
  policy that aims at the swerve clears all of them.

What is **not** here is planning depth, and it is worth saying so
plainly because the task was built expecting it. Aiming the press at
the swerve is enough on every road this deals — see :func:`dodge` for
why the generator leaves nothing harder standing. The task is
anticipation and sustained attention, not a line chosen several rows
out, and a rung name is not evidence to the contrary.

The road is finer than it looks
-------------------------------

A row is what the screen draws and it is **not** the unit the rules
work in. The road is cut into :data:`SUB` sub-rows a row, the car
travels one sub-row a tick, and the car and the donkey each have a
*length* — :data:`CAR` and :data:`BEAST` sub-rows of it. A hit is the
two of them overlapping, and nothing coarser than that.

That is not decoration. Resolved a row at a time, "did it hit" could
only ever be answered to within a whole row, so a round ended on the
tick the car entered the donkey's row rather than on the tick the two
touched — a car's length early, which is what it looked like.

Every donkey therefore blocks :data:`SPAN` sub-rows rather than one
row. That is the two bodies added together less the one they share, so
the solver's "is this sub-row free" is the same question the collision
asks, and the generator's refusals are refusals of real collisions.

So a road can be **unsurvivable**, and one that is would be scored as a
failure the player could not have avoided. The road is not generated
and then checked: a donkey goes down only where the set of surviving
car states stays non-empty, which is :func:`feasible` maintained as the
road is laid. Every road this deals has a line through it, and
:func:`line` will hand it to you.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

#: What the one key does with a tick. Two, because the original had one
#: key: holding the wheel straight is not a null action here, it is the
#: other half of the choice.
HOLD, SWITCH = 0, 1

#: Lanes. Two, and it was always two.
LANES = (0, 1)

#: Sub-rows a drawn row is cut into: the rules' unit, not the screen's.
#:
#: Four rather than more because every one of them is a step at the
#: agent boundary and a tick of the person's clock, and four is already
#: enough that the car and the donkey meet within a quarter of a row of
#: each other. Raising it buys resolution nobody can see and charges
#: for it in steps.
SUB = 4

#: How long the car and the donkey are, in sub-rows. Three quarters of
#: a drawn row each, and the screen draws them at exactly this length
#: so that the frame a round ends on is the frame the two boxes meet.
CAR, BEAST = 3, 3

#: Sub-rows a donkey blocks: the two bodies added together, less the
#: one they share.
#:
#: A car at sub-row ``at`` overlaps a donkey whose body starts at ``b``
#: exactly when ``b - CAR < at < b + BEAST``, which is :data:`SPAN`
#: sub-rows wide. Marking all of them blocked is what lets the solver
#: and the generator ask "is this sub-row free" and be asking the same
#: question the collision asks.
SPAN = CAR + BEAST - 1

#: Rows of clear road before the first donkey may stand.
#:
#: Not politeness. The first thing a round asks is whether you were
#: looking, and a donkey on the road the car starts under would be
#: asking whether you had already pressed.
RUN_IN = 3

#: Clear sub-rows kept between one donkey and the next.
#:
#: A drawn row of it. Without it two donkeys a sub-row apart in the
#: same lane draw as one long animal, and the road stops being
#: countable — which is a thing the screen promises in words at the top
#: of every trial.
GAP = SUB


class Grade(NamedTuple):
    """One rung: how long the road is, how full, and how wide the swerve."""

    name: str
    rows: int           #: rows of road in one trial
    density: float      #: donkeys a row the dice are asked for
    swerve: int         #: rows the car spends crossing, committed

    @property
    def crossing(self) -> int:
        """The swerve in the unit the rules use."""
        return self.swerve * SUB


#: Ten rungs. Density fills the road, length keeps you on it, and the
#: swerve is the one that changes what the task is.
#:
#: The first five are the original game: a one-row swerve, so the press
#: is aimed at the row in front of the bonnet and dodging on sight is
#: playing perfectly. From the sixth the swerve is two rows and dodging
#: on sight stops being a policy — measured in :func:`rehearse` and in
#: ``tests/test_donkey.py``, and what it loses there is the whole
#: content of the upper half.
GRADES: Tuple[Grade, ...] = (
    #     name                      rows  density  swerve
    Grade('a clear road',             24,    0.14,      1),
    Grade('one at a time',            28,    0.26,      1),
    Grade('closer together',          32,    0.40,      1),
    Grade('a busy road',              36,    0.54,      1),
    Grade('the long haul',            48,    0.54,      1),
    Grade('the wide swerve',          36,    0.34,      2),
    Grade('wide and busy',            40,    0.48,      2),
    Grade('no room to think',         44,    0.62,      2),
    Grade('the long night',           56,    0.62,      2),
    Grade('three rows to cross',      56,    0.54,      3),
)


class Road(NamedTuple):
    """One trial's stretch of road, and the rung that dealt it."""

    grade: Grade
    #: One entry a **sub-row**, from the sub-row the car meets first:
    #: the lane a donkey blocks, or ``None`` for clear road. A donkey
    #: fills :data:`SPAN` of these. Both lanes are never blocked at
    #: once — that would be a wall, not a donkey.
    blocked: Tuple[Optional[int], ...]
    #: ``(first blocked sub-row, lane)`` for each donkey, in order.
    beasts: Tuple[Tuple[int, int], ...]
    #: The lane the car starts in.
    start: int

    @property
    def donkeys(self) -> int:
        return len(self.beasts)

    @property
    def length(self) -> int:
        """The road in sub-rows, which is what a tick moves the car."""
        return len(self.blocked)

    @property
    def rows(self) -> int:
        """The road in drawn rows, which is what the screen counts."""
        return self.grade.rows

    @property
    def ends(self) -> frozenset:
        """The last blocked sub-row of each donkey: where it is *past*."""
        return frozenset(at + SPAN - 1 for at, _lane in self.beasts)


def body_of(at: int) -> int:
    """Where a donkey's drawn body begins, given its blocked run.

    The run starts a car's length before the animal does, because that
    is where the two would first overlap. The screen wants the animal.
    """
    return at + CAR - 1


class Car:
    """Where the car is, what it is in the middle of, and how it went."""

    __slots__ = ('lane', 'crossing', 'at', 'passed', 'hit', 'span')

    def __init__(self, lane: int = 0, swerve: int = 1) -> None:
        self.lane = lane
        #: Sub-rows of the crossing still to run, this one included.
        #: Non-zero means the car is between lanes and a donkey in
        #: either one is a donkey in this one.
        self.crossing = 0
        self.at = 0             #: sub-rows of road behind it
        self.passed = 0         #: donkeys it got by
        self.hit = False
        #: What a crossing costs, in sub-rows. Taken in rows, because
        #: rows are what a rung is written in and what a player counts.
        self.span = swerve * SUB

    @property
    def across(self) -> bool:
        return self.crossing > 0

    @property
    def rows_done(self) -> int:
        """How far along in drawn rows, for the screen to say out loud."""
        return self.at // SUB

    @property
    def share(self) -> float:
        """How far across the car is: 0 in the lane it left, 1 in the new one.

        A fraction rather than a flag, so the car slides. It is also the
        honest picture: for the whole of this the car is in both lanes,
        and a car drawn in one of them would be the screen telling a lie
        about the only rule in the game.
        """
        if not self.crossing:
            return 0.0
        return (self.span - self.crossing + 1) / float(self.span + 1)

    @property
    def covers(self) -> Tuple[int, ...]:
        """The lanes a donkey would have to stand in to be hit."""
        return LANES if self.crossing else (self.lane,)


# --- one tick ------------------------------------------------------------

def steer(car: Car, port: int) -> bool:
    """Take the press, if there is anything for it to do.

    A swerve already under way swallows the key. That is the whole of
    what makes the road a road rather than a quiz: the press commits
    the next :attr:`Grade.swerve` rows, and no second press buys them
    back.
    """
    if port != SWITCH or car.crossing:
        return False
    car.crossing = car.span
    return True


def beat(car: Car, road: Road, ends: Optional[frozenset] = None) -> int:
    """One sub-row of road arrives. Returns the donkeys got past, 0 or 1.

    Order matters and it is the same order the screen draws in: the
    press has already been taken, so the road that arrives is met by
    the car the press left behind. A swerve started this tick is across
    the middle for *this* sub-row, which is why it cannot be a dodge.
    """
    if car.hit or car.at >= road.length:
        return 0
    lane = road.blocked[car.at]
    car.at += 1
    got = 0
    if lane is not None and lane in car.covers:
        car.hit = True
    elif lane is not None and car.at - 1 in (road.ends if ends is None
                                             else ends):
        # Counted where the overlap would have *ended* rather than
        # where it would have begun, so a donkey is past when it is
        # past rather than when it comes alongside.
        car.passed += 1
        got = 1
    if car.crossing:
        car.crossing -= 1
        if not car.crossing:
            car.lane = 1 - car.lane
    return got


def over(car: Car, road: Road) -> bool:
    return car.hit or car.at >= road.length


def cleared(car: Car, road: Road) -> bool:
    """The round's verdict: the far end of the road, on four wheels."""
    return not car.hit and car.at >= road.length


# --- what survives -------------------------------------------------------

def states(start: int) -> frozenset:
    """The car states the road starts from: settled, in the start lane."""
    return frozenset({(start, 0)})


def feasible(alive: frozenset, lane: Optional[int],
             crossing: int) -> frozenset:
    """The states that survive a sub-row blocked at *lane*, from *alive*.

    A pure function of the sub-row, which is what lets the generator
    ask "may a donkey stand here?" without simulating anything: it may
    if what comes back is non-empty.

    The state is ``(lane, owed)`` before the sub-row: ``owed`` sub-rows
    of the crossing still to run, this one included. A settled car may
    hold or start a swerve; a crossing car has no say.
    """
    out = set()
    for at, owed_in in alive:
        moves = [(at, owed_in)] if owed_in else [(at, 0), (at, crossing)]
        for was, owed in moves:
            covers = LANES if owed else (was,)
            if lane is not None and lane in covers:
                continue
            if owed:
                owed -= 1
                out.add((1 - was if not owed else was, owed))
            else:
                out.add((was, 0))
    return frozenset(out)


def survivable(road: Road) -> bool:
    """Is there a line through this road at all?"""
    alive = states(road.start)
    for lane in road.blocked:
        alive = feasible(alive, lane, road.grade.crossing)
        if not alive:
            return False
    return True


def line(road: Road) -> Optional[List[int]]:
    """One press a tick that gets the car to the far end, or ``None``.

    Breadth-first over the same states :func:`feasible` walks, keeping
    a parent so the presses can be read back. Every road
    :func:`generate` hands out has one; the ``None`` is for roads
    written by hand, which the tests do.
    """
    crossing = road.grade.crossing
    start = (road.start, 0)
    seen: List[Dict[Tuple[int, int], Tuple[Optional[Tuple[int, int]], int]]]
    seen = [{start: (None, HOLD)}]
    for lane in road.blocked:
        step: Dict[Tuple[int, int], Tuple[Optional[Tuple[int, int]], int]] = {}
        for state in seen[-1]:
            at, owed_in = state
            choices = ([(owed_in, HOLD)] if owed_in
                       else [(0, HOLD), (crossing, SWITCH)])
            for owed, port in choices:
                covers = LANES if owed else (at,)
                if lane is not None and lane in covers:
                    continue
                if owed:
                    owed -= 1
                    below = (1 - at if not owed else at, owed)
                else:
                    below = (at, 0)
                step.setdefault(below, (state, port))
        if not step:
            return None
        seen.append(step)
    state = next(iter(seen[-1]))
    presses: List[int] = []
    for step_index in range(len(road.blocked), 0, -1):
        state, port = seen[step_index][state]
        presses.append(port)
    presses.reverse()
    return presses


def dodge(road: Road, look: int) -> List[int]:
    """Swerve when the sub-row *look* ahead blocks the lane, played out.

    One policy with one number in it, and the number is the whole
    difference between playing this task and failing it.

    ``look = grade.crossing`` is **aimed**: the press is thrown at the
    sub-row the swerve will actually land on. Measured over two hundred
    deals a rung, it clears every road on every rung — which is a claim
    about the *generator* as much as about the policy, and the reason is
    worth having in one place. :func:`generate` refuses any donkey that
    would empty the surviving states, and with a two-row swerve that
    refusal bites hard: one donkey pins the car in the far lane until a
    whole crossing's worth of clear road has gone by, so the only donkey
    the generator will accept before then is another one in the lane the
    car has already left. What is left is a road on which aiming at the
    swerve is enough.

    So this task has **no planning depth**, and saying otherwise would
    have been the easy mistake to make about it. It was designed
    expecting the top rungs to need a line chosen several rows out, and
    the measurement says they do not.

    ``look = SUB`` is **reactive**: the dodge a person makes on sight,
    thrown a drawn row in front of the bonnet. It is also perfect for
    the first five rungs, because there the swerve is one row wide and
    the two policies are the same policy. From the sixth they come
    apart and it collapses. That gap **is** the task: not what to do,
    which is obvious, but how far ahead of the donkey to have already
    done it.
    """
    car = Car(road.start, road.grade.swerve)
    ends = road.ends
    presses: List[int] = []
    while not over(car, road):
        aim = car.at + look
        ahead = road.blocked[aim] if aim < road.length else None
        want = (SWITCH if not car.crossing and ahead is not None
                and ahead == car.lane else HOLD)
        steer(car, want)
        presses.append(want)
        beat(car, road, ends)
    return presses


def drive(road: Road, presses: Sequence[int]) -> Car:
    """Run *presses* down *road* and hand back the car that comes out."""
    car = Car(road.start, road.grade.swerve)
    ends = road.ends
    for port in presses:
        if over(car, road):
            break
        steer(car, port)
        beat(car, road, ends)
    return car


# --- the deal ------------------------------------------------------------

def build(grade: Grade, beasts: Sequence[Tuple[int, int]],
          start: int = 0) -> Road:
    """A road from a list of ``(first blocked sub-row, lane)`` donkeys."""
    blocked: List[Optional[int]] = [None] * (grade.rows * SUB)
    for at, lane in beasts:
        for step in range(SPAN):
            if 0 <= at + step < len(blocked):
                blocked[at + step] = lane
    return Road(grade=grade, blocked=tuple(blocked),
                beasts=tuple(beasts), start=start)


def generate(level: int, seed: int = 0) -> Road:
    """Lay one road for *level*. Deterministic in *seed*, and passable.

    Sub-rows are laid one at a time and a donkey goes down only where
    the surviving car states stay non-empty for the whole of the
    :data:`SPAN` it would block. That is not a filter over finished
    roads and it is cheaper than one: refusing the donkey is always
    available, so the road is passable at every prefix and therefore
    passable at the end.

    A road with no donkeys on it would be a free verdict, so if the
    dice never called for one, one is put where it fits.
    """
    grade = GRADES[max(0, min(len(GRADES) - 1, level - 1))]
    rng = random.Random(seed)
    start = rng.choice(LANES)
    crossing = grade.crossing
    length = grade.rows * SUB
    blocked: List[Optional[int]] = [None] * length
    beasts: List[Tuple[int, int]] = []
    alive = states(start)
    # The dice are asked once a sub-row for a rate written per row, so
    # a rung's density still reads as "donkeys a row" -- give or take
    # the road each one takes up behind it.
    chance = grade.density / float(SUB)
    free_from = RUN_IN * SUB
    for at in range(length):
        if (blocked[at] is None and at >= free_from and at + SPAN <= length
                and rng.random() < chance):
            wanted = rng.choice(LANES)
            for lane in (wanted, 1 - wanted):
                if _room_for(alive, lane, crossing):
                    for step in range(SPAN):
                        blocked[at + step] = lane
                    beasts.append((at, lane))
                    free_from = at + SPAN + GAP
                    break
        alive = feasible(alive, blocked[at], crossing)
    if not beasts:
        _one_donkey(blocked, beasts, grade, start)
    return Road(grade=grade, blocked=tuple(blocked), beasts=tuple(beasts),
                start=start)


def _room_for(alive: frozenset, lane: int, crossing: int) -> bool:
    """Would a donkey here leave the car anywhere to be?"""
    for _step in range(SPAN):
        alive = feasible(alive, lane, crossing)
        if not alive:
            return False
    return True


def _one_donkey(blocked: List[Optional[int]], beasts: List[Tuple[int, int]],
                grade: Grade, start: int) -> None:
    """Put a single donkey on an empty road, in the first place it fits."""
    alive = states(start)
    for at in range(len(blocked) - SPAN):
        for lane in LANES:
            if at >= RUN_IN * SUB and _room_for(alive, lane, grade.crossing):
                for step in range(SPAN):
                    blocked[at + step] = lane
                beasts.append((at, lane))
                return
        alive = feasible(alive, blocked[at], grade.crossing)


# --- what the policies are worth -----------------------------------------

_SCORES: Dict[Tuple[int, int, str], float] = {}


def rehearse(level: int, deals: int = 200, seed: int = 0,
             policy: str = 'random') -> float:
    """The share of roads *policy* gets to the end of, measured.

    Four policies, and the number that matters is the gap between the
    middle two rather than any of them on its own:

    ``random``
        a coin a tick, and it clears **nothing** — zero on every rung,
        which is a floor worth understanding rather than quoting. A
        press starts a crossing that swallows the next few presses, so
        a coin leaves the car across the middle most of the time, and
        across the middle every donkey in either lane is a donkey in
        yours. Cutting the road into sub-rows is what made this
        degenerate: a coin a *row* still cleared about one road in eight
        on the first rung, because it spent most of its ticks settled.
    ``reactive``
        :func:`dodge` aimed one drawn row ahead — the swerve a person
        makes on sight of the donkey. Perfect while the swerve is one
        row wide, and almost worthless once it is two.
    ``aimed``
        :func:`dodge` aimed at the swerve. Clears every road on every
        rung, measured.
    ``exact``
        :func:`line`. One by construction, and here so the other three
        have something to be a share of.
    """
    key = (level, deals, policy)
    if key in _SCORES:
        return _SCORES[key]
    rng = random.Random(seed)
    home = 0
    for _deal in range(deals):
        road = generate(level, seed=rng.randrange(1 << 30))
        if policy == 'exact':
            presses = line(road) or []
        elif policy == 'aimed':
            presses = dodge(road, road.grade.crossing)
        elif policy == 'reactive':
            presses = dodge(road, SUB)
        else:
            presses = [rng.choice((HOLD, SWITCH))
                       for _step in range(road.length)]
        home += 1 if cleared(drive(road, presses), road) else 0
    _SCORES[key] = home / float(deals)
    return _SCORES[key]


__all__ = ['BEAST', 'CAR', 'GAP', 'GRADES', 'HOLD', 'LANES', 'RUN_IN', 'SPAN',
           'SUB', 'SWITCH', 'Car', 'Grade', 'Road', 'beat', 'body_of', 'build',
           'cleared', 'dodge', 'drive', 'feasible', 'generate', 'line', 'over',
           'rehearse', 'states', 'steer', 'survivable']
