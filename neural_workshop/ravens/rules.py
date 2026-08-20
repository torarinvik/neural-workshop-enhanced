# -*- coding: utf-8 -*-
"""What changes from one cell to the next.

A layer is built by one *base* rule, which decides what shapes appear
at all, optionally followed by *supplemental* rules, which each change
one property of those shapes as the route is walked. Stacking them is
where difficulty comes from: one rule is a pattern anybody sees, three
interacting rules is a puzzle.

Base rules come in two kinds. Shape repetition seeds the route's
starting cells and carries the shapes along it unchanged, leaving the
supplemental rules to do the varying. The logic rules are different in
shape: they seed a two-by-two corner and fill every other cell by
combining two cells already known, so they never walk a route at all.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence, Tuple

from .geometry import Point
from .surfaces import (GREYS, Palette, Surface, WHITE, generate_surface)
from .transforms import CornerOut, LogicRoute, Route, generate_route

#: How small a shrinking rule may leave a shape by the end of its
#: route, as a share of the size it started at.
#:
#: The step is worked back from this rather than fixed, because it
#: compounds and the routes are not the same length. The original
#: shrank by a third at every step, which is fine down a column of
#: three — two steps, ending at 44% — and ruinous on the route that
#: sweeps outward from the top-left corner, which is eight steps long
#: and ended at 3.6%. Shapes became dots, and a puzzle whose answer
#: choices are eight indistinguishable dots cannot be answered at all.
SMALLEST_SCALE = 0.4

#: How far a rotation rule turns a shape at each step, in degrees.
ROTATION_STEP = 45

#: Shapes a logic rule is seeded with. Fewer and the combinations
#: repeat; more and a cell becomes an unreadable pile.
MIN_LOGIC_SHAPES = 3
MAX_LOGIC_SHAPES = 5

#: Most shapes a numerosity rule starts a route with.
MAX_INITIAL_COUNT = 2


class Rule:
    """A change applied along a route."""

    #: Shown to the player when a puzzle is explained.
    description = 'rule'

    def __init__(self, route: Route) -> None:
        self.route = route

    def seed(self, base_index: int,
             existing: Optional[Sequence[Surface]]) -> List[Surface]:
        """The shapes at one of the route's starting cells."""
        raise NotImplementedError

    def derive(self, source: Sequence[Surface],
               existing: Optional[Sequence[Surface]]) -> List[Surface]:
        """The shapes one step along the route from ``source``.

        ``existing`` is what earlier rules in this layer already put in
        this cell, or ``None`` if this rule is the first to reach it.
        """
        raise NotImplementedError


# --- base rules ---------------------------------------------------------

class ShapeRepetition(Rule):
    """Each starting cell gets its own shape, carried along the route."""

    description = 'the same shape repeats'

    def __init__(self, route: Route,
                 seeds: Sequence[Sequence[Surface]]) -> None:
        super().__init__(route)
        self.seeds = [list(group) for group in seeds]

    def seed(self, base_index: int,
             existing: Optional[Sequence[Surface]]) -> List[Surface]:
        return list(self.seeds[base_index % len(self.seeds)])

    def derive(self, source: Sequence[Surface],
               existing: Optional[Sequence[Surface]]) -> List[Surface]:
        return list(source)


class LogicRule(Rule):
    """Every cell is two earlier cells combined.

    The top-left two-by-two block is given; from there each cell is
    the combination of the two cells above it, or of the two to its
    left on the first two rows.
    """

    def __init__(self, route: Route, shapes: Sequence[Surface],
                 rng: random.Random) -> None:
        super().__init__(route)
        self.shapes = list(shapes)
        self.assignments = self._assign(rng)

    def _assign(self, rng: random.Random) -> List[List[Surface]]:
        """Deal the shapes out over the given cells.

        Redealt until every shape is used somewhere and every given
        cell has something in it: a shape that appears nowhere cannot
        be reasoned about, and an empty starting cell makes the first
        combination trivially empty too.
        """
        count = len(self.route.bases)
        while True:
            assignments: List[List[Surface]] = [[] for _ in range(count)]
            for index in range(count):
                for _ in range(rng.randrange(len(self.shapes) + 1)):
                    shape = rng.choice(self.shapes)
                    if not any(shape.looks_like(chosen)
                               for chosen in assignments[index]):
                        assignments[index].append(shape)
            used = {shape.kind + shape.fill.name + str(shape.width)
                    for group in assignments for shape in group}
            if (all(assignments)
                    and len(used) >= len({shape.kind + shape.fill.name
                                          + str(shape.width)
                                          for shape in self.shapes})):
                return assignments

    def seed(self, base_index: int,
             existing: Optional[Sequence[Surface]]) -> List[Surface]:
        return list(self.assignments[base_index])

    def derive(self, source: Sequence[Surface],
               existing: Optional[Sequence[Surface]]) -> List[Surface]:
        raise NotImplementedError('a logic rule combines two cells')

    def combine(self, one: Sequence[Surface],
                two: Sequence[Surface]) -> List[Surface]:
        raise NotImplementedError


