#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Matrix Reasoning: the puzzle generator, and the screen it is drawn on.

A generated matrix can be wrong in ways that still look like a working
game. Two answer choices that draw the same picture make the puzzle
unfair without looking broken; a rule that does not actually change
anything leaves a grid that reads as a pattern but cannot be reasoned
about; a set of choices where only the right one holds four shapes
lets a player win by counting without finding the rule at all. None of
those show up as a crash, so each is checked here directly.

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
from neural_workshop.ravens import matrix as engine
from neural_workshop.ravens import rules as ruleset
from neural_workshop.ravens import surfaces, transforms
from neural_workshop.ravens.geometry import (Point, ellipse_outline,
                                             is_convex, signed_area,
                                             transformed, triangulate)
from neural_workshop.ravens.surfaces import Surface, same_picture

#: Enough puzzles that a rare bad one still shows up, while the suite
#: stays quick — a puzzle costs well under a millisecond to build.
SAMPLE = 200

#: The shapes, at a size the generator actually produces.
EVERY_SHAPE = tuple(
    Surface(kind, 50.0, 75.0, Point(50.0, 50.0), surfaces.WHITE)
    for kind in surfaces.SHAPE_KINDS)



#: The smallest colour difference an ordinary eye can see, in CIELAB.
#: Anything the puzzle asks a player to tell apart has to clear it by
#: a wide margin, under every kind of vision.
JUST_NOTICEABLE = 2.3

#: Linear-RGB to LMS, and the dichromat projections back onto the
#: colours that kind of eye can form. Vienot, Brettel & Mollon (1999).
_RGB_TO_LMS = ((17.8824, 43.5161, 4.11935),
               (3.45565, 27.1554, 3.86714),
               (0.0299566, 0.184309, 1.46709))
_LMS_TO_RGB = ((0.0809444479, -0.130504409, 0.116721066),
               (-0.0102485335, 0.0540193266, -0.113614708),
               (-0.000365296938, -0.00412161469, 0.693511405))
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
    """*rgb* as an eye of that kind forms it."""
    lms = _apply(_RGB_TO_LMS, [_to_linear(c) for c in rgb])
    return _apply(_LMS_TO_RGB, _apply(VISION[vision], lms))


def _lab(rgb, already_linear=False):
    linear = rgb if already_linear else [_to_linear(c) for c in rgb]
    x = 0.4124 * linear[0] + 0.3576 * linear[1] + 0.1805 * linear[2]
    y = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    z = 0.0193 * linear[0] + 0.1192 * linear[1] + 0.9505 * linear[2]

    def curve(value):
        value = max(0.0, value)
        return value ** (1 / 3.) if value > 0.008856 else 7.787 * value + 16 / 116.

    fx, fy, fz = (curve(x / 0.95047), curve(y / 1.0), curve(z / 1.08883))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(one, two, linear=False):
    """How far apart two colours look."""
    return math.sqrt(sum((a - b) ** 2
                         for a, b in zip(_lab(one, linear), _lab(two, linear))))


def lightness(fill):
    return _lab(on_paper(fill))[0]


def polygon_area(outline):
    return abs(signed_area(list(outline))) / 2.0


