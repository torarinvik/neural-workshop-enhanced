#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Cookie Thief's model: the door, the press, and the three promises.

Nothing here draws anything. What is being checked is the part the
screen only reports:

* that the ladder is a ladder — that each rung adds one thing, that the
  warning only ever gets shorter, that reaction stops being enough
  exactly once and never starts again, and that random presses are
  worth less the higher you go;

* that every rung is winnable **without gambling at all**, by a thief
  who takes only the grabs that cannot possibly bring her, so a round
  that was lost was lost on a decision and not on the deal;

* that coach mode is **blind to both hidden things**. It reads the jar,
  the pips and the door, and it cannot read the trigger or the
  deadline. Those two are the whole of what the task hides, and a coach
  that knew them would have answered the only question it asks.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import inspect
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('NW_HEADLESS', '1')

import oracle_cookie as O                              # noqa: E402
from neural_workshop import cookiethief as C           # noqa: E402
from uisupport import (UI_IMPORT_ERROR, close_overlays,  # noqa: E402
                       needs_ui, reset_window)

if UI_IMPORT_ERROR is None:
    from nwenv import catalog                          # noqa: E402


def dealt(level, seed=0):
    """A setup and a fresh thief, the way a round starts."""
    return C.generate(level, seed=seed), C.Thief()


def alone(level, seed=0):
    """The same, with nobody coming: for testing the door on its own."""
    setup, thief = dealt(level, seed=seed)
    return setup._replace(trigger=10 ** 6, deadline=10 ** 6,
                          decoys=()), thief


def run(setup, thief, ports):
    """Press *ports* in order, one a beat, and stop when the round does."""
    for port in ports:
        if C.over(thief, setup):
            break
        C.press(thief, port, setup)
        C.beat(thief, setup)
    return thief


class TheLadder(unittest.TestCase):
    """What the rungs promise before anybody plays them."""

    def test_the_first_rung_is_one_cookie_and_nothing_else(self):
        """A ladder whose bottom rung needs a plan has no bottom."""
        first = C.GRADES[0]
        self.assertEqual(first.quota, 1)
        self.assertEqual(first.opening, 0)
        self.assertTrue(first.reactive)
        self.assertEqual(first.gold, 0)
        self.assertEqual(first.decoys, 0)

    def test_the_quota_never_falls(self):
        quotas = [grade.quota for grade in C.GRADES]
        self.assertEqual(quotas, sorted(quotas), quotas)

    def test_every_rung_has_room_for_what_it_asks_for(self):
        """A quiet beat takes the noise back off but never the gap in
        the jar, so ``room`` is the hard ceiling however patient anybody
        is. A rung asking for more than that would be asking for
        something it does not have."""
        for grade in C.GRADES:
            self.assertGreaterEqual(grade.room, grade.quota, grade.name)

    def test_each_rung_adds_something(self):
        for below, above in zip(C.GRADES, C.GRADES[1:]):
            harder = (
                above.quota > below.quota
                or above.warn < below.warn
                or above.spread < below.spread
                or above.opening > below.opening
                or above.settling < below.settling
                or above.gold > below.gold
                or above.decoys > below.decoys)
            self.assertTrue(harder, '%s adds nothing to %s'
                                    % (above.name, below.name))

    def test_the_warning_only_ever_gets_shorter(self):
        warns = [grade.warn for grade in C.GRADES]
        self.assertEqual(warns, sorted(warns, reverse=True), warns)
        self.assertGreaterEqual(warns[0], 5)
        self.assertEqual(warns[-1], 0)

    def test_reaction_stops_being_enough_once_and_stays_that_way(self):
        """The break in the ladder, and there is meant to be exactly one.

        Below it a thief can play by watching the doorway. Above it he
        cannot, ever again — a rung that handed reaction back would be
        one on which everything learned above it was optional.
        """
        reactive = [grade.reactive for grade in C.GRADES]
        self.assertTrue(reactive[0])
        self.assertFalse(reactive[-1])
        self.assertEqual(reactive, sorted(reactive, reverse=True), reactive)

    def test_she_never_comes_below_the_safe_line(self):
        """Which is what makes leaving at the line a certainly clean round.

        The trigger can only ever punish a grab taken past the point
        where the door is known to be safe, never the quota itself.
        """
        for level in range(1, len(C.GRADES) + 1):
            grade = C.GRADES[level - 1]
            for seed in range(30):
                setup = C.generate(level, seed=seed)
                self.assertGreaterEqual(setup.trigger, C.SAFE)
                self.assertLess(setup.trigger, grade.limit)

    def test_the_extras_arrive_at_the_top(self):
        for grade in C.GRADES[:7]:
            self.assertEqual(grade.gold, 0, grade.name)
            self.assertEqual(grade.decoys, 0, grade.name)
        self.assertTrue(C.GRADES[-1].gold)
        self.assertTrue(C.GRADES[-1].decoys)

    def test_guessing_is_worth_less_the_higher_you_go(self):
        """Measured, because there is nothing here to derive.

        What a run of random presses scores is whatever a random hand
        happens to take before the door is open far enough. It is not
        asserted rung by rung either: four hundred deals at a floor of a
        few per cent carry about a point of standard error, and most of
        the ladder is already at the bottom of the scale.
        """
        deals = 400
        tolerance = 0.03            # about two standard errors down here
        floors = [C.rehearse(level, deals=deals)
                  for level in range(1, len(C.GRADES) + 1)]
        self.assertGreater(floors[0], 0.2, floors)
        self.assertLess(floors[-1], 0.05, floors)
        for above in range(1, len(floors)):
            self.assertLessEqual(floors[above],
                                 max(floors[:above]) + tolerance, floors)


