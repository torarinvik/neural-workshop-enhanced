# -*- coding: utf-8 -*-
"""Removals: things go into boxes, boxes go into boxes, boxes go into vans.

A yard of vans, a stack of boxes and a pile of things to pack. One
move happens at a time and each is drawn in full: this thing goes into
that box, that box goes into this van, these two things change places.
Where anything actually *is* is never drawn. At the end you are asked
which van some of the things ended up in.

The question is deliberately not "what did you just see". A thing is
in a box, that box is in another box, and that one is in a van, and no
single move ever said so — the answer is a *composition* of facts
learned at three or four different moments, each of which was ordinary
at the time. That is the faculty this task is for, and it is a
different one from holding a register: :mod:`neural_workshop.inthedark`
asks you to carry six values and update them, and this asks you to
carry a shape and then walk it.

Three guarantees hold the module together, and they are the same three
In the Dark keeps, because they are what separates a benchmark from a
diversion:

* Every question is answerable. A round is kept only when each thing
  it asks about rests, at the end, on a chain of moves that reaches a
  van — and the chain is read off the finished walk rather than hoped
  for.

* The floor is half proof and half measurement, and it is worth
  being clear about which half is which.

  The proof is that a short memory settles nothing. Every move is
  unconditional — a pack writes a constant into one slot, a swap
  exchanges two slots, and neither reads a value to decide what to do
  — so the resting map a walk produces is a fixed function of the map
  it started from, and each entry in it is either a constant that walk
  wrote or, traced back through the swaps, the contents of some slot
  it never wrote. A player holding fewer than :attr:`Round.needed`
  moves falls off the chain onto one of those, and what is there was
  settled before anything they saw. Their memory does not merely help
  a little; it bears on the question not at all. :func:`resting`
  computes this in one pass and :func:`belief` recomputes it the slow
  way over every possible start, and the tests hold the two against
  each other. Measured over the ladder, a player who recalls the last
  ``floor - 1`` moves is certain of exactly none of the questions,
  every rung.

  What the proof does not settle is what such a player should then
  guess, because the state before the tail is the generator's doing
  rather than a coin. So that half is measured: over three thousand
  rounds a rung, the van an answer lands in is even to within two
  standard deviations on all twelve, and the best fixed guess
  available beats chance by at most 0.010. Between the two halves the
  floor is one in :attr:`Yard.vans` and there is nothing to be had
  below it.

* The ladder's floors are laid in rather than searched for. Chains are
  designed first, at the depth the rung asks for, and the walk is
  built around them, so "level 9" really is four vans deep and fifteen
  moves back rather than a long walk with a shallow answer.

Three numbers grade a round, and they are not the same number:

``needed``
    How far back the memory must reach. The span.

``nest``
    How many hops the answer is composed of. The depth. This is the
    axis the task exists for — a chain twenty moves back but only one
    hop long is a long wait, not a hard question.

``churn``
    Moves that touched something on a chain and were then overridden.
    Work that had to be done and thrown away, which is what stops a
    player from simply keeping the first thing they hear about a box.

One operation was designed and then dropped. ``tip`` — empty a box out
onto the floor — is the most natural move in a removal and it is not
here, because its effect depends on what is inside the box and so on
the unseen start. That makes an unpinned answer a *restricted* draw
rather than a uniform one, and turns the floor from a proof into a
bound. The task is worth more with an exact floor than with a richer
verb, so the verb went.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import (Dict, FrozenSet, List, NamedTuple, Optional, Sequence,
                    Set, Tuple)

#: What a move can do. A pack puts one thing inside one holder,
#: subtree and all; a swap exchanges where two things are sitting.
#: Both are unconditional, which is the whole of why the floor is
#: provable — see the module docstring.
PACK, SWAP = 'pack', 'swap'
KINDS: Tuple[str, ...] = (PACK, SWAP)

#: A slot whose contents the walk never settled, and which therefore
#: still holds whatever the unseen start put there.
UNKNOWN = -1

#: The most vans, boxes and things the screen can tell apart, and so
#: the most the ladder may ask for. Vans are capped by the answer keys
#: and things by the palette.
MOST_VANS = 5
MOST_BOXES = 12
MOST_ITEMS = 8


class Yard(NamedTuple):
    """How many of each kind of thing a round has, and who is who.

    Everything in a round is a node, numbered so that the kind can be
    read off the number: vans first, then boxes, then things. Vans are
    their own holder, which is what lets :func:`van_of` walk a chain
    upwards and simply stop.
    """

    vans: int
    boxes: int
    items: int

    @property
    def size(self) -> int:
        """Every node there is, vans included."""
        return self.vans + self.boxes + self.items

    def box(self, which: int) -> int:
        """Node number of box *which*, counting from zero."""
        return self.vans + which

    def item(self, which: int) -> int:
        """Node number of thing *which*, counting from zero."""
        return self.vans + self.boxes + which

    def is_van(self, node: int) -> bool:
        return node < self.vans

    def is_box(self, node: int) -> bool:
        return self.vans <= node < self.vans + self.boxes

    def is_item(self, node: int) -> bool:
        return node >= self.vans + self.boxes

    def van_ids(self) -> range:
        return range(0, self.vans)

    def box_ids(self) -> range:
        return range(self.vans, self.vans + self.boxes)

    def item_ids(self) -> range:
        return range(self.vans + self.boxes, self.size)

    def holders(self) -> range:
        """Everything something can be put inside: vans and boxes."""
        return range(0, self.vans + self.boxes)

    def movers(self) -> range:
        """Everything that can be moved: boxes and things, not vans."""
        return range(self.vans, self.size)


class Move(NamedTuple):
    """One move: the single thing it does to the yard.

    *thing* is the node moved. *other* is read according to the kind —
    the holder it goes into for a pack, and the node it changes places
    with for a swap.
    """

    kind: str
    thing: int
    other: int


class Round(NamedTuple):
    """One removal: the moves, the yard behind them, and what it cost."""

    yard: Yard
    moves: Tuple[Move, ...]
    #: Where everything sat before the first move: a full holder map,
    #: vans mapped to themselves. Never drawn, never hinted at, and
    #: each thing's van drawn uniformly — which is what makes a slot
    #: the walk never settled a coin rather than a clue.
    start: Tuple[int, ...]
    #: The things asked about at the end, in the order they are asked.
    asked: Tuple[int, ...]
    #: The van each thing in :attr:`asked` really finished in.
    answers: Tuple[int, ...]
    #: Fewest trailing moves that pin the *weakest* question. Below
    #: this a player is at chance on at least one question, exactly.
    needed: int
    #: Hops from thing to van on the *shortest* chain asked about.
    #: One hop is "it is in that van"; four is a thing in a box in a
    #: box in a box in a van.
    nest: int
    #: Moves that touched something on a chain and were then
    #: overridden by a later move on the same node.
    churn: int


class Grade(NamedTuple):
    """One rung of the ladder: the yard, the walk, and the floors."""

    name: str
    vans: int
    boxes: int
    items: int
    #: Moves in the walk.
    depth: int
    #: Things asked about at the end. Asking about several is what
    #: stops a player from picking one thing to follow and letting the
    #: rest go — you cannot know which will be wanted.
    asks: int
    #: Hops every chain asked about must be worth. Laid in, not hoped
    #: for, so it is a guarantee and not an average.
    nest: int
    #: Reject rounds whose weakest question is pinned closer than this.
    floor: int
    #: The junior axis: the least churn a round may be worth. It never
    #: outranks the other two — a rung that cannot manage all three
    #: would rather bury the answer deep and compose it from far away
    #: than shuffle hard, because those are what the rung promises and
    #: what the screen reports.
    churn: int = 0


#: Kindergarten to superhuman. Two vans and a six-move walk up to five
#: vans, ten boxes and a chain five hops long buried nineteen moves
#: back. Chance runs from one in two down to one in five as the vans
#: come in, which is why the early rungs lean on depth instead.
GRADES: Tuple[Grade, ...] = (
    #                     vans box item  moves asks nest floor churn
    Grade('first load',      2,  2,   3,     6,  1,   2,    4,    0),
    Grade('two vans',        2,  3,   4,     8,  1,   2,    5,    0),
    Grade('stacking up',     3,  3,   4,    10,  2,   2,    7,    1),
    Grade('a box in a box',  3,  4,   5,    12,  2,   3,    8,    1),
    Grade('three deep',      3,  5,   5,    14,  2,   3,    9,    2),
    Grade('the shuffle',     3,  5,   6,    16,  3,   3,   10,    2),
    Grade('four vans',       4,  6,   6,    18,  3,   3,   12,    3),
    Grade('deep stack',      4,  7,   7,    22,  3,   4,   13,    3),
    Grade('the tangle',      4,  8,   7,    26,  3,   4,   15,    4),
    Grade('nightmare',       4,  8,   8,    30,  4,   4,   17,    4),
    Grade('inhuman',         5,  9,   8,    34,  4,   5,   17,    5),
    Grade('superhuman',      5, 10,   8,    40,  5,   5,   19,    6),
)

#: How often a filler move is a swap rather than a pack. Swaps are the
#: junior verb — a pack says where something is and a swap only says
#: where it is *relative to* something else — so they are seasoning
#: rather than the meal.
SWAP_SHARE = 0.3

#: How often a chain reuses a box already standing at the right depth
#: under the right holder instead of taking a fresh one. Sharing is
#: what lets a rung ask for five hops without needing twenty boxes.
SHARE = 0.45


# --- reading a walk ------------------------------------------------------


def enter(move: Move, parent: List[int]) -> List[int]:
    """Do what *move* does, to the holder map *parent*, in place.

    Both verbs are position-wise: a pack writes a constant into one
    slot and a swap exchanges two slots. Neither looks at a value to
    decide what to do, which is why :data:`UNKNOWN` flows through this
    correctly without any special handling — an unknown thing swapped
    with a known one simply trades places with it.
    """
    if move.kind == PACK:
        parent[move.thing] = move.other
    else:
        parent[move.thing], parent[move.other] = (parent[move.other],
                                                  parent[move.thing])
    return parent


def carry(moves: Sequence[Move], start: Sequence[int]) -> List[int]:
    """Where everything rests, having started at *start*."""
    parent = list(start)
    for move in moves:
        enter(move, parent)
    return parent


def resting(moves: Sequence[Move], yard: Yard) -> List[int]:
    """Where everything rests when the start is not known.

    Runs the walk from a map that knows only where the vans are.
    Every slot that comes out :data:`UNKNOWN` is one this walk never
    settled, and so still holds a thing's starting van — uniform,
    independent, and never shown.
    """
    parent = [node if yard.is_van(node) else UNKNOWN
              for node in range(yard.size)]
    for move in moves:
        enter(move, parent)
    return parent


def chain(parent: Sequence[int], node: int, yard: Yard) -> Tuple[int, ...]:
    """*node*, then what holds it, and so on up to a van.

    Stops early — and short of a van — when it reaches a slot nothing
    settled. The last entry is a van exactly when the chain is whole.
    """
    walked = [node]
    while not yard.is_van(node):
        node = parent[node]
        if node == UNKNOWN or node in walked:
            break
        walked.append(node)
    return tuple(walked)


def van_of(parent: Sequence[int], node: int, yard: Yard) -> int:
    """Which van *node* is in, or :data:`UNKNOWN` when that is open."""
    walked = chain(parent, node, yard)
    last = walked[-1]
    return last if yard.is_van(last) else UNKNOWN


def span(moves: Sequence[Move], node: int, yard: Yard) -> int:
    """Fewest trailing moves that pin which van *node* is in.

    Walks the tail outwards from nothing. The answer is exact rather
    than an estimate: a tail one move short leaves some link in the
    chain resting on a slot the tail never settled, and that slot
    holds a uniform starting van.

    Returns ``-1`` when the whole walk does not pin it — a question
    that must not be asked.
    """
    for window in range(len(moves) + 1):
        tail = moves[len(moves) - window:]
        if van_of(resting(tail, yard), node, yard) != UNKNOWN:
            return window
    return -1


def belief(moves: Sequence[Move], node: int, yard: Yard) -> FrozenSet[int]:
    """Every van *node* could still be in, over every possible start.

    The slow, obvious reading of the question :func:`resting` answers
    in one pass: put every arrangement of the yard through the whole
    walk and collect where this one ends up. Kept because a fast
    derivation that nothing checks is a fast derivation nobody should
    trust — the tests hold the two against each other, and a singleton
    here is exactly a settled slot there.

    Exponential in the number of movable things, so it is for small
    yards and for tests.
    """
    movers = list(yard.movers())
    seen: Set[int] = set()
    for value in range(yard.vans ** len(movers)):
        parent = list(range(yard.size))
        for place, mover in enumerate(movers):
            parent[mover] = (value // yard.vans ** place) % yard.vans
        seen.add(van_of(carry(moves, parent), node, yard))
    return frozenset(seen)


def touched(move: Move) -> Tuple[int, ...]:
    """The nodes *move* writes to — one for a pack, two for a swap."""
    return (move.thing,) if move.kind == PACK else (move.thing, move.other)


def wasted(moves: Sequence[Move], nodes: Set[int]) -> int:
    """Moves that write to one of *nodes* and are then written over.

    Work a player has to do and then throw away. Read off the walk
    alone: a move counts when some later move writes to the same node,
    so what makes it wasted is the walk and not the intention behind
    it.
    """
    last: Dict[int, int] = {}
    for index, move in enumerate(moves):
        for node in touched(move):
            last[node] = index
    return sum(1 for index, move in enumerate(moves)
               if any(node in nodes and last[node] > index
                      for node in touched(move)))


def remembering(a_round: Round, window: int) -> Tuple[int, int]:
    """Score a player who recalls only the last *window* moves.

    The foil, and the one this task is built to defeat. It plays as
    well as anybody could from that much: where the tail it can see
    already pins a thing's van it answers exactly, and where it does
    not it holds no information whatever and must guess. Returns the
    questions it can be sure of and the questions asked — everything
    else is one in :attr:`Yard.vans`, which is why the certain ones
    are the whole story.
    """
    tail = a_round.moves[max(0, len(a_round.moves) - window):]
    settled = resting(tail, a_round.yard)
    sure = sum(1 for node in a_round.asked
               if van_of(settled, node, a_round.yard) != UNKNOWN)
    return sure, len(a_round.asked)


# --- laying a walk -------------------------------------------------------


def inside(parent: Sequence[int], node: int, maybe: int, yard: Yard) -> bool:
    """True when *maybe* is *node*, or sits somewhere inside it."""
    seen = 0
    while True:
        if maybe == node:
            return True
        if yard.is_van(maybe) or maybe == UNKNOWN:
            return False
        maybe = parent[maybe]
        seen += 1
        if seen > yard.size:
            return False


def _room(holder: Dict[int, int], level: Dict[int, int], node: int,
          want: int) -> bool:
    """True when *want* more levels of boxes already stand under *node*.

    What makes sharing safe. A chain that reuses a box has to be able
    to finish from there, and a box with nothing under it is a dead
    end — so the question is never "is there a box at this level" but
    "is there one deep enough to land on".
    """
    if want <= 0:
        return True
    below = level.get(node, 0) + 1
    return any(holder[box] == node and level[box] == below
               and _room(holder, level, box, want - 1)
               for box in level)


def _spines(asked: Sequence[int], grade: Grade, yard: Yard,
            rng: random.Random) -> Optional[Dict[int, int]]:
    """Design where the asked things finish, before any move is laid.

    Builds each chain downwards from a van: pick a box to stand in the
    van, a box to stand in that, and so on to the depth the rung asks
    for, then hang the thing off the bottom. Fresh boxes are taken
    while there are enough left to finish the chain; past that it must
    reuse one already standing at the right depth under the right
    holder, and it reuses one sometimes anyway. Sharing is what lets
    the top rung ask for five hops from ten boxes rather than twenty —
    and it makes one remembered fact serve two answers, which is how a
    real removal works.

    Returns the designed holder of every node on a chain, or ``None``
    when the boxes ran out.
    """
    holder: Dict[int, int] = {}
    level: Dict[int, int] = {}
    free = list(yard.box_ids())
    rng.shuffle(free)
    for item in asked:
        deep = grade.nest
        if len(free) >= deep and rng.random() < 0.25:
            deep += 1
        vans = [van for van in yard.van_ids()
                if len(free) >= deep - 1
                or _room(holder, level, van, deep - 1)]
        if not vans:
            return None
        at = rng.choice(vans)
        for step in range(1, deep):
            want = deep - step
            kin = [box for box in level
                   if level[box] == step and holder[box] == at
                   and _room(holder, level, box, want - 1)]
            if kin and (len(free) < want or rng.random() < SHARE):
                at = rng.choice(kin)
            elif len(free) >= want:
                box = free.pop()
                holder[box], level[box] = at, step
                at = box
            elif kin:
                at = rng.choice(kin)
            else:
                return None
        holder[item] = at
    return holder


def _spots(links: Sequence[int], anchors: Set[int], grade: Grade,
           rng: random.Random) -> Optional[Dict[int, int]]:
    """When each designed link is laid down.

    Every chain needs one link laid early, because a question is
    pinned no further back than its earliest link — that link is its
    *anchor*, and putting anchors in the first ``depth - floor`` moves
    is what makes the rung's floor a guarantee. The rest go anywhere,
    which matters: if every link were early then the whole tail of the
    walk would be filler on a handful of things nobody asks about, and
    a player would learn to stop watching.
    """
    early = grade.depth - grade.floor + 1
    if len(anchors) > early or len(links) > grade.depth:
        return None
    free = list(range(grade.depth))
    rng.shuffle(free)
    spots: Dict[int, int] = {}
    for node in sorted(anchors):
        pick = next((spot for spot in free if spot < early), None)
        if pick is None:
            return None
        free.remove(pick)
        spots[node] = pick
    for node in links:
        if node not in spots:
            spots[node] = free.pop()
    return spots


def _swap_link(parent: Sequence[int], thing: int, want: int,
               loose: Set[int], yard: Yard,
               rng: random.Random) -> Optional[Move]:
    """A swap that lands *thing* in *want*, if one is going spare.

    Chains would otherwise be built entirely out of packs, and a
    player would learn that a swap never carries an answer. This finds
    some other thing already sitting in the holder we want and trades
    places with it instead. Both sides are things rather than boxes,
    so neither can be inside the other and no loop can be made.
    """
    spare = [node for node in loose
             if node != thing and yard.is_item(node)
             and parent[node] == want]
    if not spare:
        return None
    return Move(SWAP, thing, rng.choice(spare))


def _filler(parent: Sequence[int], loose: Set[int], chained: Set[int],
            yard: Yard, rng: random.Random) -> Optional[Move]:
    """A move that carries no answer, and disturbs no chain that does.

    Anything still loose may be packed or swapped, with two guards. A
    box that a chain runs through is only ever packed straight into a
    van, because that is the one destination that cannot put a box
    inside itself; and any other pack is checked against the yard as
    it actually stands. Between them nothing here can make a loop.
    """
    movers = list(loose)
    rng.shuffle(movers)
    for thing in movers:
        mates = [node for node in loose
                 if node != thing and yard.is_item(node)]
        if yard.is_item(thing) and mates and rng.random() < SWAP_SHARE:
            return Move(SWAP, thing, rng.choice(mates))
        if thing in chained and yard.is_box(thing):
            vans = [van for van in yard.van_ids() if parent[thing] != van]
            if vans:
                return Move(PACK, thing, rng.choice(vans))
            continue
        holders = [spot for spot in yard.holders()
                   if spot != parent[thing]
                   and not inside(parent, thing, spot, yard)]
        if holders:
            return Move(PACK, thing, rng.choice(holders))
    return None


def _deal(grade: Grade, yard: Yard, rng: random.Random) -> Optional[Round]:
    """One round at *grade*, designed from the answers backwards.

    Dealing a walk and keeping it when it happens to bury its answers
    deep enough does not work here, and for a sharper reason than it
    did not work in In the Dark: a random walk almost never nests
    anything. Packing at random puts most things straight into a van,
    so the chain the whole task is about is one hop long and the rung
    has nothing to grade.

    So the chains are designed first — a thing, the box it is in, the
    box that is in, the van that is in — and then the walk is built
    around them. Each link becomes one move; every chain gets one link
    in the early moves so that its answer is pinned at least as far
    back as the rung promises; and everything else is filler, drawn
    from whatever is still loose, so that the screen is busy with
    moves that matter and moves that do not and never says which is
    which.

    Nothing here is trusted. The construction proposes and
    :func:`resting` disposes: the numbers on the round are measured
    off the finished walk.
    """
    asked = tuple(sorted(rng.sample(list(yard.item_ids()), grade.asks)))
    holder = _spines(asked, grade, yard, rng)
    if holder is None:
        return None
    chained = set(holder)
    anchors = set()
    for item in asked:
        walk = [item]
        while walk[-1] in holder:
            walk.append(holder[walk[-1]])
        anchors.add(rng.choice(walk[:-1]))
    spots = _spots(sorted(chained), anchors, grade, rng)
    if spots is None:
        return None

    laid: Dict[int, int] = {spot: node for node, spot in spots.items()}
    start = [node if yard.is_van(node) else rng.randrange(yard.vans)
             for node in range(yard.size)]
    parent = list(start)
    loose = set(yard.movers())
    moves: List[Move] = []
    for step in range(grade.depth):
        if step in laid:
            thing = laid[step]
            want = holder[thing]
            move = None
            if yard.is_item(thing) and rng.random() < SWAP_SHARE:
                move = _swap_link(parent, thing, want, loose - {thing},
                                  yard, rng)
            if move is None:
                if inside(parent, thing, want, yard):
                    return None
                move = Move(PACK, thing, want)
            loose.discard(thing)
        else:
            move = _filler(parent, loose, chained, yard, rng)
            if move is None:
                return None
        moves.append(move)
        enter(move, parent)

    walked = tuple(moves)
    settled = resting(walked, yard)
    spans = [span(walked, item, yard) for item in asked]
    if min(spans) < 0:
        return None
    nests = [len(chain(settled, item, yard)) - 1 for item in asked]
    finish = carry(walked, start)
    return Round(yard=yard, moves=walked, start=tuple(start), asked=asked,
                 answers=tuple(van_of(finish, item, yard) for item in asked),
                 needed=min(spans), nest=min(nests),
                 churn=wasted(walked, chained))


def generate(level_number: int, seed: Optional[int] = None,
             attempts: int = 200) -> Round:
    """A round at *level_number*, at or above that rung's floors.

    The depth and the span need no searching for — :func:`_deal` lays
    every walk so that they hold — so the attempts go on the churn,
    and on the deals that simply do not come out: a chain can run out
    of boxes, or want to put a box somewhere it already is. Failing to
    find a round that shuffles as well as it buries, the busiest of
    the lot is handed back rather than the first one seen, which keeps
    the junior axis honest without ever letting it outrank the other
    two.
    """
    grade = GRADES[max(0, min(len(GRADES) - 1, level_number - 1))]
    yard = Yard(grade.vans, grade.boxes, grade.items)
    rng = random.Random(seed)
    best: Optional[Round] = None
    for _attempt in range(max(1, attempts)):
        got = _deal(grade, yard, rng)
        if got is None:
            continue
        if (got.needed >= grade.floor and got.nest >= grade.nest
                and got.churn >= grade.churn):
            return got
        if got.needed >= grade.floor and got.nest >= grade.nest:
            if best is None or got.churn > best.churn:
                best = got
    if best is None:
        raise RuntimeError('no round could be laid at level %d' % level_number)
    return best
