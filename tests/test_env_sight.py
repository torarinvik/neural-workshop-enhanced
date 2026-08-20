#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Out of Sight agent boundary.

The environment clocks the task itself, so nothing here waits on a real
second: a step is a tick, and a run of a few hundred ticks is a whole
session. The window is shrunk for the duration anyway, because every
step draws a frame and reads the whole framebuffer back, and there is
no reason to pay for a big one to check the arithmetic.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from envsupport import (OutOfSightEnv, derive_sight_outcome, digest_rgba,
                        requires_env, verify_sight_outcome)

#: Everything an observation is allowed to contain. A learner gets
#: pixels, when they were drawn, and — once — what the last question
#: was worth. No dot, no velocity, no phase, no score.
OBSERVATION_KEYS = frozenset((
    'frame_seq', 'timestamp_ns', 'width', 'height', 'rgba', 'done',
    'outcome'))

#: Enough ticks for any run these tests configure, and a stop so a
#: broken one fails instead of spinning.
STEP_LIMIT = 4000


def a_frame_of(colour, pixels):
    """A fake framebuffer that is *pixels* pixels of one colour."""
    return (bytes(colour) + b'\xff') * pixels


class SightOutcomeTests(unittest.TestCase):
    """Reading a verdict off a frame. No window needed."""

    def _colours(self):
        from neural_workshop.ui.tracking import CAUGHT, MISSED
        return CAUGHT, MISSED

    def test_the_right_answers_colour_reads_as_plus_one(self):
        caught, _missed = self._colours()
        got = derive_sight_outcome(a_frame_of(caught, 900), 30, 30, [], 1)
        self.assertEqual(got['scalar'], 1.0)

    def test_the_wrong_answers_colour_reads_as_minus_one(self):
        _caught, missed = self._colours()
        got = derive_sight_outcome(a_frame_of(missed, 900), 30, 30, [], 1)
        self.assertEqual(got['scalar'], -1.0)

    def test_a_frame_with_no_verdict_is_not_a_zero(self):
        """None and zero are different answers to different questions."""
        self.assertIsNone(derive_sight_outcome(b'', 0, 0, [], 1))
        blank = a_frame_of((255, 255, 255), 900)
        self.assertIsNone(derive_sight_outcome(blank, 30, 30, [], 1))

    def test_a_smear_too_small_to_be_a_ring_is_refused(self):
        caught, _missed = self._colours()
        thin = a_frame_of(caught, 5) + a_frame_of((255, 255, 255), 900)
        self.assertIsNone(derive_sight_outcome(thin, 30, 30, [], 1))

    def test_the_cue_colour_is_not_mistaken_for_a_verdict(self):
        """The flashed dots are on screen for whole seconds a round."""
        from neural_workshop.ui.tracking import CUED, PLAIN
        for colour in (CUED, PLAIN):
            self.assertIsNone(
                derive_sight_outcome(a_frame_of(colour, 5000), 50, 100, [], 1))

    def test_it_carries_the_scalar_and_never_the_counts(self):
        caught, _missed = self._colours()
        got = derive_sight_outcome(a_frame_of(caught, 900), 30, 30,
                                   ['abc'], 7, frame_seq=3, timestamp_ns=9)
        self.assertEqual(set(got), {'scalar', 'evidence_digests',
                                    'receipt_id', 'frame_seq',
                                    'timestamp_ns'})
        self.assertEqual(got['evidence_digests'], ['abc'])
        self.assertEqual(got['receipt_id'], 7)