class ThePress(unittest.TestCase):
    """One press, one cookie, on the beat it was asked for."""

    def setUp(self):
        self.setup, self.thief = alone(7, seed=1)
        self.grade = self.setup.grade

    def test_a_grab_is_instant(self):
        """Nothing queued and nothing in flight. The whole of the feel."""
        self.assertTrue(C.press(self.thief, C.GRAB, self.setup))
        self.assertEqual(self.thief.jar, 1)
        self.assertEqual(self.thief.eaten, 1)

    def test_leaving_ends_the_round_there_and_then(self):
        run(self.setup, self.thief, [C.GRAB] * 3)
        self.assertFalse(C.over(self.thief, self.setup))
        C.press(self.thief, C.LEAVE, self.setup)
        self.assertTrue(C.over(self.thief, self.setup))
        self.assertEqual(self.thief.eaten, 3)

    def test_waiting_takes_nothing_and_costs_a_beat(self):
        run(self.setup, self.thief, [C.WAIT] * 3)
        self.assertEqual(self.thief.jar, 0)
        self.assertEqual(self.thief.beat, 3)

    def test_lunging_at_nothing_does_nothing(self):
        self.assertFalse(C.press(self.thief, C.LUNGE, self.setup))
        self.assertEqual(self.thief.eaten, 0)


class TheDoor(unittest.TestCase):
    """The two halves of the opening, and which of them comes back off."""

    def setUp(self):
        self.setup, self.thief = alone(7, seed=1)
        self.grade = self.setup.grade

    def test_it_is_the_jar_plus_the_noise(self):
        run(self.setup, self.thief, [C.GRAB, C.GRAB])
        self.assertEqual(C.floor_of(self.thief, self.grade),
                         2 * self.grade.notice)
        self.assertEqual(C.door(self.thief, self.grade),
                         C.floor_of(self.thief, self.grade) + self.thief.pace)
        self.assertGreater(self.thief.pace, 0)

    def test_a_quiet_beat_takes_the_noise_off_and_nothing_else(self):
        run(self.setup, self.thief, [C.GRAB])
        floor = C.floor_of(self.thief, self.grade)
        opened = C.door(self.thief, self.grade)
        run(self.setup, self.thief, [C.WAIT])
        self.assertEqual(C.floor_of(self.thief, self.grade), floor)
        self.assertLess(C.door(self.thief, self.grade), opened)

    def test_the_floor_never_falls(self):
        """However long he stands there. It is what caps a round."""
        run(self.setup, self.thief, [C.GRAB] * 3 + [C.WAIT] * 30)
        self.assertEqual(self.thief.pace, 0)
        self.assertEqual(C.door(self.thief, self.grade),
                         3 * self.grade.notice)

    def test_after_a_grab_is_what_a_grab_actually_does(self):
        """The number on the screen has to be the number he gets."""
        for level in (3, 7, 10):
            setup, thief = alone(level, seed=3)
            grade = setup.grade
            for _round in range(4):
                said = C.after_a_grab(thief, grade)
                C.press(thief, C.GRAB, setup)
                self.assertEqual(C.door(thief, grade), said, grade.name)
                C.beat(thief, setup)

    def test_leaving_at_the_safe_line_is_certainly_clean(self):
        for level in range(1, len(C.GRADES) + 1):
            for seed in range(15):
                setup, thief = dealt(level, seed=seed)
                grade = setup.grade
                while C.safe(thief, grade) and not C.over(thief, setup):
                    C.press(thief, C.GRAB, setup)
                    C.beat(thief, setup)
                self.assertEqual(thief.caught, 0,
                                 '%s seed %d' % (grade.name, seed))


