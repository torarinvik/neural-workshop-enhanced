#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Monkey Ladder agent boundary.

The environment clocks the task itself, so nothing here waits on a real
second: a step is a tick and a run of a few hundred ticks is a whole
session. What is worth checking is that a round can only be scored
right by actually holding the set -- the outcome is read off pixels,
and an agent that clicks a tile it was never shown must not be able to
collect a positive one.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from envsupport import (MonkeyLadderEnv, derive_ladder_outcome,  # noqa: F401
                        digest_rgba, requires_env, verify_ladder_outcome)

#: Everything an observation is allowed to contain. A learner gets
#: pixels, when they were drawn, and -- once -- what the last round was
#: worth. No cells, no sequence, no phase, no level.
OBSERVATION_KEYS = frozenset((
    'frame_seq', 'timestamp_ns', 'width', 'height', 'rgba', 'done',
    'outcome'))

#: Enough ticks for any run these tests configure, and a stop so a
#: broken one fails instead of spinning.
STEP_LIMIT = 6000


def a_frame_of(colour, pixels):
    """A fake framebuffer that is *pixels* pixels of one colour."""
    return (bytes(colour) + b'\xff') * pixels


PREVIEW = (64, 96, 255)
CORRECT = (46, 170, 92)
WRONG = (220, 64, 64)


@requires_env
class LadderOutcomeTests(unittest.TestCase):
    """Reading a verdict off two frames. No window needed."""

    def test_wrong_colour_scores_minus_one(self):
        frame = a_frame_of(WRONG, 400)
        out = derive_ladder_outcome(frame, 20, 20, ['d'], 1)
        self.assertEqual(out['scalar'], -1.0)

    def test_wrong_colour_needs_no_preview(self):
        """A miss is legible from the result frame alone."""
        frame = a_frame_of(WRONG, 400)
        self.assertIsNotNone(derive_ladder_outcome(frame, 20, 20, ['d'], 1))

    def test_full_set_scores_plus_one(self):
        preview = a_frame_of(PREVIEW, 900)
        result = a_frame_of(CORRECT, 900)
        out = derive_ladder_outcome(result, 30, 30, ['d'], 1,
                                    preview_rgba=preview)
        self.assertEqual(out['scalar'], 1.0)

    def test_partial_set_is_not_a_verdict(self):
        """Half the set placed is not a win, and not a loss either."""
        preview = a_frame_of(PREVIEW, 900)
        result = a_frame_of(CORRECT, 400)
        self.assertIsNone(derive_ladder_outcome(
            result, 30, 30, ['d'], 1, preview_rgba=preview))

    def test_positive_verdict_requires_the_preview(self):
        """Without the preview frame there is nothing to match against."""
        result = a_frame_of(CORRECT, 900)
        self.assertIsNone(derive_ladder_outcome(result, 30, 30, ['d'], 1))

    def test_blank_frame_is_not_a_verdict(self):
        self.assertIsNone(derive_ladder_outcome(b'', 0, 0, ['d'], 1))

    def test_outcome_carries_no_pixel_counts(self):
        preview = a_frame_of(PREVIEW, 900)
        result = a_frame_of(CORRECT, 900)
        out = derive_ladder_outcome(result, 30, 30, ['d'], 1,
                                    preview_rgba=preview)
        self.assertEqual(set(out), {'scalar', 'evidence_digests',
                                    'receipt_id'})


