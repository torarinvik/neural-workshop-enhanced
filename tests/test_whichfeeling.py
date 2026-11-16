#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Which Feeling: the ladder, the answers offered, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from feelingsupport import boundary, outcomes

from neural_workshop import whichfeeling as M


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_shortcuts_fail(self):
        for r, seed, ref, wins in outcomes(M, (1, 3, 5, 8, 11, 14, 30)):
            self.assertTrue(ref, (r, seed))
            self.assertEqual(wins, [], (r, seed))

    def test_the_answers_grow_closer(self):
        self.assertEqual([M.grade(r).options for r in (1, 3, 5, 11, 14)],
                         [2, 3, 4, 6, 8])
        rnd = M.deal(1, seed=1)
        for it in rnd.items:
            st = it.steps[0]
            truth = st.options[st.answer]
            other = [o for o in st.options if o != truth][0]
            self.assertNotEqual(M.kind_of(truth), M.kind_of(other))
        rnd = M.deal(9, seed=1)
        for it in rnd.items:
            st = it.steps[0]
            kinds = {M.kind_of(o) for o in st.options}
            self.assertEqual(len(kinds), 1)


class TheBoundary(unittest.TestCase):

    def test_reference_idle_and_sound(self):
        boundary(self, 'which_feeling', M)


if __name__ == '__main__':
    unittest.main()
