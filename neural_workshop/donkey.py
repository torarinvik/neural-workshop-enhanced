# -*- coding: utf-8 -*-
"""Donkey's model: two lanes, one key, and a swerve you cannot take back.

The 1981 original is four hundred lines of BASIC and one idea. A car
runs up a two-lane road, donkeys stand in it, and the space bar puts
you in the other lane. Hit one and the round is over. That is the whole
game, and the whole of its difficulty was that the road got faster.

Speed is a **dial** here and not a rung, which is the one place this
departs from the original and it departs on purpose. One beat is one
step at the agent boundary, so a rung that ran the road faster would be
a rung a person feels and a learner cannot, and the two would be
playing different ladders while reporting the same number.

What replaces it is **the swerve**. Crossing takes
:attr:`Grade.swerve` rows and cannot be called off, and while the car
is across the middle it is in *both* lanes, so a donkey in either one
hits it. That single rule is what turns the classic into a task with
something in it:

* You cannot dodge at the last moment. The row a donkey arrives on is
  a row you must already be clear of, so the press has to come
  ``swerve`` rows early — which is exactly the opposite of what a
  reaction test rewards, and the reason this is not Reflex with a car.
* From the sixth rung the swerve is two rows wide and from the tenth
  three, so the press has to be thrown further and further in front of
  the thing it is aimed at. Measured over four hundred deals a rung,
  the swerve-on-sight dodge clears every road while the swerve is one
  row wide and 9%, 3%, 1%, 0% and 4% of them on rungs six to ten. The
  policy that aims at the swerve clears all of them.

What is **not** here is planning depth, and it is worth saying so
plainly because the task was built expecting it. Aiming the press at
the swerve is enough on every road this deals — see :func:`dodge` for
why the generator leaves nothing harder standing. The task is
anticipation and sustained attention, not a line chosen several rows
out, and a rung name is not evidence to the contrary.

That also means a road can be **unsurvivable**, and one that is would
be scored as a failure the player could not have avoided. So the road
is not generated and then checked: a donkey goes down only where the
set of surviving car states stays non-empty, which is
:func:`feasible` maintained as the road is laid. Every road this deals
has a line through it, and :func:`line` will hand it to you.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

#: What the one key does with a beat. Two, because the original had one
#: key: holding the wheel straight is not a null action here, it is the
#: other half of the choice.
HOLD, SWITCH = 0, 1

#: Lanes. Two, and it was always two.
LANES = (0, 1)

#: Rows of clear road before the first donkey may stand.
#:
#: Not politeness. The first thing a round asks is whether you were
#: looking, and a donkey on the row the car starts under would be
#: asking whether you had already pressed.
RUN_IN = 3


class Grade(NamedTuple):
    """One rung: how long the road is, how full, and how wide the swerve."""

    name: str
    rows: int           #: rows of road in one trial
    density: float      #: chance a row is offered a donkey
    swerve: int         #: rows the car spends crossing, committed

    @property
    def blind(self) -> int:
        """How far ahead a press has to be aimed, in rows.

        One on the early rungs, which a player can do by looking at the
        row in front of the bonnet. Two and up, and the row in front of
        the bonnet is no longer enough to decide by.
        """
        return self.swerve


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
    Grade('a clear road',             24,    0.10,      1),
    Grade('one at a time',            28,    0.18,      1),
    Grade('closer together',          32,    0.26,      1),
    Grade('a busy road',              36,    0.34,      1),
    Grade('the long haul',            48,    0.34,      1),
    Grade('the wide swerve',          36,    0.22,      2),
    Grade('wide and busy',            40,    0.30,      2),
    Grade('no room to think',         44,    0.38,      2),
    Grade('the long night',           56,    0.38,      2),
    Grade('three rows to cross',      56,    0.34,      3),
)


class Road(NamedTuple):
    """One trial's stretch of road, and the rung that dealt it."""

    grade: Grade
    #: One entry a row, from the row the car meets first: the lane a
    #: donkey stands in, or ``None`` for clear road. Both lanes are
    #: never blocked at once — that would be a wall, not a donkey.
    blocked: Tuple[Optional[int], ...]
    #: The lane the car starts in.
    start: int

    @property
    def donkeys(self) -> int:
        return sum(1 for lane in self.blocked if lane is not None)

    @property
    def length(self) -> int:
        return len(self.blocked)


