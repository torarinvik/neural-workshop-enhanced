#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Cipher Abyss: the language, the laboratory, the boundary.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from handsupport import heard, wins
from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import cipherabyss as M
from neural_workshop import cipherlang as L

RUNGS = (1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 40)
ZERO = L.START


class TheLadder(unittest.TestCase):

    def test_the_reference_passes_and_idle_and_random_fail(self):
        ref, idle, rand = wins(M, RUNGS)
        self.assertEqual(len(ref), 2 * len(RUNGS))
        self.assertEqual(idle, [])
        self.assertEqual(rand, [])

    def test_each_stage_comes_in_at_its_rung(self):
        starts = [s for s, _n in M.STAGES]
        self.assertEqual([M.grade(r).stage for r in starts],
                         list(range(1, len(starts) + 1)))
        self.assertLess(M.grade(60).budget, M.grade(40).budget)

    def test_the_first_rungs_are_short_and_plain(self):
        one, two, three = M.grade(1), M.grade(2), M.grade(3)
        self.assertTrue(M.plain(one) and M.plain(two))
        self.assertFalse(M.plain(three))
        self.assertEqual((one.length, one.tests), (3, 2))
        for rung in (1, 2):                   # one plain step, one quirk
            for seed in range(6):
                r = M.deal(rung, seed=seed).rule
                self.assertIsInstance(r, L.If)
                for arm in (r.then, r.other):
                    self.assertEqual(len(arm.parts), 1)

    def test_the_open_top_never_stops_growing(self):
        def biggest(rung):
            return max(L.size(r) for r in M.truths(M.grade(rung)))
        sizes = [biggest(r) for r in (40, 100, 400, 1600)]
        self.assertEqual(sizes, sorted(sizes))
        self.assertGreater(sizes[-1], 4 * sizes[0])
        far = M.grade(100000)
        self.assertEqual((far.k, far.length, far.budget, far.tests),
                         (8, 12, 4, 6))
        self.assertTrue(M.play(M.deal(700, seed=1))[0])

    def test_every_stage_has_machines(self):
        for start, _name in M.STAGES:
            self.assertTrue(M._one_look(M.grade(start)), start)


class TheGuarantees(unittest.TestCase):

    def play_plan(self, m):
        run = M.Run(m)
        for x in m.plan:
            for v in x:
                M.act(run, M.SYM + v)
            M.act(run, M.RUN)
        return run

    def test_every_rule_still_standing_agrees_on_the_test(self):
        for rung in (1, 7, 16, 25):
            m = M.deal(rung, seed=3)
            run = self.play_plan(m)
            mind = M.Mind(m.level, m.seed)
            mind.update(run.log)
            M.act(run, M.TEST)
            mind.begin_test()
            for q in m.tests:
                outs = {L.run(r, q, m.level.k, st)
                        for r, st in mind.testing.items()}
                self.assertEqual(len(outs), 1, (rung, L.code(m.rule)))
                truth = outs.pop()
                for v in truth:
                    M.act(run, M.SYM + v)
                M.act(run, M.RUN)
                mind.tested_on(q, truth)
            if run.result is None:           # a two machines round: one more
                self.assertTrue(run.twins_q)
                while run.result is None:
                    ports = M.autopilot(run)
                    if ports:
                        M.act(run, ports[0])
                    run.step(1 / 60.0)
            self.assertTrue(run.result[0])

    def test_nothing_simpler_still_fits(self):
        for rung in (4, 10, 19):
            m = M.deal(rung, seed=4)
            run = self.play_plan(m)
            mind = M.Mind(m.level, m.seed)
            mind.update(run.log)
            self.assertEqual(L.size(m.rule),
                             min(L.size(r) for r in mind.alive))

    def test_one_look_is_never_enough(self):
        for rung in (1, 2, 3, 4, 10):
            m = M.deal(rung, seed=5)
            self.assertTrue(M._one_look(m.level)[m.rule])

    def test_the_test_starts_the_machine_afresh(self):
        m = M.deal(13, seed=2)
        run = self.play_plan(m)
        M.act(run, M.TEST)
        self.assertEqual(run.state, L.START)


