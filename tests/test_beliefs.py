#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Who Knows What?: the belief tracker, the stories, the boundary, the
screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import draws, drive, right, wrong
from uisupport import needs_ui

from neural_workshop import beliefs as B
from neural_workshop.beliefs import Event

ANN, BEN, CLEO = 0, 1, 2
BALL = 0
BASKET, BOX, DRAWER = 0, 1, 2


def told(people, things, *events):
    return B.tell(people, things, events)


class TheTracker(unittest.TestCase):

    def test_sally_anne(self):
        t = told(2, 1, Event('put', ANN, thing=BALL, where=BASKET),
                 Event('leave', ANN),
                 Event('move', BEN, thing=BALL, where=BOX),
                 Event('enter', ANN))
        self.assertEqual(t.truth[BALL], BOX)
        self.assertEqual(t.belief[ANN][BALL], BASKET)
        self.assertEqual(t.belief[BEN][BALL], BOX)
        # Ben saw Ann go out, so knows she thinks it is in the basket;
        # Ann does not know it moved, so thinks Ben thinks the basket.
        self.assertEqual(t.second[BEN][ANN][BALL], BASKET)
        self.assertEqual(t.second[ANN][BEN][BALL], BASKET)

    def test_second_order_needs_both_to_have_seen(self):
        t = told(3, 1, Event('put', ANN, thing=BALL, where=BASKET),
                 Event('leave', BEN),
                 Event('move', CLEO, thing=BALL, where=BOX),
                 Event('leave', CLEO),
                 Event('move', ANN, thing=BALL, where=DRAWER))
        self.assertEqual(t.belief[CLEO][BALL], BOX)
        self.assertEqual(t.second[ANN][CLEO][BALL], BOX)
        self.assertEqual(t.second[ANN][BEN][BALL], BASKET)
        self.assertEqual(t.second[CLEO][ANN][BALL], BOX)

    def test_a_call_passes_a_belief_and_a_lie_passes_a_falsehood(self):
        t = told(2, 1, Event('put', ANN, thing=BALL, where=BASKET),
                 Event('leave', BEN),
                 Event('move', ANN, thing=BALL, where=BOX),
                 Event('call', ANN, BEN, BALL, BOX))
        self.assertEqual(t.belief[BEN][BALL], BOX)
        self.assertEqual(t.second[ANN][BEN][BALL], BOX)
        t = told(2, 1, Event('put', ANN, thing=BALL, where=BASKET),
                 Event('leave', BEN),
                 Event('move', ANN, thing=BALL, where=BOX),
                 Event('lie', ANN, BEN, BALL, DRAWER))
        self.assertEqual(t.belief[BEN][BALL], DRAWER)
        self.assertEqual(t.truth[BALL], BOX)
        self.assertEqual(t.second[BEN][ANN][BALL], DRAWER)

    def test_coming_back_shows_nothing_and_a_peek_does(self):
        events = [Event('put', ANN, thing=BALL, where=BASKET),
                  Event('leave', BEN),
                  Event('move', ANN, thing=BALL, where=BOX),
                  Event('enter', BEN)]
        t = told(2, 1, *events)
        self.assertEqual(t.belief[BEN][BALL], BASKET)
        t = told(2, 1, *events + [Event('peek', BEN, thing=BALL,
                                        where=BOX)])
        self.assertEqual(t.belief[BEN][BALL], BOX)
        self.assertEqual(t.second[ANN][BEN][BALL], BOX)

    def test_an_empty_peek_where_one_believed_leaves_one_unsure(self):
        t = told(2, 1, Event('put', ANN, thing=BALL, where=BASKET),
                 Event('leave', BEN),
                 Event('move', ANN, thing=BALL, where=BOX),
                 Event('enter', BEN),
                 Event('peek', BEN, thing=BALL, where=BASKET))
        self.assertIsNone(t.belief[BEN].get(BALL))


class TheStories(unittest.TestCase):

    def test_every_answer_is_the_tracker_s(self):
        for rung in (1, 4, 7, 10, 14, 18, 23, 29):
            for seed in range(30):
                s = B.deal(rung, seed=seed)
                t = B.tell(len(s.people), len(s.things), s.events)
                kind, a, b, thing = s.asked
                want = {'truth': t.truth[thing],
                        'first': t.belief[a].get(thing),
                        'second': t.second[a][b].get(thing)
                        if b >= 0 else None}[kind]
                self.assertEqual(s.answer, want, (rung, seed))

    def test_most_answers_are_not_where_the_thing_is(self):
        false = 0
        for seed in range(200):
            s = B.deal(12, seed=seed)
            t = B.tell(len(s.people), len(s.things), s.events)
            false += s.answer != t.truth[s.asked[3]]
        self.assertGreater(false, 110)
        self.assertLess(false, 170)

    def test_the_ladder_brings_in_its_events(self):
        seen = {}
        for rung in (12, 15, 19, 23):
            kinds = set()
            for seed in range(40):
                kinds |= {e.kind for e in B.deal(rung, seed=seed).events}
            seen[rung] = kinds
        self.assertNotIn('call', seen[12])
        self.assertIn('call', seen[15])
        self.assertNotIn('lie', seen[15])
        self.assertIn('lie', seen[19])
        self.assertIn('peek', seen[23])

    def test_second_order_questions_from_rung_nine(self):
        kinds = {B.deal(8, seed=s).asked[0] for s in range(40)}
        self.assertNotIn('second', kinds)
        kinds = {B.deal(10, seed=s).asked[0] for s in range(40)}
        self.assertIn('second', kinds)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 14):
            self.assertEqual(drive('who_knows_what', rung, right), [1.0])
            self.assertEqual(drive('who_knows_what', rung, wrong), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def test_every_rung_draws(self):
        from neural_workshop.ui.beliefs import WhoKnowsWhat
        draws(self, WhoKnowsWhat, (1, 5, 10, 18, 26))


if __name__ == '__main__':
    unittest.main()