class OutlineTests(unittest.TestCase):
    """Turning a shape into triangles must not change the shape."""

    def test_every_shape_triangulates_to_its_own_area(self):
        """Including the tee, which is the one concave shape.

        A triangle fan — the obvious way, and what pyglet's Polygon
        does — paints across the notch between the tee's arms and
        comes out too big. Comparing areas catches that; comparing
        triangle counts would not.
        """
        for shape in EVERY_SHAPE:
            outline = shape.outline()
            pieces = triangulate(list(outline))
            covered = sum(
                abs((two.x - one.x) * (three.y - one.y)
                    - (three.x - one.x) * (two.y - one.y)) / 2.0
                for one, two, three in pieces)
            self.assertAlmostEqual(covered, polygon_area(outline), places=6,
                                   msg=shape.kind)

    def test_the_tee_is_the_one_shape_the_fan_is_wrong_for(self):
        """Otherwise the test above proves nothing about concavity.

        Convex outlines take a triangle fan, which is exact and cheap;
        the tee must not, and must be routed to ear clipping instead.
        Misclassifying it would paint across the notch between its arms.
        """
        convex = dict((shape.kind, is_convex(list(shape.outline())))
                      for shape in EVERY_SHAPE)
        self.assertFalse(convex.pop('tee'))
        self.assertTrue(all(convex.values()), convex)

    def test_an_ellipse_is_round_enough(self):
        outline = ellipse_outline(100.0, 50.0)
        self.assertLess(abs(polygon_area(outline) - math.pi * 50.0 * 25.0)
                        / (math.pi * 50.0 * 25.0), 0.005)

    def test_scaling_and_rotation_do_what_they_say(self):
        square = [Point(-10, -10), Point(10, -10), Point(10, 10),
                  Point(-10, 10)]
        bigger = transformed(square, 2.0, 0, Point(0, 0))
        self.assertAlmostEqual(polygon_area(bigger), 4 * polygon_area(square))
        turned = transformed(square, 1.0, 90, Point(0, 0))
        self.assertAlmostEqual(polygon_area(turned), polygon_area(square))
        # A quarter turn takes the first corner to where the last was.
        self.assertAlmostEqual(turned[0].x, 10.0)
        self.assertAlmostEqual(turned[0].y, -10.0)


class RouteTests(unittest.TestCase):
    """A route has to reach every cell, exactly once, and be reversible."""

    def test_every_route_covers_the_grid_exactly_once(self):
        for kind in transforms.ROUTES:
            route = kind(3, 3)
            seen = []
            for base in route.bases:
                seen.append(base)
                seen.extend(route.walk(base))
            self.assertEqual(sorted(seen),
                             sorted(transforms.Location(row, column)
                                    for row in range(3)
                                    for column in range(3)),
                             kind.__name__)

    def test_a_cell_steps_back_to_where_it_came_from(self):
        """A rule reads its input through ``source``, and writes through
        ``step``. If the two disagree anywhere, a cell derives from a
        cell that never fed it and the grid stops being a pattern."""
        for kind in transforms.ROUTES:
            route = kind(3, 3)
            for row in range(3):
                for column in range(3):
                    here = transforms.Location(row, column)
                    self.assertEqual(route.step(route.source(here)), here,
                                     '%s at %r' % (kind.__name__, here))

    def test_diagonals_are_withheld_from_grids_they_do_not_fit(self):
        """They only cover an odd-sided square; elsewhere they would
        revisit cells and leave others empty."""
        square = transforms.available_routes(3, 3)
        oblong = transforms.available_routes(3, 4)
        even = transforms.available_routes(4, 4)
        for kind in transforms.DIAGONAL_ROUTES:
            self.assertIn(kind, square)
            self.assertNotIn(kind, oblong)
            self.assertNotIn(kind, even)


