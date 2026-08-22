#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""What the glyph distorter is worth, measured rather than asserted.

Three things are being checked, and they are not the same kind of thing.

The **rules** are geometry, so they are checked as geometry: a warp that
does not fold, an inverse that inverts, a budget that is spent. None of
that needs a window and none of it needs a font, so most of this file
runs anywhere.

The **ladder** is a claim about difficulty, and difficulty is not
something a shape can be asked about — so it is measured, with the weak
recogniser in :mod:`neural_workshop.glyphs` and held-out typefaces. The
version here is deliberately small; ``bench_glyphs.py`` runs the whole
column and is where the numbers in the module docstring came from.

And the **signature** is checked against the thing that broke it once.
A single speck of noise in a corner used to double the box the grid was
measured in, which moved every cell boundary, so the speckle knob was
scored as if it had destroyed a letter it had barely touched. That is
:class:`ASpeckIsNotADistortion`, and it fails without :data:`TRIM`.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import random
import unittest

from uisupport import UI_IMPORT_ERROR

from neural_workshop import glyphs as G

if UI_IMPORT_ERROR is None:
    from neural_workshop.ui import glyphs as UG

#: The alphabet every measurement here asks for.
LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

#: Small on purpose: this file wants a signal, not the whole column.
ASK_LETTERS = 'ACEGKMORTW'


def block(width: int, height: int, *boxes) -> G.Coverage:
    """A coverage with the given rectangles filled in. Pixels, not fonts."""
    cov = G.Coverage(width, height)
    for left, top, right, bottom in boxes:
        for y in range(top, bottom):
            for x in range(left, right):
                cov.alpha[y * width + x] = 255
    return cov


def an_ell(size: int = 32) -> G.Coverage:
    """An L. Lopsided in both axes, which is what a signature needs."""
    return block(size, size, (8, 6, 12, 26), (8, 22, 24, 26))


def _pool():
    """Latin-capable families here, split into train and held out."""
    found = G.families(G.platform_dirs(), must_draw=LETTERS)
    names = [name for name in
             (UG.register(paths[0]) for paths in found.values()) if name]
    train, _val, test = G.split(names, seed=7)
    return train, test


class TheMatrixIsAMatrix(unittest.TestCase):
    """The affine and perspective part, checked as arithmetic."""

    def test_an_inverse_undoes_the_thing_it_inverts(self):
        forward = G.homography(stretch_x=1.3, stretch_y=0.8, shear=0.2,
                               turn=math.radians(17), tilt_x=0.2,
                               tilt_y=-0.1)
        back = G.mat_inverse(forward)
        for x, y in ((0.0, 0.0), (1.0, 0.0), (0.5, 0.5), (0.2, 0.9)):
            there = G.mat_apply(forward, x, y)
            here = G.mat_apply(back, *there)
            self.assertAlmostEqual(here[0], x, places=6)
            self.assertAlmostEqual(here[1], y, places=6)

    def test_the_product_of_the_two_is_the_identity(self):
        forward = G.homography(stretch_x=0.7, shear=-0.3, tilt_y=0.25)
        product = G.mat_mul(forward, G.mat_inverse(forward))
        scale = product[8]
        for got, want in zip(product, G.IDENTITY):
            self.assertAlmostEqual(got / scale, want, places=6)

    def test_a_flattened_warp_is_refused_rather_than_returned(self):
        # A zero-width stretch is not a hard warp, it is not a warp:
        # every point of the letter lands on one line. Returning some
        # enormous number instead would show up much later as a stamp
        # that is a single smeared column, a long way from the cause.
        with self.assertRaises(ValueError):
            G.mat_inverse(G.homography(stretch_x=0.0))

    def test_a_turn_about_the_centre_leaves_the_centre_alone(self):
        turned = G.homography(turn=math.radians(30))
        x, y = G.mat_apply(turned, 0.5, 0.5)
        self.assertAlmostEqual(x, 0.5, places=9)
        self.assertAlmostEqual(y, 0.5, places=9)


