#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fold It: the nets, the folding, the deals, the boundary, the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from spatialsupport import draws, drive, right, wrong
from uisupport import needs_ui

from neural_workshop import fold as F, space as S


def hinge_fold(net):
    """Fold a net by turning each square about its hinge, a quarter turn
    away from the eye: a check on :func:`fold` made another way."""
    cells = sorted(net)
    placed = {cells[0]: (S.IDENTITY, (0.0, 0.0, 0.0))}
    todo = [cells[0]]
    while todo:
        cell = todo.pop()
        turn, shift = placed[cell]
        x, y = cell
        for nxt, axis, pivot in (((x + 1, y), (0, 1, 0), (x + 1, 0, 0)),
                                 ((x - 1, y), (0, 1, 0), (x, 0, 0)),
                                 ((x, y + 1), (1, 0, 0), (0, y + 1, 0)),
                                 ((x, y - 1), (1, 0, 0), (0, y, 0))):
            if nxt not in net or nxt in placed:
                continue
            centre = (nxt[0] + 0.5, nxt[1] + 0.5, 0.0)
            for angle in (1.5707963, -1.5707963):
                hinge = S.rotation(axis, angle)
                if S.add(S.apply(hinge, S.sub(centre, pivot)),
                         pivot)[2] < 0:
                    break
            placed[nxt] = (S.compose(turn, hinge), S.add(S.apply(
                turn, S.sub(pivot, S.apply(hinge, pivot))), shift))
            todo.append(nxt)
    return placed


class TheNets(unittest.TestCase):

    def test_there_are_eleven_and_the_cross_is_one(self):
        self.assertEqual(len(F.NETS), 11)
        self.assertIn(F.CROSS, F.NETS)

    def test_folding_agrees_with_turning_each_square_on_its_hinge(self):
        for net in F.NETS:
            frames = F.fold(net)
            for cell, (turn, _shift) in hinge_fold(net).items():
                got = tuple(tuple(int(round(v)) for v in S.apply(turn, e))
                            for e in ((0, 0, 1), (1, 0, 0), (0, 1, 0)))
                self.assertEqual(got, tuple(frames[cell]), (net, cell))

    def test_a_two_by_two_block_does_not_fold(self):
        self.assertIsNone(F.fold(((0, 0), (1, 0), (0, 1), (1, 1),
                                  (2, 0), (3, 0))))


class TheDeals(unittest.TestCase):

    def test_every_deal_has_one_answer_by_the_folding(self):
        for rung in (1, 3, 5, 8, 11, 14, 17, 21, 27):
            for seed in range(25):
                self.assertTrue(F.check(F.deal(rung, seed=seed)),
                                (rung, seed))

    def test_a_mirrored_cube_is_wrong_when_marks_have_handedness(self):
        p = F.deal(22, seed=2)
        cube = F.folded(p.net, p.marks)
        if any(F.GLYPHS[m.glyph].handed or F.GLYPHS[m.glyph].symmetry < 4
               for m in cube.values()):
            self.assertFalse(F.every_view(cube) & F.every_view(
                F.mirror(cube)))

    def test_the_wrong_cubes_differ_the_way_the_rung_says(self):
        self.assertEqual(F.grade(5).wrongs, ('swap',))
        self.assertIn('mirror', F.grade(17).wrongs)
        self.assertNotIn('swap', F.grade(17).wrongs)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 12):
            self.assertEqual(drive('fold_it', rung, right), [1.0])
            self.assertEqual(drive('fold_it', rung, wrong), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def test_every_kind_of_trial_draws(self):
        from neural_workshop.ui.fold import FoldIt
        draws(self, FoldIt, (1, 5, 11, 14, 18, 26))


if __name__ == '__main__':
    unittest.main()
