#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Removals: the chains, the yard, and what a short memory cannot do.

The generator's promises are what is tested hardest, because the whole
claim of the task rests on them: every question really is answerable,
every answer really is as many hops deep as the rung says, the
distance back to it really is at least the rung's floor, and a player
who remembers fewer moves than that really is holding nothing at all.
The last one is checked by playing that player.

Small walks are written out as scripts so the expected answer can be
worked out by hand, and the fast reading in :func:`resting` is held
against the slow enumeration in :func:`belief` on generated ones.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import (TASKS, Removals, close_overlays, key, needs_ui,
                       reset_window, state, taskoptions)

from neural_workshop import removals as R
from neural_workshop.i18n import _
from neural_workshop.ui.removals import ANSWER_KEYS, ITEM_COLORS
from nwenv.frames import capture_rgba, digest_rgba

#: A rung whose yard is small enough to enumerate every start of.
SMALL_RUNG = 3
#: The rungs the slow checks sweep, one from each end and two between.
SPREAD = (1, 4, 8, 12)
#: A yard used by the hand-written scripts: vans 0-1, box 2, things 3-4.
TOY = R.Yard(vans=2, boxes=1, items=2)


def script(*lines):
    """A walk written out: ``pack 3 2`` packs thing 3 into holder 2.

    Nodes are named by their number, which is how
    :class:`~neural_workshop.removals.Move` stores them: vans first,
    then boxes, then things. ``swap 3 4`` exchanges where two of them
    are sitting.
    """
    made = []
    for line in lines:
        word = line.split()
        made.append(R.Move(word[0], int(word[1]), int(word[2])))
    return tuple(made)


def flat(yard, *vans):
    """A starting map: every mover in the van named for it, in order."""
    parent = list(range(yard.size))
    for mover, van in zip(yard.movers(), vans):
        parent[mover] = van
    return parent


class YardTests(unittest.TestCase):
    """Who is a van, who is a box, and who is a thing."""

    def test_the_number_says_what_something_is(self):
        yard = R.Yard(3, 4, 5)
        self.assertTrue(yard.is_van(0))
        self.assertTrue(yard.is_van(2))
        self.assertTrue(yard.is_box(3))
        self.assertTrue(yard.is_box(6))
        self.assertTrue(yard.is_item(7))
        self.assertTrue(yard.is_item(11))
        self.assertEqual(yard.size, 12)

    def test_the_kinds_do_not_overlap_and_leave_nothing_out(self):
        yard = R.Yard(3, 4, 5)
        seen = list(yard.van_ids()) + list(yard.box_ids()) + \
            list(yard.item_ids())
        self.assertEqual(sorted(seen), list(range(yard.size)))

    def test_boxes_and_things_are_named_from_zero(self):
        yard = R.Yard(3, 4, 5)
        self.assertEqual(yard.box(0), 3)
        self.assertEqual(yard.item(0), 7)

    def test_only_vans_and_boxes_hold_and_only_they_do_not_move(self):
        yard = R.Yard(3, 4, 5)
        self.assertEqual(list(yard.holders()), list(range(0, 7)))
        self.assertEqual(list(yard.movers()), list(range(3, 12)))


class MoveTests(unittest.TestCase):
    """What one move does, including to what nobody knows."""

    def test_a_pack_writes_one_slot(self):
        parent = flat(TOY, 0, 0, 1)
        R.enter(R.Move(R.PACK, 3, 2), parent)
        self.assertEqual(parent[3], 2)
        self.assertEqual(parent[4], 1)

    def test_a_swap_exchanges_two_slots(self):
        parent = flat(TOY, 0, 0, 1)
        R.enter(R.Move(R.SWAP, 3, 4), parent)
        self.assertEqual((parent[3], parent[4]), (1, 0))

    def test_a_swap_carries_the_unknown_across(self):
        """The one place the unknown has to behave, and does.

        A slot nobody has written is not a special case to be guarded
        against — it is a value like any other, and a swap moves it
        the way it moves anything.
        """
        parent = R.resting(script('pack 4 2'), TOY)
        self.assertEqual(parent[3], R.UNKNOWN)
        R.enter(R.Move(R.SWAP, 3, 4), parent)
        self.assertEqual(parent[3], 2)
        self.assertEqual(parent[4], R.UNKNOWN)

    def test_a_pack_carries_what_is_inside_along_with_it(self):
        moves = script('pack 3 2', 'pack 2 1')
        parent = R.carry(moves, flat(TOY, 0, 0, 0))
        self.assertEqual(R.van_of(parent, 3, TOY), 1)

    def test_what_a_move_writes_to(self):
        self.assertEqual(R.touched(R.Move(R.PACK, 3, 2)), (3,))
        self.assertEqual(R.touched(R.Move(R.SWAP, 3, 4)), (3, 4))