class SurfaceTests(unittest.TestCase):
    """When two drawings count as the same drawing."""

    def test_every_fill_has_its_own_name(self):
        """Fills are compared by name, so two sharing one are one fill.

        The original gave two different greys the same name, and a
        choice differing only in being one grey rather than the other
        was thrown away as a duplicate of it.
        """
        names = [fill.name for fill in surfaces.ALL_FILLS]
        self.assertEqual(len(names), len(set(names)), names)

    def test_every_fill_is_visibly_different_from_the_others(self):
        """Distinct names are not enough; they have to look different.

        Each fill is a wash over white paper, so what the player sees
        is the composite, not the colour as written down.
        """
        for palette in (surfaces.GREYS, surfaces.COLOURS):
            for one, two in itertools.combinations(palette.ramp, 2):
                gap = delta_e(on_paper(one), on_paper(two))
                self.assertGreater(gap, JUST_NOTICEABLE * 2,
                                   '%s and %s are too close in %s (dE %.1f)'
                                   % (one.name, two.name, palette.name, gap))

    def test_the_same_drawing_at_a_different_scale_is_the_same_drawing(self):
        small = Surface('rectangle', 25.0, 25.0, Point(50, 50),
                        surfaces.WHITE, scale=2.0)
        big = Surface('rectangle', 50.0, 50.0, Point(50, 50), surfaces.WHITE)
        self.assertTrue(small.looks_like(big))

    def test_a_turned_triangle_is_not_the_same_drawing(self):
        upright = Surface('triangle', 50.0, 75.0, Point(50, 50),
                          surfaces.WHITE)
        self.assertFalse(upright.looks_like(upright.rotated(180)))

    def test_shading_alone_makes_two_drawings_different(self):
        pale = Surface('ellipse', 50.0, 50.0, Point(50, 50), surfaces.WHITE)
        self.assertFalse(pale.looks_like(pale.filled(surfaces.BLACK)))

    def test_cells_are_compared_without_regard_to_order(self):
        one, two = EVERY_SHAPE[0], EVERY_SHAPE[1]
        self.assertTrue(same_picture([one, two], [two, one]))
        self.assertFalse(same_picture([one, two], [one, one]))


