#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The planning tasks: the Tower of Hanoi and the Traveling Salesman.

Both score against a knowable optimum, so the first thing tested is
that the optimum really is one: the tower minimum against its closed
form, and the Held-Karp tours against brute force over every
permutation.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import random
import unittest

from uisupport import (TASKS, TowerOfHanoi, TravelingSalesman,
                       close_overlays, display, key, needs_ui,
                       reset_window, state, taskoptions)

from neural_workshop.ui import hanoi, salesman


class HanoiRuleTests(unittest.TestCase):
    """The puzzle's furniture: legality, the minimum, being solved."""

    def test_the_minimum_is_two_to_the_n_minus_one(self):
        for disks, moves in ((1, 1), (3, 7), (5, 31), (8, 255)):
            self.assertEqual(hanoi.minimum_moves(disks), moves)

    def test_a_fresh_tower_is_all_on_the_first_peg_in_order(self):
        pegs = hanoi.fresh_pegs(4)
        self.assertEqual(pegs, [[4, 3, 2, 1], [], []])
        self.assertFalse(hanoi.solved(pegs, 4))

    def test_a_disk_never_rests_on_a_smaller_one(self):
        pegs = [[3, 1], [2], []]
        self.assertFalse(hanoi.can_move(pegs, 1, 0))    # 2 onto 1
        self.assertTrue(hanoi.can_move(pegs, 0, 1))     # 1 onto 2
        self.assertTrue(hanoi.can_move(pegs, 1, 2))     # 2 onto empty
        self.assertFalse(hanoi.can_move(pegs, 2, 0))    # nothing to move
        self.assertFalse(hanoi.can_move(pegs, 0, 0))    # nowhere new

    def test_the_classic_recursion_solves_at_the_minimum(self):
        for disks in range(1, 7):
            pegs = hanoi.fresh_pegs(disks)
            moves = []

            def shift(count, source, target, spare):
                if not count:
                    return
                shift(count - 1, source, spare, target)
                moves.append((source, target))
                pegs[target].append(pegs[source].pop())
                shift(count - 1, spare, target, source)

            shift(disks, 0, 2, 1)
            self.assertTrue(hanoi.solved(pegs, disks))
            self.assertEqual(len(moves), hanoi.minimum_moves(disks))

    def test_rebuilding_on_the_first_peg_does_not_count(self):
        self.assertFalse(hanoi.solved([[3, 2, 1], [], []], 3))
        self.assertTrue(hanoi.solved([[], [3, 2, 1], []], 3))
        self.assertTrue(hanoi.solved([[], [], [3, 2, 1]], 3))


