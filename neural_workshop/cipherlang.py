# -*- coding: utf-8 -*-
"""The language The Cipher Abyss's machines are written in.

A machine is a small program over rows of symbols 0..k-1. Programs are
trees of these nodes:

* ``Prim(op, args)``: one transformation (reverse, rotate 2, ...);
* ``Seq(parts)``: transformations one after another;
* ``If(test, then, other)``: one or the other, by a test of the input
  or of the machine's state;
* ``Alt(even, odd)``: one on even runs, the other on odd runs;
* ``Except(usual, odd)``: the usual unless every symbol is the same;
* ``Prog(ops)``: the input is itself a program: some symbols are
  opcodes (each with a hidden meaning), the rest are data, and each
  opcode in turn is applied to the data;
* ``Meta(branches, trigger)``: a rule that changes which rule applies:
  every input that passes the trigger moves the machine on to the next
  branch.

The machine's state between runs is a ``State``: how many runs, the
last input and output, and the meta counter.

Everything here is pure: ``run`` interprets, ``advance`` moves the
state on, ``say`` puts a program in words, ``code`` in a compact formal
notation that ``parse`` reads back, ``canon`` simplifies (rotations add
up, a reverse twice is nothing, ...), ``size`` is its description
length, and ``dedupe`` keeps one program per behaviour so a family's
count of hypotheses is honest.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .i18n import _

Row = Tuple[int, ...]


class _Node:
    """Programs are compared and hashed a great deal: keep the hash."""

    __slots__ = ()

    def __hash__(self):
        try:
            return self.__dict__['_h']
        except KeyError:
            h = hash((type(self).__name__,) + tuple(
                getattr(self, f) for f in self.__dataclass_fields__))
            object.__setattr__(self, '_h', h)
            return h


@dataclass(frozen=True, eq=True)
class Prim(_Node):
    op: str
    args: tuple = ()


@dataclass(frozen=True, eq=True)
class Test(_Node):
    op: str
    args: tuple = ()


@dataclass(frozen=True, eq=True)
class Seq(_Node):
    parts: tuple = ()


@dataclass(frozen=True, eq=True)
class If(_Node):
    test: Test
    then: object
    other: object


@dataclass(frozen=True, eq=True)
class Alt(_Node):
    even: object
    odd: object


@dataclass(frozen=True, eq=True)
class Except(_Node):
    usual: object
    odd: object


@dataclass(frozen=True, eq=True)
class Prog(_Node):
    ops: tuple                 # ((symbol, Prim), ...)


@dataclass(frozen=True, eq=True)
class Meta(_Node):
    branches: tuple
    trigger: Test


@dataclass(frozen=True)
class State:
    runs: int = 0
    last_in: Optional[Row] = None
    last_out: Optional[Row] = None
    meta: int = 0


START = State()


def one(op: str, *args) -> Seq:
    return Seq((Prim(op, tuple(args)),))


# --- the primitives ----------------------------------------------------

#: Primitives that keep the row's length.
KEEP = ('rev', 'swap', 'rot', 'shift', 'mul', 'affine', 'sub', 'perm',
        'prefix', 'diff', 'sort', 'conv', 'tshift', 'mem', 'mirror',
        'weave', 'unweave', 'runs', 'oddshift', 'xor', 'gf', 'feistel',
        'fold', 'stride')
#: Primitives that change it.
RESIZE = ('dedupe', 'double', 'halve')
#: Primitives defined only for one row length (no generalising).
FIXED = ('perm', 'feistel')

GF_POLY = {4: 0b111, 8: 0b1011}


def gf_mul(a: int, b: int, k: int) -> int:
    """Multiplication in GF(k), k = 4 or 8."""
    poly, top = GF_POLY[k], k.bit_length() - 1
    out = 0
    while b:
        if b & 1:
            out ^= a
        b >>= 1
        a <<= 1
        if a >> top:
            a ^= poly
    return out


def prim(p: Prim, x: Row, k: int, st: State) -> Row:
    op, a, n = p.op, p.args, len(x)
    if n == 0:
        return x
    if op == 'rev':
        return x[::-1]
    if op == 'swap':
        y = list(x)
        for i in range(0, n - 1, 2):
            y[i], y[i + 1] = y[i + 1], y[i]
        return tuple(y)
    if op == 'rot':
        m = a[0] % n
        return x[-m:] + x[:-m] if m else x
    if op == 'shift':
        return tuple((v + a[0]) % k for v in x)
    if op == 'mul':
        return tuple((v * a[0]) % k for v in x)
    if op == 'affine':
        return tuple((a[0] * v + a[1]) % k for v in x)
    if op == 'sub':
        return tuple(a[0][v] for v in x)
    if op == 'perm':
        table = a[0]
        if len(table) != n:
            return x
        return tuple(x[table[i]] for i in range(n))
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
        p0, p1, c = a
        return tuple((p0 * x[i] + p1 * (x[i - 1] if i else 0) + c) % k
                     for i in range(n))
    if op == 'tshift':
        return tuple((v + a[0] * st.runs) % k for v in x)
    if op == 'mem':
        last = st.last_in or ()
        return tuple((v + (last[i] if i < len(last) else 0)) % k
                     for i, v in enumerate(x))
    if op == 'stride':                         # every s-th place, wrapping
        return tuple(x[(i * a[0]) % n] for i in range(n))
    if op == 'mirror':
        h = n // 2
        return x[:h][::-1] + x[h:][::-1]
    if op == 'weave':
        return x[0::2] + x[1::2]
    if op == 'unweave':
        h = (n + 1) // 2
        y = [0] * n
        y[0::2], y[1::2] = x[:h], x[h:]
        return tuple(y)
    if op == 'runs':
        out, count = [], 0
        for i, v in enumerate(x):
            count = count + 1 if i and x[i - 1] == v else 1
            out.append(count % k)
        return tuple(out)
    if op == 'oddshift':
        return tuple((v + a[0]) % k if i % 2 else v for i, v in enumerate(x))
    if op == 'xor':
        return tuple(v ^ a[0] for v in x)
    if op == 'gf':
        return tuple(gf_mul(v, a[0], k) for v in x)
    if op == 'fold':                        # each plus its mirror partner
        return tuple((x[i] + x[n - 1 - i]) % k for i in range(n))
    if op == 'feistel':
        h = n // 2
        left, right = x[:h], x[h:2 * h]
        f = run(a[0], right, k, st)
        return right + tuple((l + r) % k for l, r in zip(left, f)) + x[2 * h:]
    if op == 'dedupe':
        return tuple(v for i, v in enumerate(x) if i == 0 or x[i - 1] != v)
    if op == 'double':
        return tuple(v for v in x for _t in (0, 1))
    if op == 'halve':
        return x[0::2]
    raise ValueError(op)


def test(t: Test, x: Row, k: int, st: State) -> bool:
    op, a = t.op, t.args
    if not x:
        return False
    if op == 'first':
        return x[0] == a[0]
    if op == 'last':
        return x[-1] == a[0]
    if op == 'has':
        return a[0] in x
    if op == 'evens':
        return x.count(a[0]) % 2 == 0
    if op == 'sumeven':
        return sum(x) % 2 == 0
    if op == 'rises':
        return x[0] < x[-1]
    if op == 'tparity':
        return st.runs % 2 == 0
    if op == 'same':
        return len(set(x)) == 1
    if op == 'pal':
        return x == x[::-1]
    if op == 'sorted':
        return all(x[i] <= x[i + 1] for i in range(len(x) - 1))
    if op == 'echo':
        return bool(st.last_out) and st.last_out[0] == a[0]
    raise ValueError(op)


def run(node, x: Row, k: int, st: State = START) -> Row:
    """What the program gives for *x* in state *st*."""
    if isinstance(node, Seq):
        for p in node.parts:
            x = prim(p, x, k, st) if isinstance(p, Prim) else run(p, x, k, st)
        return x
    if isinstance(node, Prim):
        return prim(node, x, k, st)
    if isinstance(node, If):
        return run(node.then if test(node.test, x, k, st) else node.other,
                   x, k, st)
    if isinstance(node, Alt):
        return run(node.even if st.runs % 2 == 0 else node.odd, x, k, st)
    if isinstance(node, Except):
        return run(node.odd if len(set(x)) == 1 else node.usual, x, k, st)
    if isinstance(node, Prog):
        ops = dict(node.ops)
        data = tuple(v for v in x if v not in ops)
        for v in x:
            if v in ops and data:
                data = prim(ops[v], data, k, st)
        return data
    if isinstance(node, Meta):
        return run(node.branches[st.meta % len(node.branches)], x, k, st)
    raise TypeError(node)


def _metas(node) -> Iterable[Meta]:
    if isinstance(node, Meta):
        yield node
        for b in node.branches:
            yield from _metas(b)
    elif isinstance(node, Seq):
        for p in node.parts:
            yield from _metas(p)
    elif isinstance(node, If):
        yield from _metas(node.then)
        yield from _metas(node.other)
    elif isinstance(node, Alt):
        yield from _metas(node.even)
        yield from _metas(node.odd)
    elif isinstance(node, Except):
        yield from _metas(node.usual)
        yield from _metas(node.odd)


def advance(node, st: State, x: Row, y: Row, k: int) -> State:
    """The machine's state after it was given *x* and gave *y*."""
    bump = sum(1 for m in _metas(node) if test(m.trigger, x, k, st))
    return State(st.runs + 1, x, y, st.meta + bump)