class NoDealFoldsTheLetterOverItself(unittest.TestCase):
    """The one property that makes a warp a rearrangement of a letter.

    A folded map sends two places to the same place, and the letter that
    comes back has had a piece of itself pasted over another piece. That
    is not a hard letter, it is a different letter, and the ladder would
    be measuring damage it cannot describe.

    Checked by walking the Jacobian rather than by trusting the budget
    that is supposed to prevent it, because the budget is an argument
    and the determinant is the fact.
    """

    def test_every_rung_stays_the_right_way_round(self):
        worst = {}
        for rung in range(1, len(G.GRADES) + 1):
            least = None
            for seed in range(60):
                warp = G.deal(rung, random.Random(seed)).warp
                det = G.fold_free(warp, steps=12)
                if least is None or det < least:
                    least = det
            worst[rung] = least
            self.assertGreater(least, 0.0,
                               'rung %d folds: %.3f' % (rung, least))
        # And the room left shrinks as the ladder climbs, which is the
        # ladder doing what it says rather than merely staying legal.
        self.assertLess(worst[len(G.GRADES)], worst[1])

    def test_the_ripple_budget_is_per_axis_and_is_spent(self):
        for rung in range(2, len(G.GRADES) + 1):
            grade = G.grade_of(rung)
            if not grade.waves:
                continue
            warp = G.deal(rung, random.Random(rung * 31)).warp
            for axis in (0, 1):
                spent = warp.slope(axis)
                if not spent:
                    continue
                self.assertAlmostEqual(spent, G.RIPPLE_SLOPE * grade.ripple,
                                       places=6)


class ARungIsABox(unittest.TestCase):
    """Dealing: repeatable, bounded, and independent knob by knob."""

    def test_the_same_seed_deals_the_same_appearance(self):
        one = G.deal(7, random.Random(99))
        two = G.deal(7, random.Random(99))
        self.assertEqual(one, two)
        self.assertNotEqual(one, G.deal(7, random.Random(100)))

    def test_nothing_is_dealt_outside_its_rung(self):
        for rung in range(1, len(G.GRADES) + 1):
            grade = G.grade_of(rung)
            for seed in range(40):
                dealt = G.deal(rung, random.Random(seed))
                self.assertLessEqual(abs(dealt.thickness),
                                     grade.thickness + 1e-9)
                self.assertLessEqual(dealt.speckle, grade.speckle + 1e-9)
                self.assertGreaterEqual(dealt.contrast, grade.contrast - 1e-9)
                covered = sum(bar.width * bar.height for bar in dealt.bars)
                # Bars may overlap, so this bounds what was *asked* for
                # rather than what is actually hidden.
                self.assertLessEqual(covered, grade.occlusion + 0.22)

    def test_the_first_rung_is_very_nearly_a_clean_page(self):
        for seed in range(40):
            dealt = G.deal(1, random.Random(seed))
            self.assertEqual(dealt.bars, ())
            self.assertEqual(dealt.warp.ripple, ())
            self.assertEqual(dealt.speckle, 0.0)
            self.assertEqual(dealt.contrast, 1.0)

    def test_the_ladder_widens_every_knob_it_names(self):
        for earlier, later in zip(G.GRADES, G.GRADES[1:]):
            for knob in ('stretch', 'shear', 'turn', 'tilt', 'ripple',
                         'speckle', 'occlusion'):
                self.assertGreaterEqual(getattr(later, knob),
                                        getattr(earlier, knob), knob)
            self.assertLessEqual(later.contrast, earlier.contrast)


