# -*- coding: utf-8 -*-
"""Building a matrix, and the answers offered for it.

A puzzle is one layout, held for all nine panels, with up to three
components in it. Each component has a handful of attributes — which
figure, how big, what colour, how many — and each attribute is given a
rule that says what it does across a row. Run the rules, and the nine
panels fall out.

Every figure of a component shares that component's attributes within
a panel. Three figures on a lattice are three of the *same* figure at
the same size and colour, not three unrelated ones. That is what makes
a panel readable at a glance, and it is the difference between a rule
about *how many* and a jumble that happens to have three things in it.

**How the wrong answers are built.** A handful of the puzzle's
attributes are targeted, each is given one wrong value, and the wrong
answers are the right one with fixed *combinations* of those wrong
values swapped in — chosen so that every targeted attribute is wrong
in exactly half of the answers offered. That balance is the whole
point. The obvious construction — the right answer with one attribute
changed, drawn a few times — leaves the right answer agreeing with
every distractor on everything but its one change, so it sits at the
centre of the set and "pick the most typical answer" finds it without
reading the matrix at all. The RAVEN dataset shipped with exactly this
leak and was solved from its answer lists alone. Balanced, a vote on
any attribute is a dead tie, and the only way in is the rules.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .figures import (Figure, Panel, SHAPES, SIZES, _ladder, same_panel,
                      turn_ladder)
from .layouts import (CENTRE, GRID_FOUR, GRID_NINE, INSIDE_OUTSIDE,
                      PAIRED_LAYOUTS, SIMPLE_LAYOUTS, TRIPTYCH,
                      Component, Layout)
from .palette import GREYS, Palette
from .rules import (ACROSS, Constant, Logic, Rule, apply_rule, choose_rule)

#: Tries before a puzzle is given up on and built again from scratch.
PATIENCE = 400

#: Sizes for the easiest grades: three steps, far apart, so "bigger"
#: is something a child sees rather than judges.
COARSE_SIZES: Tuple[float, ...] = _ladder(0.45, 0.95, 3)

#: Sizes for the hardest grades: seven steps, each about sixteen per
#: cent up from the last. A rule that has been *found* still takes
#: care to apply, which is a different kind of difficulty from more
#: rules — and a cheaper one to give, because nothing else changes.
FINE_SIZES: Tuple[float, ...] = _ladder(0.38, 0.95, 7)


@dataclass(frozen=True)
class Grade:
    """Everything one difficulty level fixes about its puzzles.

    Difficulty is not one dial. A grade sets how many answers are
    offered, which layouts may carry the matrix, how many attributes
    carry a live rule, which rules those may be, how finely sizes are
    graded, how often a rotation is added, and whether the logic rule
    — the hardest thing here — is on the table.
    """

    name: str
    #: How many answers are offered: four for the easy grades, as the
    #: children's form of the real test does, eight otherwise.
    choices: int
    #: How many attributes carry a rule other than holding constant.
    active: int
    layouts: Tuple[Layout, ...]
    #: Rule names the live rules may be drawn from; ``None`` is all.
    rules: Optional[Tuple[str, ...]]
    sizes: Tuple[float, ...]
    #: How often a rotation rule is added where one can be seen.
    turn_chance: float
    #: Whether a lattice's *how many* may become *which places*,
    #: governed by combining two panels into a third.
    logic: bool


#: The difficulty ladder, easiest first.
#:
#: Grade 1 has no live rule at all: every panel is the same picture,
#: and the question is only "which piece matches?" — pattern
#: completion, the genuinely easy end of the real test, answerable by
#: a five-year-old. From there each grade turns one dial: more rules,
#: then more components to carry them, then the logic rule, then
#: finer sizes, until grade 12 runs nine live rules at once on three
#: components — more than a person tracks, on purpose.
GRADES: Tuple[Grade, ...] = (
    Grade('matching', 4, 0, (CENTRE, GRID_FOUR), (), COARSE_SIZES,
          0.0, False),
    Grade('one step', 4, 1, (CENTRE,), ('progression',), COARSE_SIZES,
          0.0, False),
    Grade('one rule', 4, 1, SIMPLE_LAYOUTS,
          ('progression', 'distribute three'), COARSE_SIZES, 0.0, False),
    Grade('two rules', 8, 2, SIMPLE_LAYOUTS, None, SIZES, 0.0, False),
    Grade('three rules', 8, 3, SIMPLE_LAYOUTS, None, SIZES, 0.2, False),
    Grade('two parts', 8, 3, PAIRED_LAYOUTS, None, SIZES, 0.2, False),
    Grade('four rules', 8, 4, PAIRED_LAYOUTS, None, SIZES, 0.25, False),
    Grade('five rules', 8, 5, PAIRED_LAYOUTS + (GRID_NINE,), None, SIZES,
          0.25, True),
    Grade('six rules', 8, 6, (INSIDE_OUTSIDE, TRIPTYCH, GRID_NINE), None,
          FINE_SIZES, 0.3, True),
    Grade('seven rules', 8, 7, (TRIPTYCH, INSIDE_OUTSIDE, GRID_NINE), None,
          FINE_SIZES, 0.4, True),
    Grade('eight rules', 8, 8, (TRIPTYCH,), None, FINE_SIZES, 0.5, True),
    Grade('everything moves', 8, 9, (TRIPTYCH,), None, FINE_SIZES,
          0.6, True),
)


@dataclass
class Attribute:
    """One thing about a component that a rule can govern."""

    name: str
    #: What it is called when the puzzle is explained.
    noun: str
    ladder: Tuple
    rule: Rule = field(default_factory=Constant)
    #: ``values[row][column]`` once the rule has been run.
    values: List[List] = field(default_factory=list)

    def at(self, row: int, column: int):
        return self.values[row][column]

    def alternatives(self, value) -> List:
        """Every value a wrong answer could swap in for ``value``.

        For a ladder attribute, the other rungs. For the logic rule's
        place-sets, every set one flip away — one place added or one
        removed — so the wrong answer is a near miss rather than a
        different picture entirely.
        """
        if isinstance(value, frozenset):
            found = []
            for place in self.ladder:
                flipped = value ^ {place}
                if flipped:
                    found.append(frozenset(flipped))
            return found
        return [rung for rung in self.ladder if rung != value]


@dataclass
class Puzzle:
    """A finished matrix: the panels, the answers, and which is right."""

    layout: Layout
    palette: Palette
    #: ``panels[row][column]``. The last one is the answer and is not
    #: shown to the player.
    panels: List[List[Panel]]
    choices: List[Panel]
    answer: int
    explanation: List[str]

    @property
    def question(self) -> Panel:
        return self.panels[ACROSS - 1][ACROSS - 1]


class _Stalled(Exception):
    """This attempt cannot be finished; build another."""


def _attributes(component: Component, palette: Palette,
                grade: Grade) -> List[Attribute]:
    """The attributes of one component, in the order rules are dealt."""
    found = [Attribute('shape', 'which figure', SHAPES),
             Attribute('size', 'the size', component.sizes or grade.sizes),
             Attribute('colour', 'the %s' % palette.noun, palette.fills)]
    if component.varies_in_number:
        found.append(Attribute('number', 'how many', component.counts))
    return found


def _spots(component: Component, held) -> Tuple:
    """The slots a panel fills, from a count or a set of places.

    A count takes its named arrangement, fixed per count rather than
    drawn, so that a matrix whose rule is about how many reads as
    figures being added rather than as figures moving about. A set of
    places — the logic rule's values — *is* the arrangement.
    """
    if isinstance(held, frozenset):
        return tuple(component.slots[index] for index in sorted(held))
    return component.places(held)


def _build_panels(layout: Layout,
                  dealt: List[List[Attribute]]) -> List[List[Panel]]:
    """Run every component's attributes out into nine panels."""
    panels: List[List[Panel]] = []
    for row in range(ACROSS):
        line: List[Panel] = []
        for column in range(ACROSS):
            figures: List[Figure] = []
            for part, (component, attributes) in enumerate(
                    zip(layout.components, dealt)):
                by_name = dict((one.name, one) for one in attributes)
                held = (by_name['number'].at(row, column)
                        if 'number' in by_name else component.counts[0])
                shape = by_name['shape'].at(row, column)
                size = by_name['size'].at(row, column)
                fill = by_name['colour'].at(row, column)
                angle = (by_name['angle'].at(row, column)
                         if 'angle' in by_name else 0)
                for slot in _spots(component, held):
                    figures.append(Figure(shape=shape, centre=slot.centre,
                                          radius=slot.radius * size,
                                          fill=fill, angle=angle,
                                          component=part))
            line.append(tuple(figures))
        panels.append(line)
    return panels