def replay(node, log: Sequence[Tuple[Row, Row]], k: int) -> State:
    """The state after the inputs in *log* (the outputs it records are
    the real machine's, but each program computes its own)."""
    st = START
    for x, _y in log:
        st = advance(node, st, x, run(node, x, k, st), k)
    return st


def uses_state(node) -> bool:
    text = code(node)
    return any(w in text for w in ('tshift', 'mem', 'tparity', 'echo',
                                   'alt(', 'meta('))


def fixed_length(node) -> bool:
    text = code(node)
    return any(w + '[' in text or w + '(' in text for w in FIXED)


# --- words ---------------------------------------------------------------

def say_prim(p: Prim) -> str:
    op, a = p.op, p.args
    plain = {'rev': _('reverse'), 'swap': _('swap neighbours'),
             'prefix': _('running sum'), 'diff': _('differences'),
             'sort': _('sort'), 'mem': _('add the last input'),
             'mirror': _('reverse each half'),
             'weave': _('evens first, then odds'),
             'unweave': _('deal into evens and odds'),
             'runs': _('count each run'), 'fold': _('add each to its mirror'),
             'dedupe': _('drop repeats'), 'double': _('double each'),
             'halve': _('keep every other')}
    if op in plain:
        return plain[op]
    if op == 'sub':
        return _('substitute %s') % ''.join(str(v) for v in a[0])
    if op == 'perm':
        return _('shuffle positions %s') % ''.join(str(v) for v in a[0])
    if op == 'conv':
        return _('out = %d*this + %d*before + %d') % a
    if op == 'affine':
        return _('multiply by %d and add %d') % a
    if op == 'feistel':
        return _('a Feistel round of (%s)') % say(a[0])
    return {'rot': _('rotate right %d'), 'shift': _('add %d to each'),
            'mul': _('multiply each by %d'),
            'tshift': _('add %d more each run'),
            'oddshift': _('add %d at odd places'),
            'xor': _('xor each with %d'),
            'stride': _('read every %d-th place, wrapping round'),
            'gf': _('multiply each by %d in GF(k)')}[op] % a[0]


