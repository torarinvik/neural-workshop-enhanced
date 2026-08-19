#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Determinism, and parity between stepping and the scheduled clock.

The parity tests hide the window, so they prove stepped-versus-
scheduled parity rather than literal visible-window execution.

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


@requires_env
class DeterminismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = DiagnosticEnv(seed=0)

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def _trace(self, seed, n=8):
        obs = self.env.reset(seed)
        frames = [digest_rgba(obs['rgba'])]
        receipts = [tuple(self.env._trial_receipt['ports'])]
        outcomes = []
        stims = [dict(self.env.probe.stim())]
        for _ in range(n):
            obs, ev, done = self.env.step(None)
            frames.append(digest_rgba(obs['rgba']))
            receipts.append(tuple(self.env._trial_receipt['ports'])
                            if self.env._trial_receipt else None)
            if self.env.probe.phase() == 'stimulus':
                stims.append(dict(self.env.probe.stim()))
            for e in ev:
                if e.get('type') == 'outcome':
                    outcomes.append(e['scalar'])
            if done:
                break
        return frames, receipts, outcomes, stims

    def test_seed_zero_and_nonzero_repeat(self):
        for seed in (0, 1, 42):
            a = self._trace(seed, 6)
            b = self._trace(seed, 6)
            self.assertEqual(a[0], b[0], 'frame digests seed=%s' % seed)
            self.assertEqual(a[1], b[1], 'receipts seed=%s' % seed)
            self.assertEqual(a[2], b[2], 'outcomes seed=%s' % seed)
            self.assertEqual(a[3], b[3], 'stims seed=%s' % seed)


