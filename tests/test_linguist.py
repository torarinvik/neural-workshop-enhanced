#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The Linguist: saying, learning, the deal, the answers, the page, the
boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import linguist as M

RUNGS = (1, 3, 4, 7, 10, 13, 16, 19, 22, 25, 31)
WORDS = {('s', 0): (0, 1), ('s', 1): (2, 3), ('s', 2): (4, 5),
         ('c', 0): (1, 0), ('v', 0): (3, 2), ('v', 1): (5, 4),
         'rel': (6, 6), 'pl': (7,), 'big': (8,), 'agr': (9,), 'case': (6,)}
A, B, C = M.Thing(0), M.Thing(1), M.Thing(2)


def say(h, scene, order=None):
    return M.realise(M.template(h, scene, order), WORDS)


class Saying(unittest.TestCase):

    def test_word_order(self):
        scene = M.Scene((A, B), ((0, 0, 1),))
        self.assertEqual(say(M.Tongue('SVO'), scene),
                         ((0, 1), (3, 2), (2, 3)))
        self.assertEqual(say(M.Tongue('OVS'), scene),
                         ((2, 3), (3, 2), (0, 1)))

    def test_the_describing_word_goes_before_or_after(self):
        red = M.Scene((A._replace(colour=0),))
        self.assertEqual(say(M.Tongue(adj=0), red), ((1, 0), (0, 1)))
        self.assertEqual(say(M.Tongue(adj=1), red), ((0, 1), (1, 0)))

    def test_more_than_one_and_big(self):
        many = M.Scene((A._replace(plural=True, big=True),))
        self.assertEqual(say(M.Tongue(pl='suf', big='suf'), many),
                         ((0, 1, 8, 7),))
        self.assertEqual(say(M.Tongue(pl='pre', big='pre'), many),
                         ((7, 8, 0, 1),))
        self.assertEqual(say(M.Tongue(pl='rl', big='pre'), many),
                         ((8, 0, 1, 1),))
        self.assertEqual(say(M.Tongue(pl='rf'), many._replace(
            things=(A._replace(plural=True),))), ((0, 0, 1),))

    def test_agreement(self):
        scene = M.Scene((A._replace(plural=True), B), ((0, 0, 1),))
        with_doer = M.Tongue(agr=('S', 'suf'))
        with_done = M.Tongue(agr=('O', 'suf'))
        self.assertEqual(say(with_doer, scene)[1], (3, 2, 9))
        self.assertEqual(say(with_done, scene)[1], (3, 2))
        many = M.Scene((A._replace(colour=0, plural=True),))
        self.assertEqual(say(M.Tongue(adjagr=True), many),
                         ((1, 0, 7), (0, 1, 7)))

    def test_marked_roles_leave_the_order_free(self):
        scene = M.Scene((A, B), ((0, 0, 1),))
        h = M.Tongue(case=('O', 'suf'))
        said = M.says(h, WORDS, scene)
        self.assertEqual(len(said), 6)
        for sentence in said:
            self.assertIn((2, 3, 6), sentence)       # the done-to, marked
            self.assertIn((0, 1), sentence)

    def test_a_clause_inside_a_clause(self):
        scene = M.Scene((A, B, C), ((0, 0, 1), (1, 1, 2)))
        after = say(M.Tongue('SVO'), scene)
        self.assertEqual(after, ((0, 1), (3, 2), (2, 3), (6, 6), (5, 4),
                                 (4, 5)))
        before = say(M.Tongue('SVO', rel=1, relorder=1), scene)
        self.assertEqual(before, ((0, 1), (3, 2), (6, 6), (4, 5), (5, 4),
                                  (2, 3)))


