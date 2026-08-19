#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Count: the perception task, and the tangles it generates.

Most of what can go wrong here is geometric — a shape drawn outside
the area it belongs in, or a "line" so short it is a dot — so the
generator is tested over many shapes rather than one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import unittest

from uisupport import (Counting, TASKS, TaskHub, close_overlays, display,
                       geometry, key, needs_ui, reset_window, state)

#: Enough shapes that a rare bad case still shows up.
SAMPLE = 400


class PerceptionCategoryTests(unittest.TestCase):
    """The hub gained a category, and it holds the task."""

    def test_perception_is_a_category(self):
        from neural_workshop.ui.taskhub import CATEGORIES
        self.assertIn('perception', [cat for cat, _name in CATEGORIES])
        self.assertIn('perception', TASKS)

    def test_count_is_in_it(self):
        self.assertEqual([task for task, _name in TASKS['perception']],
                         ['count'])

    def test_it_has_an_options_screen(self):
        from neural_workshop.ui import taskoptions
        self.assertTrue(taskoptions.has_options('count'))


@needs_ui
class PerceptionHubTests(unittest.TestCase):
    """Five categories still lay out."""

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_the_hub_shows_it(self):
        hub = TaskHub(category='perception')
        self.assertEqual(hub.selected_task(), 'count')
        self.assertEqual(len(hub.tab_rects), len(TASKS))
        hub.on_draw()

    def test_the_tabs_still_fit_the_window(self):
        hub = TaskHub()
        for left, _bottom, width, _height, _cat in hub.tab_rects:
            self.assertGreaterEqual(left, 0)
            self.assertLessEqual(left + width, state.window.width)

    def test_the_tabs_do_not_overlap(self):
        hub = TaskHub()
        rects = sorted(hub.tab_rects, key=lambda r: r[0])
        for first, second in zip(rects, rects[1:]):
            self.assertLessEqual(first[0] + first[2], second[0])


@needs_ui
class ShapeGeneratorTests(unittest.TestCase):
    """Every shape must sit inside the area it is drawn in."""

    def setUp(self):
        close_overlays()
        from neural_workshop.ui import taskoptions
        self.saved = {option.key: state.cfg[option.key]
                      for option in taskoptions.COUNTING.options}
        self.game = Counting()

    def tearDown(self):
        close_overlays()
        state.cfg.update(self.saved)
        reset_window()

    def _generate(self, kind, count=SAMPLE):
        state.cfg.COUNT_SHAPE = kind
        self.game.apply_options()
        return self.game.generate(count)

    def test_every_kind_stays_inside_the_area(self):
        from neural_workshop.ui.counting import MIXED_KINDS, MIXED
        for kind in tuple(MIXED_KINDS) + (MIXED,):
            for shape in self._generate(kind):
                for x, y in shape.points:
                    self.assertGreaterEqual(x, 0.0, kind)
                    self.assertLessEqual(x, 1.0, kind)
                    self.assertGreaterEqual(y, 0.0, kind)
                    self.assertLessEqual(y, 1.0, kind)

    def test_circles_keep_their_radius_off_the_edge(self):
        from neural_workshop.ui.counting import CIRCLES
        for shape in self._generate(CIRCLES):
            (x, y), radius = shape.points[0], shape.radius
            self.assertGreater(radius, 0)
            self.assertGreaterEqual(x - radius, -0.001)
            self.assertLessEqual(x + radius, 1.001)
            self.assertGreaterEqual(y - radius, -0.001)
            self.assertLessEqual(y + radius, 1.001)

    def test_lines_are_long_enough_to_be_lines(self):
        from neural_workshop.ui.counting import LINES, MIN_LINE_SPAN
        for shape in self._generate(LINES, 2000):
            span = math.dist(shape.points[0], shape.points[1])
            self.assertGreaterEqual(span, MIN_LINE_SPAN)

    def test_lines_span_the_area_rather_than_huddling(self):
        from neural_workshop.ui.counting import LINES
        spans = [math.dist(s.points[0], s.points[1])
                 for s in self._generate(LINES)]
        self.assertGreater(sum(spans) / len(spans), 0.5)

    def test_lines_point_in_all_sorts_of_directions(self):
        from neural_workshop.ui.counting import LINES
        angles = set()
        for shape in self._generate(LINES):
            (x1, y1), (x2, y2) = shape.points
            angles.add(round(math.degrees(math.atan2(y2 - y1, x2 - x1)) / 30))
        self.assertGreater(len(angles), 4)

    def test_the_count_asked_for_is_the_count_made(self):
        for wanted in (1, 2, 8, 30):
            self.assertEqual(len(self._generate('lines', wanted)), wanted)

    def test_one_kind_makes_only_that_kind(self):
        from neural_workshop.ui.counting import MIXED_KINDS
        for kind in MIXED_KINDS:
            self.assertEqual({s.kind for s in self._generate(kind, 50)},
                             {kind})

    def test_mixed_really_mixes(self):
        from neural_workshop.ui.counting import MIXED, MIXED_KINDS
        self.assertEqual({s.kind for s in self._generate(MIXED)},
                         set(MIXED_KINDS))

    def test_every_kind_builds_a_drawable(self):
        from neural_workshop.ui.counting import MIXED
        for shape in self._generate(MIXED, 60):
            built = self.game._build_shape(shape)
            self.assertIsNotNone(built, shape.kind)
            built.delete()

    def test_shapes_land_inside_the_canvas_in_pixels(self):
        from neural_workshop.ui.counting import MIXED
        left, bottom, width, height = self.game.canvas()
        for shape in self._generate(MIXED, 200):
            for point in shape.points:
                x, y = self.game._to_pixels(point)
                self.assertGreaterEqual(x, left - 1)
                self.assertLessEqual(x, left + width + 1)
                self.assertGreaterEqual(y, bottom - 1)
                self.assertLessEqual(y, bottom + height + 1)