def _deal_rules(layout: Layout, palette: Palette, grade: Grade,
                rng: random.Random) -> List[List[Attribute]]:
    """Give every attribute a rule, ``grade.active`` of them live.

    Which attributes get the interesting rules is drawn rather than
    fixed, so two puzzles at the same grade are not the same puzzle
    with different figures in it. A grade asking for more live rules
    than the layout has attributes simply lights them all.
    """
    dealt = [_attributes(component, palette, grade)
             for component in layout.components]

    slots = [(component, attribute)
             for component, attributes in zip(layout.components, dealt)
             for attribute in attributes]
    rng.shuffle(slots)
    for index, (component, attribute) in enumerate(slots):
        if index >= grade.active:
            attribute.rule = Constant()
        elif (attribute.name == 'number' and grade.logic
                and len(component.slots) >= 4 and rng.random() < 0.5):
            # The count becomes a set of places, and the rule becomes
            # one about combining panels. The ladder becomes the
            # universe of places — which is both what the rule draws
            # from and what a near miss flips within.
            attribute.noun = 'where the figures sit'
            attribute.ladder = tuple(range(len(component.slots)))
            attribute.rule = Logic(rng.choice(('or', 'and', 'xor')))
        else:
            attribute.rule = choose_rule(
                attribute.ladder, rng,
                allow_arithmetic=(attribute.name == 'number'),
                allowed=grade.rules)

    for attributes in dealt:
        by_name = dict((one.name, one) for one in attributes)
        for attribute in attributes:
            attribute.values = apply_rule(attribute.rule, attribute.ladder,
                                          rng)
        # A turn is only offered when the figure is the same all the
        # way across, because how far a figure must turn before it
        # looks turned depends on how symmetrical it is, and there is
        # one ladder per matrix. A circle's ladder has one rung — it
        # looks the same every way up — so a circle is never turned
        # without that having to be said anywhere.
        shape = by_name['shape']
        if isinstance(shape.rule, Constant) \
                and rng.random() < grade.turn_chance:
            ladder = turn_ladder(shape.at(0, 0))
            turning = Attribute('angle', 'the way it faces', ladder)
            turning.rule = choose_rule(ladder, rng)
            turning.values = apply_rule(turning.rule, ladder, rng)
            attributes.append(turning)
        # No angle attribute at all otherwise, rather than one held at
        # zero. A held attribute is still something a wrong answer may
        # change, and a tilted figure among eight upright ones is a
        # wrong answer anybody can dismiss without reading the matrix.
        # Panels default to upright when no angle attribute is present.
    return dealt