class Car:
    """Where the car is, what it is in the middle of, and how it went."""

    __slots__ = ('lane', 'crossing', 'row', 'passed', 'hit', 'swerve')

    def __init__(self, lane: int = 0, swerve: int = 1) -> None:
        self.lane = lane
        #: Rows of the crossing still to run, this one included. Non-zero
        #: means the car is between lanes and a donkey in either one is
        #: a donkey in this one.
        self.crossing = 0
        self.row = 0            #: rows of road behind it
        self.passed = 0         #: donkeys it got by
        self.hit = False
        self.swerve = swerve

    @property
    def across(self) -> bool:
        return self.crossing > 0

    @property
    def covers(self) -> Tuple[int, ...]:
        """The lanes a donkey would have to stand in to be hit."""
        return LANES if self.crossing else (self.lane,)


# --- one beat ------------------------------------------------------------

def steer(car: Car, port: int) -> bool:
    """Take the press, if there is anything for it to do.

    A swerve already under way swallows the key. That is the whole of
    what makes the road a road rather than a quiz: the press commits
    the next :attr:`Grade.swerve` rows, and no second press buys them
    back.
    """
    if port != SWITCH or car.crossing:
        return False
    car.crossing = car.swerve
    return True


def beat(car: Car, road: Road) -> int:
    """One row of road arrives. Returns the donkeys got past, 0 or 1.

    Order matters and it is the same order the screen draws in: the
    press has already been taken, so the row that arrives is met by the
    car the press left behind. A swerve started this beat is across the
    middle for *this* row, which is why it cannot be a dodge.
    """
    if car.hit or car.row >= road.length:
        return 0
    lane = road.blocked[car.row]
    car.row += 1
    got = 0
    if lane is not None and lane in car.covers:
        car.hit = True
    elif lane is not None:
        car.passed += 1
        got = 1
    if car.crossing:
        car.crossing -= 1
        if not car.crossing:
            car.lane = 1 - car.lane
    return got


def over(car: Car, road: Road) -> bool:
    return car.hit or car.row >= road.length


def cleared(car: Car, road: Road) -> bool:
    """The round's verdict: the far end of the road, on four wheels."""
    return not car.hit and car.row >= road.length


# --- what survives -------------------------------------------------------

def states(start: int) -> frozenset:
    """The car states the road starts from: settled, in the start lane."""
    return frozenset({(start, 0)})


def feasible(alive: frozenset, lane: Optional[int], swerve: int) -> frozenset:
    """The states that survive a row blocked at *lane*, from *alive*.

    A pure function of the row, which is what lets the generator ask
    "may a donkey stand here?" without simulating anything: it may if
    what comes back is non-empty.

    The state is ``(lane, crossing)`` before the row: ``crossing`` rows
    of the swerve still owed, this row included. A settled car may hold
    or start a swerve; a crossing car has no say.
    """
    out = set()
    for at, crossing in alive:
        moves = [(at, crossing)] if crossing else [(at, 0), (at, swerve)]
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
        alive = feasible(alive, lane, road.grade.swerve)
        if not alive:
            return False
    return True


def line(road: Road) -> Optional[List[int]]:
    """One press a row that gets the car to the far end, or ``None``.

    Breadth-first over the same states :func:`feasible` walks, keeping
    a parent so the presses can be read back. Every road :func:`deal`
    hands out has one; the ``None`` is for roads written by hand, which
    the tests do.
    """
    swerve = road.grade.swerve
    start = (road.start, 0)
    seen: List[Dict[Tuple[int, int], Tuple[Optional[Tuple[int, int]], int]]]
    seen = [{start: (None, HOLD)}]
    for lane in road.blocked:
        step: Dict[Tuple[int, int], Tuple[Optional[Tuple[int, int]], int]] = {}
        for state in seen[-1]:
            at, crossing = state
            choices = ([(crossing, HOLD)] if crossing
                       else [(0, HOLD), (swerve, SWITCH)])
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
    for row in range(len(road.blocked), 0, -1):
        state, port = seen[row][state]
        presses.append(port)
    presses.reverse()
    return presses


