# -*- coding: utf-8 -*-
"""Own presses: the right port depends on what the player pressed, and
was paid, on earlier trials, and nothing on screen says what that was.

Every trial shows four plain panels, the same for every answer, in a
layout and colour that change from trial to trial. A blank frame comes
first, presses during it are ignored, and then the question is put.
The verdict says only right or wrong: it never shows which port was
pressed, nor which was right.

``cycle``  the ports go round in a fixed cycle (look 0: 1, 2, 3, 4 and
           back to 1; look 1: 1, 3, 4, 2 and back to 1). At rung k the
           right port is the one after the port pressed k trials ago.
           Where that trial had no press, or there is no such trial
           yet, the right port is drawn at random.
``stay``   one hidden port is right for a block of three to six trials
           and then moves, without notice, to one of the other three.
           At rung k there are k hidden ports taking turns, so the one
           right now is the one that was right k trials ago, unless its
           block has just run out: stay after a payment k trials back,
           shift after a loss.

Chance: whatever a player does without memory of its own presses is
right one time in four, since the screen is the same for every answer
and the right port is drawn evenly. The cheap partial strategies,
which the tests count:

``cycle``  pressing round the cycle, without looking back, is right on
           every trial at rungs 1, 5, 9, ... (where k - 1 is a whole
           number of turns round) and never at the other rungs.
``stay``   pressing one port all run long: one in four. Win-stay,
           lose-shift (to any other port) on the trial just before is
           right about half the time at rung 1, a little more than
           one in four at rung 2 (about 0.29: once the two hidden ports
           happen to be the same it keeps winning until one moves) and
           one in four from rung 3 on; done k trials back, about half the time at
           rung k. Shifting only to ports not yet tried since the last
           payment does better still.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional

from . import framed
from .i18n import _

KINDS = ('cycle', 'stay')
PORTS = 4
#: The port after each port, by look.
CYCLES = {0: (1, 2, 3, 0), 1: (2, 0, 3, 1)}
#: How many of its own turns a hidden port stays right.
BLOCK = (3, 6)
LAYOUTS = {0: ('row', 'square', 'column'), 1: ('diamond', 'arc', 'zigzag')}

QUESTIONS = {
    'cycle': _('Press the next one round'),
    'stay': _('Find the right one'),
}


class Hidden(NamedTuple):
    port: int
    age: int                     # turns it has been right, counting this
    length: int                  # turns it stays right


class Ledger:
    """What has happened so far in a run: the player's presses (None
    for a trial with none) and, for ``stay``, the hidden port of every
    trial."""

    def __init__(self) -> None:
        self.presses: List[Optional[int]] = []
        self.hidden: List[Hidden] = []

    def record(self, pressed: Optional[int]) -> None:
        self.presses.append(pressed)


def next_hidden(ledger: Ledger, k: int, rng: random.Random) -> Hidden:
    """The hidden port for the trial about to be dealt."""
    if len(ledger.hidden) >= k:
        before = ledger.hidden[-k]
        if before.age < before.length:
            return Hidden(before.port, before.age + 1, before.length)
        port = rng.choice([p for p in range(PORTS) if p != before.port])
    else:
        port = rng.randrange(PORTS)
    return Hidden(port, 1, rng.randint(*BLOCK))


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         look: int = 0, ledger: Optional[Ledger] = None) -> framed.Puzzle:
    """The next trial of a run whose history is *ledger*. A ``stay``
    deal adds the trial's hidden port to the ledger; the caller records
    the press once the trial is judged."""
    rng = rng or random.Random()
    ledger = ledger if ledger is not None else Ledger()
    k = max(1, int(rung))
    data = {'look': look, 'hue': rng.randrange(len(framed.HUES_A)),
            'rim': rng.randrange(len(framed.RIMS)),
            'layout': rng.choice(LAYOUTS[look]),
            'place': (rng.random(), rng.random())}
    if kind == 'cycle':
        before = ledger.presses[-k] if len(ledger.presses) >= k else None
        answer = (CYCLES[look][before] if before is not None
                  else rng.randrange(PORTS))
    elif kind == 'stay':
        hidden = next_hidden(ledger, k, rng)
        ledger.hidden.append(hidden)
        answer = hidden.port
    else:
        raise ValueError(kind)
    choices = tuple(str(p + 1) for p in range(PORTS))
    return framed.puzzle(kind, k, (-1, 0), choices, answer, data,
                         QUESTIONS[kind])
