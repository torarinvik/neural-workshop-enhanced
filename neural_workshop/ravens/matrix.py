# -*- coding: utf-8 -*-
"""Building a puzzle: layers, the grid, and the wrong answers.

A **layer** is one base rule plus its supplemental rules, worked out
over the whole grid. A **matrix** is one or two layers drawn on top of
one another — two layers is how a cell comes to hold a circle inside a
square, each obeying a rule of its own.

The bottom-right cell is the answer. The wrong answers are the hard
part and the reason this file is worth reading: a puzzle is only as
good as the choices it offers. Distractors that are obviously wrong
make the puzzle trivial, and a distractor that is secretly *right*
makes it unfair, so every candidate is checked against the answer and
against the choices already taken before it is accepted.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .rules import (LogicRule, Numerosity, Rule, ShapeRepetition,
                    generate_base_rule, generate_supplemental)
from .surfaces import BASIC_FILLS, Surface, same_picture
from .transforms import Location

#: How many candidate wrong answers may be rejected in a row before
#: the generator accepts that this puzzle has run dry. Reached only
#: when the rules produce so few distinct cells that there is nothing
#: left to offer; the puzzle is then thrown away rather than padded.
MAX_REJECTIONS = 500

#: How many wrong answers should hold the same number of shapes as the
#: right one. Without this the generator leaks the answer: a player who
#: never finds the rule can still count the shapes in each choice and
#: pick the odd one out, which happened in a third of two-layer puzzles
#: before the quota was imposed. Three matching choices leaves counting
#: unable to narrow the field below four.
COUNT_MATCH_QUOTA = 3

#: Rejections allowed while holding out for a matching shape count.
#: Some rule combinations — counting rules above all — cannot produce
#: one at all, so the quota gives way rather than throwing the puzzle
#: out for failing a preference.
COUNT_MATCH_BUDGET = 150

#: Ways a wrong answer can be built, for the explanation screen.
FROM_MATRIX = 'a cell copied from elsewhere in the grid'
MODIFIED = 'a cell from the grid with one property altered'
RECOMBINED = 'shapes from the grid combined differently'
PARTIAL = 'the answer with a layer missing'


class Layer:
    """One base rule and its supplementals, applied over the grid."""

    def __init__(self, rows: int, columns: int,
                 rules: Sequence[Rule]) -> None:
        if not rules:
            raise ValueError('a layer needs at least one rule')
        self.rows = rows
        self.columns = columns
        self.rules = list(rules)
        self.cells: List[List[List[Surface]]] = [
            [None for _ in range(columns)] for _ in range(rows)]
        self._build()

    def at(self, location: Location) -> List[Surface]:
        return self.cells[location.row][location.column]

    def _put(self, location: Location, shapes: List[Surface]) -> None:
        self.cells[location.row][location.column] = shapes

    def _build(self) -> None:
        for rule in self.rules:
            if isinstance(rule, LogicRule):
                self._build_logic(rule)
            else:
                self._build_walk(rule)
        for row in range(self.rows):
            for column in range(self.columns):
                if self.cells[row][column] is None:
                    self.cells[row][column] = []

    def _build_logic(self, rule: LogicRule) -> None:
        """Seed the corner block, then combine downward and rightward."""
        for index, base in enumerate(rule.route.bases):
            self._put(base, rule.seed(index, None))
        for row in range(self.rows):
            for column in range(self.columns):
                if self.cells[row][column] is not None:
                    continue
                if row > 1:
                    one = self.cells[row - 2][column]
                    two = self.cells[row - 1][column]
                else:
                    one = self.cells[row][column - 2]
                    two = self.cells[row][column - 1]
                self.cells[row][column] = rule.combine(one, two)

    def _build_walk(self, rule: Rule) -> None:
        """Seed the route's starting cells, then walk each of them."""
        for index, base in enumerate(rule.route.bases):
            self._put(base, rule.seed(index, self.at(base)))
            for location in rule.route.walk(base):
                source = self.at(rule.route.source(location))
                if not source:
                    continue
                self._put(location, rule.derive(source, self.at(location)))

    def uses_numerosity(self) -> bool:
        return any(isinstance(rule, Numerosity) for rule in self.rules)

    def describe(self) -> List[str]:
        """One line per rule, for the explanation screen."""
        lines = []
        for rule in self.rules:
            if isinstance(rule, LogicRule):
                lines.append(rule.description)
            else:
                lines.append('%s, %s' % (rule.description, rule.route.name))
        return lines