class RuleTests(unittest.TestCase):
    """Each rule has to actually change what it claims to change."""

    def setUp(self):
        self.rng = random.Random(20260820)
        self.route = transforms.Vertical(3, 3)
        self.shape = Surface('rectangle', 50.0, 50.0, Point(50, 50),
                             surfaces.WHITE)

    def _down_a_column(self, rule, start):
        """What one column holds, top to bottom, under ``rule``."""
        column = [start]
        for _step in range(2):
            column.append(rule.derive(column[-1], column[-1]))
        return column

    def test_rotation_turns_by_the_same_amount_at_each_step(self):
        rule = ruleset.ApplyRotation(self.route)
        column = self._down_a_column(rule, [self.shape])
        self.assertEqual([cell[0].rotation for cell in column],
                         [0, ruleset.ROTATION_STEP, 2 * ruleset.ROTATION_STEP])

    def test_scaling_shrinks_by_the_same_factor_at_each_step(self):
        rule = ruleset.ApplyScaling(self.route)
        column = self._down_a_column(rule, [self.shape])
        self.assertAlmostEqual(column[1][0].scale, rule.factor)
        self.assertAlmostEqual(column[2][0].scale, rule.factor ** 2)

    def test_a_long_route_shrinks_more_gently_than_a_short_one(self):
        """The factor compounds, so a fixed one ruins the long route.

        Sweeping outward from the top-left corner is eight steps on a
        three-by-three grid against a column's two. Shrinking by a
        third each time would end at 3.6% of the size it started —
        a dot, and eight dots to choose between.
        """
        short = ruleset.ApplyScaling(transforms.Vertical(3, 3))
        long = ruleset.ApplyScaling(transforms.CornerOut(3, 3))
        self.assertGreater(long.factor, short.factor)
        for rule in (short, long):
            steps = len(rule.route.walk(rule.route.bases[0]))
            self.assertAlmostEqual(rule.factor ** steps,
                                   ruleset.SMALLEST_SCALE, places=6)

    def test_nothing_is_ever_shrunk_out_of_sight(self):
        """Whatever route a shrinking rule takes, across every puzzle."""
        smallest = 1.0
        for seed in range(400):
            puzzle = ravens.generate(seed=seed, layers=2, rules_per_layer=3,
                                     palettes=surfaces.PALETTES)
            for cell in ([c for row in puzzle.cells for c in row]
                         + puzzle.choices):
                for shape in cell:
                    drawn = (max(shape.width, shape.height) * shape.scale
                             / float(puzzle.cell_size))
                    smallest = min(smallest, drawn)
        self.assertGreater(smallest, 0.05,
                           'a shape was drawn at %.1f%% of the cell'
                           % (smallest * 100))

    def test_changing_the_fill_moves_one_place_and_wraps(self):
        rule = ruleset.ChangeFill(self.route)
        names = [fill.name for fill in rule.fills]
        current = [self.shape.filled(rule.fills[0])]
        for expected in names[1:] + names[:1]:
            current = rule.derive(current, current)
            self.assertEqual(current[0].fill.name, expected)

    def test_counting_adds_exactly_one_copy_at_each_step(self):
        rule = ruleset.Numerosity(self.route, 100, 3, 3, initial=1)
        cell = rule.seed(0, [self.shape])
        counts = [len(cell)]
        for _step in range(3):
            cell = rule.derive(cell, cell)
            counts.append(len(cell))
        self.assertEqual(counts, [1, 2, 3, 4])

    def test_counted_copies_do_not_sit_on_top_of_one_another(self):
        rule = ruleset.Numerosity(self.route, 100, 3, 3, initial=1)
        cell = rule.derive(rule.derive(rule.seed(0, [self.shape]),
                                       [self.shape]), [self.shape])
        spots = [(round(shape.position.x, 3), round(shape.position.y, 3))
                 for shape in cell]
        self.assertEqual(len(spots), len(set(spots)), spots)

    def _logic(self, kind):
        shapes = list(EVERY_SHAPE[:3])
        rule = kind(transforms.LogicRoute(3, 3), shapes, self.rng)
        return rule, shapes

    def test_and_keeps_only_what_is_in_both(self):
        rule, shapes = self._logic(ruleset.LogicalAnd)
        got = rule.combine([shapes[0], shapes[1]], [shapes[1], shapes[2]])
        self.assertTrue(same_picture(got, [shapes[1]]))

    def test_or_keeps_everything_once(self):
        rule, shapes = self._logic(ruleset.LogicalOr)
        got = rule.combine([shapes[0], shapes[1]], [shapes[1], shapes[2]])
        self.assertTrue(same_picture(got, shapes))

    def test_xor_keeps_only_what_is_in_one(self):
        rule, shapes = self._logic(ruleset.LogicalXor)
        got = rule.combine([shapes[0], shapes[1]], [shapes[1], shapes[2]])
        self.assertTrue(same_picture(got, [shapes[0], shapes[2]]))

    def test_a_logic_rule_uses_every_shape_it_was_given(self):
        """A shape assigned to no cell cannot be reasoned about, and a
        given cell left empty makes its combinations empty too."""
        for _try in range(60):
            rule, shapes = self._logic(ruleset.LogicalXor)
            for group in rule.assignments:
                self.assertTrue(group)
            placed = [shape for group in rule.assignments for shape in group]
            for shape in shapes:
                self.assertTrue(any(shape.looks_like(other)
                                    for other in placed))


