# -*- coding: utf-8 -*-
"""The Cipher Abyss: find out what the machine does.

A machine takes a row of coloured symbols and gives back another row.
What it does to them is hidden. Build an input from the palette, run
it, and read what comes out; the experiments are limited. When you are
ready (or the experiments are spent) the machine is tested: it shows
inputs it has not shown before, and you must give the output it would
give, every one right.

The machines are programs in a small language (``cipherlang``) that
grows up the ladder, and what was learned below stays useful above.
Every stage starts gently and grows inside itself (a longer row, one
more kind of piece, one experiment fewer):

* rungs 1-3, patterns: two colours; positions moved about (reverse,
  rotate, swap neighbours, reverse each half, weave), the colours
  swapped, or both;
* rungs 4-6, transformations: three symbols counted mod 3: shifts,
  multiplying, substitutions, running sums, differences, sorting,
  counting runs, odd places shifted, each added to its mirror;
* rungs 7-9, conditions: one transformation or another, picked by a
  hidden test of the input;
* rungs 10-12, composition: two transformations chained;
* rungs 13-15, state: what the machine does depends on how many times
  it has run, or on what it was given last time;
* rungs 16-18, hidden language: some symbols are instructions with
  hidden meanings, the rest are data, and each instruction in the input
  is applied in turn to the data (so the answer can be shorter);
* rungs 19-21, arithmetic and cryptography: affine maps and weighted
  sums mod k, xor and multiplication in GF(4) and GF(8), a Feistel
  round, after a reshuffle of positions;
* rungs 22-24, rules that modify rules: the machine works through a
  list of rules, moving on to the next after every input that passes a
  hidden test;
* rungs 25-27, nested systems: the test that picks the rule may look
  at the machine's own last answer or its run count, and the branches
  are chains;
* rungs 28-39, adversarial: a hidden exception that only a row of one
  symbol sets off (the test will ask about it); rules that drop
  repeats, double up or halve the row; six symbols, longer rows, fewer
  experiments;
* from rung 40, open-ended: programs grown at random from the whole
  language, deeper every few rungs.

Each machine dealt is one a careful experimenter can pin down. The
reference player keeps every rule of the rung's language that is still
consistent with what it has seen and runs whichever input splits them
most evenly. A machine is only dealt when, after the reference
player's experiments, every rule still standing gives the same answer
to every test question; when no simpler rule than the real one still
fits; and when each question is one that rules which fitted a little
earlier get wrong.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import functools
import itertools
import math
import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from . import cipherlang as L
from . import hand as H
from .cipherlang import (Alt, Except, If, Meta, Prim, Prog, Seq, State, Test,
                         one)
from .i18n import _

SYMBOLS = 8
SYM = H.KEYS                   # ports 14-21: the eight symbols
DELETE = H.KEYS + SYMBOLS      # 22
RUN = DELETE + 1               # 23: run the input, or give the answer
TEST = DELETE + 2              # 24: ready for the test
NEXT_BLOCK = DELETE + 3        # 25: the hypothesis board's menu, down
PREV_BLOCK = DELETE + 4        # 26: and up
ADD_BLOCK = DELETE + 5         # 27: put the highlighted block on the board
UNDO_BLOCK = DELETE + 6        # 28: take the last block off
CHECK = DELETE + 7             # 29: run the hypothesis over the notebook
SUBMIT = DELETE + 8            # 30: give the hypothesis as the answer
PREDICT = DELETE + 9           # 31: predict before each run, on or off
SCROLL_UP = DELETE + 10        # 32: the notebook, back
SCROLL_DOWN = DELETE + 11      # 33: and forward
MARK = DELETE + 12             # 34: star the newest row
NUMBERS = DELETE + 13          # 35: numbers on the symbols, on or off
SORT = DELETE + 14             # 36: the notebook in time or input order
PORTS = DELETE + 15
EVENTS = tuple(range(PORTS))
CHIME, TONE, BUZZ, DONE, MISS, TICK, HUM = range(7)
PATCHES = ('bell', 'chirp', 'growl', 'bell', 'growl', 'wood', 'growl')
PITCH = (262.0, 294.0, 330.0, 392.0, 440.0, 523.0, 587.0, 659.0)

# Where things are on the 1000 by 640 screen (y up).
PAL_Y = 62.0
BUTTON_W = 84.0
DEL_X, RUN_X, TEST_X = 680.0, 780.0, 880.0
ROW_Y = 150.0                  # the row being built
BOARD = (20.0, 190.0, 500.0, 440.0)       # left, bottom, right, top
MENU_X, MENU_TOP, MENU_ROW, MENU_ROWS = 30.0, 404.0, 22.0, 9
BOARD_BUTTONS = {'undo': (270.0, 212.0), 'check': (350.0, 212.0),
                 'submit': (440.0, 212.0)}
BOARD_BUTTON_W = 74.0
PREDICT_AT = (430.0, ROW_Y)
NOTE = (515.0, 100.0, 990.0, 630.0)       # the notebook
NOTE_TOP, NOTE_ROW, NOTE_ROWS = 572.0, 38.0, 12


def pal_x(i: int) -> float:
    return 52.0 + 70.0 * i


def slot_x(i: int, n: int) -> float:
    gap = min(52.0, 380.0 / max(1, n))
    return 40.0 + gap * (i + 0.5)


def menu_y(i: int) -> float:
    return MENU_TOP - MENU_ROW * i


def note_y(i: int) -> float:
    return NOTE_TOP - NOTE_ROW * i


Row = Tuple[int, ...]

STAGES = ((1, 'patterns'), (4, 'transformations'), (7, 'conditions'),
          (10, 'composition'), (13, 'state'), (16, 'hidden language'),
          (19, 'cryptography'), (22, 'rules that change rules'),
          (25, 'nested'), (28, 'adversarial'), (40, 'open-ended'))


class Grade(NamedTuple):
    rung: int
    stage: int                 # 1 patterns ... 11 open-ended
    step: int                  # rungs into the stage, from 0
    k: int                     # symbols
    length: int
    budget: int                # experiments
    tests: int
    seconds: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    stage = max(i + 1 for i, (start, _n) in enumerate(STAGES)
                if r >= start)
    step = r - STAGES[stage - 1][0]
    k = (2, 3, 3, 4, 4, 5, 4, 4, 5, 6, 6)[stage - 1]
    if stage == 7 and step == 2:
        k = 8                                  # GF(8)
    length = (4, 5, 5, 6, 6, 7, 6, 6, 6, 6, 7)[stage - 1]
    if stage == 1 and step == 0:
        length = 3                             # the gentlest start
    if stage == 2:
        length = 4 + min(step, 1)
    if stage == 10:
        length += min(2, step // 4)
    budget = (8, 8, 9, 9, 9, 9, 9, 9, 10, 10, 10)[stage - 1]
    budget -= min(2, step // 2) if stage < 10 else min(4, step // 3)
    tests = (3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4)[stage - 1]
    if stage == 1 and step < 2:
        budget, tests = 8, 2
    if stage == 11:
        # The open top never stops getting harder. What the screen can
        # hold saturates (eight symbols, rows of twelve, four experiments,
        # six questions); the machines themselves (see _open) grow for
        # ever.
        k = min(SYMBOLS, 6 + step // 20)
        length = min(12, 7 + step // 8)
        budget = max(4, 10 - step // 6)
        tests = min(6, 4 + step // 30)
    return Grade(r, stage, step, k, length, max(4, budget), tests,
                 min(1200.0, 300.0 + 30.0 * r))


def gentle(level: Grade) -> bool:
    """The first two rungs: one plain step, nothing hidden behind it, and
    a single good experiment may well be enough."""
    return level.stage == 1 and level.step < 2


def stage_name(level: Grade) -> str:
    return STAGES[level.stage - 1][1]


# --- the families ------------------------------------------------------

POSITION = ('rev', 'swap', 'mirror', 'weave', 'unweave')


def places(n: int) -> List[Prim]:
    """Named moves of positions."""
    return [Prim(op) for op in POSITION] + \
        [Prim('rot', (m,)) for m in range(1, n)]


#: The held-out family: reading every s-th place. No machine below this
#: rung uses it, and no look-alike either, so it tests transfer.
HELD_OUT_FROM = 30


def strides(n: int) -> List[Prim]:
    return [Prim('stride', (s,)) for s in range(2, n)
            if math.gcd(s, n) == 1]


def values(k: int, step: int = 9) -> List[Prim]:
    """Named changes of symbols."""
    out = [Prim('shift', (c,)) for c in range(1, k)]
    out += [Prim('mul', (a,)) for a in range(2, k) if math.gcd(a, k) == 1]
    if step >= 1 or k > 3:
        out += [Prim('prefix'), Prim('diff'), Prim('sort'), Prim('runs')]
    if step >= 2 or k > 3:
        out += [Prim('oddshift', (c,)) for c in range(1, k)] + \
            [Prim('fold')]
    return out


def tables(n: int, k: int) -> List[Prim]:
    """The unnamed pieces: any shuffle of positions, any substitution."""
    out = [Prim('perm', (p,)) for p in itertools.permutations(range(n))
           if list(p) != list(range(n))]
    if k <= 3:
        out += [Prim('sub', (p,)) for p in itertools.permutations(range(k))
                if list(p) != list(range(k))]
    return out


def tests(k: int, state: bool = False) -> List[Test]:
    out = [Test(op, (s,)) for op in ('first', 'last', 'has')
           for s in range(k)]
    out += [Test('evens', (0,)), Test('sumeven'), Test('rises')]
    if state:
        out += [Test('tparity')] + [Test('echo', (s,)) for s in range(k)]
    return out


def _seq(*ps) -> Seq:
    return Seq(tuple(ps))


def _raw(level: Grade):
    """Every program of the rung, and which of them may be the machine:
    the rest are there to be ruled out."""
    k, n, s, j = level.k, level.length, level.stage, level.step
    if s == 1:
        flips = [None, Prim('shift', (1,)), Prim('oddshift', (1,))]
        moves = [Prim('perm', (p,)) for p in itertools.permutations(range(n))]
        hyp = [_seq(m) if f is None else _seq(m, f)
               for m in moves for f in flips]
        if j == 0:                             # one of five plain things
            easy = [Prim('rev'), Prim('rot', (1,)), Prim('rot', (2,)),
                    Prim('swap'), Prim('shift', (1,))]
            return hyp + [_seq(p) for p in easy], [_seq(p) for p in easy]
        named = places(n) + [Prim('sort')]
        if j == 1:                             # one named move or one flip
            single = [_seq(p) for p in named + flips[1:]]
            return hyp + single, single
        truths = [_seq(m) if f is None else _seq(m, f)
                  for m in named for f in flips] + \
            [_seq(f) for f in flips[1:]]
        return hyp + truths, truths
    if s == 2:
        singles = places(n) + values(k)
        singles += [Prim('affine', (a, b)) for a in range(2, k)
                    for b in range(1, k) if math.gcd(a, k) == 1]
        hyp = [_seq(p) for p in singles + tables(n, k)]
        return hyp, [_seq(p) for p in singles]
    if s == 3:
        b = places(n) + values(k, j)[:k + 1]
        rules = [If(t, _seq(f), _seq(g)) for t in tests(k)
                 for f in b for g in b if f != g]
        return rules, rules
    if s == 4:
        w = places(n) + values(k, j)
        rules = [_seq(f, g) for f in w for g in w if f != g]
        return rules, rules
    if s == 5:
        w, b = places(n) + values(k), places(n)
        rules = [_seq(f, Prim('tshift', (c,))) for f in w
                 for c in range(1, k)]
        rules += [Alt(_seq(f), _seq(g)) for f in b + values(k)[:3]
                  for g in b + values(k)[:3] if f != g]
        rules += [_seq(f, Prim('mem')) for f in w]
        if j >= 1:
            rules += [If(Test('tparity'), _seq(f), _seq(g))
                      for f in w for g in w if f != g]
        return rules, rules
    if s == 6:
        means = [Prim('rev'), Prim('swap'), Prim('rot', (1,)),
                 Prim('shift', (1,)), Prim('mirror'), Prim('sort'),
                 Prim('diff'), Prim('mul', (2,))]
        count = 2 if j < 2 else 3
        rules = []
        for ops in itertools.combinations(range(k), count):
            for meaning in itertools.product(means, repeat=count):
                if len(set(meaning)) < count:
                    continue
                rules.append(Prog(tuple(zip(ops, meaning))))
        return rules, rules
    if s == 7:
        pre = [None, Prim('rev'), Prim('weave')] + \
            [Prim('rot', (m,)) for m in (1, 2)]
        if k == 8:
            core = [Prim('gf', (a,)) for a in range(2, 8)] + \
                [Prim('xor', (c,)) for c in range(1, 8)]
        elif j == 0:
            core = [Prim('affine', (a, b)) for a in (1, 3) for b in range(k)
                    if (a, b) != (1, 0)] + \
                [Prim('conv', (a, b, c)) for a in (1, 3) for b in (1, 2, 3)
                 for c in range(k)]
        else:
            core = [Prim('gf', (a,)) for a in (2, 3)] + \
                [Prim('xor', (c,)) for c in range(1, k)] + \
                [Prim('feistel', (_seq(f),)) for f in
                 [Prim('rev'), Prim('rot', (1,)), Prim('shift', (1,)),
                  Prim('mul', (3,)), Prim('xor', (1,)), Prim('prefix')]]
        rules = [_seq(c) if p is None else _seq(p, c)
                 for p in pre for c in core]
        return rules, rules
    if s == 8:
        b = places(n)[:5] + [Prim('shift', (1,)), Prim('rot', (1,)),
                             Prim('mul', (3,))]
        trig = tests(k)[:2 * k] + [Test('sumeven')]
        if j == 0:
            rules = [Meta((_seq(f), _seq(g)), t) for t in trig
                     for f in b for g in b if f != g]
        else:
            rules = [Meta((_seq(f), _seq(g), _seq(h)), t) for t in trig
                     for f, g, h in itertools.permutations(b, 3)]
        return rules, rules
    if s == 9:
        w = places(n) + values(k)[:k + 1]
        pairs = [_seq(f, g) for f in w[:8] for g in w[8:]]
        branches = [_seq(f) for f in w] + (pairs if j >= 1 else [])
        ts = tests(k, state=True)
        draw = random.Random(level.rung)
        rules = [If(t, f, g) for t in ts for f in branches for g in branches
                 if f != g]
        draw.shuffle(rules)
        return rules[:9000], rules[:9000]
    if s == 10:
        w = places(n) + values(k)[:6]
        if j >= 2:
            w += [Prim('dedupe'), Prim('double'), Prim('halve')]
        if level.rung >= HELD_OUT_FROM:
            w += strides(n)
        draw = random.Random(level.rung)
        rules = [Except(_seq(f, g), _seq(h)) for f in w for g in w
                 for h in w if f != g]
        draw.shuffle(rules)
        return rules[:9000], rules[:9000]
    return _open(level)


def _open(level: Grade):
    """From rung 40: random programs from the whole language, and no
    ceiling. Chains lengthen with the square root of the climb and
    branches nest with its logarithm, so the machines grow for ever, and
    a deal still gets done."""
    k, n, j = level.k, level.length, level.step
    draw = random.Random(level.rung * 7 + 1)
    w = places(n) + values(k) + [Prim('dedupe'), Prim('halve')] + \
        strides(n)
    depth = 2 + int(math.sqrt(j / 3.0))
    nest = 1 + int(math.log2(1.0 + j / 10.0))
    ts = tests(k, state=True)

    def chain():
        return _seq(*[draw.choice(w) for _d in range(draw.randint(1, depth))])

    def grow(level_):
        kind = draw.random()
        if level_ <= 0 or kind < 0.4:
            return chain()
        if kind < 0.7:
            return If(draw.choice(ts), grow(level_ - 1), grow(level_ - 1))
        if kind < 0.85:
            return Except(grow(level_ - 1), chain())
        return Meta((grow(level_ - 1), chain()), draw.choice(ts[:k]))

    # Bigger machines cost more to run, so there are fewer of them to
    # tell apart: the work of a deal stays within reach at any rung.
    count = max(500, int(4000 / (1.0 + j / 20.0)))
    rules = set()
    while len(rules) < count:
        rules.add(grow(nest))
    rules = sorted(rules, key=L.code)
    return rules, rules


@functools.lru_cache(maxsize=64)
def _order(level: Grade) -> Dict:
    return {r: i for i, r in enumerate(family(level))}


@functools.lru_cache(maxsize=64)
def _one_look(level: Grade):
    """For each rule the machine may be: the rules a player would settle
    on after one random experiment by taking the simplest that fits, or
    nothing when for some experiment that would be the real rule (one
    look must never be enough). Worked out once a rung over a fixed set
    of random inputs."""
    if gentle(level):                        # there one look may be enough
        return {t: frozenset() for t in truths(level)}
    fam = family(level)
    k = level.k
    draw = random.Random(level.rung * 31 + 7)
    looks = [tuple(draw.randrange(k) for _i in range(level.length))
             for _t in range(80)]
    firsts = []
    for x in looks:
        first: Dict[Row, object] = {}
        for r in fam:                         # in order: simplest first
            first.setdefault(L.run(r, x, k, L.START), r)
        firsts.append(first)
    out = {}
    for t in truths(level):
        rivals = set()
        for x, first in zip(looks, firsts):
            r = first[L.run(t, x, k, L.START)]
            if r == t:
                break
            rivals.add(r)
        else:
            out[t] = frozenset(rivals)
    return out


def _background(level: Grade) -> List:
    """What was learned below, at this rung's symbols and length: every
    single piece, and from the state stage on every pair of named
    pieces. These are the simpler look-alikes a machine must be told
    apart from."""
    k, n, s = level.k, level.length, level.stage
    if s < 3:
        return []
    singles = places(n) + values(k)
    out = [_seq(p) for p in singles]
    if s >= 5:
        named = places(n) + values(k)[:k + 2]
        out += [_seq(f, g) for f in named for g in named if f != g]
    return out


#: Stages whose machines carry a quirk: on a rare kind of row they do
#: something else, so one look never tells the whole story.
QUIRKS = {1: ('same',), 2: ('same', 'sorted'), 4: ('pal', 'sorted'),
          6: ('sorted',), 7: ('pal', 'sorted', 'same')}


def _quirked(level: Grade, plain: Sequence) -> List:
    k, n = level.k, level.length
    odd = [Prim('shift', (c,)) for c in range(1, k)] + \
        [Prim('rev'), Prim('sort')] + \
        ([Prim('mul', (k - 1,))] if k > 2 else [])
    if level.stage == 6:
        odd = odd[:2]
    out = []
    for t in QUIRKS[level.stage]:
        for base in plain:
            for q in odd:
                out.append(If(Test(t), _seq(q), base))
    return out


@functools.lru_cache(maxsize=64)
def _families(level: Grade):
    hyp, truths = _raw(level)
    hyp = list(hyp) + _background(level)
    if level.stage in QUIRKS and not gentle(level):
        quirky = _quirked(level, truths)
        hyp += quirky
        truths = quirky
    k, n = level.k, level.length
    fam = L.dedupe(hyp + list(truths), n, k)
    names = {L.code(L.canon(t, n, k)) for t in truths}
    fam.sort(key=lambda r: (L.size(r), L.code(r)))
    sure = [r for r in fam if L.code(r) in names]
    return tuple(fam), tuple(sure)


def family(level: Grade) -> Tuple:
    """Every rule of the rung's language, one per behaviour."""
    return _families(level)[0]


