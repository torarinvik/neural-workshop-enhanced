#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Matrix Reasoning: the puzzle generator, and the screen it is drawn on.

A generated matrix can be wrong in ways that still look like a working
game. Two answers that draw the same picture make it unfair; an
attribute that varies with no rule behind it sends a player looking for
something that is not there; a wrong answer that breaks a rule the
matrix never mentions can be dismissed without understanding anything.
None of those show up as a crash, so each is checked here directly.

The engine needs no window, so most of this runs anywhere.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import math
import random
import unittest

from uisupport import (MatrixReasoning, TASKS, close_overlays, display, key,
                       needs_ui, reset_window, state)

from neural_workshop import ravens
from neural_workshop.ravens import figures, layouts, palette
from neural_workshop.ravens import matrix as engine
from neural_workshop.ravens import rules as ruleset
from neural_workshop.ravens.geometry import (is_convex, signed_area,
                                             triangulate)

#: Enough puzzles that a rare bad one still shows up, while the suite
#: stays quick — a puzzle costs well under a tenth of a millisecond.
SAMPLE = 300

#: Every level the task offers.
LEVELS = tuple(range(1, len(engine.GRADES) + 1))

#: The smallest colour difference an ordinary eye can see, in CIELAB.
JUST_NOTICEABLE = 2.3

_RGB_TO_LMS = ((17.8824, 43.5161, 4.11935),
               (3.45565, 27.1554, 3.86714),
               (0.0299566, 0.184309, 1.46709))
_LMS_TO_RGB = ((0.0809444479, -0.130504409, 0.116721066),
               (-0.0102485335, 0.0540193266, -0.113614708),
               (-0.000365296938, -0.00412161469, 0.693511405))

#: Dichromat projections, Vienot, Brettel & Mollon (1999).
VISION = {
    'ordinary': ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    'protanopia': ((0, 2.02344, -2.52581), (0, 1, 0), (0, 0, 1)),
    'deuteranopia': ((1, 0, 0), (0.494207, 0, 1.24827), (0, 0, 1)),
    'tritanopia': ((1, 0, 0), (0, 1, 0), (-0.395913, 0.801109, 0)),
}


def _apply(matrix, vector):
    return tuple(sum(matrix[row][col] * vector[col] for col in range(3))
                 for row in range(3))


def _to_linear(channel):
    channel /= 255.0
    return (channel / 12.92 if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4)


def on_paper(fill, paper=(255, 255, 255)):
    """The colour a fill actually shows as, washed over the paper."""
    share = fill.color[3] / 255.0
    return tuple(channel * share + under * (1 - share)
                 for channel, under in zip(fill.color[:3], paper))


def as_seen(rgb, vision):
    lms = _apply(_RGB_TO_LMS, [_to_linear(channel) for channel in rgb])
    return _apply(_LMS_TO_RGB, _apply(VISION[vision], lms))