class ChainTests(unittest.TestCase):
    """Walking up from a thing to the van it is in."""

    def test_a_chain_runs_up_to_a_van(self):
        parent = R.carry(script('pack 3 2', 'pack 2 1'), flat(TOY, 0, 0, 0))
        self.assertEqual(R.chain(parent, 3, TOY), (3, 2, 1))
        self.assertEqual(R.van_of(parent, 3, TOY), 1)

    def test_a_chain_stops_where_the_walk_stopped(self):
        parent = R.resting(script('pack 3 2'), TOY)
        self.assertEqual(R.chain(parent, 3, TOY), (3, 2))
        self.assertEqual(R.van_of(parent, 3, TOY), R.UNKNOWN)

    def test_a_van_is_its_own_chain(self):
        parent = R.resting((), TOY)
        self.assertEqual(R.chain(parent, 1, TOY), (1,))
        self.assertEqual(R.van_of(parent, 1, TOY), 1)

    def test_resting_knows_only_where_the_vans_are(self):
        parent = R.resting((), TOY)
        self.assertEqual(parent[0], 0)
        self.assertEqual(parent[1], 1)
        self.assertEqual(parent[2], R.UNKNOWN)

    def test_something_is_inside_itself_and_inside_what_holds_it(self):
        parent = R.carry(script('pack 3 2', 'pack 2 1'), flat(TOY, 0, 0, 0))
        self.assertTrue(R.inside(parent, 2, 2, TOY))
        self.assertTrue(R.inside(parent, 2, 3, TOY))
        self.assertFalse(R.inside(parent, 3, 2, TOY))
        self.assertFalse(R.inside(parent, 2, 4, TOY))


class SpanTests(unittest.TestCase):
    """How far back a memory has to reach, worked out by hand."""

    def test_the_last_move_is_enough_when_it_names_a_van(self):
        self.assertEqual(R.span(script('pack 3 0'), 3, TOY), 1)

    def test_a_chain_reaches_back_to_its_earliest_link(self):
        """Three moves, and only the first and last of them matter.

        The box goes into the van, something irrelevant happens, then
        the thing goes into the box. The answer needs both ends, so
        the memory has to span all three even though the middle move
        was nothing to do with it.
        """
        moves = script('pack 2 1', 'pack 4 0', 'pack 3 2')
        self.assertEqual(R.span(moves, 3, TOY), 3)
        self.assertEqual(R.span(moves, 4, TOY), 2)

    def test_a_chain_the_walk_never_finishes_is_not_pinned(self):
        self.assertEqual(R.span(script('pack 3 2'), 3, TOY), -1)

    def test_a_later_move_can_shorten_the_reach(self):
        moves = script('pack 2 1', 'pack 3 2', 'pack 3 0')
        self.assertEqual(R.span(moves, 3, TOY), 1)

    def test_a_swap_hands_the_question_to_the_other_one(self):
        moves = script('pack 4 1', 'swap 3 4')
        self.assertEqual(R.span(moves, 3, TOY), 2)
        self.assertEqual(R.span(moves, 4, TOY), -1)


class BeliefTests(unittest.TestCase):
    """The slow reading, held against the fast one."""

    def test_a_pinned_thing_can_only_be_in_one_van(self):
        moves = script('pack 2 1', 'pack 3 2')
        self.assertEqual(R.belief(moves, 3, TOY), frozenset([1]))

    def test_an_unpinned_thing_could_be_in_any_of_them(self):
        self.assertEqual(R.belief(script('pack 4 0'), 3, TOY),
                         frozenset(TOY.van_ids()))

    def test_the_two_readings_agree_on_generated_rounds(self):
        """Every slot, every round, over every possible start.

        A fast derivation nothing checks is a fast derivation nobody
        should trust, so this is the enumeration that would catch it:
        where :func:`resting` says a slot is settled the slow reading
        must find exactly one van, and where it says the slot is open
        the slow reading must find them all.
        """
        for trial in range(8):
            a_round = R.generate(SMALL_RUNG, seed=400 + trial)
            settled = R.resting(a_round.moves, a_round.yard)
            for node in a_round.yard.movers():
                fast = R.van_of(settled, node, a_round.yard)
                slow = R.belief(a_round.moves, node, a_round.yard)
                if fast == R.UNKNOWN:
                    self.assertEqual(slow,
                                     frozenset(a_round.yard.van_ids()))
                else:
                    self.assertEqual(slow, frozenset([fast]))