class SalesmanTourTests(unittest.TestCase):
    """The optimum had better be the optimum."""

    def setUp(self):
        self.rng = random.Random(20260820)

    def test_held_karp_matches_brute_force(self):
        for count in (4, 5, 6, 7, 8):
            for _trial in range(6):
                cities = salesman.scatter(count, self.rng)
                _order, length = salesman.optimal_tour(cities)
                brute = min(
                    salesman.tour_length(cities, [0] + list(rest))
                    for rest in itertools.permutations(range(1, count)))
                self.assertAlmostEqual(length, brute, places=9)

    def test_the_reported_order_has_the_reported_length(self):
        for count in (5, 9, 12):
            cities = salesman.scatter(count, self.rng)
            order, length = salesman.optimal_tour(cities)
            self.assertEqual(sorted(order), list(range(count)))
            self.assertAlmostEqual(salesman.tour_length(cities, order),
                                   length, places=9)

    def test_no_tour_beats_it_by_local_improvement(self):
        """Reverse every segment of the optimal tour — the classic
        2-opt move — and nothing gets shorter."""
        cities = salesman.scatter(10, self.rng)
        order, length = salesman.optimal_tour(cities)
        for one in range(10):
            for two in range(one + 2, 10):
                tried = order[:one] + order[one:two][::-1] + order[two:]
                self.assertGreaterEqual(
                    salesman.tour_length(cities, tried) + 1e-9, length)

    def test_scattered_cities_keep_their_distance(self):
        for count in (5, 12):
            cities = salesman.scatter(count, self.rng)
            self.assertEqual(len(cities), count)
            for (ax, ay), (bx, by) in itertools.combinations(cities, 2):
                self.assertGreater(((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5,
                                   0.05)


@needs_ui
class HanoiScreenTests(unittest.TestCase):

    def setUp(self):
        close_overlays()
        self.task = TowerOfHanoi()
        self.task.total_rounds = 2
        self.task.adaptive = False

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _solve(self):
        def shift(count, source, target, spare):
            if not count:
                return
            shift(count - 1, source, spare, target)
            self.task._pick(source)
            self.task._pick(target)
            shift(count - 1, spare, target, source)
        shift(self.task.trial_disks, 0, 2, 1)

    def test_starting_builds_a_fresh_tower(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'solving')
        self.assertEqual(self.task.pegs,
                         hanoi.fresh_pegs(self.task.trial_disks))
        self.assertEqual(self.task.par,
                         hanoi.minimum_moves(self.task.trial_disks))
        self.task.on_draw()

    def test_an_illegal_move_is_refused_and_not_counted(self):
        self.task.start_run()
        self.task._pick(0)
        self.task._pick(2)          # smallest to an empty peg: fine
        self.task._pick(0)
        self.task._pick(2)          # second-smallest onto smallest: no
        self.assertEqual(self.task.moves, 1)
        self.assertEqual(len(self.task.pegs[2]), 1)
        self.assertIsNone(self.task.picked)

    def test_picking_the_same_peg_puts_the_disk_back(self):
        self.task.start_run()
        self.task._pick(0)
        self.assertEqual(self.task.picked, 0)
        self.task._pick(0)
        self.assertIsNone(self.task.picked)
        self.assertEqual(self.task.moves, 0)

    def test_the_keys_move_disks_too(self):
        self.task.start_run()
        self.task.on_key_press(key._1, 0)
        self.task.on_key_press(key._3, 0)
        self.assertEqual(self.task.moves, 1)

    def test_solving_at_the_minimum_is_a_perfect_score(self):
        self.task.start_run()
        self._solve()
        self.assertEqual(self.task.phase, 'solved')
        _disks, efficiency, _took = self.task.results[-1]
        self.assertEqual(efficiency, 1.0)

    def test_an_efficient_solve_grows_the_tower(self):
        self.task.adaptive = True
        self.task.start_disks = 3
        self.task.start_run()
        self._solve()
        self.assertEqual(self.task.disks, 4)

    def test_a_wasteful_solve_shrinks_it(self):
        self.task.adaptive = True
        self.task.start_disks = 4
        self.task.start_run()
        for _waste in range(2 * self.task.par):
            self.task._pick(0)
            self.task._pick(2 if self.task.picked is not None else 0)
            self.task._pick(2)
            self.task._pick(0)
        self.task.moves = self.task.par * 3
        self._solve()
        self.assertEqual(self.task.disks, 3)

    def test_a_run_ends_with_a_score(self):
        self.task.start_run()
        for _round in range(2):
            self._solve()
            self.task.feedback_until = 0
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['rounds'], 2)
        self.assertIn('move efficiency', self.task.message)

    def test_closing_gives_back_its_handlers(self):
        self.task.start_run()
        self.task.close()
        self.assertIsNone(TowerOfHanoi.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class SalesmanScreenTests(unittest.TestCase):

    def setUp(self):
        close_overlays()
        self.task = TravelingSalesman()
        self.task.total_rounds = 2
        self.task.adaptive = False

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def test_starting_scatters_cities_and_solves_them_exactly(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'touring')
        self.assertEqual(len(self.task.cities), self.task.trial_cities)
        self.assertAlmostEqual(
            salesman.tour_length(self.task.cities, self.task.best_order),
            self.task.best_length, places=9)
        self.task.on_draw()

    def test_clicking_cities_builds_the_route_and_undo_retracts(self):
        self.task.start_run()
        self.task._pick(0)
        self.task._pick(3)
        self.assertEqual(self.task.route, [0, 3])
        self.task._pick(3)
        self.assertEqual(self.task.route, [0])
        self.task._pick(0)
        self.assertEqual(self.task.route, [])

    def test_a_city_cannot_be_visited_twice(self):
        self.task.start_run()
        self.task._pick(1)
        self.task._pick(2)
        self.task._pick(1)
        self.assertEqual(self.task.route, [1, 2])

    def test_touring_the_optimum_scores_perfectly(self):
        self.task.start_run()
        for city in self.task.best_order:
            self.task._pick(city)
        self.assertEqual(self.task.phase, 'toured')
        _cities, closeness, _took = self.task.results[-1]
        self.assertEqual(closeness, 1.0)
        self.assertIn('shortest route there is', self.task.message)

    def test_a_worse_tour_is_told_how_much_worse(self):
        self.task.start_run()
        order = list(self.task.best_order)
        worse = None
        for one in range(len(order)):
            for two in range(one + 2, len(order)):
                tried = order[:one] + order[one:two][::-1] + order[two:]
                length = salesman.tour_length(self.task.cities, tried)
                if length > self.task.best_length * 1.02:
                    worse = tried
                    break
            if worse:
                break
        self.assertIsNotNone(worse, 'every 2-opt neighbour ties the '
                                    'optimum; astonishing scatter')
        for city in worse:
            self.task._pick(city)
        _cities, closeness, _took = self.task.results[-1]
        self.assertLess(closeness, 1.0)
        self.assertIn('longer than the shortest', self.task.message)

    def test_a_near_optimal_tour_grows_the_map(self):
        self.task.adaptive = True
        self.task.start_cities = 6
        self.task.start_run()
        for city in self.task.best_order:
            self.task._pick(city)
        self.assertEqual(self.task.city_count, 7)

    def test_a_run_ends_with_a_score(self):
        self.task.start_run()
        for _round in range(2):
            for city in self.task.best_order:
                self.task._pick(city)
            self.task.feedback_until = 0
            self.task.update(0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['rounds'], 2)
        self.assertEqual(self.task.score()['closeness'], 100)

    def test_closing_gives_back_its_handlers(self):
        self.task.start_run()
        self.task.close()
        self.assertIsNone(TravelingSalesman.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class PlanningHubTests(unittest.TestCase):
    """The category exists, and both tasks are reachable and named."""

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_planning_is_a_category_with_both_tasks(self):
        listed = [task_id for task_id, _label in TASKS['planning']]
        self.assertIn('tower_of_hanoi', listed)
        self.assertIn('salesman', listed)

    def test_the_hub_can_launch_both(self):
        from neural_workshop.ui.taskhub import launch_task
        launch_task('tower_of_hanoi')
        self.assertIsNotNone(TowerOfHanoi.instance)
        TowerOfHanoi.instance.close()
        launch_task('salesman')
        self.assertIsNotNone(TravelingSalesman.instance)
        TravelingSalesman.instance.close()

    def test_the_notes_say_what_the_numbers_mean(self):
        note = taskoptions.hanoi_note({'HANOI_DISKS': 8,
                                       'HANOI_ADAPTIVE': False})
        self.assertIn('255', note)
        note = taskoptions.salesman_note({'TSP_CITIES': 9,
                                          'TSP_ADAPTIVE': True})
        self.assertIn('9 cities', note)
        self.assertIn('exactly', note)


if __name__ == '__main__':
    unittest.main()