@requires_env
class ParityTests(unittest.TestCase):
    """Stepped vs scheduled ``update()`` parity with the window hidden.

    Limitation: this is not literal visible-window parity. The scheduled
    path calls ``window.set_visible(False)``. Pixel, action, input,
    outcome, and termination checks still run on the full session.
    """
    @classmethod
    def setUpClass(cls):
        cls.env = DiagnosticEnv(seed=13, game_mode=2, num_trials=6)

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    @staticmethod
    def _policy(trial_number):
        if trial_number <= 2:
            return []
        return [0] if trial_number % 2 == 0 else []

    def _bootstrap_clock_session(self, seed):
        random.seed(seed)
        bwaccel.seed(seed)
        if bw.mode.started:
            bw.end_session(cancelled=True)
        bw.mode.step_mode = True
        bw.mode.session_done = False
        bw.mode.phase = None
        bw.mode.session_number = 0
        bw.mode.progress = 0
        bw.cfg.SHOW_FEEDBACK = True
        bw.cfg.ANIMATE_SQUARES = False
        bw.mode.hide_text = False
        bw.mode.mode = 2
        bw.cfg.GAME_MODE = 2
        bw.mode.num_trials = 6
        bw.mode.num_trials_factor = 0
        bw.mode.num_trials_total = 6
        bw.new_session()
        bw.mode.tick = 0
        bw.mode.phase = None
        bw.mode.session_number = 1
        bw.mode.num_trials = 6
        bw.mode.num_trials_factor = 0
        bw.mode.num_trials_total = 6
        random.seed(seed)
        bwaccel.seed(seed)
        bw.mode.step_mode = False

    def test_step_vs_scheduled_update_parity(self):
        """Full-session step vs scheduled update(); window stays hidden."""
        seed = 13
        env = self.env
        first = env.reset(seed)
        self.assertEqual(env.probe.phase(), 'stimulus')
        rec0 = env.act(self._policy(bw.mode.trial_number), logp=-0.5)
        step_digests = [digest_rgba(first['rgba'])]
        step_stims = [dict(env.probe.stim())]
        step_receipts = [(rec0.get('receipt_id'), tuple(rec0.get('ports') or ()),
                          rec0.get('logp'))]
        step_outcomes = []
        step_inputs = []
        step_term = False
        while True:
            obs, ev, done = env.step(None)
            step_digests.append(digest_rgba(obs['rgba']))
            phase = env.probe.phase()
            if phase == 'stimulus':
                step_stims.append(dict(env.probe.stim()))
                rec = env.act(self._policy(bw.mode.trial_number),
                              logp=-0.5 if bw.mode.trial_number % 2 == 0 else None)
                step_receipts.append((
                    rec.get('receipt_id'), tuple(rec.get('ports') or ()),
                    rec.get('logp')))
            if phase == 'feedback':
                step_inputs.append(dict(bw.mode.inputs))
            for e in ev:
                if e.get('type') == 'outcome':
                    step_outcomes.append(e['scalar'])
            if done:
                step_term = True
                break
            if len(step_digests) > 80:
                self.fail('step path did not terminate')
        step_trial = bw.mode.trial_number
        step_session = {
            'position1': list(bw.stats.session.get('position1', [])),
            'audio': list(bw.stats.session.get('audio', [])),
            'position1_input': list(bw.stats.session.get('position1_input', [])),
            'audio_input': list(bw.stats.session.get('audio_input', [])),
        }
        step_stats = env.accounting.snapshot()
        sessions_today = bw.stats.sessions_today

        self._bootstrap_clock_session(seed)
        bw.stats.sessions_today = sessions_today
        try:
            bw.window.set_visible(False)
        except Exception:
            pass
        clock_digests = []
        clock_stims = []
        clock_receipts = []
        clock_outcomes = []
        clock_inputs = []
        last_phase = None
        guard = 0
        clock_term = False
        while guard < 20000:
            bw.update(0.001)
            ph = bw.mode.phase
            if ph and ph != last_phase:
                # Capture *before* injecting, matching step: publish then act.
                w, h, rgba = render_significant_frame()
                clock_digests.append(digest_rgba(rgba))
                if ph == 'stimulus':
                    clock_stims.append(dict(bw.mode.current_stim))
                    names = bw.action_button_names()
                    ports = self._policy(bw.mode.trial_number)
                    buttons = [names[i] for i in ports if 0 <= i < len(names)]
                    bw.inject_match_action(buttons)
                    clock_receipts.append((
                        bw.mode.trial_number, tuple(ports),
                        -0.5 if bw.mode.trial_number % 2 == 0 else None))
                if ph == 'feedback':
                    clock_inputs.append(dict(bw.mode.inputs))
                    out = derive_public_outcome(
                        rgba, w, h, [digest_rgba(rgba)], bw.mode.trial_number)
                    if out is not None:
                        clock_outcomes.append(out['scalar'])
                last_phase = ph
            if bw.mode.phase == 'done' or not bw.mode.started:
                clock_term = True
                break
            guard += 1
        try:
            bw.window.set_visible(False)
        except Exception:
            pass
        bw.mode.step_mode = True
        clock_session = {
            'position1': list(bw.stats.session.get('position1', [])),
            'audio': list(bw.stats.session.get('audio', [])),
            'position1_input': list(bw.stats.session.get('position1_input', [])),
            'audio_input': list(bw.stats.session.get('audio_input', [])),
        }

        self.assertTrue(step_term)
        self.assertTrue(clock_term)
        self.assertEqual(step_stims, clock_stims)
        # In-session frames must match. The post-session analysis overlay
        # includes session counters / timestamps, so the terminal digest is
        # not part of the trial protocol.
        self.assertGreaterEqual(len(step_digests), 2)
        self.assertEqual(len(step_digests), len(clock_digests))
        self.assertEqual(step_digests[:-1], clock_digests[:-1])
        self.assertEqual([r[1] for r in step_receipts],
                         [r[1] for r in clock_receipts])
        self.assertEqual(step_inputs, clock_inputs)
        self.assertEqual(step_outcomes, clock_outcomes)
        self.assertTrue(any(s == 1.0 for s in step_outcomes)
                        or any(s == -1.0 for s in step_outcomes)
                        or any(s == 0.0 for s in step_outcomes),
                        'parity session produced no public outcomes')
        self.assertEqual(step_trial, bw.mode.trial_number)
        self.assertEqual(step_session, clock_session)
        self.assertGreaterEqual(step_stats['logical_trials'], 6)
        self.assertTrue(bw.mode.phase == 'done' or not bw.mode.started)

if __name__ == '__main__':
    unittest.main(verbosity=2)
