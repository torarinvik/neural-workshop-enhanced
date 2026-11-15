#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Spreadsheet: the table, the tools, the answers, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import sheet as M


class TheTools(unittest.TestCase):

    def setUp(self):
        self.puzzle = M.deal(17, seed=4)
        self.sheet = M.Sheet(self.puzzle)

    def test_filter_and_sum(self):
        cat = self.puzzle.categories[1]
        self.sheet.do(('filter', cat))
        self.sheet.do(('sum', 'total'))
        rows = [r for r in self.puzzle.rows if r.category == cat]
        self.assertEqual(self.sheet.stats(),
                         (sum(r.total for r in rows), len(rows),
                          max(r.total for r in rows)))

    def test_sorting_turns_round_on_a_second_click(self):
        self.sheet.do(('sort', 'price'))
        up = [r.price for r in self.sheet.visible_rows()]
        self.assertEqual(up, sorted(up))
        self.sheet.do(('sort', 'price'))
        self.assertEqual([r.price for r in self.sheet.visible_rows()],
                         sorted(up, reverse=True))

    def test_scrolling_stops_at_the_end(self):
        for _k in range(50):
            self.sheet.wheel(1)
        self.assertEqual(self.sheet.scroll, self.sheet.max_scroll())
        self.assertEqual(len(self.sheet.shown()), M.VISIBLE)

    def test_the_keypad_types_and_submits_once(self):
        for d in ('4', '2', 'del', '7'):
            self.sheet.do(('key', d))
        self.assertEqual(self.sheet.typed, '47')
        self.sheet.do(('submit',))
        self.assertEqual(self.sheet.submitted, 47)


class TheAnswers(unittest.TestCase):

    def test_every_answer_is_read_off_the_rows(self):
        for rung in (2, 5, 8, 11, 14, 17, 22, 27):
            for seed in range(20):
                p = M.deal(rung, seed=seed)
                bad = [r for r in p.rows if r.total != r.qty * r.price]
                self.assertEqual(len(bad), 1 if p.kind in ('wrong', 'fix')
                                 else 0)
                if p.kind == 'wrong':
                    self.assertEqual(p.answer, bad[0].id)
                elif p.kind == 'fix':
                    self.assertEqual(p.answer, bad[0].qty * bad[0].price)
                elif p.kind == 'max':
                    self.assertEqual(p.answer, max(p.rows,
                                                   key=lambda r: r.total).id)

    def test_the_plan_answers_within_par(self):
        for rung in (1, 6, 9, 12, 15, 18, 24):
            for seed in range(10):
                p = M.deal(rung, seed=seed)
                sheet = M.Sheet(p)
                for action in M.plan(p):
                    sheet.clicks += 1
                    sheet.do(action)
                self.assertEqual(sheet.submitted, p.answer)
                self.assertLessEqual(sheet.clicks, M.par(p))


def queued(make):
    queue = []

    def policy(task):
        if not queue:
            queue.extend(make(task))
        return queue.pop(0)
    return policy


def wrong_answer(task):
    from neural_workshop import browser
    sheet = M.Sheet(task.sheet.puzzle)
    sheet.pointer = list(task.sheet.pointer)
    rects = dict(sheet.targets())
    ports = []
    digit = str((task.sheet.puzzle.answer + 1) % 10)
    for action in (('key', digit), ('key', digit), ('submit',)):
        tx, ty = browser.click_point(rects[action])
        moves = browser.moves_to(sheet.pointer[0], sheet.pointer[1], tx, ty)
        for port in moves:
            dx, dy = browser.DIRECTIONS[port // 3]
            sheet.move(dx * browser.STEPS[port % 3],
                       dy * browser.STEPS[port % 3])
        ports += moves + [12]
    return ports


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_a_wrong_number_fails(self):
        from neural_workshop.ui.sheet import reference_ports
        for rung in (2, 9, 21):
            self.assertEqual(drive('spreadsheet', rung,
                                   queued(reference_ports), steps=2000),
                             [1.0])
        self.assertEqual(drive('spreadsheet', 9, queued(wrong_answer),
                               steps=2000), [-1.0])


if __name__ == '__main__':
    unittest.main()