class LogicalAnd(LogicRule):
    """Only shapes present in both cells survive."""

    description = 'shapes in both cells are kept'

    def combine(self, one: Sequence[Surface],
                two: Sequence[Surface]) -> List[Surface]:
        return [shape for shape in one
                if any(shape.looks_like(other) for other in two)]


class LogicalOr(LogicRule):
    """Every shape from either cell appears, once."""

    description = 'shapes from either cell are kept'

    def combine(self, one: Sequence[Surface],
                two: Sequence[Surface]) -> List[Surface]:
        combined = list(one)
        for shape in two:
            if not any(shape.looks_like(other) for other in combined):
                combined.append(shape)
        return combined


class LogicalXor(LogicRule):
    """Only shapes in exactly one of the two cells survive."""

    description = 'shapes in exactly one of the two cells are kept'

    def combine(self, one: Sequence[Surface],
                two: Sequence[Surface]) -> List[Surface]:
        return ([shape for shape in one
                 if not any(shape.looks_like(other) for other in two)]
                + [shape for shape in two
                   if not any(shape.looks_like(other) for other in one)])


# --- supplemental rules -------------------------------------------------

class Supplemental(Rule):
    """A rule that changes shapes another rule already put in place.

    Reaching a starting cell first, it leaves what it finds alone; the
    change only happens along the route. If it finds nothing at all —
    no earlier rule has run — it has nothing to change and passes the
    previous cell's shapes through.
    """

    def seed(self, base_index: int,
             existing: Optional[Sequence[Surface]]) -> List[Surface]:
        return list(existing) if existing is not None else []

    def change(self, shape: Surface, source: Surface) -> Surface:
        """``shape``, changed one step on from ``source``."""
        raise NotImplementedError

    def derive(self, source: Sequence[Surface],
               existing: Optional[Sequence[Surface]]) -> List[Surface]:
        if existing is None:
            return list(source)
        return [self.change(shape, source[0]) for shape in existing]


class ApplyRotation(Supplemental):
    """Each step turns the shapes a further eighth of a turn."""

    description = 'the shape turns'

    def change(self, shape: Surface, source: Surface) -> Surface:
        return shape.rotated(ROTATION_STEP + source.rotation)


class ApplyScaling(Supplemental):
    """Each step shrinks the shapes, by the same factor every time.

    The factor is chosen so that the far end of this particular route
    lands on :data:`SMALLEST_SCALE`, whether the route is two steps
    long or eight.
    """

    description = 'the shape shrinks'

    def __init__(self, route: Route) -> None:
        super().__init__(route)
        steps = len(route.walk(route.bases[0])) or 1
        self.factor = SMALLEST_SCALE ** (1.0 / steps)

    def change(self, shape: Surface, source: Surface) -> Surface:
        return shape.scaled(self.factor * source.scale)


class FillRepetition(Supplemental):
    """Each route keeps one fill, and the routes differ.

    The fill is chosen by which starting cell the route began at, so
    it is constant along a route and varies across them — a column of
    black shapes beside a column of white ones.
    """

    def __init__(self, route: Route, palette: Palette = GREYS) -> None:
        super().__init__(route)
        self.palette = palette
        self.fills = list(palette.basic)

    @property
    def description(self) -> str:
        return 'the %s is constant along the route' % self.palette.noun

    def seed(self, base_index: int,
             existing: Optional[Sequence[Surface]]) -> List[Surface]:
        if existing is None:
            return []
        fill = self.fills[base_index % len(self.fills)]
        return [shape.filled(fill) for shape in existing]

    def change(self, shape: Surface, source: Surface) -> Surface:
        return shape.filled(source.fill)


class ChangeFill(Supplemental):
    """Each step moves the fill one place along a cycle of five."""

    def __init__(self, route: Route, palette: Palette = GREYS) -> None:
        super().__init__(route)
        self.palette = palette
        self.fills = list(palette.ramp)

    @property
    def description(self) -> str:
        return 'the %s changes' % self.palette.noun

    def seed(self, base_index: int,
             existing: Optional[Sequence[Surface]]) -> List[Surface]:
        if existing is None:
            return []
        return [shape.filled(self.fills[0]) for shape in existing]

    def change(self, shape: Surface, source: Surface) -> Surface:
        names = [fill.name for fill in self.fills]
        position = (names.index(source.fill.name) + 1) % len(self.fills)
        return shape.filled(self.fills[position])


