#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Artist: the paint box, how alike is measured, the ladder from a
block to a photograph, the pilot without a mouse, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import artist as M

RED, BLUE = (200, 30, 30), (30, 30, 200)


class ThePaintBox(unittest.TestCase):

    def canvas(self, size=8):
        return M.blank(size)

    def test_a_block_fills_its_rectangle_and_nothing_else(self):
        pix = self.canvas()
        M.paint(pix, 8, M.Op('block', RED, 2, 1, 4, 3))
        inked = [(x, y) for y in range(8) for x in range(8)
                 if M.get(pix, 8, x, y) == RED]
        self.assertEqual(len(inked), 9)
        self.assertEqual(M.get(pix, 8, 5, 3), M.PAPER)

    def test_a_box_is_an_outline(self):
        pix = self.canvas()
        M.paint(pix, 8, M.Op('box', RED, 1, 1, 5, 5))
        self.assertEqual(M.get(pix, 8, 1, 3), RED)
        self.assertEqual(M.get(pix, 8, 3, 3), M.PAPER)

    def test_a_line_joins_its_ends(self):
        pix = self.canvas()
        M.paint(pix, 8, M.Op('line', RED, 0, 0, 7, 7))
        self.assertTrue(all(M.get(pix, 8, k, k) == RED for k in range(8)))

    def test_fill_stops_at_an_outline(self):
        pix = self.canvas()
        M.paint(pix, 8, M.Op('box', RED, 1, 1, 5, 5))
        M.paint(pix, 8, M.Op('fill', BLUE, 3, 3, 3, 3))
        self.assertEqual(M.get(pix, 8, 4, 4), BLUE)
        self.assertEqual(M.get(pix, 8, 1, 1), RED)
        self.assertEqual(M.get(pix, 8, 7, 7), M.PAPER)

    def test_strokes_off_the_canvas_are_brought_onto_it(self):
        pix = self.canvas()
        M.paint(pix, 8, M.Op('block', RED, -5, -5, 50, 50))
        self.assertEqual(bytes(pix), bytes(M.blank(8, RED)))


class TheEasel(unittest.TestCase):

    def setUp(self):
        self.p = M.deal(7, seed=1)
        self.e = M.Easel(self.p)

    def test_a_shape_follows_the_drag_and_leaves_no_trail(self):
        self.e.tool = 'block'
        self.e.press(2, 2)
        self.e.drag(12, 12)
        self.e.release(4, 4)
        self.assertEqual(M.get(self.e.pix, 16, 10, 10), M.PAPER)
        self.assertEqual(M.get(self.e.pix, 16, 3, 3), self.e.colour)

    def test_undo_takes_back_one_stroke(self):
        before = bytes(self.e.pix)
        self.e.do(M.Op('block', RED, 1, 1, 5, 5))
        self.e.do(M.Op('line', BLUE, 0, 0, 9, 9))
        self.e.undo()
        self.assertEqual(M.get(self.e.pix, 16, 0, 0), M.PAPER)
        self.assertEqual(M.get(self.e.pix, 16, 3, 3), RED)
        self.e.undo()
        self.assertEqual(bytes(self.e.pix), before)

    def test_the_picker_takes_the_picture_s_colour(self):
        self.e.pick_from_picture(3, 3)
        self.assertEqual(self.e.colour, M.get(self.p.target, 16, 3, 3))

    def test_clear_can_be_undone(self):
        self.e.do(M.Op('block', RED, 1, 1, 5, 5))
        self.e.clear()
        self.assertEqual(bytes(self.e.pix), bytes(M.blank(16)))
        self.e.undo()
        self.assertEqual(M.get(self.e.pix, 16, 3, 3), RED)


class HowAlike(unittest.TestCase):

    def test_a_perfect_copy_is_one_and_one_flat_colour_is_nothing(self):
        for rung in (1, 7, 13, 16):
            p = M.deal(rung, seed=3)
            self.assertAlmostEqual(M.alike(p, p.target), 1.0)
            for colour in p.palette + (M.average(p.target),):
                self.assertLessEqual(M.alike(p, M.blank(p.size, colour)),
                                     1e-9, (rung, colour))

    def test_low_down_a_slip_of_a_pixel_costs_nothing(self):
        for seed in range(20):
            p = M.deal(1, seed=seed)
            op = p.shapes[0]
            dx = 1 if op.x1 < p.size - 1 else -1
            near = op._replace(x0=op.x0 + dx, x1=op.x1 + dx)
            self.assertAlmostEqual(M.replay(p, [near]).alike(), 1.0)

    def test_low_down_a_block_a_pixel_too_wide_nearly_always_passes(self):
        tried = passed = 0
        for seed in range(60):
            p = M.deal(1, seed=seed)
            op = p.shapes[0]
            if op.x1 < p.size - 1:
                big = op._replace(x1=op.x1 + 1)
                tried += 1
                passed += M.replay(p, [big]).alike() >= p.level.need
        self.assertGreater(tried, 10)
        self.assertGreaterEqual(passed, tried * 0.9)

    def test_high_up_a_slip_costs(self):
        p = M.deal(13, seed=1)
        moved = [op._replace(x0=op.x0 + 2, x1=op.x1 + 2) for op in p.shapes]
        self.assertLess(M.replay(p, moved).alike(), 1.0)

    def test_the_wrong_colour_does_not_pass(self):
        p = M.deal(4, seed=2)
        swapped = [op._replace(colour=p.palette[1 + (p.palette.index(op.colour))
                                                % (len(p.palette) - 1)])
                   for op in p.shapes]
        self.assertLess(M.replay(p, swapped).alike(), p.level.need)


