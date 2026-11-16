#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Proofreader: the ladder, the damage, the pen, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, wins
from spatialsupport import drive, queued

from neural_workshop import proofreader as M

RUNGS = (1, 4, 10, 16, 22, 30)


def at(run, x, y):
    run.hand.to(x, y)


def click(run, x, y):
    at(run, x, y)
    run.press()
    run.release()


def drag(run, a, b):
    at(run, *a)
    run.press()
    at(run, *b)
    run.release()


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertEqual(rand, [])

    def test_the_ladder_adds_what_it_says(self):
        self.assertEqual(M.grade(1).kinds, ('swap',))
        for kind, r in M.FROM.items():
            self.assertIn(kind, M.grade(r).kinds)
            if r > 1:
                self.assertNotIn(kind, M.grade(r - 1).kinds)
        self.assertEqual([M.grade(r).sentences for r in (1, 4, 10, 16)],
                         [1, 2, 3, 4])
        self.assertTrue(M.grade(18).hint and not M.grade(19).hint)
        errs = [M.grade(r).errors for r in range(1, 120)]
        self.assertEqual(errs, sorted(errs))
        self.assertGreater(errs[-1], errs[29])

    def test_far_rungs_still_deal(self):
        for r in (60, 120):
            m = M.deal(r, seed=2)
            self.assertTrue(M.play(m)[0])


class TheDamage(unittest.TestCase):

    def test_a_deal_differs_from_what_was_written(self):
        for r in RUNGS:
            m = M.deal(r, seed=5)
            self.assertNotEqual(M.texts(m.rows),
                                [list(s) for s in m.original])

    def test_damaged_neighbours_were_never_written(self):
        for r in (7, 13, 20):
            m = M.deal(r, seed=1)
            for kind, si, i in m.damage:
                if kind not in ('intruder', 'agree', 'scramble'):
                    continue
                row = m.rows[m.row_of.index(si)]
                k = next(k for k, t in enumerate(row)
                         if m.origin[t.id] == (si, i))
                w = row[k].text
                if k > 0:
                    self.assertFalse(M.said(row[k - 1].text, w))
                if k + 1 < len(row):
                    self.assertFalse(M.said(w, row[k + 1].text))

    def test_the_forms_always_hold_the_truth(self):
        for r in RUNGS:
            m = M.deal(r, seed=3)
            for tid, opts in m.options.items():
                si, i = m.origin[tid]
                self.assertIn(m.original[si][i], opts)

    def test_names_are_never_damaged(self):
        m = M.deal(20, seed=4)
        for kind, si, i in m.damage:
            if si >= 0 and kind != 'move' and kind != 'swap':
                self.assertFalse(M.name(m.original[si][i]))


class ThePen(unittest.TestCase):

    def setUp(self):
        self.run = M.Run(M.deal(10, seed=1))

    def test_a_click_shows_the_forms_and_a_pick_writes_one(self):
        run = self.run
        row = run.rows[0]
        k = next(k for k, t in enumerate(row) if t.id in run.machine.options)
        y = M.row_y(0, run.n())
        click(run, M.centres(row)[k], y)
        opts = run.options()
        self.assertTrue(opts)
        pick = next(o for o in opts if o != row[k].text)
        click(run, M.option_x(opts.index(pick), len(opts)), M.OPT_Y)
        self.assertEqual(run.rows[0][k].text, pick)
        self.assertIsNone(run.selected)

    def test_a_word_dragged_along_its_line_moves(self):
        run = self.run
        row = list(run.rows[0])
        y = M.row_y(0, run.n())
        cs = M.centres(row)
        drag(run, (cs[0], y), (cs[-1] + 20, y))
        self.assertEqual(run.rows[0][-1].id, row[0].id)
        self.assertEqual(len(run.rows[0]), len(row))

    def test_a_word_cannot_leave_its_line(self):
        run = self.run
        before = M.texts(run.rows)
        cs = M.centres(run.rows[0])
        drag(run, (cs[0], M.row_y(0, run.n())), (cs[0], M.row_y(1, run.n())))
        self.assertEqual(M.texts(run.rows), before)

    def test_a_sentence_moves_by_its_number_and_reset_undoes_it(self):
        run = self.run
        n = run.n()
        first = run.rows[0]
        drag(run, (M.HANDLE_X, M.row_y(0, n)), (M.HANDLE_X, M.row_y(n - 1, n)))
        self.assertIs(run.rows[-1], first)
        click(run, *M.RESET_AT)
        self.assertEqual(M.texts(run.rows), M.texts(run.machine.rows))

    def test_done_on_the_damage_fails(self):
        run = self.run
        click(run, *M.DONE_AT)
        self.assertEqual(run.result[0], False)


class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('proofreader', 4, pilot, seed=1, steps=12000),
                         [1.0])
        self.assertEqual(drive('proofreader', 1, lambda t: None, seed=1,
                               steps=12000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('proofreader', M), 0)


if __name__ == '__main__':
    unittest.main()
