#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A player that already knows which box is the Core.

What it measures is the *route*, not the identity: if this cannot
finish a rung inside its budget then nobody can, and a budget it
barely clears is a budget that is the difficulty rather than the end
of a round.

    PYTHONPATH=.. ../.venv/bin/python oracle_custody.py 300

It is also imported by ``test_custody.py``, so the ladder's promise
that every rung is winnable is checked on every run of the suite
rather than the last time somebody remembered to look.

**A claw cannot chase a box.** Both move one slot a step, so a claw
behind a box stays behind it forever. Interception is standing still
and letting the ring bring it round, which is what this does and what
a person ends up doing too.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from neural_workshop import custody as C            # noqa: E402

#: The ports, in the order the boundary offers them.
LEFT, RIGHT, GRAB, DROP, WAIT = range(5)
NAMES = ('left', 'right', 'grab', 'drop', 'wait')


def toward(claw: int, want: int, slots: int):
    """One step around the ring, the short way. None when already there."""
    if claw == want:
        return None
    forward = (want - claw) % slots
    return RIGHT if forward <= slots - forward else LEFT


def apply(action, boxes, held, claw, layout):
    """Do one action, exactly as the screen and the boundary do it."""
    if action == LEFT:
        claw = (claw - 1) % layout.slots
    elif action == RIGHT:
        claw = (claw + 1) % layout.slots
    elif action == GRAB and held is None:
        held = C.grab(boxes, claw)
    elif action == DROP and held is not None:
        if C.put_down(held, boxes, claw, layout):
            held = None
    if held is not None:
        held.slot = claw
    return held, claw


def choose(boxes, core, held, claw, layout):
    """What a player who knows the Core does next."""
    if held is core:
        target = C.next_target(core, layout, claw)
        step = toward(claw, target, layout.slots)
        if step is not None:
            return step
        if target == layout.bay:
            return DROP
        return DROP if C.box_at(boxes, claw) is None else WAIT
    if held is not None:
        return DROP if C.box_at(boxes, claw) is None else RIGHT
    if C.box_at(boxes, claw) is core:
        # Includes taking it straight back out of a machine it was
        # just put into: a machine holds a box for one belt step.
        return GRAB
    if not layout.moving:
        step = toward(claw, core.slot, layout.slots)
        return step if step is not None else GRAB
    return WAIT             # a claw cannot chase; the ring brings it


def play(level: int, seed: int, trace: bool = False):
    """Run one round. Returns (actions spent, delivered right, layout)."""
    layout = C.generate(level, seed=seed)
    rng = random.Random(seed)
    boxes = C.fresh_boxes(layout, rng)
    core = C.core_of(boxes, layout)
    claw, held = 0, None
    for spent in range(layout.budget):
        if core.delivered:
            return spent, C.wanted(core, layout), layout
        action = choose(boxes, core, held, claw, layout)
        if trace:                       # pragma: no cover - debugging only
            print('%3d claw=%-3d %-6s core@%-3d c=%-3d h=%-3d %s'
                  % (spent, claw, NAMES[action], core.slot, core.charge,
                     core.heat, 'held' if core.held else ''))
        held, claw = apply(action, boxes, held, claw, layout)
        C.step_belt(boxes, layout)
    return layout.budget, False, layout


def survey(rounds: int = 200):
    """Every rung, every seed: what it took and whether it was won."""
    out = []
    for level in range(1, len(C.GRADES) + 1):
        costs, wins = [], 0
        for seed in range(rounds):
            spent, ok, _layout = play(level, seed)
            wins += ok
            if ok:
                costs.append(spent)
        out.append((level, wins, costs))
    return out


def main():                             # pragma: no cover - a tool
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    print('%-2s %-14s %-9s %-20s %-7s %s'
          % ('', 'rung', 'solved', 'actions', 'budget', 'floor'))
    worst = 0.0
    for level, wins, costs in survey(rounds):
        grade = C.GRADES[level - 1]
        if costs:
            worst = max(worst, max(costs) / float(grade.budget))
        print('%-2d %-14s %3d/%-5d %-20s %-7d 1 in %.2f'
              % (level, grade.name, wins, rounds,
                 '%d med, %d worst' % (statistics.median(costs), max(costs))
                 if costs else '-',
                 grade.budget, grade.rivals))
    print('\nthe worst rung spent %.0f%% of its budget' % (100 * worst))


if __name__ == '__main__':
    main()
