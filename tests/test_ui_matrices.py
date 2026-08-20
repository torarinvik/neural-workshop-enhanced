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
LEVELS = tuple(range(1, len(engine.LADDER) + 1))

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
            for puzzle in every_puzzle(40, level=level):
                self.assertEqual(len(puzzle.choices), engine.CHOICES)
                self.assertTrue(0 <= puzzle.answer < engine.CHOICES)

    def test_the_answer_is_the_panel_that_was_taken_out(self):
        for level in LEVELS:
            for puzzle in every_puzzle(40, level=level):
                self.assertTrue(figures.same_panel(
                    puzzle.choices[puzzle.answer], puzzle.question))

    def test_no_two_answers_draw_the_same_picture(self):
        for level in LEVELS:
            for puzzle in every_puzzle(40, level=level):
                for first in range(engine.CHOICES):
                    for second in range(first + 1, engine.CHOICES):
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
        seen = set(puzzle.answer for puzzle in every_puzzle(120))
        self.assertEqual(seen, set(range(engine.CHOICES)))

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
        def rules_at(level):
            return sum(len(puzzle.explanation)
                       for puzzle in every_puzzle(60, level=level)) / 60.0

        counts = [rules_at(level) for level in LEVELS]
        self.assertEqual(counts, sorted(counts), counts)
        self.assertGreater(counts[-1], counts[0] + 1.5, counts)


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
        out. That has to be worth no more than a guess, which with eight
        choices is about one time in eight."""
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
                    for count in component.counts:
                        for slot in component.places(count):
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

    def test_the_near_misses_are_spread_across_the_rules(self):
        """Drawn independently they cluster: a matrix with four
        attributes routinely produced five wrong answers that all
        differed in size, which narrows the question to "which size?"
        and throws away what the other rules were asking.

        Measured as how many wrong answers make the *same single*
        mistake — differ from the answer in one thing, and the same
        thing. Dealing them round the attributes holds this near two of
        seven; drawing each independently pushes it towards three.

        Counting how many different things go wrong *somewhere* does
        not measure this: with seven wrong answers, drawing at random
        covers nearly every attribute too. It is the piling up that
        matters, not the coverage.
        """
        worst = []
        for puzzle in every_puzzle(300, level=6):
            answer = puzzle.choices[puzzle.answer]
            tally = dict((cue, 0) for cue in DistractorTests.CUES)
            for index, choice in enumerate(puzzle.choices):
                if index == puzzle.answer:
                    continue
                differ = [cue for cue, read in DistractorTests.CUES.items()
                          if read(choice) != read(answer)]
                if len(differ) == 1:
                    tally[differ[0]] += 1
            worst.append(max(tally.values()))
        average = sum(worst) / float(len(worst))
        self.assertLess(
            average, 2.45,
            '%.2f of the seven wrong answers make the same single '
            'mistake; they are piling up on one rule' % average)


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
        self.assertEqual(len(self.task.sprites), 1 + engine.CHOICES)

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
        self.task.on_key_press(key._1 + (self.task.puzzle.answer + 1) % 8, 0)
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
        self.task.answer((self.task.puzzle.answer + 1) % 8)
        self.assertEqual(self.task.level, 1)

    def test_the_level_never_leaves_the_ladder(self):
        self.assertEqual(self.task.clamped(-5), 0)
        self.assertEqual(self.task.clamped(99), len(engine.LADDER) - 1)

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