class WastedTests(unittest.TestCase):
    """Work that had to be done and then thrown away."""

    def test_a_move_nothing_undoes_is_not_wasted(self):
        self.assertEqual(R.wasted(script('pack 3 2', 'pack 4 1'), {3, 4}), 0)

    def test_a_move_written_over_is_wasted(self):
        self.assertEqual(R.wasted(script('pack 3 2', 'pack 3 1'), {3}), 1)

    def test_only_moves_on_things_that_matter_count(self):
        moves = script('pack 4 2', 'pack 4 1', 'pack 3 0')
        self.assertEqual(R.wasted(moves, {3}), 0)
        self.assertEqual(R.wasted(moves, {4}), 1)

    def test_a_swap_counts_for_either_of_its_two(self):
        moves = script('swap 3 4', 'pack 4 1')
        self.assertEqual(R.wasted(moves, {4}), 1)
        self.assertEqual(R.wasted(moves, {3}), 0)


class RememberingTests(unittest.TestCase):
    """The foil: a player who only recalls the last few moves."""

    def test_the_whole_history_answers_every_question(self):
        for rung in SPREAD:
            a_round = R.generate(rung, seed=90 + rung)
            sure, asked = R.remembering(a_round, len(a_round.moves))
            self.assertEqual(sure, asked)

    def test_one_move_short_of_the_span_is_worth_nothing(self):
        """The claim the whole task rests on, played out.

        Not "does badly" and not "does nearly as badly as guessing" —
        certain of *none* of the questions, which is the only reading
        under which the score below the floor is exactly one in the
        number of vans.
        """
        for rung in range(1, len(R.GRADES) + 1):
            grade = R.GRADES[rung - 1]
            for trial in range(6):
                a_round = R.generate(rung, seed=6100 + rung * 17 + trial)
                sure, _asked = R.remembering(a_round, grade.floor - 1)
                self.assertEqual(sure, 0, 'rung %d leaked' % rung)

    def test_remembering_more_can_only_help(self):
        a_round = R.generate(8, seed=77)
        scores = [R.remembering(a_round, window)[0]
                  for window in range(len(a_round.moves) + 1)]
        self.assertEqual(scores, sorted(scores))
        self.assertEqual(scores[0], 0)


