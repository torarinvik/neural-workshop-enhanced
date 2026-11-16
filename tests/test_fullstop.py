#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Full Stop: the ladder, the breaks, the clicks, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, wins
from spatialsupport import drive, queued

from neural_workshop import fullstop as M
from neural_workshop import proofreader as PR

RUNGS = (1, 5, 10, 14, 20, 30)


def click(run, x, y):
    run.hand.to(x, y)
    run.press()
    run.release()


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertEqual(rand, [])

    def test_the_ladder_adds_what_it_says(self):
        self.assertEqual([M.grade(r).sentences for r in (1, 3, 5, 21, 99)],
                         [2, 3, 4, 12, 12])
        self.assertTrue(M.grade(9).hint and not M.grade(10).hint)
        self.assertTrue(M.grade(14).flat and not M.grade(13).flat)
        self.assertTrue(M.grade(20).short and not M.grade(19).short)
        paces = [M.grade(r).pace for r in range(1, 80)]
        self.assertEqual(paces, sorted(paces, reverse=True))
        self.assertLess(paces[-1], paces[0] / 2)


class TheBreaks(unittest.TestCase):

    def test_every_break_joins_words_never_joined(self):
        for r in RUNGS:
            m = M.deal(r, seed=3)
            for i in m.stops:
                self.assertFalse(PR.said(m.words[i], m.words[i + 1]))

    def test_the_words_are_the_sentences_run_together(self):
        m = M.deal(10, seed=1)
        self.assertEqual(sum(len(s) for s in m.sentences), len(m.words))
        self.assertEqual(len(m.stops), len(m.sentences) - 1)

    def test_flat_rungs_have_no_capitals(self):
        m = M.deal(16, seed=2)
        self.assertTrue(all(w == w.lower() for w in m.words))

    def test_the_page_fits(self):
        m = M.deal(30, seed=1)
        run = M.Run(m)
        self.assertGreaterEqual(min(y for _x, y, _w in run.places),
                                M.BOTTOM - 1)


class TheClicks(unittest.TestCase):

    def test_a_click_puts_a_stop_and_another_takes_it(self):
        run = M.Run(M.deal(4, seed=1))
        x, y, _w = run.places[2]
        click(run, x, y)
        self.assertEqual(run.stops, {2})
        click(run, x, y)
        self.assertEqual(run.stops, set())

    def test_the_last_word_takes_no_stop(self):
        run = M.Run(M.deal(4, seed=1))
        x, y, _w = run.places[-1]
        click(run, x, y)
        self.assertEqual(run.stops, set())

    def test_reset_and_a_wrong_hand_in(self):
        run = M.Run(M.deal(4, seed=1))
        for i in range(3):
            click(run, *run.places[i][:2])
        click(run, *M.RESET_AT)
        self.assertEqual(run.stops, set())
        click(run, *M.DONE_AT)
        self.assertFalse(run.result[0])


class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('full_stop', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('full_stop', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('full_stop', M), 0)


if __name__ == '__main__':
    unittest.main()