class SheComes(unittest.TestCase):
    """When, with how much warning, and whether the grab was hers."""

    def test_the_door_brings_her(self):
        setup, thief = dealt(7, seed=3)
        setup = setup._replace(deadline=10 ** 6, decoys=())
        run(setup, thief, [C.GRAB] * 40)
        self.assertGreaterEqual(C.door(thief, setup.grade), setup.trigger)
        self.assertEqual(thief.who, C.MOTHER)

    def test_the_deadline_brings_her_even_if_he_took_nothing(self):
        setup, thief = dealt(7, seed=3)
        setup = setup._replace(deadline=5, decoys=())
        run(setup, thief, [C.WAIT] * 40)
        self.assertEqual(thief.jar, 0)
        self.assertEqual(thief.who, C.MOTHER)

    def test_a_warning_is_the_rung_s_warning(self):
        setup, thief = dealt(3, seed=3)
        setup = setup._replace(deadline=3, decoys=())
        run(setup, thief, [C.WAIT] * 3)
        self.assertEqual(thief.phase, C.COMING)
        came = thief.beat
        while thief.phase == C.COMING:
            C.beat(thief, setup)
        self.assertEqual(thief.beat - came, setup.grade.warn)
        self.assertEqual(thief.phase, C.WATCHING)

    def test_with_no_warning_she_is_looking_the_beat_she_arrives(self):
        """The grab that opens the door far enough is the one she sees.

        This is the whole of what the top half of the ladder is: there
        is nothing to react to, because by the time there is anything on
        the screen the press has already happened.
        """
        setup, thief = dealt(10, seed=3)
        setup = setup._replace(deadline=10 ** 6, decoys=())
        self.assertEqual(setup.grade.warn, 0)
        run(setup, thief, [C.GRAB] * 40)
        self.assertGreater(thief.caught, 0)

    def test_with_a_warning_leaving_still_saves_him(self):
        setup, thief = dealt(3, seed=3)
        setup = setup._replace(deadline=10 ** 6, decoys=())
        for _beat in range(60):
            if C.over(thief, setup):
                break
            port = C.LEAVE if thief.who == C.MOTHER else C.GRAB
            C.press(thief, port, setup)
            C.beat(thief, setup)
        self.assertEqual(thief.caught, 0)

    def test_a_decoy_goes_away_again(self):
        setup, thief = dealt(9, seed=3)
        setup = setup._replace(trigger=10 ** 6, deadline=10 ** 6,
                               decoys=((4, C.DOG),))
        run(setup, thief, [C.WAIT] * 3 + [C.WAIT] * 12)
        self.assertEqual(thief.phase, C.AWAY)
        self.assertIsNone(thief.who)

    def test_she_wins_over_a_decoy_on_the_same_beat(self):
        """A round where the real one hid behind a false one is a round
        nobody could have played."""
        setup, thief = dealt(9, seed=3)
        setup = setup._replace(deadline=4, decoys=((4, C.SISTER),))
        run(setup, thief, [C.WAIT] * 6)
        self.assertEqual(thief.who, C.MOTHER)


