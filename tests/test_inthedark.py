#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""In the Dark: the rooms, the chain back, and what a short memory cannot do.

The generator's promises are what is tested hardest, because the whole
claim of the task rests on them: every question really is answerable,
the distance back to its answer really is at least the rung's floor,
and a player who remembers fewer rooms than that really is holding
nothing at all. The last one is checked by playing that player.

Small walks are written out as scripts so the expected answer can be
worked out by hand, and the fast chain in :func:`trace` is held
against the slow enumeration in :func:`belief` on generated ones.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import (InTheDark, TASKS, close_overlays, key, needs_ui,
                       reset_window, state, taskoptions)

from neural_workshop import inthedark as D
from neural_workshop.i18n import _
from neural_workshop.ui.inthedark import ANSWER_KEYS, VERDICT_SECONDS
from nwenv.frames import capture_rgba, digest_rgba

#: A rung small enough to enumerate every starting arrangement of.
SMALL_RUNG = 4
#: The rungs the slow checks sweep, one from each end and two between.
SPREAD = (1, 4, 8, 12)


def script(*lines):
    """A walk written out: ``paint 1 2``, ``turn 0``, ``swap 0 2``, ``copy 0 2``.

    ``copy 0 2`` copies lamp 2 onto lamp 0, which is the order
    :class:`~neural_workshop.inthedark.Room` stores it in — the lamp
    written to first, the lamp read second.
    """
    made = []
    for line in lines:
        word = line.split()
        made.append(D.Room(word[0], int(word[1]),
                           int(word[2]) if len(word) > 2 else 0))
    return tuple(made)


class RoomTests(unittest.TestCase):
    """What one room does to the lamps."""

    def test_paint_puts_a_colour_on_one_lamp_and_leaves_the_rest(self):
        self.assertEqual(D.enter(D.Room(D.PAINT, 1, 2), [0, 0, 0], 3),
                         [0, 2, 0])

    def test_turn_moves_one_lamp_along_by_one(self):
        self.assertEqual(D.enter(D.Room(D.TURN, 0), [1, 0], 3), [2, 0])

    def test_turn_wraps_round_the_last_colour(self):
        self.assertEqual(D.enter(D.Room(D.TURN, 0), [2, 0], 3), [0, 0])

    def test_swap_exchanges_two_lamps(self):
        self.assertEqual(D.enter(D.Room(D.SWAP, 0, 2), [1, 5, 3], 6),
                         [3, 5, 1])

    def test_copy_overwrites_the_first_lamp_from_the_second(self):
        self.assertEqual(D.enter(D.Room(D.COPY, 0, 2), [1, 5, 3], 6),
                         [3, 5, 3])

    def test_copy_leaves_the_lamp_it_read(self):
        cells = D.enter(D.Room(D.COPY, 0, 2), [1, 5, 3], 6)
        self.assertEqual(cells[2], 3)

    def test_a_walk_is_its_rooms_one_after_another(self):
        rooms = script('paint 0 1', 'turn 0', 'swap 0 1')
        self.assertEqual(D.walk(rooms, [0, 0], 3), (0, 2))

    def test_an_empty_walk_changes_nothing(self):
        self.assertEqual(D.walk((), [1, 2], 3), (1, 2))


