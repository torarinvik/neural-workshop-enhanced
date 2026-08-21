#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A painted verdict is read by the deriver that already exists.

This is the whole claim behind :mod:`neural_workshop.ui.verdict`. The agent
boundary can already turn pixels into a public scalar and can already verify
one, natively and under test. Three tasks were nonetheless wrapped with a
bespoke deriver and a bespoke verifier apiece -- about a hundred lines each,
and two functions that have to agree while being edited apart.

If a label painted by ``VerdictLabel`` derives to +1 and -1 through the
*default* reader, then a task that paints it needs neither, and the saving is
not an estimate.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import UI_IMPORT_ERROR

if UI_IMPORT_ERROR is None:
    import bwaccel
    import pyglet

    from neural_workshop import state
    from neural_workshop.ui.verdict import (VerdictLabel, above_the_band,
                                            band_rows)
    from nwenv.frames import capture_rgba, digest_rgba
    from nwenv.outcome import derive_public_outcome
    from nwenv.taskenv import TaskEnv


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class VerdictIsDerivable(unittest.TestCase):

    def setUp(self):
        # Its own batch, so the frame carries the verdict and nothing else.
        # A bare application window already contributes one blue run of
        # persistent furniture to the band, which would be read as a verdict.
        self.batch = pyglet.graphics.Batch()
        self.verdict = VerdictLabel(batch=self.batch)

    def tearDown(self):
        self.verdict.delete()

    def frame(self):
        """Draw once and read the pixels back, as the boundary does."""
        window = state.window
        window.switch_to()
        window.dispatch_events()
        window.clear()
        self.batch.draw()
        return capture_rgba(window)

    def scalar(self):
        width, height, rgba = self.frame()
        outcome = derive_public_outcome(rgba, width, height, ['x'], 1)
        return None if outcome is None else outcome['scalar']

    def test_a_good_verdict_derives_positive(self):
        self.verdict.show(True)
        self.assertEqual(self.scalar(), 1.0)

    def test_a_bad_verdict_derives_negative(self):
        self.verdict.show(False)
        self.assertEqual(self.scalar(), -1.0)

    def test_nothing_painted_derives_to_none(self):
        """None is not zero: an unresolved trial has no scalar at all."""
        self.verdict.clear()
        self.assertIsNone(self.scalar())

    def test_clearing_takes_a_verdict_back_down(self):
        """A verdict left up would be derived again by the next trial."""
        self.verdict.show(True)
        self.assertEqual(self.scalar(), 1.0)
        self.verdict.clear()
        self.assertIsNone(self.scalar())

    def test_a_stray_saturated_colour_in_the_band_is_read_as_a_verdict(self):
        """The constraint a task painting here has to respect."""
        stray = pyglet.shapes.Rectangle(
            0, 0, 40, 40, color=(255, 0, 0), batch=self.batch)
        try:
            self.assertEqual(self.scalar(), -1.0)
        finally:
            stray.delete()

    def test_the_task_s_own_words_do_not_change_the_scalar(self):
        """Text is for the person; only the colour is public."""
        self.verdict.show(True, 'Out in 12 steps, the minimum was 12')
        self.assertEqual(self.scalar(), 1.0)
        self.verdict.show(False, 'Out in 30 steps, the minimum was 12')
        self.assertEqual(self.scalar(), -1.0)


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class WhereTheBandIs(unittest.TestCase):
    """The layout helper and the pixel reader must mean the same rows.

    :func:`above_the_band` is what a task's layout calls to keep its
    art out of the strip the boundary reads, and it works that strip
    out itself rather than importing it. Two opinions about where the
    band is would be worse than one wrong one: the task would lay out
    against a line the reader does not use, look right, and be paid
    off its own scenery on some window sizes and not others.
    """

    def test_it_agrees_with_the_reader_at_every_size(self):
        for height in (480, 600, 720, 768, 1000, 1001, 1080, 1368, 2160):
            self.assertEqual(band_rows(height), bwaccel.default_band(height),
                             'height %d' % height)

    def test_the_floor_it_gives_is_above_the_band(self):
        """In screen coordinates, where the bottom row is y=0."""
        height = state.window.height
        first_row, _past = band_rows(height)
        self.assertGreaterEqual(above_the_band(), height - first_row)

    def test_it_never_lowers_a_layout_that_was_already_clear(self):
        self.assertEqual(above_the_band(state.window.height),
                         state.window.height)

    def test_it_raises_one_that_was_not(self):
        self.assertGreater(above_the_band(0), 0)

    def test_it_leaves_room_for_an_anti_aliased_edge(self):
        """The reason it is not simply the band's own first row.

        An orange square on a pale page is edged by every blend
        between the two, and part of that ramp reads as a verdict —
        which is how the Maze came to be paid off its own doors. The
        art stopping *at* the line still puts its blend across it.
        """
        height = state.window.height
        self.assertGreater(above_the_band(), height - band_rows(height)[0])


@unittest.skipIf(UI_IMPORT_ERROR is not None, str(UI_IMPORT_ERROR))
class WholeTaskNeedsNeither(unittest.TestCase):
    """A task that paints the label writes no deriver and no verifier.

    This is the claim the whole arrangement rests on, so it is tested against
    a real painted frame rather than a fixture: the subclass below declares
    four things and inherits everything that turns pixels into a checked
    public outcome.
    """

    class Painted(TaskEnv):
        ports = 4

        def build(self, seed, **dials):
            return object()

        def drive(self, task, port):
            self.last = port

    def setUp(self):
        self.batch = pyglet.graphics.Batch()
        self.verdict = VerdictLabel(batch=self.batch)

    def tearDown(self):
        self.verdict.delete()

    def frame(self):
        window = state.window
        window.switch_to()
        window.dispatch_events()
        window.clear()
        self.batch.draw()
        return capture_rgba(window)

    def test_the_inherited_deriver_reads_a_painted_verdict(self):
        for good, expected in ((True, 1.0), (False, -1.0)):
            with self.subTest(good=good):
                self.verdict.show(good)
                width, height, rgba = self.frame()
                outcome = self.Painted.derive(rgba, width, height, ['x'], 1)
                self.assertEqual(outcome['scalar'], expected)

    def test_the_generated_verifier_accepts_what_the_deriver_read(self):
        self.verdict.show(True)
        width, height, rgba = self.frame()
        digest = digest_rgba(rgba)
        outcome = self.Painted.derive(rgba, width, height, [digest], 1,
                                      frame_seq=0, timestamp_ns=0)
        ledger = {1: {'stimulus_digest': digest,
                      'evidence_digests': [digest],
                      'feedback_digest': digest}}
        verify = self.Painted.verifier()
        self.assertTrue(verify(outcome, rgba, width, height,
                               archive={digest: rgba},
                               receipt_ledger=ledger))

    def test_the_generated_verifier_rejects_a_tampered_scalar(self):
        """The point of deriving from pixels: a claim must be visible."""
        self.verdict.show(False)
        width, height, rgba = self.frame()
        digest = digest_rgba(rgba)
        outcome = self.Painted.derive(rgba, width, height, [digest], 1,
                                      frame_seq=0, timestamp_ns=0)
        self.assertEqual(outcome['scalar'], -1.0)
        outcome['scalar'] = 1.0          # claim a win the frame does not show
        ledger = {1: {'stimulus_digest': digest,
                      'evidence_digests': [digest],
                      'feedback_digest': digest}}
        verify = self.Painted.verifier()
        self.assertFalse(verify(outcome, rgba, width, height,
                                archive={digest: rgba},
                                receipt_ledger=ledger))


if __name__ == '__main__':
    unittest.main()