def _lab(rgb, already_linear=False):
    linear = rgb if already_linear else [_to_linear(c) for c in rgb]
    x = 0.4124 * linear[0] + 0.3576 * linear[1] + 0.1805 * linear[2]
    y = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    z = 0.0193 * linear[0] + 0.1192 * linear[1] + 0.9505 * linear[2]

    def curve(value):
        value = max(0.0, value)
        return (value ** (1 / 3.) if value > 0.008856
                else 7.787 * value + 16 / 116.)

    fx, fy, fz = curve(x / 0.95047), curve(y / 1.0), curve(z / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(one, two, linear=False):
    return math.sqrt(sum((a - b) ** 2
                         for a, b in zip(_lab(one, linear),
                                         _lab(two, linear))))


def lightness(fill):
    return _lab(on_paper(fill))[0]


def every_puzzle(count=SAMPLE, level=3, palettes=None):
    for seed in range(count):
        yield ravens.generate(level=level, seed=seed,
                              palettes=palettes or palette.PALETTES)


class FigureTests(unittest.TestCase):
    """The figures are regular, and drawn the way the eye expects."""

    def test_every_figure_has_the_sides_it_claims(self):
        for name, (sides, _offset) in figures.POLYGONS.items():
            outline = figures.polygon(name, 50.0, figures.Point(0, 0))
            self.assertEqual(len(outline),
                             sides or figures.CIRCLE_SEGMENTS, name)

    def test_every_figure_is_regular(self):
        """Every corner the same distance out, every side the same
        length. This is most of what separates the look of a matrix
        from the look of a heap."""
        for name in figures.SHAPES:
            outline = figures.polygon(name, 50.0, figures.Point(0, 0))
            radii = [math.hypot(point.x, point.y) for point in outline]
            self.assertAlmostEqual(max(radii), min(radii), places=6, msg=name)
            sides = [math.hypot(outline[index].x - outline[index - 1].x,
                                outline[index].y - outline[index - 1].y)
                     for index in range(len(outline))]
            self.assertAlmostEqual(max(sides), min(sides), places=6, msg=name)

    def test_each_figure_sits_the_way_it_should(self):
        """A triangle on its base, a square square rather than diamond.

        Checked on the shape of the outline rather than on the offset
        it was given, so that changing the offset without meaning to
        shows up here.
        """
        upright = {'triangle': 1, 'pentagon': 1, 'square': 2, 'hexagon': 2}
        for name, corners_on_top in upright.items():
            outline = figures.polygon(name, 50.0, figures.Point(0, 0))
            top = min(point.y for point in outline)
            found = sum(1 for point in outline
                        if abs(point.y - top) < 1e-6)
            self.assertEqual(found, corners_on_top, name)

    def test_a_circle_looks_the_same_every_way_up(self):
        one = figures.Figure('circle', figures.Point(0, 0), 10.0,
                             palette.WHITE, angle=0)
        self.assertTrue(one.looks_like(
            figures.Figure('circle', figures.Point(0, 0), 10.0,
                           palette.WHITE, angle=137)))

    def test_a_turn_that_lands_on_a_symmetry_is_not_a_difference(self):
        """A hexagon turned a sixth of a turn is the same hexagon, and
        offering both as answers would offer the same picture twice."""
        hexagon = figures.Figure('hexagon', figures.Point(0, 0), 10.0,
                                 palette.WHITE, angle=0)
        self.assertTrue(hexagon.looks_like(
            figures.Figure('hexagon', figures.Point(0, 0), 10.0,
                           palette.WHITE, angle=60)))
        self.assertFalse(hexagon.looks_like(
            figures.Figure('hexagon', figures.Point(0, 0), 10.0,
                           palette.WHITE, angle=30)))

    def test_a_turned_triangle_is_a_different_figure(self):
        triangle = figures.Figure('triangle', figures.Point(0, 0), 10.0,
                                  palette.WHITE, angle=0)
        self.assertFalse(triangle.looks_like(
            figures.Figure('triangle', figures.Point(0, 0), 10.0,
                           palette.WHITE, angle=60)))

    def test_every_figure_triangulates_to_its_own_area(self):
        for name in figures.SHAPES:
            outline = list(figures.polygon(name, 50.0, figures.Point(0, 0)))
            covered = sum(
                abs((two.x - one.x) * (three.y - one.y)
                    - (three.x - one.x) * (two.y - one.y)) / 2.0
                for one, two, three in triangulate(outline))
            self.assertAlmostEqual(covered, abs(signed_area(outline)) / 2.0,
                                   places=6, msg=name)

    def test_every_figure_is_convex_so_the_fast_fill_is_right(self):
        for name in figures.SHAPES:
            self.assertTrue(is_convex(
                list(figures.polygon(name, 50.0, figures.Point(0, 0)))), name)


class LayoutTests(unittest.TestCase):
    """Where figures sit, and that they stay where they were put."""

    def test_no_figure_reaches_outside_its_panel(self):
        """Panels are drawn edge to edge with a hairline between them,
        so anything past the edge lands in a neighbour."""
        for layout in layouts.LAYOUTS:
            for component in layout.components:
                for slot in component.slots:
                    for axis in (slot.centre.x, slot.centre.y):
                        self.assertGreaterEqual(axis - slot.radius, -1e-9,
                                                layout.name)
                        self.assertLessEqual(axis + slot.radius, 1 + 1e-9,
                                             layout.name)

    def test_the_inner_figure_always_fits_inside_the_outer(self):
        """The two size themselves independently, so nothing else stops
        a small outer figure and a large inner one coming out the same
        size and reading as one blob."""
        outer, inner = layouts.INSIDE_OUTSIDE.components
        sizes = layouts.LATTICE_SIZES + figures.SIZES
        biggest_inner = max(sizes) * inner.slots[0].radius
        smallest_outer = min(figures.SIZES) * outer.slots[0].radius
        self.assertLess(biggest_inner, smallest_outer * 0.75)

    def test_two_slots_never_overlap(self):
        for layout in layouts.LAYOUTS:
            for component in layout.components:
                for one, two in itertools.combinations(component.slots, 2):
                    apart = math.hypot(one.centre.x - two.centre.x,
                                       one.centre.y - two.centre.y)
                    self.assertGreaterEqual(apart, one.radius + two.radius,
                                            layout.name)

    def test_every_count_has_somewhere_to_put_its_figures(self):
        for layout in layouts.LAYOUTS:
            for component in layout.components:
                for count in component.counts:
                    places = component.places(count)
                    self.assertEqual(len(places), count, layout.name)
                    self.assertEqual(len(set(places)), count, layout.name)

    def test_neighbouring_sizes_are_tellable_apart_where_they_are_drawn(self):
        """A size ladder is only as good as the room it is drawn in.

        A figure on a three-by-three lattice is a sixth of a panel
        across; at that size the full five-step ladder puts neighbours
        about a fifth apart, which is there but not something to ask a
        person to be sure about. Measured on the drawn radius, not on
        the fraction, because the fraction is not what anybody sees.
        """
        for layout in layouts.LAYOUTS:
            for component in layout.components:
                ladder = component.sizes or figures.SIZES
                drawn = sorted(size * component.slots[0].radius
                               for size in ladder)
                for smaller, larger in zip(drawn, drawn[1:]):
                    self.assertGreater(
                        larger / smaller, 1.25,
                        '%s: %.4f and %.4f are too close to call apart'
                        % (layout.name, smaller, larger))

    def test_a_part_filled_lattice_sits_squarely_in_its_panel(self):
        """Three figures along the top of an empty lattice read as six
        missing rather than three present."""
        component = layouts.GRID_NINE.components[0]
        for count in component.counts:
            places = component.places(count)
            middle = sum(slot.centre.y for slot in places) / len(places)
            self.assertAlmostEqual(middle, 0.5, places=6,
                                   msg='%d figures sit off centre' % count)


class RuleTests(unittest.TestCase):
    """What each rule does across a row."""

    def setUp(self):
        self.rng = random.Random(20260820)
        self.ladder = ('a', 'b', 'c', 'd', 'e')

    def test_constant_holds_across_the_whole_matrix(self):
        """Not merely along each row. An attribute that changes between
        rows is doing something, and a player is right to go looking
        for the rule behind it — so there had better be one."""
        for _try in range(200):
            rows = ruleset.Constant().rows(self.ladder, self.rng)
            self.assertEqual(len(set(value for row in rows for value in row)),
                             1, rows)

    def test_a_progression_steps_by_the_same_amount_every_time(self):
        for step in (1, -1, 2, -2):
            rows = ruleset.Progression(step).rows(self.ladder, self.rng)
            for row in rows:
                places = [self.ladder.index(value) for value in row]
                self.assertEqual([two - one for one, two
                                  in zip(places, places[1:])],
                                 [step, step])

    def test_distribute_three_gives_every_row_and_column_all_three(self):
        """A Latin square, not merely a shuffle. The player can read the
        missing value off the row or the column and both agree, which is
        what makes a matrix feel solvable rather than merely consistent.
        """
        for _try in range(200):
            rows = ruleset.DistributeThree().rows(self.ladder, self.rng)
            wanted = set(rows[0])
            self.assertEqual(len(wanted), 3)
            for row in rows:
                self.assertEqual(set(row), wanted)
            for column in range(3):
                self.assertEqual(set(row[column] for row in rows), wanted)

    def test_arithmetic_adds_up(self):
        for sign in (1, -1):
            rows = ruleset.Arithmetic(sign).rows((1, 2, 3, 4, 5, 6),
                                                 self.rng)
            for first, second, third in rows:
                self.assertEqual(third, first + sign * second)

    def test_a_rule_too_big_for_its_ladder_falls_back_rather_than_breaks(self):
        short = ('a', 'b')
        rows = ruleset.apply_rule(ruleset.Progression(2), short, self.rng)
        self.assertEqual(len(set(value for row in rows for value in row)), 1)

    def test_logic_combines_the_first_two_panels_into_the_third(self):
        ops = {'or': lambda a, b: a | b,
               'and': lambda a, b: a & b,
               'xor': lambda a, b: a ^ b}
        for name, combine in ops.items():
            for _try in range(100):
                rows = ruleset.Logic(name).rows(tuple(range(9)), self.rng)
                for first, second, third in rows:
                    self.assertEqual(third, combine(first, second))

    def test_a_logic_row_always_shows_its_operation(self):
        """Identical operands show nothing, and a result equal to one
        of them is explained by "copy that one" just as well."""
        for name in ('or', 'and', 'xor'):
            for _try in range(100):
                for first, second, third in ruleset.Logic(name).rows(
                        tuple(range(4)), self.rng):
                    self.assertNotEqual(first, second)
                    self.assertNotIn(third, (first, second))
                    self.assertTrue(third)

    def test_second_order_steps_further_each_row(self):
        """Row one holds, row two steps, row three steps twice as far
        — the progression is of the rules, not the values."""
        for delta in (1, -1):
            for _try in range(100):
                rows = ruleset.SecondOrder(delta).rows(
                    tuple(range(9)), self.rng)
                for count, row in enumerate(rows):
                    steps = [two - one for one, two in zip(row, row[1:])]
                    self.assertEqual(steps, [delta * count] * 2, rows)

    def test_a_second_order_row_is_free_to_start_anywhere(self):
        """Tied to one start the item reads as a plain pattern of
        positions; the only thread through the rows must be the
        accelerating step."""
        opened = set()
        for _try in range(200):
            rows = ruleset.SecondOrder(1).rows(tuple(range(9)), self.rng)
            opened.add(tuple(row[0] for row in rows))
        self.assertGreater(len(opened), 20)

    def test_second_order_needs_a_ladder_of_five(self):
        self.assertFalse(ruleset.SecondOrder.fits(tuple(range(4))))
        self.assertTrue(ruleset.SecondOrder.fits(tuple(range(5))))

    def test_logic_needs_a_lattice_to_live_on(self):
        self.assertFalse(ruleset.Logic.fits(tuple(range(3))))
        self.assertTrue(ruleset.Logic.fits(tuple(range(4))))

    def test_a_narrowed_pool_offers_only_what_it_names(self):
        for rule in ruleset.rule_choices(self.ladder,
                                         allowed=('progression',)):
            self.assertEqual(rule.name, 'progression')
        self.assertEqual(ruleset.rule_choices(self.ladder, allowed=()), [])

    def test_only_rules_that_fit_are_ever_offered(self):
        for size in range(1, 6):
            ladder = tuple('abcde'[:size])
            for rule in ruleset.rule_choices(ladder):
                rule.rows(ladder, self.rng)   # must not raise


class PuzzleTests(unittest.TestCase):
    """What every generated matrix has to be true of."""

    def test_a_seed_always_builds_the_same_puzzle(self):
        first = ravens.generate(level=5, seed=99, palettes=palette.PALETTES)
        again = ravens.generate(level=5, seed=99, palettes=palette.PALETTES)
        self.assertEqual(first.answer, again.answer)
        self.assertEqual(first.layout.name, again.layout.name)
        for one, two in zip(first.choices, again.choices):
            self.assertTrue(figures.same_panel(one, two))

    def test_every_level_builds(self):
        for level in LEVELS:
            offered = engine.GRADES[level - 1].choices
            for puzzle in every_puzzle(40, level=level):
                self.assertEqual(len(puzzle.choices), offered)
                self.assertTrue(0 <= puzzle.answer < offered)

    def test_the_answer_is_the_panel_that_was_taken_out(self):
        for level in LEVELS:
            for puzzle in every_puzzle(40, level=level):
                self.assertTrue(figures.same_panel(
                    puzzle.choices[puzzle.answer], puzzle.question))

    def test_no_two_answers_draw_the_same_picture(self):
        for level in LEVELS:
            for puzzle in every_puzzle(40, level=level):
                for first in range(len(puzzle.choices)):
                    for second in range(first + 1, len(puzzle.choices)):
                        self.assertFalse(
                            figures.same_panel(puzzle.choices[first],
                                               puzzle.choices[second]),
                            'choices %d and %d are the same picture'
                            % (first, second))

    def test_no_panel_of_the_matrix_is_empty(self):
        for level in LEVELS:
            for puzzle in every_puzzle(40, level=level):
                for row in puzzle.panels:
                    for panel in row:
                        self.assertTrue(panel)

    def test_no_answer_is_blank(self):
        for level in LEVELS:
            for puzzle in every_puzzle(40, level=level):
                for index, choice in enumerate(puzzle.choices):
                    self.assertTrue(choice, 'choice %d is empty' % index)

    def test_the_right_answer_lands_everywhere_over_a_run(self):
        for level in (3, 6):
            seen = set(puzzle.answer
                       for puzzle in every_puzzle(150, level=level))
            self.assertEqual(seen,
                             set(range(engine.GRADES[level - 1].choices)))

    def test_every_panel_holds_the_same_layout(self):
        """The layout is the puzzle's shape, not one of its variables."""
        for puzzle in every_puzzle(60, level=6):
            counts = set()
            for row in puzzle.panels:
                for panel in row:
                    counts.add(tuple(sorted(
                        round(figure.centre.x, 4) for figure in panel)))
            # Panels may hold different numbers of figures only when the
            # layout allows a number rule at all.
            varies = any(component.varies_in_number
                         for component in puzzle.layout.components)
            if not varies:
                self.assertEqual(len(counts), 1, puzzle.layout.name)

    @staticmethod
    def _by_component(puzzle):
        """Every figure of the matrix, grouped by which component it is.

        Two components are two different things and may perfectly well
        differ from each other — the figure above being a square while
        the one below is a circle is not variation, it is the layout.
        Only variation *within* a component needs a rule behind it.
        """
        groups = [[] for _ in puzzle.layout.components]
        for row in puzzle.panels:
            for panel in row:
                for figure in panel:
                    groups[figure.component].append(figure)
        return groups

    def test_nothing_varies_without_a_rule_saying_so(self):
        """Every attribute that differs within a component must be one
        the explanation names. Variation nobody explained sends a player
        looking for a rule that is not there.
        """
        for level in LEVELS:
            for puzzle in every_puzzle(30, level=level):
                said = ' '.join(puzzle.explanation)
                for group in self._by_component(puzzle):
                    for name, read in (
                            ('which figure', lambda f: f.shape),
                            ('the size', lambda f: round(f.radius, 4)),
                            ('the way it faces', lambda f: f.angle),
                            ('the %s' % puzzle.palette.noun,
                             lambda f: f.fill.name)):
                        if len(set(read(figure) for figure in group)) > 1:
                            self.assertIn(
                                name, said,
                                '%s varies but no rule mentions it: %s'
                                % (name, puzzle.explanation))

    def test_a_rotation_rule_is_only_used_where_a_turn_can_be_seen(self):
        """A hexagon turned a sixth of a turn is the same hexagon and a
        circle is the same every way up, so a rotation rule on either
        is a rule the puzzle claims and never shows.
        """
        seen = 0
        for level in LEVELS:
            for puzzle in every_puzzle(60, level=level):
                for panel_row in puzzle.panels:
                    for panel in panel_row:
                        for figure in panel:
                            if figure.shape == 'circle':
                                self.assertEqual(figure.angle, 0,
                                                 'a circle was turned')
                if not any('faces' in line for line in puzzle.explanation):
                    continue
                seen += 1
                groups = self._by_component(puzzle)
                turning = [group for group in groups
                           if len(set(figure.angle
                                      for figure in group)) > 1]
                self.assertTrue(turning, puzzle.explanation)
                for group in turning:
                    self.assertGreater(
                        len(set(figure._turn() for figure in group)), 1,
                        'a %s is turned but looks the same either way'
                        % group[0].shape)
        self.assertGreater(seen, 0, 'no rotation rule was ever generated')

    def test_a_harder_level_carries_more_rules(self):
        """Realized rules, not nominal ones: a grade asking for more
        rules than its layouts have attributes would claim difficulty
        it does not deliver, and only counting what the explanations
        actually name can catch that."""
        def rules_at(level):
            return sum(sum(1 for line in puzzle.explanation
                           if 'same picture' not in line)
                       for puzzle in every_puzzle(60, level=level)) / 60.0

        counts = [rules_at(level) for level in LEVELS]
        self.assertEqual(counts[0], 0.0, 'grade one is pure matching')
        for level, (fewer, more) in enumerate(zip(counts, counts[1:]), 2):
            self.assertGreater(more, fewer - 0.35,
                               'level %d carries fewer rules than the one '
                               'below it: %s' % (level, counts))
        self.assertGreater(counts[-1], counts[0] + 6, counts)

    def test_the_hardest_grade_is_genuinely_loaded(self):
        """Grade twelve claims nine rules; most of a sample had better
        actually run at least eight."""
        totals = [sum(1 for line in puzzle.explanation
                      if 'same picture' not in line)
                  for puzzle in every_puzzle(60, level=LEVELS[-1])]
        self.assertGreater(sum(totals) / 60.0, 7.5, totals)

    def test_easy_grades_ask_less_of_the_easiest_thing(self):
        """Grade one is matching: every panel of the matrix draws the
        same picture, which is what makes it answerable at five."""
        for puzzle in every_puzzle(40, level=1):
            first = puzzle.panels[0][0]
            for row in puzzle.panels:
                for panel in row:
                    self.assertTrue(figures.same_panel(panel, first))

    def test_the_logic_rule_appears_at_the_top_and_never_below(self):
        def logical(level, count=120):
            return sum(any('third panel' in line
                           for line in puzzle.explanation)
                       for puzzle in every_puzzle(count, level=level))

        for level in (1, 3, 5, 7):
            self.assertEqual(logical(level, 60), 0, level)
        self.assertGreater(sum(logical(level) for level in (8, 9, 10)), 20)

    def test_second_order_appears_at_the_top_and_never_below(self):
        """The rule that changes between rows is the hardest thing the
        real test asks; the middle grades draw from the first-order
        pool only."""
        def carrying(level, count):
            return sum(any('further each row' in line
                           for line in puzzle.explanation)
                       for puzzle in every_puzzle(count, level=level))

        for level in (2, 4, 6, 8):
            self.assertEqual(carrying(level, 80), 0, level)
        self.assertGreater(carrying(9, 120), 30)

    def test_a_second_order_matrix_shows_its_accelerating_step(self):
        """Read the values back off the panels: within each row the
        step is even, and it grows from nothing by one per row.
        Checked on sizes, where the rungs can be recovered exactly."""
        seen = 0
        for puzzle in every_puzzle(300, level=9):
            for index, (component, describes) in enumerate(
                    zip(puzzle.layout.components,
                        puzzle.layout.describes)):
                said = [line for line in puzzle.explanation
                        if 'further each row' in line and 'size' in line
                        and (len(puzzle.layout.components) == 1
                             or line.startswith(describes))]
                ladder = sorted(component.sizes
                                or engine.GRADES[8].sizes)
                if not said or len(ladder) < 5:
                    continue
                seen += 1
                room = component.slots[0].radius
                deltas = []
                for row in range(2):   # the last row's end is hidden
                    rungs = []
                    for panel in puzzle.panels[row]:
                        radius = set(f.radius for f in panel
                                     if f.component == index).pop()
                        rungs.append(ladder.index(round(radius / room, 4)))
                    steps = set(two - one
                                for one, two in zip(rungs, rungs[1:]))
                    self.assertEqual(len(steps), 1, rungs)
                    deltas.append(steps.pop())
                self.assertEqual(deltas[0], 0, deltas)
                self.assertIn(deltas[1], (1, -1), deltas)
        self.assertGreater(seen, 3, 'no second-order size rule was '
                                    'ever generated at grade nine')

    def test_a_logic_puzzle_combines_its_panels_as_it_says(self):
        """Panel three's filled places really are panels one and two
        combined, on every row, under the operation the explanation
        names."""
        ops = {'gathers everything': lambda a, b: a | b,
               'keeps only what': lambda a, b: a & b,
               'exactly one': lambda a, b: a ^ b}
        seen = 0
        for puzzle in every_puzzle(200, level=9):
            said = [line for line in puzzle.explanation
                    if 'third panel' in line]
            if not said or len(puzzle.layout.components) != 1:
                continue
            combine = next(op for phrase, op in ops.items()
                           if phrase in said[0])
            seen += 1
            slots = puzzle.layout.components[0].slots
            spot = dict(((round(slot.centre.x, 4), round(slot.centre.y, 4)),
                         index) for index, slot in enumerate(slots))
            for row in range(2):     # the third row's last panel is hidden
                places = [frozenset(spot[(round(f.centre.x, 4),
                                          round(f.centre.y, 4))]
                                    for f in panel)
                          for panel in puzzle.panels[row]]
                self.assertEqual(places[2], combine(places[0], places[1]),
                                 said)
        self.assertGreater(seen, 5, 'no single-component logic puzzle '
                                    'was ever generated')


class DistractorTests(unittest.TestCase):
    """The wrong answers decide whether the puzzle asks anything."""

    CUES = {
        'how many figures': lambda panel: len(panel),
        'which figures': lambda panel: frozenset(f.shape for f in panel),
        'which colours': lambda panel: frozenset(f.fill.name for f in panel),
        'which sizes': lambda panel: frozenset(round(f.radius, 4)
                                               for f in panel),
    }

    def test_no_single_cue_finds_the_answer_better_than_guessing(self):
        """A player who has found no rule can still look for the odd one
        out. That has to be worth no more than a guess."""
        for level in (2, 4, 6):
            alone = dict((cue, 0) for cue in self.CUES)
            for puzzle in every_puzzle(SAMPLE, level=level):
                for cue, read in self.CUES.items():
                    wanted = read(puzzle.choices[puzzle.answer])
                    if sum(1 for choice in puzzle.choices
                           if read(choice) == wanted) == 1:
                        alone[cue] += 1
            for cue, count in alone.items():
                self.assertLess(
                    count / float(SAMPLE), 0.25,
                    'level %d: "%s" alone picks the answer in %d of %d'
                    % (level, cue, count, SAMPLE))

    def test_a_wrong_answer_is_never_a_panel_the_layout_could_not_hold(self):
        """A near miss has to be wrong about a rule, not about the shape
        of a panel. One that could not exist is answerable by noticing
        that it could not."""
        for level in LEVELS:
            for puzzle in every_puzzle(30, level=level):
                allowed = set()
                for component in puzzle.layout.components:
                    for slot in component.slots:
                        allowed.add((round(slot.centre.x, 4),
                                     round(slot.centre.y, 4)))
                for choice in puzzle.choices:
                    for figure in choice:
                        self.assertIn((round(figure.centre.x, 4),
                                       round(figure.centre.y, 4)), allowed,
                                      puzzle.layout.name)

    def test_no_wrong_answer_turns_a_figure_the_matrix_never_turns(self):
        """A tilted figure among eight upright ones is a wrong answer
        anybody can dismiss without reading the matrix."""
        for level in LEVELS:
            for puzzle in every_puzzle(40, level=level):
                turned = set(figure.angle for row in puzzle.panels
                             for panel in row for figure in panel)
                if turned == {0}:
                    for choice in puzzle.choices:
                        for figure in choice:
                            self.assertEqual(figure.angle, 0,
                                             puzzle.explanation)

    @staticmethod
    def _description(panel):
        """Everything a lazy eye can read off one panel at a glance."""
        return {
            'count': len(panel),
            'shapes': tuple(sorted(f.shape for f in panel)),
            'fills': tuple(sorted(f.fill.name for f in panel)),
            'sizes': tuple(sorted(round(f.radius, 3) for f in panel)),
            'angles': tuple(sorted(f._turn() for f in panel)),
            'spots': tuple(sorted((round(f.centre.x, 2),
                                   round(f.centre.y, 2)) for f in panel)),
        }

    def _typicality(self, puzzle):
        """Each answer's agreement with the others, feature by feature."""
        told = [self._description(choice) for choice in puzzle.choices]
        return [sum(1 for feature in told[index]
                    for position, other in enumerate(told)
                    if position != index
                    and other[feature] == told[index][feature])
                for index in range(len(told))]

    def _guessing_beats_nothing(self, pick, allowance=1.8):
        """Run a context-blind solver over three grades; it must do no
        better than guessing, within sampling noise.

        This is the leak the whole answer design exists to close. Wrong
        answers built as "the right one with a single thing changed"
        put the right answer at the centre of its own distractor set,
        and picking the most typical answer solved 96 per cent of the
        old puzzles without reading the matrix. The RAVEN dataset
        shipped with the same fault. Balance — every targeted attribute
        wrong in exactly half the answers — is what closes it, and this
        is the test that keeps it closed.
        """
        trials = 200
        for level in (2, 6, 12):
            chance = 1.0 / engine.GRADES[level - 1].choices
            hits = 0
            for puzzle in every_puzzle(trials, level=level):
                if pick(self._typicality(puzzle)) == puzzle.answer:
                    hits += 1
            self.assertLess(
                hits / float(trials), chance * allowance,
                'level %d: a solver that never reads the matrix scores '
                '%d of %d against a chance of %.0f%%'
                % (level, hits, trials, 100 * chance))

    @staticmethod
    def _read_attributes(panel, component):
        """One component's attribute values, as a wrong answer sees them."""
        mine = [f for f in panel if f.component == component]
        if not mine:
            return {}
        return {'shape': set(f.shape for f in mine).pop(),
                'size': round(set(f.radius for f in mine).pop(), 4)
                        if len(set(round(f.radius, 4) for f in mine)) == 1
                        else None,
                'fill': set(f.fill.name for f in mine).pop(),
                'angle': set(f._turn() for f in mine).pop(),
                'places': frozenset((round(f.centre.x, 4),
                                     round(f.centre.y, 4)) for f in mine)}

    def test_every_live_rule_is_challenged_and_challenged_fairly(self):
        """At a grade whose live rules all fit inside the answer
        design, every attribute that varies across the matrix must be
        wrong in *exactly half* of the answers offered. Fewer than
        half and the right value is the most common one, which is the
        centroid leak; more than half and it is the rarest, which is
        the odd-one-out leak; all-agreeing and the rule was never
        challenged at all — every answer being right about it, the
        player never has to solve it."""
        for puzzle in every_puzzle(200, level=4):
            offered = len(puzzle.choices)
            for component in range(len(puzzle.layout.components)):
                varies = {}
                for row in puzzle.panels:
                    for panel in row:
                        for name, value in self._read_attributes(
                                panel, component).items():
                            varies.setdefault(name, set()).add(value)
                answer = self._read_attributes(
                    puzzle.choices[puzzle.answer], component)
                for name, values in varies.items():
                    if len(values) < 2:
                        continue
                    agree = sum(
                        1 for choice in puzzle.choices
                        if self._read_attributes(choice, component)
                        .get(name) == answer[name])
                    self.assertEqual(
                        agree, offered // 2,
                        '%s: the answers agree with the right one %d of '
                        '%d times' % (name, agree, offered))

    def test_the_live_rules_are_challenged_before_held_attributes(self):
        """A two-part puzzle has more attributes than the answer design
        can target, so the choice of which four matters: a wrong
        answer that breaks a rule the matrix actually runs tests that
        rule, where one that breaks a held attribute only tests
        whether the player noticed the theme. Whenever the varying
        attributes fit the design, every one of them must be among
        the challenged."""
        for puzzle in every_puzzle(200, level=7):
            offered = len(puzzle.choices)
            varying = []
            for component in range(len(puzzle.layout.components)):
                values = {}
                for row in puzzle.panels:
                    for panel in row:
                        for name, value in self._read_attributes(
                                panel, component).items():
                            values.setdefault(name, set()).add(value)
                varying.extend((component, name)
                               for name, seen in values.items()
                               if len(seen) > 1)
            if len(varying) > 4:
                continue
            for component, name in varying:
                answer = self._read_attributes(
                    puzzle.choices[puzzle.answer], component)
                agree = sum(1 for choice in puzzle.choices
                            if self._read_attributes(choice, component)
                            .get(name) == answer[name])
                self.assertEqual(
                    agree, offered // 2,
                    '%s varies across the matrix but no wrong answer '
                    'challenges it' % name)

    def test_the_easy_grades_offer_four_answers_and_the_rest_eight(self):
        """Four for the easy grades, as the children's form of the
        real test does; eight from grade four up."""
        self.assertEqual(len(ravens.generate(level=1, seed=1).choices), 4)
        self.assertEqual(len(ravens.generate(level=3, seed=1).choices), 4)
        self.assertEqual(len(ravens.generate(level=4, seed=1).choices), 8)
        self.assertEqual(len(ravens.generate(level=12, seed=1).choices), 8)

    def test_all_three_logic_operations_come_up(self):
        """One operation only would make every logic puzzle the same
        question wearing different figures."""
        seen = set()
        for puzzle in every_puzzle(300, level=9):
            for line in puzzle.explanation:
                for phrase in ('gathers everything', 'keeps only what',
                               'exactly one'):
                    if phrase in line:
                        seen.add(phrase)
        self.assertEqual(len(seen), 3, seen)

    def test_a_place_set_near_miss_is_one_flip_away(self):
        """The logic rule's wrong answers add or drop a single figure;
        anything wilder is a different picture, not a near miss."""
        attribute = engine.Attribute('number', 'where the figures sit',
                                     tuple(range(4)))
        value = frozenset((0, 2))
        options = attribute.alternatives(value)
        self.assertTrue(options)
        for option in options:
            self.assertEqual(len(option ^ value), 1)
            self.assertTrue(option)
        lonely = engine.Attribute('number', 'where the figures sit', (0,))
        self.assertEqual(lonely.alternatives(frozenset((0,))), [])

    def test_the_easy_grades_use_few_sizes_and_keep_them_far_apart(self):
        """Three rungs, each at least a third bigger than the last, so
        "bigger" is something a child sees rather than judges."""
        used = set()
        for puzzle in every_puzzle(150, level=2):
            for row in puzzle.panels:
                for panel in row:
                    for figure in panel:
                        used.add(round(figure.radius / 0.42, 4))
        self.assertLessEqual(len(used), 3, sorted(used))
        rungs = sorted(used)
        for smaller, bigger in zip(rungs, rungs[1:]):
            self.assertGreater(bigger / smaller, 1.33, rungs)

    def test_the_most_typical_answer_is_no_better_than_a_guess(self):
        self._guessing_beats_nothing(
            lambda scores: scores.index(max(scores)))

    def test_the_least_typical_answer_is_no_better_than_a_guess(self):
        """The other classic cheat — and the one the wide balanced
        design failed before it was capped: the all-correct answer
        agreed with the wrong ones less than they agreed with each
        other, and "odd one out" found it 44 per cent of the time."""
        self._guessing_beats_nothing(
            lambda scores: scores.index(min(scores)))

class PaletteTests(unittest.TestCase):
    """Colour has to be readable by everyone the game is for."""

    def test_every_fill_has_its_own_name(self):
        """Fills are compared by name, so two sharing one are one fill,
        and two panels differing only in that would count as the same
        picture — which is how a puzzle comes to offer its answer twice.
        """
        for group in (palette.GREY_FILLS, palette.COLOUR_FILLS):
            names = [fill.name for fill in group]
            self.assertEqual(len(names), len(set(names)), names)

    def test_colours_stay_apart_for_every_kind_of_eye(self):
        for kind in VISION:
            for one, two in itertools.combinations(palette.COLOUR_FILLS, 2):
                gap = delta_e(as_seen(on_paper(one), kind),
                              as_seen(on_paper(two), kind), linear=True)
                self.assertGreater(
                    gap, JUST_NOTICEABLE * 4,
                    '%s and %s are only %.1f apart under %s'
                    % (one.name, two.name, gap, kind))

    def test_colours_are_no_harder_to_tell_apart_than_the_greys(self):
        def worst(fills):
            return min(delta_e(as_seen(on_paper(one), kind),
                               as_seen(on_paper(two), kind), linear=True)
                       for kind in VISION
                       for one, two in itertools.combinations(fills, 2))

        self.assertGreater(worst(palette.COLOUR_FILLS),
                           worst(palette.GREY_FILLS))

    def test_the_colour_ramp_is_also_a_lightness_ramp(self):
        """So a colour rule can be followed without seeing colour."""
        levels = [lightness(fill) for fill in palette.COLOUR_FILLS]
        self.assertEqual(levels, sorted(levels, reverse=True), levels)
        for brighter, darker in zip(levels, levels[1:]):
            self.assertGreater(brighter - darker, 5.0, levels)

    def test_a_puzzle_never_mixes_the_two(self):
        for puzzle in every_puzzle(120, level=6):
            allowed = set(fill.name for fill in puzzle.palette.fills)
            for row in puzzle.panels:
                for panel in row:
                    for figure in panel:
                        self.assertIn(figure.fill.name, allowed)
            for choice in puzzle.choices:
                for figure in choice:
                    self.assertIn(figure.fill.name, allowed)

    def test_greys_only_unless_colour_is_asked_for(self):
        for puzzle in every_puzzle(60, palettes=(palette.GREYS,)):
            self.assertEqual(puzzle.palette.name, 'greys')

    def test_a_colour_puzzle_says_colour_when_it_is_explained(self):
        said = set()
        for puzzle in every_puzzle(200, level=4,
                                   palettes=(palette.COLOURS,)):
            said.update(puzzle.explanation)
        self.assertTrue(any('colour' in line for line in said))
        self.assertFalse(any('shade' in line for line in said), said)


@needs_ui
class MatrixHubTests(unittest.TestCase):
    """The task is reachable and named."""

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_reasoning(self):
        self.assertIn('matrix_reasoning',
                      [task_id for task_id, _label in TASKS['reasoning']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        launch_task('matrix_reasoning')
        self.assertIsNotNone(MatrixReasoning.instance)
        MatrixReasoning.instance.close()


@needs_ui
class MatrixScreenTests(unittest.TestCase):
    """The screen: drawing, answering, and cleaning up after itself."""

    def setUp(self):
        close_overlays()
        self.task = MatrixReasoning()

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def test_it_draws_a_puzzle_without_complaint(self):
        self.task.start_run()
        self.task.on_draw()
        self.assertEqual(self.task.phase, 'asking')
        self.assertEqual(len(self.task.sprites),
                         1 + len(self.task.puzzle.choices))

    def test_every_level_draws(self):
        for level in LEVELS:
            self.task.start_level = level
            self.task.start_run()
            self.task.on_draw()
            self.assertIsNotNone(self.task.puzzle)

    def test_painting_a_card_leaves_the_clear_colour_alone(self):
        """Left set to paper white, the window itself clears to white on
        the next frame, which on the dark theme is white on white."""
        from pyglet import gl
        gl.glClearColor(0., 0., 0., 1.)
        try:
            self.task.start_run()
            after = (gl.GLfloat * 4)()
            gl.glGetFloatv(gl.GL_COLOR_CLEAR_VALUE, after)
            self.assertEqual(list(after), [0., 0., 0., 1.])
        finally:
            black = state.cfg.BLACK_BACKGROUND
            gl.glClearColor(*((0., 0., 0., 1.) if black
                              else (1., 1., 1., 1.)))

    def test_the_right_key_scores_and_a_wrong_one_does_not(self):
        self.task.start_run()
        self.task.on_key_press(key._1 + self.task.puzzle.answer, 0)
        self.assertEqual(self.task.correct, 1)
        self.task.phase = 'asking'
        wrong = (self.task.puzzle.answer + 1) % len(self.task.puzzle.choices)
        self.task.on_key_press(key._1 + wrong, 0)
        self.assertEqual(self.task.correct, 1)

    def test_clicking_a_box_answers_it(self):
        self.task.start_run()
        left, bottom, width, height = \
            self.task._choice_rects()[self.task.puzzle.answer]
        self.task.on_mouse_press(int(left + width / 2),
                                 int(bottom + height / 2), 1, 0)
        self.assertEqual(self.task.correct, 1)

    def test_clicking_outside_every_box_answers_nothing(self):
        self.task.start_run()
        self.task.on_mouse_press(2, 2, 1, 0)
        self.assertIsNone(self.task.picked)

    def test_a_right_answer_goes_up_a_level_and_a_wrong_one_down(self):
        self.task.adaptive = True
        self.task.start_level = 2
        self.task.start_run()
        self.assertEqual(self.task.level, 1)
        self.task.answer(self.task.puzzle.answer)
        self.assertEqual(self.task.level, 2)
        self.task.phase = 'asking'
        self.task.answer((self.task.puzzle.answer + 1)
                         % len(self.task.puzzle.choices))
        self.assertEqual(self.task.level, 1)

    def test_the_level_never_leaves_the_ladder(self):
        self.assertEqual(self.task.clamped(-5), 0)
        self.assertEqual(self.task.clamped(99), len(engine.GRADES) - 1)

    def test_the_reported_level_is_the_one_the_puzzle_was_asked_at(self):
        self.task.adaptive = True
        self.task.feedback = True
        self.task.start_level = 2
        self.task.start_run()
        asked_at = self.task.trial_level
        self.task.answer(self.task.puzzle.answer)
        self.assertNotEqual(self.task.level, asked_at)
        self.assertIn('level %d' % (asked_at + 1), self.task.status.text)

    def test_resizing_keeps_the_same_puzzle(self):
        self.task.start_run()
        puzzle = self.task.puzzle
        state.window.set_size(720, 560)
        display.ensure_laid_out()
        self.task.relayout()
        self.assertIs(self.task.puzzle, puzzle)
        self.task.on_draw()

    def test_closing_gives_back_its_textures_and_handlers(self):
        self.task.start_run()
        self.assertTrue(self.task.choice_cards)
        self.task.close()
        self.assertIsNone(self.task.matrix_card)
        self.assertEqual(self.task.choice_cards, [])
        self.assertIsNone(MatrixReasoning.instance)
        self.assertNotIn(self.task, display.open_overlays())

    def test_a_second_task_closes_the_first(self):
        first = self.task
        self.task = MatrixReasoning()
        self.assertIsNone(first.matrix_card)
        self.assertIs(MatrixReasoning.instance, self.task)

    def test_crossing_the_four_answer_line_redraws_the_cards(self):
        """An adaptive run climbing from grade three to grade four goes
        from four answers to eight; the cards, whose size depends on
        how many rows they share, have to follow."""
        self.task.adaptive = True
        self.task.feedback = False
        self.task.start_level = 3
        self.task.start_run()
        self.assertEqual(len(self.task.choice_cards), 4)
        self.task.answer(self.task.puzzle.answer)
        self.assertEqual(len(self.task.puzzle.choices), 8)
        self.assertEqual(len(self.task.choice_cards), 8)
        self.task.on_draw()
        self.assertEqual(len(self.task.sprites), 1 + 8)

    def test_a_run_ends_with_a_score(self):
        self.task.total_trials = 3
        self.task.feedback = False
        self.task.start_run()
        for _trial in range(3):
            self.task.answer(self.task.puzzle.answer if self.task.puzzle
                             else 0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['trials'], 3)
        self.assertEqual(self.task.score()['accuracy'], 100)


if __name__ == '__main__':
    unittest.main()
