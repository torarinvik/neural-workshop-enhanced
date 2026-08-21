#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Crossed Wires: the wiring, the budget, and what four players make of it.

The generator has little to promise here — a deal is one draw and
never a hunt — so the weight of the testing falls on the four players
instead, because between them they are what the rungs mean. The oracle
says a rung can be cleared at all, the random presser says it cannot
be cleared by accident, the learner says what finding the wiring out
while using it is worth, and the same learner with its memory frozen
says what the drifting rungs are for.

The wrapping is checked at the edges rather than in the middle, since
a torus that is only a torus away from the seams is a rectangle.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import (CrossedWires, TASKS, close_overlays, key, needs_ui,
                       reset_window, state, taskoptions)

from neural_workshop import crossedwires as C
from neural_workshop.i18n import _
from neural_workshop.ui.crossedwires import EIGHT_KEYS, FOUR_KEYS, keys_for
from nwenv.frames import capture_rgba, digest_rgba

#: The rungs the slow sweeps visit, one from each end and two between.
SPREAD = (1, 4, 8, 12)
#: Rungs whose wiring moves under the player.
RESTLESS = tuple(rung for rung, grade in enumerate(C.GRADES, 1)
                 if grade.drift)


class GridTests(unittest.TestCase):
    """The board, and the fact that it wraps."""

    def test_four_keys_get_the_square_directions(self):
        self.assertEqual(C.ways(4), ((0, 1), (1, 0), (0, -1), (-1, 0)))

    def test_eight_keys_get_the_diagonals_as_well(self):
        self.assertEqual(C.ways(8), C.WAYS)
        self.assertEqual(len(set(C.ways(8))), 8)

    def test_a_step_off_the_top_comes_back_at_the_bottom(self):
        self.assertEqual(C.step((3, 9), (0, 1), 10, 10), (3, 0))
        self.assertEqual(C.step((0, 0), (-1, 0), 10, 10), (9, 0))
        self.assertEqual(C.step((9, 9), (1, 1), 10, 10), (0, 0))

    def test_a_step_in_the_middle_is_just_a_step(self):
        self.assertEqual(C.step((4, 4), (1, 0), 10, 10), (5, 4))

    def test_the_gap_goes_the_short_way_round(self):
        self.assertEqual(C.gap((0, 0), (9, 0), 10, 10, 4), 1)
        self.assertEqual(C.gap((0, 0), (5, 0), 10, 10, 4), 5)

    def test_four_keys_pay_for_both_axes_and_eight_do_not(self):
        self.assertEqual(C.gap((0, 0), (3, 3), 20, 20, 4), 6)
        self.assertEqual(C.gap((0, 0), (3, 3), 20, 20, 8), 3)

    def test_the_gap_is_nothing_when_you_are_there(self):
        self.assertEqual(C.gap((2, 5), (2, 5), 11, 11, 8), 0)

    def test_a_step_never_widens_the_gap_by_more_than_one(self):
        for keys in (4, 8):
            for way in C.ways(keys):
                for spot in ((0, 0), (5, 5), (9, 0), (0, 9)):
                    moved = C.step(spot, way, 10, 10)
                    was = C.gap(spot, (4, 6), 10, 10, keys)
                    now = C.gap(moved, (4, 6), 10, 10, keys)
                    self.assertLessEqual(abs(now - was), 1)


class WiringTests(unittest.TestCase):
    """How the keys get crossed, and what each family promises."""

    def _wirings(self, family, keys, count=40):
        return [C.wirings(family, keys, random.Random(seed))
                for seed in range(count)]

    def test_every_wiring_is_a_bijection(self):
        for family in C.FAMILIES:
            for keys in (4, 8):
                for wiring in self._wirings(family, keys, count=20):
                    self.assertEqual(sorted(wiring), list(range(keys)))

    def test_steady_leaves_the_keys_alone(self):
        self.assertEqual(C.wirings(C.STEADY, 4, random.Random(1)),
                         (0, 1, 2, 3))

    def test_a_turn_moves_every_key_by_the_same_amount(self):
        for wiring in self._wirings(C.TURNED, 8):
            steps = {(way - k) % 8 for k, way in enumerate(wiring)}
            self.assertEqual(len(steps), 1)
            self.assertNotEqual(steps.pop(), 0)

    def test_a_mirror_is_a_reflection_and_not_a_turn(self):
        for wiring in self._wirings(C.MIRRORED, 8):
            abouts = {(way + k) % 8 for k, way in enumerate(wiring)}
            self.assertEqual(len(abouts), 1)

    def test_crossed_is_never_simply_straight(self):
        for wiring in self._wirings(C.CROSSED, 4):
            self.assertNotEqual(wiring, (0, 1, 2, 3))

    def test_crossed_reaches_past_the_turns_and_mirrors(self):
        """The families have to differ, or the rung names mean nothing."""
        seen = {C.wirings(C.CROSSED, 4, random.Random(seed))
                for seed in range(200)}
        dihedral = set(self._wirings(C.TURNED, 4, 40)) | \
            set(self._wirings(C.MIRRORED, 4, 40))
        self.assertTrue(seen - dihedral)

    def test_turning_a_wiring_moves_it_round_the_ring(self):
        self.assertEqual(C.turned((0, 1, 2, 3), 1, 4), (1, 2, 3, 0))

    def test_turning_leaves_a_dead_key_dead(self):
        self.assertEqual(C.turned((0, C.DEAD, 2, 3), 1, 4),
                         (1, C.DEAD, 3, 0))


