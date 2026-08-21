# -*- coding: utf-8 -*-
"""In the Dark: rooms you can see, lamps you cannot.

A row of lamps is lit behind you, in colours you are never shown. You
walk through a string of rooms, and each room does one thing to the
lamps — paints one a colour, turns one on to the next colour, swaps
two of them over, copies one onto another. Every room is drawn in
full. The lamps never are. At the end you are asked what colour some
of them ended up.

The point of the design is what a player cannot do. Nothing on the
screen at any moment says what colour any lamp is, so there is no
frame to read the answer off; and because the rooms are drawn from
the operation alone, two runs with different lamps behind them draw
*exactly the same pixels* and want different answers. A player who
looks only at what is in front of them is not merely handicapped, they
are at chance, and it is chance by construction rather than by
measurement.

The one thing that carries the answer is a register kept between the
rooms, updated once a room. That is the whole task: hold four to six
invisible values, apply thirty to forty exact updates to them, and be
right about all of them at the end. There is no partial credit for
remembering roughly.

Three guarantees hold the module together:

* Every question is answerable, by construction. A round is kept only
  when each lamp it asks about is pinned by some room in the walk, and
  the check is exact rather than statistical. Measured over the whole
  ladder, a player with the whole walk in mind scores exactly 1.000.

* The floor is exact, and it is a proof rather than a benchmark. Walk
  a lamp's history backwards — ``copy`` moves which lamp you are
  following, ``swap`` exchanges it, ``turn`` shifts the value, and
  ``paint`` fixes it and ends the chain. Until the chain reaches a
  paint, the final colour is a *bijection* applied to some lamp's
  starting colour, and the starting colours are uniform and unseen. So
  a player who remembers fewer than ``needed`` rooms holds no
  information at all about the answer, and scores exactly one in
  ``colours``. :func:`trace` computes ``needed`` in one pass, and
  :func:`belief` recomputes it the slow, obvious way so the two can be
  held against each other.

* The ladder's floors are measured. A rung rejects rounds whose
  weakest question is pinned closer than its floor, so "level 9" takes
  nine rooms of memory rather than being a long walk with a short
  answer.

The second axis exists because distance is not effort. A chain twenty
rooms long whose value simply sat there is a long wait, not a hard
question; :attr:`Round.work` counts only the rooms that actually moved
or changed the value being carried, which is the difference between
remembering a colour and computing one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import (Dict, FrozenSet, List, NamedTuple, Optional, Sequence,
                    Tuple)

#: What a room can do to the lamps. There is deliberately no "nothing
#: happens" room: measured, dropping it cut the search for a hard
#: round by a third and raised the work on the chain by a fifth, and
#: with five or six lamps most rooms are already a rest as far as any
#: one lamp is concerned.
PAINT, TURN, SWAP, COPY = 'paint', 'turn', 'swap', 'copy'
KINDS: Tuple[str, ...] = (PAINT, TURN, SWAP, COPY)

#: How often each kind is dealt, before being shared out between the
#: rooms of that kind. Paint is the only one that ends a chain, so its
#: weight is the dial between rounds that can be answered at all and
#: rounds whose answer is buried deep enough to be worth asking.
MIX: Dict[str, int] = {PAINT: 2, TURN: 3, SWAP: 3, COPY: 2}


class Room(NamedTuple):
    """One room of the walk: the single thing it does to the lamps.

    *lamp* is the lamp written to, and *other* is read according to
    the kind — the colour for a paint, the far lamp for a swap, the
    source for a copy, and nothing at all for a turn.
    """

    kind: str
    lamp: int
    other: int = 0


class Round(NamedTuple):
    """One walk: the rooms, the lamps behind them, and what it cost."""

    lamps: int
    colours: int
    rooms: Tuple[Room, ...]
    #: The colours the lamps started at. Never drawn, never hinted at,
    #: and uniform — which is what makes an unpinned lamp a coin.
    start: Tuple[int, ...]
    #: The lamps asked about at the end, in the order they are asked.
    asked: Tuple[int, ...]
    #: The true finishing colour of each lamp in :attr:`asked`.
    answers: Tuple[int, ...]
    #: Fewest trailing rooms that pin the *weakest* question. A player
    #: who remembers fewer than this many rooms is at chance on at
    #: least one of the questions, exactly.
    needed: int
    #: Rooms per question that actually moved or changed the value
    #: being carried, averaged over the questions. Distance says how
    #: long the answer had to be held; this says how much happened to
    #: it on the way.
    work: float


class Grade(NamedTuple):
    """One rung of the ladder: the lamps, the walk, and the floors."""

    name: str
    lamps: int
    colours: int
    #: Rooms in the walk.
    depth: int
    #: Lamps asked about at the end. Asking about most of them is what
    #: stops a player from picking one lamp to follow and ignoring the
    #: rest — you cannot know which will be wanted.
    asks: int
    #: Reject rounds whose weakest question is pinned closer than this.
    floor: int
    #: The junior axis: the least mean work a round may be worth. It
    #: never outranks the floor — a rung that cannot manage both would
    #: rather have the answer buried deep than shuffled hard, because
    #: depth is what the rung promises and what the screen reports.
    work: float = 0.0


#: Kindergarten to superhuman. Every number was measured rather than
#: guessed, over four hundred rounds a rung. The step floors sit at
#: about the mean of what each rung deals, which is what leaves them
#: binding without sending the search past a few dozen tries; the work
#: floors sit a little below theirs, because work is bounded from
#: above by the lamp count — with six lamps most rooms act on somebody
#: else's chain, so a twenty-room chain carries only about six rooms
#: of real work and asking for more would only cost depth.
GRADES: Tuple[Grade, ...] = (
    Grade('first light', 2, 2, 6, 1, 4, 2.0),
    Grade('two lamps', 2, 3, 8, 2, 5, 2.5),
    Grade('three lamps', 3, 3, 10, 2, 7, 2.5),
    Grade('the swap', 3, 3, 12, 2, 8, 3.0),
    Grade('four lamps', 4, 3, 14, 3, 9, 3.0),
    Grade('the shuffle', 4, 4, 16, 3, 10, 3.5),
    Grade('five lamps', 5, 4, 18, 3, 12, 3.5),
    Grade('the tangle', 5, 4, 22, 4, 13, 3.5),
    Grade('six lamps', 6, 4, 26, 4, 15, 3.5),
    Grade('nightmare', 6, 5, 30, 5, 17, 4.0),
    Grade('inhuman', 6, 5, 34, 5, 18, 4.0),
    Grade('superhuman', 6, 5, 40, 6, 20, 4.5),
)

#: The most lamps and colours the palette can tell apart, and so the
#: most the ladder may ask for.
MOST_LAMPS = 6
MOST_COLOURS = 5


def vocabulary(lamps: int, colours: int) -> List[Room]:
    """Every room that makes sense with this many lamps and colours."""
    rooms = [Room(PAINT, lamp, colour)
             for lamp in range(lamps) for colour in range(colours)]
    rooms += [Room(TURN, lamp) for lamp in range(lamps)]
    rooms += [Room(SWAP, one, other)
              for one in range(lamps) for other in range(one + 1, lamps)]
    rooms += [Room(COPY, dest, source)
              for dest in range(lamps) for source in range(lamps)
              if source != dest]
    return rooms


def _weights(rooms: Sequence[Room]) -> List[float]:
    """Share each kind's weight out evenly between its rooms."""
    counted = {kind: sum(1 for room in rooms if room.kind == kind)
               for kind in KINDS}
    return [MIX[room.kind] / float(counted[room.kind]) for room in rooms]


