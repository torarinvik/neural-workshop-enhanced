#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A smaller frame at the boundary: drawn at full size, read back at a
half or a quarter of each side, and judged the same.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from nwenv import catalog, frames
from nwenv.taskenv import TaskEnv

#: The first-steps families; and one in five of every other task built
#: on the shared boundary.
FAMILY_TASKS = [t for members in catalog.FAMILIES.values() for t in members]
OTHERS = [t for t in catalog.task_ids()
          if t not in FAMILY_TASKS
          and issubclass(catalog.env_class(t), TaskEnv)][::5]


def play(task_id, scale, seed, steps=600, outcomes=6):
    """What a run of random presses is paid, the presses drawn without
    looking at the frame, so both sizes are pressed the same."""
    env = catalog.env_class(task_id)(seed=seed, frame_scale=scale)
    rng = random.Random(seed)
    paid, size = [], None
    try:
        for _step in range(steps):
            port = (rng.randrange(env.ports) if rng.random() < 0.3
                    else None)
            obs, events, done = env.step(port)
            size = (env._width, env._height)
            paid += [(e['type'], e.get('scalar'), e.get('receipt_id'))
                     for e in events if e['type'] in ('outcome', 'run_end')]
            if done or sum(p[0] == 'outcome' for p in paid) >= outcomes:
                break
    finally:
        env.close()
    return paid, size


class TheSmallFrame(unittest.TestCase):

    def test_only_a_whole_share_is_taken(self):
        for bad in (0.0, 0.3, 1.5, -1.0):
            with self.assertRaises(ValueError):
                catalog.env_class('short_maze')(seed=1, frame_scale=bad)

    def test_the_gpu_takes_the_pixels_a_full_readback_would(self):
        from neural_workshop import state
        env = catalog.env_class('match_shapes')(seed=1, rung=3)
        try:
            env.step(None)
            window = state.window
            window.switch_to()
            env.task.on_draw()
            w, h, full = frames.capture_rgba(window)
            for scale in (0.5, 0.25):
                sw, sh, small = frames.capture_rgba(window, scale)
                self.assertEqual((sw, sh), frames.scaled_size(w, h, scale))
                self.assertEqual(small,
                                 frames.sample_rgba(full, w, h, sw, sh))
        finally:
            env.close()

    def test_a_run_is_judged_the_same_at_both_sizes(self):
        """The first-steps families deal from their seed alone, so two
        runs, one at each size, can be set side by side."""
        judged = 0
        for task_id in FAMILY_TASKS:
            for seed in (1, 2):
                full, full_size = play(task_id, 1.0, seed)
                small, small_size = play(task_id, 0.25, seed)
                self.assertEqual(small, full, (task_id, seed))
                self.assertEqual(small_size,
                                 frames.scaled_size(*full_size, 0.25))
                judged += sum(p[0] == 'outcome' for p in full)
        self.assertGreater(judged, 300)

    def test_every_verdict_reads_the_same_small(self):
        """Other tasks may deal from more than their seed (a clip
        rotation kept on disk, say), so there each frame of one run is
        read at both sizes: every verdict paid on the full frame, and
        every tenth frame besides, read the same off its quarter."""
        from nwenv.outcome import _label_run_scalar
        read = 0
        for task_id in OTHERS:
            env = catalog.env_class(task_id)(seed=1)
            rng = random.Random(1)
            try:
                for step in range(600):
                    port = (rng.randrange(env.ports) if rng.random() < 0.3
                            else None)
                    _obs, events, done = env.step(port)
                    paid = [e for e in events if e['type'] == 'outcome']
                    if not paid and step % 10:
                        continue
                    w, h, rgba = env._width, env._height, env._rgba
                    sw, sh = frames.scaled_size(w, h, 0.25)
                    small = frames.sample_rgba(rgba, w, h, sw, sh)
                    self.assertEqual(_label_run_scalar(small, sw, sh)[2],
                                     _label_run_scalar(rgba, w, h)[2],
                                     (task_id, step))
                    for event in paid:
                        if event['scalar'] != 0.0:
                            self.assertEqual(
                                _label_run_scalar(small, sw, sh)[2],
                                event['scalar'], (task_id, step))
                            read += 1
                    if done:
                        break
            finally:
                env.close()
        self.assertGreater(read, 100)

if __name__ == '__main__':
    unittest.main()