class TheLadder(unittest.TestCase):

    def test_it_runs_from_a_block_to_a_photograph(self):
        sizes = [M.grade(r).size for r in (1, 4, 7, 10, 13, 16, 19, 25, 30)]
        self.assertEqual(sizes, sorted(sizes))
        self.assertEqual((sizes[0], sizes[-1]), (8, 128))
        self.assertEqual(len(M.deal(1, seed=1).shapes), 1)
        self.assertEqual(M.grade(1).need, 0.25)
        self.assertTrue(M.grade(30).full)
        self.assertGreater(M.grade(45).need, M.grade(30).need)

    def test_the_reference_copies_every_rung(self):
        for rung, seeds in ((1, 12), (4, 12), (7, 12), (10, 12), (13, 12),
                            (16, 2), (19, 2), (25, 1), (30, 1), (45, 1)):
            for seed in range(seeds):
                p = M.deal(rung, seed=seed)
                self.assertGreaterEqual(M.replay(p, M.solve(p)).alike(),
                                        p.level.need, (rung, seed))

    def test_the_same_seed_deals_the_same(self):
        self.assertEqual(M.deal(16, seed=5), M.deal(16, seed=5))
        self.assertNotEqual(M.deal(16, seed=5).target, M.deal(16, seed=6).target)

    def test_low_pictures_use_only_their_palette(self):
        for rung in (1, 10, 16, 19):
            p = M.deal(rung, seed=1)
            seen = {tuple(p.target[k:k + 3])
                    for k in range(0, len(p.target), 3)}
            self.assertLessEqual(seen, set(p.palette), rung)

    def test_a_photograph_is_used_when_there_is_one(self):
        def photo(size, draw):
            return bytes(bytearray((x * 7 + y * 3) % 256
                                   for y in range(size) for x in range(size)
                                   for _c in range(3)))
        p = M.deal(30, seed=1, photo=photo)
        self.assertEqual(p.target, photo(128, None))
        self.assertNotEqual(M.deal(30, seed=1).target, p.target)


class WithoutAMouse(unittest.TestCase):

    def pilot(self, p):
        e = M.Easel(p)
        for op in M.solve(p):
            for port in M.ports_for(e, op):
                self.assertFalse(e.act(port))
        return e

    def test_the_pilot_passes_the_shape_rungs(self):
        for rung in (1, 4, 7, 10, 13):
            for seed in range(10):
                p = M.deal(rung, seed=seed)
                self.assertGreaterEqual(self.pilot(p).alike(), p.level.need,
                                        (rung, seed))

    def test_random_play_does_not_pass(self):
        rnd = random.Random(1)
        for seed in range(40):
            p = M.deal(1, seed=seed)
            e = M.Easel(p)
            for _k in range(300):
                if e.act(rnd.randrange(M.PORTS)):
                    break
            self.assertLess(e.alike(), p.level.need, seed)

    def test_the_pen_draws_only_while_it_is_down(self):
        e = M.Easel(M.deal(7, seed=1))
        before = bytes(e.pix)
        for port in (M.P_LEFT, M.P_UP_FAR, M.P_RIGHT):
            e.act(port)
        self.assertEqual(bytes(e.pix), before)
        e.act(M.P_PEN)
        e.act(M.P_RIGHT)
        e.act(M.P_PEN)
        self.assertNotEqual(bytes(e.pix), before)
        self.assertTrue(e.act(M.P_DONE))


@needs_ui
class TheBoundary(unittest.TestCase):

    def pilot(self):
        def ports(easel):
            if easel.strokes < len(easel.puzzle.shapes):
                return M.ports_for(easel, easel.puzzle.shapes[easel.strokes])
            return [M.P_DONE]
        return queued(ports, lambda task: task.easel)

    def test_a_copy_passes_and_a_blank_canvas_fails(self):
        for rung in (1, 10):
            self.assertEqual(drive('the_artist', rung, self.pilot(), seed=2,
                                   steps=2000), [1.0], rung)
            self.assertEqual(drive('the_artist', rung, lambda t: M.P_DONE,
                                   seed=2, steps=50), [-1.0], rung)

    def test_doing_nothing_is_never_paid(self):
        self.assertEqual(drive('the_artist', 1, lambda t: None, seed=2,
                               steps=400), [])

    def test_a_photograph_rung_draws(self):
        self.assertEqual(drive('the_artist', 19, lambda t: M.P_DONE, seed=1,
                               steps=50), [-1.0])


if __name__ == '__main__':
    unittest.main()