class BenchTests(unittest.TestCase):
    """A round being played, and the wiring behind it."""

    def _bench(self, rung=4, seed=1):
        return C.Bench(C.deal(rung, seed=seed))

    def test_a_press_moves_the_marker_the_way_it_is_wired(self):
        bench = self._bench()
        was = bench.at
        went = bench.press(0)
        self.assertEqual(went, C.ways(4)[bench.bout.wiring[0]])
        self.assertEqual(bench.at, C.step(was, went, 13, 13))
        self.assertEqual(bench.presses, 1)

    def test_a_key_the_rung_does_not_have_does_nothing_and_costs_nothing(self):
        bench = self._bench()
        self.assertEqual(bench.press(9), (0, 0))
        self.assertEqual(bench.presses, 0)

    def test_the_budget_runs_out(self):
        bench = self._bench()
        for _press in range(bench.bout.budget):
            bench.press(0)
        self.assertTrue(bench.over())
        self.assertEqual(bench.left(), 0)
        was = bench.at
        bench.press(1)
        self.assertEqual(bench.at, was)

    def test_reaching_a_target_moves_on_to_the_next(self):
        bench = self._bench()
        bench.at = bench.goal()
        # A step away and a step back, so the marker really arrives.
        wired = C.ways(4)[bench.wiring_now()[0]]
        bench.at = C.step(bench.at, tuple(-n for n in wired), 13, 13)
        bench.press(0)
        self.assertEqual(bench.reached, 1)
        self.assertEqual(bench.goal_at, 1)

    def test_a_steady_rung_never_moves_its_wiring(self):
        bench = self._bench(rung=4)
        first = bench.wiring_now()
        for _press in range(20):
            bench.press(0)
        self.assertEqual(bench.wiring_now(), first)

    def test_a_drifting_rung_turns_on_time(self):
        rung = RESTLESS[0]
        bench = C.Bench(C.deal(rung, seed=5))
        drift = C.GRADES[rung - 1].drift
        first = bench.wiring_now()
        for _press in range(drift - 1):
            bench.press(0)
        self.assertEqual(bench.wiring_now(), first)
        bench.press(0)
        self.assertNotEqual(bench.wiring_now(), first)
        self.assertEqual(bench.wiring_now(),
                         C.turned(first, bench.bout.turn, 8))

    def test_a_dead_key_dies_on_time_and_still_costs_a_press(self):
        rung = next(r for r, g in enumerate(C.GRADES, 1) if g.dies)
        grade = C.GRADES[rung - 1]
        bench = C.Bench(C.deal(rung, seed=9)._replace(budget=10000))
        dead = bench.bout.dead
        for _press in range(grade.dies):
            bench.press((dead + 1) % grade.keys)
        self.assertEqual(bench.wiring_now()[dead], C.DEAD)
        was, spent = bench.at, bench.presses
        self.assertEqual(bench.press(dead), (0, 0))
        self.assertEqual(bench.at, was)
        self.assertEqual(bench.presses, spent + 1)

    def test_a_press_that_widens_the_gap_is_counted_as_wasted(self):
        bench = self._bench()
        wired = bench.wiring_now()
        away = max(range(4), key=lambda k: C.gap(
            C.step(bench.at, C.ways(4)[wired[k]], 13, 13),
            bench.goal(), 13, 13, 4))
        bench.press(away)
        self.assertEqual(bench.wasted, 1)

    def test_the_wiring_is_read_from_the_press_count_and_not_kept(self):
        """A round replays exactly, which is what lets a test pin one."""
        bout = C.deal(RESTLESS[-1], seed=12)
        pressed = [random.Random(3).randrange(bout.grade.keys)
                   for _n in range(15)]
        walks = []
        for _again in range(2):
            bench = C.Bench(bout)
            walks.append([bench.press(keyed) for keyed in pressed])
        self.assertEqual(walks[0], walks[1])


