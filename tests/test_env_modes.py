#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Label aggregation, dual-modality play, gym knobs and curriculum.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from envsupport import (  # noqa: F401
    ENV_IMPORT_ERROR, DiagnosticEnv, NeuralWorkshopEnv, advance_to, bw,
    bwaccel, derive_public_outcome, diagnose_public_outcome, digest_rgba,
    next_scorable_stimulus, ports_for, render_significant_frame,
    requires_env, verify_public_outcome, verify_public_pixels)




class LabelAggregationTests(unittest.TestCase):
    def _frame(self, specs):
        """Build a 80x24 frame with colored column bands in the bottom quarter.

        specs: list of (x0, x1, rgb)
        """
        w, h = 80, 24
        pix = bytearray([10, 10, 10, 255] * (w * h))
        for x0, x1, rgb in specs:
            for y in range(18, 24):
                for x in range(x0, x1):
                    off = (y * w + x) * 4
                    pix[off:off + 3] = bytes(rgb)
        return bytes(pix), w, h

    def test_run_count_invariant_to_band_width(self):
        narrow, w, h = self._frame([(5, 10, (64, 255, 64)), (40, 45, (255, 64, 64))])
        wide, _, _ = self._frame([(5, 25, (64, 255, 64)), (40, 70, (255, 64, 64))])
        a = bwaccel.count_feedback_label_runs(narrow, w, h, 18, 24)
        b = bwaccel.count_feedback_label_runs(wide, w, h, 18, 24)
        self.assertEqual(a, (1, 1, 0))
        self.assertEqual(b, (1, 1, 0))
        oa = derive_public_outcome(narrow, w, h, ['d'], 1)
        ob = derive_public_outcome(wide, w, h, ['d'], 1)
        self.assertEqual(oa['scalar'], 0.0)
        self.assertEqual(ob['scalar'], 0.0)

    def test_two_correct_two_incorrect(self):
        two_g, w, h = self._frame([(4, 12, (64, 255, 64)), (30, 38, (64, 255, 64))])
        two_r, _, _ = self._frame([(4, 12, (255, 64, 64)), (30, 38, (255, 64, 64))])
        self.assertEqual(derive_public_outcome(two_g, w, h, ['d'], 1)['scalar'], 1.0)
        self.assertEqual(derive_public_outcome(two_r, w, h, ['d'], 1)['scalar'], -1.0)

    def test_miss_plus_correct(self):
        mix, w, h = self._frame([(4, 12, (64, 64, 255)), (30, 38, (64, 255, 64))])
        self.assertEqual(derive_public_outcome(mix, w, h, ['d'], 1)['scalar'], 0.0)


