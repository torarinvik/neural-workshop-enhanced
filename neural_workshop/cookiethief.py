# -*- coding: utf-8 -*-
"""Cookie Thief's model: one cookie a press, and one press too many.

Nothing here draws anything. The boy stands **at** the jar with his hand
already over it. A press takes one cookie, now: it is in the count on
the beat you asked for it and his hand is back at his side on the same
beat. There is no run-up and nothing to wait out.

What there is instead is **the door**, and it only ever opens.

Every cookie leaves a gap she would notice on its own — that is
:attr:`Grade.notice`, and it never comes back. Taking them quickly is
noisy on top of that, :attr:`Grade.opening` a grab, and that part dies
away at :attr:`Grade.settling` a quiet beat. So the door is two things
added together: a floor that rises with the jar and never falls, and a
spike that rises with the pace and does. Both are drawn.

She comes the first beat the door reaches a number nobody is told. All
anybody is told is the range it is in, which is shaded on the door. So
the fatal grab is the one that opens the door far enough — and it is
that grab she walks in on. Under :attr:`Grade.warn` beats of warning
there is still time to get out; from the sixth rung there is no warning
to get out under.

That leaves four things to do with a beat and all four are worth doing.
Grab. Wait, which lets the noise die down and so buys the grab after
next. **Leave**, which banks what you have and ends the round — the
only move that cannot go wrong and the only one that stops you earning.
And reach for the golden one, which is two beats you cannot take back.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

#: What a thief can do with a beat. Every one of them is worth doing.
#:
#: Waiting is not padding here and neither is leaving. Waiting is how
#: the noise a fast hand makes dies down, so it is what buys the grab
#: after next; leaving is the only move that cannot go wrong and the
#: only one that stops the count going up.
GRAB, LEAVE, LUNGE, WAIT = 0, 1, 2, 3

#: Where the doorway is in a round.
AWAY, COMING, WATCHING, GONE = 'away', 'coming', 'watching', 'gone'

#: Who is in it. Only one of them ends the round.
MOTHER, SISTER, DOG = 'mother', 'sister', 'dog'

#: The door reading below which she never comes, whatever else is true.
#:
#: A hundred because the door is drawn as one, and a number a player can
#: read as a percentage is a number they can do arithmetic with while
#: the beat is running.
SAFE = 100

#: How long the golden cookie stays on the counter once it is offered.
GOLD_BEATS = 6

#: How far short of the quota it is offered, in cookies out of the jar.
GOLD_GAP = 3

#: Beats a reach for the golden one takes, both of them committed.
#:
#: The only lag in the task, and it is deliberate rather than left over.
#: An ordinary grab is instant; the golden one is two beats in which he
#: can neither grab nor leave. A temptation is supposed to cost
#: something, and what this one costs is the ability to change your mind.
GOLD_REACH = 2

#: What a grab she saw costs, counted in cookies she did not see.
#:
#: A cookie you got away with is worth one; a grab she saw costs two on
#: top of whatever it yielded. So a haul goes negative on a bad round,
#: and — the part that took measuring — a grab into the shaded zone is
#: worth taking exactly while the chance of it bringing her is under one
#: in three. It was three for a while, which put that line at one in
#: four, and one in four is finer than a grab can be aimed: the greed
#: dial had its best setting at zero and the shaded zone was decoration.
CAUGHT_COST = 2

#: Beats of standing there doing nothing, with something already taken
#: and nobody at the door, after which he gives it up and sneaks off.
#:
#: Leaving is a key, so this is only the lazy way of pressing it. It is
#: here so that a round always ends, and so that a thief who has stopped
#: is not left standing in a kitchen nothing further can happen in.
#:
#: **Letting the noise die down is not doing nothing**, so a beat spent
#: waiting with the pace still above zero does not count towards it.
#: Without that clause the rule fought the game: waiting is how a fast
#: hand buys its next grab, and four quiet beats is exactly what the top
#: rungs need after a run of them, so the thief walked off in the middle
#: of the plan and came in one cookie short of the quota on every rung
#: above the sixth.
SETTLE = 4


class Grade(NamedTuple):
    """One rung: how much she lets you take, and how fast you may take it."""

    name: str
    quota: int          #: cookies the round asks for
    notice: int         #: door the jar gains per cookie, and never loses
    opening: int        #: door a grab adds on top, for being quick about it
    settling: int       #: door a quiet beat takes back off that
    spread: int         #: how wide the range she might come in is
    warn: int           #: beats between the doorway and her eyes
    visit: int          #: beats she stays once she is looking
    patience: int       #: earliest beat she walks in regardless
    slack: int          #: how much later than that she might
    gold: int           #: what the golden cookie is worth, 0 for none
    decoys: int         #: figures in the doorway who are not her

    @property
    def limit(self) -> int:
        """The door reading she certainly comes at."""
        return SAFE + self.spread

    @property
    def room(self) -> int:
        """Cookies he can take without ever hurrying, at worst.

        A quiet beat takes the noise back off but never the gap in the
        jar, so this is the hard ceiling on a round however patient
        anybody is. It has to be at least the quota, or the rung is
        asking for something it does not have.
        """
        return max(0, (SAFE - 1 - self.opening) // self.notice)

    @property
    def reactive(self) -> bool:
        """Is there anything to react to at all?

        True and the rung can be played by watching the doorway: she
        stands in it for :attr:`warn` beats before her eyes are on the
        jar, and one press of *leave* inside that window costs nothing.
        False and the grab that brings her is a grab she is already
        looking at, so the only defence left is having stopped before
        there was anything to see.
        """
        return self.warn > 0


#: Ten rungs. Each adds one thing, and the thing it adds is in the name.
#:
#: **The warning only ever gets shorter**, six beats down to none, and
#: it runs out for good at the sixth rung. Below that a thief can play
#: by watching the doorway. Above it the door is the only warning there
#: is, and it is a range rather than a number.
GRADES: Tuple[Grade, ...] = (
    #     name                 quota not open sett sprd warn vis pat sl gold dec
    Grade('one cookie',            1,  8,   0,  40,  60,   6,  5, 26, 6,   0, 0),
    Grade('a handful',             4,  8,   0,  40,  60,   5,  5, 26, 6,   0, 0),
    Grade('quick hands',           7,  6,   4,  24,  55,   4,  5, 30, 6,   0, 0),
    Grade('she is listening',      9,  6,   5,  22,  50,   3,  6, 32, 6,   0, 0),
    Grade('quieter feet',         11,  5,   5,  20,  48,   2,  6, 34, 6,   0, 0),
    Grade('no warning at all',    11,  5,   5,  20,  46,   0,  6, 34, 6,   0, 0),
    Grade('she is quick',         12,  5,   6,  18,  42,   0,  7, 36, 6,   0, 0),
    Grade('the golden one',       12,  5,   6,  18,  40,   0,  7, 36, 5,   6, 0),
    Grade('someone at the door',  13,  5,   7,  16,  36,   0,  8, 38, 5,   6, 1),
    Grade('the kitchen at night', 14,  5,   8,  14,  30,   0,  8, 40, 5,   8, 2),
)


class Setup(NamedTuple):
    """One deal: everything hidden about the round, fixed before it starts."""

    grade: Grade
    #: The door reading that brings her. Shaded on the door as a range
    #: and never marked as a line, so a thief knows how far in he is and
    #: not which grab is the one.
    trigger: int
    #: The beat she walks in on regardless. Nothing on screen says when.
    deadline: int
    #: (beat, who) for each figure in the doorway who is not her.
    decoys: Tuple[Tuple[int, str], ...]


class Thief:
    """The boy at the jar, and what he has got away with so far."""

    __slots__ = ('jar', 'eaten', 'caught', 'pace', 'beat', 'phase', 'who',
                 'until', 'gold_from', 'gold_taken', 'reaching', 'took',
                 'noisy', 'seen', 'left', 'still')

    def __init__(self) -> None:
        self.jar = 0            #: cookies out of the jar — the door's floor
        self.eaten = 0          #: what they were worth — what the quota counts
        self.caught = 0         #: grabs she had her eyes on
        self.pace = 0           #: the noisy part of the door
        self.beat = 0
        self.phase = AWAY
        self.who: Optional[str] = None
        self.until = 0
        self.gold_from = -1     #: beat the golden cookie went on offer
        self.gold_taken = False
        self.reaching = 0       #: beats of the golden reach still to run
        self.took = 0           #: cookies this beat was worth, for the screen
        self.noisy = False      #: was his hand over the jar this beat
        self.seen = False       #: did she have her eyes on it, this beat
        self.left = False       #: he walked off with it
        self.still = 0          #: beats he has stood there doing nothing

    @property
    def gold_on_offer(self) -> bool:
        return (self.gold_from >= 0 and not self.gold_taken
                and self.beat < self.gold_from + GOLD_BEATS)

    @property
    def committed(self) -> bool:
        """Mid-reach for the golden one: no grabbing and no leaving."""
        return self.reaching > 0


# --- the door ------------------------------------------------------------

def door(thief: Thief, grade: Grade) -> int:
    """How far open it is: the jar's floor plus the noise on top.

    The whole of the risk, and every term in it is on the screen. The
    floor is the cookies already gone and it never falls; the noise is
    how quick he has been about it, and that does.
    """
    return thief.jar * grade.notice + thief.pace


def floor_of(thief: Thief, grade: Grade) -> int:
    """The part of the door no quiet beat can take back."""
    return thief.jar * grade.notice


def after_a_grab(thief: Thief, grade: Grade) -> int:
    """What the door would read if he took one right now.

    Everything in it is drawn. Nothing about the trigger, the deadline
    or the decoys goes into it, which is what makes it safe to shape
    with: it says how far one more cookie would open the door, and
    nothing at all about where she is.
    """
    return door(thief, grade) + grade.notice + grade.opening


def certain(thief: Thief, grade: Grade) -> bool:
    """Is one more grab bound to bring her, rather than merely likely?"""
    return after_a_grab(thief, grade) >= grade.limit


def safe(thief: Thief, grade: Grade) -> bool:
    """Is one more grab certain *not* to bring her?"""
    return after_a_grab(thief, grade) < SAFE


# --- the deal ------------------------------------------------------------

def generate(level: int, seed: int = 0) -> Setup:
    """Deal one round of *level*. Deterministic in *seed*."""
    grade = GRADES[max(0, min(len(GRADES) - 1, level - 1))]
    rng = random.Random(seed)
    trigger = SAFE + rng.randrange(grade.spread)
    deadline = grade.patience + rng.randrange(grade.slack + 1)
    decoys: List[Tuple[int, str]] = []
    if grade.decoys:
        # Kept clear of each other, so a figure in the doorway is always
        # one figure and always resolves before the next thing happens.
        gap = max(1, grade.warn) + 2
        room = list(range(3, max(4, deadline - gap)))
        rng.shuffle(room)
        picked: List[int] = []
        for at in room:
            if all(abs(at - other) > gap for other in picked):
                picked.append(at)
            if len(picked) == grade.decoys:
                break
        decoys = [(at, rng.choice((SISTER, DOG))) for at in sorted(picked)]
    return Setup(grade=grade, trigger=trigger, deadline=deadline,
                 decoys=tuple(decoys))


# --- one beat ------------------------------------------------------------

def press(thief: Thief, port: int, setup: Setup) -> bool:
    """Do the thing, now. Whether it was seen is the beat's business.

    A grab lands here: the cookie is in the count on the beat it was
    asked for and his hand is back at his side. Nothing is queued and
    nothing is in flight, which is the difference between this and every
    earlier version of the task — there is one thing a thief can be
    wrong about and it is *whether* to press, never *when* the press
    will arrive.
    """
    grade = setup.grade
    if thief.committed:
        # Both hands at the back of the counter. This is the whole cost
        # of the golden one and it is why it is worth anything.
        return False
    if port == GRAB:
        thief.jar += 1
        thief.eaten += 1
        thief.pace += grade.opening
        thief.took = 1
        thief.noisy = True
        if (grade.gold and thief.gold_from < 0
                and thief.jar >= grade.quota - GOLD_GAP):
            thief.gold_from = thief.beat
        return True
    if port == LEAVE:
        thief.left = True
        return True
    if port == LUNGE and thief.gold_on_offer:
        thief.gold_taken = True
        thief.reaching = GOLD_REACH
        thief.pace += grade.opening
        thief.noisy = True
        return True
    return False


def beat(thief: Thief, setup: Setup) -> int:
    """One beat of the kitchen: the door moves, and she may be behind it.

    The order is the whole of the timing. Whatever he did has already
    happened — :func:`press` did it — so the door is asked *after* the
    grab, and she arrives on the grab that opened it. That is what makes
    the fatal press the press itself rather than the one after it, and
    it is why a rung with no warning cannot be played by watching.
    """
    grade = setup.grade
    thief.beat += 1
    if thief.reaching:
        thief.reaching -= 1
        thief.pace += grade.opening
        thief.noisy = True
        if not thief.reaching:
            thief.eaten += grade.gold
            thief.took = grade.gold
    _figure(thief, setup)
    _arrive(thief, setup)
    thief.seen = thief.phase == WATCHING and thief.noisy
    if thief.seen:
        thief.caught += 1
    # Asked *before* the noise is taken off rather than after, so the
    # beat that finishes clearing it is a beat that did something. It is
    # the beat after that one, the first with nothing left to settle,
    # that starts counting as standing there.
    idle = (not thief.noisy and not thief.pace and thief.jar
            and thief.phase == AWAY)
    if not thief.noisy:
        thief.pace = max(0, thief.pace - grade.settling)
    thief.still = thief.still + 1 if idle else 0
    took, thief.took = thief.took, 0
    thief.noisy = False
    return took


def _figure(thief: Thief, setup: Setup) -> None:
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


def _arrive(thief: Thief, setup: Setup) -> None:
    """Does anybody arrive this beat?

    She wins over a decoy, because a round in which the real one was
    hidden behind a false one is a round nobody could have played.

    With no warning she does not stand in the doorway first: she is
    looking on the beat she arrives, and the grab that opened the door
    that far is one she saw.
    """
    if thief.phase != AWAY:
        return
    grade = setup.grade
    if door(thief, grade) >= setup.trigger or thief.beat >= setup.deadline:
        thief.who = MOTHER
        if grade.warn:
            thief.phase = COMING
            thief.until = thief.beat + grade.warn
        else:
            thief.phase = WATCHING
            thief.until = thief.beat + grade.visit
        return
    for at, who in setup.decoys:
        if at == thief.beat:
            thief.phase = COMING
            thief.who = who
            # Visible for a beat even on the rungs with no warning at
            # all, or there would be nothing to tell apart.
            thief.until = thief.beat + max(1, grade.warn)
            return


def beats_of(grade: Grade) -> int:
    """Hard cap on a round, so one always ends."""
    return (grade.patience + grade.slack + max(1, grade.warn)
            + grade.visit + 4)


def over(thief: Thief, setup: Setup) -> bool:
    """He left, she has been and gone, or the round ran out of beats."""
    return (thief.left or thief.phase == GONE or thief.still >= SETTLE
            or thief.beat >= beats_of(setup.grade))


def cleared(thief: Thief, setup: Setup) -> bool:
    """The round's verdict: enough cookies, and not one grab seen."""
    return thief.eaten >= setup.grade.quota and thief.caught == 0


