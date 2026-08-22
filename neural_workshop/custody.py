# -*- coding: utf-8 -*-
"""Chain of Custody: one of these is the one, and it has to arrive right.

A carousel of boxes goes round a belt. At the start one of them is
ringed for a moment — that one is the Core — and then the ring goes
away and it looks like all the others. The job is to get *that* box
into the bay, charged enough and cool enough, before the actions run
out.

Everything else on the belt exists because it affects that. The
charger raises charge and raises heat with it, so charging is not free.
The cooler brings heat down and does nothing else. The painter repaints
whatever passes through it, which is how a box can stop looking like
the box you were following. The claw picks a box up and puts it down,
and while it is held it does not ride the belt.

**What the task actually measures.** Not the delivery, which is easy,
but whether the identity survived the trip. A player who tracks
position loses it at the first jam; one who tracks colour loses it at
the painter; one who tracks neither is at chance among however many
boxes share the Core's look. The model knows which box is the Core the
whole time and never draws it.

Three things hold the module together:

* **Identity is never recoverable from a frame.** After the marking
  phase the Core carries no mark, and every rung deals more boxes than
  coats, so a colour narrows the field and never closes it — from two
  boxes to a coat at the bottom of the ladder to six at the top. The
  only thing that distinguishes the Core is the history of where it
  went, which is not in any single frame. :attr:`Grade.rivals` is that
  field, and one over it is what a player who has lost the Core and
  guesses among the boxes of its colour scores.

* **The requirement needs a plan, not a fetch.** From rung five the
  charger heats what it charges and the cooler is somewhere else on
  the ring, so the order matters: charge to the mark, then cool, then
  deliver. Cooling first is wasted, and delivering hot is a loss with
  the right box in the bay.

* **The shaping reveals nothing the screen does not.** :func:`potential`
  reads only the held box's charge, heat and position and the machine
  positions, all of which are drawn. It is deliberately blind to which
  box is the Core, so coach mode makes the routing easier to learn and
  the identity no easier at all. See :func:`potential`.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional, Sequence, Tuple

#: What a machine does to a box that rides into it.
CHARGER, COOLER, PAINTER = 'charger', 'cooler', 'painter'
KINDS: Tuple[str, ...] = (CHARGER, COOLER, PAINTER)

#: What one pass through the charger is worth, and what it costs in
#: heat. Sized so that **one pass clears the mark** and leaves the box
#: over the heat limit: the route is charger, then cooler, then bay,
#: three legs of one pass each. Making it three passes instead would
#: have added grinding rather than difficulty — the plan is the
#: content here, not the repetition.
CHARGE_STEP, CHARGE_HEAT = 45, 30

#: What one pass through the cooler takes off. More than the charger
#: puts on, so a cooled box is properly cold and the order cannot be
#: rescued by cooling first.
COOL_STEP = 35

#: How many appearances the palette can tell apart. Four, because the
#: boxes are small and a fifth would start to need looking at rather
#: than seeing.
LOOKS = 4

#: A box that is not on the belt: held in the claw, or delivered.
OFF_BELT = -1


def rivals_expected(boxes: int, looks: int) -> float:
    """Boxes per colour: the field a player who lost the Core guesses from.

    One over this is what a colour-only strategy scores, so it is the
    floor a rung's result has to be read against. Named on the ladder
    rather than derived, because deriving it made the ladder get
    *easier*: with a colour per two boxes the field is two boxes wide
    however many are on the belt, so a rung that added boxes added no
    difficulty at all on this axis. Measured, rungs six to eight came
    out below rungs three to five.
    """
    return boxes / float(max(1, looks))


class Machine(NamedTuple):
    """One machine, and the slot it sits in."""

    kind: str
    slot: int


class Layout(NamedTuple):
    """One dealt world: the ring, what is on it, and what is wanted."""

    #: Slots per row. The ring is twice this: the top row runs one way
    #: and the bottom row runs back.
    width: int
    boxes: int
    looks: int
    machines: Tuple[Machine, ...]
    #: Where a box is delivered. Off the belt, below the bottom row.
    bay: int
    #: Charge the Core must have when it arrives. Zero asks nothing.
    need_charge: int
    #: Heat it must be at or under. A hundred asks nothing.
    max_heat: int
    #: Charge a box loses on each step of the belt. Only while riding:
    #: a held box holds its charge, so the claw is somewhere safe and
    #: the belt is the only way to reach a machine. That trade is the
    #: whole of what decay adds.
    decay: int
    #: Whether the belt runs at all.
    moving: bool
    #: Actions the player gets. Running out is a loss, which is what
    #: stops a round from being solvable by trying everything.
    budget: int
    #: Which box is the Core. Shown once, then never again.
    core: int

    @property
    def slots(self) -> int:
        return self.width * 2


class Box:
    """One box on the belt. Mutable, because it is the live state."""

    __slots__ = ('latent', 'look', 'charge', 'heat', 'slot', 'held',
                 'delivered', 'stalled')

    def __init__(self, latent: int, look: int, slot: int) -> None:
        #: Its identity, which the screen never shows after the marking.
        self.latent = latent
        self.look = look
        self.charge = 0
        self.heat = 0
        self.slot = slot
        self.held = False
        self.delivered = False
        #: Standing in a machine that is working on it, so the belt
        #: leaves it alone for one step. That is what lets the claw put
        #: a box into a machine and take it straight back out.
        self.stalled = False

    def __repr__(self) -> str:      # pragma: no cover - debugging only
        return ('Box(%d, look=%d, slot=%d, charge=%d, heat=%d%s%s)'
                % (self.latent, self.look, self.slot, self.charge, self.heat,
                   ', held' if self.held else '',
                   ', delivered' if self.delivered else ''))


class Grade(NamedTuple):
    """One rung: what is on the belt, what is asked, and what it costs."""

    name: str
    boxes: int
    #: Coats the boxes wear. One means they are all identical and the
    #: only thing to go on is where the box went.
    looks: int
    width: int
    chargers: int
    coolers: int
    painters: int
    need_charge: int
    max_heat: int
    decay: int
    moving: bool
    budget: int

    @property
    def rivals(self) -> float:
        """The guessing floor: boxes wearing any one coat."""
        return rivals_expected(self.boxes, self.looks)


#: Toddler to hard. The first rung is a box and a bay and nothing else,
#: which is deliberate: a ladder whose bottom rung already needs a plan
#: has no bottom. Each rung after it adds exactly one thing, so a run
#: that fails says which one.
#:
#: Budgets are about four times what a player who already knows which
#: box is the Core spends at its worst, measured over two hundred deals
#: a rung by ``tests/oracle_custody.py``. Four, so that being wrong
#: twice and starting again is affordable: the budget is here to end a
#: round rather than to be the difficulty.
#:
#: The guessing floor rises the whole way — 1.0, 2.0, 2.5 ... 6.0 boxes
#: to a coat — so a rung is never easier than the one below it on the
#: axis the task is named for.
GRADES: Tuple[Grade, ...] = (
    #     name             box lk  w  ch co pa  need heat dec  move budget
    Grade('one box',         1, 1,  5, 0, 0, 0,    0, 100, 0, False,   40),
    Grade('two boxes',       2, 1,  5, 0, 0, 0,    0, 100, 0, False,   40),
    Grade('the belt',        5, 2,  6, 0, 0, 0,    0, 100, 0, True,    70),
    Grade('charge it',       5, 2,  6, 1, 0, 0,   40, 100, 0, True,   100),
    Grade('keep it cool',    6, 2,  7, 1, 1, 0,   40,  25, 0, True,   150),
    Grade('a new coat',      7, 2,  7, 1, 1, 1,   40,  25, 0, True,   150),
    Grade('it leaks',        8, 2,  8, 1, 1, 1,   40,  25, 1, True,   160),
    Grade('a busy belt',     9, 2,  8, 1, 1, 1,   40,  25, 1, True,   180),
    Grade('two coats',      10, 2,  9, 1, 1, 2,   40,  25, 2, True,   200),
    Grade('the yard',       12, 2, 10, 2, 1, 2,   40,  20, 2, True,   220),
)

#: The most boxes the ladder will ever put on the belt.
MOST_BOXES = max(grade.boxes for grade in GRADES)

#: The widest ring, so a wrapper knows how far the claw can travel.
MOST_WIDTH = max(grade.width for grade in GRADES)


# --- the ring ---------------------------------------------------------------


def gap(one: int, other: int, slots: int) -> int:
    """Slots between two positions, the short way round the ring.

    The claw may travel either way, so this is what a move changes by
    exactly one — which is the property :func:`potential` is built on.
    """
    straight = abs(one - other) % slots
    return min(straight, slots - straight)


def ahead(slot: int, slots: int) -> int:
    """The slot the belt carries this one into."""
    return (slot + 1) % slots


# --- what the machines do ---------------------------------------------------


def treat(box: Box, kind: str, layout: Layout) -> None:
    """Do what a machine of *kind* does to *box*, in place.

    The charger heats what it charges, which is the whole of why the
    order matters: three passes clear a sixty mark and leave the box
    at fifty-four, over a forty limit, so the cooler comes after.
    """
    if kind == CHARGER:
        box.charge = min(100, box.charge + CHARGE_STEP)
        box.heat = min(100, box.heat + CHARGE_HEAT)
    elif kind == COOLER:
        box.heat = max(0, box.heat - COOL_STEP)
    elif kind == PAINTER:
        # Moved on one colour rather than set to a fixed one. Measured
        # both ways: a fixed colour drove every box on the belt to the
        # same coat within three laps, which killed the colour channel
        # outright — a lost player was guessing among all twelve, and
        # nothing ever looked like anything again. Cycling keeps the
        # coats spread, so a colour still halves the field, and it
        # repaints the Core about once a lap instead of once a round,
        # which is the thing worth testing: an identity that has to
        # survive its own appearance changing.
        box.look = (box.look + 1) % layout.looks


def machine_at(layout: Layout, slot: int) -> Optional[str]:
    """The kind of machine in *slot*, or None."""
    for machine in layout.machines:
        if machine.slot == slot:
            return machine.kind
    return None


def slots_of(layout: Layout, kind: str) -> Tuple[int, ...]:
    """Every slot holding a machine of *kind*."""
    return tuple(m.slot for m in layout.machines if m.kind == kind)


# --- the belt ---------------------------------------------------------------


def loose(boxes: Sequence[Box]) -> List[Box]:
    """The boxes actually riding the belt."""
    return [box for box in boxes if not box.held and not box.delivered]


def step_belt(boxes: Sequence[Box], layout: Layout) -> None:
    """Carry the belt on one slot, and bleed the charge of what rides it.

    **The belt does not work the machines.** It used to, and that made
    the whole middle of the ladder free: a box left to ride would pass
    the charger and then the cooler on its own, arrive prepared, and
    the plan the rungs are named for cost nothing. A machine now acts
    only on a box the claw sets down in it — so preparation is
    actions, and where the machines sit is a route to work out rather
    than scenery to wait through.

    A box only moves if the slot in front of it is free, so a box put
    down in front of a queue holds it up rather than being driven
    through. Jams are part of the task: the claw is what clears them,
    and clearing one costs actions.

    Repeated rather than done in one sweep because the ring wraps, so
    there is no first box to start from; each pass moves whatever can
    move, and it stops as soon as a pass moves nothing.
    """
    riding = loose(boxes)
    if layout.moving:
        taken = {box.slot: box for box in riding}
        gone = set()
        for _pass in range(len(riding)):
            moved = False
            for box in sorted(riding, key=lambda b: b.slot, reverse=True):
                # One slot each, per step. Without this the passes that
                # unpick a jam would carry the same box round again and
                # again — measured, a box crossed five or six slots in a
                # step, which put it past the claw every time and made
                # the boxes impossible to intercept at all.
                if id(box) in gone:
                    continue
                if box.stalled:
                    # A machine is working on it. It holds its slot for
                    # this step, which is what makes a machine a place
                    # the claw can put something and take it back —
                    # without it, using a machine cost a whole lap of
                    # the ring to get the box in hand again, and with
                    # charge bleeding that was not a cost, it was a
                    # wall.
                    box.stalled = False
                    gone.add(id(box))
                    continue
                front = ahead(box.slot, layout.slots)
                if front in taken:
                    continue
                del taken[box.slot]
                box.slot = front
                taken[front] = box
                gone.add(id(box))
                moved = True
            if not moved:
                break
    for box in riding:
        # The painter is the one machine the belt still works, because
        # it is not a service anybody asks for — it is a hazard, and
        # its whole job is to repaint boxes without being asked. A
        # charger nobody chose to use would make preparation free; a
        # painter nobody chose to pass through is what stops a player
        # following a colour instead of following the box.
        #
        # It gives the claw its second reason to exist: a held box
        # keeps its coat, so holding the Core is how you protect what
        # you know about it, at the price of not being able to carry
        # anything else.
        if machine_at(layout, box.slot) == PAINTER:
            treat(box, PAINTER, layout)
        if layout.decay:
            # Only what rides, for the same reason.
            box.charge = max(0, box.charge - layout.decay)


# --- what the claw does -----------------------------------------------------


def box_at(boxes: Sequence[Box], slot: int) -> Optional[Box]:
    """The box riding *slot*, if any."""
    for box in loose(boxes):
        if box.slot == slot:
            return box
    return None


def grab(boxes: Sequence[Box], claw: int) -> Optional[Box]:
    """Lift the box under the claw, or nothing if the slot is empty."""
    box = box_at(boxes, claw)
    if box is not None:
        box.held = True
        box.stalled = False
        box.slot = claw
    return box


def put_down(held: Box, boxes: Sequence[Box], claw: int,
             layout: Layout) -> bool:
    """Set *held* down at the claw. False when the slot is taken.

    Setting a box down **in** a machine is what works the machine, and
    it is the only thing that does. The box is left standing in the
    slot afterwards, so it can be picked straight back up — at the
    cost of two actions a treatment, which is what stops charging from
    being free. Charge caps at a hundred and heat rises with it, so a
    learner that keeps charging cooks the box rather than improving
    it.

    Dropping at the bay delivers instead, and delivering is final —
    which is the point. There is no taking it back out to check.
    """
    if claw == layout.bay:
        held.held = False
        held.delivered = True
        held.slot = OFF_BELT
        return True
    if box_at(boxes, claw) is not None:
        return False
    held.held = False
    held.slot = claw
    kind = machine_at(layout, claw)
    if kind is not None:
        treat(held, kind, layout)
        held.stalled = True
    return True


# --- what the round wants ---------------------------------------------------


def wanted(box: Box, layout: Layout) -> bool:
    """Is this box in the state the bay asks for?"""
    return box.charge >= layout.need_charge and box.heat <= layout.max_heat


def next_target(box: Box, layout: Layout, claw: int) -> int:
    """The slot this box has to reach next, whichever box it is.

    The order is the plan: charge to the mark, then cool if charging
    left it hot, then the bay. Nothing here consults the Core — this
    is what *any* box in hand would need next, which is what keeps
    :func:`potential` from being an answer key.
    """
    if box.charge < layout.need_charge:
        chargers = slots_of(layout, CHARGER)
        if chargers:
            return min(chargers, key=lambda s: gap(claw, s, layout.slots))
    if box.heat > layout.max_heat:
        coolers = slots_of(layout, COOLER)
        if coolers:
            return min(coolers, key=lambda s: gap(claw, s, layout.slots))
    return layout.bay


def potential(held: Optional[Box], claw: int,
              layout: Layout) -> Optional[int]:
    """How far the held box still is from where it next has to be.

    Lower is better, and one claw move changes it by exactly one — so
    the sign of the change *is* the potential-based shaping term of Ng
    et al., every closed loop of moves telescopes to nothing, and the
    optimal policy is unchanged.

    **It is blind to the Core on purpose.** Everything it reads — the
    held box's charge and heat, its position, where the machines are,
    where the bay is — is drawn on the screen, so the shaping tells a
    learner nothing a frame does not already carry. Had it read
    ``layout.core`` it would have been an answer key for the one thing
    this task is about, and coach mode would have measured routing
    while appearing to measure identity.

    None when nothing is held: an empty claw has no plan to be near or
    far from, and paying its movement would pay wandering.
    """
    if held is None:
        return None
    return gap(claw, next_target(held, layout, claw), layout.slots)


# --- dealing ----------------------------------------------------------------


def _place(kinds: Sequence[str], slots: int, bay: int,
           rng: random.Random) -> List[Machine]:
    """Find a slot for each machine that leaves it usable.

    Two rules, and both were found by an oracle failing rather than by
    thinking about it.

    **Nothing may sit on the bay.** A machine there could never be
    used: setting a box down in that slot delivers it instead of
    treating it.

    **No two machines may be adjacent.** Not needed any more now that
    the claw works them one at a time, but kept because a box left
    standing in a machine rides into its neighbour on the next belt
    step, and a cooler behind a charger would quietly undo work the
    player had just paid two actions for.
    """
    barred = {bay}
    free = [slot for slot in range(slots) if slot not in barred]
    rng.shuffle(free)
    placed: List[Machine] = []
    for kind in kinds:
        for slot in free:
            near = {(slot - 1) % slots, slot, (slot + 1) % slots}
            if any(m.slot in near for m in placed):
                continue
            placed.append(Machine(kind, slot))
            break
        else:                       # pragma: no cover - the ladder fits
            raise ValueError('no room on a ring of %d for %d machines'
                             % (slots, len(kinds)))
    return placed


def generate(level_number: int, seed: Optional[int] = None,
             rng: Optional[random.Random] = None) -> Layout:
    """Deal one round at *level_number*, counting from one."""
    grade = GRADES[max(0, min(len(GRADES) - 1, level_number - 1))]
    rng = rng or random.Random(seed)
    slots = grade.width * 2
    bay = grade.width + grade.width // 2

    wants = ([CHARGER] * grade.chargers + [COOLER] * grade.coolers
             + [PAINTER] * grade.painters)
    machines = tuple(sorted(_place(wants, slots, bay, rng),
                            key=lambda m: m.slot))

    return Layout(
        width=grade.width, boxes=grade.boxes, looks=grade.looks,
        machines=machines, bay=bay, need_charge=grade.need_charge,
        max_heat=grade.max_heat, decay=grade.decay, moving=grade.moving,
        budget=grade.budget, core=rng.randrange(grade.boxes))


def fresh_boxes(layout: Layout, rng: random.Random) -> List[Box]:
    """Lay the boxes out on the belt, spread and dealt their looks.

    Looks are dealt round-robin and then shuffled, so the count of
    each is as even as it can be — an appearance worn by one box would
    be an appearance that answers the question.
    """
    free = [slot for slot in range(layout.slots)
            if slot != layout.bay and machine_at(layout, slot) is None]
    rng.shuffle(free)
    places = sorted(free[:layout.boxes])
    rng.shuffle(places)
    looks = [index % layout.looks for index in range(layout.boxes)]
    rng.shuffle(looks)
    return [Box(latent, look, slot)
            for latent, (look, slot) in enumerate(zip(looks, places))]


def core_of(boxes: Sequence[Box], layout: Layout) -> Optional[Box]:
    """The box that was ringed at the start."""
    for box in boxes:
        if box.latent == layout.core:
            return box
    return None


def rivals(boxes: Sequence[Box], layout: Layout) -> int:
    """How many boxes currently look like the Core does.

    The floor on guessing: a player who has lost the Core and picks
    among the boxes wearing its look is right one time in this many.
    Reported at the end of a run, because it is what the score has to
    be read against.
    """
    core = core_of(boxes, layout)
    if core is None:
        return 0
    return sum(1 for box in boxes
               if box.look == core.look and not box.delivered)


__all__ = [
    'Box', 'CHARGER', 'CHARGE_HEAT', 'CHARGE_STEP', 'COOLER', 'COOL_STEP',
    'GRADES', 'Grade', 'KINDS', 'LOOKS', 'Layout', 'MOST_BOXES',
    'MOST_WIDTH', 'Machine', 'OFF_BELT', 'PAINTER', 'ahead', 'box_at',
    'core_of', 'fresh_boxes', 'gap', 'generate', 'grab', 'loose',
    'machine_at', 'next_target', 'potential', 'put_down', 'rivals',
    'rivals_expected', 'slots_of', 'step_belt', 'treat', 'wanted',
]
