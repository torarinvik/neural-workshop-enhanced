# -*- coding: utf-8 -*-
"""Cookie Thief's model: momentum, and the cost of carrying it.

Nothing here draws anything. The task is one boy, one jar and one
doorway, and the whole of it is that **stopping takes longer than
starting wants it to**.

The physics is a speed rather than a counter. ``reach`` adds
:attr:`Grade.accel` to the boy's speed, ``freeze`` takes
:attr:`Grade.brake` off it, and every beat he eats whatever fraction of
a cookie his speed came to. So a fast thief earns faster and needs more
beats to stop, and the two are the same number: a rung is hard exactly
in the ratio between them.

There are two ways to be caught and they are meant to be different
skills.

*Reactive* — she is in the doorway and you have :attr:`Grade.warn`
beats before she is looking. A full-speed thief needs
:attr:`Grade.stopping` beats to halt, so the warning is enough or it is
not, and :attr:`Grade.reactive` says which. The first four rungs it is
enough. After that it never is again.

*Proactive* — she also comes when the jar is down far enough, and how
far is drawn on the jar as a band but never as a line. Under the band
she cannot come. Inside it she can come on any beat. So a thief who
waits to be told is already too late, and the only defence left is
having stopped before there was anything to react to.

The quota is what stops "never steal" from being a winning policy, and
the trigger band sits above it: stop on the quota and the count can
never call her. That is the whole target — arrive at exactly the number
you were asked for, with the momentum already spent.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

#: What a thief can do with a beat.
#:
#: Waiting is a real one and not padding. Freezing takes
#: :attr:`Grade.brake` off his speed and waiting takes only
#: :attr:`Grade.drag`, so the three of them are three different
#: accelerations and a thief who never waits cannot hold a speed. It is
#: handled by falling through :func:`press`, which is why it has no
#: branch of its own: pressing nothing *is* the action.
REACH, FREEZE, LUNGE, WAIT = 0, 1, 2, 3

#: Where the doorway is in a round.
AWAY, COMING, WATCHING, GONE = 'away', 'coming', 'watching', 'gone'

#: Who is in it. Only one of them ends the round.
MOTHER, SISTER, DOG = 'mother', 'sister', 'dog'

#: How long the golden cookie stays on the counter once it is offered.
GOLD_BEATS = 6

#: How far short of the quota it appears, counted in jar cookies. Four,
#: so that it is offered while he is still going flat out and stays on
#: the counter long enough to be taken later, on purpose, once he has
#: slowed down. Offered only at the end it would be free; offered only
#: at the start it would not be a temptation. The window is the choice.
GOLD_GAP = 4

#: What a cookie she saw costs, counted in cookies she did not.
#:
#: A cookie you got away with is worth one. A cookie she saw is worth
#: minus two — it was still a cookie, and then it cost you three. So a
#: haul is ``eaten - 3 * caught``, it goes negative on a bad round, and
#: greed pays for itself right up until it does not.
CAUGHT_COST = 3

#: Beats after a lunge in which freezing does nothing.
#:
#: This is the whole cost of the golden one, and the first design got it
#: wrong: it used to fling him to full speed, which is fatal that late
#: in a round whatever else he does, so the port was a button that was
#: never worth pressing and a learner's only job was to find that out
#: once. Locking the brakes instead makes it a question of *when* — take
#: it flat out and two unbraked beats are two cookies out of the jar you
#: cannot take back; wait until you are nearly stopped and it costs
#: almost nothing, but the window may close first.
GOLD_LOCK = 2

#: Beats of standing perfectly still, with something already taken and
#: nobody at the door, after which he gives it up and sneaks off.
#:
#: **Stopping is committing**, and that is the rule this constant is.
#: Without it a round that was decided at beat fifteen ran on to the
#: deadline anyway, which is eight seconds of a person watching a still
#: kitchen; with it, halting is the move that ends the round, so a
#: thief who stops one cookie short has chosen to stop one cookie short
#: rather than merely paused. He may start again inside the three
#: beats. After that the round is over and it is scored where he left
#: it.
SETTLE = 3


class Grade(NamedTuple):
    """One rung: how fast he starts, how slowly he stops, how much warning."""

    name: str
    quota: int          #: cookies the round asks for
    spread: int         #: how many cookies wide the band above it is
    accel: float        #: speed one reach adds
    brake: float        #: speed one freeze takes off
    drag: float         #: speed every beat takes off, whatever was pressed
    warn: int           #: beats between the doorway and her eyes
    visit: int          #: beats she stays once she is looking
    patience: int       #: earliest beat she walks in regardless
    slack: int          #: how much later than that she might
    gold: int           #: what the golden cookie is worth, 0 for none
    decoys: int         #: figures in the doorway who are not her

    @property
    def stopping(self) -> int:
        """Beats to halt from full speed."""
        return int(math.ceil(1.0 / (self.brake + self.drag)))

    @property
    def reflex_bites(self) -> int:
        """Cookies a flat-out thief still takes after she starts looking.

        He is going at full speed, he brakes the beat she appears in the
        doorway, and he brakes every beat after it. This counts what he
        gets anyway once her eyes are on him, with the crumb count taken
        at its worst — a cookie half out of the jar is a cookie.

        Simulated for the same reason :func:`stopping_bites` is: the
        physics is in one place, so this cannot drift away from it.
        """
        speed, crumbs = 1.0, 0.999
        for _beat in range(self.warn):
            speed = max(0.0, speed - self.brake)
            crumbs += speed
            if crumbs >= 1.0:
                crumbs -= 1.0
            speed = max(0.0, speed - self.drag)
        return stopping_bites(speed, crumbs, self)

    @property
    def reactive(self) -> bool:
        """Can a flat-out thief save himself on the warning alone?

        The one number that says what a rung is *about*. True and the
        rung tests noticing; false and noticing is not enough, and the
        rung is about not having been going that fast in the first
        place.

        It is not simply stopping distance against the warning, and that
        was the first version's mistake: what catches him is taking
        another *cookie*, not still drifting, so a thief who is down to
        a crawl when her eyes arrive is safe however long he takes to
        reach nothing.
        """
        return self.reflex_bites == 0

    @property
    def beats(self) -> int:
        """Hard cap on a round, so one always ends."""
        return self.patience + self.slack + self.warn + self.visit + 4


#: Ten rungs. Each adds one thing, and the thing it adds is in the name.
#:
#: **The warning only ever gets shorter.** It runs nine beats down to
#: one, a beat at a time, and takes its one double step between the
#: fifth rung and the sixth — because that is where it crosses what his
#: momentum still owes. Below that a thief can play by watching the
#: doorway; above it he cannot, ever again. See
#: :attr:`Grade.reflex_bites`, which is the crossing measured rather
#: than asserted, and note that it is *bites* rather than beats: what
#: catches him is taking another cookie, not still drifting.
GRADES: Tuple[Grade, ...] = (
    #     name                 quota spr accel brake  drag warn vis pat sl gold dec
    Grade('one cookie',            1,  3, 1.00, 1.00, 0.05,   9,  6, 14, 4,   0, 0),
    Grade('a handful',             3,  3, 0.50, 0.50, 0.05,   8,  6, 16, 4,   0, 0),
    Grade('he gets going',         5,  3, 0.34, 0.34, 0.04,   7,  6, 18, 5,   0, 0),
    Grade('hard to stop',          6,  3, 0.34, 0.20, 0.04,   6,  6, 20, 5,   0, 0),
    Grade('quieter feet',          7,  3, 0.34, 0.20, 0.04,   5,  6, 22, 5,   0, 0),
    Grade('the jar is watched',    8,  2, 0.25, 0.16, 0.03,   3,  7, 24, 6,   0, 0),
    Grade('she is just there',     8,  2, 0.25, 0.16, 0.03,   2,  7, 24, 6,   0, 0),
    Grade('the golden one',        9,  2, 0.25, 0.14, 0.03,   2,  7, 21, 5,   3, 0),
    Grade('someone at the door',  10,  2, 0.22, 0.12, 0.03,   1,  8, 23, 5,   3, 1),
    Grade('the kitchen at night', 12,  2, 0.20, 0.10, 0.03,   1,  8, 26, 6,   4, 2),
)


class Setup(NamedTuple):
    """One deal: everything hidden about the round, fixed before it starts."""

    grade: Grade
    #: Jar cookies that bring her. Drawn on the jar as a band, never as
    #: a line, so the thief knows the range and not the number.
    trigger: int
    #: The beat she walks in on regardless. Nothing on screen says when.
    deadline: int
    #: (beat, who) for each figure in the doorway who is not her.
    decoys: Tuple[Tuple[int, str], ...]


class Thief:
    """The boy, and what he has got away with so far."""

    __slots__ = ('speed', 'crumbs', 'jar', 'eaten', 'caught', 'beat',
                 'phase', 'who', 'until', 'gold_from', 'gold_taken', 'took',
                 'still', 'locked')

    def __init__(self) -> None:
        self.speed = 0.0
        self.crumbs = 0.0
        self.jar = 0            #: cookies out of the jar — what she counts
        self.eaten = 0          #: what they were worth — what the quota counts
        self.caught = 0         #: cookies taken while she was looking
        self.beat = 0
        self.phase = AWAY
        self.who: Optional[str] = None
        self.until = 0
        self.gold_from = -1     #: beat the golden cookie went on offer
        self.gold_taken = False
        self.took = 0           #: what the last beat was worth, for the screen
        self.still = 0          #: beats he has stood still with the goods
        self.locked = 0         #: beats the lunge has his brakes for

    @property
    def gold_on_offer(self) -> bool:
        return (self.gold_from >= 0 and not self.gold_taken
                and self.beat < self.gold_from + GOLD_BEATS)

    @property
    def moving(self) -> bool:
        return self.speed > 0.0


# --- the deal ------------------------------------------------------------

def generate(level: int, seed: int = 0) -> Setup:
    """Deal one round of *level*. Deterministic in *seed*."""
    grade = GRADES[max(0, min(len(GRADES) - 1, level - 1))]
    rng = random.Random(seed)
    trigger = grade.quota + 1 + rng.randrange(grade.spread)
    deadline = grade.patience + rng.randrange(grade.slack + 1)
    decoys: List[Tuple[int, str]] = []
    if grade.decoys:
        # Kept clear of each other and of the deadline, so a figure in
        # the doorway is always one figure and always resolves before
        # the next thing happens.
        gap = grade.warn + 2
        room = list(range(3, max(4, deadline - gap)))
        rng.shuffle(room)
        picked: List[int] = []
        for beat in room:
            if all(abs(beat - other) > gap for other in picked):
                picked.append(beat)
            if len(picked) == grade.decoys:
                break
        decoys = [(beat, rng.choice((SISTER, DOG))) for beat in sorted(picked)]
    return Setup(grade=grade, trigger=trigger, deadline=deadline,
                 decoys=tuple(decoys))


# --- one beat ------------------------------------------------------------

def press(thief: Thief, port: int, setup: Setup) -> bool:
    """Apply one action. Nothing else moves; the beat does that.

    Returns whether the action did anything, which is what the screen
    needs to say and what a lunge at nothing has to answer honestly.
    """
    grade = setup.grade
    if port == REACH:
        thief.speed = min(1.0, thief.speed + grade.accel)
        return True
    if port == FREEZE:
        if thief.locked:
            return False        # his hand is still out; there is no brake
        was = thief.speed
        thief.speed = max(0.0, thief.speed - grade.brake)
        return thief.speed != was
    if port == LUNGE and thief.gold_on_offer:
        # The golden one is on the counter rather than in the jar, so it
        # is worth cookies she never counts. What it costs is the reach:
        # for GOLD_LOCK beats afterwards he cannot stop.
        thief.gold_taken = True
        thief.eaten += grade.gold
        thief.locked = GOLD_LOCK
        return True
    return False


def beat(thief: Thief, setup: Setup) -> int:
    """One beat of the kitchen: the door moves, he eats, he tires.

    The order is the whole of the timing. The door moves **first**, so
    the beat she starts looking is a beat on which eating counts as
    caught; then he eats at whatever speed the action just set; then
    drag; and only then does the round ask whether what he has taken
    has brought her.
    """
    thief.beat += 1
    if thief.locked:
        thief.locked -= 1
    _door(thief, setup)
    took = _bite(thief, setup)
    thief.speed = max(0.0, thief.speed - setup.grade.drag)
    _knock(thief, setup)
    thief.still = (thief.still + 1
                   if not thief.moving and thief.jar and thief.phase == AWAY
                   else 0)
    thief.took = took
    return took


def _door(thief: Thief, setup: Setup) -> None:
    if thief.phase in (AWAY, GONE) or thief.beat < thief.until:
        return
    if thief.phase == COMING:
        if thief.who == MOTHER:
            thief.phase = WATCHING
            thief.until = thief.beat + setup.grade.visit
        else:
            thief.phase = AWAY
            thief.who = None
    elif thief.phase == WATCHING:
        thief.phase = GONE


def _bite(thief: Thief, setup: Setup) -> int:
    """At most one cookie a beat, because speed is capped at one."""
    thief.crumbs += thief.speed
    if thief.crumbs < 1.0:
        return 0
    thief.crumbs -= 1.0
    thief.jar += 1
    thief.eaten += 1
    if thief.phase == WATCHING:
        thief.caught += 1
    if (setup.grade.gold and thief.gold_from < 0
            and thief.jar >= setup.grade.quota - GOLD_GAP):
        thief.gold_from = thief.beat
    return 1


def _knock(thief: Thief, setup: Setup) -> None:
    """Does anybody arrive at the door this beat?

    She wins over a decoy, because a round in which the real one was
    hidden behind a false one is a round nobody could have played.
    """
    if thief.phase != AWAY:
        return
    if thief.jar >= setup.trigger or thief.beat >= setup.deadline:
        thief.phase = COMING
        thief.who = MOTHER
        thief.until = thief.beat + setup.grade.warn
        return
    for at, who in setup.decoys:
        if at == thief.beat:
            thief.phase = COMING
            thief.who = who
            thief.until = thief.beat + setup.grade.warn
            return


def over(thief: Thief, setup: Setup) -> bool:
    """She has been and gone, or he has, or the round ran out of beats."""
    return (thief.phase == GONE or thief.still >= SETTLE
            or thief.beat >= setup.grade.beats)


def cleared(thief: Thief, setup: Setup) -> bool:
    """The round's verdict: enough cookies, and not one of them seen."""
    return thief.eaten >= setup.grade.quota and thief.caught == 0