class WhatAStampDoesToPixels(unittest.TestCase):
    """The pipeline, on hand-drawn rectangles rather than on typefaces."""

    def test_growing_and_eating_the_ink_go_opposite_ways(self):
        ell = an_ell()
        self.assertGreater(G.thicken(ell, 2.0).ink(), ell.ink())
        self.assertLess(G.thicken(ell, -1.0).ink(), ell.ink())

    def test_a_radius_under_half_a_pixel_is_left_alone(self):
        ell = an_ell()
        self.assertEqual(G.thicken(ell, 0.4).alpha, ell.alpha)

    def test_a_letter_is_fitted_by_its_ink_and_not_by_its_frame(self):
        # The same L, once in the corner of a big empty rectangle and
        # once snug. A stamp of either should be the same picture: what
        # is fitted is the ink, not the paper it arrived on.
        snug = block(16, 24, (0, 0, 4, 20), (0, 16, 14, 20))
        loose = block(48, 48, (0, 0, 4, 20), (0, 16, 14, 20))
        plain = G.Distortion(G.Warp.of(G.IDENTITY), 0.0, 0.0, (), 1.0)
        one = G.stamp(snug, plain, 32)
        two = G.stamp(loose, plain, 32)
        self.assertEqual(one.bounds(), two.bounds())

    def test_an_empty_letter_stamps_to_an_empty_square(self):
        blank = G.Coverage(8, 8)
        out = G.stamp(blank, G.deal(9, random.Random(1)), 24)
        self.assertEqual(out.width, 24)
        self.assertEqual(out.ink(), 0)

    def test_a_bar_takes_out_the_rows_it_covers_and_no_others(self):
        solid = block(32, 32, (0, 0, 32, 32))
        across = G.Distortion(G.Warp.of(G.IDENTITY), 0.0, 0.0,
                              (G.Bar(0.0, 0.25, 1.0, 0.25),), 1.0)
        out = G.stamp(solid, across, 40, margin=0.0)
        rows = [any(out.alpha[y * 40 + x] for x in range(40))
                for y in range(40)]
        self.assertFalse(any(rows[10:20]))
        self.assertTrue(rows[0] and rows[39])

    def test_fading_the_ink_leaves_it_where_it_was(self):
        # Contrast is a change of colour, not of shape. Anything else
        # would make it a second thickness knob wearing another name.
        ell = an_ell()
        plain = G.Distortion(G.Warp.of(G.IDENTITY), 0.0, 0.0, (), 1.0)
        faint = plain._replace(contrast=0.6)
        full = G.stamp(ell, plain, 32)
        dim = G.stamp(ell, faint, 32)
        self.assertLess(dim.weight(), full.weight())
        self.assertEqual([bool(value) for value in dim.alpha],
                         [bool(value) for value in full.alpha])


class ASpeckIsNotADistortion(unittest.TestCase):
    """The regression that the trimmed ink box exists for.

    Without it a signature is measured inside the box that holds *all*
    the ink, so one lit pixel in a corner moves every cell boundary and
    the letter is scored as though it had been rearranged. The knob it
    made unreadable was speckle, and the damage was not small: the
    ladder's second rung read 0.57 with a bare box and 0.88 with this
    one, against a first rung of 0.90 either way.
    """

    def speckled(self):
        clean = an_ell()
        dirty = G.Coverage(clean.width, clean.height, bytearray(clean.alpha))
        dirty.alpha[1] = 255                      # top-right of an empty row
        dirty.alpha[len(dirty.alpha) - 2] = 255   # and the far corner
        return clean, dirty

    def test_two_specks_barely_move_a_trimmed_signature(self):
        clean, dirty = self.speckled()
        moved = G.distance(G.signature(clean), G.signature(dirty))
        self.assertLess(moved, 0.10)

    def test_the_same_two_specks_wreck_an_untrimmed_one(self):
        clean, dirty = self.speckled()
        moved = G.distance(G.signature(clean, trim=0.0),
                           G.signature(dirty, trim=0.0))
        self.assertGreater(moved, 0.7)

    def test_a_signature_is_a_share_of_the_ink(self):
        self.assertAlmostEqual(sum(G.signature(an_ell())), 1.0, places=6)

    def test_an_empty_square_is_equally_far_from_every_letter(self):
        self.assertEqual(sum(G.signature(G.Coverage(8, 8))), 0.0)

    def test_where_the_letter_sits_and_how_big_it_is_are_not_the_answer(self):
        # The same L twice over: once small in a corner, once twice the
        # size in the middle. Position and scale are knobs this module
        # turns, so a recogniser they alone could beat would be scoring
        # the knobs rather than the damage.
        small = block(40, 40, (2, 2, 4, 12), (2, 10, 10, 12))
        large = block(40, 40, (20, 16, 24, 36), (20, 32, 36, 36))
        solid = block(40, 40, (0, 0, 40, 40))
        moved = G.distance(G.signature(small), G.signature(large))
        different = G.distance(G.signature(small), G.signature(solid))
        # Not zero: an eight-cell grid over a ten-pixel box and over a
        # twenty-pixel one do not bin the same way. Small against a
        # shape that really is another shape, which is the comparison
        # that matters.
        self.assertLess(moved, 0.2)
        self.assertGreater(different, moved * 5)


