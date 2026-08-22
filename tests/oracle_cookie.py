#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A thief who can read the door, used to check what the rungs promise.

Every player here reads the same three things a person reads: the jar,
the door, and who is in the doorway. None of them can see
:attr:`Setup.trigger`, :attr:`Setup.deadline` or the decoy roster.

:func:`careful` never takes a grab that could possibly bring her — he
stops at the edge of the shaded zone and leaves. He is the proof that
every rung is winnable without gambling at all.

:func:`bold` is the same player with one number: how far into the shaded
zone he is willing to push the door. Zero is :func:`careful`. ``--haul``
sweeps it and prints what each step of greed buys and what it costs,
which is the only honest way to say where the marginal cookie turns.

:func:`impulsive` never looks at the door. He grabs every beat and
leaves only once there is somebody visibly in the doorway, which makes
him the reactive half of the task on its own — he clears exactly the
rungs that still have a warning and none of the rungs that do not.

Run it::

    cd tests && PYTHONPATH=.. ../.venv/bin/python oracle_cookie.py
    cd tests && PYTHONPATH=.. ../.venv/bin/python oracle_cookie.py --haul
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


def _her(thief):
    """Is the one who ends rounds actually there?"""
    return thief.who == C.MOTHER and thief.phase in (C.COMING, C.WATCHING)


def bold(over=0, target=None, gold=False):
    """A thief willing to push the door *over* points into the shaded zone.

    At ``over=0`` he never takes a grab that could bring her, which is
    :func:`careful`. Every point above that is a step further into the
    range she might be waiting in.

    *target* caps how many he is willing to end up with; ``None`` means
    he takes whatever the ceiling allows. *gold* is whether he reaches
    for the golden one when it is offered.
    """
    def player(thief, setup):
        grade = setup.grade
        if _her(thief):
            return C.LEAVE
        if target is not None and thief.eaten >= target:
            return C.LEAVE
        if gold and thief.gold_on_offer:
            return C.LUNGE
        if C.after_a_grab(thief, grade) < C.SAFE + over:
            return C.GRAB
        # Waiting takes the noise back off but never the gap in the jar,
        # so it is worth waiting only while the floor alone would leave
        # room for another grab.
        if C.floor_of(thief, grade) + grade.notice + grade.opening \
                < C.SAFE + over:
            return C.WAIT
        return C.LEAVE
    player.__name__ = 'bold%d%s' % (over, '+gold' if gold else '')
    return player


careful = bold(0)
careful.__name__ = 'careful'


def greedy(thief, setup):
    """Careful about the door, and helpless about the golden one."""
    return bold(0, gold=True)(thief, setup)


def impulsive(thief, setup):
    """Takes every grab short of a certainty; leaves only on sight.

    Reaction and nothing else, which is the whole point of him. He does
    read the door — a thief who ignored it entirely would trip her
    before he had the quota and come up short rather than caught, which
    says nothing about reacting — but he reads it only to avoid the
    grabs that are *bound* to bring her, and he stops for her only once
    she is visibly there.

    So he is what a rung with a warning can still be beaten by, and what
    a rung without one cannot: on those, the grab that brings her is one
    she is already looking at.
    """
    if _her(thief):
        return C.LEAVE
    grade = setup.grade
    if C.after_a_grab(thief, grade) < grade.limit:
        return C.GRAB
    if C.floor_of(thief, grade) + grade.notice + grade.opening < grade.limit:
        return C.WAIT
    return C.LEAVE


PLAYERS = {'careful': careful, 'greedy': greedy, 'impulsive': impulsive,
           'bold1': bold(1), 'bold5': bold(5), 'bold10': bold(10)}


def play(level, seed=0, player=careful, warn=None, fumble=0.0, rng=None):
    """One round.

    *warn* overrides the rung's warning, for the curve. *fumble* is the
    share of beats on which the player presses something at random
    instead of what it meant to, which is the only way to ask what a
    rung costs somebody who has not got it down yet.
    """
    setup = C.generate(level, seed=seed)
    if warn is not None:
        setup = setup._replace(grade=setup.grade._replace(warn=warn))
    rng = rng or random.Random(seed)
    thief = C.Thief()
    while not C.over(thief, setup):
        port = player(thief, setup)
        if fumble and rng.random() < fumble:
            port = rng.choice((C.GRAB, C.LEAVE, C.LUNGE, C.WAIT))
        C.press(thief, port, setup)
        C.beat(thief, setup)
    return thief, setup