class TheLaboratory(unittest.TestCase):

    def test_an_experiment_is_logged_and_spends_one(self):
        run = M.Run(M.deal(1, seed=1))
        for v in (0, 1, 0, 0):
            M.act(run, M.SYM + v)
        M.act(run, M.RUN)
        self.assertEqual(len(run.log), 1)
        self.assertEqual(run.left(), run.level.budget - 1)

    def test_a_short_input_does_not_run(self):
        run = M.Run(M.deal(1, seed=1))
        M.act(run, M.SYM)
        M.act(run, M.RUN)
        self.assertEqual(run.log, [])

    def test_a_wrong_answer_fails_and_says_the_rule(self):
        machine = M.deal(1, seed=1)
        run = M.Run(machine)
        M.act(run, M.TEST)
        q = run.question()
        truth = L.run(machine.rule, q, machine.level.k, ZERO)
        wrong = tuple(1 - v for v in truth)
        for v in wrong:
            M.act(run, M.SYM + v)
        M.act(run, M.RUN)
        self.assertFalse(run.result[0])
        self.assertIn(M.describe(machine.rule), run.result[1])

    def test_the_adversarial_test_asks_about_the_exception(self):
        machine = M.deal(28, seed=2)
        self.assertTrue(any(len(set(t)) == 1 for t in machine.tests))

    def test_a_hidden_language_answer_can_be_shorter(self):
        machine = M.deal(16, seed=2)
        run = M.Run(machine)
        M.act(run, M.TEST)
        self.assertLessEqual(run.want(), machine.level.length)


@needs_ui
def board_for(rule, level):
    """The blocks that write ``rule`` on the board, or None."""
    by = {(b.kind, b.value): b for b in M.blocks(level)}
    out = []

    def put(n):
        if isinstance(n, L.Prim):
            n = L.Seq((n,))
        if isinstance(n, L.Seq):
            if len(n.parts) == 1:
                out.append(by['rule', n.parts[0]])
                return
            out.append(by['form', 'then%d' % len(n.parts)])
            for p in n.parts:
                put(p)
        elif isinstance(n, L.If):
            out.append(by['form', 'if'])
            out.append(by['test', n.test])
            put(n.then)
            put(n.other)
        elif isinstance(n, L.Alt):
            out.append(by['form', 'alt'])
            put(n.even)
            put(n.odd)
        elif isinstance(n, L.Except):
            out.append(by['form', 'except'])
            put(n.usual)
            put(n.odd)
        elif isinstance(n, L.Meta):
            out.append(by['form', 'meta%d' % len(n.branches)])
            out.append(by['test', n.trigger])
            for b in n.branches:
                put(b)
        else:
            raise KeyError(n)
    try:
        put(rule)
    except KeyError:
        return None
    return out


def write(run, blocks, keys=False):
    """Put blocks on the board through the menu, by key or by index."""
    for b in blocks:
        i = run.menu().index(b)
        if keys:
            while run.cursor != i:
                M.act(run, M.NEXT_BLOCK)
            M.act(run, M.ADD_BLOCK)
        else:
            run.add_block(i)