class TraceTests(unittest.TestCase):
    """Following one lamp's colour backwards to where it came from."""

    def test_a_paint_at_the_end_is_one_room_back(self):
        self.assertEqual(D.trace(script('turn 0', 'paint 0 1'), 0), (1, 0))

    def test_rooms_after_the_paint_count_towards_the_distance(self):
        rooms = script('paint 0 1', 'turn 0', 'turn 0')
        self.assertEqual(D.trace(rooms, 0), (3, 2))

    def test_rooms_that_touch_other_lamps_cost_no_work(self):
        rooms = script('paint 0 1', 'turn 1', 'turn 1', 'turn 1')
        self.assertEqual(D.trace(rooms, 0), (4, 0))

    def test_a_swap_moves_which_lamp_is_being_followed(self):
        # lamp 0 ends up holding what lamp 1 was painted, so the chain
        # runs back through the swap to the paint on lamp 1.
        rooms = script('paint 1 2', 'swap 0 1')
        self.assertEqual(D.trace(rooms, 0), (2, 1))

    def test_a_copy_moves_the_chain_to_the_lamp_it_read(self):
        rooms = script('paint 1 2', 'copy 0 1')
        self.assertEqual(D.trace(rooms, 0), (2, 1))

    def test_a_copy_out_of_a_lamp_does_not_move_that_lamp_s_chain(self):
        rooms = script('paint 1 2', 'copy 0 1')
        self.assertEqual(D.trace(rooms, 1), (2, 0))

    def test_a_swap_and_a_swap_back_lead_where_they_started(self):
        rooms = script('paint 0 1', 'swap 0 1', 'swap 0 1')
        self.assertEqual(D.trace(rooms, 0), (3, 2))

    def test_a_lamp_no_room_ever_pinned_has_no_chain(self):
        self.assertEqual(D.trace(script('turn 0', 'swap 0 1'), 0)[0], -1)

    def test_a_paint_on_another_lamp_pins_nothing_here(self):
        self.assertEqual(D.trace(script('paint 1 0'), 0)[0], -1)

    def test_the_last_paint_wins_over_an_earlier_one(self):
        rooms = script('paint 0 1', 'turn 0', 'paint 0 2')
        self.assertEqual(D.trace(rooms, 0), (1, 0))

    def test_an_empty_walk_pins_nothing(self):
        self.assertEqual(D.trace((), 0)[0], -1)


class BeliefTests(unittest.TestCase):
    """The slow reading of the same question, and the fast one."""

    def test_an_unpinned_lamp_could_still_be_any_colour(self):
        rooms = script('turn 0', 'swap 0 1')
        self.assertEqual(D.belief(rooms, 0, 2, 3), frozenset((0, 1, 2)))

    def test_a_pinned_lamp_could_only_be_the_one(self):
        rooms = script('paint 0 1', 'turn 0')
        self.assertEqual(D.belief(rooms, 0, 2, 3), frozenset((2,)))

    def test_pinned_reports_the_colour_belief_settles_on(self):
        rooms = script('paint 0 1', 'turn 0')
        self.assertEqual(D.pinned(rooms, 0, 2, 3), 2)

    def test_pinned_says_nothing_about_a_lamp_with_no_chain(self):
        self.assertIsNone(D.pinned(script('turn 0'), 0, 2, 3))

    def test_the_chain_and_the_enumeration_always_agree(self):
        """A pinned chain and a single-colour belief are the same thing."""
        for rung in SPREAD:
            grade = D.GRADES[rung - 1]
            if grade.colours ** grade.lamps > 4096:
                continue                     # enumeration would be silly here
            for trial in range(12):
                got = D.generate(rung, seed=900 + rung * 40 + trial)
                for lamp in range(got.lamps):
                    chained = D.trace(got.rooms, lamp)[0] >= 0
                    settled = len(D.belief(got.rooms, lamp, got.lamps,
                                           got.colours)) == 1
                    self.assertEqual(chained, settled,
                                     'lamp %d of rung %d' % (lamp, rung))

    def test_a_pinned_colour_does_not_depend_on_what_the_lamps_started_at(self):
        rng = random.Random(4)
        for trial in range(40):
            got = D.generate(SMALL_RUNG, seed=1200 + trial)
            for _try in range(4):
                other = [rng.randrange(got.colours) for _ in range(got.lamps)]
                reached = D.walk(got.rooms, other, got.colours)
                for lamp, answer in zip(got.asked, got.answers):
                    self.assertEqual(reached[lamp], answer)