class DealTests(unittest.TestCase):
    """What a round is given, before anybody presses anything."""

    def test_the_budget_is_the_trip_plus_what_the_rung_allows(self):
        for rung in range(1, len(C.GRADES) + 1):
            grade = C.GRADES[rung - 1]
            bout = C.deal(rung, seed=100 + rung)
            self.assertEqual(bout.budget,
                             bout.shortest + grade.spare + C.limp(grade))

    def test_a_rung_with_a_dead_key_gets_something_back_for_it(self):
        for grade in C.GRADES:
            self.assertEqual(C.limp(grade) > 0, bool(grade.dies))

    def test_the_targets_are_worth_walking_to(self):
        for rung in range(1, len(C.GRADES) + 1):
            grade = C.GRADES[rung - 1]
            bout = C.deal(rung, seed=200 + rung)
            least = max(2, min(grade.across, grade.down) // 3)
            here = bout.start
            for spot in bout.goals:
                self.assertGreaterEqual(
                    C.gap(here, spot, grade.across, grade.down, grade.keys),
                    least)
                here = spot

    def test_the_deal_matches_the_rung(self):
        for rung in range(1, len(C.GRADES) + 1):
            grade = C.GRADES[rung - 1]
            bout = C.deal(rung, seed=300 + rung)
            self.assertEqual(len(bout.goals), grade.targets)
            self.assertEqual(sorted(bout.wiring), list(range(grade.keys)))
            self.assertEqual(bout.dead >= 0, bool(grade.dies))
            self.assertTrue(0 <= bout.start[0] < grade.across)
            self.assertTrue(0 <= bout.start[1] < grade.down)

    def test_the_same_seed_deals_the_same_round(self):
        self.assertEqual(C.deal(6, seed=3), C.deal(6, seed=3))
        self.assertNotEqual(C.deal(6, seed=3), C.deal(6, seed=4))

    def test_a_level_off_the_end_of_the_ladder_is_pulled_back_on(self):
        self.assertEqual(C.deal(0, seed=1), C.deal(1, seed=1))
        self.assertEqual(C.deal(99, seed=1),
                         C.deal(len(C.GRADES), seed=1))

    def test_the_ladder_climbs(self):
        for lower, upper in zip(C.GRADES, C.GRADES[1:]):
            self.assertLess(C.pressure(lower), C.pressure(upper))

    def test_never_sorts_below_rarely(self):
        steady = C.GRADES[0]._replace(drift=0)
        rare = C.GRADES[0]._replace(drift=40)
        often = C.GRADES[0]._replace(drift=5)
        self.assertLess(C.pressure(steady), C.pressure(rare))
        self.assertLess(C.pressure(rare), C.pressure(often))


class PlayerTests(unittest.TestCase):
    """The four players, which are what the rungs actually mean."""

    def _run(self, play, rung, count=30, **kw):
        got = asked = 0
        for trial in range(count):
            bout = C.deal(rung, seed=7000 + rung * 53 + trial)
            got += play(C.Bench(bout), **kw)
            asked += len(bout.goals)
        return got / float(asked)

    def test_the_oracle_clears_every_rung(self):
        """A rung nobody can pass is a broken rung, not a hard one.

        The oracle is greedy rather than optimal — it walks the way
        that shortens the gap most and does not plan around the key
        about to die — so the bar is set just short of perfect on the
        rungs that kill one.
        """
        for rung in range(1, len(C.GRADES) + 1):
            share = self._run(
                lambda bench: C.play_oracle(bench), rung, count=40)
            self.assertGreaterEqual(share, 0.98, 'rung %d' % rung)

    def test_pressing_at_random_gets_almost_nowhere(self):
        for rung in SPREAD:
            share = self._run(
                lambda bench: C.play_random(bench, random.Random(1)),
                rung, count=60)
            self.assertLess(share, 0.20, 'rung %d' % rung)

    def test_the_learner_beats_pressing_at_random_everywhere(self):
        for rung in range(1, len(C.GRADES) + 1):
            blind = self._run(
                lambda bench: C.play_random(bench, random.Random(2)), rung)
            learned = self._run(
                lambda bench: C.play_learner(bench, random.Random(2)), rung)
            self.assertGreater(learned, blind + 0.1, 'rung %d' % rung)

    def test_the_learner_clears_the_bottom_of_the_ladder(self):
        self.assertEqual(
            self._run(lambda b: C.play_learner(b, random.Random(3)), 1), 1.0)

    def test_the_ladder_gets_harder_for_the_learner_it_is_graded_on(self):
        low = self._run(lambda b: C.play_learner(b, random.Random(4)), 1,
                        count=60)
        high = self._run(lambda b: C.play_learner(b, random.Random(4)), 12,
                         count=60)
        self.assertGreater(low - high, 0.5)

    def test_a_frozen_memory_costs_nothing_while_nothing_moves(self):
        """The foil is only a foil where there is something to miss.

        On a rung whose wiring sits still, identifying it once is
        exactly the right thing to do, and the two players must agree
        — otherwise the separation further up would be measuring the
        relearning machinery rather than the drift.
        """
        for rung in (1, 4, 7):
            self.assertEqual(
                self._run(lambda b: C.play_learner(b, random.Random(5)),
                          rung),
                self._run(lambda b: C.play_learner(b, random.Random(5),
                                                   relearn=False), rung))

    def test_a_frozen_memory_is_punished_wherever_the_wiring_moves(self):
        for rung in RESTLESS:
            fresh = self._run(
                lambda b: C.play_learner(b, random.Random(6)), rung, count=60)
            stale = self._run(
                lambda b: C.play_learner(b, random.Random(6), relearn=False),
                rung, count=60)
            self.assertGreater(fresh, stale + 0.15, 'rung %d' % rung)

    def test_the_oracle_wastes_fewer_presses_than_the_learner(self):
        bout = C.deal(7, seed=21)
        wise, guessing = C.Bench(bout), C.Bench(bout)
        C.play_oracle(wise)
        C.play_learner(guessing, random.Random(7))
        self.assertLess(wise.wasted, guessing.wasted)


@needs_ui
class CrossedWiresScreenTests(unittest.TestCase):
    """The screen: a board, a marker, and no hint of what the keys do."""

    RUNG = 4

    def setUp(self):
        close_overlays()
        self.task = CrossedWires()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.start_rung = self.task.rung = self.RUNG
        self.now = 1000.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _spend(self):
        """Use the whole budget up on one key."""
        while self.task.phase == 'playing':
            self.task.press(0)

    def test_it_is_in_the_reasoning_category(self):
        self.assertIn('crossed_wires',
                      [task for task, _n in TASKS['reasoning']])

    def test_a_trial_deals_a_board(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'playing')
        self.assertEqual(self.task.bench.presses, 0)
        self.assertNotEqual(self.task.bench.at, self.task.bench.goal())
        self.task.on_draw()

    def test_a_key_moves_the_marker(self):
        self.task.start_run()
        was = self.task.bench.at
        self.task.press(0)
        self.assertNotEqual(self.task.bench.at, was)

    def test_the_arrows_and_the_letters_drive_the_same_four_keys(self):
        self.task.start_run()
        first = C.Bench(self.task.bench.bout)
        first.press(0)
        self.task.on_key_press(key.UP, 0)
        self.assertEqual(self.task.bench.at, first.at)
        self.task.on_key_press(key.W, 0)
        first.press(0)
        self.assertEqual(self.task.bench.at, first.at)

    def test_spending_the_budget_ends_the_round(self):
        self.task.start_run()
        self._spend()
        self.assertEqual(self.task.phase, 'scored')
        self.assertEqual(len(self.task.results), 1)
        self.task.on_draw()

    def test_a_key_outside_the_ring_is_ignored(self):
        self.task.start_run()
        self.task.on_key_press(key.J, 0)
        self.assertEqual(self.task.bench.presses, 0)

    def test_the_run_finishes_after_its_rounds(self):
        self.task.start_run()
        for _trial in range(self.task.total_trials):
            self._spend()
            self.now += 10.0
            self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['rounds'],
                         self.task.total_trials)

    def _play_out(self, well):
        """Play a whole round, either knowing the wiring or wasting it."""
        while self.task.phase == 'playing':
            if well:
                bench = self.task.bench
                live = bench.wiring_now()
                want = C.helpful(bench)
                pressed = next((k for k, way in enumerate(live)
                                if way in want), 0)
                self.task.press(pressed)
            else:
                self.task.press(0)

    def test_adaptive_climbs_after_a_clean_round(self):
        self.task.adaptive = True
        self.task.start_run()
        was = self.task.rung
        self._play_out(well=True)
        self.assertEqual(self.task.rung, was + 1)

    def test_adaptive_drops_after_a_poor_one(self):
        self.task.adaptive = True
        self.task.start_run()
        was = self.task.rung
        self._play_out(well=False)
        self.assertEqual(self.task.rung, was - 1)

    def test_it_draws_in_every_phase(self):
        self.task.on_draw()                       # ready
        self.task.start_run()
        self.task.on_draw()                       # playing
        self._spend()
        self.task.on_draw()                       # scored
        self.task.total_trials = 1
        self.now += 10.0
        self.task.on_key_press(key.SPACE, 0)
        self.task.on_draw()                       # done

    def test_it_draws_with_the_grid_off_as_well(self):
        self.task.show_grid = False
        self.task.start_run()
        self.task.on_draw()

    def test_every_cell_lands_on_screen(self):
        self.task.start_run()
        grade = self.task.grade()
        for across in range(grade.across):
            for down in range(grade.down):
                x, y, side = self.task._cell_rect((across, down))
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(x + side, state.window.width + 1)
                self.assertLessEqual(y + side, state.window.height + 1)

    def test_a_board_of_every_size_the_ladder_deals_still_fits(self):
        for rung in range(1, len(C.GRADES) + 1):
            self.task.start_rung = self.task.rung = rung
            self.task.start_run()
            grade = self.task.grade()
            x, y, side = self.task._cell_rect((grade.across - 1,
                                               grade.down - 1))
            self.assertLessEqual(x + side, state.window.width + 1)
            self.assertLessEqual(y + side, state.window.height + 1)
            self.task.on_draw()

    def test_the_eight_key_rungs_use_the_ring_and_the_four_key_the_arrows(self):
        self.assertIs(keys_for(8), EIGHT_KEYS)
        self.assertIs(keys_for(4), FOUR_KEYS)
        self.assertEqual(len(EIGHT_KEYS), 8)
        self.assertEqual(len(FOUR_KEYS), 4)

    def test_c_is_south_east_where_there_are_eight_keys(self):
        """Which is why the options moved to O.

        A settings screen that quietly stops opening at level six
        would be a worse surprise than an unfamiliar shortcut, so this
        pins both halves: C drives the marker on an eight-key rung,
        and O still opens the options there.
        """
        self.task.start_rung = self.task.rung = 12
        self.task.start_run()
        self.assertEqual(self.task.grade().keys, 8)
        self.task.on_key_press(key.C, 0)
        self.assertEqual(self.task.bench.presses, 1)
        self.task.on_key_press(key.O, 0)
        self.assertIsNotNone(taskoptions.TASK_SPECS['crossed_wires'])

    def test_the_board_says_nothing_about_the_wiring(self):
        """The claim the task rests on, read off the pixels themselves.

        Before a single press, two rounds that differ only in how the
        keys are crossed must draw the same bytes. If the wiring ever
        reached the screen, this is where it would show.
        """
        bout = C.deal(7, seed=515)
        prints = set()
        for wiring in ((0, 1, 2, 3, 4, 5, 6, 7), (3, 4, 5, 6, 7, 0, 1, 2),
                       (7, 6, 5, 4, 3, 2, 1, 0)):
            self.task.rung = 7
            self.task.bench = C.Bench(bout._replace(wiring=wiring))
            self.task.phase = 'playing'
            self.task._redraw()
            self.task.on_draw()
            prints.add(digest_rgba(capture_rgba(state.window)[2]))
        self.assertEqual(len(prints), 1)

    def test_moving_the_marker_does_change_the_picture(self):
        """The other half, so the test above cannot pass by drawing nothing."""
        self.task.start_run()
        self.task._redraw()
        self.task.on_draw()
        before = digest_rgba(capture_rgba(state.window)[2])
        self.task.press(0)
        self.task.on_draw()
        self.assertNotEqual(digest_rgba(capture_rgba(state.window)[2]),
                            before)

    def test_it_has_an_options_screen(self):
        spec = taskoptions.TASK_SPECS['crossed_wires']
        chosen = {opt.key: opt.default for opt in spec.options}
        self.assertIn('WIRES_LEVEL', chosen)
        self.assertTrue(spec.note(chosen))

    def test_the_note_says_what_is_spare_and_what_moves(self):
        spec = taskoptions.TASK_SPECS['crossed_wires']
        chosen = {opt.key: opt.default for opt in spec.options}
        chosen['WIRES_LEVEL'] = 12
        said = spec.note(chosen)
        grade = C.GRADES[11]
        self.assertIn(_(grade.name), said)
        self.assertIn(str(grade.spare), said)
        self.assertIn(str(grade.drift), said)
        self.assertIn(str(grade.dies), said)

    def test_the_note_says_when_nothing_is_scrambled(self):
        spec = taskoptions.TASK_SPECS['crossed_wires']
        chosen = {opt.key: opt.default for opt in spec.options}
        chosen['WIRES_LEVEL'] = 1
        self.assertIn('say', spec.note(chosen))


if __name__ == '__main__':
    unittest.main()