def say_test(t: Test) -> str:
    op, a = t.op, t.args
    if a:
        return {'first': _('it starts with %d'), 'last': _('it ends with %d'),
                'has': _('it has a %d'),
                'evens': _('it has an even number of %ds'),
                'echo': _('the last answer started with %d')}[op] % a[0]
    return {'sumeven': _('its sum is even'),
            'rises': _('it starts lower than it ends'),
            'tparity': _('the run count is even'),
            'same': _('every symbol is the same'),
            'pal': _('it reads the same both ways'),
            'sorted': _('it is already in order')}[op]


def say(node) -> str:
    if isinstance(node, Prim):
        return say_prim(node)
    if isinstance(node, Seq):
        if not node.parts:
            return _('nothing')
        return _(', then ').join(say(p) for p in node.parts)
    if isinstance(node, If):
        return _('if %s: %s; else %s') % (say_test(node.test),
                                           say(node.then), say(node.other))
    if isinstance(node, Alt):
        return _('on even runs %s; on odd runs %s') % (say(node.even),
                                                       say(node.odd))
    if isinstance(node, Except):
        return _('%s; but when every symbol is the same: %s') % (
            say(node.usual), say(node.odd))
    if isinstance(node, Prog):
        return _('symbols %s are instructions (%s), applied in turn to '
                 'the rest') % (
            ', '.join(str(s) for s, _p in node.ops),
            '; '.join('%d: %s' % (s, say_prim(p)) for s, p in node.ops))
    if isinstance(node, Meta):
        return _('in turn %s; moving on after every input where %s') % (
            _(' / ').join(say(b) for b in node.branches),
            say_test(node.trigger))
    return str(node)


