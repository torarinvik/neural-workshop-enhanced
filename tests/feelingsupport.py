# -*- coding: utf-8 -*-
"""Shared checks for the Emotion tasks, which all run on
:mod:`neural_workshop.feelings`.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

from neural_workshop import feelings as F


def outcomes(model, rungs, seeds=2):
    """For each dealt round: whether the reference passed, and which
    shortcut players (one fixed answer, or guessing) passed."""
    out = []
    for r in rungs:
        for seed in range(seeds):
            rnd = model.deal(r, seed=seed)
            wins = [k for k in range(F.PORTS)
                    if F.play(rnd, F.always(k))[0]]
            if F.play(rnd, F.at_random(seed))[0]:
                wins.append('random')
            out.append((r, seed, F.play(rnd)[0], wins))
    return out


def boundary(test, task_id, model, rung=1, idle_steps=6000):
    from handsupport import heard
    from spatialsupport import drive, queued
    pilot = queued(model.autopilot, lambda t: t.run)
    test.assertEqual(drive(task_id, rung, pilot, seed=1, steps=6000), [1.0])
    test.assertEqual(drive(task_id, rung, lambda t: None, seed=1,
                           steps=idle_steps), [-1.0])
    test.assertGreater(heard(task_id, model, rung=rung, steps=600), 0)
