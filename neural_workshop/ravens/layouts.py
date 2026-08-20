# -*- coding: utf-8 -*-
"""Where the figures sit inside a panel.

A layout is the arrangement a panel uses, and it is fixed for the whole
matrix: every panel of a puzzle uses the same one, so the layout is
part of the puzzle's shape rather than something that varies and has
to be worked out.

This is the piece the previous engine had no idea of. It drew every
figure at the centre of the panel and let them overlap, which is why
two rules running at once came out as a tangle. Giving each figure a
slot of its own is most of what separates a matrix that looks designed
from one that looks like a collision.

A layout carries one or two **components**. A component is a group of
figures that share a rule — the outer ring and the inner mark of an
in-out layout are two components, and each follows rules of its own.
That is how a matrix asks two questions at once without the answers
being drawn on top of each other.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from .figures import _ladder
from .geometry import Point


@dataclass(frozen=True)
class Slot:
    """Room for one figure: where its centre goes, and how big it may be."""

    centre: Point
    radius: float


@dataclass(frozen=True)
class Component:
    """One group of figures within a panel, and the slots it may fill.

    ``counts`` are how many of its slots may be filled. A component
    with a single slot is always full; one on a lattice can hold a
    varying number, which is what a rule about *how many* needs.

    ``arrangements`` says which slots a given count uses. Left to
    itself a count takes the first slots in reading order, which puts
    three figures along the top of an otherwise empty lattice — it
    reads as six figures missing rather than as three present. Naming
    the arrangement lets each count sit squarely in the panel.

    ``sizes`` narrows the size ladder. A figure on a three-by-three
    lattice is a sixth of the panel across, and at that size one step
    of the full ladder is a difference of about a fifth — there, but
    not something to ask a person to be sure about.
    """

    name: str
    slots: Tuple[Slot, ...]
    counts: Tuple[int, ...]
    arrangements: Dict[int, Tuple[int, ...]] = field(default_factory=dict)
    sizes: Optional[Tuple[float, ...]] = None

    @property
    def varies_in_number(self) -> bool:
        return len(self.counts) > 1

    def places(self, count: int) -> Tuple[Slot, ...]:
        """The slots a panel holding ``count`` figures fills."""
        chosen = self.arrangements.get(count)
        if chosen is None:
            return self.slots[:count]
        return tuple(self.slots[index] for index in chosen)


@dataclass(frozen=True)
class Layout:
    """A panel's arrangement, as one or two components."""

    name: str
    components: Tuple[Component, ...]
    #: How the layout reads when a puzzle is explained.
    describes: Tuple[str, ...]


def _lattice(across: int, radius_share: float = 0.86) -> Tuple[Slot, ...]:
    """``across`` by ``across`` evenly spaced slots filling the panel."""
    step = 1.0 / across
    room = step / 2.0 * radius_share
    return tuple(Slot(Point((column + 0.5) * step, (row + 0.5) * step), room)
                 for row in range(across) for column in range(across))


CENTRE = Layout(
    'centre',
    (Component('the figure', (Slot(Point(0.5, 0.5), 0.42),), (1,)),),
    ('one figure',))

#: Sizes for figures on a lattice: three steps rather than five, and so
#: further apart, because a lattice figure is a sixth of a panel across
#: and five steps there are five sizes nobody can rank.
LATTICE_SIZES: Tuple[float, ...] = _ladder(0.5, 0.95, 3)

GRID_FOUR = Layout(
    'grid of four',
    (Component('the figures', _lattice(2), (1, 2, 3, 4),
               sizes=LATTICE_SIZES),),
    ('up to four figures on a two-by-two lattice',))

#: Counts that fill whole rows of the lattice. A lattice holding five
#: of its nine places looks like a lattice with four things missing;
#: one holding six looks like two rows of three, which is a number a
#: person can see without counting.
GRID_NINE = Layout(
    'grid of nine',
    (Component('the figures', _lattice(3), (3, 6, 9),
               arrangements={3: (3, 4, 5),
                             6: (0, 1, 2, 6, 7, 8),
                             9: tuple(range(9))},
               sizes=LATTICE_SIZES),),
    ('figures on a three-by-three lattice',))

LEFT_RIGHT = Layout(
    'left and right',
    (Component('the left figure', (Slot(Point(0.27, 0.5), 0.22),), (1,)),
     Component('the right figure', (Slot(Point(0.73, 0.5), 0.22),), (1,))),
    ('a figure on the left', 'a figure on the right'))

UP_DOWN = Layout(
    'above and below',
    (Component('the upper figure', (Slot(Point(0.5, 0.27), 0.22),), (1,)),
     Component('the lower figure', (Slot(Point(0.5, 0.73), 0.22),), (1,))),
    ('a figure above', 'a figure below'))

#: The inner figure's room, set so that the largest inner figure is
#: still comfortably smaller than the smallest outer one. The two
#: components size themselves independently — that is the point of
#: having two — so nothing else stops a small outer figure and a large
#: inner one from coming out the same size and reading as one blob.
#: At these radii the inner figure is at most 58% of the outer's, and
#: usually far less.
INSIDE_OUTSIDE = Layout(
    'one inside another',
    (Component('the outer figure', (Slot(Point(0.5, 0.5), 0.44),), (1,)),
     Component('the inner figure', (Slot(Point(0.5, 0.5), 0.11),), (1,))),
    ('the outer figure', 'the figure inside it'))

#: Every layout, simplest first.
LAYOUTS: Tuple[Layout, ...] = (CENTRE, LEFT_RIGHT, UP_DOWN, INSIDE_OUTSIDE,
                               GRID_FOUR, GRID_NINE)

#: The layouts with a single component, which is all a one-rule puzzle
#: needs and all an easy one should carry.
SIMPLE_LAYOUTS: Tuple[Layout, ...] = (CENTRE, GRID_FOUR, GRID_NINE)