@requires_env
class DualModalityLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = DiagnosticEnv(seed=30, game_mode=2, num_trials=24)

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def _seek_ports(self, want_correct, want_incorrect, limit=80):
        for _ in range(limit):
            if not next_scorable_stimulus(self.env):
                return None, None
            c = ports_for('correct')
            i = ports_for('incorrect')
            if len(c) >= want_correct and len(i) >= want_incorrect:
                return c, i
            self.env.advance()
        return None, None

    def _feedback_scalar(self):
        while self.env.probe.phase() != 'feedback':
            self.env.advance()
            if self.env.probe.session_done():
                return None
        return diagnose_public_outcome(
            self.env._rgba, self.env._width, self.env._height,
            self.env._trial_digests,
            self.env._trial_receipt['receipt_id'])

    def test_dual_stimulus_publishes_waveform_not_letter_id(self):
        self.env.reset(30)
        found = None
        for _ in range(40):
            obs = self.env.observe()
            if self.env.probe.phase() == 'stimulus' and obs.get('audio_pcm'):
                found = obs
                break
            self.env.advance()
        self.assertIsNotNone(found)
        self.assertIsInstance(found['audio_pcm'], (bytes, bytearray))
        self.assertGreater(len(found['audio_pcm']), 0)
        self.assertGreater(int(found['audio_rate']), 0)
        self.assertNotIn('audio', found)
        self.assertNotIn('current_stim', found)
        self.assertNotIn('letter', found)

    def test_dual_one_correct_one_incorrect(self):
        self.env.reset(30)
        self.assertGreaterEqual(self.env.n_actions, 2)
        c, i = self._seek_ports(1, 1)
        self.assertIsNotNone(c)
        self.env.act([c[0], i[0]])
        out = self._feedback_scalar()
        self.assertIsNotNone(out)
        self.assertEqual(out['n_pos'], 1)
        self.assertEqual(out['n_neg'], 1)
        self.assertEqual(out['scalar'], 0.0)
        public = derive_public_outcome(
            self.env._rgba, self.env._width, self.env._height,
            self.env._trial_digests,
            self.env._trial_receipt['receipt_id'])
        self.assertNotIn('n_pos', public)
        self.assertNotIn('n_neg', public)

    def test_dual_two_correct(self):
        found = None
        for seed in range(31, 80):
            self.env.reset(seed)
            c, i = self._seek_ports(2, 0)
            if c and len(c) >= 2:
                self.env.act(c[:2])
                found = self._feedback_scalar()
                break
        self.assertIsNotNone(found, 'needed a two-match trial')
        self.assertEqual(found['n_pos'], 2)
        self.assertEqual(found['n_neg'], 0)
        self.assertEqual(found['scalar'], 1.0)

    def test_dual_two_incorrect(self):
        found = None
        for seed in range(32, 80):
            self.env.reset(seed)
            c, i = self._seek_ports(0, 2)
            if i and len(i) >= 2:
                self.env.act(i[:2])
                found = self._feedback_scalar()
                break
        self.assertIsNotNone(found, 'needed a two-nonmatch trial')
        self.assertEqual(found['n_pos'], 0)
        self.assertEqual(found['n_neg'], 2)
        self.assertEqual(found['scalar'], -1.0)

    def test_dual_one_missed_one_correct(self):
        found = None
        for seed in range(33, 80):
            self.env.reset(seed)
            c, i = self._seek_ports(2, 0)
            if c and len(c) >= 2:
                self.env.act(c[:1])  # press one match, miss the other
                found = self._feedback_scalar()
                break
        self.assertIsNotNone(found, 'needed a two-match trial to miss one')
        self.assertEqual(found['n_pos'], 1)
        self.assertEqual(found['n_neg'], 1)
        self.assertEqual(found['scalar'], 0.0)


@requires_env
class GymConfigTests(unittest.TestCase):
    """Constructor-owned session knobs. Training must not poke bw.cfg."""

    def test_constructor_applies_and_keeps_session_knobs(self):
        env = DiagnosticEnv(
            seed=8,
            game_mode=10,
            num_trials=12,
            n_back=3,
            grid_size=3,
            active_cells=2,
        )
        try:
            self.assertEqual(bw.mode.mode, 10)
            self.assertEqual(bw.mode.back, 3)
            self.assertEqual(bw.mode.num_trials_total, 12)
            self.assertEqual(bw.cfg.GRID_SIZE, 3)
            self.assertEqual(bw.cfg.ACTIVE_POSITION_CELLS, 2)
            self.assertFalse(bw.cfg.USE_MUSIC)
            self.assertTrue(bw.mode.manual)
            env.reset(9)
            self.assertEqual(bw.mode.back, 3)
            self.assertEqual(bw.mode.num_trials_total, 12)
            self.assertEqual(len(bw.current_active_position_ids()), 2)
        finally:
            env.close()
            bw.cfg.GRID_SIZE = 3
            bw.cfg.ACTIVE_POSITION_CELLS = 0
            bw.cfg.POSITION_CELL_COUNT = 0
            bw.cfg.GAME_MODE = 2
            bw.mode.mode = 2
            bw.mode.back = 2

    def test_dual_constructor_sets_two_ports_and_depth(self):
        env = DiagnosticEnv(
            seed=11, game_mode=2, num_trials=8, n_back=1,
        )
        try:
            self.assertEqual(bw.mode.mode, 2)
            self.assertEqual(bw.mode.back, 1)
            self.assertEqual(env.n_actions, 2)
        finally:
            env.close()


class CurriculumTests(unittest.TestCase):
    def test_grid_coverage_full_and_subset(self):
        for n in (2, 3, 4, 5, 8, 16, 32):
            total = bwaccel.grid_cell_count(n, False)
            full = bwaccel.active_position_ids(n, False, 0)
            self.assertEqual(len(full), total, 'full %sx%s' % (n, n))
            if total >= 4:
                subset = bwaccel.active_position_ids(n, False, 4)
                self.assertEqual(len(subset), 4)
                self.assertTrue(set(subset).issubset(set(full)))

if __name__ == '__main__':
    unittest.main(verbosity=2)
