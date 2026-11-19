#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stepping the frame families a shown frame at a time.

The memory families declare that they may be driven at two steps a
second, one step a shown frame. This checks that at that rate every
frame of a trial is seen once and that a trial is judged as it is at
ten steps a second. The older frame tasks may opt in to the same rate,
and are checked the same way; at their usual rates they keep their
own tick.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from memorysupport import drive

from neural_workshop import framed
from neural_workshop.ui.clocked import ClockedTask
from neural_workshop.ui.framed import FrameTask
from nwenv import catalog
from nwenv.framed import FRAME_HZ, FrameRung

#: Every task that declares it may be stepped a frame at a time.
STEPPED = [task for task in catalog.task_ids()
           if issubclass(catalog.env_class(task), FrameRung)]
#: Those of them that put one question and take one answer; the walks
#: from memory test their own rate.
IDS = [task for task in STEPPED
       if issubclass(catalog.ui_class(task), FrameTask)]
#: The frame tasks written before the rate was declared, which may opt
#: in to it.
OLDER = ('shape_back', 'hidden_cue', 'sound_back', 'changed_tile',
         'swapped_boxes')
POLICIES = {
    'right': (lambda t: t.puzzle.answer, None),
    'wrong': (lambda t: (t.puzzle.answer + 1) % len(t.puzzle.choices),
              None),
    'early': (lambda t: t.puzzle.answer, 0),
    'none': (lambda t: None, None),
    'first': (lambda t: 1, None),
}


class TheRate(unittest.TestCase):

    def test_the_frame_families_take_one_step_a_frame(self):
        self.assertEqual(FRAME_HZ, 2.0)
        for task_id in STEPPED:
            env = catalog.env_class(task_id)(seed=1, rung=1, trials=1,
                                             adaptive=False,
                                             frame_hz=FRAME_HZ)
            env.close()

    def test_older_tasks_take_a_frame_a_step_and_no_other_slow_rate(self):
        for task_id in OLDER:
            env = catalog.env_class(task_id)(seed=1, rung=1, trials=1,
                                             adaptive=False, frame_hz=2.0)
            self.assertEqual(env.task.LONGEST_TICK, 0.5)
            env.close()
            env = catalog.env_class(task_id)(seed=1, rung=1, trials=1,
                                             adaptive=False, frame_hz=10.0)
            self.assertEqual(env.task.LONGEST_TICK, 0.1)
            self.assertEqual(env.task.SUBSTEP, ClockedTask.SUBSTEP)
            env.close()
            for hz in (1.0, 5.0):
                with self.assertRaises(ValueError):
                    catalog.env_class(task_id)(seed=1, rung=1, trials=1,
                                               adaptive=False, frame_hz=hz)

    def test_older_tasks_are_judged_the_same_a_frame_a_step(self):
        for task_id in OLDER:
            for rung in (1, 3):
                for name, (pick, early) in POLICIES.items():
                    slow = drive(task_id, pick, rung, early=early, seed=3,
                                 frame_hz=FRAME_HZ, steps=400)
                    fast = drive(task_id, pick, rung, early=early, seed=3,
                                 frame_hz=10.0, steps=2000)
                    self.assertEqual(slow, fast, (task_id, rung, name))
                    self.assertEqual(len(slow), 1, (task_id, rung, name))

    def test_older_tasks_keep_their_longest_tick(self):
        from neural_workshop.ui.inmind import ChangedTile
        from neural_workshop.ui.lookback import HiddenCue
        self.assertEqual(ClockedTask.LONGEST_TICK, 0.1)
        self.assertEqual(HiddenCue.LONGEST_TICK, 0.1)
        self.assertEqual(ChangedTile.LONGEST_TICK, 0.1)

    def test_every_frame_is_seen_once(self):
        self.assertGreaterEqual(len(IDS), 8)
        for task_id in IDS[::4]:
            for rung in (1, 3):
                env = catalog.env_class(task_id)(
                    seed=2, rung=rung, trials=1, adaptive=False,
                    frame_hz=FRAME_HZ)
                seen = []
                try:
                    for _step in range(200):
                        task = env.task
                        if task.phase != 'playing' or task.run is None:
                            env.step(None)
                            continue
                        f, _showing = framed.frame_at(task.puzzle,
                                                      task.run.t)
                        seen.append(f)
                        if task.run.open:
                            break
                        env.step(None)
                finally:
                    env.close()
                self.assertEqual(seen, list(range(len(seen))), task_id)
                self.assertGreaterEqual(len(seen), 2, task_id)

    def test_a_trial_is_judged_the_same_at_both_rates(self):
        for task_id in IDS:
            for rung in (1, 2):
                for name, (pick, early) in POLICIES.items():
                    slow = drive(task_id, pick, rung, early=early, seed=3,
                                 frame_hz=FRAME_HZ, steps=400)
                    fast = drive(task_id, pick, rung, early=early, seed=3,
                                 frame_hz=10.0, steps=2000)
                    self.assertEqual(slow, fast, (task_id, rung, name))
                    self.assertEqual(len(slow), 1, (task_id, rung, name))


if __name__ == '__main__':
    unittest.main()