@dataclass
class Puzzle:
    """A finished puzzle: the grid, the choices, and the answer."""

    rows: int
    columns: int
    cell_size: int
    #: ``cells[row][column]`` — the shapes drawn in that cell. The
    #: bottom-right one is the answer and is not shown to the player.
    cells: List[List[List[Surface]]]
    #: The answer choices, in the order they are shown.
    choices: List[List[Surface]]
    #: Index into :attr:`choices` of the right one.
    answer: int
    #: One line per rule, per layer.
    explanation: List[str]
    #: How each wrong answer was built, for the explanation screen.
    origins: List[str]

    @property
    def question(self) -> List[Surface]:
        """The shapes the answer cell should hold."""
        return self.cells[self.rows - 1][self.columns - 1]


class _Stalled(Exception):
    """Raised when a puzzle cannot fill its answer choices."""


def _composite(layers: Sequence[Layer], location: Location) -> List[Surface]:
    """Every layer's shapes at one cell, stacked."""
    shapes: List[Surface] = []
    for layer in layers:
        shapes.extend(layer.at(location))
    return shapes


def _build_choices(layers: Sequence[Layer], rows: int, columns: int,
                   cells: List[List[List[Surface]]], count: int,
                   cell_size: int, rng: random.Random
                   ) -> Tuple[List[List[Surface]], List[str]]:
    """The wrong answers, built four different ways.

    Mixing the strategies matters. Cells copied from the grid catch a
    player who has found no rule and is picking something that merely
    looks like it belongs; altered cells catch one who has found the
    rule but applied it loosely; recombinations catch one who has
    found only one of two layers.
    """
    answer = cells[rows - 1][columns - 1]
    chosen: List[List[Surface]] = []
    origins: List[str] = []
    rejections = 0
    matching = 0
    spent_on_matching = 0

    strategies = [FROM_MATRIX, MODIFIED, RECOMBINED]
    if len(layers) > 1:
        strategies.append(PARTIAL)

    while len(chosen) < count - 1:
        if rejections >= MAX_REJECTIONS:
            raise _Stalled()
        origin = rng.choice(strategies)
        candidate = _candidate(origin, layers, rows, columns, cells,
                               cell_size, rng)
        if (not candidate
                or same_picture(candidate, answer)
                or any(same_picture(candidate, taken) for taken in chosen)):
            rejections += 1
            continue

        # Hold out for choices that hide the answer's shape count,
        # while there is still room to place them and budget to wait.
        wanted = COUNT_MATCH_QUOTA - matching
        if (wanted > 0 and len(candidate) != len(answer)
                and spent_on_matching < COUNT_MATCH_BUDGET
                and (count - 1) - len(chosen) <= wanted):
            spent_on_matching += 1
            rejections += 1
            continue

        if len(candidate) == len(answer):
            matching += 1
        chosen.append(candidate)
        origins.append(origin)
        rejections = 0
    return chosen, origins


def _candidate(origin: str, layers: Sequence[Layer], rows: int, columns: int,
               cells: List[List[List[Surface]]], cell_size: int,
               rng: random.Random) -> List[Surface]:
    """One candidate wrong answer, built the way ``origin`` says."""
    if origin == PARTIAL:
        keep = rng.sample(range(len(layers)),
                          rng.randrange(1, len(layers)))
        answer_cell = Location(rows - 1, columns - 1)
        return _composite([layers[index] for index in sorted(keep)],
                          answer_cell)

    if origin == FROM_MATRIX:
        return list(_composite(layers, _other_cell(rows, columns, rng)))

    if origin == MODIFIED:
        return _modified(layers, rows, columns, cell_size, rng)

    return _recombined(layers, rows, columns, rng)


def _other_cell(rows: int, columns: int, rng: random.Random) -> Location:
    """A cell of the grid that is not the answer."""
    while True:
        location = Location(rng.randrange(rows), rng.randrange(columns))
        if location != Location(rows - 1, columns - 1):
            return location