# --- the formal notation -------------------------------------------------

def _args(a) -> str:
    out = []
    for v in a:
        if isinstance(v, tuple):
            out.append('[' + ','.join(str(t) for t in v) + ']')
        elif isinstance(v, (Seq, Prim)):
            out.append(code(v))
        else:
            out.append(str(v))
    return ','.join(out)


def code(node) -> str:
    """A compact formal form that ``parse`` reads back."""
    if isinstance(node, Prim):
        return node.op + ('(%s)' % _args(node.args) if node.args else '')
    if isinstance(node, Test):
        return node.op + ('(%s)' % _args(node.args) if node.args else '')
    if isinstance(node, Seq):
        if len(node.parts) == 1:
            return code(node.parts[0])
        return 'seq(%s)' % ','.join(code(p) for p in node.parts)
    if isinstance(node, If):
        return 'if(%s,%s,%s)' % (code(node.test), code(node.then),
                                 code(node.other))
    if isinstance(node, Alt):
        return 'alt(%s,%s)' % (code(node.even), code(node.odd))
    if isinstance(node, Except):
        return 'except(%s,%s)' % (code(node.usual), code(node.odd))
    if isinstance(node, Prog):
        return 'prog(%s)' % ','.join('%d:%s' % (s, code(p))
                                     for s, p in node.ops)
    if isinstance(node, Meta):
        return 'meta(%s,%s)' % (code(node.trigger),
                                ','.join(code(b) for b in node.branches))
    raise TypeError(node)


TESTS = ('first', 'last', 'has', 'evens', 'sumeven', 'rises', 'tparity',
         'echo', 'same', 'pal', 'sorted')


