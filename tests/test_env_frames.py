#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Frame capture, phase publication and the production environment.

The production environment must expose no probe and no privileged
state; these tests hold that line as well as checking that frames are
published exactly once per significant change.

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
class CaptureAndPhaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = DiagnosticEnv(seed=5)

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def test_feedback_digest_is_this_frame_not_prior_stimulus(self):
        self.env.reset(5)
        self.assertTrue(next_scorable_stimulus(self.env))
        stim_digest = digest_rgba(self.env._rgba)
        # Force public feedback: miss a match or false-alarm.
        if not ports_for('correct'):
            ports = ports_for('incorrect')
            self.assertTrue(ports)
            self.env.act(ports[:1])
        obs = None
        for _ in range(8):
            obs = self.env.advance()
            if self.env.probe.phase() == 'feedback':
                break
        self.assertIsNotNone(obs)
        self.assertNotEqual(digest_rgba(obs['rgba']), stim_digest)
        self.assertIn('outcome', obs)
        self.assertEqual(obs['outcome']['evidence_digests'][-1],
                         digest_rgba(obs['rgba']))
        self.assertTrue(verify_public_outcome(
            obs['outcome'], obs['rgba'], obs['width'], obs['height'],
            archive=self.env._archive,
            receipt_ledger=self.env._receipt_ledger))
        self.assertTrue(set(obs['outcome'].keys()) <= {
            'scalar', 'evidence_digests', 'receipt_id',
            'frame_seq', 'timestamp_ns'})
        self.assertNotIn('n_pos', obs['outcome'])
        self.assertNotIn('n_neg', obs['outcome'])

    def test_verify_rejects_forged_digest(self):
        w, h = 20, 24
        row_g = bytes([64, 255, 64, 255] * w)
        row_k = bytes([10, 10, 10, 255] * w)
        rgba = row_k * 18 + row_g * 6
        real_d = digest_rgba(rgba)
        archive = {real_d: rgba}
        outcome = derive_public_outcome(rgba, w, h, [real_d], 1)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome['scalar'], 1.0)
        self.assertTrue(verify_public_pixels(outcome, rgba, w, h, archive))
        self.assertFalse(
            verify_public_outcome(outcome, rgba, w, h, archive=archive),
            'public verifier requires a receipt ledger')
        forged = dict(outcome)
        forged['evidence_digests'] = ['forged']
        self.assertFalse(verify_public_pixels(forged, rgba, w, h, archive))
        earlier = dict(outcome)
        earlier['evidence_digests'] = ['forged-stim', real_d]
        self.assertFalse(
            verify_public_pixels(earlier, rgba, w, h, archive=None),
            'multi-frame evidence requires an archive')
        self.assertFalse(
            verify_public_pixels(earlier, rgba, w, h, archive=archive))

    def test_public_observation_schema(self):
        obs = self.env.reset(1)
        allowed = {'frame_seq', 'timestamp_ns', 'width', 'height',
                   'rgba', 'done', 'outcome',
                   'audio_pcm', 'audio_rate', 'audio_channels',
                   'audio_sample_width'}
        self.assertTrue(set(obs.keys()) <= allowed)
        for leaked in ('phase', 'position1', 'correct', 'match',
                       'bt_sequence', 'current_stim', 'feedback',
                       'n_pos', 'n_neg', 'letter', 'audio'):
            self.assertNotIn(leaked, obs)

    def test_significant_states_once_each(self):
        first = self.env.reset(6)
        seqs = [first['frame_seq']]
        phases = [self.env.probe.phase()]
        for _ in range(8):
            obs = self.env.advance()
            seqs.append(obs['frame_seq'])
            phases.append(self.env.probe.phase())
        self.assertEqual(seqs, sorted(set(seqs)))
        self.assertEqual(phases[0], 'stimulus')
        self.assertIn(phases[1], ('blank', 'feedback'))


@requires_env
class ProductionEnvTests(unittest.TestCase):
    def test_production_has_no_probe(self):
        os.environ.pop('NW_DIAGNOSTICS', None)
        env = NeuralWorkshopEnv(seed=1)
        try:
            self.assertFalse(hasattr(env, 'probe'))
            with self.assertRaises(RuntimeError):
                NeuralWorkshopEnv(seed=1, diagnostics=True)
        finally:
            env.close()

    def test_observe_emits_outcome_once(self):
        env = DiagnosticEnv(seed=7)
        try:
            self.assertTrue(next_scorable_stimulus(env))
            if not ports_for('correct'):
                ports = ports_for('incorrect')
                if ports:
                    env.act(ports[:1])
            first = None
            while env.probe.phase() != 'feedback':
                first = env.advance()
            n_out = lambda ev: sum(1 for e in ev if e.get('type') == 'outcome')
            ev1 = n_out(env._events)
            lat1 = len(env.accounting.action_to_outcome_ns)
            self.assertEqual(ev1, 1)
            self.assertEqual(lat1, 1)
            self.assertIn('outcome', first)
            pixels = first['rgba']
            for _ in range(3):
                again = env.observe()
                self.assertNotIn('outcome', again)
                self.assertEqual(again['rgba'], pixels)
            self.assertEqual(n_out(env._events), 1)
            self.assertEqual(len(env.accounting.action_to_outcome_ns), 1)
            self.assertEqual(len(env._delivered), len(set(env._delivered)))
        finally:
            env.close()

    def test_session_end_emits_once(self):
        env = DiagnosticEnv(seed=8, num_trials=4)
        try:
            done = False
            guard = 0
            while not done and guard < 80:
                obs = env.advance()
                done = bool(obs.get('done'))
                guard += 1
            self.assertTrue(done)
            n_end = sum(1 for e in env._events if e.get('type') == 'session_end')
            self.assertEqual(n_end, 1)
            seq = env._seq
            for _ in range(4):
                obs = env.advance()
                self.assertTrue(obs.get('done'))
                self.assertEqual(obs['frame_seq'], seq)
            self.assertEqual(
                sum(1 for e in env._events if e.get('type') == 'session_end'), 1)
        finally:
            env.close()

    def test_headless_terminates_without_audio_thread_exceptions(self):
        caught = []

        def hook(args):
            caught.append(args)

        prev = threading.excepthook
        threading.excepthook = hook
        env = DiagnosticEnv(seed=4, game_mode=2, num_trials=4)
        try:
            done = False
            for _ in range(40):
                _obs, _ev, done = env.step([])
                if done:
                    break
            self.assertTrue(done)
            driver = __import__('pyglet').media.get_audio_driver()
            self.assertEqual(driver.__class__.__name__, 'SilentDriver')
            self.assertTrue(isinstance(bw.player, bw.CapturePlayer))
            self.assertEqual(caught, [], 'OpenAL/audio worker raised: %s' % caught)
        finally:
            threading.excepthook = prev
            env.close()

    def test_act_stores_logp_on_receipt(self):
        env = DiagnosticEnv(seed=3)
        try:
            rec = env.act(0, logp=-1.25)
            self.assertTrue(rec.get('ok'))
            self.assertEqual(rec.get('logp'), -1.25)
            self.assertEqual(env._trial_receipt['logp'], -1.25)
            self.assertEqual(
                env._receipt_ledger[rec['receipt_id']]['logp'], -1.25)
        finally:
            env.close()

if __name__ == '__main__':
    unittest.main(verbosity=2)
