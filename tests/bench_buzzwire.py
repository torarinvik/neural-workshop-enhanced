#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fly every rung of the Buzz Wire ladder and print what got through.

The ladder claims to run from a hoop a child could carry to a wire
nobody could hold, and a claim like that is worth nothing until someone
has measured it. This flies each rung with :func:`pilot_port`, the
reference controller — one port a tick, through the same eleven ports a
learner has, but reading the true state — and reports how many wires it
finished, how many buzzes it collected and how long it took.

The pilot is a yardstick rather than a ceiling: it is a fixed-gain
PD controller with a fixed look-ahead, so it is beatable, and the top
rungs are meant to beat *it*. What the sweep is for is the shape:
finishing everything at the bottom, degrading smoothly, and nothing
about the middle depending on a number nobody looked at.

    cd tests && PYTHONPATH=.. ../.venv/bin/python bench_buzzwire.py

Needs no window: :mod:`neural_workshop.buzzwire` is geometry and
physics and imports no pyglet.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neural_workshop import buzzwire as B    # noqa: E402

#: Ticks a second, the rate the boundary drives at by default.
HZ = 60.0

#: Wires per rung. Enough to separate the rungs, few enough to run in a
#: coffee break.
WIRES = 12


class Flight(object):
    """What one flown wire came to."""

    def __init__(self, home, touches, seconds, worst, travelled):
        self.home, self.touches, self.seconds = home, touches, seconds
        #: The 95th percentile of how much of the clearance was used up,
        #: which is the number that says whether a rung is merely hard
        #: or is off the end of what any controller could hold. A rung
        #: the pilot flies at 0.5 has room in it; one it flies at 0.98
        #: is passing by luck and will not keep passing.
        self.worst, self.travelled = worst, travelled


def fly(rung, seed, hz=HZ, budget=None, forgiving=False):
    """One wire, flown by the pilot.

    *forgiving* ignores the rung's touch allowance and flies to the end
    regardless, which is how the buzz *rate* is measured: a rung that
    ends on the first graze tells you when it grazed and nothing about
    how often it would have.
    """
    grade = B.grade_of(rung)
    wire = B.deal(rung, seed=seed)
    hand = B.Hand(wire, grade, rng=random.Random(seed ^ 0x5eed))
    room = max(1e-9, B.clearance(grade))
    dt = 1.0 / hz
    ticks = int((budget or grade.seconds) * hz)
    used = []
    for tick in range(ticks):
        port = B.pilot_port(hand)
        name = B.PORTS[port]
        push = B.push_vector(grade, name) if name in B.PUSHES else None
        twist = {'tilt up': (1.0, 0.0), 'tilt down': (-1.0, 0.0),
                 'tilt left': (0.0, 1.0), 'tilt right': (0.0, -1.0)
                 }.get(name, (0.0, 0.0))
        step = hand.advance(dt, push=push, twist=twist, grip=(name == B.GRIP))
        used.append(min(2.0, hand.offset() / room))
        if not forgiving and hand.touches > grade.touches:
            break
        if step.home:
            break
    used.sort()
    return Flight(home=hand.home, touches=hand.touches, seconds=tick / hz,
                  worst=used[int(0.95 * (len(used) - 1))] if used else 0.0,
                  travelled=max(1e-6, hand.arc))


def tightest(wire):
    """Smallest radius of curvature on the wire, in cm.

    Worth watching while the top of the ladder is being sharpened: a
    bend tighter than the loop is one the loop cannot be threaded round
    at all, however well it is flown, and the wire would be impossible
    rather than hard.
    """
    worst = float('inf')
    for one, two in zip(wire.tangents, wire.tangents[2:]):
        turn = math.acos(max(-1.0, min(1.0, B.dot(one, two))))
        if turn > 1e-6:
            worst = min(worst, 2.0 * wire.spacing() / turn)
    return worst


def turn_rate(wire, grade):
    """Fastest the tangent swings, in rad/s, at this rung's own pace.

    What the wrist has to keep up with. Above rung six the loop is
    aimed by hand, so this against ``top_twist`` is the whole question
    of whether a rung can be flown at all.
    """
    pace = B.hand_speed(grade) * 0.72
    worst = 0.0
    for one, two in zip(wire.tangents, wire.tangents[4:]):
        turn = math.acos(max(-1.0, min(1.0, B.dot(one, two))))
        worst = max(worst, turn / (4.0 * wire.spacing()) * pace)
    return worst


