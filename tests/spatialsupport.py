# -*- coding: utf-8 -*-
"""What the spatial tasks' tests share: driving one trial through the
agent boundary with a policy, and drawing a screen at several rungs.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from uisupport import close_overlays, reset_window


def drive(task_id, rung, policy, seed=0, steps=600):
    """Outcome scalars of one trial, *policy(task)* giving each port
    (None to wait)."""
    from nwenv import catalog
    env = catalog.env_class(task_id)(seed=seed, rung=rung, trials=1,
                                     adaptive=False)
    scalars = []
    try:
        for _step in range(steps):
            task = env.task
            port = policy(task) if task.phase == 'playing' else None
            _obs, events, done = env.step(port)
            scalars += [e['scalar'] for e in events
                        if e.get('type') == 'outcome']
            if done or scalars:
                break
    finally:
        env.close()
        close_overlays()
        reset_window()
    return scalars


def right(task):
    return task.puzzle.answer


def wrong(task):
    return (task.puzzle.answer + 1) % len(task.puzzle.choices)


def draws(test, cls, rungs, seed=1):
    """Every rung draws, as playing and as judged, and the click targets
    cover every choice."""
    import random
    close_overlays()
    task = cls()
    try:
        for rung in rungs:
            task.rng = random.Random(seed)
            task.start_rung = rung
            task.total_trials = 1
            task.adaptive = False
            task.start_run()
            task.on_draw()
            test.assertEqual(task.phase, 'playing', rung)
            test.assertTrue(task.hits, rung)
            task.choose(task.puzzle.answer)
            task.on_draw()
            test.assertIn(task.phase, ('judged', 'playing'), rung)
    finally:
        task.close()
        close_overlays()
        reset_window()


def queued(pilot, state):
    """A drive policy from a model pilot that may hand back several
    ports at once: they go out one a step, in order, before the pilot
    is asked again."""
    pending = []

    def policy(task):
        if not pending:
            pending.extend(pilot(state(task)))
        return pending.pop(0) if pending else None
    return policy