class Learning(unittest.TestCase):

    def test_examples_whittle_the_family_down(self):
        level = M.grade(8)
        truth = M.Tongue('SOV', adj=1)
        states = [(h, {}) for h in M.family(level)]
        self.assertEqual(len(states), 12)
        scene = M.Scene((A, B), ((0, 0, 1),))
        states = M.learn(states, scene, say(truth, scene))
        self.assertEqual(len(states), 12)        # any order still reads it
        for thing in (A, B):
            alone = M.Scene((thing,))
            states = M.learn(states, alone, say(truth, alone))
        self.assertEqual({h.order for h, _w in states}, {'SOV'})
        red = M.Scene((A._replace(colour=0),))
        states = M.learn(states, red, say(truth, red))
        self.assertEqual([h for h, _w in states], [truth])
        self.assertEqual(states[0][1][('c', 0)], (1, 0))

    def test_a_reading_that_cannot_be_is_dropped(self):
        self.assertIsNone(M._read(M.template(M.Tongue(), M.Scene((A,))),
                                  ((0, 1), (2, 3)), {}))
        self.assertIsNone(M._read(M.template(M.Tongue(), M.Scene((A,))),
                                  ((0, 1),), {('s', 1): (0, 1)}))

    def test_the_family_grows_with_the_rung(self):
        sizes = [len(M.family(M.grade(r))) for r in (4, 7, 10, 13, 16, 22)]
        self.assertEqual(sizes, sorted(sizes))
        self.assertEqual(sizes[0], 2)
        self.assertGreater(sizes[-1], 2000)


class TheDeal(unittest.TestCase):

    def test_the_solver_agrees_with_every_deal(self):
        for rung in RUNGS:
            for seed in range(12 if rung < 22 else 5):
                p = M.deal(rung, seed=seed)
                found = M.solve(p)
                if p.kind == 'build':
                    self.assertEqual(found[-1], M.DONE)
                    self.assertTrue(M.check(p, found[:-1]), (rung, seed))
                else:
                    self.assertEqual(found, p.answer, (rung, seed))

    def test_every_example_is_needed(self):
        for rung in (7, 13, 19):
            for seed in range(6):
                p = M.deal(rung, seed=seed)
                for k in range(len(p.examples)):
                    fewer = p._replace(examples=p.examples[:k]
                                       + p.examples[k + 1:])
                    found = M.solve(fewer)
                    if p.kind == 'build':
                        self.assertIsNone(found, (rung, seed, k))
                    else:
                        self.assertNotEqual(found, p.answer, (rung, seed, k))

    def test_the_question_is_not_among_the_examples(self):
        for rung in (4, 10, 19, 22):
            for seed in range(10):
                p = M.deal(rung, seed=seed)
                for scene, sentence in p.examples:
                    self.assertNotEqual(scene, p.scene)
                    self.assertNotEqual(sentence, p.truth)
                self.assertLessEqual(len(p.examples), 12)

    def test_the_ladder(self):
        self.assertEqual(M.grade(1).kinds, ('match',))
        self.assertNotIn('order', M.grade(4).has)
        self.assertIn('order', M.grade(7).has)
        self.assertIn('build', M.grade(10).kinds)
        self.assertIn('agr', M.grade(13).has)
        self.assertIn('twice', M.grade(16).has)
        self.assertIn('case', M.grade(19).has)
        self.assertEqual(M.grade(22).depth, 1)
        self.assertEqual(M.grade(25).depth, 2)
        self.assertGreater(M.grade(60).depth, 10)
        deep = M.deal(31, seed=1)
        self.assertEqual(len(deep.scene.deeds), M.grade(31).depth + 1)

    def test_a_seed_deals_the_same_trial_and_another_language(self):
        self.assertEqual(M.deal(14, seed=3), M.deal(14, seed=3))
        one, two = M.deal(14, seed=3), M.deal(14, seed=4)
        self.assertNotEqual(one.glyphs, two.glyphs)
        self.assertNotEqual(one.truth, two.truth)

    def test_letters_differ(self):
        for seed in range(20):
            p = M.deal(10, seed=seed)
            self.assertEqual(len(set(p.glyphs)), len(p.glyphs))