class Numerosity(Supplemental):
    """Each step adds one more copy of the shape.

    The copies are laid out on a small grid inside the cell and shrunk
    to fit, so a cell holding four of them is no more crowded than one
    holding one. Counting is the whole rule, which is why the copies
    are identical and evenly placed.
    """

    description = 'one more copy appears at each step'

    def __init__(self, route: Route, cell_size: int, rows: int, columns: int,
                 initial: int) -> None:
        super().__init__(route)
        self.cell_size = cell_size
        self.initial = initial
        # How many copies the longest walk will have to hold. The
        # corner-out route is one walk over every cell, so it reaches
        # far more than a route that restarts on each row.
        if isinstance(route, CornerOut):
            reach = rows + columns - 1
        else:
            reach = max(rows, columns) + initial - 1
        self.positions = max(1, math.ceil(math.sqrt(reach)))
        self.step_size = cell_size / float(self.positions + 1)
        self.scaling = 0.75 / self.positions

    def _laid_out(self, shapes: Sequence[Surface],
                  rescale) -> List[Surface]:
        """Put ``shapes`` on the grid of positions, shrunk to fit."""
        placed = []
        for index, shape in enumerate(shapes):
            column = index % self.positions
            row = index // self.positions
            placed.append(shape.scaled(rescale(shape))
                          .moved(Point((column + 1) * self.step_size,
                                       (row + 1) * self.step_size)))
        return placed

    def seed(self, base_index: int,
             existing: Optional[Sequence[Surface]]) -> List[Surface]:
        if not existing:
            return []
        return self._laid_out([existing[0]] * self.initial,
                              lambda shape: self.scaling)

    def derive(self, source: Sequence[Surface],
               existing: Optional[Sequence[Surface]]) -> List[Surface]:
        if not existing:
            return list(source)
        return self._laid_out([existing[0]] * (len(source) + 1),
                              lambda shape: self.scaling * shape.scale)


#: The supplemental rules, in the order the original picked between them.
SUPPLEMENTALS: Tuple[type, ...] = (ApplyScaling, FillRepetition,
                                   ApplyRotation, Numerosity, ChangeFill)

#: Which property of a shape each rule writes.
#:
#: Two rules in one layer that write the same property do not stack —
#: the second simply overwrites the first, and the first becomes a rule
#: the puzzle claims to follow while showing no sign of it. That is
#: worse than having one fewer rule: a player who takes the puzzle
#: seriously looks for it and finds nothing.
#:
#: Counting shares the size family because it sizes its copies to fit
#: the cell. A scaling rule applied afterwards resets that, and the
#: copies spill out of the cell they were laid out for.
RULE_WRITES = {
    ApplyRotation: 'turn',
    ApplyScaling: 'size',
    Numerosity: 'size',
    ChangeFill: 'fill',
    FillRepetition: 'fill',
}


def choose_supplementals(count: int, rng: random.Random) -> List[type]:
    """``count`` supplemental rules, no two writing the same property."""
    spare = list(SUPPLEMENTALS)
    rng.shuffle(spare)
    chosen: List[type] = []
    taken: List[str] = []
    for kind in spare:
        if len(chosen) >= count:
            break
        if RULE_WRITES[kind] in taken:
            continue
        chosen.append(kind)
        taken.append(RULE_WRITES[kind])
    return chosen


def generate_base_rule(rows: int, columns: int, cell_size: int,
                       rng: random.Random, palette: Palette = GREYS,
                       kind: type = None, route_kind: type = None) -> Rule:
    """A base rule: shape repetition, or one of the three logic rules.

    Logic rules need a grid with room for a two-by-two seed and cells
    left over to derive, so they are only offered above two-by-two.
    """
    logic_kinds = (LogicalOr, LogicalAnd, LogicalXor)
    if kind is None:
        if rows > 2 and columns > 2 and rng.random() < 0.5:
            kind = rng.choice(logic_kinds)
        else:
            kind = ShapeRepetition

    if kind is ShapeRepetition:
        route = generate_route(rows, columns, rng, route_kind)
        return ShapeRepetition(route,
                               _distinct_seeds(len(route.bases), cell_size,
                                               rng, palette))

    count = rng.randrange(MIN_LOGIC_SHAPES, MAX_LOGIC_SHAPES + 1)
    shapes: List[Surface] = []
    while len(shapes) < count:
        candidate = generate_surface(cell_size, rng, fills=(WHITE,))
        if not any(candidate.looks_like(chosen) for chosen in shapes):
            shapes.append(candidate)
    return kind(LogicRoute(rows, columns), shapes, rng)


def _distinct_seeds(count: int, cell_size: int, rng: random.Random,
                    palette: Palette = GREYS) -> List[List[Surface]]:
    """One shape per starting cell, no two of the same kind.

    Repeating a kind across starting cells would make two routes look
    alike at a glance, which reads as a rule that is not there.
    """
    seeds: List[List[Surface]] = []
    used: List[str] = []
    for _ in range(count):
        shape = generate_surface(cell_size, rng, palette.basic)
        while shape.kind in used:
            shape = generate_surface(cell_size, rng, palette.basic)
        used.append(shape.kind)
        seeds.append([shape])
    return seeds


def generate_supplemental(rows: int, columns: int, cell_size: int,
                          rng: random.Random, palette: Palette = GREYS,
                          kind: type = None,
                          route_kind: type = None) -> Supplemental:
    """One supplemental rule, on a route of its own."""
    route = generate_route(rows, columns, rng, route_kind)
    if kind is None:
        kind = rng.choice(SUPPLEMENTALS)
    if kind is Numerosity:
        return Numerosity(route, cell_size, rows, columns,
                          rng.randrange(1, MAX_INITIAL_COUNT + 1))
    if kind is FillRepetition:
        return FillRepetition(route, palette)
    if kind is ChangeFill:
        return ChangeFill(route, palette)
    return kind(route)
