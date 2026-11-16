# -*- coding: utf-8 -*-
"""Shared checks for the tasks played with the drawn pointer.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random


def wins(model, rungs, seeds=2):
    """How the reference, an idle player and a random one fare: three
    lists of (rung, seed) that passed."""
    ref, idle, rand = [], [], []
    for rung in rungs:
        for s in range(seeds):
            dealt = model.deal(rung, seed=s)
            if model.play(dealt)[0]:
                ref.append((rung, s))
            if model.play(dealt, lambda run: [])[0]:
                idle.append((rung, s))
            draw = random.Random(s)
            if model.play(dealt, lambda run: [
                    draw.randrange(model.PORTS)])[0]:
                rand.append((rung, s))
    return ref, idle, rand


def settle(run, seconds, control=None):
    for _k in range(int(round(seconds * 60))):
        run.step(1 / 60.0, control)


def heard(task_id, model, rung=4, steps=900, seed=3):
    """Samples of sound the agent is given while the reference plays."""
    from nwenv import catalog
    env = catalog.env_class(task_id)(seed=seed, rung=rung, trials=3,
                                     adaptive=False)
    total = 0
    try:
        for _k in range(steps):
            task = env.task
            port = None
            if task.phase == 'playing' and task.run is not None:
                ports = model.autopilot(task.run)
                port = ports[0] if ports else None
            env.step(port)
            chunk = env._public_audio
            if chunk:
                total += len(chunk['audio_pcm'])
    finally:
        env.close()
    return total
