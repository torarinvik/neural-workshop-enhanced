# -*- coding: utf-8 -*-
"""Hidden Wiring: find how switches drive lamps by trying them, then use it.

A panel of switches and a row of lamps, wired through gates nobody shows.
Setting the switches is free; **looking** at the lamps costs a point, and
shows which are lit for the switches as they stand. When the wiring is
known well enough, the exam begins: it shows a pattern of lamps, lit and
dark, and asks for switches that would produce it. Nothing is shown
until the last question, and every wrong setting costs the rung's
penalty. A round's cost is its looks plus its penalties.

It asks what Hidden Rule does not: not a rule about the objects put in
front of it but a *mechanism*, found by intervening on it -- which
switch matters to which lamp, through what gate -- and then used in the
other direction, from the effect wanted back to the cause that makes it.

The ladder: more switches, some of which do nothing; more lamps; gates
of two inputs (AND, OR, with either input inverted), then XOR, then
three inputs (AND, OR, majority, parity); and from rung 16 a lamp that
on some looks shows the wrong state -- fixed by look number, so the
reference meets the same lies.

Each lamp's wiring is one function of the switches, and with at most
eight switches a function is a 256-bit truth table: one Python integer,
bit *c* the lamp's state for switch setting *c*. Ruling a wiring out,
asking whether every wiring still possible agrees, finding a setting that
gives a pattern for certain -- all are a few bitwise operations.

The reference holds every wiring each lamp could still have, looks at
the setting whose result those wirings split on most, and sits the exam
once every question can be answered for certain or its looks run out.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import math
import random
from functools import lru_cache
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

MOST_SWITCHES = 8
MOST_LAMPS = 6
#: The most a lamp lies, as a share of looks.
NOISIEST = 0.12


class Grade(NamedTuple):
    rung: int
    switches: int
    lamps: int
    #: Gate families allowed: 'copy', 'and', 'xor', 'three'.
    gates: Tuple[str, ...]
    #: Whether a two-input gate's inputs may be inverted (a lamp that
    #: follows one switch may show it backwards on any rung).
    inverts: bool
    #: Share of looks on which one lamp shows the wrong state.
    noise: float
    questions: int
    penalty: int
    factor: float
    slack: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    gates: Tuple[str, ...] = ('copy',)
    if r >= 3:
        gates += ('and',)
    if r >= 7:
        gates += ('xor',)
    if r >= 12:
        gates += ('three',)
    return Grade(
        rung=r,
        switches=min(MOST_SWITCHES, 2 + (r + 1) // 3),
        lamps=min(MOST_LAMPS, 1 + (r - 1) // 4),
        gates=gates,
        inverts=r >= 5,
        noise=0.0 if r < 16 else min(NOISIEST, 0.04 + 0.01 * (r - 16)),
        questions=min(5, 2 + r // 6),
        # More than par's allowance: one wrong answer always fails.
        penalty=6 + r,
        factor=(max(1.0, 2.0 - (r - 1) / 11.0) if r <= 20
                else 1.0 / (1.0 + 0.04 * (r - 20))),
        slack=2.0 if r < 12 else 1.0,
    )


# --- the wirings a lamp can have ---------------------------------------------

class Gate(NamedTuple):
    """One lamp's wiring: a gate kind over some switches, some inverted."""
    kind: str
    inputs: Tuple[int, ...]
    inverted: Tuple[bool, ...]


def evaluate(gate: Gate, setting: int) -> bool:
    bits = [bool(setting >> i & 1) != inv
            for i, inv in zip(gate.inputs, gate.inverted)]
    if gate.kind == 'copy':
        return bits[0]
    if gate.kind == 'and':
        return all(bits)
    if gate.kind == 'or':
        return any(bits)
    if gate.kind == 'xor':
        return sum(bits) % 2 == 1
    if gate.kind == 'majority':
        return sum(bits) >= 2
    raise ValueError(gate.kind)


def table(gate: Gate, switches: int) -> int:
    """The gate's truth table: bit *c* set if lit for setting *c*."""
    found = 0
    for setting in range(1 << switches):
        if evaluate(gate, setting):
            found |= 1 << setting
    return found


