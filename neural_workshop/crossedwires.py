# -*- coding: utf-8 -*-
"""Crossed Wires: the keys do something, but not what they say.

A marker on a wrapped-round grid, a target to reach, and a handful of
keys. Each key moves the marker one cell in some fixed direction — but
which key goes which way is scrambled, and nothing on screen says how.
The only way to find out is to press one and watch.

Every other task in the workshop hands the player all the information
it is ever going to give and then asks what follows from it. This one
does not: the information does not exist until the player goes and
makes some. That is the faculty it is for, and it is why none of the
usual tricks apply. There is nothing to read off the frame, nothing to
recall from earlier, and no amount of thinking between presses buys
anything at all — the answer is only available to somebody willing to
spend a move to find it out.

Which is the whole design. Presses are budgeted. A round gives about
as many as the distance to the targets demands and a little over, so a
player who probes every key before committing has spent its slack
before it starts, and a player who commits without probing walks the
wrong way. Neither pure exploring nor pure exploiting clears a rung;
the task is the trade between them, made move by move without ever
being able to see what the trade is worth.

Four things follow from that and each is measured rather than claimed:

* Pressing at random is not enough. On a wrapped grid a random walk
  does stumble onto a target eventually, so the floor here is a real
  number rather than a zero, and :func:`play_random` is the thing that
  measures it.

* The rungs are clearable. :func:`play_oracle` plays a round already
  knowing the wiring, and every rung's budget is set so that it
  clears: measured, it takes every target on every rung but the top
  two, where it misses about two targets in ten thousand. It is a
  greedy player rather than an optimal one — it walks the way that
  shortens the gap most and does not plan around the key that is
  about to die — so that last tenth of a percent is its greed and not
  the budget. A rung nobody can pass would be a broken rung; this is
  not one.

* Learning while moving is worth doing, and :func:`play_learner` is
  what does it: press an unknown key when nothing known helps, trust
  what you saw last, and go the way that shortens the gap. The space
  between it and the oracle is what a rung is actually asking for.

* And the wiring does not sit still. The top rungs turn it every so
  many presses and let a key die partway through, both silently. A
  player who identifies the wiring once and then trusts it forever is
  the foil, and ``play_learner(relearn=False)`` plays it — the drift
  rungs exist precisely to separate the two.

The grid wraps deliberately. A bounded arena would make a press into
the wall look exactly like a press on a dead key, and an ambiguity
between "this key does nothing" and "this key does something I cannot
do from here" is a muddle rather than a difficulty. On a torus every
press moves, so every press is evidence.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

#: The eight ways, clockwise from north, on a grid whose y grows
#: upwards. Rungs with four keys use every other one, so that the four
#: are the square directions and not a lopsided half of the ring.
WAYS: Tuple[Tuple[int, int], ...] = (
    (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1))

#: How the wiring may be scrambled, hardest last. A turn is the whole
#: ring rotated; a mirror is it reflected, which is a different animal
#: — reflections cannot be undone by leaning the way rotations can;
#: and crossed is any permutation at all.
STEADY, TURNED, MIRRORED, CROSSED = 'steady', 'turned', 'mirrored', 'crossed'
FAMILIES: Tuple[str, ...] = (STEADY, TURNED, MIRRORED, CROSSED)

#: What a dead key is wired to.
DEAD = -1


class Grade(NamedTuple):
    """One rung of the ladder: the keys, the grid, and the budget."""

    name: str
    #: Keys to play with, and so directions to tell apart: four or
    #: eight. Eight is not merely twice as many — the ring of possible
    #: wirings goes from twenty-four to forty thousand.
    keys: int
    family: str
    across: int
    down: int
    #: Targets to reach in a round, one after another.
    targets: int
    #: Presses allowed *beyond* what a player who already knew the
    #: wiring would spend. An absolute allowance rather than a
    #: multiple of the trip, because what identification costs does
    #: not grow with how far there is to walk — measured as a
    #: multiple, a longer round is an easier one, which is backwards.
    spare: int
    #: Presses between one silent turn of the whole wiring. Zero
    #: leaves it alone.
    drift: int = 0
    #: The press at which one key stops working, silently. Zero never.
    dies: int = 0


#: Kindergarten to superhuman. The first rung is a control condition —
#: the keys do exactly what they say — so that a player who cannot
#: clear it has a problem with the task and not with the wiring.
GRADES: Tuple[Grade, ...] = (
    #                       keys family    across down targets spare drift dies
    Grade('as marked',         4, STEADY,    11, 11,  3,  12,    0,   0),
    Grade('a quarter turn',    4, TURNED,    11, 11,  3,   8,    0,   0),
    Grade('through a mirror',  4, MIRRORED,  11, 11,  4,   5,    0,   0),
    Grade('crossed',           4, CROSSED,   13, 13,  4,   3,    0,   0),
    Grade('crossed tighter',   4, CROSSED,   13, 13,  5,   2,    0,   0),
    Grade('eight ways',        8, TURNED,    13, 13,  5,   6,    0,   0),
    Grade('eight crossed',     8, CROSSED,   13, 13,  5,   5,    0,   0),
    Grade('eight tighter',     8, CROSSED,   15, 15,  6,   4,    0,   0),
    Grade('the slow drift',    8, CROSSED,   15, 15,  6,   6,   25,   0),
    Grade('drifting',          8, CROSSED,   15, 15,  6,   6,   15,   0),
    Grade('inhuman',           8, CROSSED,   17, 17,  7,   5,    9,  25),
    Grade('superhuman',        8, CROSSED,   17, 17,  8,   6,    6,  20),
)


def pressure(grade: Grade) -> Tuple[int, int, int, int]:
    """Roughly how much a rung asks, for putting them in order.

    Two axes and one dial, so the ladder has to rank them rather than
    add them up: more keys outranks everything, because eight of them
    takes the wirings from twenty-four to forty thousand; then how
    often the ring turns, expressed as turns per hundred presses so
    that "never" sorts below "rarely" instead of above it; then the
    length of the trip and how little is spare.
    """
    return (grade.keys, 100 // grade.drift if grade.drift else 0,
            grade.targets, -grade.spare)


class Bout(NamedTuple):
    """One round: the grid, the wiring behind it, and what it allows."""

    grade: Grade
    #: Where the marker starts.
    start: Tuple[int, int]
    #: The targets, in the order they are asked for.
    goals: Tuple[Tuple[int, int], ...]
    #: Which way each key really goes, as an index into :data:`WAYS`.
    #: Never drawn and never hinted at.
    wiring: Tuple[int, ...]
    #: How far the ring turns, every ``grade.drift`` presses.
    turn: int
    #: Which key dies at ``grade.dies``, or ``-1`` when none does.
    dead: int
    #: Presses allowed for the whole round.
    budget: int
    #: What the trip would cost a player who already knew the wiring.
    shortest: int


# --- the grid ------------------------------------------------------------


def ways(keys: int) -> Tuple[Tuple[int, int], ...]:
    """The directions a rung with this many keys can move in."""
    return WAYS if keys == 8 else WAYS[::2]


def step(spot: Tuple[int, int], way: Tuple[int, int],
         across: int, down: int) -> Tuple[int, int]:
    """One move from *spot*, wrapped round the edges."""
    return ((spot[0] + way[0]) % across, (spot[1] + way[1]) % down)


def gap(here: Tuple[int, int], there: Tuple[int, int],
        across: int, down: int, keys: int) -> int:
    """Presses from *here* to *there* for a player who knew the wiring.

    Wrapped both ways, so the shorter way round always counts. With
    eight keys a diagonal covers both axes at once and the cost is the
    larger of the two; with four it is their sum.
    """
    side = min((here[0] - there[0]) % across, (there[0] - here[0]) % across)
    rise = min((here[1] - there[1]) % down, (there[1] - here[1]) % down)
    return max(side, rise) if keys == 8 else side + rise


def turned(wiring: Sequence[int], by: int, keys: int) -> Tuple[int, ...]:
    """*wiring* with every key's direction moved *by* round the ring."""
    return tuple(DEAD if way == DEAD else (way + by) % keys for way in wiring)