def truths(level: Grade) -> Tuple:
    """The rules the machine itself may be."""
    return _families(level)[1]


def describe(rule) -> str:
    return L.say(rule)


def apply(rule, x: Row, k: int, st: State = L.START) -> Row:
    return L.run(rule, x, k, st)


# --- the reference player's mind ---------------------------------------

class Mind:
    """Every rule of the rung still consistent with what has been seen,
    each with its own state, and how to choose the next experiment."""

    def __init__(self, level: Grade, seed: int) -> None:
        self.level = level
        self.alive: Dict = {r: L.START for r in family(level)}
        self.draw = random.Random(seed)
        self.seen = 0
        self.history: List[int] = [len(self.alive)]
        self.snapshots: List[Tuple] = [tuple(self.alive)]
        self.answered = 0
        self.split = 0
        self.queue: List[int] = []
        self.testing: Optional[Dict] = None   # each rule's state in the test
        self.tested = 0

    def begin_test(self) -> None:
        self.testing = {r: L.START for r in self.alive}

    def tested_on(self, given: Row, truth: Row) -> None:
        """The machine's answer to a test question: rules that would
        have said otherwise go, the rest move on."""
        k = self.level.k
        keep = {}
        for r, st in self.testing.items():
            out = L.run(r, given, k, st)
            if out == truth:
                keep[r] = L.advance(r, st, given, out, k)
        self.testing = keep
        self.tested += 1

    def update(self, log: Sequence[Tuple[Row, Row]]) -> None:
        k = self.level.k
        while self.seen < len(log):
            x, y = log[self.seen]
            keep = {}
            for rule, st in self.alive.items():
                out = L.run(rule, x, k, st)
                if out == y:
                    keep[rule] = L.advance(rule, st, x, out, k)
            self.alive = keep
            self.seen += 1
            self.history.append(len(keep))
            self.snapshots.append(tuple(keep))

    def predict(self, rule, x: Row) -> Row:
        return L.run(rule, x, self.level.k, self.alive[rule])

    def candidates(self) -> List[Row]:
        lv = self.level
        out = [tuple(self.draw.randrange(lv.k) for _i in range(lv.length))
               for _c in range(36)]
        out += [(v,) * lv.length for v in range(lv.k)]
        out.append(tuple(i % lv.k for i in range(lv.length)))
        out.append(tuple([1] + [0] * (lv.length - 1)))
        out.append(tuple(sorted(self.draw.randrange(lv.k)
                                for _i in range(lv.length))))
        half = [self.draw.randrange(lv.k) for _i in range(lv.length // 2)]
        mid = [self.draw.randrange(lv.k)] if lv.length % 2 else []
        out.append(tuple(half + mid + half[::-1]))
        out.append(tuple(range(lv.length - 1, -1, -1)) if lv.k >= lv.length
                   else tuple((lv.length - 1 - i) % lv.k
                              for i in range(lv.length)))
        return out

    def experiment(self) -> Optional[Row]:
        rules = list(self.alive.items())
        sample = rules if len(rules) <= SAMPLE else \
            self.draw.sample(rules, SAMPLE)
        if len(sample) <= 1:
            return None
        k = self.level.k
        best, worst = None, len(sample) + 1
        run = L.run
        for x in self.candidates():
            buckets: Dict[Row, int] = {}
            big = 0
            for rule, st in sample:
                y = run(rule, x, k, st)
                c = buckets.get(y, 0) + 1
                buckets[y] = c
                if c > big:
                    big = c
                    if big >= worst:         # no better than the best
                        break
            if big < worst:
                best, worst = x, big
        if worst >= len(sample):
            # Nothing tells them apart now; but rules that keep state may
            # differ later. Run the input that moves the most of them on.
            if not any(L.uses_state(r) for r, _st in sample[:20]):
                return None
            best, most = None, 0
            for x in self.candidates():
                moved = 0
                for rule, st in sample:
                    y = run(rule, x, k, st)
                    if L.advance(rule, st, x, y, k).meta != st.meta:
                        moved += 1
                if moved > most:
                    best, most = x, moved
            return best
        return best

    def invert(self, y: Row) -> Row:
        """The input the live rules agree gives *y*."""
        votes: Dict[Row, int] = {}
        for rule in self.testing:
            back = preimages(rule, self.level) or {}
            x = back.get(y)
            if x is not None:
                votes[x] = votes.get(x, 0) + 1
        self.answered += 1
        self.split += len(votes) > 1
        return max(votes, key=votes.get) if votes else y

    def tell_apart(self, other) -> Optional[Row]:
        """An input where every live rule differs from *other*, or None
        when they all behave like it."""
        k, n = self.level.k, self.level.length
        live = list(self.testing) or list(self.alive)
        if all(same_machine(r, other, self.level) for r in live):
            return None
        for x in L.probes(n, k, count=400, seed=7):
            b = L.run(other, x, k, L.START)
            if all(L.run(r, x, k, L.START) != b for r in live):
                return x
        return None

    def answer(self, x: Row) -> Row:
        votes: Dict[Row, int] = {}
        for rule, st in self.testing.items():
            y = L.run(rule, x, self.level.k, st)
            votes[y] = votes.get(y, 0) + 1
        self.answered += 1
        self.split += len(votes) > 1
        return max(votes, key=votes.get) if votes else x


# --- a machine ---------------------------------------------------------

class Machine(NamedTuple):
    level: Grade
    rule: object
    tests: Tuple[Row, ...]
    seed: int
    plan: Tuple[Row, ...]      # the reference player's experiments
    kind: str = 'crack'        # 'crack', 'twins' or 'invert'
    other: object = None       # the second machine of a 'twins' round


@functools.lru_cache(maxsize=4096)
def _twins(level: Grade, rule) -> frozenset:
    """The rules a single stray experiment would most often mistake for
    this one: those agreeing with it on many fresh inputs."""
    k, n = level.k, level.length
    draw = random.Random(hash(L.code(rule)) & 0xffff)
    xs = [tuple(draw.randrange(k) for _i in range(n)) for _p in range(24)]
    ys = [L.run(rule, x, k, L.START) for x in xs]
    near = []
    for r in _hypotheses(level):
        if r == rule:
            continue
        same = 0
        for x, y in zip(xs, ys):
            if L.run(r, x, k, L.START) == y:
                same += 1
            elif same == 0 and x is xs[2]:
                break
        if same >= 3:
            near.append((-same, L.size(r), r))
    near.sort(key=lambda t: t[:2])
    return frozenset(t[2] for t in near[:40])


@functools.lru_cache(maxsize=64)
def _hypotheses(level: Grade) -> tuple:
    """Every rule a player of this rung could hold, in the order a first
    look would try them."""
    return tuple(Mind(level, 0).alive)


#: How many live rules the reference weighs an experiment against.
SAMPLE = 150

#: Shares of rounds of the other kinds, and where they start.
TWINS_FROM, TWINS_SHARE = 4, 0.25        # from composition
INVERT_STAGE, INVERT_SHARE = 7, 0.4      # at the cryptography stage


def _splits(p: Prim, level: Grade) -> List[Tuple[Prim, ...]]:
    """Two steps that do what one step does."""
    k, n, op, a = level.k, level.length, p.op, p.args
    out = []
    if op in ('rot', 'shift') and a:
        m = n if op == 'rot' else k
        out += [(Prim(op, (b,)), Prim(op, ((a[0] - b) % m,)))
                for b in range(1, m) if (a[0] - b) % m]
    if op == 'mul' and a:
        out += [(Prim('mul', (b,)), Prim('mul', (c,)))
                for b in range(2, k) for c in range(2, k)
                if (b * c) % k == a[0] % k]
    if op == 'rev' and n % 2 == 0:
        out.append((Prim('mirror'), Prim('rot', (n // 2,))))
    return out


def _rewrites(node, level: Grade) -> List:
    """Programs written differently from *node*, step by step (not yet
    checked to behave alike)."""
    out = []
    if isinstance(node, Seq):
        ps = list(node.parts)
        for i, p in enumerate(ps):
            if isinstance(p, Prim):
                for two in _splits(p, level):
                    out.append(Seq(tuple(ps[:i]) + two + tuple(ps[i + 1:])))
            else:
                out += [Seq(tuple(ps[:i]) + (q,) + tuple(ps[i + 1:]))
                        for q in _rewrites(p, level)]
            if i + 1 < len(ps):
                out.append(Seq(tuple(ps[:i]) + (ps[i + 1], ps[i]) +
                               tuple(ps[i + 2:])))
    elif isinstance(node, If):
        out += [If(node.test, q, node.other)
                for q in _rewrites(node.then, level)]
        out += [If(node.test, node.then, q)
                for q in _rewrites(node.other, level)]
    elif isinstance(node, Except):
        out += [Except(q, node.odd) for q in _rewrites(node.usual, level)]
    elif isinstance(node, Alt):
        out += [Alt(q, node.odd) for q in _rewrites(node.even, level)]
        out += [Alt(node.even, q) for q in _rewrites(node.odd, level)]
    elif isinstance(node, Prim):
        out += [Seq(two) for two in _splits(node, level)]
    return out


def _disguise(rule, level: Grade, draw: random.Random):
    """The same machine written another way, or None."""
    ways = [w for w in _rewrites(rule, level) if L.code(w) != L.code(rule)]
    draw.shuffle(ways)
    for w in ways[:12]:
        if same_machine(w, rule, level):
            return w
    return None


def _twin_for(level: Grade, rule, draw: random.Random):
    """A second machine: the same one written another way, or one that
    differs only on a few rows."""
    if draw.random() < 0.5:
        same = _disguise(rule, level, draw)
        if same is not None:
            return same, True
    k, n = level.k, level.length
    xs = L.probes(n, k, count=64, seed=31)
    near = []
    for r in _twins(level, rule):
        if L.uses_state(r) != L.uses_state(rule):
            continue
        apart = sum(L.run(r, x, k, L.START) != L.run(rule, x, k, L.START)
                    for x in xs)
        if 0 < apart <= len(xs) // 4:
            near.append(r)
    if not near:
        return None, False
    return draw.choice(sorted(near, key=L.code)), False


def _preimages(rule, level: Grade) -> Optional[Dict[Row, Row]]:
    """Output -> input for a rule that is one-to-one on rows of the
    rung's length (None if it is not)."""
    k, n = level.k, level.length
    if L.uses_state(rule):
        return None
    back: Dict[Row, Row] = {}
    for x in itertools.product(range(k), repeat=n):
        y = L.run(rule, x, k, L.START)
        if len(y) != n or y in back:
            return None
        back[y] = x
    return back


_PRE: Dict[Tuple[Grade, object], Optional[Dict[Row, Row]]] = {}


def preimages(rule, level: Grade) -> Optional[Dict[Row, Row]]:
    key = (level, rule)
    if key not in _PRE:
        if len(_PRE) > 2000:
            _PRE.clear()
        _PRE[key] = _preimages(rule, level)
    return _PRE[key]


def _invert_tests(level, rule, final, early, draw) -> Optional[Tuple]:
    """Questions for an 'invert it' round: outputs whose input every rule
    still standing agrees on."""
    if level.k ** level.length > 5000:
        return None
    mine = preimages(rule, level)
    if mine is None:
        return None
    tables = []
    for r in final:
        t = preimages(r, level)
        if t is None:
            return None
        tables.append(t)
    others = [preimages(r, level) for r in early]
    asked: List[Row] = []
    outs = list(mine)
    for _q in range(level.tests):
        best, score = None, -1
        for _c in range(80):
            y = draw.choice(outs)
            x = mine[y]
            if y in asked or x == y or len(set(y)) == 1:
                continue
            if any(t.get(y) != x for t in tables):
                continue
            gain = sum(1 for t in others if t is None or t.get(y) != x)
            if gain > score:
                best, score = y, gain
        if best is None:
            return None
        asked.append(best)
    return tuple(asked)


#: Why build() turned candidates down, by place (for tools/bench_cipher).
REJECTS: Dict[int, int] = {}


def _reject(where: int) -> None:
    REJECTS[where] = REJECTS.get(where, 0) + 1
    return None


#: From the nested stage on, the last test question is on a longer row.
GENERALISE = 9


def build(level: Grade, draw: random.Random) -> Optional[Machine]:
    looks = _one_look(level)
    pool = sorted(looks, key=_order(level).get)
    if not pool:
        return _reject(1)
    k = level.k
    rule = draw.choice(pool)
    rivals = set(looks[rule])
    # Shortcut players must lose too: the rung's commonest rule, and the
    # rule a player would settle on after one stray experiment.
    rivals.update(r for r in truths(level)[:3] if r != rule)
    if not gentle(level):
        rivals.update(_twins(level, rule))
    seed = draw.randrange(1 << 30)
    mind = Mind(level, seed)
    if rule not in mind.alive:
        return _reject(2)
    st, log = L.START, []
    while len(log) < level.budget:
        x = mind.experiment()
        if x is None:
            break
        y = L.run(rule, x, k, st)
        st = L.advance(rule, st, x, y, k)
        log.append((x, y))
        mind.update(log)
    final = list(mind.alive)
    if rule not in mind.alive:
        return _reject(3)
    # The real rule must be as simple as anything still standing.
    if L.size(rule) > min(L.size(r) for r in final):
        return _reject(4)
    # Questions: every rule still standing agrees; rules that stood a
    # little earlier do not; the answer is not the question, nor the
    # last thing the machine said.
    earlier = mind.snapshots[max(0, len(mind.snapshots) - 3)]
    if len(earlier) > 200:
        earlier = draw.sample(earlier, 200)
    kind = 'crack'
    if level.stage == INVERT_STAGE and draw.random() < INVERT_SHARE:
        early_rules = list(set(earlier) | rivals)[:60]
        asked_y = _invert_tests(level, rule, final, early_rules, draw)
        if asked_y is not None:
            return Machine(level, rule, asked_y, seed,
                           tuple(x for x, _y in log), 'invert')
    st = L.START                             # the test starts afresh
    states = {r: L.START for r in final}
    early = {r: L.START for r in set(earlier) | rivals}
    beaten = {r: False for r in rivals}
    asked: List[Row] = []
    for q in range(level.tests):
        best, score = None, -1
        cands = [tuple(draw.randrange(k) for _i in range(level.length))
                 for _c in range(90)]
        cands += [(v,) * level.length for v in range(k)]
        cands += [tuple(sorted(c)) for c in cands[:20]]
        cands += [c[:level.length // 2] + c[:(level.length + 1) // 2][::-1]
                  for c in cands[20:40]]
        if level.stage >= 10 and q == 0:
            v = draw.randrange(k)
            cands = [(v,) * level.length]
        flat = sum(len(set(a)) == 1 for a in asked)
        for x in cands:
            if x in asked or (flat and len(set(x)) == 1):
                continue
            y = L.run(rule, x, k, st)
            if not y or y == x or (asked and y == L.run(rule, asked[-1], k,
                                                        L.START)):
                continue
            if any(L.run(r, x, k, s) != y for r, s in states.items()):
                continue
            gain = sum((1000 if r in beaten and not beaten[r] else 1)
                       for r, s in early.items()
                       if L.run(r, x, k, s)[:len(y)] != y)
            if gain > score:
                best, score = x, gain
        if best is None:
            return _reject(5)
        y = L.run(rule, best, k, st)
        for r in beaten:
            if L.run(r, best, k, early[r])[:len(y)] != y:
                beaten[r] = True
        asked.append(best)
        st = L.advance(rule, st, best, y, k)
        states = {r: L.advance(r, s, best, L.run(r, best, k, s), k)
                  for r, s in states.items()}
        early = {r: L.advance(r, s, best, L.run(r, best, k, s), k)
                 for r, s in early.items()}
    if not all(beaten.values()):
        return _reject(6)
    if level.stage >= GENERALISE:
        # One question on a longer row than any experiment: the rule, not
        # a table of the rows seen, is what answers it.
        if any(L.fixed_length(r) for r in states):
            return _reject(7)
        best, score = None, -1
        for _c in range(60):
            x = tuple(draw.randrange(k) for _i in range(level.length + 2))
            if len(set(x)) == 1 or x in asked:
                continue
            y = L.run(rule, x, k, st)
            if not y or y == x:
                continue
            if any(L.run(r, x, k, s) != y for r, s in states.items()):
                continue
            gain = sum(L.run(r, x, k, s)[:len(y)] != y
                       for r, s in early.items())
            if gain > score:
                best, score = x, gain
        if best is None:
            return _reject(8)
        asked.append(best)
    other = None
    if level.stage >= TWINS_FROM and draw.random() < TWINS_SHARE:
        other, same = _twin_for(level, rule, draw)
        # Whether the two are the same must follow from the experiments.
        if other is not None and any(
                same_machine(r, other, level) != same for r in final):
            other = None
        if other is not None:
            kind = 'twins'
    return Machine(level, rule, tuple(asked), seed,
                   tuple(x for x, _y in log), kind, other)


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Machine:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=200)


# --- the hypothesis board -------------------------------------------------
#
# A hypothesis is built from blocks, in prefix order: a form block (two
# steps in a row, if-then-else, ...) is followed by the blocks it needs.
# The menu only offers blocks that fit the next slot, so whatever is on
# the board is always a well-formed beginning of a program.

FORMS = {'then2': ('rule', 'rule'), 'then3': ('rule', 'rule', 'rule'),
         'if': ('test', 'rule', 'rule'), 'alt': ('rule', 'rule'),
         'except': ('rule', 'rule'), 'meta2': ('test', 'rule', 'rule'),
         'meta3': ('test', 'rule', 'rule', 'rule'),
         'prog2': ('sym', 'rule') * 2, 'prog3': ('sym', 'rule') * 3}
FORM_WORDS = {'then2': _('two steps:'), 'then3': _('three steps:'),
              'if': _('if ... then ... else'), 'alt': _('even runs / odd runs'),
              'except': _('usually ... but one symbol throughout ...'),
              'meta2': _('in turn, moving on when ... (2 rules)'),
              'meta3': _('in turn, moving on when ... (3 rules)'),
              'prog2': _('2 instruction symbols'),
              'prog3': _('3 instruction symbols')}
SLOT_WORDS = {'rule': _('a rule'), 'test': _('a test'),
              'sym': _('a symbol')}


class Block(NamedTuple):
    kind: str                  # 'form', 'rule', 'test' or 'sym'
    value: object
    label: str


def _forms_of(node, out: set) -> None:
    if isinstance(node, Seq):
        if len(node.parts) == 2:
            out.add('then2')
        elif len(node.parts) >= 3:
            out.add('then3')
        for p in node.parts:
            if isinstance(p, Prim) and p.op == 'feistel':
                _forms_of(p.args[0], out)
    elif isinstance(node, If):
        out.add('if')
        _forms_of(node.then, out)
        _forms_of(node.other, out)
    elif isinstance(node, Alt):
        out.add('alt')
        _forms_of(node.even, out)
        _forms_of(node.odd, out)
    elif isinstance(node, Except):
        out.add('except')
        _forms_of(node.usual, out)
        _forms_of(node.odd, out)
    elif isinstance(node, Meta):
        out.add('meta%d' % len(node.branches))
        for b in node.branches:
            _forms_of(b, out)
    elif isinstance(node, Prog):
        out.add('prog%d' % len(node.ops))


def _pieces_of(node, prims: set, tests_: set) -> None:
    if isinstance(node, Seq):
        for p in node.parts:
            if isinstance(p, Prim):
                prims.add(p)
            else:
                _pieces_of(p, prims, tests_)
    elif isinstance(node, If):
        tests_.add(node.test)
        _pieces_of(node.then, prims, tests_)
        _pieces_of(node.other, prims, tests_)
    elif isinstance(node, Alt):
        _pieces_of(node.even, prims, tests_)
        _pieces_of(node.odd, prims, tests_)
    elif isinstance(node, Except):
        _pieces_of(node.usual, prims, tests_)
        _pieces_of(node.odd, prims, tests_)
    elif isinstance(node, Meta):
        tests_.add(node.trigger)
        for b in node.branches:
            _pieces_of(b, prims, tests_)
    elif isinstance(node, Prog):
        for _s, p in node.ops:
            prims.add(p)


@functools.lru_cache(maxsize=64)
def blocks(level: Grade) -> Tuple[Block, ...]:
    """Every block the rung's machines are made of."""
    forms, prims, tests_ = {'then2', 'then3'}, set(), set()
    for rule in truths(level):
        _forms_of(rule, forms)
        _pieces_of(rule, prims, tests_)
    prims = {p for p in prims if p.op not in ('perm', 'sub')}
    out = [Block('form', f, FORM_WORDS[f]) for f in FORMS if f in forms]
    out += [Block('rule', p, L.say_prim(p))
            for p in sorted(prims, key=lambda p: (L.size(p), L.code(p)))]
    out += [Block('test', t, L.say_test(t))
            for t in sorted(tests_, key=L.code)]
    if any(f.startswith('prog') for f in forms):
        out += [Block('sym', v, _('symbol %d') % v) for v in range(level.k)]
    return tuple(out)


def expecting(board: Sequence[Block]) -> List[str]:
    """The slots still to fill, the next one last."""
    need = ['rule']
    for b in board:
        if not need:
            break
        need.pop()
        if b.kind == 'form':
            need.extend(reversed(FORMS[b.value]))
    return need


def assemble(board: Sequence[Block]):
    """The program on the board, or None while it is unfinished."""
    if expecting(board):
        return None
    it = iter(board)

    def take():
        b = next(it)
        if b.kind == 'rule':
            return Seq((b.value,))
        if b.kind in ('test', 'sym'):
            return b.value
        parts = [take() for _p in FORMS[b.value]]
        f = b.value
        if f.startswith('then'):
            out = []
            for p in parts:
                out.extend(p.parts if isinstance(p, Seq) else (p,))
            return Seq(tuple(out))
        if f == 'if':
            return If(*parts)
        if f == 'alt':
            return Alt(*parts)
        if f == 'except':
            return Except(*parts)
        if f.startswith('meta'):
            return Meta(tuple(parts[1:]), parts[0])
        ops = []
        for sym, rule in zip(parts[0::2], parts[1::2]):
            first = rule.parts[0] if isinstance(rule, Seq) and rule.parts \
                else None
            ops.append((sym, first if isinstance(first, Prim)
                        else Prim('rev')))
        return Prog(tuple(ops))
    return take()


def same_machine(a, b, level: Grade) -> bool:
    """Whether two programs behave alike on a large set of inputs run in
    order (state and all), and on longer rows where both allow it."""
    k, n = level.k, level.length
    for length in (n, n + 2):
        if length != n and (L.fixed_length(a) or L.fixed_length(b)):
            continue
        ins = L.probes(length, k, count=160, seed=97)
        if L.fingerprint(a, ins, k) != L.fingerprint(b, ins, k):
            return False
    return True


# --- a run ---------------------------------------------------------------

class Run(H.HandRun):
    def __init__(self, machine: Machine) -> None:
        super().__init__(machine.level.seconds)
        self.machine, self.level = machine, machine.level
        self.entry: List[int] = []
        self.log: List[Tuple[Row, Row]] = []
        self.state: State = L.START
        self.testing = False
        self.test_no = 0
        self.answers: List[Tuple[Row, Row, bool]] = []
        self.flash, self.flash_at = '', -10.0
        self.submitted = None
        self.said_same: Optional[bool] = None
        self.mind = None                     # the reference player's notes
        self.twins_q = False                 # asking about a second machine
        # the hypothesis board
        self.board: List[Block] = []
        self.cursor = 0
        self.checked: Dict[Tuple[str, int], bool] = {}
        self.check_text = ''
        # predicting before each run
        self.predicting = False
        self.pending: Optional[Row] = None
        self.predictions: Dict[int, Row] = {}
        # the notebook
        self.scroll = 0
        self.marks: set = set()
        self.numbers = True
        self.order = 'time'
        # the machine at work
        self.shown_at = -10.0
        self.last: Optional[Tuple[Row, Row]] = None

    def left(self) -> int:
        return self.level.budget - len(self.log)

    def _truth(self, x: Row, st: Optional[State] = None) -> Row:
        return L.run(self.machine.rule, x, self.level.k,
                     self.state if st is None else st)

    def want(self) -> int:
        """How many symbols the row being built must have."""
        if self.pending is not None:
            return len(self._truth(self.pending))
        if not self.testing:
            return self.level.length
        q = self.question()
        if q is None or self.machine.kind == 'invert':
            return self.level.length
        return len(self._truth(q))

    def _run(self, x: Row) -> Row:
        y = self._truth(x)
        self.state = L.advance(self.machine.rule, self.state, x, y,
                               self.level.k)
        self.last, self.shown_at = (x, y), self.t
        # the machine thinks: a low hum while the answer comes out
        self.note(0.16 * max(1, len(y)) + 0.15, 98.0, HUM, 0.12,
                  bright=0.3)
        return y

    def _sound(self, y: Row) -> None:
        for i, v in enumerate(y):
            self.note(0.14, PITCH[v], TONE, 0.4,
                      pan=-0.6 + 1.2 * i / max(1, len(y) - 1),
                      at=self.t + 0.16 * i)

    def say(self, words: str) -> None:
        self.flash = words
        self.flash_at = self.t

    def type(self, v: int) -> None:
        if self.result is not None or v >= self.level.k or \
                len(self.entry) >= self.want():
            return
        self.entry.append(v)
        self.note(0.06, PITCH[v], TICK, 0.3)

    def delete(self, at: Optional[int] = None) -> None:
        if self.entry:
            self.entry.pop(len(self.entry) - 1 if at is None
                           else min(at, len(self.entry) - 1))
        elif self.pending is not None:       # back to the input
            self.entry, self.pending = list(self.pending), None

    def go(self) -> None:
        if self.result is not None:
            return
        if len(self.entry) != self.want():
            self.say(_('Fill every slot first'))
            self.note(0.1, 90.0, BUZZ, 0.3)
            return
        x = tuple(self.entry)
        self.entry = []
        if not self.testing:
            if self.left() <= 0:
                return
            if self.predicting and self.pending is None:
                self.pending = x                 # now the prediction
                self.say(_('What will it give? Put in your guess'))
                return
            guess = None
            if self.pending is not None:
                x, guess = self.pending, x
                self.pending = None
            y = self._run(x)
            self.log.append((x, y))
            if guess is not None:
                self.predictions[len(self.log) - 1] = guess
                self.say(_('As you said') if guess == y
                         else _('Not what you said'))
            self.checked = {}
            self.note(0.1, 700.0, CHIME, 0.3)
            self._sound(y)
            self.scroll = 0
            if self.left() <= 0:
                self.begin_test()
            return
        m, k = self.machine, self.level.k
        if self.twins_q:                     # an input that tells them apart
            a = L.run(m.rule, x, k, L.START)
            b = L.run(m.other, x, k, L.START)
            self.answers.append((x, a, a != b))
            self._sound(a)
            return self._end(a != b, _('They differ there') if a != b
                             else _('Both give the same there'))
        given = m.tests[self.test_no]
        if m.kind == 'invert':               # given the output: the input
            truth = preimages(m.rule, self.level)[given]
            ok = L.run(m.rule, x, k, L.START) == given
            self.answers.append((truth, given, ok))
            self._sound(given)
        else:
            truth = self._run(given)
            ok = x == truth
            self.answers.append((given, truth, ok))
            self._sound(truth)
        self.scroll = 0
        if not ok:
            return self._end(False, _('Wrong'))
        self.test_no += 1
        self.note(0.15, 880.0, CHIME, 0.4)
        if self.test_no >= len(m.tests):
            if m.kind == 'twins':
                self.twins_q = True
                self.entry = []
                self.say(_('Is the second machine the same?'))
                return
            self._end(True, _('Cracked it'))

    def _end(self, ok: bool, words: str) -> None:
        self.note(0.6, 1046.0, DONE, 0.5) if ok else \
            self.note(0.5, 80.0, MISS, 0.5)
        self.result = (ok, _('%s. The machine: %s') %
                       (words, describe(self.machine.rule)))

    def begin_test(self) -> None:
        if not self.testing and self.result is None:
            self.testing = True
            self.pending = None
            self.state = L.START             # the test starts afresh
            self.entry = []
            self.checked = {}
            self.note(0.3, 520.0, CHIME, 0.4)

    def question(self) -> Optional[Row]:
        if self.twins_q or not self.testing or \
                self.test_no >= len(self.machine.tests):
            return None
        return self.machine.tests[self.test_no]

    # --- the hypothesis board -----------------------------------------

    def menu(self) -> List[Block]:
        """The blocks that fit the board's next slot."""
        need = expecting(self.board)
        if not need:
            return []
        return [b for b in blocks(self.level) if b.kind == need[-1] or
                (need[-1] == 'rule' and b.kind == 'form')]

    def move_cursor(self, by: int) -> None:
        n = len(self.menu())
        self.cursor = (self.cursor + by) % n if n else 0

    def add_block(self, i: Optional[int] = None) -> None:
        menu = self.menu()
        if self.result is not None or not menu:
            return
        i = self.cursor if i is None else i
        if 0 <= i < len(menu):
            self.board.append(menu[i])
            self.cursor = 0
            self.checked = {}
            self.note(0.05, 600.0, TICK, 0.25)

    def undo_block(self) -> None:
        if self.board:
            self.board.pop()
            self.cursor = 0
            self.checked = {}

    def hypothesis(self):
        return assemble(self.board)

    def check(self) -> None:
        """Run the hypothesis over every row of the notebook."""
        h = self.hypothesis()
        if h is None:
            self.say(_('Finish the hypothesis first'))
            self.note(0.1, 90.0, BUZZ, 0.3)
            return
        k, out = self.level.k, {}
        st = L.START
        for i, (x, y) in enumerate(self.log):
            got = L.run(h, x, k, st)
            out[('run', i)] = got == y
            st = L.advance(h, st, x, got, k)
        st = L.START
        for i, (x, y, _ok) in enumerate(self.answers):
            got = L.run(h, x, k, st)
            out[('test', i)] = got == y
            st = L.advance(h, st, x, got, k)
        self.checked = out
        good = sum(out.values())
        self.check_text = _('fits %d of %d rows') % (good, len(out))
        self.note(0.2, 660.0 if good == len(out) else 220.0, CHIME, 0.3)

    def submit(self) -> None:
        """Give the hypothesis itself as the answer (from the composition
        stage on): judged by how it behaves, not how it is written."""
        if self.result is not None:
            return
        if self.twins_q:                     # "they are the same"
            same = same_machine(self.machine.rule, self.machine.other,
                                self.level)
            self.said_same = same
            return self._end(same, _('Yes, the same machine') if same
                             else _('No, they differ'))
        if self.level.stage < 4:
            self.say(_('From rung 10 you can give the rule itself'))
            return
        h = self.hypothesis()
        if h is None:
            self.say(_('Finish the hypothesis first'))
            return
        if same_machine(h, self.machine.rule, self.level):
            self.note(0.6, 1046.0, DONE, 0.5)
            self.result = (True, _('Cracked it, rule and all: %s') %
                           describe(self.machine.rule))
        else:
            self.note(0.5, 80.0, MISS, 0.5)
            self.result = (False, _('Not the same machine. It was: %s') %
                           describe(self.machine.rule))
        self.submitted = h

    # --- the notebook -------------------------------------------------

    def rows(self) -> List[Tuple[str, int, Row, Row]]:
        """The notebook: ('run', i, input, output) and ('test', ...), in
        the order chosen."""
        out = [('run', i, x, y) for i, (x, y) in enumerate(self.log)]
        if self.order == 'input':
            out.sort(key=lambda r: r[2])
        out += [('test', i, x, y) for i, (x, y, _ok) in
                enumerate(self.answers)]
        return out

    def visible(self) -> List[Tuple[str, int, Row, Row]]:
        rows = self.rows()
        end = max(0, len(rows) - self.scroll)
        return rows[max(0, end - NOTE_ROWS):end]

    def scroll_by(self, by: int) -> None:
        most = max(0, len(self.rows()) - NOTE_ROWS)
        self.scroll = max(0, min(most, self.scroll + by))

    def mark(self, row: Optional[Tuple[str, int]] = None) -> None:
        if row is None:
            if not self.log:
                return
            row = ('run', len(self.log) - 1)
        self.marks ^= {row}

    # --- the pointer and the keys ---------------------------------------

    def press(self) -> None:
        if self.result is not None or self.hand.down:
            return
        self.hand.down = True
        x, y = self.hand.x, self.hand.y
        if abs(y - PAL_Y) <= 30:
            for i in range(self.level.k):
                if abs(x - pal_x(i)) <= 30:
                    return self.type(i)
            for bx, act_ in ((DEL_X, self.delete), (RUN_X, self.go),
                             (TEST_X, self.begin_test)):
                if abs(x - bx) <= BUTTON_W / 2:
                    return act_()
        if abs(y - ROW_Y) <= 24:
            if abs(x - PREDICT_AT[0]) <= 60:
                return self.key(PREDICT)
            n = self.want()
            for i in range(len(self.entry)):
                if abs(x - slot_x(i, n)) <= 22:
                    return self.delete(i)
        for name, (bx, by) in BOARD_BUTTONS.items():
            if abs(x - bx) <= BOARD_BUTTON_W / 2 and abs(y - by) <= 12:
                return {'undo': self.undo_block, 'check': self.check,
                        'submit': self.submit}[name]()
        if MENU_X <= x <= MENU_X + 190:
            menu = self.menu()
            top = max(0, self.cursor - MENU_ROWS + 1)
            for j in range(min(MENU_ROWS, len(menu) - top)):
                if abs(y - menu_y(j)) <= MENU_ROW / 2:
                    return self.add_block(top + j)
        if NOTE[0] <= x <= NOTE[2]:
            if y >= NOTE[3] - 26:
                return self.key(SORT if x < 760 else NUMBERS)
            for j, row in enumerate(self.visible()):
                if abs(y - note_y(j)) <= NOTE_ROW / 2:
                    return self.mark(row[:2])

    def release(self) -> None:
        self.hand.down = False

    def key(self, port: int) -> None:
        if SYM <= port < SYM + SYMBOLS:
            self.type(port - SYM)
        elif port == DELETE:
            self.delete()
        elif port == RUN:
            self.go()
        elif port == TEST:
            self.begin_test()
        elif port == NEXT_BLOCK:
            self.move_cursor(1)
        elif port == PREV_BLOCK:
            self.move_cursor(-1)
        elif port == ADD_BLOCK:
            self.add_block()
        elif port == UNDO_BLOCK:
            self.undo_block()
        elif port == CHECK:
            self.check()
        elif port == SUBMIT:
            self.submit()
        elif port == PREDICT:
            if not self.testing:
                self.predicting = not self.predicting
                if not self.predicting and self.pending is not None:
                    self.entry, self.pending = list(self.pending), None
        elif port == SCROLL_UP:
            self.scroll_by(1)
        elif port == SCROLL_DOWN:
            self.scroll_by(-1)
        elif port == MARK:
            self.mark()
        elif port == NUMBERS:
            self.numbers = not self.numbers
        elif port == SORT:
            self.order = 'input' if self.order == 'time' else 'time'

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t >= self.end:
            self.result = (False, _('Out of time. The machine: %s') %
                           describe(self.machine.rule))


# --- what a player keeps between rounds ----------------------------------
#
# The screen keeps a small library in the data folder (never in agent or
# test runs): each operator a player has cracked and the rung where it was
# first met. These functions only read and build it; the screen writes it.

LIBRARY = 'cipher_abyss_library.json'
#: One JSON object per round played (fields: METRIC_FIELDS).
ROUNDS = 'cipher_abyss_rounds.jsonl'


def operators(rule) -> List[str]:
    """The kinds of step a program is made of (rot, shift, stride, ...)."""
    ops: set = set()

    def walk(n):
        if isinstance(n, Prim):
            ops.add(n.op)
            if n.op == 'feistel':
                walk(n.args[0])
        elif isinstance(n, Seq):
            for p in n.parts:
                walk(p)
        elif isinstance(n, If):
            walk(n.then)
            walk(n.other)
        elif isinstance(n, (Alt,)):
            walk(n.even)
            walk(n.odd)
        elif isinstance(n, Except):
            walk(n.usual)
            walk(n.odd)
        elif isinstance(n, Meta):
            for b in n.branches:
                walk(b)
        elif isinstance(n, Prog):
            for _s, p in n.ops:
                walk(p)
    walk(rule)
    return sorted(ops)


def remembered(library: Dict, rule, rung: int) -> List[Tuple[str, int]]:
    """The operators of *rule* this player cracked at a lower rung."""
    seen = library.get('operators', {})
    return [(op, seen[op]) for op in operators(rule)
            if op in seen and seen[op] < rung]


def learn(library: Dict, rule, rung: int) -> Dict:
    """The library after cracking *rule* at *rung*."""
    seen = dict(library.get('operators', {}))
    for op in operators(rule):
        seen[op] = min(seen.get(op, rung), rung)
    return dict(library, version=1, operators=seen)


def notebook_text(run: Run) -> str:
    """The notebook as plain text, numbers only, for keeping."""
    lines = ['# The Cipher Abyss, rung %d (%s)' % (run.level.rung,
                                                  stage_name(run.level)),
             '# symbols 0-%d; input -> output' % (run.level.k - 1)]
    for i, (x, y) in enumerate(run.log):
        lines.append('%2d  %s -> %s' % (i + 1, ' '.join(map(str, x)),
                                        ' '.join(map(str, y))))
    for x, y, ok in run.answers:
        lines.append('test %s -> %s  %s' % (' '.join(map(str, x)),
                                            ' '.join(map(str, y)),
                                            'right' if ok else 'wrong'))
    if run.result is not None:
        lines.append('# the machine: %s' % L.code(run.machine.rule))
    return '\n'.join(lines) + '\n'


def end_tones(run: Run, bits: Sequence[float]) -> None:
    """On the end screen, one tone per experiment in order: a bright one,
    higher the more it told, for an experiment that split the rules, a
    dull one for one that told (almost) nothing."""
    for i, b in enumerate(bits):
        at = run.t + 0.4 + 0.28 * i
        if b >= 0.5:
            run.note(0.22, 660.0 + 70.0 * min(b, 6.0), CHIME, 0.3, at=at)
        else:
            run.note(0.26, 110.0, BUZZ, 0.22, at=at)


def summary(run: Run) -> Dict:
    """What the end of a round shows: the rule, how much each of the
    player's experiments told (in bits: the rung's rules standing before
    and after), which told most, and what the reference player ran."""
    mind = Mind(run.level, 0)
    bits = []
    before = len(mind.alive)
    for i in range(len(run.log)):
        mind.update(run.log[:i + 1])
        after = max(1, len(mind.alive))
        bits.append(math.log2(before / after) if before else 0.0)
        before = after
    best = max(range(len(bits)), key=bits.__getitem__) if bits else None
    return {'words': describe(run.machine.rule),
            'code': L.code(run.machine.rule), 'bits': bits, 'best': best,
            'standing': len(mind.alive), 'reference': run.machine.plan}


#: The fields of one round's record (see the Readme): the results file
#: holds one such JSON object per line.
METRIC_FIELDS = ('rung', 'stage', 'kind', 'won', 'accuracy', 'questions',
                 'experiments', 'reference_experiments', 'bits',
                 'bits_per_experiment', 'rule', 'rule_size',
                 'submitted', 'submitted_size', 'seconds')


def metrics(run: Run) -> Dict:
    """How a round went, beyond pass or fail: for the end screen, the
    results file and scoring scripts (never the reward)."""
    info = summary(run)
    said = run.said_same                    # None, or right or not
    asked = len(run.answers) + (said is not None)
    right = sum(ok for _x, _y, ok in run.answers) + bool(said)
    h = run.submitted
    bits = info['bits']
    return {'rung': run.level.rung, 'stage': stage_name(run.level),
            'kind': run.machine.kind,
            'won': bool(run.result and run.result[0]),
            'accuracy': right / asked if asked else None,
            'questions': asked, 'experiments': len(run.log),
            'reference_experiments': len(run.machine.plan),
            'bits': [round(b, 3) for b in bits],
            'bits_per_experiment': (round(sum(bits) / len(bits), 3)
                                    if bits else 0.0),
            'rule': info['code'], 'rule_size': L.size(run.machine.rule),
            'submitted': L.code(h) if h is not None else None,
            'submitted_size': L.size(h) if h is not None else None,
            'seconds': round(run.t, 2)}


act = H.act


def full_log(run: Run) -> List[Tuple[Row, Row]]:
    return run.log + [(g, t) for g, t, _ok in run.answers]


def test_log(run: Run) -> List[Tuple[Row, Row]]:
    """The test so far: it starts the machine afresh."""
    return [(g, t) for g, t, _ok in run.answers]


def autopilot(run: Run) -> List[int]:
    """Run the input that splits the live rules most evenly; when the
    experiments are spent, or nothing more can split them, take the test
    and answer as the live rules all would."""
    if run.result is not None:
        return []
    if run.hand.down:
        return [H.RELEASE]
    if run.mind is None:
        run.mind = Mind(run.level, run.machine.seed)
    mind = run.mind
    if mind.queue:
        return [mind.queue.pop(0)]
    mind.update(run.log)
    if run.entry:
        return [DELETE]
    if not run.testing:
        x = mind.experiment() if run.left() > 0 else None
        if x is None:
            return [TEST]
    else:
        if mind.testing is None:
            mind.begin_test()
        while mind.tested < len(run.answers):
            given, truth, _ok = run.answers[mind.tested]
            mind.tested_on(given, truth)
        if run.twins_q:
            x = mind.tell_apart(run.machine.other)
            if x is None:
                return [SUBMIT]
        elif run.machine.kind == 'invert':
            x = mind.invert(run.question())
        else:
            x = mind.answer(run.question())
    mind.queue = [SYM + v for v in x] + [RUN]
    return [mind.queue.pop(0)]


def play(machine: Machine, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(machine), pilot, EVENTS, act, dt)
