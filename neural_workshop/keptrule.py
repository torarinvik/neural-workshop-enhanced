# -*- coding: utf-8 -*-
"""A rule that holds across trials: a sign at the start of a block says
which of two rules holds, and is not shown again.

``rule``  at the start of a block of k trials a sign shows for a frame:
          *same*, press where the square is, or *opposite*, press the
          place across from it. Every trial of the block then shows one
          of four places filled, with the question; each is judged. The
          sign shows on the first trial of the block only, and nothing
          on screen says how far into the block a trial is.

Rung k is k trials a block: at rung 1 the sign shows on every trial, a
frame before the question. A block keeps the length it began with when
the rung changes inside it. The rule of each block is drawn evenly and
apart from the last. Any press before the question is put ends the
trial unpaid (see :mod:`keptcue`). Across from a place is the place
three less its number in look 0 (the end of the row or column, or the
other corner of the square), and the place halfway round the ring in
look 1.

From the question frame alone a player cannot tell the rule: pressing
by one rule all run long earns one half, as does the best player that
sees the question frame; pressing at random earns one in four. The
tests count them.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Optional

from . import framed, keptcue
from .i18n import _
from .keptcue import PLACES, Run, act  # noqa: F401

KINDS = ('rule',)
RULES = ('same', 'opposite')
QUESTION = _('Press by the rule of the block')


class Ledger:
    """The block a run is in: its rule and the trials it has left."""

    def __init__(self) -> None:
        self.rule: Optional[str] = None
        self.left = 0
        self.into = 0


def across(look: int, place: int) -> int:
    return PLACES - 1 - place if look == 0 else (place + 2) % PLACES


def deal(kind: str, rung: int, rng: Optional[random.Random] = None,
         look: int = 0, ledger: Optional[Ledger] = None) -> framed.Puzzle:
    """The next trial of a run whose block is *ledger*."""
    rng = rng or random.Random()
    if kind not in KINDS:
        raise ValueError(kind)
    k = max(1, int(rung))
    ledger = ledger if ledger is not None else Ledger()
    sign = None
    if ledger.left <= 0:
        ledger.rule = rng.choice(RULES)
        ledger.left, ledger.into = k, 0
        sign = ledger.rule
    rule, into = ledger.rule, ledger.into
    ledger.left -= 1
    ledger.into += 1
    place = rng.randrange(PLACES)
    answer = place if rule == 'same' else across(look, place)
    return keptcue.make(kind, k, rng, look, ((1, place, 0),), 2, answer,
                        QUESTION, sign=sign, rule=rule, into=into)