class TheRound(unittest.TestCase):
    """How it ends, and what it is worth when it does."""

    def test_letting_the_noise_die_down_is_not_doing_nothing(self):
        """The rule that used to fight the game.

        Waiting is how a quick hand buys its next grab, and the top
        rungs need several quiet beats after a run of them. Counted as
        idling, the thief walked off in the middle of the plan and came
        home a cookie short on every rung above the sixth.
        """
        setup, thief = alone(10, seed=5)
        run(setup, thief, [C.GRAB] * 4)
        self.assertGreater(thief.pace, 0)
        run(setup, thief, [C.WAIT] * 3)
        self.assertEqual(thief.still, 0)
        self.assertFalse(C.over(thief, setup))

    def test_standing_there_doing_nothing_ends_it(self):
        setup, thief = alone(10, seed=5)
        run(setup, thief, [C.GRAB] + [C.WAIT] * 30)
        self.assertEqual(thief.pace, 0)
        self.assertTrue(C.over(thief, setup))

    def test_it_does_not_end_before_he_has_started(self):
        setup, thief = alone(10, seed=5)
        run(setup, thief, [C.WAIT] * 10)
        self.assertEqual(thief.jar, 0)
        self.assertFalse(C.over(thief, setup))

    def test_a_grab_under_her_eye_is_caught(self):
        setup, thief = dealt(7, seed=5)
        setup = setup._replace(deadline=1, decoys=())
        run(setup, thief, [C.GRAB] * 20)
        self.assertGreater(thief.caught, 0)
        self.assertFalse(C.cleared(thief, setup))

    def test_stopping_short_is_a_loss_as_well(self):
        """Or never taking anything would be a winning policy."""
        setup, thief = alone(7, seed=5)
        run(setup, thief, [C.GRAB, C.LEAVE])
        self.assertLess(thief.eaten, setup.grade.quota)
        self.assertEqual(thief.caught, 0)
        self.assertFalse(C.cleared(thief, setup))

    def test_a_round_always_ends(self):
        for level in range(1, len(C.GRADES) + 1):
            for seed in range(10):
                setup, thief = dealt(level, seed=seed)
                run(setup, thief, [C.GRAB] * (C.beats_of(setup.grade) + 5))
                self.assertTrue(C.over(thief, setup),
                                '%s seed %d' % (setup.grade.name, seed))


class TheHaul(unittest.TestCase):
    """The bar and the margin, which are two different questions."""

    def test_a_cookie_he_got_away_with_is_worth_one(self):
        _setup, thief = dealt(6, seed=2)
        thief.eaten = 7
        self.assertEqual(C.haul(thief), 7)

    def test_a_grab_she_saw_costs_more_than_it_was_worth(self):
        _setup, thief = dealt(6, seed=2)
        thief.eaten, thief.caught = 7, 1
        self.assertEqual(C.haul(thief), 7 - C.CAUGHT_COST)
        self.assertLess(C.haul(thief), 6)

    def test_enough_of_them_takes_it_negative(self):
        _setup, thief = dealt(6, seed=2)
        thief.eaten, thief.caught = 4, 4
        self.assertLess(C.haul(thief), 0)

    def test_cookies_past_the_quota_still_count(self):
        """The clause that makes leaving a decision rather than a target.

        With the haul capped at the quota, one more cookie was worth
        exactly zero and carried a risk, so the answer was always to
        leave on the bar.
        """
        setup, thief = dealt(6, seed=2)
        thief.eaten = setup.grade.quota + 3
        self.assertEqual(C.haul(thief), setup.grade.quota + 3)

    def test_the_bar_and_the_margin_disagree_and_that_is_the_point(self):
        setup, thief = dealt(6, seed=2)
        thief.eaten, thief.caught = setup.grade.quota + 5, 1
        self.assertGreater(C.haul(thief), setup.grade.quota)
        self.assertFalse(C.cleared(thief, setup))

    def test_a_grab_is_worth_taking_while_it_is_under_one_in_three(self):
        """What :data:`CAUGHT_COST` is actually setting.

        A grab into the shaded range pays ``+1`` when it is safe and
        costs ``CAUGHT_COST`` when it is not, so it is worth taking
        while the chance of it bringing her is under ``1/(1+cost)``. At
        three that line is one in four, which is finer than a grab can
        be aimed — the greed dial had its best setting at zero and the
        shaded range was decoration. At two it is one in three, which a
        grab can land inside.
        """
        self.assertEqual(C.CAUGHT_COST, 2)
        worth_it = 1.0 / (1 + C.CAUGHT_COST)
        self.assertGreater(worth_it, 0.3)
        for grade in C.GRADES[5:]:
            # The first grab past the safe line lands, on average, half
            # a step into the range, so this is the chance it brings her.
            step = grade.notice + grade.opening
            self.assertLess(step / (2.0 * grade.spread), worth_it, grade.name)