class RememberingTests(unittest.TestCase):
    """The foil: a player who recalls only the last few rooms."""

    def test_it_is_sure_of_a_question_the_tail_pins(self):
        one = D.Round(lamps=2, colours=3, rooms=script('turn 1', 'paint 0 2'),
                      start=(0, 0), asked=(0,), answers=(2,), needed=1,
                      work=0.0)
        self.assertEqual(D.remembering(one, 1), (1, 1))

    def test_it_is_sure_of_nothing_the_tail_does_not_reach(self):
        one = D.Round(lamps=2, colours=3,
                      rooms=script('paint 0 2', 'turn 1', 'turn 1'),
                      start=(0, 0), asked=(0,), answers=(2,), needed=3,
                      work=0.0)
        self.assertEqual(D.remembering(one, 2), (0, 1))

    def test_the_whole_walk_settles_every_question(self):
        for rung in SPREAD:
            got = D.generate(rung, seed=2200 + rung)
            self.assertEqual(D.remembering(got, len(got.rooms)),
                             (len(got.asked), len(got.asked)))

    def test_a_memory_shorter_than_the_round_needs_settles_nothing(self):
        """The claim the whole task rests on, played out rung by rung."""
        for rung in range(1, len(D.GRADES) + 1):
            for trial in range(25):
                got = D.generate(rung, seed=3300 + rung * 60 + trial)
                sure, asked = D.remembering(got, got.needed - 1)
                self.assertEqual(sure, 0,
                                 'rung %d settled %d of %d questions from '
                                 '%d rooms' % (rung, sure, asked,
                                               got.needed - 1))

    def test_a_memory_of_the_whole_round_settles_the_weakest_question(self):
        for rung in SPREAD:
            for trial in range(15):
                got = D.generate(rung, seed=4400 + rung * 30 + trial)
                sure, _asked = D.remembering(got, got.needed)
                self.assertGreaterEqual(sure, 1)


class LadderTests(unittest.TestCase):
    """The rungs themselves, before anything is dealt."""

    def test_the_ladder_climbs(self):
        for lower, upper in zip(D.GRADES, D.GRADES[1:]):
            self.assertGreater(upper.floor, lower.floor, upper.name)
            self.assertGreaterEqual(upper.depth, lower.depth, upper.name)
            self.assertGreaterEqual(upper.lamps, lower.lamps, upper.name)
            self.assertGreaterEqual(upper.colours, lower.colours, upper.name)
            self.assertGreaterEqual(upper.work, lower.work, upper.name)

    def test_no_rung_asks_for_more_lamps_or_colours_than_can_be_told_apart(self):
        for grade in D.GRADES:
            self.assertLessEqual(grade.lamps, D.MOST_LAMPS, grade.name)
            self.assertLessEqual(grade.colours, D.MOST_COLOURS, grade.name)

    def test_no_rung_asks_about_more_lamps_than_it_has(self):
        for grade in D.GRADES:
            self.assertLessEqual(grade.asks, grade.lamps, grade.name)
            self.assertGreaterEqual(grade.asks, 1, grade.name)

    def test_every_floor_leaves_room_for_the_answer_to_be_put_there(self):
        """A walk must be long enough to bury its answers and pin them."""
        for grade in D.GRADES:
            self.assertLess(grade.floor + grade.asks, grade.depth, grade.name)

    def test_the_names_are_all_different(self):
        names = [grade.name for grade in D.GRADES]
        self.assertEqual(len(names), len(set(names)))


