#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Cookie Thief's model: the momentum, the doorway, and the three promises.

Nothing here draws anything. What is being checked is the part the
screen only reports:

* that the ladder is a ladder — that each rung adds one thing, that
  reaction stops being enough exactly once and never starts again, and
  that random presses are worth less the higher you go;

* that every rung is winnable, by a thief who can count, well inside
  its beats — so a round that was lost was lost on the stop and not on
  the arithmetic;

* that coach mode is **blind to both hidden things**. It reads the jar,
  the pips, the boy's speed and the doorway, and it cannot read the
  trigger or the deadline. Those two are the whole of what the task
  hides, and a coach that knew them would have answered the only
  question it asks.

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


def dealt(level, seed=0):
    """A setup and a fresh thief, the way a round starts."""
    return C.generate(level, seed=seed), C.Thief()


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
        self.assertEqual(first.stopping, 1)
        self.assertTrue(first.reactive)
        self.assertEqual(first.gold, 0)
        self.assertEqual(first.decoys, 0)

    def test_the_quota_never_falls(self):
        quotas = [grade.quota for grade in C.GRADES]
        self.assertEqual(quotas, sorted(quotas), quotas)

    def test_stopping_never_gets_easier(self):
        stops = [grade.stopping for grade in C.GRADES]
        self.assertEqual(stops, sorted(stops), stops)

    def test_each_rung_adds_something(self):
        for below, above in zip(C.GRADES, C.GRADES[1:]):
            harder = (
                above.quota > below.quota
                or above.stopping > below.stopping
                or above.warn < below.warn
                or above.reflex_bites > below.reflex_bites
                or above.spread < below.spread
                or above.gold > below.gold
                or above.decoys > below.decoys)
            self.assertTrue(harder, '%s adds nothing to %s'
                                    % (above.name, below.name))

    def test_reaction_stops_being_enough_once_and_stays_that_way(self):
        """The break in the ladder, and there is meant to be exactly one.

        Below it a thief can play by watching the doorway. Above it he
        cannot, ever again — a rung that handed reaction back would be
        a rung on which everything learned above it was optional.
        """
        reactive = [grade.reactive for grade in C.GRADES]
        self.assertTrue(reactive[0])
        self.assertFalse(reactive[-1])
        self.assertEqual(reactive, sorted(reactive, reverse=True), reactive)

    def test_what_reaction_alone_leaves_him_holding_never_falls(self):
        bites = [grade.reflex_bites for grade in C.GRADES]
        self.assertEqual(bites, sorted(bites), bites)

    def test_the_band_is_always_above_the_quota(self):
        """Stop on the number you were asked for and the count is safe.

        Which is what makes a perfect stop a perfect round: the trigger
        can only ever punish momentum, never the quota itself.
        """
        for level in range(1, len(C.GRADES) + 1):
            grade = C.GRADES[level - 1]
            for seed in range(30):
                setup = C.generate(level, seed=seed)
                self.assertGreater(setup.trigger, grade.quota)
                self.assertLessEqual(setup.trigger,
                                     grade.quota + grade.spread)

    def test_the_extras_arrive_at_the_top(self):
        for grade in C.GRADES[:7]:
            self.assertEqual(grade.gold, 0, grade.name)
            self.assertEqual(grade.decoys, 0, grade.name)
        self.assertTrue(C.GRADES[-1].gold)
        self.assertTrue(C.GRADES[-1].decoys)

    def test_guessing_is_worth_less_the_higher_you_go(self):
        """Measured, because there is nothing here to derive.

        What a run of random presses scores is whatever a random walk in
        speed happens to eat before somebody walks in, and that is a
        simulation question.

        Measured is also why this is not asserted rung by rung. Four
        hundred deals at a floor near a twentieth carry about a point of
        standard error, and the middle of the ladder really is flat —
        3.5% against 5.5% at one point, which is a tie read as an
        ordering. So what is checked is the shape: the floor falls by a
        long way across the ladder, and no rung sits above the best of
        the ones below it by more than the noise in the measurement.
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


class ThePhysics(unittest.TestCase):
    """Speed, and the three ways a beat can change it."""

    def setUp(self):
        self.setup, self.thief = dealt(6, seed=1)
        self.grade = self.setup.grade

    def test_reaching_speeds_him_up_and_stops_at_one(self):
        for _press in range(20):
            C.press(self.thief, C.REACH, self.setup)
        self.assertEqual(self.thief.speed, 1.0)

    def test_freezing_slows_him_down_and_stops_at_nothing(self):
        self.thief.speed = 0.5
        C.press(self.thief, C.FREEZE, self.setup)
        self.assertAlmostEqual(self.thief.speed, 0.5 - self.grade.brake)
        for _press in range(20):
            C.press(self.thief, C.FREEZE, self.setup)
        self.assertEqual(self.thief.speed, 0.0)

    def test_waiting_is_not_freezing(self):
        """Or there would be no way to hold a speed, only two ways to lose one."""
        one, other = C.Thief(), C.Thief()
        one.speed = other.speed = 0.8
        C.press(one, C.WAIT, self.setup)
        C.press(other, C.FREEZE, self.setup)
        self.assertEqual(one.speed, 0.8)
        self.assertLess(other.speed, one.speed)

    def test_every_beat_costs_drag_whatever_was_pressed(self):
        self.thief.speed = 0.8
        C.press(self.thief, C.WAIT, self.setup)
        C.beat(self.thief, self.setup)
        self.assertAlmostEqual(self.thief.speed, 0.8 - self.grade.drag)

    def test_at_most_one_cookie_a_beat(self):
        self.thief.speed = 1.0
        for _beat in range(6):
            self.thief.speed = 1.0
            self.assertLessEqual(C.beat(self.thief, self.setup), 1)

    def test_stopping_bites_agrees_with_actually_stopping(self):
        """The number the screen shows has to be the number he gets.

        Both are simulations of the same loop, which is the point: a
        closed form would agree with the physics only until one of them
        was edited.
        """
        for level in (3, 6, 10):
            grade = C.GRADES[level - 1]
            for speed in (0.2, 0.5, 0.75, 1.0):
                for crumbs in (0.0, 0.4, 0.9):
                    setup = C.generate(level, seed=7)
                    # A round with nobody in it, so only the eating runs.
                    setup = setup._replace(trigger=999, deadline=999,
                                           decoys=())
                    thief = C.Thief()
                    thief.speed, thief.crumbs = speed, crumbs
                    said = C.stopping_bites(speed, crumbs, grade)
                    while thief.moving:
                        C.press(thief, C.FREEZE, setup)
                        C.beat(thief, setup)
                    self.assertEqual(thief.jar, said,
                                     '%s %s %s' % (grade.name, speed, crumbs))


class TheDoorway(unittest.TestCase):
    """Who arrives, when, and how long there is before it matters."""

    def test_the_count_brings_her(self):
        setup, thief = dealt(6, seed=3)
        setup = setup._replace(deadline=999, decoys=())
        run(setup, thief, [C.REACH] * 60)
        self.assertGreaterEqual(thief.jar, setup.trigger)
        self.assertIsNotNone(thief.who)

    def test_the_deadline_brings_her_even_if_he_took_nothing(self):
        setup, thief = dealt(6, seed=3)
        setup = setup._replace(deadline=5, decoys=())
        run(setup, thief, [C.WAIT] * 40)
        self.assertEqual(thief.jar, 0)
        self.assertEqual(thief.who, C.MOTHER)

    def test_the_warning_is_the_rung_s_warning(self):
        setup, thief = dealt(4, seed=3)
        setup = setup._replace(deadline=3, decoys=())
        for _beat in range(3):
            C.beat(thief, setup)
        self.assertEqual(thief.phase, C.COMING)
        came = thief.beat
        while thief.phase == C.COMING:
            C.beat(thief, setup)
        self.assertEqual(thief.beat - came, setup.grade.warn)
        self.assertEqual(thief.phase, C.WATCHING)

    def test_a_decoy_goes_away_again(self):
        setup, thief = dealt(9, seed=3)
        setup = setup._replace(deadline=999, decoys=((4, C.DOG),))
        run(setup, thief, [C.WAIT] * 30)
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

    def test_standing_still_ends_it(self):
        setup, thief = dealt(2, seed=5)
        setup = setup._replace(deadline=999, decoys=())
        run(setup, thief, [C.REACH] * 3 + [C.FREEZE] * 20)
        self.assertTrue(C.over(thief, setup))
        self.assertLess(thief.beat, setup.grade.beats)

    def test_it_does_not_end_before_he_has_started(self):
        """Or a round would be over before anybody had a chance at it."""
        setup, thief = dealt(2, seed=5)
        setup = setup._replace(deadline=999, decoys=())
        run(setup, thief, [C.WAIT] * 10)
        self.assertEqual(thief.jar, 0)
        self.assertFalse(C.over(thief, setup))

    def test_a_cookie_under_her_eye_is_caught(self):
        setup, thief = dealt(7, seed=5)
        setup = setup._replace(deadline=1, decoys=())
        run(setup, thief, [C.REACH] * 20)
        self.assertGreater(thief.caught, 0)
        self.assertFalse(C.cleared(thief, setup))

    def test_stopping_short_is_a_loss_as_well(self):
        """Or never stealing anything would be a winning policy."""
        setup, thief = dealt(6, seed=5)
        setup = setup._replace(deadline=999, decoys=())
        run(setup, thief, [C.REACH] * 2 + [C.FREEZE] * 20)
        self.assertLess(thief.eaten, setup.grade.quota)
        self.assertEqual(thief.caught, 0)
        self.assertFalse(C.cleared(thief, setup))

    def test_a_round_always_ends(self):
        for level in range(1, len(C.GRADES) + 1):
            for seed in range(10):
                setup, thief = dealt(level, seed=seed)
                run(setup, thief, [C.REACH] * (setup.grade.beats + 5))
                self.assertTrue(C.over(thief, setup),
                                '%s seed %d' % (setup.grade.name, seed))


class TheGoldenOne(unittest.TestCase):
    """The temptation, and the two beats it costs to take it."""

    def setUp(self):
        self.setup, self.thief = dealt(10, seed=11)
        self.setup = self.setup._replace(trigger=999, deadline=999, decoys=())
        self.grade = self.setup.grade

    def test_it_is_not_on_offer_until_he_is_near_the_quota(self):
        self.assertFalse(self.thief.gold_on_offer)
        run(self.setup, self.thief, [C.REACH] * 40)
        self.assertGreaterEqual(self.thief.gold_from, 0)
        self.assertGreaterEqual(self.thief.jar, self.grade.quota - C.GOLD_GAP)

    def test_lunging_at_nothing_does_nothing(self):
        self.assertFalse(C.press(self.thief, C.LUNGE, self.setup))
        self.assertEqual(self.thief.eaten, 0)
        self.assertEqual(self.thief.locked, 0)

    def test_it_is_worth_its_cookies_and_none_of_them_come_from_the_jar(self):
        self.thief.gold_from, self.thief.beat = 0, 0
        jar, eaten = self.thief.jar, self.thief.eaten
        self.assertTrue(C.press(self.thief, C.LUNGE, self.setup))
        self.assertEqual(self.thief.eaten, eaten + self.grade.gold)
        self.assertEqual(self.thief.jar, jar)

    def test_it_takes_the_brake_away_for_two_beats(self):
        self.thief.gold_from, self.thief.beat = 0, 0
        self.thief.speed = 1.0
        C.press(self.thief, C.LUNGE, self.setup)
        self.assertEqual(self.thief.locked, C.GOLD_LOCK)
        for _beat in range(C.GOLD_LOCK):
            self.assertFalse(C.press(self.thief, C.FREEZE, self.setup))
            self.assertEqual(self.thief.speed, 1.0)
            C.beat(self.thief, self.setup)
            self.thief.speed = 1.0
        self.assertTrue(C.press(self.thief, C.FREEZE, self.setup))

    def test_the_window_closes(self):
        self.thief.gold_from = 0
        self.thief.beat = C.GOLD_BEATS
        self.assertFalse(self.thief.gold_on_offer)


class TheCoachIsBlind(unittest.TestCase):
    """The one thing that could quietly gut the task.

    Coach mode pays per beat, and everything it reads has to be on the
    screen. Had it read the trigger or the deadline it would have been
    telling a learner when she was coming, and every number taken under
    it would have been about a schedule while claiming to be about
    self-control.
    """

    def test_what_the_screen_shows_cannot_reach_the_hidden_numbers(self):
        """Structural, not incidental: neither takes a Setup at all."""
        for func in (C.landing, C.jar_landing):
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

    def test_the_same_boy_is_told_the_same_thing_whenever_she_is_coming(self):
        """Two rounds that differ only in when she comes look identical
        to the coach until she actually turns up."""
        one = C.generate(6, seed=4)._replace(trigger=9, deadline=999,
                                             decoys=())
        other = one._replace(trigger=99)
        boys = (C.Thief(), C.Thief())
        for _beat in range(6):
            for thief, setup in zip(boys, (one, other)):
                C.press(thief, C.REACH, setup)
                C.beat(thief, setup)
        for thief in boys:
            self.assertEqual(thief.phase, C.AWAY)
        self.assertEqual(
            [(boy.jar, boy.eaten, round(boy.speed, 6)) for boy in boys[:1]],
            [(boy.jar, boy.eaten, round(boy.speed, 6)) for boy in boys[1:]])


class EveryRungIsWinnable(unittest.TestCase):
    """A thief who can count clears every rung, every time.

    So a round that was lost was lost on the stop rather than on the
    ladder being impossible. This is the same claim ``oracle_cookie.py``
    prints, run small enough to belong in the suite.
    """

    def test_the_counting_thief_gets_away_with_it(self):
        for level in range(1, len(C.GRADES) + 1):
            rng = random.Random(level)
            for _deal in range(40):
                thief, setup = O.play(level, seed=rng.randrange(1 << 30),
                                      player=O.steady)
                self.assertTrue(C.cleared(thief, setup),
                                '%s: %d eaten, %d caught'
                                % (setup.grade.name, thief.eaten,
                                   thief.caught))

    def test_he_does_it_well_inside_the_beats(self):
        for level in range(1, len(C.GRADES) + 1):
            thief, setup = O.play(level, seed=level, player=O.steady)
            self.assertLess(thief.beat, setup.grade.beats * 0.8,
                            setup.grade.name)


class ReactionIsNotEnoughUpTop(unittest.TestCase):
    """Measured, and it is the claim the ladder is built on.

    A thief who eats flat out and brakes the instant she appears is the
    reactive half of the task on its own. He clears the rungs whose
    warning is longer than what his momentum still owes, and he cannot
    clear one of the others however quick he is.
    """

    def clean(self, level, deals=40):
        rng = random.Random(level)
        won = 0
        for _deal in range(deals):
            thief, setup = O.play(level, seed=rng.randrange(1 << 30),
                                  player=O.impulsive)
            won += 1 if C.cleared(thief, setup) else 0
        return won / float(deals)

    def test_he_clears_the_rungs_the_ladder_says_he_can(self):
        for level, grade in enumerate(C.GRADES, 1):
            got = self.clean(level)
            if grade.reactive:
                self.assertGreater(got, 0.9, '%s: %.0f%%'
                                             % (grade.name, 100 * got))
            else:
                self.assertLess(got, 0.1, '%s: %.0f%%'
                                          % (grade.name, 100 * got))


class TheHubHasSomewhereToPutIt(unittest.TestCase):
    """A category of its own, and the reason it is not filed under attention.

    Everything under attention is about finding or following the right
    thing. This is about *not* doing a thing you are already doing and
    would rather keep doing, which is a different faculty and fails for
    different reasons — Reflex would lose every rung above the fifth by
    being fast.
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
