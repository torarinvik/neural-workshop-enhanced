#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Fog of War agent boundary.

Three of these tests are the reason the task exists in the shape it
does, and they are worth naming up front:

* **A bump changes nothing.** Walking into a wall must leave the frame
  byte for byte as it was. An agent on a prediction-based intrinsic
  reward will do whichever thing makes the screen least predictable,
  and if a bump flickers anything at all it will stand in a corner
  bumping instead of exploring. This is checked by bumping.

* **The walker can actually get about.** A scripted policy has to
  reach a real number of distinct cells in two hundred ticks. An
  avatar sealed into one cell, or stood somewhere off the drawn
  surface, is indistinguishable from an agent that has not learned to
  explore, and that mistake has been made before and cost five
  experiments.

* **The dark is real.** A cell that has not been seen may not reach
  the frame, not even by one pixel. This is checked by changing an
  unseen cell and watching the bytes not move.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from envsupport import (FogOfWarEnv, derive_fog_outcome,  # noqa: F401
                        digest_rgba, make_fog_env, requires_env,
                        verify_fog_outcome)

#: Everything an observation is allowed to contain. A learner gets
#: pixels, when they were drawn, and -- once -- what the last move was
#: worth. No cells, no coordinates, no coverage, no world.
OBSERVATION_KEYS = frozenset((
    'frame_seq', 'timestamp_ns', 'width', 'height', 'rgba', 'done',
    'outcome'))

#: The ports, which the task keeps and the tests borrow. A learner is
#: told none of this.
STAY, UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3, 4
WAYS = (UP, DOWN, LEFT, RIGHT)

#: What the brief asks of the world, and what these tests hold it to.
MOBILITY_TICKS = 200
MOBILITY_CELLS = 20

#: Enough ticks for any run these tests configure, and a stop so a
#: broken one fails instead of spinning.
STEP_LIMIT = 4000


def colours():
    """The floor and walker fills. Imported late: the module needs a window."""
    from neural_workshop.ui.fogofwar import FLOOR, WALKER
    return FLOOR, WALKER


def a_frame_of(colour, pixels):
    """A fake framebuffer that is *pixels* pixels of one colour."""
    return (bytes(colour) + b'\xff') * pixels


def where(env):
    """The cell the walker is on. Privileged; tests only."""
    return env.task.at


def ahead_of(env, port):
    """The cell *port* would step onto, walkable or not."""
    from neural_workshop.ui.fogofwar import STEPS
    world, here = env.task.world, env.task.at
    dx, dy = STEPS[port]
    x, y = here % world.width + dx, here // world.width + dy
    if not (0 <= x < world.width and 0 <= y < world.height):
        return None
    return y * world.width + x


def a_wall_port(env):
    """A port that walks into a wall from where the walker stands."""
    for port in WAYS:
        cell = ahead_of(env, port)
        if cell is None or not env.task.world.walkable(cell):
            return port
    return None


def explore(env, ticks, seed=17):
    """A scripted walker that prefers somewhere it has not been.

    Not a policy anybody would train -- it reads the world directly --
    but it is scripted, it is deterministic, and what it proves is
    about the world rather than about learning: that there is
    somewhere to go and a way to get there.
    """
    task = env.task
    seen = {task.at}
    rng = random.Random(seed)
    for _tick in range(ticks):
        fresh = [port for port in WAYS
                 if ahead_of(env, port) is not None
                 and task.world.walkable(ahead_of(env, port))
                 and ahead_of(env, port) not in seen]
        env.step(rng.choice(fresh) if fresh else rng.choice(WAYS))
        seen.add(task.at)
    return seen