def dodge(road: Road, look: int) -> List[int]:
    """Swerve when the row *look* ahead blocks the lane, played out.

    One policy with one number in it, and the number is the whole
    difference between playing this task and failing it.

    ``look = grade.swerve`` is **aimed**: the press is thrown at the row
    the swerve will actually land on. Measured over four hundred deals a
    rung, it clears every road on every rung — which is a claim about
    the *generator* as much as about the policy, and the reason is worth
    having in one place. :func:`generate` refuses any donkey that would
    empty the surviving states, and with a two-row swerve that refusal
    bites hard: one donkey pins the car in the far lane until two clear
    rows have gone by, so the only donkey the generator will accept
    before then is another one in the lane the car has already left.
    What is left is a road on which aiming at the swerve is enough.

    So this task has **no planning depth**, and saying otherwise would
    have been the easy mistake to make about it. It was designed
    expecting the top rungs to need a line chosen several rows out, and
    the measurement says they do not.

    ``look = 1`` is **reactive**: the dodge a person makes on sight,
    thrown at the row in front of the bonnet. It is also perfect for the
    first five rungs, because there the swerve is one row wide and the
    two policies are the same policy. From the sixth they come apart and
    it collapses — 9%, 3%, 1%, 0% and 4% of roads cleared on rungs six
    to ten, against a hundred for the aimed one. That gap **is** the
    task: not what to do, which is obvious, but how far ahead of the
    donkey to have already done it.
    """
    car = Car(road.start, road.grade.swerve)
    presses: List[int] = []
    while not over(car, road):
        aim = car.row + look
        ahead = road.blocked[aim] if aim < road.length else None
        want = (SWITCH if not car.crossing and ahead is not None
                and ahead == car.lane else HOLD)
        steer(car, want)
        presses.append(want)
        beat(car, road)
    return presses


def drive(road: Road, presses: Sequence[int]) -> Car:
    """Run *presses* down *road* and hand back the car that comes out."""
    car = Car(road.start, road.grade.swerve)
    for port in presses:
        if over(car, road):
            break
        steer(car, port)
        beat(car, road)
    return car


# --- the deal ------------------------------------------------------------

def generate(level: int, seed: int = 0) -> Road:
    """Lay one road for *level*. Deterministic in *seed*, and passable.

    Rows are laid one at a time and a donkey goes down only where the
    surviving car states stay non-empty. That is not a filter over
    finished roads and it is cheaper than one: refusing the donkey is
    always available, so the road is passable at every prefix and
    therefore passable at the end.

    A road with no donkeys on it would be a free verdict, so if the
    dice never called for one, one is put where it fits.
    """
    grade = GRADES[max(0, min(len(GRADES) - 1, level - 1))]
    rng = random.Random(seed)
    start = rng.choice(LANES)
    alive = states(start)
    blocked: List[Optional[int]] = []
    for row in range(grade.rows):
        lane: Optional[int] = None
        if row >= RUN_IN and rng.random() < grade.density:
            wanted = rng.choice(LANES)
            for tried in (wanted, 1 - wanted):
                if feasible(alive, tried, grade.swerve):
                    lane = tried
                    break
        blocked.append(lane)
        alive = feasible(alive, lane, grade.swerve)
    if not any(lane is not None for lane in blocked):
        blocked = _one_donkey(blocked, grade, start)
    return Road(grade=grade, blocked=tuple(blocked), start=start)


def _one_donkey(blocked: List[Optional[int]], grade: Grade,
                start: int) -> List[Optional[int]]:
    """Put a single donkey on an empty road, in the first place it fits."""
    alive = states(start)
    for row in range(len(blocked)):
        for lane in LANES:
            if row >= RUN_IN and feasible(alive, lane, grade.swerve):
                blocked[row] = lane
                return blocked
        alive = feasible(alive, blocked[row], grade.swerve)
    return blocked


# --- what the two policies are worth -------------------------------------

_SCORES: Dict[Tuple[int, int, str], float] = {}


def rehearse(level: int, deals: int = 200, seed: int = 0,
             policy: str = 'random') -> float:
    """The share of roads *policy* gets to the end of, measured.

    Four policies, and the number that matters is the gap between the
    middle two rather than any of them on its own:

    ``random``
        a coin a beat. The guessing floor the options screen quotes.
    ``reactive``
        :func:`dodge` aimed one row ahead — the swerve a person makes on
        sight of the donkey. Perfect while the swerve is one row wide,
        and under a tenth of the roads once it is two.
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
            presses = dodge(road, road.grade.swerve)
        elif policy == 'reactive':
            presses = dodge(road, 1)
        else:
            presses = [rng.choice((HOLD, SWITCH))
                       for _row in range(road.length)]
        home += 1 if cleared(drive(road, presses), road) else 0
    _SCORES[key] = home / float(deals)
    return _SCORES[key]


__all__ = ['GRADES', 'HOLD', 'LANES', 'RUN_IN', 'SWITCH', 'Car', 'Grade',
           'Road', 'beat', 'cleared', 'drive', 'feasible', 'generate',
           'dodge', 'line', 'over', 'rehearse', 'states', 'steer',
           'survivable']
