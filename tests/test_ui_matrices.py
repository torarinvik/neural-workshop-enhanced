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
        is the composite, not the colour.
        """
        seen = []
        for fill in surfaces.ALL_FILLS:
            red, green, blue, alpha = fill.color
            over_paper = round(red * alpha / 255. + 255 * (1 - alpha / 255.))
            for other in seen:
                self.assertGreater(abs(over_paper - other), 8,
                                   'fills too close: %s' % fill.name)
            seen.append(over_paper)

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
        self.assertAlmostEqual(column[1][0].scale, ruleset.SCALE_STEP)
        self.assertAlmostEqual(column[2][0].scale, ruleset.SCALE_STEP ** 2)

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

    def test_counting_the_shapes_does_not_give_the_answer_away(self):
        """A player who finds no rule can still count the shapes in
        each box and pick the odd one out. That has to be no better
        than guessing, so the generator holds out for wrong answers
        that hide the right one's count.
        """
        for layers, rules in ((1, 2), (2, 3)):
            lonely = 0
            for puzzle in self._puzzles(SAMPLE, layers=layers,
                                        rules_per_layer=rules):
                wanted = len(puzzle.choices[puzzle.answer])
                if sum(1 for choice in puzzle.choices
                       if len(choice) == wanted) == 1:
                    lonely += 1
            # Chance alone would leave the answer alone in its count
            # about an eighth of the time.
            self.assertLess(lonely / float(SAMPLE), 0.25,
                            '%d layers, %d rules: %d of %d puzzles give the '
                            'answer away by count' % (layers, rules, lonely,
                                                      SAMPLE))

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