class PuzzleTests(unittest.TestCase):
    """What every generated puzzle has to be true of."""

    def _puzzles(self, count=SAMPLE, **kwargs):
        for seed in range(count):
            yield ravens.generate(seed=seed, **kwargs)

    def test_a_seed_always_builds_the_same_puzzle(self):
        first = ravens.generate(seed=99, layers=2, rules_per_layer=3)
        again = ravens.generate(seed=99, layers=2, rules_per_layer=3)
        self.assertEqual(first.answer, again.answer)
        for one, two in zip(first.choices, again.choices):
            self.assertTrue(same_picture(one, two))

    def test_the_answer_is_the_cell_that_was_taken_out(self):
        for puzzle in self._puzzles():
            self.assertTrue(same_picture(puzzle.choices[puzzle.answer],
                                         puzzle.question))

    def test_no_two_choices_draw_the_same_picture(self):
        """Two identical choices mean the puzzle has two right answers
        or two equally wrong ones, and either is unfair."""
        for puzzle in self._puzzles():
            for first in range(len(puzzle.choices)):
                for second in range(first + 1, len(puzzle.choices)):
                    self.assertFalse(
                        same_picture(puzzle.choices[first],
                                     puzzle.choices[second]),
                        'choices %d and %d are the same picture'
                        % (first, second))

    def test_no_choice_is_blank(self):
        """The original padded with empty boxes when it ran out of
        ideas, which tells the player which boxes to ignore."""
        for puzzle in self._puzzles():
            for index, choice in enumerate(puzzle.choices):
                self.assertTrue(choice, 'choice %d is empty' % index)

    def test_the_right_answer_lands_everywhere_over_a_run(self):
        seen = set(puzzle.answer for puzzle in self._puzzles(80))
        self.assertEqual(seen, set(range(8)))

    def test_a_level_carries_the_number_of_rules_it_promises(self):
        """The level is what an adaptive run moves the player along, so
        it has to mean something. A logic layer is the one exception:
        combining two cells is the whole of what such a layer says, and
        it takes no further rules.
        """
        logic = [kind.description for kind in
                 (ruleset.LogicalAnd, ruleset.LogicalOr, ruleset.LogicalXor)]
        for rules in (1, 2, 3):
            for puzzle in self._puzzles(60, layers=1, rules_per_layer=rules):
                lines = puzzle.explanation
                if any(line in logic for line in lines):
                    self.assertEqual(len(lines), 1)
                else:
                    self.assertEqual(len(lines), rules, lines)

    def test_two_layers_are_described_apart(self):
        for puzzle in self._puzzles(40, layers=2, rules_per_layer=2):
            self.assertTrue(any(line.startswith('layer 1: ')
                                for line in puzzle.explanation))
            self.assertTrue(any(line.startswith('layer 2: ')
                                for line in puzzle.explanation))

    def test_a_puzzle_that_cannot_be_filled_is_thrown_away(self):
        """Rather than padded. The stall is raised from deep inside, so
        this checks the retry actually catches it."""
        real = engine._build_choices

        def always_stalls(*args, **kwargs):
            raise engine._Stalled()

        engine._build_choices = always_stalls
        try:
            with self.assertRaises(RuntimeError):
                ravens.generate(seed=1, attempts=3)
        finally:
            engine._build_choices = real