class TheHigherTests(unittest.TestCase):

    def test_from_nested_up_the_last_question_is_longer(self):
        for rung in (25, 28, 40):
            m = M.deal(rung, seed=1)
            self.assertEqual(len(m.tests[-1]), m.level.length + 2, rung)
            self.assertTrue(all(len(q) == m.level.length
                                for q in m.tests[:-1]))
        m = M.deal(22, seed=1)
        self.assertTrue(all(len(q) == m.level.length for q in m.tests))


    def kinds(self, rung, kind, want=2):
        import random
        draw, out = random.Random(11), []
        for _i in range(400):
            m = M.build(M.grade(rung), random.Random(draw.getrandbits(32)))
            if m is not None and m.kind == kind:
                out.append(m)
                if len(out) >= want:
                    break
        return out

    def test_two_machine_rounds_are_passed_and_judged(self):
        found = self.kinds(10, 'twins', 4)
        self.assertTrue(found)
        for m in found:
            self.assertTrue(M.play(m)[0], L.code(m.rule))
            # an answer of "the same" is right only when it is
            run = M.Run(m)
            run.twins_q, run.testing = True, True
            run.submit()
            self.assertEqual(run.result[0],
                             M.same_machine(m.rule, m.other, m.level))

    def test_a_disguise_behaves_alike_but_is_written_apart(self):
        import random
        m = M.deal(25, seed=3)
        same = M._disguise(m.rule, m.level, random.Random(1))
        if same is None:
            self.skipTest('nothing to rewrite')
        self.assertNotEqual(L.code(same), L.code(m.rule))
        self.assertTrue(M.same_machine(same, m.rule, m.level))

    def test_invert_rounds_ask_for_the_input(self):
        found = self.kinds(19, 'invert', 2)
        self.assertTrue(found)
        for m in found:
            self.assertTrue(M.play(m)[0])
            run = M.Run(m)
            run.begin_test()
            y = run.question()
            x = M.preimages(m.rule, m.level)[y]
            run.entry = list(x)
            run.go()
            self.assertTrue(run.answers[0][2])
            self.assertEqual(run.answers[0][:2], (x, y))


class TheBoard(unittest.TestCase):

    def test_any_board_checks_and_submits_without_harm(self):
        import random
        draw = random.Random(0)
        for rung in (10, 16, 22, 28, 40):
            m = M.deal(rung, seed=1)
            for _t in range(40):
                run = M.Run(m)
                for _b in range(draw.randrange(1, 14)):
                    menu = run.menu()
                    if not menu:
                        break
                    run.add_block(draw.randrange(len(menu)))
                run.check()
                run.submit()


    def test_the_menu_offers_only_what_fits(self):
        run = M.Run(M.deal(7, seed=1))
        self.assertTrue(all(b.kind in ('form', 'rule')
                            for b in run.menu()))
        run.add_block([b.value for b in run.menu()].index('if'))
        self.assertTrue(all(b.kind == 'test' for b in run.menu()))
        self.assertIsNone(run.hypothesis())
        run.undo_block()
        self.assertEqual(run.board, [])

    def test_every_truth_can_be_written_and_submitted(self):
        for rung in (10, 13, 19, 22, 25, 28, 40):
            m = M.deal(rung, seed=2)
            blocks = board_for(m.rule, m.level)
            if blocks is None:
                continue
            run = M.Run(m)
            write(run, blocks, keys=True)
            self.assertTrue(M.same_machine(run.hypothesis(), m.rule,
                                           m.level), rung)
            M.act(run, M.SUBMIT)
            self.assertTrue(run.result[0], rung)

    def test_a_wrong_rule_submitted_loses(self):
        m = M.deal(10, seed=3)
        run = M.Run(m)
        rule = next(b for b in run.menu() if b.kind == 'rule')
        run.add_block(run.menu().index(rule))
        if M.same_machine(run.hypothesis(), m.rule, m.level):
            self.skipTest('the first block is the machine')
        run.submit()
        self.assertFalse(run.result[0])

    def test_below_composition_submit_only_explains(self):
        m = M.deal(4, seed=1)
        run = M.Run(m)
        write(run, board_for(m.rule, m.level) or [])
        run.submit()
        self.assertIsNone(run.result)

    def test_check_marks_every_row(self):
        m = M.deal(7, seed=4)
        run = M.Run(m)
        for x in m.plan[:3]:
            run.entry = list(x)
            run.go()
        write(run, board_for(m.rule, m.level))
        M.act(run, M.CHECK)
        self.assertEqual(len(run.checked), len(run.log))
        self.assertTrue(all(run.checked.values()))


