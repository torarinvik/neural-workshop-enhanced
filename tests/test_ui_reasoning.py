#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Graph Mapping: the reasoning task, and the pairs it builds.

Almost everything that can go wrong here is in the graph arithmetic
rather than on the screen, and it goes wrong quietly: a "different"
pair that is secretly the same network still looks like a working
game. So the generator is checked against brute force, and every pair
it builds is checked against the answer it reports.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import random
import unittest

from uisupport import (TASKS, TaskHub, close_overlays, display, key,
                       needs_ui, reset_window, state)
from neural_workshop.ui import graphmapping as gm
from neural_workshop.ui.graphmapping import DIFFERENT, SAME, GraphMapping

#: Enough pairs that a rare dishonest one still shows up.
SAMPLE = 120

#: Sizes small enough to check every relabelling of.
BRUTE_SIZES = (3, 4, 5, 6)


def brute_isomorphic(first: gm.Graph, second: gm.Graph) -> bool:
    """The definition, tried every possible way round."""
    if first.size != second.size or len(first.edges) != len(second.edges):
        return False
    return any(gm.relabel(first, naming).edges == second.edges
               for naming in itertools.permutations(range(first.size)))


class GraphArithmeticTests(unittest.TestCase):
    """The parts that never touch the screen."""

    def setUp(self):
        self.rng = random.Random(20240607)

    def test_isomorphic_agrees_with_brute_force(self):
        for _try in range(600):
            size = self.rng.choice(BRUTE_SIZES)
            lines = self.rng.randrange(size - 1, size * (size - 1) // 2 + 1)
            first = gm.random_graph(size, lines, self.rng)
            second = gm.random_graph(size, lines, self.rng)
            self.assertEqual(gm.isomorphic(first, second),
                             brute_isomorphic(first, second),
                             '%r vs %r' % (first, second))

    def test_a_graph_is_itself(self):
        for size in range(2, gm.MAX_NODES + 1):
            graph = gm.random_graph(size, gm.edge_count(size, 'medium'),
                                    self.rng)
            self.assertTrue(gm.isomorphic(graph, graph))

    def test_renaming_the_nodes_keeps_the_network(self):
        for _try in range(SAMPLE):
            size = self.rng.randrange(3, gm.MAX_NODES + 1)
            graph = gm.random_graph(size, gm.edge_count(size, 'dense'),
                                    self.rng)
            self.assertTrue(gm.isomorphic(graph, gm.shuffled(graph, self.rng)))

    def test_a_star_is_not_a_path(self):
        star = gm.Graph(4, ((0, 1), (0, 2), (0, 3)))
        path = gm.Graph(4, ((0, 1), (1, 2), (2, 3)))
        self.assertFalse(gm.isomorphic(star, path))
        self.assertEqual(sorted(gm.degrees(star)), [1, 1, 1, 3])
        self.assertEqual(sorted(gm.degrees(path)), [1, 1, 2, 2])

    def test_connected_spots_a_graph_in_pieces(self):
        self.assertTrue(gm.connected(gm.Graph(4, ((0, 1), (1, 2), (2, 3)))))
        self.assertFalse(gm.connected(gm.Graph(4, ((0, 1), (2, 3)))))

    def test_edges_are_stored_one_way_round(self):
        self.assertEqual(gm.edge(3, 1), (1, 3))
        self.assertEqual(gm.edge(1, 3), (1, 3))


class GeneratorTests(unittest.TestCase):
    """Every graph a trial can show."""

    def setUp(self):
        self.rng = random.Random(11)

    def test_generated_graphs_are_whole(self):
        for size in range(2, gm.MAX_NODES + 1):
            for density in ('sparse', 'medium', 'dense'):
                graph = gm.random_graph(size, gm.edge_count(size, density),
                                        self.rng)
                self.assertTrue(gm.connected(graph),
                                'a graph in pieces at %d dots' % size)

    def test_generated_graphs_have_the_lines_asked_for(self):
        for size in range(2, gm.MAX_NODES + 1):
            for density in ('sparse', 'medium', 'dense'):
                wanted = gm.edge_count(size, density)
                graph = gm.random_graph(size, wanted, self.rng)
                self.assertEqual(len(graph.edges), wanted)
                self.assertEqual(len(set(graph.edges)), wanted)

    def test_no_line_joins_a_dot_to_itself(self):
        for _try in range(SAMPLE):
            size = self.rng.randrange(2, gm.MAX_NODES + 1)
            graph = gm.random_graph(size, gm.edge_count(size, 'dense'),
                                    self.rng)
            for first, second in graph.edges:
                self.assertLess(first, second)
                self.assertLess(second, size)

    def test_density_is_ordered_and_never_fills_the_graph(self):
        for size in range(4, gm.MAX_NODES + 1):
            most = size * (size - 1) // 2
            counts = [gm.edge_count(size, name)
                      for name in ('sparse', 'medium', 'dense')]
            self.assertEqual(counts, sorted(counts))
            self.assertGreaterEqual(counts[0], size - 1)
            self.assertLess(counts[-1], most,
                            'a complete graph has nothing to decide')

    def test_swapping_partners_leaves_every_count_alone(self):
        for _try in range(SAMPLE * 4):
            size = self.rng.randrange(4, gm.MAX_NODES + 1)
            graph = gm.random_graph(size, gm.edge_count(size, 'medium'),
                                    self.rng)
            other = gm._swap_partners(graph, self.rng)
            if other is None:
                continue
            self.assertEqual(gm.degrees(graph), gm.degrees(other))
            self.assertEqual(len(graph.edges), len(other.edges))

    def test_moving_a_line_leaves_the_line_count_alone(self):
        for _try in range(SAMPLE * 4):
            size = self.rng.randrange(4, gm.MAX_NODES + 1)
            graph = gm.random_graph(size, gm.edge_count(size, 'medium'),
                                    self.rng)
            other = gm._move_a_line(graph, self.rng)
            if other is None:
                continue
            self.assertEqual(len(graph.edges), len(other.edges))

    def test_rewiring_gives_back_a_whole_and_different_graph(self):
        for _try in range(SAMPLE):
            size = self.rng.randrange(5, gm.MAX_NODES + 1)
            graph = gm.random_graph(size, gm.edge_count(size, 'medium'),
                                    self.rng)
            for subtle in (True, False):
                other = gm.rewired(graph, self.rng, keep_degrees=subtle)
                if other is None:
                    continue
                self.assertTrue(gm.connected(other))
                self.assertFalse(gm.isomorphic(graph, other))


class PairTests(unittest.TestCase):
    """What a trial actually puts in front of the player."""

    def setUp(self):
        self.rng = random.Random(5150)

    def pairs(self, size, density='medium', same=False, subtle=True,
              count=SAMPLE):
        lines = gm.edge_count(size, density)
        return [gm.build_pair(size, lines, same, subtle, self.rng)
                for _try in range(count)]

    def test_the_answer_it_reports_is_the_truth(self):
        for size in range(gm.MIN_NODES, gm.MAX_NODES + 1):
            for same in (True, False):
                for first, second, was_same in self.pairs(size, same=same):
                    self.assertEqual(gm.isomorphic(first, second), was_same,
                                     'a pair reported the wrong answer')

    def test_matching_pairs_always_match(self):
        for size in range(gm.MIN_NODES, gm.MAX_NODES + 1):
            for _first, _second, was_same in self.pairs(size, same=True):
                self.assertTrue(was_same)

    def test_counting_dots_or_lines_never_answers_a_trial(self):
        for size in range(gm.MIN_NODES, gm.MAX_NODES + 1):
            for density in ('sparse', 'medium', 'dense'):
                for same in (True, False):
                    for first, second, _was in self.pairs(
                            size, density=density, same=same, count=40):
                        self.assertEqual(first.size, second.size)
                        self.assertEqual(len(first.edges), len(second.edges))

    def test_subtle_mismatches_keep_the_counts_where_that_is_possible(self):
        # Below seven dots there is not always a second graph with the
        # same degrees, so only the sizes that have one are asserted on.
        for size in range(7, gm.MAX_NODES + 1):
            kept = sum(1 for first, second, was_same
                       in self.pairs(size, subtle=True)
                       if not was_same
                       and sorted(gm.degrees(first))
                       == sorted(gm.degrees(second)))
            self.assertGreater(kept, SAMPLE * 0.8,
                               'subtle mismatches are not staying subtle '
                               'at %d dots' % size)

    def test_plain_mismatches_are_usually_answerable_by_counting(self):
        for size in range(6, gm.MAX_NODES + 1):
            told = sum(1 for first, second, was_same
                       in self.pairs(size, subtle=False)
                       if not was_same
                       and sorted(gm.degrees(first))
                       != sorted(gm.degrees(second)))
            self.assertGreater(told, SAMPLE * 0.5,
                               'the easy mode is not easier at %d dots' % size)

    def test_ring_positions_stay_inside_the_panel(self):
        for _try in range(SAMPLE):
            size = self.rng.randrange(gm.MIN_NODES, gm.MAX_NODES + 1)
            spots = gm.ring_positions(size, self.rng)
            self.assertEqual(len(spots), size)
            for across, up in spots:
                self.assertGreaterEqual(across, 0.05)
                self.assertLessEqual(across, 0.95)
                self.assertGreaterEqual(up, 0.05)
                self.assertLessEqual(up, 0.95)

    def test_no_two_dots_land_on_each_other(self):
        for _try in range(SAMPLE):
            size = self.rng.randrange(gm.MIN_NODES, gm.MAX_NODES + 1)
            spots = gm.ring_positions(size, self.rng)
            self.assertEqual(len(set(spots)), size)


class ReasoningCategoryTests(unittest.TestCase):
    """The hub gained a category, and it holds the task."""

    def test_reasoning_is_a_category(self):
        from neural_workshop.ui.taskhub import CATEGORIES
        self.assertIn('reasoning', [cat for cat, _name in CATEGORIES])
        self.assertIn('reasoning', TASKS)

    def test_graph_mapping_is_in_it(self):
        self.assertEqual([task for task, _name in TASKS['reasoning']],
                         ['graph_mapping'])

    def test_it_has_an_options_screen(self):
        from neural_workshop.ui import taskoptions
        self.assertTrue(taskoptions.has_options('graph_mapping'))

    def test_every_option_has_a_default_the_task_can_use(self):
        from neural_workshop.ui import taskoptions
        chosen = taskoptions.settings(taskoptions.GRAPH_MAPPING)
        self.assertEqual(sorted(chosen),
                         sorted(option.key for option
                                in taskoptions.GRAPH_MAPPING.options))


@needs_ui
class ReasoningHubTests(unittest.TestCase):
    """Six categories still lay out."""

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_the_hub_shows_it(self):
        hub = TaskHub(category='reasoning')
        self.assertEqual(hub.selected_task(), 'graph_mapping')
        self.assertEqual(len(hub.tab_rects), len(TASKS))
        hub.on_draw()

    def test_the_tabs_still_fit_the_window(self):
        hub = TaskHub()
        for left, _bottom, width, _height, _cat in hub.tab_rects:
            self.assertGreaterEqual(left, 0)
            self.assertLessEqual(left + width, state.window.width)

    def test_the_tabs_do_not_overlap(self):
        hub = TaskHub()
        edges = sorted((left, left + width)
                       for left, _b, width, _h, _c in hub.tab_rects)
        for (_left, right), (next_left, _r) in zip(edges, edges[1:]):
            self.assertLessEqual(right, next_left)

    def test_arrows_reach_it_one_step_at_a_time(self):
        hub = TaskHub(category='working_memory')
        order = [cat for cat, _name in
                 __import__('neural_workshop.ui.taskhub', fromlist=['x'])
                 .CATEGORIES]
        for expected in order[1:] + order[:1]:
            hub.on_text_motion(key.MOTION_RIGHT)
            self.assertEqual(hub.category, expected)

    def test_launching_it_opens_the_task(self):
        hub = TaskHub(category='reasoning')
        hub.launch()
        self.assertIsNotNone(GraphMapping.instance)
        self.assertIsNone(TaskHub.instance)


@needs_ui
class GraphMappingScreenTests(unittest.TestCase):
    """The task on screen."""

    def setUp(self):
        self.task = GraphMapping()

    def tearDown(self):
        close_overlays()
        reset_window()

    def advance(self):
        """Get past a feedback pause without waiting for it."""
        self.task.feedback_until = 0.0
        self.task.update(0.0)

    def test_it_starts_waiting(self):
        self.assertEqual(self.task.phase, 'ready')
        self.assertFalse(self.task.graphs)
        self.task.on_draw()

    def test_space_starts_a_run(self):
        self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.phase, 'asking')
        self.assertEqual(len(self.task.graphs), 2)
        self.assertEqual(len(self.task.spots), 2)
        self.task.on_draw()

    def test_the_two_panels_hold_the_pair_it_asked_for(self):
        self.task.start_run()
        first, second = self.task.graphs
        self.assertEqual(gm.isomorphic(first, second), self.task.really_same)

    def test_the_dots_are_drawn_inside_their_panel(self):
        self.task.start_run()
        left, bottom, width, height = self.task.canvas()
        for panel in (0, 1):
            for spot in self.task.spots[panel]:
                across, up = self.task._to_pixels(panel, spot)
                self.assertGreaterEqual(across, left)
                self.assertLessEqual(across, left + width)
                self.assertGreaterEqual(up, bottom)
                self.assertLessEqual(up, bottom + height)

    def test_the_panels_do_not_overlap(self):
        self.task.start_run()
        (first_x, _fy, first_side), (second_x, _sy, second_side) = \
            self.task.panels()
        self.assertLessEqual(first_x + first_side / 2,
                             second_x - second_side / 2)

    def test_answering_records_a_result(self):
        self.task.start_run()
        self.task.answer(SAME)
        self.assertEqual(len(self.task.results), 1)
        was_same, said_same, took = self.task.results[0]
        self.assertTrue(said_same)
        self.assertGreaterEqual(took, 0.0)

    def test_a_right_answer_counts_and_a_wrong_one_does_not(self):
        self.task.start_run()
        self.task.answer(SAME if self.task.really_same else DIFFERENT)
        self.assertEqual(self.task.correct, 1)
        self.advance()
        self.task.answer(DIFFERENT if self.task.really_same else SAME)
        self.assertEqual(self.task.correct, 1)

    def test_it_will_not_take_a_second_answer_during_feedback(self):
        self.task.feedback = True
        self.task.start_run()
        self.task.answer(SAME)
        self.assertEqual(self.task.phase, 'feedback')
        self.task.answer(DIFFERENT)
        self.assertEqual(len(self.task.results), 1)

    def test_a_run_ends_after_its_trials(self):
        self.task.total_trials = 3
        self.task.start_run()
        for _trial in range(3):
            self.task.answer(SAME)
            self.advance()
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['trials'], 3)
        self.task.on_draw()

    def test_both_answers_turn_up_in_a_run(self):
        self.task.total_trials = 12
        self.task.start_run()
        asked = []
        for _trial in range(12):
            asked.append(self.task.really_same)
            self.task.answer(SAME)
            self.advance()
        self.assertIn(True, asked)
        self.assertIn(False, asked)

    def test_the_score_keeps_the_two_answers_apart(self):
        self.task.total_trials = 12
        self.task.adaptive = False
        self.task.start_run()
        for _trial in range(12):
            self.task.answer(DIFFERENT)     # a player who never says "same"
            self.advance()
        tally = self.task.score()
        self.assertEqual(tally['same_right'], 0)
        self.assertEqual(tally['different_right'], tally['different_total'])
        self.assertEqual(tally['same_total'] + tally['different_total'],
                         tally['trials'])

    def test_adapting_stays_between_its_bounds(self):
        self.task.adaptive = True
        self.task.nodes = gm.MAX_NODES
        self.task._adapt(True)
        self.assertEqual(self.task.nodes, gm.MAX_NODES)
        self.task.nodes = gm.MIN_NODES
        self.task._adapt(False)
        self.assertEqual(self.task.nodes, gm.MIN_NODES)

    def test_it_does_not_adapt_when_told_not_to(self):
        self.task.adaptive = False
        self.task.nodes = 6
        self.task._adapt(True)
        self.task._adapt(False)
        self.assertEqual(self.task.nodes, 6)

    def test_a_time_limit_takes_the_graphs_away_but_not_the_question(self):
        self.task.exposure_ms = 1
        self.task.start_run()
        self.task.asked_at -= 1.0
        self.task.update(0.0)
        self.assertEqual(self.task.phase, 'hidden')
        self.task.on_draw()
        self.task.answer(SAME)
        self.assertEqual(len(self.task.results), 1)

    def test_no_time_limit_leaves_them_up(self):
        self.task.exposure_ms = 0
        self.task.start_run()
        self.task.asked_at -= 60.0
        self.task.update(0.0)
        self.assertEqual(self.task.phase, 'asking')

    def test_the_buttons_are_inside_the_window(self):
        self.task.start_run()
        for left, bottom, width, height, _choice in self.task._button_rects():
            self.assertGreaterEqual(left, 0)
            self.assertGreaterEqual(bottom, 0)
            self.assertLessEqual(left + width, state.window.width)
            self.assertLessEqual(bottom + height, state.window.height)

    def test_clicking_a_button_answers(self):
        self.task.start_run()
        left, bottom, width, height, _choice = self.task._button_rects()[0]
        self.task.on_mouse_press(int(left + width / 2),
                                 int(bottom + height / 2), 1, 0)
        self.assertEqual(len(self.task.results), 1)
        self.assertTrue(self.task.results[0][1])

    def test_clicking_elsewhere_does_not(self):
        self.task.start_run()
        self.task.on_mouse_press(1, state.window.height - 1, 1, 0)
        self.assertEqual(self.task.results, [])

    def test_the_arrow_keys_answer_too(self):
        self.task.start_run()
        self.task.on_key_press(key.RIGHT, 0)
        self.assertEqual(len(self.task.results), 1)
        self.assertFalse(self.task.results[0][1])

    def test_c_opens_options_only_between_runs(self):
        from uisupport import Menu
        from neural_workshop.ui import taskoptions
        self.task.start_run()
        Menu.instance = None
        self.task.on_key_press(key.C, 0)
        self.assertIsNone(Menu.instance)     # mid-trial it must not butt in
        self.task.phase = 'ready'
        self.task.on_key_press(key.C, 0)
        self.assertIsInstance(Menu.instance, taskoptions.TaskOptions)
        Menu.instance.close()

    def test_a_resize_redraws_the_same_pair(self):
        self.task.start_run()
        before = (list(self.task.graphs), list(self.task.spots),
                  self.task.really_same)
        display.relayout(force=True)
        self.assertEqual(self.task.graphs, before[0])
        self.assertEqual(self.task.spots, before[1])
        self.assertEqual(self.task.really_same, before[2])
        self.task.on_draw()

    def test_escape_goes_back_to_its_own_category(self):
        self.task.on_key_press(key.ESCAPE, 0)
        self.assertIsNone(GraphMapping.instance)
        self.assertIsNotNone(TaskHub.instance)
        self.assertEqual(TaskHub.instance.category, 'reasoning')

    def test_it_registers_and_unregisters_as_an_overlay(self):
        self.assertIn(self.task, display.open_overlays())
        self.task.close()
        self.assertNotIn(self.task, display.open_overlays())


if __name__ == '__main__':
    unittest.main(verbosity=2)
