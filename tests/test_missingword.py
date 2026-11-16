#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Missing Word: the ladder, the gaps, the offers, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, wins
from spatialsupport import drive, queued

from neural_workshop import missingword as M
from neural_workshop import proofreader as PR

RUNGS = (1, 4, 7, 10, 16, 25)


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
        self.assertEqual(M.grade(6).kinds, ('missing',))
        self.assertEqual(M.grade(7).kinds, ('missing', 'extra'))
        self.assertEqual([M.grade(r).sentences for r in (1, 4, 10, 16)],
                         [1, 2, 3, 4])
        self.assertTrue(M.grade(13).close and not M.grade(12).close)
        self.assertTrue(M.grade(18).hint and not M.grade(19).hint)
        errs = [M.grade(r).errors for r in range(1, 120)]
        self.assertEqual(errs, sorted(errs))
        self.assertLess(M.grade(120).seconds, M.grade(40).seconds)

    def test_far_rungs_still_deal(self):
        self.assertTrue(M.play(M.deal(90, seed=2))[0])


class TheGaps(unittest.TestCase):

    def test_a_gap_leaves_a_pair_never_written(self):
        for r in (4, 10, 16):
            m = M.deal(r, seed=1)
            for si, row in enumerate(m.rows):
                for a, b in zip(row, row[1:]):
                    if M.truth_between(m, a, b) is not None:
                        self.assertFalse(PR.said(a.text, b.text))

    def test_an_extra_word_makes_unwritten_pairs_both_sides(self):
        for r in (7, 13, 22):
            m = M.deal(r, seed=2)
            for row in m.rows:
                for k, t in enumerate(row):
                    if t.id >= 9000:
                        self.assertFalse(PR.said(row[k - 1].text, t.text))
                        self.assertFalse(PR.said(t.text, row[k + 1].text))

    def test_the_ends_of_a_line_are_never_missing(self):
        m = M.deal(25, seed=3)
        for kind, si, i in m.damage:
            if kind == 'missing':
                self.assertTrue(0 < i < len(m.original[si]) - 1)

    def test_every_caret_offers_four_and_a_gap_offers_its_word(self):
        m = M.deal(16, seed=1)
        for row in m.rows:
            for a, b in zip(row, row[1:]):
                opts = M.offer(m, a, b)
                self.assertEqual(len(opts), 4)
                self.assertEqual(opts, M.offer(m, a, b))
                truth = M.truth_between(m, a, b)
                if truth is not None:
                    self.assertIn(truth, opts)


class ThePen(unittest.TestCase):

    def setUp(self):
        self.run = M.Run(M.deal(7, seed=1))

    def test_a_caret_and_a_pick_put_a_word_in(self):
        run = self.run
        row = run.rows[0]
        before = len(row)
        click(run, M.carets(row)[0], M.row_y(0, run.n()) - M.CARET_DY)
        self.assertEqual(run.chosen, ('gap', 0, 0))
        opts = run.options()
        click(run, M.option_x(2, len(opts)), M.OPT_Y)
        self.assertEqual(len(run.rows[0]), before + 1)
        self.assertEqual(run.rows[0][1].text, opts[2])

    def test_a_word_can_be_struck_and_reset_brings_it_back(self):
        run = self.run
        word = run.rows[0][1]
        click(run, M.centres(run.rows[0])[1], M.row_y(0, run.n()))
        self.assertEqual(run.options(), (M.STRIKE_OUT,))
        click(run, M.option_x(0, 1), M.OPT_Y)
        self.assertNotIn(word, run.rows[0])
        click(run, *M.RESET_AT)
        self.assertEqual(M.texts(run.rows), M.texts(run.machine.rows))

    def test_done_on_the_damage_fails(self):
        click(self.run, *M.DONE_AT)
        self.assertFalse(self.run.result[0])


class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('missing_word', 4, pilot, seed=1,
                               steps=12000), [1.0])
        self.assertEqual(drive('missing_word', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('missing_word', M), 0)


if __name__ == '__main__':
    unittest.main()