@lru_cache(maxsize=None)
def space(level: Grade) -> Tuple[Tuple[Gate, int], ...]:
    """Every wiring a lamp may have on this rung, each a distinct truth
    table, as (gate, table) pairs."""
    n = level.switches
    found: Dict[int, Gate] = {}
    full = (1 << (1 << n)) - 1

    def add(gate: Gate) -> None:
        bits = table(gate, n)
        if bits not in (0, full) and bits not in found:
            found[bits] = gate

    for i in range(n):
        # A lamp may show a switch backwards from the first rung; without
        # that, "everything on" would light any lamp and need no looks.
        add(Gate('copy', (i,), (False,)))
        add(Gate('copy', (i,), (True,)))
    flips2 = (list(itertools.product((False, True), repeat=2))
              if level.inverts else [(False, False)])
    for pair in itertools.combinations(range(n), 2):
        if 'and' in level.gates:
            for inv in flips2:
                add(Gate('and', pair, inv))
                add(Gate('or', pair, inv))
        if 'xor' in level.gates:
            add(Gate('xor', pair, (False, False)))
            if level.inverts:
                add(Gate('xor', pair, (False, True)))
    if 'three' in level.gates:
        for triple in itertools.combinations(range(n), 3):
            plain = (False, False, False)
            for kind in ('and', 'or', 'majority', 'xor'):
                add(Gate(kind, triple, plain))
    return tuple((gate, bits) for bits, gate in found.items())


# --- a deal ------------------------------------------------------------------

class Deal(NamedTuple):
    level: Grade
    #: The true wiring of each lamp.
    lamps: Tuple[Gate, ...]
    #: lies[k]: the lamp shown wrong on look k, or -1.
    lies: Tuple[int, ...]
    #: Each question: the lamp pattern wanted, bit l for lamp l.
    exam: Tuple[int, ...]


def _rank(gate: Gate) -> int:
    return len(gate.inputs)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    if rng is None:
        rng = random.Random(seed)
    level = grade(rung)
    wirings = space(level)
    widest = max(_rank(gate) for gate, _bits in wirings)
    lamps: List[Gate] = []
    used = set()
    for _l in range(level.lamps):
        # Mostly the widest gates the rung allows: that is its point.
        rank = widest if rng.random() < 0.7 else rng.randint(1, widest)
        pool = [(g, b) for g, b in wirings
                if _rank(g) == rank and b not in used]
        gate, bits = rng.choice(pool)
        used.add(bits)
        lamps.append(gate)
    most_looks = budget(level)
    lies = tuple(rng.randrange(level.lamps) if rng.random() < level.noise
                 else -1 for _k in range(most_looks))
    tables = [table(g, level.switches) for g in lamps]
    # Questions that knowing nothing cannot answer for certain first:
    # a pattern any wiring would give is no test of the wiring.
    blind = Belief(level)
    settings = list(range(1 << level.switches))
    rng.shuffle(settings)
    hard: List[int] = []
    easy: List[int] = []
    for setting in settings:
        pattern = sum(1 << l for l, bits in enumerate(tables)
                      if bits >> setting & 1)
        if pattern in hard or pattern in easy:
            continue
        (easy if blind.settings_for(pattern) else hard).append(pattern)
    patterns = (hard + easy)[:level.questions]
    return Deal(level, tuple(lamps), lies, tuple(patterns))


def budget(level: Grade) -> int:
    """The most looks a round allows before the exam starts by itself."""
    return 3 * level.lamps + 2 * level.switches + 6


def lamps_for(dealt: Deal, setting: int) -> int:
    """Which lamps the wiring lights for *setting*, as bits."""
    return sum(1 << l for l, gate in enumerate(dealt.lamps)
               if evaluate(gate, setting))


# --- a round -----------------------------------------------------------------