@needs_ui
class CountingRunTests(unittest.TestCase):
    """Answering, scoring and adapting."""

    def setUp(self):
        close_overlays()
        from neural_workshop.ui import taskoptions
        self.saved = {option.key: state.cfg[option.key]
                      for option in taskoptions.COUNTING.options}
        state.cfg.COUNT_SHAPE = 'lines'
        state.cfg.COUNT_START = 6
        state.cfg.COUNT_TRIALS = 5
        state.cfg.COUNT_EXPOSURE_MS = 0
        state.cfg.COUNT_ADAPTIVE = True
        state.cfg.COUNT_SHOW_ANSWER = False
        self.game = Counting()

    def tearDown(self):
        close_overlays()
        state.cfg.update(self.saved)
        reset_window()

    def _answer(self, number):
        for digit in str(number):
            self.game.type_digit(digit)
        self.game.submit()

    def test_a_run_shows_the_starting_count(self):
        self.game.start_run()
        self.assertEqual(self.game.count, 6)
        self.assertEqual(len(self.game.shapes_data), 6)
        self.assertEqual(self.game.trial, 1)

    def test_typing_builds_the_answer(self):
        self.game.start_run()
        self.game.type_digit('1')
        self.game.type_digit('2')
        self.assertEqual(self.game.answer_text, '12')
        self.game.backspace()
        self.assertEqual(self.game.answer_text, '1')

    def test_an_empty_answer_is_not_submitted(self):
        self.game.start_run()
        self.game.submit()
        self.assertEqual(self.game.results, [])
        self.assertEqual(self.game.trial, 1)

    def test_the_answer_cannot_run_away(self):
        self.game.start_run()
        for _ in range(8):
            self.game.type_digit('9')
        self.assertLessEqual(len(self.game.answer_text), 3)

    def test_a_right_answer_adds_a_shape(self):
        self.game.start_run()
        before = self.game.count
        self._answer(before)
        self.assertEqual(self.game.count, before + 1)

    def test_a_wrong_answer_drops_one(self):
        self.game.start_run()
        before = self.game.count
        self._answer(before + 3)
        self.assertEqual(self.game.count, before - 1)

    def test_adapting_off_holds_the_count(self):
        state.cfg.COUNT_ADAPTIVE = False
        self.game.apply_options()
        self.game.start_run()
        before = self.game.count
        self._answer(before)
        self._answer(999)
        self.assertEqual(self.game.count, before)

    def test_the_count_stays_within_bounds(self):
        from neural_workshop.ui.counting import MAX_SHAPES, MIN_SHAPES
        self.game.start_run()
        for _ in range(100):
            self.game._adapt(True)
        self.assertEqual(self.game.count, MAX_SHAPES)
        for _ in range(100):
            self.game._adapt(False)
        self.assertEqual(self.game.count, MIN_SHAPES)

    def test_a_perfect_run_scores_full_marks(self):
        self.game.start_run()
        while self.game.phase != 'done':
            self._answer(self.game.count)
        tally = self.game.score()
        self.assertEqual(tally['trials'], 5)
        self.assertEqual(tally['accuracy'], 100)
        self.assertEqual(tally['mean_error'], 0.0)

    def test_being_off_by_one_is_recorded_as_such(self):
        self.game.start_run()
        while self.game.phase != 'done':
            self._answer(self.game.count + 1)
        tally = self.game.score()
        self.assertEqual(tally['accuracy'], 0)
        self.assertEqual(tally['mean_error'], 1.0)

    def test_a_run_is_the_length_asked_for(self):
        self.game.start_run()
        while self.game.phase != 'done':
            self._answer(self.game.count)
        self.assertEqual(len(self.game.results), 5)
        self.assertEqual(self.game.phase, 'done')
        self.assertEqual(self.game.shapes_data, [])

    def test_an_untouched_run_scores_nothing(self):
        self.assertEqual(self.game.score()['trials'], 0)
        self.assertEqual(self.game.score()['accuracy'], 0)

    def test_the_hardest_trial_is_reported(self):
        self.game.start_run()
        while self.game.phase != 'done':
            self._answer(self.game.count)
        self.assertEqual(self.game.score()['hardest'], 10)

    # --- timing and display ---------------------------------------------

    def test_an_exposure_limit_takes_the_shapes_away(self):
        state.cfg.COUNT_EXPOSURE_MS = 500
        self.game.apply_options()
        self.game.start_run()
        self.assertEqual(self.game.phase, 'showing')
        self.assertTrue(self.game.drawn)
        self.game.shown_at = 0
        self.game.update(0.1)
        self.assertEqual(self.game.phase, 'hidden')
        self.assertEqual(self.game.drawn, [])
        self._answer(self.game.count)      # still answerable
        self.assertEqual(len(self.game.results), 1)

    def test_feedback_pauses_between_trials(self):
        state.cfg.COUNT_SHOW_ANSWER = True
        self.game.apply_options()
        self.game.start_run()
        self._answer(self.game.count)
        self.assertEqual(self.game.phase, 'feedback')
        self.game.feedback_until = 0
        self.game.update(0.1)
        self.assertEqual(self.game.phase, 'showing')
        self.assertEqual(self.game.trial, 2)

    def test_a_resize_keeps_the_same_tangle(self):
        self.game.start_run()
        tangle = list(self.game.shapes_data)
        geometry.set_window_size(1024, 768)
        display.relayout()
        self.assertEqual(self.game.shapes_data, tangle)
        self.assertEqual(len(self.game.drawn), len(tangle))

    def test_it_draws_in_every_phase(self):
        self.game.on_draw()
        self.game.start_run()
        self.game.on_draw()
        while self.game.phase != 'done':
            self._answer(self.game.count)
        self.game.on_draw()

    def test_enter_submits_and_digits_type(self):
        self.game.start_run()
        self.game.on_key_press(key._6, 0)
        self.assertEqual(self.game.answer_text, '6')
        self.game.on_key_press(key.RETURN, 0)
        self.assertEqual(len(self.game.results), 1)

    def test_c_opens_the_options_between_runs(self):
        from uisupport import Menu
        from neural_workshop.ui import taskoptions
        self.game.on_key_press(key.C, 0)
        self.assertIsInstance(Menu.instance, taskoptions.TaskOptions)
        Menu.instance.close()

    def test_c_mid_trial_types_nothing_and_opens_nothing(self):
        # C is a digit-entry screen's neighbour; it must not interrupt.
        from uisupport import Menu
        self.game.start_run()
        Menu.instance = None
        self.game.on_key_press(key.C, 0)
        self.assertIsNone(Menu.instance)
        self.assertEqual(self.game.answer_text, '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