class HeldOutMeansHeldOut(unittest.TestCase):
    """Splitting: by family, repeatably, with nothing on both sides."""

    NAMES = ['face %02d' % index for index in range(40)]

    def test_no_family_is_in_two_parts(self):
        train, val, test = G.split(self.NAMES, seed=3)
        self.assertFalse(set(train) & set(val))
        self.assertFalse(set(train) & set(test))
        self.assertFalse(set(val) & set(test))
        self.assertEqual(sorted(train + val + test), sorted(self.NAMES))

    def test_the_same_seed_splits_the_same_way(self):
        self.assertEqual(G.split(self.NAMES, seed=3),
                         G.split(self.NAMES, seed=3))
        self.assertNotEqual(G.split(self.NAMES, seed=3),
                            G.split(self.NAMES, seed=4))

    def test_the_shares_are_roughly_what_was_asked_for(self):
        train, val, test = G.split(self.NAMES, seed=0, shares=(.5, .25, .25))
        self.assertEqual(len(train), 20)
        self.assertEqual(len(val), 10)
        self.assertEqual(len(test), 10)


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class TypefacesOnThisMachine(unittest.TestCase):
    """Reading real font files, which is where the leak was."""

    def test_a_family_is_read_from_the_font_and_not_from_the_filename(self):
        found = G.families(G.platform_dirs())
        if not found:
            self.skipTest('no fonts on this machine')
        # Some family somewhere has more than one file: that is the
        # case the whole family-level split exists for, and if it never
        # happened here the split would be untested rather than fine.
        biggest = max(len(paths) for paths in found.values())
        self.assertGreaterEqual(biggest, 2)
        for family, paths in found.items():
            for path in paths:
                self.assertEqual(G.face_name(path)[0], family)

    def test_most_families_here_cannot_draw_a_capital_a(self):
        # The finding that invalidated the first ladder measurement: a
        # font with no Latin in it still hands back a beautiful A,
        # because the platform quietly substitutes one. Filtering on
        # the font's own cmap is what makes a held-out family held out.
        every = G.families(G.platform_dirs())
        latin = G.families(G.platform_dirs(), must_draw=LETTERS)
        if not every:
            self.skipTest('no fonts on this machine')
        self.assertLessEqual(set(latin), set(every))
        self.assertTrue(latin, 'no Latin typefaces at all')
        self.assertLess(len(latin), len(every))

    def test_a_font_that_claims_the_alphabet_really_draws_it(self):
        latin = G.families(G.platform_dirs(), must_draw=LETTERS)
        if not latin:
            self.skipTest('no Latin typefaces on this machine')
        for family, paths in sorted(latin.items())[:6]:
            ranges = G.covered(paths[0])
            self.assertTrue(G.draws(ranges, LETTERS))
            # And a codepoint no text font claims: a range list that
            # says yes to everything would pass the line above.
            self.assertFalse(G.draws(ranges, '\U000E0100'))


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class FromATypefaceToSomethingDrawable(unittest.TestCase):
    """The pyglet half: coverage in, image out, and the row order."""

    def setUp(self):
        latin = G.families(G.platform_dirs(), must_draw=LETTERS)
        if not latin:
            self.skipTest('no Latin typefaces on this machine')
        self.family = None
        for _name, paths in sorted(latin.items()):
            self.family = UG.register(paths[0])
            if self.family:
                break
        if not self.family:
            self.skipTest('pyglet would not take any font here')
        UG.forget()

    def test_a_letter_arrives_with_ink_in_it(self):
        cov = UG.coverage(self.family, 'A')
        self.assertGreater(cov.ink(), 0)
        self.assertIsNotNone(cov.bounds())

    def test_two_letters_are_two_letters(self):
        self.assertNotEqual(UG.coverage(self.family, 'I').ink(),
                            UG.coverage(self.family, 'W').ink())

    def test_the_same_four_arguments_deal_the_same_picture(self):
        one = UG.dealt(self.family, 'R', 6, 4242, size=32)
        two = UG.dealt(self.family, 'R', 6, 4242, size=32)
        other = UG.dealt(self.family, 'R', 6, 4243, size=32)
        self.assertEqual(one.alpha, two.alpha)
        self.assertNotEqual(one.alpha, other.alpha)

    def test_the_rows_come_back_the_way_pyglet_wants_them(self):
        # A coverage runs top-down and an ImageData runs bottom-up. The
        # flip happens in one place; this is the test that says which
        # way. Ink in the coverage's first row must land in the image's
        # last one, and getting it backwards would be invisible in
        # anything but an asymmetric letter.
        cov = block(4, 4, (0, 0, 4, 1))
        raw = UG.image_of(cov).get_data('RGBA', 4 * 4)
        top = [raw[(3 * 4 + x) * 4 + 3] for x in range(4)]
        bottom = [raw[x * 4 + 3] for x in range(4)]
        self.assertEqual(top, [255] * 4)
        self.assertEqual(bottom, [0] * 4)

    def test_ink_alone_is_carried_by_alpha_and_paper_makes_it_opaque(self):
        cov = block(2, 2, (0, 0, 1, 2))
        floating = UG.image_of(cov, ink=(20, 30, 40))
        raw = floating.get_data('RGBA', 2 * 4)
        self.assertEqual((raw[0], raw[1], raw[2], raw[3]), (20, 30, 40, 255))
        self.assertEqual(raw[7], 0)
        on_paper = UG.image_of(cov, ink=(0, 0, 0), paper=(255, 255, 255))
        raw = on_paper.get_data('RGBA', 2 * 4)
        self.assertEqual(raw[3], 255)
        self.assertEqual(raw[7], 255)
        self.assertEqual((raw[4], raw[5], raw[6]), (255, 255, 255))

    def test_a_stamp_asked_for_twice_is_only_made_once(self):
        UG.forget()
        one = UG.stamp_image(self.family, 'K', 3, 11, size=24)
        self.assertIs(one, UG.stamp_image(self.family, 'K', 3, 11, size=24))
        UG.forget()
        self.assertIsNot(one, UG.stamp_image(self.family, 'K', 3, 11, size=24))


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class TheLadderIsWorthSomething(unittest.TestCase):
    """A short version of the measurement in the module docstring.

    Ten letters and four held-out families rather than twenty-six and
    ten, because this runs in the suite. It is enough to catch a rung
    that has stopped costing anything and not enough to quote; the
    numbers in :mod:`neural_workshop.glyphs` come from
    ``bench_glyphs.py``, which runs the whole thing.
    """

    @classmethod
    def setUpClass(cls):
        if UI_IMPORT_ERROR is not None:
            return
        train, test = _pool()
        cls.train, cls.test = train[:12], test[:4]

    def setUp(self):
        if len(self.train) < 6 or len(self.test) < 2:
            self.skipTest('too few Latin typefaces here to hold any out')

    def templates(self):
        return {letter: [G.signature(UG.coverage(family, letter))
                         for family in self.train]
                for letter in ASK_LETTERS}

    def score(self, rung, templates):
        right = 0
        asked = 0
        rng = random.Random(4000 + rung)
        for letter in ASK_LETTERS:
            for family in self.test:
                cov = UG.dealt(family, letter, rung, rng.randrange(10 ** 6),
                               size=48)
                asked += 1
                if G.recognise(G.signature(cov), templates) == letter:
                    right += 1
        return right / float(asked)

    def test_a_clean_page_is_readable_and_the_last_rung_is_not(self):
        templates = self.templates()
        top = self.score(1, templates)
        bottom = self.score(len(G.GRADES), templates)
        floor = 1.0 / len(ASK_LETTERS)
        # The ceiling is not 1.0 and is not supposed to be: these are
        # typefaces the templates have never seen. What is being
        # checked is the fall, and that the fall is most of the way
        # down to guessing.
        self.assertGreater(top, 0.6, 'rung 1 unreadable: %.2f' % top)
        self.assertLess(bottom, top / 2.0,
                        'the ladder is flat: %.2f then %.2f' % (top, bottom))
        self.assertLess(bottom, floor + 0.25)

    def test_a_rung_in_the_middle_lands_in_the_middle(self):
        templates = self.templates()
        middle = self.score(5, templates)
        self.assertGreater(middle, self.score(len(G.GRADES), templates))
        self.assertLess(middle, self.score(1, templates))


if __name__ == '__main__':
    unittest.main(verbosity=2)
