#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stop & Switch: the rules, the blocks, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import drive
from uisupport import needs_ui

from neural_workshop import stopswitch as M
from neural_workshop.stopswitch import LEFT, RIGHT, Stimulus


class TheRules(unittest.TestCase):

    def test_each_rule_answers_its_way(self):
        s = Stimulus('circle', 'orange', 1, 'shape', False)
        self.assertEqual(M.answer(s), LEFT)
        self.assertEqual(M.answer(s._replace(rule='colour')), RIGHT)
        self.assertEqual(M.answer(s._replace(rule='opposite')), LEFT)
        self.assertEqual(M.answer(s._replace(rule='opposite', side=-1)),
                         RIGHT)

    def test_a_stop_is_right_only_unanswered(self):
        level = M.grade(5)
        s = Stimulus('circle', 'blue', 0, 'shape', True)
        self.assertTrue(M.right(s, None, None, level))
        self.assertFalse(M.right(s, LEFT, 0.3, level))

    def test_too_slow_is_wrong(self):
        level = M.grade(3)
        s = Stimulus('square', 'blue', 0, 'shape', False)
        self.assertTrue(M.right(s, RIGHT, level.window - 0.01, level))
        self.assertFalse(M.right(s, RIGHT, level.window + 0.01, level))


class TheBlocks(unittest.TestCase):

    def test_the_ladder_brings_in_its_parts(self):
        def seen(rung, what):
            out = set()
            for seed in range(20):
                for s in M.deal(rung, seed=seed).stimuli:
                    out.add(what(s))
            return out
        self.assertEqual(seen(3, lambda s: s.stop), {False})
        self.assertIn(True, seen(5, lambda s: s.stop))
        self.assertEqual(seen(6, lambda s: s.side), {0})
        self.assertIn(1, seen(8, lambda s: s.side))
        self.assertEqual(seen(9, lambda s: s.rule), {'shape'})
        self.assertEqual(seen(11, lambda s: s.rule), {'shape', 'colour'})
        self.assertIn('opposite', seen(22, lambda s: s.rule))

    def test_cued_switches_come_in_runs_of_four_to_six(self):
        rules = [s.rule for s in M.deal(11, seed=3).stimuli]
        runs, k = [], 0
        for a, b in zip(rules, rules[1:]):
            k += 1
            if a != b:
                runs.append(k)
                k = 0
        self.assertTrue(all(4 <= r <= 6 for r in runs[1:]), runs)

    def test_the_time_to_answer_shrinks(self):
        windows = [M.grade(r).window for r in (1, 3, 8, 17, 21, 30)]
        self.assertEqual(windows, sorted(windows, reverse=True))


def good(task):
    s = task.stimulus
    if not task.showing or task.replied is not None or s.stop or \
            task.clock() - task.shown_at < 0.05:
        return None
    return M.answer(s)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_by_the_rule_passes_and_always_left_fails(self):
        for rung in (2, 14, 22):
            self.assertEqual(drive('stop_and_switch', rung, good,
                                   steps=3000), [1.0])
            self.assertEqual(drive('stop_and_switch', rung,
                                   lambda t: 0 if t.showing else None,
                                   steps=3000), [-1.0])


if __name__ == '__main__':
    unittest.main()