class TheGoldenOne(unittest.TestCase):
    """The temptation, and the two beats it costs to take it."""

    def setUp(self):
        self.setup, self.thief = alone(10, seed=11)
        self.grade = self.setup.grade

    def test_it_is_not_on_offer_until_he_is_near_the_quota(self):
        self.assertFalse(self.thief.gold_on_offer)
        run(self.setup, self.thief, [C.GRAB] * (self.grade.quota - C.GOLD_GAP))
        self.assertGreaterEqual(self.thief.gold_from, 0)
        self.assertGreaterEqual(self.thief.jar,
                                self.grade.quota - C.GOLD_GAP)

    def test_it_is_worth_its_cookies_and_none_come_from_the_jar(self):
        self.thief.gold_from, self.thief.beat = 0, 0
        jar, eaten = self.thief.jar, self.thief.eaten
        self.assertTrue(C.press(self.thief, C.LUNGE, self.setup))
        run(self.setup, self.thief, [C.WAIT] * C.GOLD_REACH)
        self.assertEqual(self.thief.eaten, eaten + self.grade.gold)
        self.assertEqual(self.thief.jar, jar)

    def test_he_can_neither_grab_nor_leave_while_he_is_reaching(self):
        """The whole cost of it, and the only lag left in the task."""
        self.thief.gold_from, self.thief.beat = 0, 0
        C.press(self.thief, C.LUNGE, self.setup)
        self.assertTrue(self.thief.committed)
        for _beat in range(C.GOLD_REACH):
            self.assertFalse(C.press(self.thief, C.GRAB, self.setup))
            self.assertFalse(C.press(self.thief, C.LEAVE, self.setup))
            self.assertFalse(self.thief.left)
            C.beat(self.thief, self.setup)
        self.assertFalse(self.thief.committed)
        self.assertTrue(C.press(self.thief, C.LEAVE, self.setup))

    def test_the_window_closes(self):
        self.thief.gold_from = 0
        self.thief.beat = C.GOLD_BEATS
        self.assertFalse(self.thief.gold_on_offer)


class TheGoldenOneIsATimingDecision(unittest.TestCase):
    """Not a trap and not free money, which took measuring to find out.

    Reaching for it is two beats he can neither grab nor leave in, and
    three grabs' worth of noise goes into the door across them — one for
    the press and one for each committed beat. So whether it is worth
    taking is entirely a question of whether the door can absorb that,
    and that is a sum a player can do off the screen.

    Taken on sight it raises the haul and throws away a third of the
    clean rounds doing it. Taken only when there is room it is the
    biggest single gain in the game and costs nothing at all. A table of
    hauls alone said it was free money, which is why the oracle's
    ``--gold`` prints clean rounds beside them now.
    """

    def run_it(self, level, player, deals=50):
        rng = random.Random(level)
        clean = 0
        total = 0
        for _deal in range(deals):
            thief, setup = O.play(level, seed=rng.randrange(1 << 30),
                                  player=player)
            clean += 1 if C.cleared(thief, setup) else 0
            total += C.haul(thief)
        return clean / float(deals), total / float(deals)

    def golden_rungs(self):
        return [level for level, grade in enumerate(C.GRADES, 1)
                if grade.gold]

    def test_there_are_some(self):
        """Or the rest of this class is checking nothing."""
        self.assertTrue(self.golden_rungs())

    def test_reaching_on_sight_costs_clean_rounds(self):
        for level in self.golden_rungs():
            name = C.GRADES[level - 1].name
            blind, _blind_haul = self.run_it(level, O.greedy)
            self.assertLess(blind, 0.85, '%s: %.0f%% clean' % (name,
                                                               100 * blind))

    def test_reaching_with_room_costs_nothing_and_is_worth_the_most(self):
        for level in self.golden_rungs():
            name = C.GRADES[level - 1].name
            timely, timely_haul = self.run_it(level, O.timely)
            _left, left_haul = self.run_it(level, O.careful)
            self.assertEqual(timely, 1.0, name)
            self.assertGreater(timely_haul, left_haul + 3, name)

    def test_the_rule_reads_only_what_is_drawn(self):
        """Or it would not be a rule a player could follow."""
        names = list(inspect.signature(O.room_for_the_reach).parameters)
        self.assertEqual(names, ['thief', 'grade'])