def _explain(layout: Layout, dealt: List[List[Attribute]]) -> List[str]:
    """One line per rule that actually does something."""
    lines: List[str] = []
    for describes, attributes in zip(layout.describes, dealt):
        for attribute in attributes:
            if isinstance(attribute.rule, Constant):
                continue
            said = attribute.rule.describe(attribute.noun)
            if len(layout.components) > 1:
                said = '%s — %s' % (describes, said)
            lines.append(said)
    return lines or ['every panel holds the same picture']


def _targets(layout: Layout,
             dealt: List[List[Attribute]]) -> List[Tuple[int, Attribute]]:
    """Every attribute a wrong answer could change, as (component, attr)."""
    return [(index, attribute)
            for index, attributes in enumerate(dealt)
            for attribute in attributes
            if len(attribute.ladder) > 1]


def _panel_with(layout: Layout, dealt: List[List[Attribute]],
                swaps: Dict[Tuple[int, str], object]) -> Panel:
    """The right answer with the values in ``swaps`` swapped in.

    Rebuilt through the same machinery rather than edited in place, so
    a wrong answer is always a panel the layout could have produced —
    figures in their proper slots, at a size off the ladder. A panel
    that could not exist is answerable by noticing that it could not.
    """
    figures: List[Figure] = []
    for index, (component, group) in enumerate(zip(layout.components, dealt)):
        by_name = dict((one.name, one) for one in group)

        def value(name, default=None):
            if (index, name) in swaps:
                return swaps[(index, name)]
            return (by_name[name].at(ACROSS - 1, ACROSS - 1)
                    if name in by_name else default)

        held = value('number', component.counts[0])
        for slot in _spots(component, held):
            figures.append(Figure(shape=value('shape'), centre=slot.centre,
                                  radius=slot.radius * value('size'),
                                  fill=value('colour'),
                                  angle=value('angle', 0), component=index))
    return tuple(figures)