class _Reader:
    def __init__(self, text: str) -> None:
        self.toks = re.findall(r'\d+|[A-Za-z_]+|[(),\[\]:]', text)
        self.i = 0

    def peek(self) -> Optional[str]:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, want: Optional[str] = None) -> str:
        tok = self.peek()
        if tok is None or (want is not None and tok != want):
            raise ValueError('expected %r at %r' % (want, tok))
        self.i += 1
        return tok

    def table(self) -> tuple:
        self.take('[')
        out = []
        while self.peek() != ']':
            out.append(int(self.take()))
            if self.peek() == ',':
                self.take(',')
        self.take(']')
        return tuple(out)

    def arg(self):
        tok = self.peek()
        if tok is None:
            raise ValueError('the text stops short')
        if tok == '[':
            return self.table()
        if tok.isdigit():
            return int(self.take())
        return self.node()

    def call_args(self) -> list:
        out = []
        if self.peek() != '(':
            return out
        self.take('(')
        while self.peek() != ')':
            out.append(self.arg())
            if self.peek() == ',':
                self.take(',')
        self.take(')')
        return out

    def node(self):
        name = self.take()
        if not name[0].isalpha():
            raise ValueError('expected a name at %r' % name)
        if name == 'seq':
            return Seq(tuple(_part(p) for p in self.call_args()))
        if name == 'if':
            t, a, b = self.call_args()
            return If(t, _whole(a), _whole(b))
        if name == 'alt':
            a, b = self.call_args()
            return Alt(_whole(a), _whole(b))
        if name == 'except':
            a, b = self.call_args()
            return Except(_whole(a), _whole(b))
        if name == 'meta':
            parts = self.call_args()
            return Meta(tuple(_whole(b) for b in parts[1:]), parts[0])
        if name == 'prog':
            self.take('(')
            ops = []
            while self.peek() != ')':
                s = int(self.take())
                self.take(':')
                ops.append((s, self.node()))
                if self.peek() == ',':
                    self.take(',')
            self.take(')')
            return Prog(tuple(ops))
        args = tuple(_whole(a) if isinstance(a, Prim) else a
                     for a in self.call_args())
        if name in TESTS:
            return Test(name, args)
        return Prim(name, args)


def _part(node):
    if isinstance(node, Seq) and len(node.parts) == 1:
        return node.parts[0]
    return node


def _whole(node):
    if isinstance(node, Prim):
        return Seq((node,))
    return node


def parse(text: str):
    """The program written *text* in the formal notation."""
    r = _Reader(text)
    node = _whole(r.node())
    if r.peek() is not None:
        raise ValueError('left over: %r' % r.toks[r.i:])
    if isinstance(node, Seq):
        node = Seq(tuple(_fix_feistel(p) for p in node.parts))
    return node


def _fix_feistel(p):
    if isinstance(p, Prim) and p.op == 'feistel' and \
            isinstance(p.args[0], Prim):
        return Prim('feistel', (Seq((p.args[0],)),))
    return p


# --- simpler forms ------------------------------------------------------

def size(node) -> int:
    """Description length: how much has to be said to give the rule."""
    if isinstance(node, Prim):
        n = 1
        for a in node.args:
            n += len(a) if isinstance(a, tuple) else (
                size(a) if isinstance(a, (Seq, Prim)) else 1)
        return n
    if isinstance(node, Test):
        return 1 + len(node.args)
    if isinstance(node, Seq):
        return sum(size(p) for p in node.parts)
    if isinstance(node, If):
        return 1 + size(node.test) + size(node.then) + size(node.other)
    if isinstance(node, Alt):
        return 1 + size(node.even) + size(node.odd)
    if isinstance(node, Except):
        return 1 + size(node.usual) + size(node.odd)
    if isinstance(node, Prog):
        return 1 + sum(1 + size(p) for _s, p in node.ops)
    if isinstance(node, Meta):
        return 1 + size(node.trigger) + sum(size(b) for b in node.branches)
    raise TypeError(node)


_INVOLUTIONS = ('rev', 'swap')
_INVERSES = {('weave', 'unweave'), ('unweave', 'weave')}


