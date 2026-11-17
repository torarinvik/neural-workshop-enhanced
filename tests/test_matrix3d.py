#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""3D Matrix: the rules, the deal, the answers' balance, the solids, the
boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import random
import unittest

from spatialsupport import drive, right, wrong
from uisupport import needs_ui

from neural_workshop import matrix3d as M

RUNGS = (1, 4, 7, 10, 13, 16, 19, 25, 40)


class TheRules(unittest.TestCase):

    def test_each_rule_reads_as_it_says(self):
        self.assertEqual([M._value(('row', (2, 0, 1)), r, c)
                          for r in range(3) for c in range(3)],
                         [2, 2, 2, 0, 0, 0, 1, 1, 1])
        self.assertEqual([M._value(('col', (2, 0, 1)), 1, c)
                          for c in range(3)], [2, 0, 1])
        for sign in (1, -1):
            g = [[M._value(('latin', (0, 1, 2), sign), r, c)
                  for c in range(3)] for r in range(3)]
            for k in range(3):
                self.assertEqual(sorted(g[k]), [0, 1, 2])
                self.assertEqual(sorted(row[k] for row in g), [0, 1, 2])
        rule = ('xor', ((0, 1), (1, 1), (0, 0)))
        self.assertEqual([M._value(rule, r, 2) for r in range(3)], [1, 0, 0])

    def test_the_eight_shown_settle_the_ninth(self):
        self.assertEqual(M.infer('side', [0, 0, 0, 1, 1, 1, 2, 2]), {2})
        self.assertEqual(M.infer('side', [0, 1, 2, 0, 1, 2, 0, 1]), {2})
        self.assertEqual(M.infer('side', [0, 1, 2, 1, 2, 0, 2, 0]), {1})
        self.assertEqual(M.infer('ring', [0, 1, 1, 1, 1, 0, 1, 0]), {1})
        self.assertEqual(M.infer('side', [0, 1, 2, 2, 2, 0, 1, 0]), set())


class TheDeal(unittest.TestCase):

    def test_the_solver_agrees_with_every_deal(self):
        for rung in RUNGS:
            for seed in range(150):
                p = M.deal(rung, seed=seed)
                self.assertEqual(M.solve(p), p.answer, (rung, seed))
                self.assertEqual(p.options[p.answer], p.cells[8])

    def test_the_ladder(self):
        self.assertEqual(M.grade(1).vary, 1)
        self.assertEqual(M.grade(1).choices, 4)
        self.assertEqual(M.grade(7).choices, 6)
        self.assertEqual(M.grade(16).choices, 8)
        self.assertNotIn('view', M.grade(12).pool)
        self.assertIn('view', M.grade(13).pool)
        last = 0
        for rung in range(1, 40):
            level = M.grade(rung)
            self.assertGreaterEqual(level.vary, last)
            last = level.vary
            p = M.deal(rung, seed=rung)
            self.assertEqual(len(p.rules), level.vary)
            self.assertEqual(len(p.options), level.choices)
            for attr, kind in p.rules:
                self.assertIn(kind, level.kinds)
                self.assertGreater(len({getattr(c, attr)
                                        for c in p.cells[:8]}), 1)

    def test_what_is_not_in_play_stands_still(self):
        for seed in range(40):
            p = M.deal(2, seed=seed)
            for attr in ('top', 'base', 'height', 'view'):
                self.assertEqual({getattr(c, attr) for c in p.cells
                                  + p.options},
                                 {getattr(M.Build(), attr)})

    def test_a_seed_deals_the_same_matrix(self):
        self.assertEqual(M.deal(12, seed=4), M.deal(12, seed=4))
        self.assertNotEqual(M.deal(12, seed=4).cells,
                            M.deal(12, seed=5).cells)


