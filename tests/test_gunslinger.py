#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gunslinger: the wait, the draw, the shot, the notice, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import gunslinger as M
from neural_workshop import hand as H


def duel_with(rung, want, seeds=300):
    for s in range(seeds):
        duel = M.deal(rung, seed=s)
        if want(duel):
            return duel
    raise AssertionError('no such duel')


def until_he_draws(run):
    while not run.drawn():
        run.step(1 / 60.0)
    return run


def unholster(run):
    run.hand.to(*M.HOLSTER)
    run.press()
    run.hand.to(M.HOLSTER[0], M.HOLSTER[1] + M.PULL + 5)
    run.step(1 / 60.0)
    run.release()


def shoot_at(run, x, y):
    sx, sy = run.sway()
    run.hand.to(x - sx, y - sy)
    run.press()
    run.release()


class TheLadder(unittest.TestCase):

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 40, 80)}
        self.assertTrue(g[1].word and not g[4].word)
        self.assertTrue(g[4].cock and not g[1].cock)
        self.assertEqual((g[1].men, g[7].men, g[10].men), (1, 2, 3))
        self.assertTrue(g[7].feints and g[7].sway and not g[4].feints)
        self.assertTrue(g[10].hat and g[10].others and not g[7].hat)
        self.assertTrue(g[13].pace and g[13].beside)
        self.assertTrue(g[16].dust and not g[13].dust)
        self.assertLess(g[40].quick, g[16].quick)
        self.assertEqual(g[80].quick, 0.75)

    def test_the_notice_names_the_man_it_means(self):
        for rung in (7, 10, 13, 20):
            for s in range(10):
                duel = M.deal(rung, seed=s)
                men, foe = duel.men, duel.foe
                if 'wears the' in duel.notice:
                    self.assertIn(M.HATS[men[foe].hat], duel.notice)
                elif 'to the left of' in duel.notice:
                    self.assertIn(M.HATS[men[foe + 1].hat], duel.notice)
                    self.assertLess(men[foe].x, men[foe + 1].x)
                else:
                    self.assertIn(M.HATS[men[foe - 1].hat], duel.notice)
                self.assertEqual('hat off' in duel.notice,
                                 duel.part == 'hat')
                self.assertEqual(len({m.hat for m in men}), len(men))

    def test_the_reference_passes_and_idle_and_random_fail(self):
        for rung in (1, 4, 7, 10, 13, 16, 22, 35, 70):
            for s in range(3):
                duel = M.deal(rung, seed=s)
                self.assertTrue(M.play(duel)[0], (rung, s))
                self.assertFalse(M.play(duel, lambda run: [])[0])
                draw = random.Random(s)
                self.assertFalse(M.play(duel, lambda run: [
                    draw.randrange(M.PORTS)])[0])


