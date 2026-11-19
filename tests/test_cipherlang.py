#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Cipher Abyss's language: every piece, the notation, the
simplifier, the deduplication.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from neural_workshop import cipherlang as L
from neural_workshop.cipherlang import (Alt, Except, If, Meta, Prim, Prog,
                                        Seq, State, Test, one)

X = (0, 1, 2, 3, 3, 2)


def go(node, x=X, k=4, st=L.START):
    return L.run(node, x, k, st)


class ThePieces(unittest.TestCase):

    def test_positions(self):
        self.assertEqual(go(one('rev')), (2, 3, 3, 2, 1, 0))
        self.assertEqual(go(one('swap')), (1, 0, 3, 2, 2, 3))
        self.assertEqual(go(one('rot', 2)), (3, 2, 0, 1, 2, 3))
        self.assertEqual(go(one('mirror')), (2, 1, 0, 2, 3, 3))
        self.assertEqual(go(one('weave')), (0, 2, 3, 1, 3, 2))
        self.assertEqual(go(one('unweave'), go(one('weave'))), X)
        self.assertEqual(go(one('perm', (5, 4, 3, 2, 1, 0))),
                         go(one('rev')))

    def test_values(self):
        self.assertEqual(go(one('shift', 1)), (1, 2, 3, 0, 0, 3))
        self.assertEqual(go(one('mul', 3)), (0, 3, 2, 1, 1, 2))
        self.assertEqual(go(one('affine', 3, 1)), (1, 0, 3, 2, 2, 3))
        self.assertEqual(go(one('sub', (1, 0, 3, 2))), (1, 0, 3, 2, 2, 3))
        self.assertEqual(go(one('prefix')), (0, 1, 3, 2, 1, 3))
        self.assertEqual(go(one('diff')), (0, 1, 1, 1, 0, 3))
        self.assertEqual(go(one('sort')), (0, 1, 2, 2, 3, 3))
        self.assertEqual(go(one('runs')), (1, 1, 1, 1, 2, 1))
        self.assertEqual(go(one('oddshift', 1)), (0, 2, 2, 0, 3, 3))
        self.assertEqual(go(one('fold')), (2, 0, 1, 1, 0, 2))
        self.assertEqual(go(one('conv', 1, 1, 0)), (0, 1, 3, 1, 2, 1))

    def test_finite_fields(self):
        self.assertEqual(go(one('xor', 3)), (3, 2, 1, 0, 0, 1))
        self.assertEqual(L.gf_mul(2, 2, 4), 3)          # x*x = x+1
        self.assertEqual(L.gf_mul(2, 3, 4), 1)
        self.assertEqual(L.gf_mul(4, 2, 8), 3)          # x^3 = x+1
        for a in range(1, 8):                            # a field: no zero
            self.assertEqual(sorted(L.gf_mul(a, b, 8) for b in range(8)),
                             list(range(8)))

    def test_a_feistel_round_can_be_undone(self):
        f = one('rot', 1)
        y = go(one('feistel', f))
        right, mixed = y[:3], y[3:]
        left = tuple((m - r) % 4 for m, r in zip(mixed, go(f, right)))
        self.assertEqual(left + right, X)

    def test_length_changers(self):
        self.assertEqual(go(one('dedupe')), (0, 1, 2, 3, 2))
        self.assertEqual(go(one('double'), (1, 2)), (1, 1, 2, 2))
        self.assertEqual(go(one('halve')), (0, 2, 3))

    def test_state(self):
        st = State(runs=2, last_in=(1, 1, 1, 1, 1, 1))
        self.assertEqual(go(one('tshift', 1), st=st), (2, 3, 0, 1, 1, 0))
        self.assertEqual(go(one('mem'), st=st), (1, 2, 3, 0, 0, 3))

    def test_structures(self):
        cond = If(Test('first', (0,)), one('rev'), one('shift', 1))
        self.assertEqual(go(cond), go(one('rev')))
        self.assertEqual(go(cond, (1, 0)), (2, 1))
        alt = Alt(one('rev'), one('swap'))
        self.assertEqual(go(alt, st=State(runs=1)), go(one('swap')))
        exc = Except(one('rev'), one('shift', 1))
        self.assertEqual(go(exc, (2, 2, 2)), (3, 3, 3))
        prog = Prog(((0, Prim('rev')), (1, Prim('shift', (1,)))))
        self.assertEqual(go(prog, (2, 0, 3, 1)), (0, 3))   # 2,3 rev, +1

    def test_a_meta_rule_moves_on(self):
        meta = Meta((one('rev'), one('shift', 1)), Test('has', (3,)))
        st = L.advance(meta, L.START, (3, 0), go(meta, (3, 0)), 4)
        self.assertEqual(st.meta, 1)
        self.assertEqual(go(meta, (0, 1), st=st), (1, 2))
        st2 = L.advance(meta, st, (0, 1), (1, 2), 4)
        self.assertEqual(st2.meta, 1)                      # no 3: stays

    def test_rare_tests(self):
        self.assertTrue(L.test(Test('same'), (2, 2), 4, L.START))
        self.assertTrue(L.test(Test('pal'), (1, 2, 1), 4, L.START))
        self.assertTrue(L.test(Test('sorted'), (0, 1, 1), 4, L.START))
        self.assertFalse(L.test(Test('sorted'), (1, 0), 4, L.START))