@requires_env
class LadderRunTests(unittest.TestCase):
    """Driving a real run, headless."""

    def _env(self, **kwargs):
        kwargs.setdefault('grid', 4)
        kwargs.setdefault('level', 3)
        kwargs.setdefault('rounds', 4)
        return MonkeyLadderEnv(seed=7, **kwargs)

    def _play(self, env, oracle):
        """Run to the end, returning the outcome scalars in order."""
        scalars = []
        for _ in range(STEP_LIMIT):
            task = env.task
            if task.phase == 'input' and env._response_open:
                cell = oracle(task)
                if cell is not None:
                    env.act(cell[0] * task.grid + cell[1])
            _obs, events, done = env.step()
            scalars.extend(e['scalar'] for e in events
                           if e['type'] == 'outcome')
            if done:
                break
        return scalars

    def test_holding_the_set_scores_every_round(self):
        env = self._env()
        try:
            scalars = self._play(
                env, lambda t: t.sequence[t.next_index])
        finally:
            env.close()
        self.assertEqual(scalars, [1.0] * 4)

    def test_clicking_an_unshown_tile_never_scores(self):
        """The pixel rule is the whole defence: no set, no positive."""
        env = self._env()
        try:
            scalars = self._play(env, lambda t: next(
                ((r, c) for r in range(t.grid) for c in range(t.grid)
                 if (r, c) not in t.sequence), None))
        finally:
            env.close()
        self.assertEqual(scalars, [-1.0] * 4)

    def test_a_late_miss_still_fails_the_round(self):
        """Getting most of the set is not getting the set."""
        env = self._env(level=3)
        try:
            def oracle(task):
                if task.next_index == 0:
                    return task.sequence[0]
                return next(((r, c) for r in range(task.grid)
                             for c in range(task.grid)
                             if (r, c) not in task.sequence), None)
            scalars = self._play(env, oracle)
        finally:
            env.close()
        self.assertEqual(scalars, [-1.0] * 4)

    def test_observation_says_nothing_privileged(self):
        env = self._env()
        try:
            obs = env.observe()
            self.assertLessEqual(set(obs), OBSERVATION_KEYS)
            for _ in range(60):
                obs, _events, done = env.step()
                self.assertLessEqual(set(obs), OBSERVATION_KEYS)
                if done:
                    break
        finally:
            env.close()

    def test_two_runs_under_one_seed_match_byte_for_byte(self):
        digests = []
        for _ in range(2):
            env = self._env()
            try:
                run = []
                for _ in range(120):
                    obs, _events, done = env.step()
                    run.append(digest_rgba(obs['rgba']))
                    if done:
                        break
                digests.append(run)
            finally:
                env.close()
        self.assertEqual(digests[0], digests[1])

    def test_different_seeds_diverge(self):
        runs = []
        for seed in (7, 8):
            env = MonkeyLadderEnv(seed=seed, grid=4, level=3, rounds=4)
            try:
                run = []
                for _ in range(120):
                    obs, _events, done = env.step()
                    run.append(digest_rgba(obs['rgba']))
                    if done:
                        break
                runs.append(run)
            finally:
                env.close()
        self.assertNotEqual(runs[0], runs[1])

    def test_one_action_per_window(self):
        env = self._env()
        try:
            for _ in range(STEP_LIMIT):
                task = env.task
                if task.phase == 'input' and env._response_open:
                    cell = task.sequence[task.next_index]
                    first = env.act(cell[0] * task.grid + cell[1])
                    self.assertTrue(first['ok'])
                    again = env.act(0)
                    self.assertFalse(again['ok'])
                    break
                env.step()
            else:  # pragma: no cover - the run never took input
                self.fail('no action window opened')
        finally:
            env.close()

    def test_ports_are_the_whole_grid(self):
        env = self._env(grid=5)
        try:
            self.assertEqual(env.n_actions, 25)
        finally:
            env.close()

    def test_set_size_is_a_dial(self):
        """The point of this task: load scales, nothing else changes."""
        for level in (2, 5):
            env = MonkeyLadderEnv(seed=7, grid=5, level=level, rounds=2)
            try:
                self.assertEqual(len(env.task.sequence), level)
            finally:
                env.close()

    def test_a_run_ends_after_its_rounds(self):
        env = self._env(rounds=2)
        try:
            scalars = self._play(env, lambda t: t.sequence[t.next_index])
        finally:
            env.close()
        self.assertEqual(len(scalars), 2)