class TheCoachIsBlind(unittest.TestCase):
    """The one thing that could quietly gut the task.

    Coach mode pays per beat, and everything it reads has to be on the
    screen. Had it read the trigger or the deadline it would have been
    telling a learner when she was coming, and every number taken under
    it would have been about a schedule while claiming to be about
    self-control.
    """

    def test_what_the_screen_shows_cannot_reach_the_hidden_numbers(self):
        """Structural, not incidental: none of them takes a Setup."""
        for func in (C.door, C.floor_of, C.after_a_grab, C.certain, C.safe):
            names = list(inspect.signature(func).parameters)
            self.assertEqual(names, ['thief', 'grade'], func.__name__)
        self.assertNotIn('trigger', C.Thief.__slots__)
        self.assertNotIn('deadline', C.Thief.__slots__)

    def test_the_task_s_coach_reads_neither(self):
        from neural_workshop.ui.cookiethief import CookieThief
        source = inspect.getsource(CookieThief._coach_verdict)
        body = source.split('"""')[-1]
        for hidden in ('trigger', 'deadline', 'decoys'):
            self.assertNotIn(hidden, body)

    def test_two_rounds_that_differ_only_in_her_look_the_same(self):
        one = C.generate(7, seed=4)._replace(trigger=10 ** 6,
                                             deadline=10 ** 6, decoys=())
        other = one._replace(trigger=10 ** 5)
        boys = (C.Thief(), C.Thief())
        for _beat in range(6):
            for thief, setup in zip(boys, (one, other)):
                C.press(thief, C.GRAB, setup)
                C.beat(thief, setup)
        for thief in boys:
            self.assertEqual(thief.phase, C.AWAY)
        grade = one.grade
        self.assertEqual(
            [(b.jar, b.eaten, C.door(b, grade)) for b in boys[:1]],
            [(b.jar, b.eaten, C.door(b, grade)) for b in boys[1:]])


class EveryRungIsWinnableWithoutGambling(unittest.TestCase):
    """A thief who never takes a grab that could bring her clears them all.

    So a round that was lost was lost on a decision rather than on the
    deal. This is the same claim ``oracle_cookie.py`` prints, run small
    enough to belong in the suite.
    """

    def test_the_careful_thief_gets_away_with_it(self):
        for level in range(1, len(C.GRADES) + 1):
            rng = random.Random(level)
            for _deal in range(40):
                thief, setup = O.play(level, seed=rng.randrange(1 << 30),
                                      player=O.careful)
                self.assertTrue(C.cleared(thief, setup),
                                '%s: %d taken, %d seen'
                                % (setup.grade.name, thief.eaten,
                                   thief.caught))

    def test_he_does_it_well_inside_the_beats(self):
        for level in range(1, len(C.GRADES) + 1):
            thief, setup = O.play(level, seed=level, player=O.careful)
            self.assertLess(thief.beat, C.beats_of(setup.grade) * 0.8,
                            setup.grade.name)


class ReactionIsNotEnoughUpTop(unittest.TestCase):
    """Measured, and it is the claim the ladder is built on.

    A thief who takes every grab short of a certainty and leaves only
    once somebody is visibly in the doorway is the reactive half of the
    task on its own. Below the break he is *never* seen, because the
    warning is enough. Above it he is seen almost every round, because
    the grab that brings her is one she is already looking at.
    """

    def seen(self, level, deals=40):
        rng = random.Random(level)
        caught = 0
        for _deal in range(deals):
            thief, _setup = O.play(level, seed=rng.randrange(1 << 30),
                                   player=O.impulsive)
            caught += 1 if thief.caught else 0
        return caught / float(deals)

    def test_the_warning_is_what_saves_him_and_only_that(self):
        for level, grade in enumerate(C.GRADES, 1):
            got = self.seen(level)
            if grade.reactive:
                self.assertEqual(got, 0.0, '%s: seen %.0f%%'
                                           % (grade.name, 100 * got))
            else:
                self.assertGreater(got, 0.8, '%s: seen %.0f%%'
                                             % (grade.name, 100 * got))