class TheNotebook(unittest.TestCase):

    def run_some(self, n=3, rung=7):
        m = M.deal(rung, seed=5)
        run = M.Run(m)
        for x in m.plan[:n]:
            run.entry = list(x)
            run.go()
        return run

    def test_predicting_takes_the_guess_after_the_input(self):
        m = M.deal(4, seed=6)
        run = M.Run(m)
        M.act(run, M.PREDICT)
        x = m.plan[0]
        run.entry = list(x)
        run.go()
        self.assertEqual(run.log, [])
        self.assertEqual(run.pending, x)
        truth = L.run(m.rule, x, m.level.k, L.START)
        run.entry = list(truth)
        run.go()
        self.assertEqual(run.log, [(x, truth)])
        self.assertEqual(run.predictions[0], truth)

    def test_marks_sorting_and_numbers(self):
        run = self.run_some()
        M.act(run, M.MARK)
        self.assertIn(('run', 2), run.marks)
        M.act(run, M.SORT)
        xs = [r[2] for r in run.rows() if r[0] == 'run']
        self.assertEqual(xs, sorted(xs))
        on = run.numbers
        M.act(run, M.NUMBERS)
        self.assertNotEqual(on, run.numbers)

    def test_scrolling_stays_in_range(self):
        run = self.run_some(n=6, rung=25)
        for _i in range(20):
            M.act(run, M.SCROLL_UP)
        self.assertEqual(run.scroll, max(0, len(run.rows()) - M.NOTE_ROWS))
        for _i in range(20):
            M.act(run, M.SCROLL_DOWN)
        self.assertEqual(run.scroll, 0)

    def test_the_end_screen_counts_bits(self):
        run = self.run_some(n=3)
        info = M.summary(run)
        self.assertEqual(len(info['bits']), 3)
        self.assertTrue(all(b >= 0 for b in info['bits']))
        self.assertGreater(sum(info['bits']), 0)
        self.assertEqual(info['reference'], run.machine.plan)


class ThePointer(unittest.TestCase):
    """Mouse play: every control has a place to click."""

    def click(self, run, x, y):
        run.hand.x, run.hand.y = x, y
        M.act(run, M.H.PRESS)
        M.act(run, M.H.RELEASE)

    def test_a_round_by_mouse(self):
        m = M.deal(4, seed=7)
        run = M.Run(m)
        for x in m.plan:
            for v in x:
                self.click(run, M.pal_x(v), M.PAL_Y)
            self.click(run, M.RUN_X, M.PAL_Y)
        self.assertEqual(len(run.log), len(m.plan))
        self.click(run, M.TEST_X, M.PAL_Y)
        self.assertTrue(run.testing)
        self.click(run, M.MENU_X + 40, M.menu_y(0))
        self.assertEqual(len(run.board), 1)
        self.click(run, *M.BOARD_BUTTONS['undo'])
        self.assertEqual(run.board, [])
        self.click(run, *M.PREDICT_AT)
        self.assertFalse(run.predicting)        # not during the test
        st = L.START
        for q in m.tests:
            y = L.run(m.rule, q, m.level.k, st)
            st = L.advance(m.rule, st, q, y, m.level.k)
            for v in y:
                self.click(run, M.pal_x(v), M.PAL_Y)
            self.click(run, M.RUN_X, M.PAL_Y)
        self.assertTrue(run.result[0])


