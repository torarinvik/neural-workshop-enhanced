#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Morning Round: the ladder, the rules, the ride, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from handsupport import heard
from spatialsupport import drive, queued

from neural_workshop import morninground as M

RUNGS = (1, 3, 5, 7, 10, 12, 16, 25)


def shortcut_wins(street):
    draw = random.Random(1)
    rand = (lambda run: [draw.randrange(M.PORTS)]
            if draw.random() < 0.3 else [])
    out = {'every house': M.play(street, M.every_house)[0],
           'no house': M.play(street, lambda run: [])[0],
           'random': M.play(street, rand)[0]}
    if street.level.mode in ('sign', 'hidden'):
        out['first rule'] = M.play(street, M.stubborn)[0]
    return [name for name, won in out.items() if won]


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_the_shortcuts_fail(self):
        for r in RUNGS:
            for seed in range(2):
                s = M.deal(r, seed=seed)
                self.assertTrue(M.play(s)[0], (r, seed))
                self.assertEqual(shortcut_wins(s), [], (r, seed))

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 2, 4, 5, 7, 9, 10, 11, 12, 40)}
        self.assertEqual([g[r].mode for r in (1, 2, 4, 5, 7)],
                         ['marked', 'told', 'told', 'sign', 'hidden'])
        self.assertEqual((g[2].atoms, g[4].atoms), (1, 2))
        self.assertEqual((g[5].deck, g[9].deck), (2, 3))
        self.assertIn('even', g[9].pool)
        self.assertNotIn('even', g[7].pool)
        self.assertTrue(g[10].state and not g[9].state)
        self.assertTrue(g[11].memorise and not g[10].memorise)
        self.assertIn('church', g[12].pool)
        self.assertGreater(g[40].speed, g[12].speed)
        self.assertLess(g[40].brief, g[12].brief)

    def test_the_first_rung_is_gentle(self):
        one = M.grade(1)
        self.assertEqual((one.mode, one.blocks, one.clutter), ('marked', 1,
                                                               0.0))
        self.assertGreaterEqual(one.slack, 2)
        self.assertLessEqual(one.speed, 100.0)
        s = M.deal(1, seed=3)
        self.assertTrue(all(h.sign == w for h, w in zip(s.houses, s.want)))

    def test_far_rungs_still_deal(self):
        self.assertTrue(M.play(M.deal(60, seed=1))[0])


class TheRules(unittest.TestCase):

    def test_words_for_every_kind_of_part(self):
        rule = ('and', ('not', ('atom', 'dog')),
                ('or', ('opp', ('atom', 'blue')), ('alt', ('same',))))
        self.assertEqual(M.say(rule), 'no dog and (across from: blue door or '
                                      'every 2nd: door as the last on its '
                                      'side)')
        self.assertEqual(M.size(rule), 3)

    def test_across_every_second_and_same_door(self):
        s = M.deal(3, seed=1)
        hs = s.houses
        blue = M.truth(('atom', 'blue'), hs, s.landmarks)
        opp = M.truth(('opp', ('atom', 'blue')), hs, s.landmarks)
        at = {(h.side, h.k): h.i for h in hs}
        for h in hs:
            self.assertEqual(opp[h.i], blue[at[(-h.side, h.k)]])
        alt = M.truth(('alt', ('atom', 'blue')), hs, s.landmarks)
        blues = [h.i for h in hs if blue[h.i]]
        self.assertEqual([alt[i] for i in blues],
                         [k % 2 == 0 for k in range(len(blues))])
        same = M.truth(('same',), hs, s.landmarks)
        left = [h for h in hs if h.side < 0]
        for a, b in zip(left, left[1:]):
            self.assertEqual(same[b.i], a.door == b.door)

    def test_every_part_of_every_rule_matters(self):
        for r in (4, 12, 25):
            s = M.deal(r, seed=2)
            for rule in s.deck:
                self.assertTrue(M.meaningful(rule, s.houses, s.landmarks))

    def test_rules_tell_themselves_apart_in_every_block(self):
        s = M.deal(12, seed=4)
        vs = [M.truth(r, s.houses, s.landmarks) for r in s.deck]
        for b in range(len(s.blocks)):
            here = [h.i for h in s.houses if h.block == b]
            for a in range(len(vs)):
                for c in range(a + 1, len(vs)):
                    self.assertGreaterEqual(
                        sum(vs[a][i] != vs[c][i] for i in here), 2)


class TheRide(unittest.TestCase):

    def ride_to(self, run, d):
        while run.s < d and run.result is None:
            run.step(1 / 60.0)

    def test_a_paper_lands_where_the_bicycle_has_got_to(self):
        s = M.deal(1, seed=1)._replace(things=())
        run = M.Run(s)
        h = s.houses[0]
        tf = M.flight(run, h.side)
        self.ride_to(run, h.d - run.v * tf)
        run.throw(h.side)
        for _k in range(60):
            run.step(1 / 60.0)
        self.assertIn(h.i, run.got)
        self.assertEqual(run.got[h.i], 'ok' if s.want[h.i] else 'wrong')

    def test_a_subscriber_passed_complains_and_a_wrong_one_shouts(self):
        s = M.deal(1, seed=1)._replace(things=())
        run = M.Run(s)
        sub = next(h for h in s.houses if s.want[h.i])
        self.ride_to(run, sub.d + M.HOUSE_LEN + 1)
        self.assertEqual(run.got[sub.i], 'missed')
        self.assertTrue(any(n.voice == M.HORN for n in run.notes))
        self.assertEqual(run.mistakes, 1)

    def test_a_cone_knocks_the_rider_down(self):
        s = M.deal(1, seed=1)
        s = s._replace(things=(M.Thing(600.0, 600.0, 12.0, 'cone', 0.0),))
        run = M.Run(s)
        while run.falls == 0 and run.s < 700:
            run.step(1 / 60.0)
        self.assertEqual(run.falls, 1)
        here = run.s
        run.step(0.5)
        self.assertEqual(run.s, here)            # still on the ground

    def test_papers_run_out(self):
        s = M.deal(1, seed=1)._replace(papers=1)
        run = M.Run(s)
        self.ride_to(run, 10.0)
        run.throw(-1)
        run.t += 1.0
        run.throw(1)
        self.assertEqual((run.papers, len(run.flying)), (0, 1))

    def test_the_hidden_reference_believes_only_what_it_heard(self):
        s = M.deal(9, seed=2)
        run = M.Run(s)
        self.assertEqual(M.believed(run, 0), {s.active[0]: 1.0})
        later = M.believed(run, 1)
        self.assertEqual(set(later), set(range(len(s.deck))))


class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('morning_round', 2, pilot, seed=1,
                               steps=6000), [1.0])
        self.assertEqual(drive('morning_round', 1, lambda t: None, seed=1,
                               steps=6000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('morning_round', M, rung=2, steps=1500), 0)


if __name__ == '__main__':
    unittest.main()
