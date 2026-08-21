#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""What a task may change about the agent boundary, and what it may not.

The three hand-written wrappers each carry their own copy of the receipt
rules, the observation dictionary and a verifier maintained in parallel with
its deriver. :mod:`nwenv.taskenv` shares those, and the sharing is only worth
anything if a task cannot quietly opt out of them: a subclass that redefined
``_emit_once`` could pay one action twice, and one that redefined
``_observation`` could hand the learner a coordinate. Neither fails loudly.

So the sealing is tested rather than trusted, and so is the claim that a
generated verifier is the same function as the deriver it came from.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from nwenv.frames import digest_rgba
from nwenv.outcome import PUBLIC_OUTCOME_KEYS
from nwenv.taskenv import SEALED, SealedContractError, TaskEnv


class Minimal(TaskEnv):
    """The smallest thing that satisfies the contract."""

    ports = 3

    def build(self, seed, **dials):
        return object()

    def drive(self, task, port):
        self.driven = port

    @staticmethod
    def derive(rgba, width, height, evidence, receipt_id, frame_seq=None,
               timestamp_ns=None, neutral=False):
        return {
            'scalar': 0.0 if neutral else 1.0,
            'evidence_digests': list(evidence),
            'receipt_id': receipt_id,
            'frame_seq': frame_seq,
            'timestamp_ns': timestamp_ns,
        }


class SealingTest(unittest.TestCase):
    def test_a_conforming_subclass_is_allowed(self):
        self.assertEqual(Minimal.ports, 3)
        self.assertEqual(Minimal().n_actions, 3)

    def test_every_sealed_name_is_refused(self):
        """Not a sample -- each sealed name gets its own attempt."""
        for name in sorted(SEALED):
            with self.subTest(sealed=name):
                with self.assertRaises(SealedContractError) as caught:
                    type('Sneaky', (Minimal,), {name: lambda self: None})
                self.assertIn(name, str(caught.exception))

    def test_the_refusal_says_what_to_do_instead(self):
        with self.assertRaises(SealedContractError) as caught:
            type('Sneaky', (Minimal,), {'_emit_once': lambda self: None})
        message = str(caught.exception)
        self.assertIn('derive', message)
        self.assertIn('pay one action twice', message)

    def test_sealing_survives_an_intermediate_subclass(self):
        """A task cannot launder an override through a middle layer."""
        middle = type('Middle', (Minimal,), {})
        with self.assertRaises(SealedContractError):
            type('Sneaky', (middle,), {'_observation': lambda self: {}})

    def test_unsealed_hooks_are_freely_overridable(self):
        later = type('Later', (Minimal,), {
            'begin': lambda self, task: None,
            'settled': lambda self, task: False,
            'dials': lambda self: {'X': 1},
        })
        self.assertFalse(later().settled(None))
        self.assertEqual(later().dials(), {'X': 1})


class ObservationTest(unittest.TestCase):
    """The learner sees pixels and a scalar, and nothing that is not checkable."""

    def setUp(self):
        self.env = Minimal()
        self.env._seq = 4
        self.env._timestamp_ns = 99
        self.env._width, self.env._height = 8, 6
        self.env._rgba = b'\x00' * (8 * 6 * 4)
        self.env._done = False
        self.env._cached_outcome = None

    def test_observation_carries_only_the_permitted_keys(self):
        allowed = {'frame_seq', 'timestamp_ns', 'width', 'height', 'rgba',
                   'done', 'outcome'}
        self.assertLessEqual(set(self.env._observation()), allowed)

    def test_no_outcome_key_until_there_is_one(self):
        self.assertNotIn('outcome', self.env._observation())


class EmitOnceTest(unittest.TestCase):
    def setUp(self):
        self.env = Minimal()
        self.env._delivered = set()
        self.env._events = []

    def test_the_same_key_goes_out_exactly_once(self):
        first = self.env._emit_once(('outcome', 7), {'scalar': 1.0})
        second = self.env._emit_once(('outcome', 7), {'scalar': 1.0})
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(self.env._events), 1)

    def test_different_receipts_are_different_keys(self):
        self.env._emit_once(('outcome', 7), {'scalar': 1.0})
        self.env._emit_once(('outcome', 8), {'scalar': 1.0})
        self.assertEqual(len(self.env._events), 2)


class GeneratedVerifierTest(unittest.TestCase):
    """The verifier must be the deriver, not a second reading of it."""

    #: A real frame and its real digest. Verification checks the last
    #: evidence digest against the frame in hand before it derives
    #: anything, so a placeholder digest never reaches the deriver --
    #: and the receipt must additionally name that digest as the
    #: trial's first frame.
    FRAME = bytes(range(64))
    DIGEST = digest_rgba(FRAME)

    def bound(self):
        return {1: {'stimulus_digest': self.DIGEST,
                    'evidence_digests': [self.DIGEST],
                    'feedback_digest': self.DIGEST}}

    def claim(self, scalar):
        return {'scalar': scalar, 'receipt_id': 1,
                'evidence_digests': [self.DIGEST],
                'frame_seq': 0, 'timestamp_ns': 0}

    def watched(self, seen):
        class Watched(Minimal):
            @staticmethod
            def derive(rgba, width, height, evidence, receipt_id,
                       frame_seq=None, timestamp_ns=None, neutral=False):
                seen.append(neutral)
                return None
        return Watched

    def test_the_verifier_calls_this_task_s_deriver(self):
        seen = []
        verify = self.watched(seen).verifier()
        verify(self.claim(1.0), self.FRAME, 4, 4,
               archive={self.DIGEST: self.FRAME},
               receipt_ledger=self.bound())
        self.assertTrue(seen, 'the generated verifier never reached derive')

    def test_a_zero_claim_is_derived_as_neutral(self):
        """Claiming zero never claims more than was earned."""
        seen = []
        verify = self.watched(seen).verifier()
        for scalar in (0.0, 1.0):
            verify(self.claim(scalar), self.FRAME, 4, 4,
                   archive={self.DIGEST: self.FRAME},
                   receipt_ledger=self.bound())
        self.assertEqual(seen, [True, False])

    def test_it_fails_closed_without_the_archive_and_ledger(self):
        verify = Minimal.verifier()
        self.assertFalse(verify(self.claim(1.0), self.FRAME, 4, 4))

    def test_an_unbound_receipt_is_rejected_before_any_deriving(self):
        """A receipt that does not own this evidence never reaches pixels."""
        seen = []
        verify = self.watched(seen).verifier()
        self.assertFalse(verify(self.claim(1.0), self.FRAME, 4, 4,
                                archive={self.DIGEST: self.FRAME},
                                receipt_ledger={1: {}}))
        self.assertEqual(seen, [], 'derive ran on an unbound receipt')

    def test_each_task_gets_its_own_verifier(self):
        other = type('Other', (Minimal,), {})
        self.assertIsNot(Minimal.verifier(), other.verifier())
        self.assertIn('Other', other.verifier().__name__)


if __name__ == '__main__':
    unittest.main()