class VocabularyTests(unittest.TestCase):
    """The rooms a rung has to draw from."""

    def test_there_is_a_paint_for_every_lamp_and_colour(self):
        rooms = D.vocabulary(3, 4)
        self.assertEqual(sum(1 for r in rooms if r.kind == D.PAINT), 12)

    def test_there_is_a_turn_for_every_lamp(self):
        rooms = D.vocabulary(3, 4)
        self.assertEqual(sum(1 for r in rooms if r.kind == D.TURN), 3)

    def test_a_swap_is_counted_once_not_twice(self):
        rooms = D.vocabulary(4, 3)
        self.assertEqual(sum(1 for r in rooms if r.kind == D.SWAP), 6)

    def test_a_copy_is_counted_both_ways_round(self):
        rooms = D.vocabulary(4, 3)
        self.assertEqual(sum(1 for r in rooms if r.kind == D.COPY), 12)

    def test_no_room_reads_a_lamp_that_is_not_there(self):
        for rooms in (D.vocabulary(2, 2), D.vocabulary(6, 5)):
            lamps = max(r.lamp for r in rooms) + 1
            for room in rooms:
                self.assertLess(room.lamp, lamps)
                if room.kind in (D.SWAP, D.COPY):
                    self.assertLess(room.other, lamps)
                    self.assertNotEqual(room.other, room.lamp)

    def test_a_lamp_is_never_copied_onto_itself(self):
        for room in D.vocabulary(5, 4):
            if room.kind == D.COPY:
                self.assertNotEqual(room.lamp, room.other)

    def test_every_kind_gets_a_share_of_the_deal(self):
        rooms = D.vocabulary(4, 3)
        weights = D._weights(rooms)
        for kind in D.KINDS:
            share = sum(w for r, w in zip(rooms, weights) if r.kind == kind)
            self.assertAlmostEqual(share, D.MIX[kind])


class GenerateTests(unittest.TestCase):
    """What every dealt round promises."""

    def test_the_same_seed_deals_the_same_round(self):
        self.assertEqual(D.generate(6, seed=17), D.generate(6, seed=17))

    def test_another_seed_deals_another_round(self):
        self.assertNotEqual(D.generate(6, seed=17), D.generate(6, seed=18))

    def test_a_level_past_the_ladder_is_the_last_rung(self):
        last = D.GRADES[-1]
        got = D.generate(len(D.GRADES) + 40, seed=5)
        self.assertEqual((got.lamps, got.colours, len(got.rooms)),
                         (last.lamps, last.colours, last.depth))

    def test_a_level_below_the_ladder_is_the_first_rung(self):
        got = D.generate(0, seed=5)
        self.assertEqual(len(got.rooms), D.GRADES[0].depth)

    def test_a_round_is_its_rung_s_size(self):
        for rung in range(1, len(D.GRADES) + 1):
            grade = D.GRADES[rung - 1]
            got = D.generate(rung, seed=6600 + rung)
            self.assertEqual(len(got.rooms), grade.depth, grade.name)
            self.assertEqual(len(got.asked), grade.asks, grade.name)
            self.assertEqual(got.lamps, grade.lamps, grade.name)
            self.assertEqual(got.colours, grade.colours, grade.name)

    def test_no_lamp_is_asked_about_twice(self):
        for rung in range(1, len(D.GRADES) + 1):
            got = D.generate(rung, seed=7700 + rung)
            self.assertEqual(len(set(got.asked)), len(got.asked))

    def test_every_rung_clears_its_own_floor(self):
        for rung in range(1, len(D.GRADES) + 1):
            grade = D.GRADES[rung - 1]
            for trial in range(20):
                got = D.generate(rung, seed=8800 + rung * 50 + trial)
                self.assertGreaterEqual(got.needed, grade.floor, grade.name)

    def test_every_rung_clears_its_work_floor_too(self):
        """The junior axis, which the search shops for rather than lays."""
        for rung in range(1, len(D.GRADES) + 1):
            grade = D.GRADES[rung - 1]
            for trial in range(10):
                got = D.generate(rung, seed=9900 + rung * 30 + trial)
                self.assertGreaterEqual(got.work, grade.work, grade.name)

    def test_every_question_can_be_answered_at_all(self):
        for rung in range(1, len(D.GRADES) + 1):
            for trial in range(20):
                got = D.generate(rung, seed=11000 + rung * 50 + trial)
                for lamp in got.asked:
                    self.assertGreaterEqual(D.trace(got.rooms, lamp)[0], 0)

    def test_the_answers_are_where_the_walk_actually_ends_up(self):
        for rung in range(1, len(D.GRADES) + 1):
            for trial in range(10):
                got = D.generate(rung, seed=12000 + rung * 30 + trial)
                reached = D.walk(got.rooms, got.start, got.colours)
                self.assertEqual(got.answers,
                                 tuple(reached[lamp] for lamp in got.asked))

    def test_the_lamps_start_somewhere_inside_the_palette(self):
        for rung in SPREAD:
            got = D.generate(rung, seed=13000 + rung)
            self.assertEqual(len(got.start), got.lamps)
            for colour in got.start:
                self.assertIn(colour, range(got.colours))

    def test_no_room_is_undone_by_the_very_next_one(self):
        for rung in range(1, len(D.GRADES) + 1):
            for trial in range(10):
                got = D.generate(rung, seed=14000 + rung * 30 + trial)
                for before, after in zip(got.rooms, got.rooms[1:]):
                    self.assertNotEqual(before, after)

    def test_the_last_rooms_of_a_rung_never_settle_a_question(self):
        """What the backwards laying is for, read off the finished walk."""
        for rung in range(1, len(D.GRADES) + 1):
            grade = D.GRADES[rung - 1]
            for trial in range(10):
                got = D.generate(rung, seed=15000 + rung * 30 + trial)
                tail = got.rooms[len(got.rooms) - (grade.floor - 1):]
                for lamp in got.asked:
                    self.assertEqual(D.trace(tail, lamp)[0], -1,
                                     '%s settles lamp %d inside its last %d '
                                     'rooms' % (grade.name, lamp,
                                                grade.floor - 1))

    def test_one_attempt_still_deals_a_round_that_clears_the_floor(self):
        """The floor is laid, not shopped for, so it survives no search."""
        for rung in SPREAD:
            grade = D.GRADES[rung - 1]
            got = D.generate(rung, seed=16000 + rung, attempts=1)
            self.assertGreaterEqual(got.needed, grade.floor, grade.name)

    def test_the_work_is_the_mean_of_what_the_questions_cost(self):
        got = D.generate(8, seed=21)
        by_hand = [D.trace(got.rooms, lamp)[1] for lamp in got.asked]
        self.assertAlmostEqual(got.work, sum(by_hand) / float(len(by_hand)))

    def test_the_needed_is_the_weakest_of_what_the_questions_cost(self):
        got = D.generate(8, seed=21)
        by_hand = [D.trace(got.rooms, lamp)[0] for lamp in got.asked]
        self.assertEqual(got.needed, min(by_hand))


