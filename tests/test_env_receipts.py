#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Receipts, public outcomes and their verification.

The bulk of the boundary's security properties live here: one action
per trial, receipts bound to the frames they answer for, and outcomes
that fail closed when the archive or ledger is missing or tampered
with.

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
class ReceiptAndOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = DiagnosticEnv(seed=2, num_trials=12)

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def test_positive_outcome_required(self):
        self.env.reset(20)
        found = None
        for _ in range(50):
            if not next_scorable_stimulus(self.env):
                break
            ports = ports_for('correct')
            if not ports:
                self.env.advance()
                continue
            self.env.act(ports)
            while self.env.probe.phase() != 'feedback':
                obs = self.env.advance()
                if self.env.probe.session_done():
                    break
            else:
                obs = self.env.observe() if False else {
                    'outcome': None, 'rgba': self.env._rgba,
                    'width': self.env._width, 'height': self.env._height,
                }
                # last advance already observed; grab from last publish via step back
            # Re-read current published observation
            cur = {
                'rgba': self.env._rgba,
                'width': self.env._width,
                'height': self.env._height,
            }
            out = derive_public_outcome(
                cur['rgba'], cur['width'], cur['height'],
                self.env._trial_digests,
                self.env._trial_receipt['receipt_id'])
            if out and out['scalar'] == 1.0:
                found = out
                self.assertTrue(verify_public_outcome(
                    out, cur['rgba'], cur['width'], cur['height'],
                    archive=self.env._archive,
                    receipt_ledger=self.env._receipt_ledger))
                break
            if self.env.probe.session_done():
                break
        self.assertIsNotNone(found, 'required a +1 public outcome')

    def test_negative_false_alarm_required(self):
        self.env.reset(21)
        found = None
        for _ in range(50):
            if not next_scorable_stimulus(self.env):
                break
            ports = ports_for('incorrect')
            if not ports:
                self.env.advance()
                continue
            self.env.act(ports[:1])
            while self.env.probe.phase() != 'feedback':
                self.env.advance()
                if self.env.probe.session_done():
                    break
            out = derive_public_outcome(
                self.env._rgba, self.env._width, self.env._height,
                self.env._trial_digests,
                self.env._trial_receipt['receipt_id'])
            if out and out['scalar'] == -1.0:
                found = out
                break
            if self.env.probe.session_done():
                break
        self.assertIsNotNone(found, 'required a -1 false-alarm outcome')

    def test_missed_match_is_negative(self):
        self.env.reset(22)
        found = None
        for _ in range(50):
            if not next_scorable_stimulus(self.env):
                break
            if not ports_for('correct'):
                self.env.advance()
                continue
            # Deliberate no-action on a real match → blue oops → -1
            while self.env.probe.phase() != 'feedback':
                self.env.advance()
                if self.env.probe.session_done():
                    break
            out = derive_public_outcome(
                self.env._rgba, self.env._width, self.env._height,
                self.env._trial_digests,
                self.env._trial_receipt['receipt_id'])
            if out and out['scalar'] == -1.0:
                found = out
                break
            if self.env.probe.session_done():
                break
        self.assertIsNotNone(found, 'required a -1 missed-match outcome')

    def test_no_action_still_gets_a_receipt(self):
        self.env.reset(2)
        self.assertIsNotNone(self.env._trial_receipt)
        self.assertEqual(self.env._trial_receipt['ports'], ())
        rid = self.env._trial_receipt['receipt_id']
        advance_to(self.env, 'feedback')
        self.assertEqual(self.env._trial_receipt['receipt_id'], rid)

    def test_second_act_fails_closed(self):
        self.env.reset(3)
        advance_to(self.env, 'stimulus')
        first = self.env.act(0)
        self.assertTrue(first.get('ok'))
        second = self.env.act(0)
        self.assertFalse(second.get('ok'))
        self.assertEqual(self.env._trial_receipt['ports'], first['ports'])

    def test_late_action_fails_closed(self):
        self.env.reset(3)
        while self.env.probe.phase() == 'stimulus':
            self.env.advance()
        self.assertFalse(self.env._response_open)
        held = dict(self.env._trial_receipt)
        rejected = self.env.act(0)
        self.assertFalse(rejected.get('ok'))
        self.assertIsNone(rejected.get('receipt_id'))
        self.assertEqual(self.env._trial_receipt, held)

    def test_missing_feedback_yields_no_outcome(self):
        self.env.reset(9)
        bw.cfg.SHOW_FEEDBACK = False
        try:
            saw = False
            for _ in range(12):
                obs = self.env.advance()
                if self.env.probe.phase() == 'feedback':
                    saw = True
                    self.assertNotIn('outcome', obs)
                    self.assertIsNone(derive_public_outcome(
                        obs['rgba'], obs['width'], obs['height'], [], 1))
                    break
            self.assertTrue(saw)
        finally:
            bw.cfg.SHOW_FEEDBACK = True

    def test_duplicate_frame_does_not_advance(self):
        self.env.reset(10)
        first = self.env.advance()
        seq = first['frame_seq']
        self.env._pending = True
        self.env._consumed = False
        again = self.env.advance()
        self.assertEqual(again['frame_seq'], seq)
        self.assertGreaterEqual(self.env.accounting.duplicate_frames, 1)

    def test_reward_shuffle_fails_verify(self):
        # Bottom-quarter green band so the ROI scanner sees it
        row = bytes([64, 255, 64, 255] * 20)
        top = bytes([10, 10, 10, 255] * 20) * 18
        bot = row * 6
        rgba = top + bot
        w, h = 20, 24
        d = digest_rgba(rgba)
        real = derive_public_outcome(rgba, w, h, [d], 1)
        self.assertIsNotNone(real)
        self.assertEqual(real['scalar'], 1.0)
        shuffled = dict(real)
        shuffled['scalar'] = -1.0
        archive = {d: rgba}
        self.assertFalse(verify_public_pixels(shuffled, rgba, w, h, archive))

    def test_action_shuffled_receipt_fails_verify(self):
        self.env.reset(15)
        self.assertTrue(next_scorable_stimulus(self.env))
        self.env.act(0)
        while self.env.probe.phase() != 'feedback':
            self.env.advance()
        obs = {
            'rgba': self.env._rgba, 'width': self.env._width,
            'height': self.env._height,
        }
        out = derive_public_outcome(
            obs['rgba'], obs['width'], obs['height'],
            self.env._trial_digests,
            self.env._trial_receipt['receipt_id'])
        self.assertIsNotNone(out)
        shuffled = dict(out)
        shuffled['receipt_id'] = out['receipt_id'] + 999
        self.assertFalse(verify_public_outcome(
            shuffled, obs['rgba'], obs['width'], obs['height'],
            archive=self.env._archive,
            receipt_ledger=self.env._receipt_ledger))

    def test_foreign_valid_receipt_fails_verify(self):
        """Another ledger receipt from a different trial must not verify."""
        env = self.env
        env.reset(18)
        collected = []
        for _ in range(40):
            if len(collected) >= 2:
                break
            if not next_scorable_stimulus(env):
                break
            env.act(ports_for('incorrect')[:1] or [0])
            obs = None
            while env.probe.phase() != 'feedback':
                obs = env.advance()
                if env.probe.session_done():
                    break
            if not obs or 'outcome' not in obs:
                continue
            collected.append({
                'outcome': dict(obs['outcome']),
                'rgba': obs['rgba'],
                'width': obs['width'],
                'height': obs['height'],
            })
        self.assertGreaterEqual(len(collected), 2, 'need two scored trials')
        a, b = collected[0], collected[1]
        self.assertNotEqual(a['outcome']['receipt_id'],
                            b['outcome']['receipt_id'])
        self.assertTrue(verify_public_outcome(
            b['outcome'], b['rgba'], b['width'], b['height'],
            archive=env._archive, receipt_ledger=env._receipt_ledger))
        swapped = dict(b['outcome'])
        swapped['receipt_id'] = a['outcome']['receipt_id']
        self.assertTrue(
            verify_public_pixels(
                swapped, b['rgba'], b['width'], b['height'],
                archive=env._archive),
            'pixel-only diagnostic still accepts a swapped receipt')
        self.assertFalse(
            verify_public_outcome(
                swapped, b['rgba'], b['width'], b['height'],
                archive=env._archive),
            'public verifier fails closed without a ledger')
        self.assertFalse(verify_public_outcome(
            swapped, b['rgba'], b['width'], b['height'],
            archive=env._archive, receipt_ledger=env._receipt_ledger),
            'valid receipt from another trial must not bind')

    def test_public_verify_requires_ledger(self):
        env = self.env
        env.reset(19)
        self.assertTrue(next_scorable_stimulus(env))
        env.act(ports_for('incorrect')[:1] or [0])
        obs = None
        while env.probe.phase() != 'feedback':
            obs = env.advance()
            if env.probe.session_done():
                break
        self.assertIsNotNone(obs)
        self.assertIn('outcome', obs)
        self.assertFalse(
            verify_public_outcome(
                obs['outcome'], obs['rgba'], obs['width'], obs['height'],
                archive=env._archive),
            'archive without ledger must fail closed')
        self.assertFalse(
            verify_public_outcome(
                obs['outcome'], obs['rgba'], obs['width'], obs['height'],
                receipt_ledger=env._receipt_ledger),
            'ledger without archive must fail closed')
        self.assertTrue(verify_public_outcome(
            obs['outcome'], obs['rgba'], obs['width'], obs['height'],
            archive=env._archive, receipt_ledger=env._receipt_ledger))

    def test_count_fields_fail_verify(self):
        w, h = 20, 24
        row = bytes([64, 255, 64, 255] * w)
        rgba = bytes([10, 10, 10, 255] * w) * 18 + row * 6
        d = digest_rgba(rgba)
        out = derive_public_outcome(rgba, w, h, [d], 1)
        self.assertNotIn('n_pos', out)
        self.assertNotIn('n_neg', out)
        leaked = dict(out)
        leaked['n_pos'] = 1
        leaked['n_neg'] = 0
        ledger = {1: {
            'receipt_id': 1, 'trial_seq': 1, 'stimulus_digest': d,
            'evidence_digests': [d], 'feedback_digest': d,
        }}
        self.assertFalse(verify_public_outcome(
            leaked, rgba, w, h, archive={d: rgba}, receipt_ledger=ledger))

    def test_delayed_resolution_keeps_stimulus_receipt(self):
        """Action during stimulus is resolved only at later feedback."""
        self.env.reset(16)
        self.assertTrue(next_scorable_stimulus(self.env))
        stim = dict(self.env.probe.stim())
        rec = self.env.act(ports_for('incorrect')[:1] or [0])
        self.assertTrue(rec.get('ok'))
        rid = rec['receipt_id']
        self.assertNotIn('outcome', self.env.observe())
        while self.env.probe.phase() == 'stimulus':
            obs = self.env.advance()
            if self.env.probe.phase() != 'feedback':
                self.assertNotIn('outcome', obs)
        self.assertFalse(self.env._response_open)
        while self.env.probe.phase() != 'feedback':
            obs = self.env.advance()
            if self.env.probe.phase() != 'feedback':
                self.assertNotIn('outcome', obs)
        self.assertEqual(self.env._trial_receipt['receipt_id'], rid)
        out = derive_public_outcome(
            self.env._rgba, self.env._width, self.env._height,
            self.env._trial_digests, rid)
        self.assertIsNotNone(out)
        self.assertEqual(out['receipt_id'], rid)
        acted_scalar = out['scalar']

        # Same seed, no action: delayed resolution is causal, not a stimulus tag.
        self.env.reset(16)
        self.assertTrue(next_scorable_stimulus(self.env))
        self.assertEqual(self.env.probe.stim(), stim)
        while self.env.probe.phase() != 'feedback':
            self.env.advance()
        idle = derive_public_outcome(
            self.env._rgba, self.env._width, self.env._height,
            self.env._trial_digests,
            self.env._trial_receipt['receipt_id'])
        idle_scalar = None if idle is None else idle['scalar']
        self.assertNotEqual(acted_scalar, idle_scalar)

    def test_action_shuffled_control_changes_outcomes(self):
        """Same stimuli, permuted trial-actions: outcome sequence must move."""
        env = self.env
        actions = [[0], [1] if env.n_actions > 1 else [0], [], [0],
                   [1] if env.n_actions > 1 else [], [], [0],
                   [1] if env.n_actions > 1 else [0]]

        def collect(act_list):
            env.reset(17)
            stims, outcomes, receipts = [], [], []
            box = [0]

            def maybe_act():
                if env.probe.phase() != 'stimulus':
                    return
                if bw.mode.trial_number <= bw.mode.back:
                    return
                if box[0] >= len(act_list):
                    return
                rec = env.act(act_list[box[0]])
                box[0] += 1
                receipts.append((rec.get('receipt_id'), tuple(rec.get('ports') or ())))
                stims.append((bw.mode.trial_number, tuple(sorted(
                    env.probe.stim().items()))))

            maybe_act()
            for _ in range(80):
                if env.probe.session_done():
                    break
                env.advance()
                if env.probe.phase() == 'feedback':
                    out = derive_public_outcome(
                        env._rgba, env._width, env._height,
                        env._trial_digests,
                        (env._trial_receipt or {}).get('receipt_id'))
                    outcomes.append(None if out is None else out['scalar'])
                maybe_act()
            return stims, outcomes, receipts

        a = collect(actions)
        shuffled = list(actions)
        rng = random.Random(0)
        rng.shuffle(shuffled)
        if shuffled == actions:
            shuffled = list(reversed(actions))
        b = collect(shuffled)
        self.assertEqual(a[0], b[0], 'stimuli must be seed-identical')
        self.assertNotEqual(a[1], b[1], 'shuffled actions must move outcomes')
        self.assertNotEqual(a[2], b[2], 'receipts must follow the permuted acts')

if __name__ == '__main__':
    unittest.main(verbosity=2)