def enter(room: Room, cells: List[int], colours: int) -> List[int]:
    """Do what *room* does, to *cells*, in place. Returns *cells*."""
    if room.kind == PAINT:
        cells[room.lamp] = room.other
    elif room.kind == TURN:
        cells[room.lamp] = (cells[room.lamp] + 1) % colours
    elif room.kind == SWAP:
        one, other = room.lamp, room.other
        cells[one], cells[other] = cells[other], cells[one]
    elif room.kind == COPY:
        cells[room.lamp] = cells[room.other]
    return cells


def walk(rooms: Sequence[Room], start: Sequence[int],
         colours: int) -> Tuple[int, ...]:
    """The colours the lamps end up, having started at *start*."""
    cells = list(start)
    for room in rooms:
        enter(room, cells, colours)
    return tuple(cells)


def trace(rooms: Sequence[Room], lamp: int) -> Tuple[int, int]:
    """Follow *lamp*'s colour backwards: how far back, and how much work.

    Not a simulation — a dependency chain. The colour a lamp finishes
    on came from somewhere, and every room says where: a copy into it
    means the answer is really the source's, a swap means it is really
    the other lamp's, a turn means it is one step along from what it
    was, and a paint means it is simply the painted colour and nothing
    before that room matters.

    Returns the number of trailing rooms that pin the colour and the
    number of those rooms that actually moved or changed it. When no
    room pins it — every chain is bijections all the way back to the
    unseen start — the distance is ``-1`` and the question is a coin
    that must not be asked.
    """
    slot, work = lamp, 0
    for back, room in enumerate(reversed(rooms)):
        if room.kind == PAINT and room.lamp == slot:
            return back + 1, work
        if room.kind == TURN and room.lamp == slot:
            work += 1
        elif room.kind == COPY and room.lamp == slot:
            slot = room.other
            work += 1
        elif room.kind == SWAP and slot in (room.lamp, room.other):
            slot = room.other if slot == room.lamp else room.lamp
            work += 1
    return -1, work