class Round:
    """One round: looks, then the exam."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.level = dealt.level
        #: (setting, lamps shown) for every look.
        self.looks: List[Tuple[int, int]] = []
        self.examining = False
        #: The setting given for each question so far.
        self.answers: List[int] = []

    @property
    def looks_left(self) -> int:
        return budget(self.level) - len(self.looks)

    def look(self, setting: int) -> Optional[int]:
        if self.examining or self.looks_left <= 0:
            return None
        shown = lamps_for(self.deal, setting)
        liar = self.deal.lies[len(self.looks)]
        if liar >= 0:
            shown ^= 1 << liar
        self.looks.append((setting, shown))
        return shown

    def start_exam(self) -> None:
        self.examining = True

    @property
    def question(self) -> Optional[int]:
        if not self.examining or self.over:
            return None
        return self.deal.exam[len(self.answers)]

    def answer(self, setting: int) -> None:
        if self.question is None:
            return
        self.answers.append(setting)

    @property
    def over(self) -> bool:
        return self.examining and len(self.answers) >= len(self.deal.exam)

    @property
    def wrong(self) -> int:
        return sum(1 for want, setting in zip(self.deal.exam, self.answers)
                   if lamps_for(self.deal, setting) != want)

    @property
    def cost(self) -> float:
        return len(self.looks) + self.level.penalty * self.wrong


# --- the reference -----------------------------------------------------------

class Belief:
    """For each lamp, every wiring still possible -- the ones that
    disagree least with what was seen, where a lamp can lie."""

    def __init__(self, level: Grade) -> None:
        self.level = level
        tables = [bits for _gate, bits in space(level)]
        #: Per lamp: {table: times it disagreed with a look}.
        self.misses: List[Dict[int, int]] = [dict.fromkeys(tables, 0)
                                             for _l in range(level.lamps)]
        self.full = (1 << (1 << level.switches)) - 1

    def saw(self, setting: int, shown: int) -> None:
        for lamp, misses in enumerate(self.misses):
            lit = shown >> lamp & 1
            for bits in misses:
                if (bits >> setting & 1) != lit:
                    misses[bits] += 1
        self._alive = {}

    _alive: Dict[int, List[int]] = {}

    def alive(self, lamp: int) -> List[int]:
        if lamp not in self._alive:
            self._alive = dict(self._alive)
            self._alive[lamp] = self._live(lamp)
        return self._alive[lamp]

    def _live(self, lamp: int) -> List[int]:
        misses = self.misses[lamp]
        least = min(misses.values())
        # On an honest lamp only perfect agreement survives; where a lamp
        # lies, a wiring may have been wronged by a lie or two.
        allowed = least if not self.level.noise else least + 1
        if not self.level.noise:
            return [b for b, m in misses.items() if m == least]
        return [b for b, m in misses.items() if m <= allowed]

    def sure(self, lamp: int) -> Tuple[int, int]:
        """Settings at which every live wiring of *lamp* is lit, and
        settings at which every one is dark."""
        on, off = self.full, self.full
        best = min(self.misses[lamp].values())
        for bits, m in self.misses[lamp].items():
            if m == best:
                on &= bits
                off &= ~bits & self.full
        return on, off

    def settings_for(self, pattern: int) -> int:
        """Settings that give *pattern* under every live wiring."""
        found = self.full
        for lamp in range(self.level.lamps):
            on, off = self.sure(lamp)
            found &= on if pattern >> lamp & 1 else off
        return found

    def best_guess(self, pattern: int) -> int:
        """The setting most likely to give *pattern*."""
        certain = self.settings_for(pattern)
        if certain:
            return (certain & -certain).bit_length() - 1
        best, best_score = 0, -1e9
        live = [self.alive(l) for l in range(self.level.lamps)]
        for setting in range(1 << self.level.switches):
            score = 0.0
            for lamp, tables in enumerate(live):
                want = pattern >> lamp & 1
                agree = sum(1 for b in tables if (b >> setting & 1) == want)
                score += math.log((agree + 0.01) / (len(tables) + 0.02))
            if score > best_score:
                best, best_score = setting, score
        return best

    def split(self, setting: int) -> float:
        """How much a look at *setting* would tell, in bits."""
        gain = 0.0
        for lamp in range(self.level.lamps):
            tables = self.alive(lamp)
            if len(tables) < 2:
                continue
            lit = sum(1 for b in tables if b >> setting & 1)
            p = lit / len(tables)
            if 0 < p < 1:
                gain -= p * math.log2(p) + (1 - p) * math.log2(1 - p)
        return gain


def ready(belief: Belief, exam: Sequence[int]) -> bool:
    return all(belief.settings_for(pattern) for pattern in exam)


def reference_look(belief: Belief, exam: Sequence[int],
                   looks_left: int) -> Optional[int]:
    """The setting to look at next, or None to sit the exam."""
    if looks_left <= 0 or ready(belief, exam):
        return None
    settings = range(1 << belief.level.switches)
    gains = [(belief.split(s), -s) for s in settings]
    gain, setting = max(gains)
    if gain <= 0:
        return None
    return -setting


def reference_round(dealt: Deal) -> Round:
    play = Round(dealt)
    belief = Belief(dealt.level)
    while True:
        setting = reference_look(belief, dealt.exam, play.looks_left)
        if setting is None:
            break
        belief.saw(setting, play.look(setting))
    play.start_exam()
    while not play.over:
        play.answer(belief.best_guess(play.question))
    return play


def par(dealt: Deal) -> float:
    level = dealt.level
    return reference_round(dealt).cost * level.factor + level.slack


__all__ = ['Belief', 'Deal', 'Gate', 'Grade', 'MOST_LAMPS',
           'MOST_SWITCHES', 'NOISIEST', 'Round', 'budget', 'deal',
           'evaluate', 'grade', 'lamps_for', 'par', 'ready',
           'reference_look', 'reference_round', 'space', 'table']