class TheReadme(unittest.TestCase):
    """The language table in the task reference (docs/TASKS.md), row by row: one example a step,
    on 0 1 1 3 2 0 with four symbols."""

    X = (0, 1, 1, 3, 2, 0)
    TABLE = {'rev': '0 2 3 1 1 0', 'swap': '1 0 3 1 0 2',
             'rot(2)': '2 0 0 1 1 3', 'mirror': '1 1 0 0 2 3',
             'weave': '0 1 2 1 3 0', 'unweave': '0 3 1 2 1 0',
             'perm([2,0,1,5,3,4])': '1 0 1 0 3 2',
             'stride(5)': '0 0 2 3 1 1', 'shift(1)': '1 2 2 0 3 1',
             'mul(3)': '0 3 3 1 2 0', 'affine(3,1)': '1 0 0 2 3 1',
             'sub([1,0,3,2])': '1 0 0 2 3 1', 'prefix': '0 1 2 1 3 3',
             'diff': '0 1 0 2 3 2', 'sort': '0 0 1 1 2 3',
             'conv(1,2,0)': '0 1 3 1 0 0', 'runs': '1 1 2 1 1 1',
             'oddshift(1)': '0 2 1 0 2 1', 'fold': '0 3 0 0 3 0',
             'xor(1)': '1 0 0 2 3 1', 'gf(2)': '0 2 2 1 3 0',
             'feistel(seq(shift(1)))': '3 2 0 0 0 2',
             'dedupe': '0 1 3 2 0', 'double': '0 0 1 1 1 1 3 3 2 2 0 0',
             'halve': '0 1 2'}

    def test_every_example(self):
        for text, want in self.TABLE.items():
            got = L.run(L.parse(text), self.X, 4)
            self.assertEqual(' '.join(map(str, got)), want, text)

    def test_every_step_is_in_the_table(self):
        named = {L.parse(t).parts[0].op for t in self.TABLE}
        self.assertEqual(set(L.KEEP + L.RESIZE) - named, {'tshift', 'mem'})


class TheNotation(unittest.TestCase):

    NODES = [one('rev'), Seq((Prim('rot', (2,)), Prim('shift', (1,)))),
             If(Test('first', (0,)), one('rev'), one('sub', (1, 0, 3, 2))),
             Alt(one('swap'), one('perm', (1, 0, 3, 2))),
             Except(Seq((Prim('mul', (3,)), Prim('prefix'))),
                    one('xor', 2)),
             Prog(((0, Prim('rev')), (1, Prim('shift', (1,))))),
             Meta((one('rev'), one('rot', 1)), Test('has', (3,))),
             one('feistel', one('rot', 1)),
             If(Test('same'), one('halve'), one('dedupe'))]

    def test_every_program_reads_back(self):
        for node in self.NODES:
            self.assertEqual(L.parse(L.code(node)), node, L.code(node))

    def test_every_program_can_be_said(self):
        for node in self.NODES:
            self.assertTrue(L.say(node))

    def test_bad_text_is_refused(self):
        with self.assertRaises(ValueError):
            L.parse('seq(rev,')


class TheSimplifier(unittest.TestCase):

    def test_things_that_cancel(self):
        node = Seq((Prim('rot', (2,)), Prim('rot', (4,)), Prim('rev'),
                    Prim('rev'), Prim('shift', (1,)), Prim('shift', (3,))))
        self.assertEqual(L.canon(node, 6, 4), Seq(()))
        node = Seq((Prim('weave'), Prim('unweave'), Prim('mul', (3,)),
                    Prim('mul', (3,))))
        self.assertEqual(L.canon(node, 6, 4), Seq(()))

    def test_simplifying_keeps_the_behaviour(self):
        node = Seq((Prim('rot', (1,)), Prim('rot', (2,)), Prim('swap'),
                    Prim('shift', (2,)), Prim('shift', (1,))))
        for x in L.probes(6, 4):
            self.assertEqual(go(node, x), go(L.canon(node, 6, 4), x))

    def test_dedupe_keeps_one_per_behaviour_the_shortest(self):
        fam = [one('rev'), one('perm', (5, 4, 3, 2, 1, 0)),
               Seq((Prim('rot', (1,)), Prim('rot', (1,)))), one('rot', 2)]
        out = L.dedupe(fam, 6, 4)
        self.assertEqual(sorted(L.code(r) for r in out), ['rev', 'rot(2)'])


if __name__ == '__main__':
    unittest.main()