class LadderTests(unittest.TestCase):
    """What each rung promises, measured off what it deals."""

    def _deals(self, rung, count=12):
        return [R.generate(rung, seed=2200 + rung * 31 + trial)
                for trial in range(count)]

    def test_every_rung_holds_all_three_of_its_floors(self):
        for rung in range(1, len(R.GRADES) + 1):
            grade = R.GRADES[rung - 1]
            for a_round in self._deals(rung):
                self.assertGreaterEqual(a_round.needed, grade.floor)
                self.assertGreaterEqual(a_round.nest, grade.nest)

    def test_the_yard_is_the_one_the_rung_asked_for(self):
        for rung in range(1, len(R.GRADES) + 1):
            grade = R.GRADES[rung - 1]
            a_round = R.generate(rung, seed=31 + rung)
            self.assertEqual(a_round.yard,
                             R.Yard(grade.vans, grade.boxes, grade.items))
            self.assertEqual(len(a_round.moves), grade.depth)
            self.assertEqual(len(a_round.asked), grade.asks)

    def test_every_question_is_answerable_and_answered_truly(self):
        for rung in range(1, len(R.GRADES) + 1):
            for a_round in self._deals(rung, count=6):
                finish = R.carry(a_round.moves, a_round.start)
                for spot, item in enumerate(a_round.asked):
                    self.assertGreaterEqual(
                        R.span(a_round.moves, item, a_round.yard), 1)
                    self.assertEqual(
                        R.van_of(finish, item, a_round.yard),
                        a_round.answers[spot])

    def test_every_answer_really_is_that_many_hops_deep(self):
        """The axis the task exists for, read off the finished walk.

        A chain buried twenty moves back but only one hop long is a
        long wait, not a hard question, so this checks the hops rather
        than the distance — and checks that the hops end at a van.
        """
        for rung in range(1, len(R.GRADES) + 1):
            grade = R.GRADES[rung - 1]
            for a_round in self._deals(rung, count=6):
                settled = R.resting(a_round.moves, a_round.yard)
                for item in a_round.asked:
                    walked = R.chain(settled, item, a_round.yard)
                    self.assertGreaterEqual(len(walked) - 1, grade.nest)
                    self.assertTrue(a_round.yard.is_van(walked[-1]))

    def test_nothing_is_ever_packed_inside_itself(self):
        for rung in SPREAD:
            for a_round in self._deals(rung, count=10):
                parent = list(a_round.start)
                for move in a_round.moves:
                    R.enter(move, parent)
                    for node in a_round.yard.movers():
                        self.assertTrue(
                            a_round.yard.is_van(
                                R.chain(parent, node, a_round.yard)[-1]),
                            'a loop was made')

    def test_the_ladder_climbs(self):
        for lower, upper in zip(R.GRADES, R.GRADES[1:]):
            self.assertGreaterEqual(
                (upper.vans, upper.depth, upper.nest, upper.floor),
                (lower.vans, lower.depth, lower.nest, lower.floor))

    def test_the_ladder_stays_inside_what_the_screen_can_show(self):
        for grade in R.GRADES:
            self.assertLessEqual(grade.vans, R.MOST_VANS)
            self.assertLessEqual(grade.boxes, R.MOST_BOXES)
            self.assertLessEqual(grade.items, R.MOST_ITEMS)
            self.assertLessEqual(grade.asks, grade.items)
            self.assertLessEqual(grade.nest - 1, grade.boxes)

    def test_the_top_rung_asks_more_of_a_memory_than_the_bottom(self):
        low = R.generate(1, seed=5)
        high = R.generate(12, seed=5)
        self.assertGreater(high.needed, low.needed)
        self.assertGreater(high.nest, low.nest)

    def test_the_same_seed_deals_the_same_round(self):
        self.assertEqual(R.generate(6, seed=3), R.generate(6, seed=3))
        self.assertNotEqual(R.generate(6, seed=3), R.generate(6, seed=4))

    def test_a_level_off_the_end_of_the_ladder_is_pulled_back_on(self):
        self.assertEqual(R.generate(0, seed=1), R.generate(1, seed=1))
        self.assertEqual(R.generate(99, seed=1),
                         R.generate(len(R.GRADES), seed=1))

    def test_a_deal_that_cannot_be_laid_says_so(self):
        """The one failure that must not pass silently.

        A rung asking for more nesting than it has boxes for cannot be
        dealt at all, and handing back a shallow round instead would
        quietly break the promise the whole ladder rests on.
        """
        impossible = R.Grade('impossible', 2, 1, 2, 6, 1, 5, 4, 0)
        saved = R.GRADES
        try:
            R.GRADES = (impossible,)
            self.assertRaises(RuntimeError, R.generate, 1, seed=1)
        finally:
            R.GRADES = saved

    def test_a_van_is_not_easier_to_guess_than_its_neighbours(self):
        """No fixed guess beats chance, which is the other half of the floor.

        The proof says a short memory settles nothing; it does not say
        what such a player should guess instead. If the vans an answer
        lands in were lopsided, always naming the popular one would
        beat the floor without watching anything at all.
        """
        rng = random.Random(4)
        for rung in SPREAD:
            grade = R.GRADES[rung - 1]
            seen = [0] * grade.vans
            rounds = 400
            for trial in range(rounds):
                a_round = R.generate(rung, seed=41000 + rung * 977 + trial)
                seen[rng.choice(a_round.answers)] += 1
            even = 1.0 / grade.vans
            band = 4 * (even * (1 - even) / rounds) ** 0.5
            for count in seen:
                self.assertLess(abs(count / float(rounds) - even), band,
                                'rung %d leans on one van' % rung)


