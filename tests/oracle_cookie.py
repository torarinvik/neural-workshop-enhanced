#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A thief who can count, used to check what Cookie Thief's rungs promise.

Four players, and the difference between them is the point.

:func:`steady` brakes when braking would land him on the quota, and
ignores the golden cookie. He is the proof that every rung is winnable
without gambling.

:func:`bold` is steady with a number bolted on: how many cookies past
the quota he is willing to carry. The quota is the bar and the haul is
the margin, and those are two different questions — stopping dead on
the bar is the safest round available and it is not the richest one.
``--haul`` sweeps the greed from nothing to the width of the band and
prints what each step of it buys and what it costs.

:func:`greedy` is the same player with one change: he takes the golden
cookie whenever it is offered. Whether that is worth doing is a
measurement rather than an opinion, and ``--gold`` is where it is taken.

:func:`impulsive` never looks at the jar at all. He eats flat out and
brakes only once she is in the doorway, which makes him the reactive
half of the task on its own — and ``--curve`` sweeps the warning to
find the beat at which he stops being able to stop. That number is the
task's stop-signal threshold and it falls straight out of the physics:
he can inhibit exactly while the warning is at least as long as his
stopping distance.

None of them can see :attr:`Setup.trigger`, :attr:`Setup.deadline` or
the decoy roster. They read the jar, the boy's speed and the doorway,
all of which the screen draws.

Run it::

    cd tests && PYTHONPATH=.. ../.venv/bin/python oracle_cookie.py
    cd tests && PYTHONPATH=.. ../.venv/bin/python oracle_cookie.py --curve 7
    cd tests && PYTHONPATH=.. ../.venv/bin/python oracle_cookie.py --gold

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import argparse
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('NW_HEADLESS', '1')

from neural_workshop import cookiethief as C            # noqa: E402


def steady(thief, setup):
    """Brake once braking would land him on the quota. Ignores the gold."""
    if C.alarming(thief):
        return C.FREEZE
    if C.landing(thief, setup.grade) >= setup.grade.quota:
        return C.FREEZE
    return C.REACH


def bold(margin):
    """A thief who carries *margin* cookies past the quota before stopping.

    At zero he is :func:`steady`. Above it he is aiming at a number
    inside the band she notices from, which is safe only while he is
    already stopped when she gets there — so every extra cookie is
    bought with a beat of the stop he still has to make.
    """
    def player(thief, setup):
        if C.alarming(thief):
            return C.FREEZE
        if C.landing(thief, setup.grade) >= setup.grade.quota + margin:
            return C.FREEZE
        return C.REACH
    player.__name__ = 'bold%d' % margin
    return player


def greedy(thief, setup):
    """The same, except that he grabs the golden one the moment he sees it."""
    if thief.gold_on_offer and not C.alarming(thief):
        return C.LUNGE
    return steady(thief, setup)


def timed(thief, setup):
    """Banks the golden one before he has it, and takes it once slowed.

    The lock is the cost and speed is what makes the lock expensive, so
    the trick is to count the gold as already his the moment it is
    offered — which lets him start braking four cookies early — and only
    reach for it once braking has taken the sting out. If the window is
    about to close he takes it anyway; short of the quota is a loss too.
    """
    grade = setup.grade
    if C.alarming(thief):
        return C.FREEZE
    if thief.gold_on_offer:
        closing = thief.beat >= thief.gold_from + C.GOLD_BEATS - 1
        if closing or thief.speed <= grade.brake * 1.2:
            return C.LUNGE
    credit = grade.gold if thief.gold_on_offer else 0
    if C.landing(thief, grade) + credit >= grade.quota:
        return C.FREEZE
    return C.REACH


def impulsive(thief, setup):
    """Flat out until she is in the doorway. Reaction and nothing else."""
    return C.FREEZE if C.alarming(thief) else C.REACH


PLAYERS = {'steady': steady, 'greedy': greedy, 'timed': timed,
           'impulsive': impulsive}


def play(level, seed=0, player=steady, warn=None, fumble=0.0, rng=None):
    """One round.

    *warn* overrides the rung's warning, for the curve. *fumble* is the
    share of beats on which the player presses something at random
    instead of what it meant to, which is the only way to ask what a
    rung costs somebody who has not got the control down yet — and the
    only setting under which two policies that both clear every round
    can be told apart at all.
    """
    setup = C.generate(level, seed=seed)
    if warn is not None:
        setup = setup._replace(grade=setup.grade._replace(warn=warn))
    rng = rng or random.Random(seed)
    thief = C.Thief()
    while not C.over(thief, setup):
        port = player(thief, setup)
        if fumble and rng.random() < fumble:
            port = rng.choice((C.REACH, C.FREEZE, C.LUNGE))
        C.press(thief, port, setup)
        C.beat(thief, setup)
    return thief, setup


