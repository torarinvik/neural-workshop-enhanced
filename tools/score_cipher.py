#!/usr/bin/env python
"""Score a player of The Cipher Abyss on a fixed benchmark.

The benchmark is a fixed list of (rung, seed) rounds: for every stage,
its first rung and two rungs in, each with the same seeds every time,
the held-out family included (rungs 30 and up). A player is a function
taking a ``cipherabyss.Run`` and returning a list of ports, like
``cipherabyss.autopilot``; give it as ``module:function``.

    python tools/score_cipher.py                     # the reference player
    python tools/score_cipher.py --player mybot:act --seeds 5 --out r.jsonl
    python tools/score_cipher.py --rounds cipher_abyss_rounds.jsonl

With ``--rounds`` it scores a results file instead (the one a visible
session writes to the data folder, or one written with ``--out``).

Prints, per stage: rounds won, mean test accuracy, experiments used
against the reference player's, and bits per experiment.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('NW_HEADLESS', '1')

from neural_workshop import cipherabyss as M  # noqa: E402


def benchmark(seeds: int):
    """The fixed rounds: (rung, seed)."""
    rungs = []
    for start, _name in M.STAGES:
        rungs += [start, start + 2]
    rungs += [M.HELD_OUT_FROM, 46, 52]
    return [(r, 1000 + s) for r in sorted(set(rungs)) for s in range(seeds)]


def play(machine, pilot, budget=400000):
    run = M.Run(machine)
    n = 0
    while run.result is None and n < budget:
        ports = pilot(run)
        if ports:
            M.act(run, ports[0])
        run.step(1 / 60.0)
        n += 1
    return run


def table(rows):
    by = defaultdict(list)
    for r in rows:
        by[(M.STAGES.index(next(s for s in M.STAGES if s[1] == r['stage'])),
            r['stage'])].append(r)
    print('%-26s %6s %6s %9s %8s %6s' % ('stage', 'rounds', 'won%', 'accuracy',
                                         'exps/ref', 'bits'))
    total = []
    for (_i, name), rs in sorted(by.items()):
        acc = [r['accuracy'] for r in rs if r['accuracy'] is not None]
        ref = sum(r['reference_experiments'] for r in rs) or 1
        print('%-26s %6d %5.0f%% %9.2f %8.2f %6.2f' % (
            name, len(rs), 100 * sum(r['won'] for r in rs) / len(rs),
            sum(acc) / len(acc) if acc else 0.0,
            sum(r['experiments'] for r in rs) / ref,
            sum(r['bits_per_experiment'] for r in rs) / len(rs)))
        total += rs
    print('overall: %d of %d rounds won (%.0f%%)' % (
        sum(r['won'] for r in total), len(total),
        100 * sum(r['won'] for r in total) / max(1, len(total))))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--player', default='neural_workshop.cipherabyss:autopilot')
    ap.add_argument('--seeds', type=int, default=3)
    ap.add_argument('--out', help='write each round as a JSON line here')
    ap.add_argument('--rounds', help='score this results file instead')
    a = ap.parse_args(argv)
    if a.rounds:
        with open(a.rounds) as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        table(rows)
        return 0
    mod, fn = a.player.split(':')
    pilot = getattr(importlib.import_module(mod), fn)
    rows = []
    out = open(a.out, 'w') if a.out else None
    for rung, seed in benchmark(a.seeds):
        run = play(M.deal(rung, seed=seed), pilot)
        row = M.metrics(run)
        rows.append(row)
        if out:
            out.write(json.dumps(row) + '\n')
    if out:
        out.close()
    table(rows)
    return 0


if __name__ == '__main__':
    sys.exit(main())