@needs_ui
class RemovalsScreenTests(unittest.TestCase):
    """The screen: the moves going by, and the yard never once drawn."""

    RUNG = 4

    def setUp(self):
        close_overlays()
        self.task = Removals()
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.move_seconds = 1.0
        self.task.start_rung = self.task.rung = self.RUNG
        self.now = 1000.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _walk_through(self):
        """Sit through every move until the questions start."""
        while self.task.phase == 'moving':
            self.now += self.task.move_seconds + 0.01
            self.task.update(0.0)

    def _answer_all(self, right=True):
        for spot in range(len(self.task.round.asked)):
            truth = self.task.round.answers[spot]
            wrong = (truth + 1) % self.task.round.yard.vans
            self.task.answer(truth if right else wrong)

    def test_it_is_in_the_working_memory_category(self):
        self.assertIn('removals',
                      [task for task, _n in TASKS['working_memory']])

    def test_a_trial_deals_a_round_and_shows_its_first_move(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'moving')
        self.assertEqual(self.task.cursor, 0)
        self.assertEqual(self.task.move_now(), self.task.round.moves[0])
        self.task.on_draw()

    def test_the_moves_go_by_one_at_a_time(self):
        self.task.start_run()
        self.now += self.task.move_seconds + 0.01
        self.task.update(0.0)
        self.assertEqual(self.task.cursor, 1)

    def test_a_move_does_not_advance_before_its_time(self):
        self.task.start_run()
        self.now += self.task.move_seconds * 0.5
        self.task.update(0.0)
        self.assertEqual(self.task.cursor, 0)

    def test_the_questions_come_after_the_last_move(self):
        self.task.start_run()
        self._walk_through()
        self.assertEqual(self.task.phase, 'asking')
        self.assertEqual(self.task.asked_now(), self.task.round.asked[0])
        self.task.on_draw()

    def test_there_is_no_move_or_question_outside_their_phase(self):
        self.task.start_run()
        self.assertIsNone(self.task.asked_now())
        self._walk_through()
        self.assertIsNone(self.task.move_now())

    def test_every_question_is_asked_before_any_is_marked(self):
        """Verdicts wait, because chains share boxes.

        Saying "that one went in van two" between questions would
        narrow the others whenever two answers run through the same
        box, so nothing is marked until the last answer is in.
        """
        self.task.start_run()
        self._walk_through()
        for spot in range(len(self.task.round.asked) - 1):
            self.task.answer(0)
            self.assertEqual(self.task.phase, 'asking')
        self.task.answer(0)
        self.assertEqual(self.task.phase, 'scored')

    def test_a_right_answer_scores(self):
        self.task.start_run()
        self._walk_through()
        self._answer_all(right=True)
        rung, got, asked = self.task.results[0]
        self.assertEqual(got, asked)

    def test_a_wrong_answer_does_not(self):
        self.task.start_run()
        self._walk_through()
        self._answer_all(right=False)
        _rung, got, _asked = self.task.results[0]
        self.assertEqual(got, 0)

    def test_a_van_the_round_does_not_have_is_refused(self):
        self.task.start_run()
        self._walk_through()
        self.task.answer(self.task.round.yard.vans)
        self.assertEqual(self.task.given, [])

    def test_the_number_keys_answer(self):
        self.task.start_run()
        self._walk_through()
        self.task.on_key_press(ANSWER_KEYS[1], 0)
        self.assertEqual(self.task.given, [1])

    def test_the_run_finishes_after_its_rounds(self):
        self.task.start_run()
        for _trial in range(self.task.total_trials):
            self._walk_through()
            self._answer_all(right=True)
            self.now += 10.0
            self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.phase, 'done')
        tally = self.task.score()
        self.assertEqual(tally['rounds'], self.task.total_trials)
        self.assertEqual(tally['accuracy'], 100)

    def test_adaptive_climbs_after_a_clean_round(self):
        self.task.adaptive = True
        self.task.start_run()
        was = self.task.rung
        self._walk_through()
        self._answer_all(right=True)
        self.assertEqual(self.task.rung, was + 1)

    def test_adaptive_drops_after_a_poor_one(self):
        self.task.adaptive = True
        self.task.start_run()
        was = self.task.rung
        self._walk_through()
        self._answer_all(right=False)
        self.assertEqual(self.task.rung, was - 1)

    def test_it_draws_in_every_phase(self):
        self.task.on_draw()                       # ready
        self.task.start_run()
        self.task.on_draw()                       # moving
        self._walk_through()
        self.task.on_draw()                       # asking
        self._answer_all(right=True)
        self.task.on_draw()                       # scored
        self.task.total_trials = 1
        self.now += 10.0
        self.task.on_key_press(key.SPACE, 0)
        self.task.on_draw()                       # done

    def test_it_draws_a_pack_into_a_van_and_a_swap(self):
        """Both shapes a move can take, drawn on purpose rather than by luck."""
        self.task.start_run()
        yard = self.task.round.yard
        for move in (R.Move(R.PACK, yard.item(0), 0),
                     R.Move(R.PACK, yard.item(0), yard.box(0)),
                     R.Move(R.SWAP, yard.item(0), yard.item(1))):
            self.task._clear_drawn()
            self.task._draw_vans()
            self.task._draw_move(move)
            self.task.on_draw()

    def test_every_bay_lands_on_screen_and_they_do_not_overlap(self):
        self.task.start_run()
        spots = [self.task._van_rect(van)
                 for van in range(self.task.round.yard.vans)]
        for x, y, width, height in spots:
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + width, state.window.width + 1)
            self.assertLessEqual(y + height, state.window.height + 1)
        for (x, _y, width, _h), (nx, _ny, _nw, _nh) in zip(spots, spots[1:]):
            self.assertGreater(nx, x + width)

    def test_there_is_a_colour_for_every_thing_the_ladder_allows(self):
        self.assertGreaterEqual(len(ITEM_COLORS), R.MOST_ITEMS)

    def _frames_of(self, a_round, first=0):
        """Digest every frame of *a_round*'s walk from *first* onwards."""
        self.task.round = a_round
        self.task.phase = 'moving'
        prints = []
        for cursor_at in range(first, len(a_round.moves)):
            self.task.cursor = cursor_at
            self.task._redraw()
            self.task.on_draw()
            prints.append(digest_rgba(capture_rgba(state.window)[2]))
        return prints

    def test_the_walk_looks_the_same_whatever_yard_is_behind_it(self):
        """The claim the task rests on, read off the pixels themselves.

        Two rounds with the same moves and different yards behind them
        must draw the same bytes in every frame. If where anything
        actually was ever reached the screen, this is where it would
        show.
        """
        one = R.generate(SMALL_RUNG, seed=808)
        yard = one.yard
        other = [node if yard.is_van(node) else (one.start[node] + 1)
                 % yard.vans for node in range(yard.size)]
        self.assertNotEqual(tuple(other), one.start)
        mine = self._frames_of(one)
        theirs = self._frames_of(one._replace(start=tuple(other)))
        self.assertEqual(mine, theirs)
        self.assertGreater(len(set(mine)), 1)     # and not all one picture

    def test_two_walks_that_end_alike_look_alike_at_the_end(self):
        """The other half: the same pixels, and the answers still differ.

        A tail shared by two walks draws identically, which is why
        watching only the tail cannot tell them apart — and so why the
        answer has to come from further back than it reaches. The tail
        here ends on a swap, so it is not even the thing that was last
        named that gives the answer away.
        """
        tail = script('pack 3 2', 'swap 3 4')
        seen, answers = [], []
        for head in (script('pack 2 0'), script('pack 2 1')):
            moves = head + tail
            start = tuple(flat(TOY, 0, 0, 0))
            answer = R.van_of(R.carry(moves, start), 4, TOY)
            made = R.Round(yard=TOY, moves=moves, start=start, asked=(4,),
                           answers=(answer,),
                           needed=R.span(moves, 4, TOY), nest=2, churn=0)
            answers.append(made.answers)
            seen.append(self._frames_of(made, first=len(head)))
        self.assertEqual(seen[0], seen[1])
        self.assertNotEqual(answers[0], answers[1])

    def test_it_has_an_options_screen(self):
        spec = taskoptions.TASK_SPECS['removals']
        chosen = {opt.key: opt.default for opt in spec.options}
        self.assertIn('REMOVALS_LEVEL', chosen)
        self.assertTrue(spec.note(chosen))

    def test_the_note_says_how_deep_and_how_far_back(self):
        spec = taskoptions.TASK_SPECS['removals']
        chosen = {opt.key: opt.default for opt in spec.options}
        chosen['REMOVALS_LEVEL'] = 9
        said = spec.note(chosen)
        grade = R.GRADES[8]
        self.assertIn(str(grade.floor), said)
        self.assertIn(str(grade.nest), said)
        self.assertIn(_(grade.name), said)


if __name__ == '__main__':
    unittest.main()
