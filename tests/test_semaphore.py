#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Semaphore: the code, the flags, the letters, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, settle, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import hand as H
from neural_workshop import semaphore as M

RUNGS = (1, 4, 7, 10, 13, 16, 22, 35)


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertLessEqual(len(rand), 1)

    def test_the_ladder_adds_what_it_says(self):
        g = {r: M.grade(r) for r in (1, 4, 7, 10, 13, 16, 20, 40)}
        self.assertEqual([g[r].help for r in (1, 4, 10, 16)],
                         ['named', 'chart', 'peek', 'none'])
        self.assertTrue(g[7].roll and not g[4].roll)
        self.assertTrue(g[13].turns and not g[10].turns)
        self.assertTrue(g[13].words and not g[16].words)
        self.assertTrue(g[20].fog and not g[16].fog)
        self.assertLess(g[40].hold, g[20].hold)
        self.assertGreater(g[40].letters, g[20].letters)


class TheCode(unittest.TestCase):

    def test_every_letter_has_its_own_pair_of_positions(self):
        self.assertEqual(len(M.CODE), 26)
        self.assertEqual(len(set(M.CODE.values())), 26)
        for a, b in M.CODE.values():
            self.assertTrue(0 <= a < b < 8)

    def test_a_turned_back_shows_the_mirror(self):
        for pose in M.CODE.values():
            self.assertEqual(M.flip(M.flip(pose)), tuple(pose))
        for s in range(60):
            message = M.deal(13, seed=s)
            if any(message.turned):
                break
        k = message.turned.index(True)
        run = M.Run(message)
        run.t = 2.0 + k * run.span() + 0.1
        seen = sorted(round((a - run.roll()) / 45.0) % 8
                      for a in run.theirs())
        self.assertEqual(tuple(seen), M.flip(M.CODE[message.text[k]]))


class TheFlags(unittest.TestCase):

    def up(self, rung=4):
        run = M.Run(M.deal(rung, seed=1))
        while run.index() is None:
            run.step(1 / 60.0)
        return run

    def copy(self, run):
        run.flags = [p * 45.0 for p in M.CODE[run.message.text[run.index()]]]

    def key(self, letter):
        return H.KEYS + M.LETTERS.index(letter)

    def test_a_flag_follows_the_pointer_round(self):
        run = M.Run(M.deal(1, seed=1))
        x, y = run.tip(0)
        run.hand.to(x, y)
        run.press()
        self.assertEqual(run.held, 0)
        d = M.way(90.0)
        run.hand.to(M.PIVOT[0] + M.ARM * d[0], M.PIVOT[1] + M.ARM * d[1])
        run.step(1 / 60.0)
        self.assertAlmostEqual(run.flags[0], 90.0, places=3)
        run.release()
        self.assertIsNone(run.held)

    def test_the_pose_and_the_letter_together_read_it(self):
        run = self.up()
        self.copy(run)
        M.act(run, self.key(run.message.text[0]))
        self.assertEqual((run.read[0], run.strikes), (True, 0))

    def test_the_wrong_letter_is_a_strike(self):
        run = self.up()
        self.copy(run)
        wrong = next(c for c in M.LETTERS if c != run.message.text[0])
        M.act(run, self.key(wrong))
        self.assertEqual((run.read[0], run.strikes), (False, 1))

    def test_the_letter_without_the_pose_is_a_strike(self):
        run = self.up()
        run.flags = [100.0, 200.0]
        M.act(run, self.key(run.message.text[0]))
        self.assertEqual(run.strikes, 1)

    def test_a_signal_let_pass_is_a_strike_and_a_bell_rings_each(self):
        run = self.up()
        settle(run, run.span() + 0.2)
        self.assertEqual(run.strikes, 1)
        self.assertEqual(len([n for n in run.notes if n.voice == M.BELL]), 2)

    def test_the_chart_goes_away_part_way_through_a_signal(self):
        run = self.up(10)
        self.assertEqual(run.helped(), 'chart')
        settle(run, 0.5 * run.level.hold)
        self.assertEqual(run.helped(), 'none')


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('semaphore', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('semaphore', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('semaphore', M), 0)


if __name__ == '__main__':
    unittest.main()