@requires_env
class LadderCursorTests(unittest.TestCase):
    """The five-port interface: four moves and a commit."""

    def _env(self, **kwargs):
        kwargs.setdefault('grid', 4)
        kwargs.setdefault('level', 3)
        kwargs.setdefault('rounds', 3)
        kwargs.setdefault('cursor', True)
        return MonkeyLadderEnv(seed=11, **kwargs)

    def _port_towards(self, task):
        """The move that closes the gap, or the commit when there is none."""
        want = task.sequence[task.next_index]
        here = task.cursor_cell
        if here[0] < want[0]:
            return 0
        if here[0] > want[0]:
            return 1
        if here[1] > want[1]:
            return 2
        if here[1] < want[1]:
            return 3
        return 4

    def test_the_cursor_offers_five_ports(self):
        env = self._env()
        try:
            self.assertEqual(env.n_actions, 5)
        finally:
            env.close()

    def test_absolute_ports_are_still_the_default(self):
        env = self._env(cursor=False, grid=5)
        try:
            self.assertEqual(env.n_actions, 25)
        finally:
            env.close()

    def test_driving_the_cursor_scores_every_round(self):
        env = self._env()
        try:
            scalars = []
            for _ in range(STEP_LIMIT * 4):
                task = env.task
                port = None
                if task.phase == 'input' and env._response_open:
                    port = self._port_towards(task)
                _obs, events, done = env.step(port)
                scalars.extend(e['scalar'] for e in events
                               if e['type'] == 'outcome')
                if done:
                    break
        finally:
            env.close()
        self.assertEqual(scalars, [1.0] * 3)

    def test_the_marker_cannot_move_the_tile_counts(self):
        """The whole outcome rule rests on this.

        The marker is drawn in the gap between tiles, so parking it on
        any cell must leave every scored colour's pixel count alone --
        otherwise a round could be scored differently depending on where
        the agent happened to be looking.
        """
        from nwenv.ladder import _count_fill

        env = self._env()
        try:
            task = env.task
            counts = {colour: set() for colour in (PREVIEW, CORRECT, WRONG)}
            for row in range(task.grid):
                for col in range(task.grid):
                    task.cursor_cell = (row, col)
                    task._redraw()
                    env._publish()
                    for colour in counts:
                        counts[colour].add(_count_fill(env._rgba, colour))
            for colour, values in counts.items():
                self.assertEqual(len(values), 1, colour)
        finally:
            env.close()

    def test_the_marker_is_off_for_a_mouse_player(self):
        """Opt-in: the task a person opens is unchanged."""
        from neural_workshop.ui.monkeyladder import MonkeyLadder

        task = MonkeyLadder()
        try:
            self.assertFalse(task.cursor_enabled)
        finally:
            task.close()

    def test_neutral_mode_pays_exactly_one_outcome_per_action(self):
        """What a one-outcome-per-action runtime needs from this task."""
        env = self._env(neutral_outcomes=True)
        try:
            scalars, actions = [], 0
            for _ in range(STEP_LIMIT * 4):
                task = env.task
                port = None
                if task.phase == 'input' and env._response_open:
                    port = self._port_towards(task)
                    actions += 1
                _obs, events, done = env.step(port)
                scalars.extend(e['scalar'] for e in events
                               if e['type'] == 'outcome')
                if done:
                    break
        finally:
            env.close()
        self.assertEqual(len(scalars), actions)
        self.assertEqual(scalars.count(1.0), 3)
        self.assertEqual(scalars.count(-1.0), 0)

    def test_neutral_mode_still_cannot_be_talked_into_a_positive(self):
        """The extra outcomes are worth nothing, and change no verdict."""
        preview = a_frame_of(PREVIEW, 900)
        half = a_frame_of(CORRECT, 400)
        out = derive_ladder_outcome(half, 30, 30, ['d'], 1,
                                    preview_rgba=preview, neutral=True)
        self.assertEqual(out['scalar'], 0.0)
        full = a_frame_of(CORRECT, 900)
        out = derive_ladder_outcome(full, 30, 30, ['d'], 1,
                                    preview_rgba=preview, neutral=True)
        self.assertEqual(out['scalar'], 1.0)

    def test_the_cursor_stops_at_the_edges(self):
        env = self._env()
        try:
            task = env.task
            task.cursor_cell = (0, 0)
            for _ in range(10):
                task.move_cursor(-1, -1)
            self.assertEqual(task.cursor_cell, (0, 0))
            for _ in range(10):
                task.move_cursor(1, 1)
            self.assertEqual(task.cursor_cell,
                             (task.grid - 1, task.grid - 1))
        finally:
            env.close()


if __name__ == '__main__':
    unittest.main()