def _design(choices: int, targets: int) -> Tuple[int, Tuple[Tuple[int, ...],
                                                            ...]]:
    """Which targeted attributes each wrong answer alters.

    Returns how many attributes to target and, for each wrong answer,
    the indices of the targets it swaps. Every design here has each
    target altered in exactly half of the ``choices`` answers offered
    (the right answer counting as unaltered), which is the balance the
    module docstring is about.

    The designs, by how many targets the puzzle can offer:

    * four answers — two targets, each alone and then both together;
    * three targets — every combination of the three;
    * four or more — four targets: all six pairs, plus all four at
      once.

    Four is the ceiling on purpose. A wider design exists — seven
    targets, each answer altering a run of four round a circle — and
    it keeps every single attribute balanced, but it leaks the other
    way: the all-correct answer agrees with the wrong ones *less* than
    they agree with each other, and "pick the odd one out" found it
    44 per cent of the time. With four targets and the quadruple in
    the set, the right answer's agreements sit inside the pack. Rules
    beyond the four targeted still have to be read to know *which*
    four the answers disagree about, but a wrong answer never
    challenges them directly.
    """
    if choices == 4:
        return 2, ((0,), (1,), (0, 1))
    if targets >= 4:
        return 4, ((0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2),
                   (0, 1, 2, 3))
    return 3, tuple(tuple(bit for bit in range(3) if mask >> bit & 1)
                    for mask in range(1, 8))


def _build_choices(puzzle_panels: List[List[Panel]], layout: Layout,
                   dealt: List[List[Attribute]], grade: Grade,
                   rng: random.Random) -> Tuple[List[Panel], int]:
    """The answers offered, and where the right one was put."""
    answer = puzzle_panels[ACROSS - 1][ACROSS - 1]
    if not answer:
        raise _Stalled()

    targets = _targets(layout, dealt)
    rng.shuffle(targets)
    # Live rules first: a wrong answer that breaks a rule the matrix
    # actually runs is a test of that rule, where one that breaks a
    # held attribute only tests whether the player noticed the theme.
    targets.sort(key=lambda pair: isinstance(pair[1].rule, Constant))

    width, rows = _design(grade.choices, len(targets))
    picked: List[Tuple[Tuple[int, str], object]] = []
    names: List[Tuple[int, str]] = []
    for which, attribute in targets:
        if len(picked) == width:
            break
        # A figure swap can land on a circle and erase the turn, so a
        # shape and an angle of the same component never both serve:
        # two combinations would collapse into one picture.
        if attribute.name in ('shape', 'angle') and any(
                that == which and name in ('shape', 'angle')
                for that, name in names):
            continue
        options = attribute.alternatives(attribute.at(ACROSS - 1,
                                                      ACROSS - 1))
        if not options:
            continue
        picked.append(((which, attribute.name), rng.choice(options)))
        names.append((which, attribute.name))
    if len(picked) < width:
        raise _Stalled()

    wrong: List[Panel] = []
    for altered in rows:
        swaps = dict(picked[index] for index in altered)
        wrong.append(_panel_with(layout, dealt, swaps))

    # The design guarantees distinct combinations, not distinct
    # pictures: two different swaps can still collide — a size swap on
    # a figure whose slot rounds both to the same radius, say. Rare,
    # and a rebuild is cheaper than a proof.
    offered = [answer] + wrong
    for first in range(len(offered)):
        for second in range(first + 1, len(offered)):
            if same_panel(offered[first], offered[second]):
                raise _Stalled()

    where = rng.randrange(grade.choices)
    choices = list(wrong)
    choices.insert(where, answer)
    return choices, where


def generate(level: int = 1, seed: Optional[int] = None,
             palettes: Sequence[Palette] = (GREYS,),
             attempts: int = 80) -> Puzzle:
    """Build one puzzle at ``level``, which runs from 1 up the GRADES."""
    rng = random.Random(seed)
    palette = rng.choice(list(palettes))
    grade = GRADES[max(0, min(len(GRADES) - 1, level - 1))]

    for _ in range(attempts):
        layout = rng.choice(list(grade.layouts))
        dealt = _deal_rules(layout, palette, grade, rng)
        panels = _build_panels(layout, dealt)
        try:
            choices, where = _build_choices(panels, layout, dealt, grade,
                                            rng)
        except _Stalled:
            continue
        return Puzzle(layout=layout, palette=palette, panels=panels,
                      choices=choices, answer=where,
                      explanation=_explain(layout, dealt))
    raise RuntimeError('could not build a puzzle at level %d' % level)