class TheDuel(unittest.TestCase):

    def test_touching_the_gun_before_he_draws_loses(self):
        run = M.Run(M.deal(1, seed=1))
        run.step(1 / 60.0)
        run.hand.to(*M.HOLSTER)
        run.press()
        self.assertEqual(run.result, (False, 'You drew first'))

    def test_hovering_by_the_holster_is_allowed(self):
        run = M.Run(M.deal(1, seed=1))
        run.hand.to(*M.HOLSTER)
        for _k in range(30):
            run.step(1 / 60.0)
        self.assertIsNone(run.result)

    def test_too_slow_and_he_shoots(self):
        duel = M.deal(1, seed=1)
        run = M.Run(duel)
        while run.result is None:
            run.step(1 / 60.0)
        self.assertEqual(run.result[0], False)
        self.assertAlmostEqual(run.t, duel.draw_at + duel.level.quick,
                               delta=0.05)

    def test_draw_then_shoot_him_wins(self):
        run = until_he_draws(M.Run(M.deal(1, seed=1)))
        self.assertEqual(run.gun, 'holster')
        unholster(run)
        self.assertEqual(run.gun, 'hand')
        shoot_at(run, *run.target())
        self.assertEqual(run.result[0], True)

    def test_a_short_pull_leaves_the_gun_in_the_holster(self):
        run = until_he_draws(M.Run(M.deal(1, seed=1)))
        run.hand.to(*M.HOLSTER)
        run.press()
        run.hand.to(M.HOLSTER[0], M.HOLSTER[1] + 40)
        run.step(1 / 60.0)
        run.release()
        self.assertEqual(run.gun, 'holster')
        self.assertIsNone(run.result)

    def test_a_miss_costs_a_round_and_the_duel_goes_on(self):
        run = until_he_draws(M.Run(M.deal(1, seed=1)))
        unholster(run)
        shoot_at(run, 60.0, 560.0)
        self.assertIsNone(run.result)
        self.assertEqual(run.bullets, M.BULLETS - 1)

    def test_the_hammer_has_to_be_cocked_from_rung_4(self):
        run = until_he_draws(M.Run(M.deal(4, seed=1)))
        unholster(run)
        shoot_at(run, *run.target())
        self.assertIsNone(run.result)
        self.assertEqual(run.bullets, M.BULLETS)
        M.act(run, M.COCK)
        shoot_at(run, *run.target())
        self.assertEqual(run.result[0], True)
        self.assertFalse(run.cocked)

    def test_the_wrong_man_loses(self):
        duel = M.deal(7, seed=2)
        run = until_he_draws(M.Run(duel))
        unholster(run)
        M.act(run, M.COCK)
        other = next(k for k in range(len(duel.men)) if k != duel.foe)
        _hat, body = run.boxes(other)
        shoot_at(run, (body[0] + body[2]) / 2, (body[1] + body[3]) / 2)
        self.assertEqual(run.result, (False, 'You shot the wrong man'))

    def test_his_hat_means_his_hat(self):
        duel = duel_with(10, lambda d: d.part == 'hat')
        run = until_he_draws(M.Run(duel))
        unholster(run)
        M.act(run, M.COCK)
        _hat, body = run.boxes(duel.foe)
        shoot_at(run, (body[0] + body[2]) / 2, (body[1] + body[3]) / 2)
        self.assertEqual(run.result[0], False)
        run = until_he_draws(M.Run(duel))
        unholster(run)
        M.act(run, M.COCK)
        shoot_at(run, *run.target())
        self.assertEqual(run.result[0], True)
        self.assertIn(duel.foe, run.hatless)

    def test_a_feint_is_not_a_draw(self):
        duel = duel_with(7, lambda d: len(d.reaches) > 1)
        feint = duel.reaches[0]
        self.assertFalse(feint.real)
        run = M.Run(duel)
        peak = 0.0
        while run.t < feint.t + 2 * M.REACH + 0.1:
            run.step(1 / 60.0)
            peak = max(peak, run.arm(feint.who))
        self.assertGreater(peak, 0.3)
        self.assertLess(peak, 0.6)
        self.assertEqual(run.arm(feint.who), 0.0)
        self.assertFalse(run.drawn())
        self.assertTrue(any(n.voice == M.LEATHER for n in run.notes))
        until_he_draws(run)
        for _k in range(30):
            run.step(1 / 60.0)
        self.assertEqual(run.arm(duel.foe), 1.0)

    def test_the_aim_sways_and_the_men_pace_higher_up(self):
        low = M.Run(M.deal(1, seed=1))
        self.assertEqual(low.sway(), (0.0, 0.0))
        high = M.Run(M.deal(14, seed=1))
        a, where = high.sway(), high.stands(0)
        for _k in range(40):
            high.step(1 / 60.0)
        self.assertNotEqual(a, high.sway())
        self.assertNotEqual(where, high.stands(0))


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('gunslinger', 10, pilot, seed=1, steps=1500),
                         [1.0])
        self.assertEqual(drive('gunslinger', 1, lambda t: None, seed=1,
                               steps=1500), [-1.0])
        self.assertEqual(drive('gunslinger', 1, lambda t: [
            H.toward(t.run.hand, *M.HOLSTER, tol=10.0), H.PRESS][
                H.toward(t.run.hand, *M.HOLSTER, tol=10.0) is None],
            seed=1, steps=1500), [-1.0])

    def test_the_agent_hears_him_go_for_his_gun(self):
        from nwenv import catalog
        env = catalog.env_class('gunslinger')(seed=2, rung=1, trials=1,
                                              adaptive=False)
        try:
            heard = 0
            for _k in range(700):
                env.step(None)
                chunk = env._public_audio
                if chunk:
                    heard += len(chunk['audio_pcm'])
            self.assertGreater(heard, 0)
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()