@requires_env
class SightEnvTests(unittest.TestCase):
    """The stepped environment, driven a tick at a time."""

    @classmethod
    def setUpClass(cls):
        from neural_workshop import display, geometry
        cls.was = geometry.pixel_size()
        geometry.set_window_size(320, 240)
        display.relayout()

    @classmethod
    def tearDownClass(cls):
        from neural_workshop import display, geometry
        from neural_workshop.constants import (DEFAULT_WINDOW_HEIGHT,
                                               DEFAULT_WINDOW_WIDTH)
        geometry.set_window_size(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        display.relayout()

    def env(self, **kwargs):
        settings = dict(seed=5, dots=5, targets=2, probes=2, rounds=1,
                        frame_hz=20.)
        settings.update(kwargs)
        made = OutOfSightEnv(**settings)
        self.addCleanup(made.close)
        return made

    @staticmethod
    def play(env, answer=1, limit=STEP_LIMIT):
        """Run to the end, answering every question with *answer*.

        Returns the frame digests, the outcome events, and how many
        receipts came back ok.
        """
        frames, outcomes, receipts = [], [], 0
        done, steps = False, 0
        while not done and steps < limit:
            if env.act(answer)['ok']:
                receipts += 1
            obs, events, done = env.step()
            frames.append(digest_rgba(obs['rgba']))
            outcomes.extend(e for e in events if e['type'] == 'outcome')
            steps += 1
        return frames, outcomes, receipts

    # --- what a learner may see ------------------------------------------

    def test_an_observation_is_pixels_and_nothing_else(self):
        env = self.env()
        obs = env.observe()
        self.assertLessEqual(set(obs), OBSERVATION_KEYS)
        self.assertEqual(len(obs['rgba']), obs['width'] * obs['height'] * 4)
        self.assertGreater(obs['width'], 0)
        self.assertFalse(obs['done'])

    def test_the_frame_can_be_read_as_often_as_wanted(self):
        env = self.env()
        first = env.observe()
        again = env.observe()
        self.assertEqual(first['frame_seq'], again['frame_seq'])
        self.assertEqual(first['rgba'], again['rgba'])

    def test_a_step_is_a_tick_and_nothing_moves_between_them(self):
        env = self.env()
        was = env.observe()['frame_seq']
        moved = env.advance()['frame_seq']
        self.assertEqual(moved, was + 1)
        self.assertEqual(env.observe()['frame_seq'], moved)

    # --- determinism ------------------------------------------------------

    def test_one_seed_is_one_run_frame_for_frame(self):
        one, _outcomes, _rec = self.play(self.env(seed=11))
        two, _outcomes, _rec = self.play(self.env(seed=11))
        self.assertEqual(one, two)
        self.assertGreater(len(one), 20)

    def test_another_seed_is_another_run(self):
        one, _o, _r = self.play(self.env(seed=11))
        other, _o, _r = self.play(self.env(seed=12))
        self.assertNotEqual(one, other)

    def test_reset_starts_the_same_run_again(self):
        env = self.env(seed=11)
        first = env.observe()
        self.play(env)
        again = env.reset(11)
        self.assertEqual(digest_rgba(first['rgba']),
                         digest_rgba(again['rgba']))

    # --- the dials --------------------------------------------------------

    def test_the_dials_come_from_the_source_not_the_players_config(self):
        """A run under a seed has to mean the same on two machines."""
        from neural_workshop import state
        was = state.cfg['SIGHT_DOTS']
        state.cfg['SIGHT_DOTS'] = 25
        try:
            env = self.env(dots=None)
            self.assertEqual(env.task.dot_count, 8)   # the shipped value
        finally:
            state.cfg['SIGHT_DOTS'] = was

    def test_what_is_asked_for_is_what_is_dealt(self):
        env = self.env(dots=7, targets=3, blinds=1, probes=4, rounds=2,
                       speed=30, cross_ms=800, blind_width=6)
        self.assertEqual(env.task.dot_count, 7)
        self.assertEqual(env.task.held, 3)
        self.assertEqual(env.task.probes_per_round, 4)
        self.assertEqual(env.task.total_rounds, 2)
        self.assertAlmostEqual(env.task.speed, 0.30)
        self.assertAlmostEqual(env.task.cross_gap, 0.8)
        self.assertAlmostEqual(env.task.blind_width, 0.06)

    def test_the_flock_does_not_grow_under_the_learner_by_default(self):
        self.assertFalse(self.env().task.adaptive)

    def test_a_frame_rate_too_slow_to_mean_anything_is_refused(self):
        """Under ten a tick outruns how far the task will move."""
        for hz in (0, -5, 5, 9.9):
            self.assertRaises(ValueError, OutOfSightEnv, seed=1, frame_hz=hz)
        OutOfSightEnv(seed=1, rounds=1, probes=2, frame_hz=10).close()

    # --- actions ----------------------------------------------------------

    def test_there_are_two_ports(self):
        self.assertEqual(self.env().n_actions, 2)

    def test_an_action_with_no_question_up_is_refused(self):
        env = self.env()
        self.assertFalse(env.act(1)['ok'])
        self.assertIsNone(env.act(1)['receipt_id'])

    def test_only_the_first_answer_to_a_question_counts(self):
        env = self.env()
        first = self._to_a_question(env)
        self.assertTrue(first['ok'])
        self.assertFalse(env.act(0)['ok'])

    def test_pressing_both_ports_is_not_an_answer(self):
        env = self.env()
        self._to_a_question(env, act=False)
        self.assertFalse(env.act([0, 1])['ok'])
        self.assertFalse(env.act([])['ok'])
        self.assertTrue(env.act(1)['ok'])       # the window is still open

    def test_a_port_that_does_not_exist_is_refused(self):
        env = self.env()
        self._to_a_question(env, act=False)
        self.assertFalse(env.act(2)['ok'])
        self.assertFalse(env.act(-1)['ok'])

    def test_a_named_action_is_not_a_port(self):
        """Ports are opaque integers; a name is not a way in."""
        env = self.env()
        self._to_a_question(env, act=False)
        self.assertFalse(env.act({'mine': True})['ok'])

    def _to_a_question(self, env, act=True, limit=STEP_LIMIT):
        """Step until a ring goes up; answer it if *act*."""
        for _step in range(limit):
            obs, _events, done = env.step()
            if done:
                self.fail('the run ended before a question came up')
            if env._response_open and not env._action_finalized:
                return env.act(1) if act else {'ok': None}
        self.fail('no question ever came up')

    # --- outcomes ---------------------------------------------------------

    def test_every_question_answers_for_exactly_one_outcome(self):
        env = self.env(probes=3, rounds=2)
        _frames, outcomes, receipts = self.play(env)
        self.assertEqual(receipts, 6)
        self.assertEqual(len(outcomes), 6)
        self.assertEqual(len({o['receipt_id'] for o in outcomes}), 6)
        for outcome in outcomes:
            self.assertIn(outcome['scalar'], (1.0, -1.0))
        self.assertEqual(env.accounting.logical_trials, 6)

    def test_a_question_left_alone_still_answers_for_an_outcome(self):
        """The ring runs out on its own, and that is a real verdict."""
        env = self.env(probes=2, rounds=1)
        _frames, outcomes, receipts = self.play(env, answer=None)
        self.assertEqual(receipts, 0)
        self.assertEqual(len(outcomes), 2)
        for outcome in outcomes:
            self.assertEqual(outcome['scalar'], -1.0)

    def test_the_outcome_arrives_once_and_then_is_gone(self):
        env = self.env()
        for _step in range(STEP_LIMIT):
            env.act(1)
            obs, _events, done = env.step()
            if 'outcome' in obs:
                self.assertNotIn('outcome', env.observe())
                return
            if done:
                break
        self.fail('no outcome ever arrived')

    def test_an_outcome_verifies_against_its_own_frame(self):
        outcome, frame, env = self._first_outcome()
        self.assertTrue(verify_sight_outcome(
            outcome, frame['rgba'], frame['width'], frame['height'],
            env._archive, env._receipt_ledger))

    def test_it_fails_closed_without_the_archive_or_the_ledger(self):
        outcome, frame, env = self._first_outcome()
        self.assertFalse(verify_sight_outcome(
            outcome, frame['rgba'], frame['width'], frame['height'],
            env._archive, None))
        self.assertFalse(verify_sight_outcome(
            outcome, frame['rgba'], frame['width'], frame['height'],
            None, env._receipt_ledger))

    def test_a_bent_scalar_is_refused(self):
        outcome, frame, env = self._first_outcome()
        bent = dict(outcome)
        bent['scalar'] = -bent['scalar']
        self.assertFalse(verify_sight_outcome(
            bent, frame['rgba'], frame['width'], frame['height'],
            env._archive, env._receipt_ledger))

    def test_another_questions_receipt_is_refused(self):
        env = self.env(probes=3, rounds=1)
        seen = []
        for _step in range(STEP_LIMIT):
            env.act(1)
            obs, _events, done = env.step()
            if 'outcome' in obs:
                seen.append((obs['outcome'], dict(obs)))
            if len(seen) == 2 or done:
                break
        self.assertEqual(len(seen), 2, 'needed two questions')
        borrowed = dict(seen[0][0])
        borrowed['receipt_id'] = seen[1][0]['receipt_id']
        frame = seen[0][1]
        self.assertFalse(verify_sight_outcome(
            borrowed, frame['rgba'], frame['width'], frame['height'],
            env._archive, env._receipt_ledger))

    def _first_outcome(self):
        env = self.env()
        for _step in range(STEP_LIMIT):
            env.act(1)
            obs, _events, done = env.step()
            if 'outcome' in obs:
                return obs['outcome'], obs, env
            if done:
                break
        self.fail('no outcome ever arrived')

    # --- the end ----------------------------------------------------------

    def test_the_run_ends_and_says_so_once(self):
        env = self.env(probes=2, rounds=1)
        ended = []
        done, steps = False, 0
        while not done and steps < STEP_LIMIT:
            _obs, events, done = env.step()
            ended.extend(e for e in events if e['type'] == 'run_end')
            steps += 1
        self.assertTrue(done)
        self.assertEqual(len(ended), 1)

    def test_stepping_past_the_end_stays_put(self):
        env = self.env(probes=2, rounds=1)
        done, steps = False, 0
        while not done and steps < STEP_LIMIT:
            _obs, _events, done = env.step()
            steps += 1
        self.assertTrue(done)
        last = env.observe()['frame_seq']
        for _step in range(5):
            obs, _events, still = env.step()
            self.assertTrue(still)
            self.assertEqual(obs['frame_seq'], last)

    def test_the_accounting_adds_up(self):
        env = self.env(probes=2, rounds=2)
        frames, outcomes, _receipts = self.play(env)
        snap = env.accounting.snapshot()
        self.assertEqual(snap['logical_trials'], 4)
        # The frame reset drew counts too, and play() only sees the
        # ones the steps after it drew.
        self.assertEqual(snap['significant_frames'], len(frames) + 1)
        self.assertEqual(snap['unique_public_outcome_bits'], len(outcomes))
        self.assertEqual(snap['dropped_frames'], 0)


if __name__ == '__main__':
    unittest.main()