def _modified(layers: Sequence[Layer], rows: int, columns: int,
              cell_size: int, rng: random.Random) -> List[Surface]:
    """A cell from one layer with its shading or its size altered.

    When the layer counts shapes, every copy is changed the same way.
    Changing one of four identical shapes would leave a cell that no
    rule could ever produce, and a choice that is visibly malformed is
    not a distractor — it is a hint about which choices to ignore.
    """
    layer = layers[rng.randrange(len(layers))]
    shapes = layer.at(_other_cell(rows, columns, rng))
    if not shapes:
        return []

    if rng.random() < 0.5:
        fill = rng.choice(BASIC_FILLS)
        change = lambda shape: shape.filled(fill)
    else:
        change = lambda shape: shape.scaled(shape.scale * 0.66)

    if layer.uses_numerosity():
        return [change(shape) for shape in shapes]
    index = rng.randrange(len(shapes))
    return [change(shape) if position == index else shape
            for position, shape in enumerate(shapes)]


def _recombined(layers: Sequence[Layer], rows: int, columns: int,
                rng: random.Random) -> List[Surface]:
    """Shapes taken from scattered cells and put in one cell together.

    Each layer contributes from a cell of its own, and only some of
    what it finds, so the result is made of parts the player has seen
    without being any cell they have seen.
    """
    shapes: List[Surface] = []
    for layer in rng.sample(list(layers), rng.randrange(1, len(layers) + 1)):
        found = layer.at(Location(rng.randrange(rows), rng.randrange(columns)))
        for shape in found:
            if rng.random() < 0.5 and not any(shape.looks_like(taken)
                                              for taken in shapes):
                shapes.append(shape)
    return shapes


def generate(rows: int = 3, columns: int = 3, layers: int = 1,
             rules_per_layer: int = 1, choices: int = 8,
             cell_size: int = 100, seed: Optional[int] = None,
             attempts: int = 60) -> Puzzle:
    """Build one puzzle.

    ``rules_per_layer`` is how many rules a layer carries, exactly,
    not at most. An adaptive run moves the player up and down this
    number, so it has to mean something: drawing a random count up to
    it — what the original did — let the hardest setting hand out
    one-rule puzzles, and a level that sometimes means level one
    cannot be climbed.

    A logic layer is the exception. Combining two cells is already the
    whole of what a layer can say, and the original allowed it no
    further rules; such a layer carries one rule at any setting.

    A puzzle whose rules leave too few distinct cells to fill the
    answer choices is discarded and rebuilt rather than padded out with
    blanks. Blank choices were what the original did, and they leak the
    answer: a player who sees three empty boxes knows to ignore them.
    """
    rng = random.Random(seed)
    for _ in range(attempts):
        try:
            return _attempt(rows, columns, layers, rules_per_layer,
                            choices, cell_size, rng)
        except _Stalled:
            continue
    raise RuntimeError('could not build a puzzle with %d layers and %d rules'
                       % (layers, rules_per_layer))


def _attempt(rows: int, columns: int, layer_count: int, rules_per_layer: int,
             choices: int, cell_size: int, rng: random.Random) -> Puzzle:
    """One try at a puzzle, which may run dry and be thrown away."""
    built: List[Layer] = []
    for _ in range(layer_count):
        base = generate_base_rule(rows, columns, cell_size, rng)
        rules: List[Rule] = [base]
        if isinstance(base, ShapeRepetition):
            for _ in range(rules_per_layer - 1):
                rules.append(generate_supplemental(rows, columns, cell_size,
                                                   rng))
        built.append(Layer(rows, columns, rules))

    cells = [[_composite(built, Location(row, column))
              for column in range(columns)] for row in range(rows)]
    if not cells[rows - 1][columns - 1]:
        raise _Stalled()        # an empty answer cell is not a question

    wrong, origins = _build_choices(built, rows, columns, cells,
                                    choices, cell_size, rng)

    answer_at = rng.randrange(choices)
    ordered = list(wrong)
    ordered.insert(answer_at, cells[rows - 1][columns - 1])
    placed_origins = list(origins)
    placed_origins.insert(answer_at, 'the answer')

    explanation: List[str] = []
    for index, layer in enumerate(built):
        prefix = '' if layer_count == 1 else 'layer %d: ' % (index + 1)
        explanation.extend(prefix + line for line in layer.describe())

    return Puzzle(rows=rows, columns=columns, cell_size=cell_size,
                  cells=cells, choices=ordered, answer=answer_at,
                  explanation=explanation, origins=placed_origins)
