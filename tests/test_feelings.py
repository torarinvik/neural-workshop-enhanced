#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The engine under the Emotion tasks: steps, judging, time, buttons.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from neural_workshop import feelings as F


def a_round(n=4, need=3, seconds=5.0, tolerance=-1.0):
    st = F.Step('?', ('a', 'b', 'c'), 1, (0.0, 2.0, 4.0))
    items = tuple(F.Item('x', (st,), seconds, tolerance=tolerance)
                  for _k in range(n))
    return F.Round(None, items, need)


class TheEngine(unittest.TestCase):

    def test_right_answers_pass_and_the_round_ends(self):
        self.assertTrue(F.play(a_round())[0])
        self.assertFalse(F.play(a_round(), F.always(0))[0])

    def test_a_round_ends_as_soon_as_it_cannot_pass(self):
        run = F.Run(a_round(n=4, need=3))
        run.choose(0)
        for _k in range(60):
            run.step(1 / 30.0)
        run.choose(0)
        self.assertEqual(run.result[0], False)
        self.assertEqual(len(run.marks), 2)

    def test_time_runs_out_on_an_item(self):
        run = F.Run(a_round(seconds=1.0))
        for _k in range(40):
            run.step(1 / 30.0)
        self.assertEqual(run.marks, [False])

    def test_intensities_are_judged_by_their_summed_error(self):
        st = F.Step('?', ('0', '2', '4'), 2, (0.0, 2.0, 4.0))
        it = F.Item('x', (st, st), 5.0, tolerance=2.0)
        self.assertTrue(F.judge(it, (2, 1)))
        self.assertFalse(F.judge(it, (1, 1)))

    def test_a_click_on_a_button_picks_it(self):
        run = F.Run(a_round())
        x, y, w, h = F.option_rect(1, 3)
        run.hand.to(x + w / 2, y + h / 2)
        F.act(run, F.H.PRESS)
        self.assertEqual(run.marks, [True])

    def test_buttons_stay_on_the_screen(self):
        for n in range(2, 9):
            for k in range(n):
                x, y, w, h = F.option_rect(k, n)
                self.assertTrue(0 <= x and x + w <= 1000 and 0 <= y)

    def test_the_bar_is_set_against_guessing(self):
        self.assertEqual(F.need_for(10, 0.5), 9)
        self.assertEqual(F.need_for(12, 0.125), 5)


if __name__ == '__main__':
    unittest.main()
