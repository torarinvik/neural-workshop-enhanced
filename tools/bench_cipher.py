#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Measure The Cipher Abyss, rung by rung.

For each rung: how big the rung's language is, how often build() gives
up, how long a deal takes, how many experiments the reference player
uses, how often its test answers were a majority vote rather than
unanimous, and how often each baseline player passes a dealt machine.

    cd tests && PYTHONPATH=.. ../.venv/bin/python ../tools/bench_cipher.py
    ... --rungs 1-60 --machines 200     (the full measurement)
    ... --rungs 1,7,25 --machines 20    (a quick look)

A shortcut player that passes more than 5% of a rung's machines is a
defect: the machines on that rung can be answered without finding out
what they do.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from collections import Counter

from neural_workshop import cipherabyss as M
from neural_workshop import cipherlang as L
from neural_workshop import hand as H


def _type(run, seq):
    return [M.SYM + v for v in seq] + [M.RUN]


class Scripted:
    """A player that queues whole inputs: answer(run, question) gives
    the row it will put in for a test question; experiment(run) gives
    the next experiment's input, or None to start the test."""

    def __init__(self, seed: int = 0) -> None:
        self.queue = []
        self.draw = random.Random(seed)

    def experiment(self, run):
        return None

    def answer(self, run, q):
        return q

    def __call__(self, run):
        if run.result is not None:
            return []
        if run.hand.down:
            return [H.RELEASE]
        if self.queue:
            return [self.queue.pop(0)]
        if run.entry:
            return [M.DELETE]
        if not run.testing:
            x = self.experiment(run) if run.left() > 0 else None
            if x is None:
                return [M.TEST]
        else:
            x = self.answer(run, run.question())
        self.queue = _type(run, x)
        return [self.queue.pop(0)]


class Identity(Scripted):
    """Says the machine gives back what it is given."""


class Repeat(Scripted):
    """Gives the last thing the machine said, whatever is asked."""

    def experiment(self, run):
        if run.log:
            return None
        return tuple(self.draw.randrange(run.level.k)
                     for _k in range(run.level.length))

    def answer(self, run, q):
        log = run.log + [(g, t) for g, t, _ok in run.answers]
        return log[-1][1] if log else q


class Commonest(Scripted):
    """Assumes the stage's commonest rule, without looking (the
    machine's rule is drawn evenly, so any one rule is as common as
    another: this takes the simplest)."""

    def answer(self, run, q):
        rule = M.truths(run.level)[0]
        k = run.level.k
        return L.run(rule, q, k, L.replay(rule, M.test_log(run), k))


class Greedy(Scripted):
    """Runs one random experiment and commits to the simplest rule that
    fits it."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self.rule = None

    def experiment(self, run):
        if run.log:
            return None
        return tuple(self.draw.randrange(run.level.k)
                     for _k in range(run.level.length))

    def answer(self, run, q):
        k = run.level.k
        if self.rule is None:
            mind = M.Mind(run.level, 0)
            mind.update(run.log)
            self.rule = next(iter(mind.alive), M.truths(run.level)[0])
        return L.run(self.rule, q, k,
                     L.replay(self.rule, M.test_log(run), k))


def idle(run):
    return []


def make_random(seed):
    draw = random.Random(seed)
    return lambda run: [draw.randrange(M.PORTS)]


BASELINES = (('idle', lambda s: idle), ('random', make_random),
             ('identity', Identity), ('repeat', Repeat),
             ('commonest', Commonest), ('greedy', Greedy))


def play(machine, pilot, budget=200000):
    run = M.Run(machine)
    n = 0
    while run.result is None and n < budget:
        ports = pilot(run)
        port = ports[0] if ports else None
        if port is not None:
            M.act(run, port)
        run.step(1 / 60.0)
        n += 1
    return run


def rungs_from(text):
    out = []
    for part in text.split(','):
        step = 1
        if '/' in part:
            part, step = part.split('/')
            step = int(step)
        if '-' in part:
            a, b = part.split('-')
            out += list(range(int(a), int(b) + 1, step))
        else:
            out.append(int(part))
    return out


def bench(rung, machines, seed=0):
    level = M.grade(rung)
    draw = random.Random(seed * 7919 + rung)
    fam = len(M.family(level))
    nones = built = passed = ref_failed = 0
    spent = []
    split = answered = 0
    deal_time = 0.0
    wins = Counter()
    while built < machines:
        t0 = time.perf_counter()
        m = M.build(level, random.Random(draw.getrandbits(32)))
        if m is None:
            nones += 1
            deal_time += time.perf_counter() - t0
            continue
        run = play(m, M.autopilot)
        deal_time += time.perf_counter() - t0
        if not (run.result and run.result[0]):
            ref_failed += 1
            continue                         # deal() would not hand it out
        built += 1
        passed += 1
        spent.append(len(run.log))
        split += run.mind.split
        answered += run.mind.answered
        for name, make in BASELINES:
            got = play(m, make(draw.getrandbits(16)), budget=4000).result
            wins[name] += bool(got and got[0])
    tries = built + nones
    # deal() hands out only machines the reference passes, so on dealt
    # rounds it passes all; ref_built is its rate on everything build()
    # made, before that filter.
    return dict(rung=rung, family=fam, ref_dealt=passed / max(1, built),
                ref_built=built / max(1, built + ref_failed), none_share=nones / max(1, tries),
                deal_s=deal_time / max(1, built), experiments=(
                    sum(spent) / max(1, len(spent))),
                majority=split / max(1, answered),
                **{n: wins[n] / max(1, built) for n, _m in BASELINES})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--rungs', default='1-60')
    ap.add_argument('--machines', type=int, default=200)
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args(argv)
    names = [n for n, _m in BASELINES]
    print('rung family none%  deal_s  exps  major%   ref%  built%  ' +
          '  '.join('%9s' % n for n in names))
    worst, worst_ref = 0.0, 1.0
    for r in rungs_from(a.rungs):
        row = bench(r, a.machines, a.seed)
        # On the two gentle rungs one look may be enough and there are
        # only a handful of machines, so the players that guess a rule
        # are let off there; the blind ones never are.
        easy = M.gentle(M.grade(r))
        shortcut = max(row[n] for n in names
                       if not (easy and n in ('commonest', 'greedy')))
        worst = max(worst, shortcut)
        worst_ref = min(worst_ref, row['ref_dealt'])
        print('%4d %6d %5.1f %7.3f %5.1f %6.1f  ' % (
            r, row['family'], 100 * row['none_share'], row['deal_s'],
            row['experiments'], 100 * row['majority']) +
            '%5.0f%% %6.1f%%  ' % (100 * row['ref_dealt'],
                                   100 * row['ref_built']) +
            '  '.join('%8.1f%%' % (100 * row[n]) for n in names)
            + ('   <-- shortcut' if shortcut > 0.05 else ''), flush=True)
    print('worst shortcut pass rate: %.1f%%' % (100 * worst))
    print('reference on dealt rounds: %.1f%% at worst' % (100 * worst_ref))
    return 0 if worst <= 0.05 and worst_ref == 1.0 else 1


if __name__ == '__main__':
    sys.exit(main())
