# -*- coding: utf-8 -*-
"""What the memory families' tests share: counting what a player who
sees only the frame the question is put on could do, and driving one
trial through the agent boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict


def best_from_view(deal, view, n=6000, seed=7):
    """How often the best player who sees only ``view(puzzle)`` is
    right, fitted on one half of *n* deals and scored on the other, so
    that a view that only seems to help by chance does not."""
    rng = random.Random(seed)
    puzzles = [deal(rng) for _d in range(n)]
    fit, score = puzzles[:n // 2], puzzles[n // 2:]
    seen = defaultdict(Counter)
    for p in fit:
        seen[view(p)][p.answer] += 1
    right = 0
    for p in score:
        counts = seen.get(view(p))
        guess = counts.most_common(1)[0][0] if counts else 0
        right += guess == p.answer
    return right / len(score)


def per_port(test, deal, feature, ports, n=20000, seed=11, delta=0.035):
    """For every port and every value of what that port shows, the port
    is the answer about one time in four."""
    rng = random.Random(seed)
    seen, hit = Counter(), Counter()
    for _d in range(n):
        p = deal(rng)
        for port in range(ports):
            key = (port, feature(p, port))
            seen[key] += 1
            hit[key] += p.answer == port
    for key, count in seen.items():
        if count >= 1000:
            test.assertAlmostEqual(hit[key] / count, 0.25, delta=delta,
                                   msg=key)


def rate(deal, player, n=6000, seed=5):
    """How often *player(puzzle, rng)* is right over *n* deals."""
    rng = random.Random(seed)
    right = 0
    for _d in range(n):
        p = deal(rng)
        right += player(p, rng) == p.answer
    return right / n


def drive(name, pick, rung=1, early=None, seed=1, frame_hz=60.0,
          steps=4000):
    """Scalars paid for one trial: *early* is pressed before the
    question is put, *pick(task)* chooses once it is."""
    from nwenv import catalog
    from uisupport import close_overlays, reset_window
    env = catalog.env_class(name)(seed=seed, rung=rung, trials=1,
                                  adaptive=False, frame_hz=frame_hz)
    scalars = []
    try:
        for _step in range(steps):
            task = env.task
            port = None
            if task.phase == 'playing' and task.run is not None:
                port = pick(task) if task.run.open else early
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