def haul(thief: Thief) -> int:
    """What the round was worth, which is not the same as whether it was won.

    The verdict is a bar — the quota, cleanly — and it is what the
    agent boundary can pay, because a colour is one bit. The haul is the
    margin, and it is what a person plays for: every cookie counts,
    including the ones past the quota, and every cookie she saw costs
    :data:`CAUGHT_COST`.

    Having both is deliberate. With only the bar, a cookie past the
    quota was worth exactly nothing and the game ended at the moment it
    got interesting. With only the haul there is no such thing as
    getting away with it. The bar says whether you got out; the haul
    says what you got out with.
    """
    return thief.eaten - CAUGHT_COST * thief.caught


# --- what a thief can work out from the screen ---------------------------

def stopping_bites(speed: float, crumbs: float, grade: Grade,
                   locked: int = 0) -> int:
    """Cookies still to come if he starts stopping now.

    Simulated rather than solved, because it has to agree with
    :func:`beat` exactly and a closed form would agree with it only
    until one of them was edited. *locked* is the lunge: that many beats
    at the front on which the brake does nothing.
    """
    got = 0
    guard = 0
    while speed > 0.0 and guard < 400:
        guard += 1
        if locked:
            locked -= 1
        else:
            speed = max(0.0, speed - grade.brake)
        crumbs += speed
        if crumbs >= 1.0:
            crumbs -= 1.0
            got += 1
        speed = max(0.0, speed - grade.drag)
    return got