class PaletteTests(unittest.TestCase):
    """Colour has to be readable by everyone the game is for.

    A rule about colour is unanswerable by a player who cannot see the
    difference the rule turns on, and roughly one man in twelve has
    some red-green deficiency. So the palette is not a matter of taste
    here: every pair is simulated for each kind of dichromacy and
    checked to stay apart.
    """

    def test_colours_stay_apart_for_every_kind_of_eye(self):
        for kind in VISION:
            for one, two in itertools.combinations(surfaces.COLOUR_FILLS, 2):
                gap = delta_e(as_seen(on_paper(one), kind),
                              as_seen(on_paper(two), kind), linear=True)
                self.assertGreater(
                    gap, JUST_NOTICEABLE * 4,
                    '%s and %s are only %.1f apart under %s'
                    % (one.name, two.name, gap, kind))

    def test_colours_are_no_harder_to_tell_apart_than_the_greys(self):
        """The claim the palette was chosen on, kept honest."""
        def worst(fills):
            return min(delta_e(as_seen(on_paper(one), kind),
                               as_seen(on_paper(two), kind), linear=True)
                       for kind in VISION
                       for one, two in itertools.combinations(fills, 2))

        self.assertGreater(worst(surfaces.COLOUR_FILLS),
                           worst(surfaces.ALL_FILLS))

    def test_the_colour_ramp_is_also_a_lightness_ramp(self):
        """So the rule can be followed without seeing colour at all.

        A player who cannot separate the hues still sees the steps get
        darker, which is the same rule the grey puzzles ask for.
        """
        levels = [lightness(fill) for fill in surfaces.COLOUR_FILLS]
        self.assertEqual(levels, sorted(levels, reverse=True), levels)
        for brighter, darker in zip(levels, levels[1:]):
            self.assertGreater(brighter - darker, 5.0, levels)

    def test_a_palette_offers_a_ramp_of_five_and_a_basic_three(self):
        for palette in (surfaces.GREYS, surfaces.COLOURS):
            self.assertEqual(len(palette.ramp), 5, palette.name)
            self.assertEqual(len(palette.basic), 3, palette.name)
            for fill in palette.basic:
                self.assertIn(fill, palette.ramp, palette.name)

    def test_a_puzzle_never_mixes_the_two(self):
        """A wrong answer in the wrong palette would stand out as wrong
        without any of the rules being read."""
        for seed in range(120):
            puzzle = ravens.generate(seed=seed, layers=2, rules_per_layer=3,
                                     palettes=surfaces.PALETTES)
            allowed = set(fill.name for fill in puzzle.palette.ramp)
            everywhere = ([cell for row in puzzle.cells for cell in row]
                          + puzzle.choices)
            for cell in everywhere:
                for shape in cell:
                    self.assertIn(shape.fill.name, allowed,
                                  'a %s fill in a %s puzzle'
                                  % (shape.fill.name, puzzle.palette.name))

    def test_greys_only_unless_colour_is_asked_for(self):
        for seed in range(60):
            puzzle = ravens.generate(seed=seed, palettes=(surfaces.GREYS,))
            self.assertEqual(puzzle.palette.name, 'greys')

    def test_a_colour_puzzle_says_colour_when_it_is_explained(self):
        said = set()
        for seed in range(300):
            puzzle = ravens.generate(seed=seed, layers=1, rules_per_layer=2,
                                     palettes=(surfaces.COLOURS,))
            said.update(line for line in puzzle.explanation)
        self.assertTrue(any('colour' in line for line in said))
        self.assertFalse(any('shading' in line for line in said), said)


class RuleClashTests(unittest.TestCase):
    """Two rules in a layer must not write the same property."""

    @staticmethod
    def _families():
        """Each supplemental rule's opening words, and what it writes."""
        route = transforms.Vertical(3, 3)
        found = {}
        for palette in (surfaces.GREYS, surfaces.COLOURS):
            for kind in ruleset.SUPPLEMENTALS:
                if kind is ruleset.Numerosity:
                    rule = kind(route, 100, 3, 3, 1)
                elif kind in (ruleset.ChangeFill, ruleset.FillRepetition):
                    rule = kind(route, palette)
                else:
                    rule = kind(route)
                found[rule.description] = ruleset.RULE_WRITES[kind]
        return found

    def test_the_rule_descriptions_are_all_accounted_for(self):
        """Otherwise the test below would read no rules and pass."""
        families = self._families()
        self.assertEqual(len(families), 7)   # two of them vary by palette
        self.assertEqual(set(families.values()), {'turn', 'size', 'fill'})

    def test_no_layer_carries_two_rules_that_overwrite_each_other(self):
        """The second would simply undo the first, leaving a rule the
        puzzle claims and never shows — worse than one rule fewer,
        because a player looks for it."""
        families = self._families()
        read = 0
        for seed in range(400):
            puzzle = ravens.generate(seed=seed, layers=1, rules_per_layer=3,
                                     palettes=surfaces.PALETTES)
            written = []
            for line in puzzle.explanation:
                for description, family in families.items():
                    if line.startswith(description):
                        written.append(family)
                        break
            read += len(written)
            self.assertEqual(len(written), len(set(written)),
                             puzzle.explanation)
        # The loop above is only worth anything if it read some rules.
        self.assertGreater(read, 300, 'no supplemental rules were read')

    def test_choosing_supplementals_never_repeats_a_property(self):
        rng = random.Random(4)
        for _try in range(400):
            for wanted in (1, 2, 3):
                chosen = ruleset.choose_supplementals(wanted, rng)
                written = [ruleset.RULE_WRITES[kind] for kind in chosen]
                self.assertEqual(len(written), len(set(written)), chosen)
                self.assertLessEqual(len(chosen), wanted)

    def test_counting_and_scaling_are_treated_as_one_property(self):
        """Counting sizes its copies to fit the cell; a scaling rule
        applied afterwards resets that and they spill out."""
        self.assertEqual(ruleset.RULE_WRITES[ruleset.Numerosity],
                         ruleset.RULE_WRITES[ruleset.ApplyScaling])