def wirings(family: str, keys: int, rng: random.Random) -> Tuple[int, ...]:
    """A wiring drawn from *family*.

    The families are nested — every turn is a permutation and so is
    every mirror — so this draws from the family named rather than
    from everything at or below it, which is what makes a rung's name
    mean something.
    """
    if family == STEADY:
        return tuple(range(keys))
    if family == TURNED:
        about = rng.randrange(1, keys)
        return tuple((key + about) % keys for key in range(keys))
    if family == MIRRORED:
        about = rng.randrange(keys)
        return tuple((about - key) % keys for key in range(keys))
    while True:
        crossed = list(range(keys))
        rng.shuffle(crossed)
        if any(crossed[key] != key for key in range(keys)):
            return tuple(crossed)


class Bench:
    """A round being played: where the marker is and what is left.

    Everything a player is allowed to know is here — where the marker
    is, where the target is, how many presses are left. What is *not*
    here, and is deliberately kept on the :class:`Bout` behind it, is
    the wiring.
    """

    def __init__(self, bout: Bout) -> None:
        self.bout = bout
        self.at = bout.start
        self.goal_at = 0
        self.presses = 0
        self.reached = 0
        self.wasted = 0

    # --- what the player may see -----------------------------------------

    def goal(self) -> Tuple[int, int]:
        """The target being asked for, or the last one once they are done."""
        return self.bout.goals[min(self.goal_at, len(self.bout.goals) - 1)]

    def left(self) -> int:
        return max(0, self.bout.budget - self.presses)

    def over(self) -> bool:
        return self.left() <= 0 or self.reached >= len(self.bout.goals)

    def gap(self) -> int:
        grade = self.bout.grade
        return gap(self.at, self.goal(), grade.across, grade.down, grade.keys)

    # --- what only the bench knows ---------------------------------------

    def wiring_now(self) -> Tuple[int, ...]:
        """The wiring as it stands, drift and dead key and all.

        Recomputed from the press count rather than mutated, so a
        round is a pure function of its :class:`Bout` and the keys
        pressed — which is what lets a test replay one exactly.
        """
        grade = self.bout.grade
        live = self.bout.wiring
        if grade.drift:
            live = turned(live, self.bout.turn * (self.presses // grade.drift),
                          grade.keys)
        if grade.dies and self.presses >= grade.dies and self.bout.dead >= 0:
            live = tuple(DEAD if key == self.bout.dead else way
                         for key, way in enumerate(live))
        return live

    def press(self, keyed: int) -> Tuple[int, int]:
        """Press one key. Returns the step the marker actually took."""
        if self.over() or not 0 <= keyed < self.bout.grade.keys:
            return (0, 0)
        grade = self.bout.grade
        wired = self.wiring_now()[keyed]
        went = (0, 0) if wired == DEAD else ways(grade.keys)[wired]
        was = self.gap()
        self.at = step(self.at, went, grade.across, grade.down)
        self.presses += 1
        if self.gap() >= was:
            self.wasted += 1
        if self.at == self.goal():
            self.reached += 1
            self.goal_at += 1
        return went


# --- players -------------------------------------------------------------


def play_random(bench: Bench, rng: random.Random) -> int:
    """Press keys at random until the budget runs out.

    The floor. On a wrapped grid this is not hopeless — a random walk
    does wander onto a target now and then — so what it scores has to
    be measured rather than assumed to be nothing.
    """
    while not bench.over():
        bench.press(rng.randrange(bench.bout.grade.keys))
    return bench.reached


def _ranked(bench: Bench) -> List[Tuple[int, int]]:
    """Every direction and what the gap would be after it, best first."""
    grade = bench.bout.grade
    scored = []
    for which, way in enumerate(ways(grade.keys)):
        moved = step(bench.at, way, grade.across, grade.down)
        scored.append((gap(moved, bench.goal(), grade.across, grade.down,
                           grade.keys), which))
    scored.sort()
    return scored


def helpful(bench: Bench) -> List[int]:
    """Only the directions that actually shorten the gap, best first.

    Sorting the ring and taking the better half is not the same
    thing and is worth less: when the marker is already level with the
    target on one axis, half the ring is a step backwards, and a
    player that treats "less bad" as "good" spends its budget going
    sideways.
    """
    was = bench.gap()
    return [which for cost, which in _ranked(bench) if cost < was]


def play_oracle(bench: Bench) -> int:
    """Play knowing the wiring exactly. The ceiling.

    Not a clever player — it does not plan around the drift or spare
    itself the press that discovers the dead key, because it does not
    have to. What it establishes is only that the budget is enough,
    which is the one thing a rung has to be true for it to be worth
    setting.
    """
    while not bench.over():
        live = bench.wiring_now()
        pressed = None
        for _cost, want in _ranked(bench):
            for key, way in enumerate(live):
                if way == want:
                    pressed = key
                    break
            if pressed is not None:
                break
        bench.press(0 if pressed is None else pressed)
    return bench.reached


def play_learner(bench: Bench, rng: random.Random,
                 relearn: bool = True) -> int:
    """Find the wiring out by using it, and use it while finding it out.

    The reference player, and with *relearn* off, the foil. It keeps
    one direction per key — what that key did the last time it was
    pressed — and each press either spends itself usefully or spends
    itself learning, never neither: when something known points the
    right way it goes that way, and when nothing does it presses
    whichever key it knows least about, which on a wrapped grid still
    goes somewhere.

    With *relearn* off it writes each key down once and never looks
    again. That is exactly the player the drifting rungs are for: it
    identifies the wiring perfectly, early, and is then wrong about it
    for the rest of the round without ever being told.
    """
    grade = bench.bout.grade
    seen: Dict[int, int] = {}
    while not bench.over():
        wanted = helpful(bench)
        ready = [key for key, way in seen.items() if way in wanted]
        if ready:
            pressed = min(ready, key=lambda k: wanted.index(seen[k]))
        else:
            blind = [key for key in range(grade.keys) if key not in seen]
            pressed = (rng.choice(blind) if blind
                       else rng.randrange(grade.keys))
        expected = seen.get(pressed)
        went = bench.press(pressed)
        found = (ways(grade.keys).index(went) if went != (0, 0) else DEAD)
        if not relearn:
            seen.setdefault(pressed, found)
            continue
        if expected is not None and expected != found:
            # The whole ring turns at once, so one key caught lying
            # convicts the rest: everything but what was just seen
            # goes back to being unknown. Correcting only the key that
            # surprised it would leave the learner confidently wrong
            # about every other key until it happened to try them.
            seen = {}
        seen[pressed] = found
    return bench.reached


# --- dealing -------------------------------------------------------------


def limp(grade: Grade) -> int:
    """Presses added back for a rung that kills a key partway through.

    :attr:`Bout.shortest` is worked out with every direction
    available, so on a rung with a dead key it understates the trip —
    the shortest way somewhere with seven of eight directions is
    sometimes longer than with all eight. Without this even a player
    who knew the wiring would miss the odd target, and a rung the
    ceiling cannot clear is a broken rung rather than a hard one.
    """
    return grade.keys // 2 if grade.dies else 0


def deal(level_number: int, seed: Optional[int] = None) -> Bout:
    """A round at *level_number*.

    Nothing here needs searching for. The wiring is drawn from the
    rung's family, the targets are drawn far enough apart to be worth
    walking to, and the budget follows from the distance between them
    — so a deal is one draw and never a hunt.
    """
    grade = GRADES[max(0, min(len(GRADES) - 1, level_number - 1))]
    rng = random.Random(seed)
    start = (rng.randrange(grade.across), rng.randrange(grade.down))
    least = max(2, min(grade.across, grade.down) // 3)
    goals: List[Tuple[int, int]] = []
    here = start
    for _target in range(grade.targets):
        while True:
            spot = (rng.randrange(grade.across), rng.randrange(grade.down))
            if gap(here, spot, grade.across, grade.down,
                   grade.keys) >= least:
                break
        goals.append(spot)
        here = spot
    shortest = 0
    here = start
    for spot in goals:
        shortest += gap(here, spot, grade.across, grade.down, grade.keys)
        here = spot
    return Bout(grade=grade, start=start, goals=tuple(goals),
                wiring=wirings(grade.family, grade.keys, rng),
                turn=rng.randrange(1, grade.keys),
                dead=rng.randrange(grade.keys) if grade.dies else -1,
                budget=shortest + grade.spare + limp(grade),
                shortest=shortest)
