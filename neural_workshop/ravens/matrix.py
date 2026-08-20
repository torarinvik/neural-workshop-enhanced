# -*- coding: utf-8 -*-
"""Building a matrix, and the eight answers offered for it.

A puzzle is one layout, held for all nine panels, with one or two
components in it. Each component has a handful of attributes — which
figure, how big, what colour, how many — and each attribute is given a
rule that says what it does across a row. Run the rules, and the nine
panels fall out.

Every figure of a component shares that component's attributes within
a panel. Three figures on a lattice are three of the *same* figure at
the same size and colour, not three unrelated ones. That is what makes
a panel readable at a glance, and it is the difference between a rule
about *how many* and a jumble that happens to have three things in it.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .figures import (Figure, Panel, SHAPES, SIZES, same_panel,
                      turn_ladder)
from .layouts import (LAYOUTS, SIMPLE_LAYOUTS, Component, Layout)
from .palette import GREYS, Palette
from .rules import ACROSS, Constant, Rule, apply_rule, choose_rule

#: How many answers are offered.
CHOICES = 8

#: How many of the wrong answers are the right one with a single
#: attribute changed. The rest are panels from elsewhere in the matrix.
#: Near misses are most of them on purpose: a wrong answer that differs
#: in some way the rules never mention can be dismissed without
#: understanding anything, and a test made of those measures only
#: whether the player noticed the odd one out.
NEAR_MISS_SHARE = 0.7

#: Tries before a puzzle is given up on and built again from scratch.
PATIENCE = 400


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
                rng: random.Random) -> List[Attribute]:
    """The attributes of one component, in the order rules are dealt."""
    found = [Attribute('shape', 'which figure', SHAPES),
             Attribute('size', 'the size', component.sizes or SIZES),
             Attribute('colour', 'the %s' % palette.noun, palette.fills)]
    if component.varies_in_number:
        found.append(Attribute('number', 'how many', component.counts))
    return found


def _slots_for(component: Component, count: int) -> Tuple:
    """Which slots a panel fills when it holds ``count`` figures.

    Fixed per count rather than drawn, so that a matrix whose rule is
    about how many reads as figures being added rather than as figures
    moving about. Where they sit is not the question.
    """
    return component.places(count)


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
                count = (by_name['number'].at(row, column)
                         if 'number' in by_name else component.counts[0])
                shape = by_name['shape'].at(row, column)
                size = by_name['size'].at(row, column)
                fill = by_name['colour'].at(row, column)
                angle = (by_name['angle'].at(row, column)
                         if 'angle' in by_name else 0)
                for slot in _slots_for(component, count):
                    figures.append(Figure(shape=shape, centre=slot.centre,
                                          radius=slot.radius * size,
                                          fill=fill, angle=angle,
                                          component=part))
            line.append(tuple(figures))
        panels.append(line)
    return panels


def _deal_rules(layout: Layout, palette: Palette, active: int,
                rng: random.Random) -> List[List[Attribute]]:
    """Give every attribute a rule, ``active`` of them not constant.

    Which attributes get the interesting rules is drawn rather than
    fixed, so two puzzles at the same level are not the same puzzle
    with different figures in it.
    """
    dealt = [_attributes(component, palette, rng)
             for component in layout.components]

    slots = [(component, attribute)
             for component, attributes in zip(layout.components, dealt)
             for attribute in attributes]
    rng.shuffle(slots)
    for index, (_component, attribute) in enumerate(slots):
        if index < active:
            attribute.rule = choose_rule(
                attribute.ladder, rng,
                allow_arithmetic=(attribute.name == 'number'))
        else:
            attribute.rule = Constant()

    for attributes in dealt:
        by_name = dict((one.name, one) for one in attributes)
        for attribute in attributes:
            attribute.values = apply_rule(attribute.rule, attribute.ladder,
                                          rng)
        # A rotation rule is only offered where a turn can be seen: the
        # figure has to be the same one all the way across, and it has
        # to be a figure that looks different turned.
        # A turn is only offered when the figure is the same all the
        # way across, because how far a figure must turn before it
        # looks turned depends on how symmetrical it is, and there is
        # one ladder per matrix. A circle's ladder has one rung — it
        # looks the same every way up — so a circle is never turned
        # without that having to be said anywhere.
        shape = by_name['shape']
        if isinstance(shape.rule, Constant) and rng.random() < 0.25:
            ladder = turn_ladder(shape.at(0, 0))
            turning = Attribute('angle', 'the way it faces', ladder)
            turning.rule = choose_rule(ladder, rng)
            turning.values = apply_rule(turning.rule, ladder, rng)
            attributes.append(turning)
        # No angle attribute at all otherwise, rather than one held at
        # zero. A held attribute is still something a near miss may
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
    return lines or ['every figure is the same across each row']


def _targets(layout: Layout,
             dealt: List[List[Attribute]]) -> List[Tuple[int, Attribute]]:
    """Every attribute a near miss could change, as (component, attribute).

    Kept as a list so that the near misses can be spread across it
    rather than drawn independently. Drawn independently, a matrix with
    four attributes routinely produced five wrong answers that all
    differed in size — which narrows the question to "which size?" and
    throws away everything the other rules were asking.
    """
    return [(index, attribute)
            for index, attributes in enumerate(dealt)
            for attribute in attributes
            if len(attribute.ladder) > 1]


def _changed(layout: Layout, dealt: List[List[Attribute]],
             which: int, target: Attribute, rng: random.Random) -> Panel:
    """The right answer with ``target`` altered on one component.

    Rebuilt through the same machinery rather than edited in place, so
    a near miss is always a panel the layout could have produced —
    figures in their proper slots, at a size off the ladder. A panel
    that could not exist is answerable by noticing that it could not.
    """
    was = target.at(ACROSS - 1, ACROSS - 1)
    options = [value for value in target.ladder if value != was]
    if not options:
        return ()

    swapped = rng.choice(options)
    figures: List[Figure] = []
    for index, (component, group) in enumerate(zip(layout.components, dealt)):
        by_name = dict((one.name, one) for one in group)

        def value(name, default=None):
            if index == which and name == target.name:
                return swapped
            return (by_name[name].at(ACROSS - 1, ACROSS - 1)
                    if name in by_name else default)

        count = value('number', component.counts[0])
        for slot in _slots_for(component, count):
            figures.append(Figure(shape=value('shape'), centre=slot.centre,
                                  radius=slot.radius * value('size'),
                                  fill=value('colour'),
                                  angle=value('angle', 0), component=index))
    return tuple(figures)


def _build_choices(puzzle_panels: List[List[Panel]], layout: Layout,
                   dealt: List[List[Attribute]], palette: Palette,
                   rng: random.Random) -> Tuple[List[Panel], int]:
    """The eight answers, and where the right one was put."""
    answer = puzzle_panels[ACROSS - 1][ACROSS - 1]
    if not answer:
        raise _Stalled()

    elsewhere = [panel for row in range(ACROSS) for column in range(ACROSS)
                 for panel in (puzzle_panels[row][column],)
                 if (row, column) != (ACROSS - 1, ACROSS - 1)]

    # Deal the near misses round the attributes rather than drawing one
    # each time, so that every rule the matrix asks about is challenged
    # by at least one wrong answer before any is challenged twice.
    targets = _targets(layout, dealt)
    rng.shuffle(targets)
    turn = 0

    wrong: List[Panel] = []
    tries = 0
    while len(wrong) < CHOICES - 1:
        tries += 1
        if tries > PATIENCE:
            raise _Stalled()
        if targets and (rng.random() < NEAR_MISS_SHARE or not elsewhere):
            which, target = targets[turn % len(targets)]
            turn += 1
            candidate = _changed(layout, dealt, which, target, rng)
        else:
            candidate = rng.choice(elsewhere)
        if not candidate or same_panel(candidate, answer):
            continue
        if any(same_panel(candidate, taken) for taken in wrong):
            continue
        wrong.append(candidate)

    where = rng.randrange(CHOICES)
    choices = list(wrong)
    choices.insert(where, answer)
    return choices, where


def generate(level: int = 1, seed: Optional[int] = None,
             palettes: Sequence[Palette] = (GREYS,),
             attempts: int = 80) -> Puzzle:
    """Build one puzzle.

    ``level`` runs from 1 upward and decides two things: how many of
    the attributes carry a rule that is not simply "hold constant", and
    whether the layout may have two components to carry them.
    """
    rng = random.Random(seed)
    palette = rng.choice(list(palettes))
    components, active = LADDER[max(0, min(len(LADDER) - 1, level - 1))]

    for _ in range(attempts):
        pool = [one for one in LAYOUTS if len(one.components) == components] \
            if components > 1 else list(SIMPLE_LAYOUTS)
        layout = rng.choice(pool)
        dealt = _deal_rules(layout, palette, active, rng)
        panels = _build_panels(layout, dealt)
        try:
            choices, where = _build_choices(panels, layout, dealt, palette,
                                            rng)
        except _Stalled:
            continue
        return Puzzle(layout=layout, palette=palette, panels=panels,
                      choices=choices, answer=where,
                      explanation=_explain(layout, dealt))
    raise RuntimeError('could not build a puzzle at level %d' % level)


#: Level → how many components the layout may have, and how many
#: attributes carry a rule other than holding constant.
LADDER: Tuple[Tuple[int, int], ...] = (
    (1, 1), (1, 2), (1, 3), (2, 3), (2, 4), (2, 5),
)