def main():
    print('%-3s %-22s %5s %5s %5s %5s %5s %5s %5s %5s %6s %6s %5s'
          % ('#', 'rung', 'clear', 'tick', 'grip', 'len', 'bend', 'turn',
             'wrist', 'p95', 'buzz/m', 'flown', 'secs'))
    for rung in range(1, len(B.GRADES) + 1):
        grade = B.GRADES[rung - 1]
        done = 0
        spent = swings = worst = buzz_rate = 0.0
        span = 0.0
        bend = float('inf')
        for seed in range(WIRES):
            wire = B.deal(rung, seed=seed)
            span = wire.length
            bend = min(bend, tightest(wire))
            swings += turn_rate(wire, grade)
            scored = fly(rung, seed)
            done += int(scored.home)
            spent += scored.seconds
            loose = fly(rung, seed, forgiving=True)
            worst += loose.worst
            buzz_rate += 100.0 * loose.touches / loose.travelled
        wrist = grade.top_twist or float('nan')
        # `grip` is the tremor against what one tick of thrust can take
        # back over the tremor's own correlation time. Under about four
        # the hand is moving faster than the arm can answer it.
        grip = (grade.thrust * grade.tremor_tau
                / B.tremor_wander(grade)) if grade.tremor else float('inf')
        print('%-3d %-22s %5.2f %5.1f %5.1f %5.1f %5.2f %5.2f %5.2f %5.2f '
              '%6.2f %4d/%-2d %5.1f'
              % (rung, grade.name, B.clearance(grade),
                 B.ticks_per_clearance(grade), grip, span, bend,
                 swings / WIRES, wrist, worst / WIRES, buzz_rate / WIRES,
                 done, WIRES, spent / WIRES))


def panel(steps=420, rung=1, seconds=3.0):
    """The four axes ADDING_A_TASK.md asks a new task to be read on.

    It names a ``task_panel`` module for this and there is not one in
    this tree, so the measurements are made here instead, through the
    boundary and off the frames rather than off the task.

    *Changed* is the share of steps whose frame differs from the one
    before, and it is reported twice: once for a run that acts and once
    for a run that presses nothing. The difference is the number that
    matters. This task animates whether or not anybody acts — the hand
    sags, the tremor drifts, the clock runs — so the raw change rate
    would flatter it, which is the trap Out of Sight fell into.

    *Recoverable* is whether the port pressed can be told from
    consecutive frames: eleven ports are pressed from one identical
    state and the resulting frames counted for distinctness.

    *Paid* and *costly* are the reward's density and whether it ever
    goes negative, and *verified* re-derives every outcome from its
    archived frame through the generated verifier, which is the whole
    of the public-outcome contract.
    """
    import os
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault('NW_HEADLESS', '1')
    from nwenv import catalog
    from nwenv.buzzwire import verify_buzzwire_outcome

    def played(acting):
        env = catalog.env_class('buzz_wire')(
            seed=0, rung=rung, trials=6, seconds=seconds)
        rng = random.Random(1)
        frames, changed, scalars, checked, good = [], 0, [], 0, 0
        try:
            for _step in range(steps):
                port = rng.randrange(env.n_actions) if acting else None
                obs, events, done = env.step(port)
                if frames and obs['rgba'] != frames[-1]:
                    changed += 1
                frames.append(obs['rgba'])
                for event in events:
                    if event.get('type') != 'outcome':
                        continue
                    scalars.append(event['scalar'])
                    checked += 1
                    good += bool(verify_buzzwire_outcome(
                        event, obs['rgba'], obs['width'], obs['height'],
                        env._archive, env._receipt_ledger))
                if done:
                    break
        finally:
            env.close()
        return changed / float(max(1, len(frames) - 1)), scalars, checked, good

    acting, scalars, checked, good = played(True)
    idle, _idle_scalars, _c, _g = played(False)

    # Recoverability: one state, eleven ports, eleven frames.
    env = catalog.env_class('buzz_wire')(seed=0, rung=rung, trials=2)
    seen = set()
    try:
        for _settle in range(30):
            env.step(None)
        held = (env.task.hand.centre, env.task.hand.velocity,
                env.task.hand.yaw, env.task.hand.pitch)
        for port in range(env.n_actions):
            (env.task.hand.centre, env.task.hand.velocity,
             env.task.hand.yaw, env.task.hand.pitch) = held
            obs, _events, _done = env.step(port)
            seen.add(obs['rgba'])
    finally:
        env.close()

    print('changed while acting   %5.1f%%' % (100.0 * acting))
    print('changed while idle     %5.1f%%   (the agent-caused share is the '
          'difference)' % (100.0 * idle))
    print('recoverable ports      %d of %d frames distinct'
          % (len(seen), len(B.PORTS)))
    print('paid                   %d outcomes in %d steps (%.1f%%)'
          % (len(scalars), steps, 100.0 * len(scalars) / steps))
    print('costly                 %d of them negative'
          % sum(1 for value in scalars if value < 0))
    print('verified               %d of %d re-derive from their own frame'
          % (good, checked))


if __name__ == '__main__':
    if '--panel' in sys.argv:
        panel()
    else:
        main()
