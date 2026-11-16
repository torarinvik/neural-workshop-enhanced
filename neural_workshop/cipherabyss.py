# -*- coding: utf-8 -*-
"""The Cipher Abyss: find out what the machine does.

A machine takes a row of coloured symbols and gives back another row.
What it does to them is hidden. Build an input from the palette, run
it, and read what comes out; the experiments are limited. When you are
ready (or the experiments are spent) the machine is tested: it shows
inputs it has not shown before, and you must give the output it would
give, every one right.

Every rung adds a little more to the language the machines are written
in, and what was learned below stays useful above:

* rungs 1-3, patterns: two colours; the machine reverses, rotates,
  swaps neighbours or swaps the colours;
* rungs 4-6, transformations: three colours; shifts of any size,
  substitutions, multiplying, running sums and differences, sorting;
* rungs 7-9, conditional rules: one transformation or another,
  depending on a hidden test of the input;
* rungs 10-12, composition: two transformations chained;
* rungs 13-15, state machines: what the machine does depends on how
  many times it has run, or on what it was given last time;
* rungs 16-19, modular arithmetic: five symbols counted mod 5, each
  output a weighted sum of its input and the one before;
* rungs 20-24, nested systems: the test that picks the transformation
  may look at the machine's own last answer, or at its run count;
* from rung 25, adversarial systems: a hidden exception that only a
  rare kind of input sets off (and the test will ask about it), three
  transformations chained, six symbols, longer rows and fewer
  experiments every few rungs.

Each machine dealt is one a careful experimenter can pin down: the
reference player, which keeps every rule of the rung's language still
consistent with what it has seen and runs whichever input splits them
most evenly, must have answered the test from the experiments allowed.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import itertools
import math
import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from . import hand as H
from .i18n import _

SYM = H.KEYS                   # ports 14-19: the six symbols
DELETE = H.KEYS + 6
RUN = H.KEYS + 7               # run the input, or give the answer
TEST = H.KEYS + 8              # ready for the test
PORTS = H.KEYS + 9
EVENTS = tuple(range(PORTS))
CHIME, TONE, BUZZ, DONE, MISS, TICK = range(6)
PATCHES = ('bell', 'chirp', 'growl', 'bell', 'growl', 'wood')
PITCH = (262.0, 330.0, 392.0, 466.0, 523.0, 622.0)

# Where things are on the 1000 by 640 screen (y up).
PAL_Y = 62.0
BUTTON_W = 96.0


def pal_x(i: int) -> float:
    return 110.0 + 78.0 * i


DEL_X, RUN_X, TEST_X = 640.0, 760.0, 890.0
ROW_Y = 200.0


def slot_x(i: int, n: int) -> float:
    return 60.0 + 60.0 * i


Seq = Tuple[int, ...]


class Grade(NamedTuple):
    rung: int
    stage: int                 # 1 patterns ... 8 adversarial
    k: int                     # symbols
    length: int
    budget: int                # experiments
    tests: int
    seconds: float


STAGES = ((1, 'patterns'), (4, 'transformations'), (7, 'conditions'),
          (10, 'composition'), (13, 'state'), (16, 'arithmetic'),
          (20, 'nested'), (25, 'adversarial'))


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    stage = max(k + 1 for k, (start, _n) in enumerate(STAGES) if r >= start)
    top = max(0, r - 25)
    k = (2, 3, 3, 4, 4, 5, 5, 6)[stage - 1]
    length = (4, 5, 5, 6, 6, 6, 6, min(8, 6 + top // 6))[stage - 1]
    budget = (6, 6, 8, 7, 7, 7, 8, max(5, 8 - top // 4))[stage - 1]
    tests = (2, 3, 3, 3, 3, 3, 4, 4)[stage - 1]
    return Grade(r, stage, k, length, budget, tests,
                 min(1200.0, 300.0 + 30.0 * r))


# --- the language ------------------------------------------------------
#
# A rule is a nested tuple: ('seq', parts) or ('if', test, then, else)
# or ('except', usual, odd); a part is a primitive like ('rot', 2). The
# machine's state is (runs so far, last input, last output).

State = Tuple[int, Optional[Seq], Optional[Seq]]


def _prim(p, x: Seq, k: int, st: State) -> Seq:
    op, n = p[0], len(x)
    if op == 'rev':
        return x[::-1]
    if op == 'swap':
        y = list(x)
        for i in range(0, n - 1, 2):
            y[i], y[i + 1] = y[i + 1], y[i]
        return tuple(y)
    if op == 'rot':
        m = p[1] % n
        return x[-m:] + x[:-m] if m else x
    if op == 'shift':
        return tuple((v + p[1]) % k for v in x)
    if op == 'mul':
        return tuple((v * p[1]) % k for v in x)
    if op == 'sub':
        return tuple(p[1][v] for v in x)
    if op == 'prefix':
        out, s = [], 0
        for v in x:
            s = (s + v) % k
            out.append(s)
        return tuple(out)
    if op == 'diff':
        return tuple((x[i] - (x[i - 1] if i else 0)) % k for i in range(n))
    if op == 'sort':
        return tuple(sorted(x))
    if op == 'conv':
        a, b, c = p[1:]
        return tuple((a * x[i] + b * (x[i - 1] if i else 0) + c) % k
                     for i in range(n))
    if op == 'tshift':                      # shift by c for every run
        return tuple((v + p[1] * st[0]) % k for v in x)
    if op == 'mem':                         # add the last input
        last = st[1] or (0,) * n
        return tuple((v + w) % k for v, w in zip(x, last))
    raise ValueError(op)


def _test(t, x: Seq, k: int, st: State) -> bool:
    op = t[0]
    if op == 'first':
        return x[0] == t[1]
    if op == 'last':
        return x[-1] == t[1]
    if op == 'has':
        return t[1] in x
    if op == 'evens':
        return x.count(t[1]) % 2 == 0
    if op == 'sumeven':
        return sum(x) % 2 == 0
    if op == 'rises':
        return x[0] < x[-1]
    if op == 'tparity':
        return st[0] % 2 == 0
    if op == 'echo':                        # the last answer began with s
        return st[2] is not None and st[2][0] == t[1]
    raise ValueError(op)


def apply(rule, x: Seq, k: int, st: State) -> Seq:
    kind = rule[0]
    if kind == 'seq':
        for p in rule[1]:
            x = _prim(p, x, k, st)
        return x
    if kind == 'if':
        return apply(rule[2] if _test(rule[1], x, k, st) else rule[3], x,
                     k, st)
    if kind == 'except':
        if len(set(x)) == 1:
            return apply(rule[2], x, k, st)
        return apply(rule[1], x, k, st)
    if kind == 'alt':
        return apply(rule[1] if st[0] % 2 == 0 else rule[2], x, k, st)
    raise ValueError(kind)


def _say_prim(p) -> str:
    op = p[0]
    plain = {'rev': _('reverse'), 'swap': _('swap neighbours'),
             'prefix': _('running sum'), 'diff': _('differences'),
             'sort': _('sort'), 'mem': _('add the last input')}
    if op in plain:
        return plain[op]
    if op == 'sub':
        return _('substitute %s') % ''.join(str(v) for v in p[1])
    if op == 'conv':
        return _('out = %d*this + %d*before + %d') % p[1:]
    return {'rot': _('rotate right %d'), 'shift': _('add %d to each'),
            'mul': _('multiply each by %d'),
            'tshift': _('add %d more each run')}[op] % p[1]


def _say_test(t) -> str:
    op = t[0]
    return {
        'first': _('it starts with %d'), 'last': _('it ends with %d'),
        'has': _('it has a %d'), 'evens': _('it has an even number of %ds'),
        'echo': _('the last answer started with %d'),
    }.get(op, '') % t[1] if len(t) > 1 else {
        'sumeven': _('its sum is even'),
        'rises': _('it starts lower than it ends'),
        'tparity': _('the run count is even'),
    }[op]


def describe(rule) -> str:
    kind = rule[0]
    if kind == 'seq':
        return _(', then ').join(_say_prim(p) for p in rule[1])
    if kind == 'if':
        return _('if %s: %s; else %s') % (_say_test(rule[1]),
                                           describe(rule[2]),
                                           describe(rule[3]))
    if kind == 'except':
        return _('%s; but when every symbol is the same: %s') % (
            describe(rule[1]), describe(rule[2]))
    if kind == 'alt':
        return _('on even runs %s; on odd runs %s') % (
            describe(rule[1]), describe(rule[2]))
    return str(rule)


# --- the families ------------------------------------------------------

def _units(k: int) -> List[int]:
    return [a for a in range(2, k) if math.gcd(a, k) == 1]


def basic(k: int, n: int) -> List[tuple]:
    return ([('rev',), ('swap',)] + [('rot', m) for m in range(1, n)]
            + [('shift', c) for c in range(1, k)])


def wider(k: int, n: int) -> List[tuple]:
    out = basic(k, n) + [('mul', a) for a in _units(k)] + \
        [('prefix',), ('diff',), ('sort',)]
    if k <= 3:
        shifts = {tuple((v + c) % k for v in range(k)) for c in range(k)}
        out += [('sub', p) for p in itertools.permutations(range(k))
                if p not in shifts]
    return out


def tests(k: int, state: bool = False) -> List[tuple]:
    out = [(op, s) for op in ('first', 'last', 'has') for s in range(k)] \
        + [('evens', 0), ('sumeven',), ('rises',)]
    if state:
        out += [('tparity',)] + [('echo', s) for s in range(k)]
    return out


def _one(p) -> tuple:
    return ('seq', (p,))


def family(level: Grade) -> List[tuple]:
    k, n, s = level.k, level.length, level.stage
    if s == 1:
        return [_one(p) for p in basic(k, n)]
    if s == 2:
        return [_one(p) for p in wider(k, n)]
    if s == 3:
        b = basic(k, n)
        return [('if', t, _one(f), _one(g)) for t in tests(k)
                for f in b for g in b if f != g]
    if s == 4:
        w = wider(k, n)
        return [('seq', (f, g)) for f in w for g in w if f != g]
    if s == 5:
        w, b = wider(k, n), basic(k, n)
        return ([('seq', (f, ('tshift', c))) for f in w for c in range(1, k)]
                + [('alt', _one(f), _one(g)) for f in b for g in b if f != g]
                + [('seq', (f, ('mem',))) for f in w])
    if s == 6:
        places = [None, ('rev',)] + [('rot', m) for m in range(1, n)]
        out = []
        for a in range(1, k):
            for b in range(k):
                for c in range(k):
                    for p in places:
                        conv = ('conv', a, b, c)
                        out.append(('seq', (conv,) if p is None
                                    else (p, conv)))
        return out
    if s == 7:
        w = wider(k, n)
        return [('if', t, _one(f), _one(g)) for t in tests(k, state=True)
                for f in w for g in w if f != g]
    w = wider(k, n)
    deep = level.rung >= 33
    out = []
    rng = random.Random(level.rung)
    pairs = [(f, g) for f in w for g in w if f != g]
    for f, g in pairs:
        for h in w:
            usual = ('seq', (f, g, h)) if deep else ('seq', (f, g))
            out.append(('except', usual, _one(h)))
    rng.shuffle(out)
    return out[:6000]


# --- a machine ---------------------------------------------------------

class Machine(NamedTuple):
    level: Grade
    rule: tuple
    tests: Tuple[Seq, ...]
    seed: int


def _rand_input(level: Grade, draw: random.Random) -> Seq:
    return tuple(draw.randrange(level.k) for _k in range(level.length))


def build(level: Grade, draw: random.Random) -> Optional[Machine]:
    fam = family(level)
    rule = draw.choice(fam)
    probe = [_rand_input(level, draw) for _k in range(8)]
    st: State = (0, None, None)
    outs = []
    for x in probe:                          # does it do anything?
        y = apply(rule, x, level.k, st)
        outs.append(y)
        st = (st[0] + 1, x, y)
    if all(x == y for x, y in zip(probe, outs)):
        return None
    tests = [_rand_input(level, draw) for _k in range(level.tests)]
    if level.stage >= 8:                     # the exception is asked about
        v = draw.randrange(level.k)
        tests[draw.randrange(len(tests))] = (v,) * level.length
    return Machine(level, rule, tuple(tests), draw.randrange(1 << 30))


def deal(rung: int, seed: Optional[int] = None, rng=None) -> Machine:
    import sys
    return H.deal(sys.modules[__name__], rung, seed, rng, tries=60)


class Run(H.HandRun):
    def __init__(self, machine: Machine) -> None:
        super().__init__(machine.level.seconds)
        self.machine, self.level = machine, machine.level
        self.entry: List[int] = []
        self.log: List[Tuple[Seq, Seq]] = []
        self.state: State = (0, None, None)
        self.testing = False
        self.test_no = 0
        self.answers: List[Tuple[Seq, Seq, bool]] = []
        self.flash = ''
        self.mind = None                     # the reference player's notes

    def left(self) -> int:
        return self.level.budget - len(self.log)

    def _run(self, x: Seq) -> Seq:
        y = apply(self.machine.rule, x, self.level.k, self.state)
        self.state = (self.state[0] + 1, x, y)
        return y

    def _sound(self, y: Seq) -> None:
        for i, v in enumerate(y):
            self.note(0.14, PITCH[v], TONE, 0.4,
                      pan=-0.6 + 1.2 * i / max(1, len(y) - 1),
                      at=self.t + 0.16 * i)

    def type(self, v: int) -> None:
        if self.result is not None or v >= self.level.k or \
                len(self.entry) >= self.level.length:
            return
        self.entry.append(v)
        self.note(0.06, PITCH[v], TICK, 0.3)

    def delete(self, at: Optional[int] = None) -> None:
        if self.entry:
            self.entry.pop(len(self.entry) - 1 if at is None
                           else min(at, len(self.entry) - 1))

    def go(self) -> None:
        if self.result is not None:
            return
        if len(self.entry) != self.level.length:
            self.flash = _('Fill every slot first')
            self.note(0.1, 90.0, BUZZ, 0.3)
            return
        x = tuple(self.entry)
        self.entry = []
        if not self.testing:
            if self.left() <= 0:
                return
            y = self._run(x)
            self.log.append((x, y))
            self.note(0.1, 700.0, CHIME, 0.3)
            self._sound(y)
            if self.left() <= 0:
                self.begin_test()
            return
        given = self.machine.tests[self.test_no]
        truth = self._run(given)
        ok = x == truth
        self.answers.append((given, truth, ok))
        self._sound(truth)
        if not ok:
            self.note(0.5, 80.0, MISS, 0.5)
            self.result = (False, _('Wrong. The machine: %s') %
                           describe(self.machine.rule))
            return
        self.test_no += 1
        self.note(0.15, 880.0, CHIME, 0.4)
        if self.test_no >= len(self.machine.tests):
            self.note(0.6, 1046.0, DONE, 0.5)
            self.result = (True, _('Cracked it: %s') %
                           describe(self.machine.rule))

    def begin_test(self) -> None:
        if not self.testing and self.result is None:
            self.testing = True
            self.entry = []
            self.note(0.3, 520.0, CHIME, 0.4)

    def question(self) -> Optional[Seq]:
        if not self.testing or self.test_no >= len(self.machine.tests):
            return None
        return self.machine.tests[self.test_no]

    # pointer
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
        if abs(y - ROW_Y) <= 26:
            for i in range(len(self.entry)):
                if abs(x - slot_x(i, self.level.length)) <= 26:
                    return self.delete(i)

    def release(self) -> None:
        self.hand.down = False

    def key(self, port: int) -> None:
        if SYM <= port < SYM + 6:
            self.type(port - SYM)
        elif port == DELETE:
            self.delete()
        elif port == RUN:
            self.go()
        elif port == TEST:
            self.begin_test()

    def step(self, dt: float, control=None) -> None:
        if self.result is not None:
            return
        self.t += dt
        if self.t >= self.end:
            self.result = (False, _('Out of time. The machine: %s') %
                           describe(self.machine.rule))


act = H.act


# --- the reference player ----------------------------------------------

class Mind:
    """Every rule of the rung's language still consistent with what has
    been seen, and what to type next."""

    def __init__(self, machine: Machine) -> None:
        self.level = machine.level
        self.alive = family(machine.level)
        self.draw = random.Random(machine.seed)
        self.queue: List[int] = []
        self.seen = 0

    def predict(self, rule, log, x: Seq) -> Seq:
        st: State = (0, None, None)
        k = self.level.k
        for a, _b in log:
            y = apply(rule, a, k, st)
            st = (st[0] + 1, a, y)
        return apply(rule, x, k, st)

    def update(self, log) -> None:
        k = self.level.k
        while self.seen < len(log):
            j = self.seen
            keep = []
            for rule in self.alive:
                st: State = (0, None, None)
                ok = True
                for a, b in log[:j + 1]:
                    y = apply(rule, a, k, st)
                    st = (st[0] + 1, a, y)
                ok = y == log[j][1]
                if ok:
                    keep.append(rule)
            self.alive = keep
            self.seen += 1

    def candidates(self) -> List[Seq]:
        lv = self.level
        out = [_rand_input(lv, self.draw) for _k in range(30)]
        out += [(v,) * lv.length for v in range(lv.k)]
        out.append(tuple(i % lv.k for i in range(lv.length)))
        out.append(tuple([1] + [0] * (lv.length - 1)))
        return out

    def experiment(self, log) -> Optional[Seq]:
        sample = self.alive if len(self.alive) <= 250 else \
            self.draw.sample(self.alive, 250)
        if len(sample) <= 1:
            return None
        best, worst = None, len(sample) + 1
        for x in self.candidates():
            buckets: Dict[Seq, int] = {}
            for rule in sample:
                y = self.predict(rule, log, x)
                buckets[y] = buckets.get(y, 0) + 1
            big = max(buckets.values())
            if big < worst:
                best, worst = x, big
        if worst >= len(sample):
            return None                      # nothing tells them apart
        return best

    def answer(self, log, x: Seq) -> Seq:
        votes: Dict[Seq, int] = {}
        for rule in self.alive:
            y = self.predict(rule, log, x)
            votes[y] = votes.get(y, 0) + 1
        return max(votes, key=votes.get) if votes else x


def _full_log(run: Run) -> List[Tuple[Seq, Seq]]:
    return run.log + [(g, t) for g, t, _ok in run.answers]


def autopilot(run: Run) -> List[int]:
    """Run the input that splits the live rules most evenly; when the
    experiments are spent, or nothing more can split them, take the test
    and answer as most of the live rules would."""
    if run.result is not None:
        return []
    if run.hand.down:
        return [H.RELEASE]
    if run.mind is None:
        run.mind = Mind(run.machine)
    mind = run.mind
    if mind.queue:
        return [mind.queue.pop(0)]
    log = _full_log(run)
    mind.update(log)
    if run.entry:
        return [DELETE]
    if not run.testing:
        x = mind.experiment(log) if run.left() > 0 else None
        if x is None:
            return [TEST]
    else:
        x = mind.answer(log, run.question())
    mind.queue = [SYM + v for v in x] + [RUN]
    return [mind.queue.pop(0)]


def play(machine: Machine, pilot=autopilot, dt: float = 1 / 60.0
         ) -> Tuple[bool, str]:
    return H.play(Run(machine), pilot, EVENTS, act, dt)