class TheAnswers(unittest.TestCase):

    def test_they_differ_and_the_right_one_is_anywhere(self):
        for rung in RUNGS:
            where = collections.Counter()
            for seed in range(400):
                p = M.deal(rung, seed=seed)
                self.assertEqual(len(set(p.options)), len(p.options))
                where[p.answer] += 1
            n = M.grade(rung).choices
            self.assertEqual(len(where), n)
            self.assertLess(max(where.values()), 400 / n * 1.5, rung)

    def test_the_answers_alone_give_nothing_away(self):
        """Every value an answer has is in as many answers as its
        alternative, so the commonest-of-each guess is no guess."""
        for rung in RUNGS:
            for seed in range(60):
                p = M.deal(rung, seed=seed)
                for attr in M.ATTRS:
                    counts = collections.Counter(getattr(o, attr)
                                                 for o in p.options)
                    self.assertEqual(len(set(counts.values())), 1,
                                     (rung, seed, attr))

    def test_random_and_fixed_play_are_at_chance(self):
        rng = random.Random(3)
        for rung in (1, 7, 16):
            n = M.grade(rung).choices
            deals = [M.deal(rung, seed=s) for s in range(600)]
            luck = sum(rng.randrange(n) == p.answer for p in deals)
            self.assertLess(luck, 600 / n * 1.35, rung)
            for port in range(n):
                fixed = sum(p.answer == port for p in deals)
                self.assertLess(fixed, 600 / n * 1.4, (rung, port))

    def test_the_answer_is_worked_out_not_copied(self):
        """From two rules up the answer is never a cell on show; and
        picking among the answers that are not on show is little
        better than picking among them all."""
        rng = random.Random(5)
        for rung in (4, 7, 10, 13, 16, 19):
            n = M.grade(rung).choices
            wins = 0
            for seed in range(600):
                p = M.deal(rung, seed=seed)
                self.assertNotIn(p.cells[8], p.cells[:8])
                fresh = [i for i, o in enumerate(p.options)
                         if o not in p.cells[:8]]
                wins += rng.choice(fresh) == p.answer
            self.assertLess(wins, 600 / n * 1.8, rung)


class TheSolids(unittest.TestCase):

    def test_a_construction_has_what_it_says(self):
        plain = [part.mesh for part in M.parts(M.Build())]
        self.assertEqual(sorted(plain), ['ball', 'box', 'wedge'])
        full = M.parts(M.Build(ring=1, cap=1, top=2, base=1, height=2))
        self.assertEqual(sorted(part.mesh for part in full),
                         ['box', 'cone', 'drum', 'drum', 'drum', 'ring',
                          'wedge'])

    def test_the_ramp_goes_where_it_says(self):
        def ramp(side):
            return [part for part in M.parts(M.Build(side=side))
                    if part.mesh == 'wedge'][0].pos
        self.assertGreater(ramp(0)[0], 0.5)
        self.assertLess(ramp(1)[1], -0.5)      # the front is towards -y
        self.assertLess(ramp(2)[0], -0.5)

    def test_nothing_sinks_into_the_table_and_it_stands_as_tall(self):
        for build in (M.Build(), M.Build(cap=1, top=2, height=2),
                      M.Build(top=0, cap=1), M.Build(ring=1, base=2)):
            high = 0.0
            for part in M.parts(build):
                self.assertGreaterEqual(part.pos[2] - part.size[2], -1e-9)
                if part.mesh != 'box' or part.size[0] > 0.2:
                    high = max(high, part.pos[2] + part.size[2])
            self.assertLessEqual(high, M.tall(build) + 0.05)

    def test_the_ramp_stays_inside_the_ring(self):
        self.assertLess(M.HALF + 0.55, 1.42 * 0.82)


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_right_passes_and_wrong_fails(self):
        for rung in (1, 10, 20):
            self.assertEqual(drive('matrix_3d', rung, right, seed=2), [1.0])
            self.assertEqual(drive('matrix_3d', rung, wrong, seed=2), [-1.0])

    def test_the_solver_passes_through_the_ports(self):
        self.assertEqual(drive('matrix_3d', 16,
                               lambda task: M.solve(task.puzzle), seed=5),
                         [1.0])

    def test_idle_is_never_paid(self):
        self.assertEqual(drive('matrix_3d', 1, lambda task: None, seed=2,
                               steps=200), [])

    def test_every_rung_draws_its_cells_in_3d(self):
        from neural_workshop.ui.matrix3d import Matrix3D
        from uisupport import close_overlays, reset_window
        close_overlays()
        task = Matrix3D()
        try:
            self.assertTrue(task.stage.ok, task.stage.trouble)
            for rung in (1, 8, 14, 20):
                task.rng = random.Random(2)
                task.start_rung = rung
                task.total_trials = 1
                task.adaptive = False
                task.start_run()
                task.on_draw()
                n = task.puzzle.level.choices
                self.assertEqual(len(task.panels), 8 + n, rung)
                self.assertEqual(len(task.hits), n, rung)
                sizes = {(round(p[2]), round(p[3])) for p in task.panels}
                self.assertEqual(len(sizes), 1, rung)
                task.choose(task.puzzle.answer)
                task.on_draw()
                if task.phase == 'judged':
                    # The missing cell is shown once it is judged.
                    self.assertEqual(len(task.panels), 9 + n, rung)
        finally:
            task.close()
            close_overlays()
            reset_window()


if __name__ == '__main__':
    unittest.main()