class ShallowCueTests(unittest.TestCase):
    """No property of a choice may pick the answer out on its own.

    A player who has found no rule can still look for the odd one out —
    the only box with four shapes, the only one holding a triangle, the
    only blue one. Each of those has to be no better than guessing,
    which with eight choices means about one time in eight.
    """

    CUES = {
        'how many shapes': lambda cell: len(cell),
        'which shadings': lambda cell: frozenset(shape.fill.name
                                                 for shape in cell),
        'which shapes': lambda cell: frozenset(shape.kind for shape in cell),
    }

    def test_no_single_cue_finds_the_answer_better_than_guessing(self):
        for layers, rules in ((1, 2), (2, 3)):
            alone = dict((cue, 0) for cue in self.CUES)
            for seed in range(SAMPLE):
                puzzle = ravens.generate(seed=seed, layers=layers,
                                         rules_per_layer=rules,
                                         palettes=surfaces.PALETTES)
                for cue, read in self.CUES.items():
                    wanted = read(puzzle.choices[puzzle.answer])
                    if sum(1 for choice in puzzle.choices
                           if read(choice) == wanted) == 1:
                        alone[cue] += 1
            for cue, count in alone.items():
                self.assertLess(
                    count / float(SAMPLE), 0.25,
                    '%d layers, %d rules: "%s" alone picks the answer in '
                    '%d of %d puzzles' % (layers, rules, cue, count, SAMPLE))

    def test_some_wrong_answers_are_the_right_one_barely_changed(self):
        """The strategy the original declared and never wrote. Without
        it the wrong answers all come from elsewhere in the grid, and
        none of them looks much like the answer."""
        seen = 0
        for seed in range(80):
            puzzle = ravens.generate(seed=seed, layers=2, rules_per_layer=3,
                                     palettes=surfaces.PALETTES)
            if engine.NEAR_MISS in puzzle.origins:
                seen += 1
        self.assertGreater(seen, 60, '%d of 80 puzzles had a near miss' % seen)

    def test_a_near_miss_holds_the_answer_shapes_and_one_change(self):
        rng = random.Random(11)
        for _try in range(300):
            answer = [Surface('rectangle', 50.0, 75.0, Point(50, 50),
                              surfaces.WHITE),
                      Surface('triangle', 25.0, 50.0, Point(50, 50),
                              surfaces.BLACK)]
            near = engine._near_miss(answer, surfaces.GREYS, 100, rng)
            self.assertEqual(len(near), len(answer))
            self.assertFalse(same_picture(near, answer))
            differing = sum(1 for one, two in zip(near, answer)
                            if not one.looks_like(two))
            self.assertEqual(differing, 1, near)

    def test_a_near_miss_is_never_drawn_bigger_than_its_box(self):
        """A shape past its own box reads as broken rather than wrong,
        and a player learns to skip the broken-looking one."""
        rng = random.Random(5)
        widest = Surface('rectangle', 75.0, 75.0, Point(50, 50),
                         surfaces.WHITE)
        for _try in range(400):
            near = engine._near_miss([widest], surfaces.GREYS, 100, rng)
            for shape in near:
                self.assertLessEqual(
                    max(shape.width, shape.height) * shape.scale, 90.0)