class TheMemory(unittest.TestCase):

    def test_the_library_remembers_where_each_operator_was_met(self):
        rule = L.parse('seq(rot(2),shift(1))')
        lib = M.learn({}, rule, 10)
        self.assertEqual(lib['operators'], {'rot': 10, 'shift': 10})
        lib = M.learn(lib, L.parse('if(pal,rot(1),stride(3))'), 31)
        self.assertEqual(lib['operators']['rot'], 10)
        self.assertEqual(lib['operators']['stride'], 31)
        self.assertEqual(M.remembered(lib, L.parse('seq(rev,rot(1))'), 40),
                         [('rot', 10)])
        self.assertEqual(M.remembered(lib, rule, 10), [])

    def test_the_held_out_family_waits_until_rung_30(self):
        for rung in range(1, M.HELD_OUT_FROM, 3):
            fam = M.family(M.grade(rung))
            self.assertFalse(any('stride' in L.code(r) for r in fam), rung)
        self.assertTrue(any('stride' in L.code(r) for r in
                            M.truths(M.grade(M.HELD_OUT_FROM))))

    def test_the_notebook_exports_as_numbers(self):
        m = M.deal(7, seed=2)
        run = M.Run(m)
        for x in m.plan[:2]:
            run.entry = list(x)
            run.go()
        text = M.notebook_text(run)
        self.assertEqual(len(text.strip().split('\n')), 4)
        self.assertIn(' '.join(map(str, m.plan[0])), text)
        self.assertNotIn(L.code(m.rule), text)     # not before the end


class TheScore(unittest.TestCase):

    def test_a_round_is_measured(self):
        m = M.deal(10, seed=4)
        run = M.Run(m)
        while run.result is None:
            ports = M.autopilot(run)
            if ports:
                M.act(run, ports[0])
            run.step(1 / 60.0)
        got = M.metrics(run)
        self.assertEqual(set(got), set(M.METRIC_FIELDS))
        self.assertTrue(got['won'])
        self.assertEqual(got['accuracy'], 1.0)
        self.assertEqual(got['experiments'], got['reference_experiments'])
        self.assertEqual(len(got['bits']), got['experiments'])

    def test_the_benchmark_is_fixed(self):
        import importlib.util
        import os
        path = os.path.join(os.path.dirname(__file__), '..', 'tools',
                            'score_cipher.py')
        spec = importlib.util.spec_from_file_location('score_cipher', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.benchmark(2), mod.benchmark(2))
        self.assertIn(M.HELD_OUT_FROM, {r for r, _s in mod.benchmark(1)})


class TheSound(unittest.TestCase):

    def test_the_machine_hums_while_it_answers(self):
        m = M.deal(4, seed=2)
        run = M.Run(m)
        run.entry = list(m.plan[0])
        run.go()
        voices = [n.voice for n in run.notes]
        self.assertIn(M.HUM, voices)
        self.assertGreaterEqual(voices.count(M.TONE),
                                len(run.log[0][1]))

    def test_the_end_rings_for_telling_experiments(self):
        m = M.deal(7, seed=2)
        run = M.Run(m)
        before = len(run.notes)
        M.end_tones(run, [3.0, 0.0, 1.2])
        new = run.notes[before:]
        self.assertEqual([n.voice for n in new],
                         [M.CHIME, M.BUZZ, M.CHIME])
        self.assertTrue(all(n.t > run.t for n in new))


class TheKeys(unittest.TestCase):

    @needs_ui
    def test_every_control_has_a_key(self):
        from neural_workshop.ui.cipherabyss import CipherAbyss
        keyed = set(CipherAbyss.EVENT_KEYS.values())
        self.assertEqual(set(range(M.SYM, M.PORTS)) - keyed, set())


class TheBoundary(unittest.TestCase):

    def test_the_reference_passes_and_idling_fails(self):
        pilot = queued(M.autopilot, lambda t: t.run)
        self.assertEqual(drive('cipher_abyss', 4, pilot, seed=1,
                               steps=12000), [1.0])
        self.assertEqual(drive('cipher_abyss', 1, lambda t: None, seed=1,
                               steps=40000), [-1.0])

    def test_the_agent_hears_it(self):
        self.assertGreater(heard('cipher_abyss', M), 0)


if __name__ == '__main__':
    unittest.main()