def haul(thief: Thief) -> int:
    """What the round was worth, which is not whether it was won.

    The verdict is a bar — the quota, cleanly — and it is what the agent
    boundary can pay, because a colour is one bit. The haul is the
    margin, and it is what a person plays for: every cookie counts,
    including the ones past the quota, and every grab she saw costs
    :data:`CAUGHT_COST`.

    Having both is deliberate. With only the bar, a cookie past the
    quota was worth exactly nothing and the round ended at the moment it
    got interesting. With only the haul there is no such thing as
    getting away with it.
    """
    return thief.eaten - CAUGHT_COST * thief.caught


# --- what guessing is worth ----------------------------------------------

_FLOOR: Dict[Tuple[int, int], float] = {}


def rehearse(level: int, deals: int = 400, seed: int = 0,
             ports: Sequence[int] = (GRAB, LEAVE, LUNGE, WAIT)) -> float:
    """The share of rounds a run of random presses gets away clean.

    Measured rather than derived, because there is nothing to derive:
    the floor here is whatever a random hand happens to take before the
    door is open far enough, and that is a simulation question.
    """
    key = (level, deals)
    if key in _FLOOR:
        return _FLOOR[key]
    rng = random.Random(seed)
    won = 0
    for _deal in range(deals):
        setup = generate(level, seed=rng.randrange(1 << 30))
        thief = Thief()
        while not over(thief, setup):
            press(thief, rng.choice(ports), setup)
            beat(thief, setup)
        won += 1 if cleared(thief, setup) else 0
    _FLOOR[key] = won / float(deals)
    return _FLOOR[key]


__all__ = ['AWAY', 'CAUGHT_COST', 'COMING', 'DOG', 'GOLD_BEATS', 'GOLD_GAP',
           'GOLD_REACH', 'GONE', 'GRAB', 'GRADES', 'LEAVE', 'LUNGE', 'MOTHER',
           'SAFE', 'SETTLE', 'SISTER', 'Setup', 'Thief', 'WAIT', 'WATCHING',
           'after_a_grab', 'beat', 'beats_of', 'certain', 'cleared', 'door',
           'floor_of', 'generate', 'haul', 'over', 'press', 'rehearse', 'safe']