def canon(node, n: int, k: int):
    """A simpler program that does the same: rotations and shifts add
    up, multiplications multiply, a reverse twice is nothing, a weave
    and its unweave cancel, and steps that do nothing go."""
    if isinstance(node, Seq):
        parts: List[Prim] = []
        for p in node.parts:
            p = canon(p, n, k)
            if isinstance(p, Seq):
                parts.extend(p.parts)
            else:
                parts.append(p)
        out: List = []
        for p in parts:
            if isinstance(p, Prim):
                if (p.op == 'rot' and p.args[0] % n == 0) or \
                        (p.op in ('shift', 'xor', 'tshift', 'oddshift')
                         and p.args[0] % k == 0) or \
                        (p.op == 'mul' and p.args[0] % k == 1):
                    continue
            if out and isinstance(p, Prim) and isinstance(out[-1], Prim):
                q = out[-1]
                if q.op == p.op == 'rot':
                    out[-1] = Prim('rot', ((q.args[0] + p.args[0]) % n,))
                elif q.op == p.op and p.op in ('shift', 'tshift',
                                               'oddshift'):
                    out[-1] = Prim(p.op, ((q.args[0] + p.args[0]) % k,))
                elif q.op == p.op == 'mul':
                    out[-1] = Prim('mul', ((q.args[0] * p.args[0]) % k,))
                elif q.op == p.op == 'xor':
                    out[-1] = Prim('xor', (q.args[0] ^ p.args[0],))
                elif q.op == p.op and p.op in _INVOLUTIONS:
                    out.pop()
                elif (q.op, p.op) in _INVERSES:
                    out.pop()
                elif q.op == p.op == 'sort':
                    continue
                else:
                    out.append(p)
                    continue
                last = out[-1] if out else None
                if isinstance(last, Prim) and (
                        (last.op == 'rot' and last.args[0] == 0) or
                        (last.op in ('shift', 'tshift', 'oddshift', 'xor')
                         and last.args[0] == 0) or
                        (last.op == 'mul' and last.args[0] == 1)):
                    out.pop()
                continue
            out.append(p)
        return Seq(tuple(out))
    if isinstance(node, If):
        a, b = canon(node.then, n, k), canon(node.other, n, k)
        return a if a == b else If(node.test, a, b)
    if isinstance(node, Alt):
        a, b = canon(node.even, n, k), canon(node.odd, n, k)
        return a if a == b else Alt(a, b)
    if isinstance(node, Except):
        a, b = canon(node.usual, n, k), canon(node.odd, n, k)
        return a if a == b else Except(a, b)
    if isinstance(node, Meta):
        bs = tuple(canon(b, n, k) for b in node.branches)
        return bs[0] if len(set(bs)) == 1 else Meta(bs, node.trigger)
    return node


def probes(n: int, k: int, count: int = 48, seed: int = 1) -> List[Row]:
    """A fixed set of inputs that tells most programs apart."""
    draw = random.Random(seed * 1000 + n * 10 + k)
    out = [tuple(draw.randrange(k) for _i in range(n)) for _c in range(count)]
    out += [(v,) * n for v in range(k)]
    out.append(tuple(i % k for i in range(n)))
    out.append(tuple([1 % k] + [0] * (n - 1)))
    out.append(tuple([0] * (n - 1) + [1 % k]))
    return out


def fingerprint(node, ins: Sequence[Row], k: int) -> tuple:
    """What the program says to *ins*, run in that order, state and all."""
    st, out = START, []
    for x in ins:
        y = run(node, x, k, st)
        out.append(y)
        st = advance(node, st, x, y, k)
    return tuple(out)


def dedupe(family: Iterable, n: int, k: int) -> List:
    """One program per behaviour: the simplest (canonical, shortest)."""
    ins = probes(n, k)
    best: Dict[tuple, object] = {}
    for node in family:
        node = canon(node, n, k)
        if isinstance(node, Seq) and not node.parts:
            continue                          # it does nothing
        fp = fingerprint(node, ins, k)
        if all(x == y for x, y in zip(ins, fp)):
            continue
        old = best.get(fp)
        if old is None or (size(node), code(node)) < (size(old), code(old)):
            best[fp] = node
    return list(best.values())