def survey(deals=300, player=careful, seed=0, fumble=0.0):
    """Every rung, played *deals* times."""
    rng = random.Random(seed)
    rows = []
    for level, grade in enumerate(C.GRADES, 1):
        won = caught = short = 0
        beats = total = 0
        for _deal in range(deals):
            thief, setup = play(level, seed=rng.randrange(1 << 30),
                                player=player, fumble=fumble, rng=rng)
            beats += thief.beat
            total += C.haul(thief)
            if C.cleared(thief, setup):
                won += 1
            elif thief.caught:
                caught += 1
            else:
                short += 1
        rows.append((level, grade, won, caught, short, beats / float(deals),
                     total / float(deals)))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--deals', type=int, default=300)
    ap.add_argument('--player', default='careful', choices=sorted(PLAYERS))
    ap.add_argument('--fumble', type=float, default=0.0,
                    help='share of beats pressed at random')
    ap.add_argument('--haul', action='store_true',
                    help='what pushing into the shaded zone buys, and costs')
    ap.add_argument('--gold', action='store_true',
                    help='the golden one, at a range of fumble rates')
    ap.add_argument('--floor', action='store_true',
                    help='what random presses are worth, per rung')
    args = ap.parse_args(argv)

    if args.haul:
        # The quota is the bar and the haul is the margin. Leaving at
        # the edge of the shaded zone is the safest round there is;
        # whether it is the best one is a measurement, and this is it.
        print('%-22s %7s %7s %7s %7s'
              % ('rung', 'over', 'clean', 'haul', 'caught'))
        for level, grade in enumerate(C.GRADES, 1):
            steps = sorted({0, grade.notice // 2, grade.notice,
                            grade.notice + grade.opening, grade.spread})
            for over in steps:
                row = survey(deals=args.deals, player=bold(over))[level - 1]
                print('%-22s %7d %6.0f%% %7.1f %6.0f%%'
                      % (grade.name if not over else '', over,
                         100.0 * row[2] / args.deals, row[6],
                         100.0 * row[3] / args.deals))
        return 0

    if args.gold:
        print('%-22s %7s %8s %8s' % ('rung', 'fumble', 'no gold', 'gold'))
        for level, grade in enumerate(C.GRADES, 1):
            if not grade.gold:
                continue
            for fumble in (0.0, 0.05, 0.10, 0.20):
                one = survey(deals=args.deals, player=bold(0),
                             fumble=fumble)[level - 1]
                two = survey(deals=args.deals, player=bold(0, gold=True),
                             fumble=fumble)[level - 1]
                print('%-22s %6.0f%% %7.1f  %7.1f'
                      % (grade.name if not fumble else '', 100 * fumble,
                         one[6], two[6]))
        return 0

    if args.floor:
        print('%-22s %8s' % ('rung', 'guessing'))
        for level, grade in enumerate(C.GRADES, 1):
            print('%-22s %7.0f%%'
                  % (grade.name, 100 * C.rehearse(level, deals=args.deals)))
        return 0

    print('%-22s %5s %5s %5s %6s %6s %6s %7s %6s'
          % ('rung', 'quota', 'room', 'warn', 'clean', 'caught', 'short',
             'beats', 'haul'))
    worst = 1.0
    for level, grade, won, caught, short, beats, got in survey(
            deals=args.deals, player=PLAYERS[args.player],
            fumble=args.fumble):
        worst = min(worst, won / float(args.deals))
        print('%-22s %5d %5d %5d %5.0f%% %5.0f%% %5.0f%% %7.1f %6.1f'
              % ('%d %s' % (level, grade.name), grade.quota, grade.room,
                 grade.warn, 100.0 * won / args.deals,
                 100.0 * caught / args.deals, 100.0 * short / args.deals,
                 beats, got))
    print('\nworst rung: %.0f%%' % (100 * worst))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