def _rest(thief: Thief, grade: Grade) -> int:
    return stopping_bites(thief.speed, thief.crumbs, grade, thief.locked)


def landing(thief: Thief, grade: Grade) -> int:
    """What he ends up having eaten if he starts stopping now.

    Everything in it is on the screen: the row of pips, the boy's speed,
    and the rung's own numbers. Nothing about the trigger, the deadline
    or the decoys goes into it, which is what makes it safe to shape
    with — it says how far the momentum still has to run, and nothing
    at all about when she is coming.
    """
    return thief.eaten + _rest(thief, grade)


def jar_landing(thief: Thief, grade: Grade) -> int:
    """Where the *jar* ends up if he starts stopping now.

    The same number counted the way she counts it, which differs from
    :func:`landing` by whatever the golden one was worth.
    """
    return thief.jar + _rest(thief, grade)


def alarming(thief: Thief) -> bool:
    """Is the one who ends rounds actually in the room or the doorway?"""
    return thief.who == MOTHER and thief.phase in (COMING, WATCHING)


# --- what guessing is worth ----------------------------------------------

_FLOOR: Dict[Tuple[int, int], float] = {}


def rehearse(level: int, deals: int = 400, seed: int = 0,
             ports: Sequence[int] = (REACH, FREEZE, LUNGE)) -> float:
    """The share of rounds a run of random presses clears.

    Measured rather than derived, because there is nothing to derive:
    the floor here is whatever a random walk in speed happens to eat
    before somebody walks in, and that is a simulation question.
    """
    key = (level, deals)
    if key in _FLOOR:
        return _FLOOR[key]
    rng = random.Random(seed)
    won = 0
    for deal in range(deals):
        setup = generate(level, seed=rng.randrange(1 << 30))
        thief = Thief()
        while not over(thief, setup):
            press(thief, rng.choice(ports), setup)
            beat(thief, setup)
        won += 1 if cleared(thief, setup) else 0
    _FLOOR[key] = won / float(deals)
    return _FLOOR[key]


__all__ = ['AWAY', 'CAUGHT_COST', 'COMING', 'DOG', 'FREEZE', 'WAIT', 'GOLD_BEATS', 'GOLD_GAP',
           'GONE', 'GRADES', 'LUNGE', 'MOTHER', 'REACH', 'SETTLE', 'SISTER',
           'GOLD_LOCK', 'Setup', 'Thief', 'WATCHING', 'alarming', 'beat',
           'cleared', 'generate', 'haul', 'jar_landing', 'landing', 'over',
           'press', 'rehearse', 'stopping_bites']