@needs_ui
class DarkScreenTests(unittest.TestCase):
    """The screen: walking it, answering it, and what it never shows."""

    def setUp(self):
        close_overlays()
        self.now = 1000.0
        self.task = InTheDark()
        self.task.clock = lambda: self.now
        self.task.total_trials = 2
        self.task.adaptive = False
        self.task.room_seconds = 1.0
        self.task.start_rung = SMALL_RUNG
        self.task.rung = SMALL_RUNG

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def _tick(self, seconds=1.0):
        """Let *seconds* of the virtual clock go by, a frame at a time."""
        for _frame in range(max(1, int(seconds * 60))):
            self.now += 1 / 60.
            self.task.update(1 / 60.)

    def _walk_the_rooms(self):
        """Run the walk out, leaving the task at its first question."""
        while self.task.phase == 'walking':
            self._tick(self.task.room_seconds + 0.02)

    def _answer_all(self, right=True):
        for spot in range(len(self.task.round.asked)):
            truth = self.task.round.answers[spot]
            self.task.answer(truth if right
                             else (truth + 1) % self.task.round.colours)

    def test_it_is_in_the_working_memory_category(self):
        self.assertIn('in_the_dark',
                      [task for task, _n in TASKS['working_memory']])

    def test_a_trial_deals_a_round_and_shows_its_first_room(self):
        self.task.start_run()
        self.assertEqual(self.task.phase, 'walking')
        self.assertEqual(self.task.cursor, 0)
        self.assertEqual(self.task.room_now(), self.task.round.rooms[0])
        self.task.on_draw()

    def test_the_rooms_go_by_one_at_a_time(self):
        self.task.start_run()
        self._tick(self.task.room_seconds + 0.02)
        self.assertEqual(self.task.cursor, 1)
        self._tick(self.task.room_seconds + 0.02)
        self.assertEqual(self.task.cursor, 2)

    def test_a_room_stays_put_until_its_time_is_up(self):
        self.task.start_run()
        self._tick(self.task.room_seconds * 0.5)
        self.assertEqual(self.task.cursor, 0)

    def test_the_walk_ends_in_questions(self):
        self.task.start_run()
        self._walk_the_rooms()
        self.assertEqual(self.task.phase, 'asking')
        self.assertEqual(self.task.asked_now(), self.task.round.asked[0])

    def test_no_room_is_shown_once_the_questions_start(self):
        self.task.start_run()
        self._walk_the_rooms()
        self.assertIsNone(self.task.room_now())

    def test_the_questions_come_one_after_another(self):
        self.task.start_run()
        self._walk_the_rooms()
        asked = self.task.round.asked
        for spot in range(len(asked) - 1):
            self.assertEqual(self.task.asked_now(), asked[spot])
            self.task.answer(0)
        self.assertEqual(self.task.asked_now(), asked[-1])

    def test_no_verdict_is_given_until_the_last_question_is_taken(self):
        """Saying which was right would narrow what the others can be."""
        self.task.start_run()
        self._walk_the_rooms()
        for _spot in range(len(self.task.round.asked) - 1):
            self.task.answer(0)
            self.assertEqual(self.task.phase, 'asking')
            self.assertEqual(self.task.results, [])
        self.task.answer(0)
        self.assertEqual(self.task.phase, 'scored')

    def test_a_clean_round_scores_every_question(self):
        self.task.start_run()
        self._walk_the_rooms()
        asked = len(self.task.round.asked)
        self._answer_all(right=True)
        self.assertEqual(self.task.results[-1][1:], (asked, asked))

    def test_a_wrong_answer_is_counted_as_one(self):
        self.task.start_run()
        self._walk_the_rooms()
        asked = len(self.task.round.asked)
        self._answer_all(right=False)
        self.assertEqual(self.task.results[-1][1:], (0, asked))

    def test_a_colour_the_round_does_not_have_is_not_an_answer(self):
        self.task.start_run()
        self._walk_the_rooms()
        before = self.task.asking_at
        self.task.answer(self.task.round.colours + 1)
        self.assertEqual(self.task.asking_at, before)

    def test_a_key_past_the_round_s_colours_does_nothing(self):
        self.task.start_run()
        self._walk_the_rooms()
        self.assertLess(self.task.round.colours, D.MOST_COLOURS)
        before = self.task.asking_at
        self.task.on_key_press(ANSWER_KEYS[D.MOST_COLOURS - 1], 0)
        self.assertEqual(self.task.asking_at, before)

    def test_a_key_inside_them_answers(self):
        self.task.start_run()
        self._walk_the_rooms()
        self.task.on_key_press(ANSWER_KEYS[0], 0)
        self.assertEqual(self.task.given, [0])

    def test_the_run_finishes_after_its_rounds(self):
        self.task.start_run()
        for _trial in range(self.task.total_trials):
            self._walk_the_rooms()
            self._answer_all(right=True)
            self.now += VERDICT_SECONDS + 0.1
            self.task.on_key_press(key.SPACE, 0)
        self.assertEqual(self.task.phase, 'done')
        self.assertEqual(self.task.score()['rounds'], self.task.total_trials)

    def test_the_score_counts_questions_not_rounds(self):
        self.task.start_run()
        self._walk_the_rooms()
        self._answer_all(right=True)
        self.assertEqual(self.task.score()['accuracy'], 100)
        self.assertEqual(self.task.score()['perfect'], 1)

    def test_adaptive_climbs_on_a_clean_round(self):
        self.task.adaptive = True
        self.task.start_run()
        was = self.task.rung
        self._walk_the_rooms()
        self._answer_all(right=True)
        self.assertEqual(self.task.rung, was + 1)

    def test_adaptive_drops_on_a_poor_one(self):
        self.task.adaptive = True
        self.task.start_rung = self.task.rung = 5
        self.task.start_run()
        was = self.task.rung
        self._walk_the_rooms()
        self._answer_all(right=False)
        self.assertEqual(self.task.rung, was - 1)

    def test_it_draws_in_every_phase(self):
        self.task.on_draw()                      # ready
        self.task.start_run()
        self.task.on_draw()                      # walking
        self._walk_the_rooms()
        self.task.on_draw()                      # asking
        self._answer_all(right=True)
        self.task.on_draw()                      # scored
        self.task.total_trials = 1
        self.now += VERDICT_SECONDS + 0.1
        self.task.on_key_press(key.SPACE, 0)
        self.task.on_draw()                      # done

    def test_every_socket_lands_on_screen(self):
        self.task.start_run()
        for lamp in range(self.task.round.lamps):
            x, y, radius = self.task._socket(lamp)
            self.assertGreaterEqual(x - radius, 0)
            self.assertLessEqual(x + radius, state.window.width)
            self.assertGreaterEqual(y - radius, 0)
            self.assertLessEqual(y + radius, state.window.height)

    def test_the_sockets_do_not_overlap(self):
        self.task.start_run()
        spots = [self.task._socket(lamp)
                 for lamp in range(self.task.round.lamps)]
        for (x, _y, radius), (nx, _ny, _nr) in zip(spots, spots[1:]):
            self.assertGreater(nx - x, radius * 2)

    def _frames_of(self, a_round, first=0):
        """Digest every frame of *a_round*'s walk from *first* onwards."""
        self.task.round = a_round
        self.task.phase = 'walking'
        prints = []
        for cursor_at in range(first, len(a_round.rooms)):
            self.task.cursor = cursor_at
            self.task._redraw()
            self.task.on_draw()
            prints.append(digest_rgba(capture_rgba(state.window)[2]))
        return prints

    def test_the_walk_looks_the_same_whatever_is_behind_it(self):
        """The claim the task rests on, read off the pixels themselves.

        Two rounds with the same rooms and different colours behind
        them must draw the same bytes in every frame of the walk. If a
        lamp ever reached the screen, this is where it would show.
        """
        one = D.generate(SMALL_RUNG, seed=606)
        other = tuple((colour + 1) % one.colours for colour in one.start)
        self.assertNotEqual(other, one.start)
        mine = self._frames_of(one)
        theirs = self._frames_of(one._replace(start=other))
        self.assertEqual(mine, theirs)
        self.assertGreater(len(set(mine)), 1)     # and not all one picture

    def test_two_walks_that_end_alike_look_alike_at_the_end(self):
        """The other half: the same pixels, and the answers still differ.

        A tail shared by two different walks draws identically, which
        is why watching only the tail cannot tell them apart — and so
        why the answer has to come from further back than it reaches.
        """
        tail = script('turn 0', 'swap 0 1', 'turn 1')
        seen, answers = [], []
        for head in (script('paint 0 0'), script('paint 0 1')):
            rooms = head + tail
            made = D.Round(lamps=2, colours=3, rooms=rooms, start=(0, 0),
                           asked=(1,), answers=(D.walk(rooms, (0, 0), 3)[1],),
                           needed=D.trace(rooms, 1)[0], work=0.0)
            answers.append(made.answers)
            seen.append(self._frames_of(made, first=len(head)))
        self.assertEqual(seen[0], seen[1])
        self.assertNotEqual(answers[0], answers[1])

    def test_it_has_an_options_screen(self):
        spec = taskoptions.TASK_SPECS['in_the_dark']
        chosen = {opt.key: opt.default for opt in spec.options}
        self.assertIn('DARK_LEVEL', chosen)
        self.assertTrue(spec.note(chosen))

    def test_the_note_says_what_a_short_memory_is_worth(self):
        spec = taskoptions.TASK_SPECS['in_the_dark']
        chosen = {opt.key: opt.default for opt in spec.options}
        chosen['DARK_LEVEL'] = 9
        said = spec.note(chosen)
        grade = D.GRADES[8]
        self.assertIn(str(grade.floor), said)
        self.assertIn(_(grade.name), said)


if __name__ == '__main__':
    unittest.main()