@needs_ui
class MatrixHubTests(unittest.TestCase):
    """The task is reachable and named."""

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_reasoning(self):
        ids = [task_id for task_id, _label in TASKS['reasoning']]
        self.assertIn('matrix_reasoning', ids)

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

    def _ask(self):
        self.task.start_run()
        return self.task.puzzle

    def test_it_draws_a_puzzle_without_complaint(self):
        self._ask()
        self.task.on_draw()
        self.assertEqual(self.task.phase, 'asking')
        self.assertEqual(len(self.task.sprites), 1 + 8)

    def test_painting_a_card_leaves_the_clear_colour_alone(self):
        """A card is painted on white paper, and the clear colour is
        global: left set, the window itself clears to white on the next
        frame, which on the dark theme is white text on white.

        The colour is set to black here rather than merely read back
        first. Reading it would compare paper white against paper white
        if anything earlier had already left it set, and the test would
        pass on exactly the fault it exists to catch.
        """
        from pyglet import gl
        gl.glClearColor(0., 0., 0., 1.)
        try:
            self._ask()
            after = (gl.GLfloat * 4)()
            gl.glGetFloatv(gl.GL_COLOR_CLEAR_VALUE, after)
            self.assertEqual(list(after), [0., 0., 0., 1.])
        finally:
            black = state.cfg.BLACK_BACKGROUND
            gl.glClearColor(*((0., 0., 0., 1.) if black
                              else (1., 1., 1., 1.)))

    def test_the_right_key_scores_and_a_wrong_one_does_not(self):
        puzzle = self._ask()
        self.task.on_key_press(key._1 + puzzle.answer, 0)
        self.assertEqual(self.task.correct, 1)

        puzzle = self.task.puzzle or self._ask()
        self.task.phase = 'asking'
        self.task.on_key_press(key._1 + (puzzle.answer + 1) % 8, 0)
        self.assertEqual(self.task.correct, 1)

    def test_clicking_a_box_answers_it(self):
        puzzle = self._ask()
        left, bottom, width, height = \
            self.task._choice_rects()[puzzle.answer]
        self.task.on_mouse_press(int(left + width / 2),
                                 int(bottom + height / 2), 1, 0)
        self.assertEqual(self.task.correct, 1)

    def test_clicking_outside_every_box_answers_nothing(self):
        self._ask()
        self.task.on_mouse_press(2, 2, 1, 0)
        self.assertIsNone(self.task.picked)

    def test_a_right_answer_goes_up_a_level_and_a_wrong_one_down(self):
        self.task.adaptive = True
        self.task.start_level = 2
        self._ask()
        self.assertEqual(self.task.level, 1)
        self.task.answer(self.task.puzzle.answer)
        self.assertEqual(self.task.level, 2)
        self.task.phase = 'asking'
        self.task.answer((self.task.puzzle.answer + 1) % 8)
        self.assertEqual(self.task.level, 1)

    def test_the_level_never_leaves_the_ladder(self):
        from neural_workshop.ui.ravens import LADDER
        self.assertEqual(self.task.clamped(-5), 0)
        self.assertEqual(self.task.clamped(99), len(LADDER) - 1)

    def test_the_reported_level_is_the_one_the_puzzle_was_asked_at(self):
        """It has already moved on by the time the answer is shown.

        Checked on the words the player reads, not on the attribute
        behind them: the attribute being right is no help if the label
        is built from the other one.
        """
        self.task.adaptive = True
        self.task.feedback = True
        self.task.start_level = 2
        self._ask()
        asked_at = self.task.trial_level
        self.task.answer(self.task.puzzle.answer)
        self.assertNotEqual(self.task.level, asked_at)
        self.assertIn('level %d' % (asked_at + 1), self.task.status.text)

    def test_resizing_keeps_the_same_puzzle(self):
        puzzle = self._ask()
        state.window.set_size(720, 560)
        display.ensure_laid_out()
        self.task.relayout()
        self.assertIs(self.task.puzzle, puzzle)
        self.task.on_draw()

    def test_closing_gives_back_its_textures_and_handlers(self):
        self._ask()
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