class TheAnswers(unittest.TestCase):

    def test_they_differ_and_the_right_one_is_anywhere(self):
        for rung in (2, 5, 8, 14):
            where = collections.Counter()
            n = 0
            for seed in range(300 if rung < 14 else 120):
                p = M.deal(rung, seed=seed)
                if p.kind == 'build':
                    continue
                n += 1
                self.assertEqual(len(set(p.options)), len(p.options))
                where[p.answer] += 1
            self.assertEqual(len(where), M.grade(rung).options, rung)
            self.assertLess(max(where.values()),
                            n / M.grade(rung).options * 1.6, rung)

    def test_only_right_sentences_build(self):
        for seed in range(40):
            p = M.deal(11, seed=seed)
            if p.kind != 'build':
                continue
            ports = M.solve(p)[:-1]
            self.assertTrue(M.check(p, ports))
            self.assertFalse(M.check(p, ports[:-1]))
            turned = tuple(reversed(p.truth))
            if turned not in p.valid:
                self.assertFalse(M.check(p, list(reversed(ports))))
            self.assertLessEqual(len(p.options), 10)
            for word in p.truth:
                self.assertIn(word, p.options)

    def test_matching_gets_closer(self):
        far = M.deal(1, seed=2)
        near = M.deal(3, seed=2)
        self.assertEqual(len(far.sentence[0]), 3)
        self.assertEqual(len(near.sentence[0]), 5)
        for option in near.options:
            if option != near.sentence:
                self.assertEqual(sorted(option[0]) == sorted(near.sentence[0])
                                 or sum(a != b for a, b in zip(
                                     option[0], near.sentence[0])) <= 2, True)


class ThePage(unittest.TestCase):

    def test_every_kind_draws_with_its_click_targets(self):
        seen = set()
        for rung in RUNGS:
            for seed in range(6):
                p = M.deal(rung, seed=seed)
                seen.add(p.kind)
                prims = M.scene(p)
                hits = [q[5] for q in prims if q[0] == 'hit']
                if p.kind == 'build':
                    self.assertEqual(hits, list(range(len(p.options)))
                                     + [M.UNDO, M.DONE])
                else:
                    self.assertEqual(hits, list(range(len(p.options))))
                for q in prims:
                    if q[0] == 'rect':
                        self.assertGreaterEqual(q[1], -1e-6)
                        self.assertLessEqual(q[1] + q[3], 1.6 + 1e-6)
                        self.assertGreaterEqual(q[2], -1e-6)
                        self.assertLessEqual(q[2] + q[4], 1.0 + 1e-6)
                M.scene(p, (0,), True)
        self.assertEqual(seen, {'match', 'describe', 'read', 'build'})


def pilot(task):
    found = M.solve(task.puzzle)
    return found if isinstance(found, list) else [found]


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_solver_passes_every_kind_through_the_ports(self):
        for rung, seed in ((2, 1), (5, 1), (8, 2), (11, 1), (11, 2),
                           (11, 3), (11, 5), (20, 1), (23, 1)):
            self.assertEqual(
                drive('the_linguist', rung, queued(pilot, lambda t: t),
                      seed=seed), [1.0], (rung, seed))

    def test_a_wrong_answer_fails_and_idle_is_never_paid(self):
        def wrong(task):
            p = task.puzzle
            if p.kind != 'build':
                return (p.answer + 1) % len(p.options)
            if task.taken:
                return M.DONE                # one word is never the whole
            return 0
        for rung, seed in ((2, 1), (5, 1), (11, 1), (11, 2), (11, 3)):
            self.assertEqual(drive('the_linguist', rung, wrong, seed=seed),
                             [-1.0], (rung, seed))
        self.assertEqual(drive('the_linguist', 5, lambda task: None, seed=1,
                               steps=200), [])

    def test_building_takes_tiles_and_takes_them_back(self):
        from neural_workshop.ui.linguist import Linguist
        from uisupport import close_overlays, reset_window
        close_overlays()
        task = Linguist()
        try:
            task.rng = random.Random(1)
            task.start_rung = 11
            task.total_trials = 40
            task.adaptive = False
            task.start_run()
            for _k in range(40):
                if task.puzzle.kind == 'build':
                    break
                task.choose(task.puzzle.answer)
                task.feedback_until = 0.0
                task.update(0.0)
            self.assertEqual(task.puzzle.kind, 'build')
            task.on_draw()
            task.choose(0)
            task.choose(0)                       # a tile is taken once
            task.choose(1)
            self.assertEqual(task.taken, [0, 1])
            task.choose(M.UNDO)
            self.assertEqual(task.taken, [0])
            task.choose(M.UNDO)
            task.choose(M.DONE)                  # nothing said: not judged
            self.assertEqual(task.phase, 'playing')
            for port in M.solve(task.puzzle):
                task.choose(port)
            self.assertEqual(task.phase, 'judged')
            self.assertTrue(task.results[-1][1])
        finally:
            task.close()
            close_overlays()
            reset_window()


if __name__ == '__main__':
    unittest.main()