def pinned(rooms: Sequence[Room], lamp: int, lamps: int,
           colours: int) -> Optional[int]:
    """The colour *lamp* must finish on, or None when it is not pinned.

    Once a chain reaches a paint the answer no longer depends on what
    the lamps started at, so running the walk from any starting point
    at all gives it. This runs one.
    """
    if trace(rooms, lamp)[0] < 0:
        return None
    return walk(rooms, [0] * lamps, colours)[lamp]


def belief(rooms: Sequence[Room], lamp: int, lamps: int,
           colours: int) -> FrozenSet[int]:
    """Every colour *lamp* could still finish on, over all starts.

    The slow, obvious reading of the same question :func:`trace`
    answers in one pass: run every starting arrangement of the lamps
    through the whole walk and collect what this one ends up. Kept
    because a fast derivation that nothing checks is a fast
    derivation nobody should trust — the tests hold the two against
    each other, and a singleton here is exactly a chain that reached a
    paint there.
    """
    seen = set()
    for value in range(colours ** lamps):
        cells = [(value // colours ** place) % colours
                 for place in range(lamps)]
        for room in rooms:
            enter(room, cells, colours)
        seen.add(cells[lamp])
    return frozenset(seen)


def remembering(a_round: Round, window: int) -> Tuple[int, int]:
    """Score a player who recalls only the last *window* rooms.

    The foil, and the one this task is built to defeat. It plays as
    well as anybody can from that much: where the tail it can see
    already pins a lamp it answers exactly, and where it does not it
    has no information whatever and must guess. Returns the questions
    it can be sure of and the questions asked — everything else is one
    in :attr:`Round.colours`, which is why the certain ones are the
    whole story.
    """
    tail = a_round.rooms[max(0, len(a_round.rooms) - window):]
    sure = sum(1 for lamp in a_round.asked
               if trace(tail, lamp)[0] >= 0)
    return sure, len(a_round.asked)


def _backwards(room: Room, live: set) -> None:
    """Move the live chains back through *room*, in place.

    *live* is the set of lamps the unanswered questions are resting on
    at this point in the walk, read from the end. A paint ends every
    chain sitting on the lamp it paints; a copy moves them to the lamp
    it copied from; a swap carries them across.
    """
    if room.kind == PAINT:
        live.discard(room.lamp)
    elif room.kind == COPY and room.lamp in live:
        live.discard(room.lamp)
        live.add(room.other)
    elif room.kind == SWAP:
        here, there = room.lamp in live, room.other in live
        if here != there:
            live.discard(room.lamp if here else room.other)
            live.add(room.other if here else room.lamp)


def _draw(rooms: Sequence[Room], weights: Sequence[float],
          rng: random.Random, spare: Optional[set],
          avoid: Optional[Room]) -> Room:
    """One room: never painting a lamp in *spare*, never *avoid*.

    *avoid* is the room that will follow this one, and refusing to
    repeat it is what keeps a swap from being undone by the very next
    room. Such a pair is a no-op that :func:`trace` nonetheless counts
    as two rooms of work, so leaving them in would let the junior axis
    be paid in coin it did not earn.
    """
    allowed = [(room, weight) for room, weight in zip(rooms, weights)
               if room != avoid
               and not (spare and room.kind == PAINT and room.lamp in spare)]
    return rng.choices([room for room, _w in allowed],
                       weights=[weight for _r, weight in allowed])[0]


def _deal(grade: Grade, rng: random.Random,
          rooms: Sequence[Room], weights: Sequence[float]) -> Round:
    """One round at *grade*, built from the end so its floor is certain.

    Dealing a walk and keeping it only if it happened to bury its
    answers deep enough does not work: measured, the median walk pins
    its weakest question four rooms from the end against a floor of
    twenty, and seven deals in eight ask about a lamp no room ever
    pinned at all. Both are the wrong tail to sample from.

    So the walk is laid backwards instead. Every question starts
    resting on the lamp it asks about, and the rooms are drawn from
    the end towards the beginning, carrying the questions back through
    each one. For the last ``floor - 1`` rooms a paint onto a lamp a
    question is resting on is simply not offered, so no chain can end
    inside them and ``needed`` cannot come out below the floor. Past
    that paints are offered again and the chains end where they fall —
    except that when only as many rooms are left as there are
    questions still open, each remaining one is closed by hand, which
    is what makes every question answerable rather than merely likely
    to be.

    The construction proposes and :func:`trace` disposes: nothing here
    is trusted, and the numbers on the round are measured off the
    finished walk.
    """
    asked = tuple(rng.sample(range(grade.lamps), grade.asks))
    live = set(asked)
    laid: List[Room] = []                     # from the last room backwards
    for step in range(grade.depth):
        left = grade.depth - step             # rooms still to lay, this one in
        if left <= len(live):
            room = Room(PAINT, min(live), rng.randrange(grade.colours))
        else:
            deep = step < grade.floor - 1     # too near the end to end a chain
            room = _draw(rooms, weights, rng, live if deep else None,
                         laid[-1] if laid else None)
        laid.append(room)
        _backwards(room, live)
    walked = tuple(reversed(laid))

    traces = [trace(walked, lamp) for lamp in asked]
    start = tuple(rng.randrange(grade.colours) for _lamp in range(grade.lamps))
    finish = walk(walked, start, grade.colours)
    return Round(lamps=grade.lamps, colours=grade.colours, rooms=walked,
                 start=start, asked=asked,
                 answers=tuple(finish[lamp] for lamp in asked),
                 needed=min(back for back, _work in traces),
                 work=sum(work for _back, work in traces) / float(len(traces)))


def generate(level_number: int, seed: Optional[int] = None,
             attempts: int = 80) -> Round:
    """A round at *level_number*, at or above that rung's floors.

    The floor needs no searching for — :func:`_deal` lays every walk so
    that it holds — so the only axis left to shop for is the work, and
    the attempts go on finding a round that shuffles as well as it
    buries. Failing that the hardest-working round of the lot is
    handed back rather than the first one seen, which keeps the junior
    axis honest without ever letting it outrank the floor.
    """
    grade = GRADES[max(0, min(len(GRADES) - 1, level_number - 1))]
    rooms = vocabulary(grade.lamps, grade.colours)
    weights = _weights(rooms)
    rng = random.Random(seed)
    best: Optional[Round] = None
    for _attempt in range(max(1, attempts)):
        got = _deal(grade, rng, rooms, weights)
        if got.work >= grade.work:
            return got
        if best is None or got.work > best.work:
            best = got
    assert best is not None
    return best