class GreedIsPricedOnlyWhereThereIsNoWarning(unittest.TestCase):
    """What pushing into the shaded range costs, measured.

    Below the break it costs nothing at all — you see her coming and
    leave, so the range is free to walk into. Above it every step in is
    paid for, and the haul turns over: a little way in is worth more
    than stopping at the line, and the whole way in is worth a fraction
    of it.
    """

    def carry(self, level, over, deals=40):
        rng = random.Random(level * 100 + over)
        caught = 0
        total = 0
        for _deal in range(deals):
            thief, _setup = O.play(level, seed=rng.randrange(1 << 30),
                                   player=O.bold(over))
            caught += 1 if thief.caught else 0
            total += C.haul(thief)
        return caught / float(deals), total / float(deals)

    def test_below_the_break_the_range_is_free(self):
        for level, grade in enumerate(C.GRADES, 1):
            if not grade.reactive:
                continue
            caught, _got = self.carry(level, grade.spread)
            self.assertEqual(caught, 0.0, grade.name)

    def test_above_it_the_whole_way_in_loses_every_round(self):
        for level, grade in enumerate(C.GRADES, 1):
            if grade.reactive:
                continue
            caught, deep = self.carry(level, grade.spread)
            _safe_caught, edge = self.carry(level, 0)
            self.assertGreater(caught, 0.8, grade.name)
            self.assertLess(deep, edge, grade.name)


class TheHubHasSomewhereToPutIt(unittest.TestCase):
    """A category of its own, and the reason it is not filed under attention.

    Everything under attention is about finding or following the right
    thing. This is about *not* pressing a key you are already pressing
    and would rather keep pressing, which is a different faculty and
    fails for different reasons.
    """

    def test_self_control_is_a_category_and_holds_it(self):
        from neural_workshop.ui.taskhub import CATEGORIES, TASKS
        self.assertIn('self_control', [cat for cat, _name in CATEGORIES])
        self.assertEqual([task for task, _name in TASKS['self_control']],
                         ['cookie_thief'])

    def test_it_has_an_options_screen(self):
        from neural_workshop.ui import taskoptions
        self.assertTrue(taskoptions.has_options('cookie_thief'))

    def test_the_note_says_what_the_rung_does(self):
        from neural_workshop.ui import taskoptions
        for level in range(1, len(C.GRADES) + 1):
            said = taskoptions.cookie_note({'COOKIE_LEVEL': level})
            self.assertIn('%d' % C.GRADES[level - 1].quota, said)
            self.assertIn('Guessing', said)


@needs_ui
class TheHandAnswersTheKeyAtOnce(unittest.TestCase):
    """The thing a person notices in the first two seconds.

    A press used to change nothing on screen until the next beat came
    round, and what it changed then was a bar that took several beats to
    catch up. Now the arm is in the jar on the frame the key was pressed
    and out of it on the next one, and there is nothing else to wait
    for.
    """

    def setUp(self):
        close_overlays()
        self.env = catalog.env_class('cookie_thief')(seed=0, rung=10,
                                                     trials=2)
        self.env.reset(0)
        self.task = self.env.task

    def tearDown(self):
        self.env.close()
        close_overlays()
        reset_window()

    def running(self):
        for _step in range(20):
            self.env.step(C.WAIT)
            if self.task.phase == 'running':
                return
        self.fail('the round never opened')

    def test_the_hand_goes_in_on_the_frame_the_key_was_pressed(self):
        self.running()
        self.assertFalse(self.task.grabbing)
        self.task.act(C.GRAB)
        self.assertTrue(self.task.grabbing)
        self.assertEqual(self.task.thief.jar, 1)

    def test_and_is_back_out_a_beat_later(self):
        self.running()
        self.task.act(C.GRAB)
        self.env.step(C.WAIT)
        self.env.step(C.WAIT)
        self.assertFalse(self.task.grabbing)

    def test_a_press_that_does_nothing_does_not_move_it(self):
        self.running()
        self.task.act(C.LUNGE)          # no golden one on offer yet
        self.assertFalse(self.task.grabbing)


@needs_ui
class TheRunReportsBothScores(unittest.TestCase):
    """The bar and the margin, out of the task rather than the model."""

    def setUp(self):
        close_overlays()

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_a_run_totals_the_haul(self):
        env = catalog.env_class('cookie_thief')(seed=0, rung=6, trials=3,
                                                adaptive=False)
        env.reset(0)
        task = env.task
        try:
            for _step in range(4000):
                port = C.WAIT
                if task.phase == 'running' and task.thief is not None:
                    port = O.careful(task.thief, task.setup)
                _obs, _ev, done = env.step(port)
                if done or task.phase == 'done':
                    break
            tally = task.score()
            self.assertEqual(tally['rounds'], 3)
            self.assertEqual(tally['clean'], 3)
            self.assertEqual(tally['points'], tally['cookies'])
            self.assertGreaterEqual(tally['points'], 3 * C.GRADES[5].quota)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