@requires_env
class FogWorldTests(unittest.TestCase):
    """The grid behind the fog, which needs no window at all."""

    def world(self, seed=5):
        from neural_workshop import fogworld
        return fogworld.generate(seed)

    def test_the_world_is_the_size_it_says(self):
        from neural_workshop import fogworld
        made = self.world()
        self.assertEqual((made.width, made.height),
                         (2 * fogworld.ROOMS_ACROSS + 1,
                          2 * fogworld.ROOMS_DOWN + 1))

    def test_the_same_seed_makes_the_same_world(self):
        self.assertEqual(self.world(9), self.world(9))

    def test_another_seed_makes_another_world(self):
        self.assertNotEqual(self.world(9), self.world(10))

    def test_the_walker_starts_somewhere_it_can_stand(self):
        for seed in range(8):
            made = self.world(seed)
            self.assertTrue(made.walkable(made.start), 'seed %d' % seed)

    def test_every_floor_cell_can_be_reached_from_the_start(self):
        """The sealed-in failure, ruled out where it would begin."""
        from neural_workshop.maze import adjacency, reachable
        for seed in range(8):
            made = self.world(seed)
            floor = made.open_cells()
            links = adjacency(made.width, made.height, floor)
            self.assertEqual(len(reachable(links, made.start)), len(floor),
                             'seed %d strands part of the world' % seed)

    def test_there_is_a_real_amount_of_world_to_walk(self):
        for seed in range(8):
            made = self.world(seed)
            self.assertGreater(len(made.open_cells()), 100, 'seed %d' % seed)

    def test_a_wall_is_not_walkable_and_neither_is_off_the_grid(self):
        made = self.world()
        wall = sorted(made.walls)[0]
        self.assertFalse(made.walkable(wall))
        self.assertFalse(made.walkable(-1))
        self.assertFalse(made.walkable(made.width * made.height))

    def test_the_eye_reaches_a_disc(self):
        from neural_workshop import fogworld
        made = self.world()
        middle = (made.height // 2) * made.width + made.width // 2
        seen = fogworld.visible(made, middle, 2)
        self.assertEqual(len(seen), 13)          # the r=2 disc
        self.assertIn(middle, seen)

    def test_the_eye_is_clipped_at_the_edge_of_the_world(self):
        from neural_workshop import fogworld
        made = self.world()
        seen = fogworld.visible(made, 0, 3)
        self.assertTrue(all(0 <= c < made.width * made.height for c in seen))
        self.assertLess(len(seen), len(fogworld.visible(
            made, (made.height // 2) * made.width + made.width // 2, 3)))

    def test_the_eye_reaches_further_when_told_to(self):
        from neural_workshop import fogworld
        made = self.world()
        middle = (made.height // 2) * made.width + made.width // 2
        self.assertGreater(len(fogworld.visible(made, middle, 4)),
                           len(fogworld.visible(made, middle, 2)))

    def test_coverage_is_the_share_of_the_floor_walked(self):
        from neural_workshop import fogworld
        made = self.world()
        floor = made.open_cells()
        self.assertEqual(fogworld.coverage(made, frozenset()), 0.0)
        self.assertEqual(fogworld.coverage(made, floor), 1.0)


@requires_env
class FogOutcomeTests(unittest.TestCase):
    """Reading a move's worth off two frames. No window needed."""

    def test_ground_found_scores_plus_one(self):
        floor, _walker = colours()
        before = a_frame_of(floor, 1000)
        after = a_frame_of(floor, 4000)
        out = derive_fog_outcome(after, 40, 40, ['a', 'b'], 1,
                                 before_rgba=before)
        self.assertEqual(out['scalar'], 1.0)

    def test_the_walker_counts_as_ground(self):
        """Standing on new ground must not cost what walking there won."""
        floor, walker = colours()
        before = a_frame_of(floor, 1000)
        after = a_frame_of(floor, 900) + a_frame_of(walker, 3100)
        out = derive_fog_outcome(after, 40, 40, ['a', 'b'], 1,
                                 before_rgba=before)
        self.assertEqual(out['scalar'], 1.0)

    def test_finding_nothing_owes_nothing(self):
        floor, _walker = colours()
        same = a_frame_of(floor, 1000)
        self.assertIsNone(derive_fog_outcome(same, 40, 40, ['a', 'b'], 1,
                                             before_rgba=same))

    def test_finding_nothing_is_zero_when_every_action_wants_one(self):
        floor, _walker = colours()
        same = a_frame_of(floor, 1000)
        out = derive_fog_outcome(same, 40, 40, ['a', 'b'], 1,
                                 before_rgba=same, neutral=True)
        self.assertEqual(out['scalar'], 0.0)

    def test_a_frame_that_lost_ground_is_never_a_positive(self):
        floor, _walker = colours()
        out = derive_fog_outcome(a_frame_of(floor, 100), 40, 40, ['a', 'b'],
                                 1, before_rgba=a_frame_of(floor, 4000),
                                 neutral=True)
        self.assertEqual(out['scalar'], 0.0)

    def test_a_crumb_of_growth_is_not_new_ground(self):
        """Below the threshold is the seam between cells, not a cell."""
        from nwenv.fog import NEW_GROUND_PIXELS
        floor, _walker = colours()
        before = a_frame_of(floor, 1000)
        after = a_frame_of(floor, 1000 + NEW_GROUND_PIXELS - 1)
        self.assertIsNone(derive_fog_outcome(after, 40, 40, ['a', 'b'], 1,
                                             before_rgba=before))

    def test_without_the_earlier_frame_there_is_no_verdict(self):
        """Fail closed: a claim nobody can check is not owed."""
        floor, _walker = colours()
        frame = a_frame_of(floor, 4000)
        self.assertIsNone(derive_fog_outcome(frame, 40, 40, ['a'], 1))
        self.assertIsNone(derive_fog_outcome(frame, 40, 40, ['a'], 1,
                                             neutral=True))

    def test_an_empty_frame_is_no_verdict(self):
        self.assertIsNone(derive_fog_outcome(b'', 0, 0, ['a'], 1,
                                             before_rgba=b'x'))

    def test_the_payload_says_nothing_about_the_world(self):
        floor, _walker = colours()
        out = derive_fog_outcome(a_frame_of(floor, 4000), 40, 40, ['a', 'b'],
                                 7, before_rgba=a_frame_of(floor, 100))
        self.assertEqual(set(out), {'scalar', 'evidence_digests',
                                    'receipt_id'})


@requires_env
class FogEnvTests(unittest.TestCase):
    """The boundary itself: ports, frames, outcomes and receipts."""

    def setUp(self):
        self.envs = []

    def tearDown(self):
        for env in self.envs:
            env.close()

    def env(self, **kw):
        kw.setdefault('seed', 4)
        kw.setdefault('worlds', 1)
        kw.setdefault('moves', 4000)
        made = FogOfWarEnv(**kw)
        self.envs.append(made)
        return made

    # --- the interface ---------------------------------------------------

    def test_an_observation_carries_nothing_but_pixels(self):
        env = self.env()
        for _step in range(30):
            obs, _events, done = env.step(random.choice(WAYS))
            self.assertLessEqual(set(obs), OBSERVATION_KEYS)
            if done:
                break

    def test_there_are_five_ports(self):
        self.assertEqual(self.env().n_actions, 5)

    def test_a_wider_decoder_can_drive_it(self):
        env = self.env(runtime_ports=8)
        self.assertEqual(env.n_actions, 8)
        before = where(env)
        env.step(7)                    # a spare port is a stay
        self.assertEqual(where(env), before)

    def test_a_narrower_decoder_is_refused(self):
        with self.assertRaises(ValueError):
            FogOfWarEnv(seed=1, runtime_ports=4)

    def test_naming_no_port_or_several_is_not_a_move(self):
        env = self.env()
        self.assertFalse(env.act(())['ok'])
        self.assertFalse(env.act((UP, DOWN))['ok'])

    def test_a_port_that_is_not_there_is_refused(self):
        env = self.env()
        self.assertFalse(env.act(99)['ok'])
        self.assertFalse(env.act(-1)['ok'])

    def test_only_one_move_fits_in_a_window(self):
        env = self.env()
        self.assertTrue(env.act(UP)['ok'])
        self.assertFalse(env.act(DOWN)['ok'])

    def test_staying_put_stays_put(self):
        env = self.env()
        before = where(env)
        env.step(STAY)
        self.assertEqual(where(env), before)

    # --- the three that matter -------------------------------------------

    def test_walking_into_a_wall_changes_not_one_byte(self):
        """The whole reason this task is drawn as bare as it is."""
        env = self.env()
        port = a_wall_port(env)
        self.assertIsNotNone(port, 'the walker started in the open')
        before = env.advance()
        stood = where(env)
        obs, _events, _done = env.step(port)
        self.assertEqual(where(env), stood, 'that was not a wall')
        self.assertEqual(digest_rgba(obs['rgba']),
                         digest_rgba(before['rgba']))

    def test_bumping_over_and_over_changes_nothing_over_and_over(self):
        env = self.env()
        port = a_wall_port(env)
        self.assertIsNotNone(port)
        first = digest_rgba(env.advance()['rgba'])
        for _again in range(12):
            obs, _events, _done = env.step(port)
            self.assertEqual(digest_rgba(obs['rgba']), first)

    def test_a_bump_is_never_paid_for(self):
        env = self.env(neutral_outcomes=True)
        port = a_wall_port(env)
        self.assertIsNotNone(port)
        paid = []
        for _again in range(10):
            _obs, events, _done = env.step(port)
            paid += [e['scalar'] for e in events if e['type'] == 'outcome']
        self.assertEqual(len(paid), 10, 'a bump got no verdict at all')
        self.assertEqual(set(paid), {0.0})

    def test_a_scripted_walker_gets_about(self):
        """The mobility precondition. Assume nothing; measure it."""
        for seed in range(5):
            env = self.env(seed=seed)
            seen = explore(env, MOBILITY_TICKS)
            self.assertGreaterEqual(
                len(seen), MOBILITY_CELLS,
                'seed %d reached only %d cells in %d ticks'
                % (seed, len(seen), MOBILITY_TICKS))

    def test_a_walker_that_gets_about_is_paid_for_it(self):
        env = self.env(neutral_outcomes=True)
        paid = []
        task = env.task
        rng = random.Random(2)
        seen = {task.at}
        for _tick in range(MOBILITY_TICKS):
            fresh = [p for p in WAYS
                     if ahead_of(env, p) is not None
                     and task.world.walkable(ahead_of(env, p))
                     and ahead_of(env, p) not in seen]
            _obs, events, _done = env.step(
                rng.choice(fresh) if fresh else rng.choice(WAYS))
            seen.add(task.at)
            paid += [e['scalar'] for e in events if e['type'] == 'outcome']
        self.assertGreater(sum(paid), 0, 'exploring earned nothing')

    def test_the_move_rate_says_the_world_is_walkable(self):
        env = self.env()
        explore(env, MOBILITY_TICKS)
        rate = env.mobility()
        self.assertGreater(rate['move_rate'], 0.5, rate)
        self.assertGreaterEqual(rate['cells_walked'], MOBILITY_CELLS)

    def test_an_unseen_cell_cannot_reach_the_frame(self):
        """The dark is real: change what is hidden, and nothing moves."""
        env = self.env()
        task = env.task
        hidden = next(cell for cell in range(task.world.width
                                             * task.world.height)
                      if cell not in task.revealed)
        before = digest_rgba(env.advance()['rgba'])

        walls = set(task.world.walls)
        walls.symmetric_difference_update({hidden})
        task.world = task.world._replace(walls=frozenset(walls))
        task._redraw()
        self.assertEqual(digest_rgba(env.advance()['rgba']), before,
                         'an unseen cell reached the screen')

        task.revealed.add(hidden)
        task._redraw()
        self.assertNotEqual(digest_rgba(env.advance()['rgba']), before,
                            'a revealed cell did not reach the screen')

    # --- determinism ------------------------------------------------------

    def test_the_same_seed_draws_the_same_frames(self):
        moves = [random.Random(8).choice(WAYS) for _ in range(40)]
        runs = []
        for _twice in range(2):
            env = self.env(seed=11)
            runs.append([digest_rgba(env.step(port)[0]['rgba'])
                         for port in moves])
        self.assertEqual(runs[0], runs[1])

    def test_another_seed_draws_another_world(self):
        first = digest_rgba(self.env(seed=11).observe()['rgba'])
        second = digest_rgba(self.env(seed=12).observe()['rgba'])
        self.assertNotEqual(first, second)

    def test_a_reset_puts_the_walker_back(self):
        env = self.env()
        explore(env, 30)
        env.reset(11)
        self.assertEqual(where(env), env.task.world.start)
        self.assertEqual(env.mobility()['attempts'], 0)

    # --- outcomes ---------------------------------------------------------

    def test_every_action_is_paid_when_the_runtime_wants_that(self):
        env = self.env(neutral_outcomes=True)
        paid = 0
        for _tick in range(40):
            _obs, events, done = env.step(random.choice(WAYS))
            paid += sum(1 for e in events if e['type'] == 'outcome')
            self.assertFalse(done)
        self.assertEqual(paid, 40)

    def test_only_the_moves_that_found_something_are_paid_otherwise(self):
        env = self.env()
        paid = []
        for _tick in range(60):
            _obs, events, _done = env.step(random.choice(WAYS))
            paid += [e['scalar'] for e in events if e['type'] == 'outcome']
        self.assertGreater(len(paid), 0, 'sixty moves found no ground at all')
        self.assertEqual(set(paid), {1.0})

    def test_the_first_frame_of_a_world_is_never_scored(self):
        env = self.env(neutral_outcomes=True)
        self.assertNotIn('outcome', env.observe())

    def test_the_outcome_arrives_once_and_then_is_gone(self):
        env = self.env(neutral_outcomes=True)
        for _step in range(STEP_LIMIT):
            obs, _events, done = env.step(random.choice(WAYS))
            if 'outcome' in obs:
                self.assertNotIn('outcome', env.observe())
                return
            if done:
                break
        self.fail('no outcome ever arrived')

    def test_a_run_ends_after_its_worlds(self):
        env = self.env(worlds=2, moves=12)
        for _step in range(STEP_LIMIT):
            _obs, _events, done = env.step(RIGHT)
            if done:
                self.assertEqual(env._round, 2)
                return
        self.fail('the run never ended')

    def test_a_world_can_be_bounded_in_ticks(self):
        """An agent that only ever stays still must not sit for ever."""
        env = self.env(worlds=1, moves=100000, round_tick_limit=25)
        for _step in range(STEP_LIMIT):
            _obs, _events, done = env.step(STAY)
            if done:
                self.assertGreaterEqual(env._round_timeouts, 1)
                return
        self.fail('the tick limit never fired')

    # --- verification -----------------------------------------------------

    def _first_outcome(self):
        env = self.env(neutral_outcomes=True)
        for _step in range(STEP_LIMIT):
            obs, _events, done = env.step(random.choice(WAYS))
            if 'outcome' in obs:
                return obs['outcome'], dict(obs), env
            if done:
                break
        self.fail('no outcome ever arrived')

    def test_an_outcome_verifies_against_its_own_frames(self):
        outcome, frame, env = self._first_outcome()
        self.assertTrue(verify_fog_outcome(
            outcome, frame['rgba'], frame['width'], frame['height'],
            env._archive, env._receipt_ledger))

    def test_it_fails_closed_without_the_archive_or_the_ledger(self):
        outcome, frame, env = self._first_outcome()
        self.assertFalse(verify_fog_outcome(
            outcome, frame['rgba'], frame['width'], frame['height'],
            env._archive, None))
        self.assertFalse(verify_fog_outcome(
            outcome, frame['rgba'], frame['width'], frame['height'],
            None, env._receipt_ledger))

    def test_it_fails_closed_without_the_frame_the_move_started_from(self):
        outcome, frame, env = self._first_outcome()
        partial = dict(env._archive)
        partial.pop(outcome['evidence_digests'][0], None)
        self.assertFalse(verify_fog_outcome(
            outcome, frame['rgba'], frame['width'], frame['height'],
            partial, env._receipt_ledger))

    def test_a_bent_scalar_is_refused(self):
        env = self.env(neutral_outcomes=True)
        for _step in range(STEP_LIMIT):
            obs, _events, done = env.step(random.choice(WAYS))
            outcome = obs.get('outcome')
            if outcome and outcome['scalar'] == 0.0:
                bent = dict(outcome)
                bent['scalar'] = 1.0
                self.assertFalse(verify_fog_outcome(
                    bent, obs['rgba'], obs['width'], obs['height'],
                    env._archive, env._receipt_ledger))
                return
            if done:
                break
        self.fail('no nothing-found outcome to bend')

    def test_another_move_s_receipt_is_refused(self):
        env = self.env(neutral_outcomes=True)
        seen = []
        for _step in range(STEP_LIMIT):
            obs, _events, done = env.step(random.choice(WAYS))
            if 'outcome' in obs:
                seen.append((obs['outcome'], dict(obs)))
            if len(seen) == 2 or done:
                break
        self.assertEqual(len(seen), 2, 'needed two moves')
        borrowed = dict(seen[0][0])
        borrowed['receipt_id'] = seen[1][0]['receipt_id']
        frame = seen[0][1]
        self.assertFalse(verify_fog_outcome(
            borrowed, frame['rgba'], frame['width'], frame['height'],
            env._archive, env._receipt_ledger))

    def test_a_made_up_receipt_is_refused(self):
        outcome, frame, env = self._first_outcome()
        forged = dict(outcome)
        forged['receipt_id'] = 999999
        self.assertFalse(verify_fog_outcome(
            forged, frame['rgba'], frame['width'], frame['height'],
            env._archive, env._receipt_ledger))

    def test_the_shipped_environment_builds(self):
        env = make_fog_env(seed=2)
        self.envs.append(env)
        self.assertEqual(env.n_actions, 5)
        self.assertTrue(env.task.persist)


if __name__ == '__main__':
    unittest.main()