def survey(deals=300, player=steady, seed=0, fumble=0.0):
    """Every rung, played *deals* times, against what guessing pays."""
    rng = random.Random(seed)
    rows = []
    for level, grade in enumerate(C.GRADES, 1):
        won = caught = short = 0
        beats = 0
        for _deal in range(deals):
            thief, setup = play(level, seed=rng.randrange(1 << 30),
                                player=player, fumble=fumble, rng=rng)
            beats += thief.beat
            if C.cleared(thief, setup):
                won += 1
            elif thief.caught:
                caught += 1
            else:
                short += 1
        rows.append((level, grade, won, caught, short, beats / float(deals)))
    return rows


def curve(level, deals=300, seed=0, player=impulsive):
    """How late she can arrive before he can no longer stop.

    The measurement the design is named for. Everything but the warning
    is held at the rung's own settings, so what moves is the one thing
    being swept.
    """
    rng = random.Random(seed)
    grade = C.GRADES[level - 1]
    out = []
    for warn in range(0, grade.stopping + 4):
        clean = 0
        for _deal in range(deals):
            thief, setup = play(level, seed=rng.randrange(1 << 30),
                                player=player, warn=warn)
            clean += 1 if thief.caught == 0 else 0
        out.append((warn, clean / float(deals)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--deals', type=int, default=300)
    ap.add_argument('--player', default='steady', choices=sorted(PLAYERS))
    ap.add_argument('--curve', type=int, default=0,
                    help='sweep the warning at this rung instead')
    ap.add_argument('--fumble', type=float, default=0.0,
                    help='share of beats pressed at random')
    ap.add_argument('--gold', action='store_true',
                    help='the three gold policies, at a range of fumble rates')
    ap.add_argument('--floor', action='store_true',
                    help='what random presses are worth, per rung')
    ap.add_argument('--haul', action='store_true',
                    help='what carrying past the quota buys, and costs')
    args = ap.parse_args(argv)

    if args.curve:
        grade = C.GRADES[args.curve - 1]
        print('rung %d, %s: stopping distance %d beats, own warning %d'
              % (args.curve, grade.name, grade.stopping, grade.warn))
        print('%6s  %s' % ('warn', 'not caught'))
        for warn, clean in curve(args.curve, deals=args.deals):
            print('%6d  %6.0f%%  %s' % (warn, 100 * clean,
                                        '#' * int(round(40 * clean))))
        return 0

    if args.gold:
        # Every one of these clears every round when it is played
        # perfectly, so a table of clean runs would say nothing. What
        # separates them is what a slip costs, which is what fumble is.
        print('%-22s %7s %8s %8s %8s'
              % ('rung', 'fumble', 'no gold', 'on sight', 'timed'))
        for level, grade in enumerate(C.GRADES, 1):
            if not grade.gold:
                continue
            for fumble in (0.0, 0.05, 0.10, 0.20):
                got = []
                for who in (steady, greedy, timed):
                    row = survey(deals=args.deals, player=who,
                                 fumble=fumble)[level - 1]
                    got.append(100.0 * row[2] / args.deals)
                print('%-22s %6.0f%% %7.0f%% %7.0f%% %7.0f%%'
                      % (grade.name if fumble == 0.0 else '', 100 * fumble,
                         got[0], got[1], got[2]))
        return 0

    if args.haul:
        # The quota is the bar and the haul is the margin. Stopping dead
        # on the bar is the safest round there is; whether it is the
        # best one is a measurement, and this is it.
        print('%-22s %7s %7s %7s %7s'
              % ('rung', 'greed', 'clean', 'haul', 'caught'))
        for level, grade in enumerate(C.GRADES, 1):
            for margin in range(0, grade.spread + 2):
                rng = random.Random(level * 100 + margin)
                clean = caught = 0
                total = 0
                for _deal in range(args.deals):
                    thief, setup = play(level, seed=rng.randrange(1 << 30),
                                        player=bold(margin))
                    total += C.haul(thief)
                    clean += 1 if C.cleared(thief, setup) else 0
                    caught += 1 if thief.caught else 0
                print('%-22s %7d %6.0f%% %7.1f %6.0f%%'
                      % (grade.name if not margin else '', margin,
                         100.0 * clean / args.deals, total / float(args.deals),
                         100.0 * caught / args.deals))
        return 0

    if args.floor:
        print('%-22s %8s' % ('rung', 'guessing'))
        for level, grade in enumerate(C.GRADES, 1):
            print('%-22s %7.0f%%'
                  % (grade.name, 100 * C.rehearse(level, deals=args.deals)))
        return 0

    print('%-22s %5s %5s %5s %6s %6s %6s %7s'
          % ('rung', 'quota', 'stop', 'warn', 'clear', 'caught', 'short',
             'beats'))
    worst = 1.0
    for level, grade, won, caught, short, beats in survey(
            deals=args.deals, player=PLAYERS[args.player],
            fumble=args.fumble):
        worst = min(worst, won / float(args.deals))
        print('%-22s %5d %5d %5d %5.0f%% %5.0f%% %5.0f%% %7.1f'
              % ('%d %s' % (level, grade.name), grade.quota, grade.stopping,
                 grade.warn, 100.0 * won / args.deals,
                 100.0 * caught / args.deals, 100.0 * short / args.deals,
                 beats))
    print('\nworst rung: %.0f%%' % (100 * worst))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
