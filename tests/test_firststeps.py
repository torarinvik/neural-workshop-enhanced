#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The first-steps families: short walks, twins, looking back, what the
ports do and rule discovery. The held-out tasks are tested in
test_heldout."""
from __future__ import annotations

import os
import random
import unittest

from neural_workshop import lookback, ministeps, ruleguess, twins
from nwenv import catalog

try:
    from uisupport import needs_ui
    from spatialsupport import drive
except Exception:                                      # pragma: no cover
    needs_ui = unittest.skip('no UI')
    drive = None

NEW = [task for family in catalog.FAMILIES.values() for task in family]
OPEN = [task for task in NEW if task not in catalog.HELD_OUT]
#: Families whose wait is closed to presses: a press before the question
#: ends the trial unpaid, or must be the wait's job, so a press at every
#: step is never paid there, by design.
CLOSED_WAIT = ('hands off', 'uneven wait', 'several kept')


class ShortWalks(unittest.TestCase):
    def test_rung_n_is_n_presses_from_done(self):
        for kind in ministeps.MAKERS:
            top = 8 if kind == 'tiles' else 14
            for rung in range(1, top + 1):
                for seed in range(6):
                    p = ministeps.deal(kind, rung, random.Random(seed))
                    self.assertEqual(p.far, rung, (kind, rung))
                    self.assertEqual(len(ministeps.solve(p)), rung)

    def test_the_way_through_passes(self):
        for kind in ministeps.MAKERS:
            p = ministeps.deal(kind, 6, random.Random(3))
            walk = ministeps.Walk(p)
            for port in ministeps.solve(p):
                self.assertIsNone(walk.result)
                self.assertTrue(walk.press(port))
            self.assertEqual(walk.result[0], True, kind)

    def test_a_press_that_gets_no_nearer_ends_the_trial(self):
        for kind in ministeps.MAKERS:
            for seed in range(20):
                p = ministeps.deal(kind, 4, random.Random(seed))
                bad = [port for port in range(p.ports)
                       if port not in ministeps.good(p, p.start)]
                self.assertTrue(bad, kind)
                walk = ministeps.Walk(p)
                self.assertFalse(walk.press(bad[0]))
                self.assertEqual(walk.result[0], False, kind)

    def test_trials_do_not_repeat(self):
        for kind in ministeps.MAKERS:
            seen = {repr((p.start, sorted(map(repr, p.data.items())), p.look))
                    for p in (ministeps.deal(kind, 3, random.Random(s))
                              for s in range(30))}
            self.assertGreater(len(seen), 20, kind)

    def test_the_shuffled_ports_move_the_same_four_ways(self):
        for order in ((0, 1, 2, 3), (3, 1, 0, 2)):
            p = ministeps.deal('walk', 3, random.Random(1), order=order)
            ways = {ministeps.STEPS[order[port]] for port in range(4)}
            self.assertEqual(ways, set(ministeps.STEPS))
            self.assertEqual(len(ministeps.solve(p)), 3)


class Twins(unittest.TestCase):
    def test_each_rule_has_two_looks_and_one_ladder(self):
        for rule in twins.RULES:
            if rule == 'odd':
                continue                      # its look b is held out
            for rung in (1, 2, 5, 9):
                for seed in range(40):
                    a = twins.deal(rule, 'a', rung, random.Random(seed))
                    b = twins.deal(rule, 'b', rung, random.Random(seed))
                    self.assertEqual(len(a.choices), len(b.choices))
                    self.assertTrue(0 <= a.answer < len(a.choices))
                    self.assertTrue(0 <= b.answer < len(b.choices))

    def test_a_rung_adds_one(self):
        for rule in twins.RULES:
            sizes = [twins.size(rule, r) for r in range(1, 9)]
            self.assertEqual([b - a for a, b in zip(sizes, sizes[1:])],
                             [1] * 7, rule)

    def test_the_ports_are_in_another_order(self):
        for rule in ('same', 'inside'):
            a = twins.deal(rule, 'a', 3, random.Random(0))
            b = twins.deal(rule, 'b', 3, random.Random(0))
            self.assertEqual(a.choices, b.choices[::-1])

    def test_the_two_looks_share_no_colour(self):
        self.assertFalse(set(twins.HUES_A) & set(twins.HUES_B))

    def test_the_pattern_really_has_its_period(self):
        for rung in range(1, 9):
            p = twins.deal('next', 'a', rung, random.Random(rung))
            seq, period = p.data['seq'], p.data['period']
            self.assertEqual(period, rung + 1)
            self.assertGreaterEqual(len(seq), 2 * period)
            self.assertEqual(seq[period:], seq[:len(seq) - period])
            nxt = seq[len(seq) - period]
            self.assertEqual(p.data['cards'][p.answer], nxt)

    def test_the_catalogue_records_the_pairs(self):
        self.assertEqual(len(catalog.TWINS), 18)
        for one, two in catalog.TWINS:
            self.assertEqual(catalog.twin_of(one), two)
            self.assertEqual(catalog.twin_of(two), one)
            self.assertIn(one, catalog.BY_ID)
            self.assertIn(two, catalog.BY_ID)
        self.assertIsNone(catalog.twin_of('short_maze'))


class LookingBack(unittest.TestCase):
    def test_the_answer_is_k_frames_back(self):
        for kind in lookback.KINDS:
            for rung in range(1, 10):
                p = lookback.deal(kind, rung, random.Random(rung))
                self.assertEqual(p.back, rung)
                asked = int(round(p.open_at / lookback.FRAME))
                self.assertEqual(asked - (1 if kind == 'cue' else 0), rung)
                if kind == 'shape':
                    self.assertEqual(p.data['cards'][p.answer], p.frames[0])
                else:
                    self.assertEqual(p.answer, p.frames[0])

    def test_now_is_never_the_answer(self):
        for kind in ('shape', 'sound'):
            for seed in range(60):
                p = lookback.deal(kind, 3, random.Random(seed))
                self.assertNotEqual(p.frames[-1], p.frames[0])

    def test_the_sound_task_makes_a_tone_a_frame(self):
        p = lookback.deal('sound', 4, random.Random(2))
        self.assertEqual(len(p.notes), 5)
        self.assertEqual([round(n.t / lookback.FRAME) for n in p.notes],
                         [0, 1, 2, 3, 4])


class RuleDiscovery(unittest.TestCase):
    def test_two_candidates_then_one_more_a_rung(self):
        self.assertEqual([len(ruleguess.candidates(r)) for r in range(1, 9)],
                         list(range(2, 10)))

    def test_every_rule_points_at_exactly_one_card(self):
        for seed in range(100):
            p = ruleguess.deal('red', 10, random.Random(seed))
            for rule in ruleguess.RULES:
                self.assertIn(ruleguess.pick(rule, p.things), (0, 1, 2))
            self.assertEqual(sum(t.hollow for t in p.things), 1)
            self.assertEqual(sum(t.dotted for t in p.things), 1)

    def test_presses_rule_candidates_out(self):
        rng = random.Random(5)
        rule = ruleguess.draw_rule(6, rng)
        log = []
        for _trial in range(30):
            p = ruleguess.deal(rule, 6, rng)
            port = rng.randrange(3)
            log.append((p, port, port == p.answer))
        self.assertEqual(ruleguess.left(log, 6), [rule])


def _right(task):
    if hasattr(task, 'walk') and task.walk is not None:
        if hasattr(task.walk, 'good'):
            return task.walk.good()[0]
        return ministeps.good(task.puzzle, task.walk.state)[0]
    run = getattr(task, 'run', None)
    if run is not None and not run.open:
        return _job(task)
    return task.puzzle.answer


def _wrong(task):
    if hasattr(task, 'walk') and task.walk is not None:
        ok = (task.walk.good() if hasattr(task.walk, 'good')
              else ministeps.good(task.puzzle, task.walk.state))
        return next(p for p in range(task.puzzle.ports) if p not in ok)
    run = getattr(task, 'run', None)
    if run is not None and not run.open:
        return _job(task)
    return (task.puzzle.answer + 1) % len(task.puzzle.choices)


def _job(task):
    """The port a wait's job asks for now, once; else no press."""
    run = task.run
    if not hasattr(run, 'job'):
        return None
    j = run.job()
    if j is None or j in run.done:
        return None
    look = task.puzzle.data['look']
    place = task.puzzle.data['jobs'][j][1]
    return place if look == 0 else 3 - place


@needs_ui
class TheBoundary(unittest.TestCase):
    def test_right_is_green_and_wrong_is_red(self):
        for task_id in OPEN:
            for rung in (1, 8):
                self.assertEqual(drive(task_id, rung, _right, seed=3,
                                       steps=3000), [1.0], (task_id, rung))
                self.assertEqual(drive(task_id, rung, _wrong, seed=3,
                                       steps=3000), [-1.0], (task_id, rung))

    def test_doing_nothing_is_never_paid(self):
        for task_id in NEW:
            self.assertNotEqual(drive(task_id, 1, lambda task: None, seed=1,
                                      steps=900), [1.0], task_id)

    def test_a_press_before_the_question_is_ignored(self):
        early = {'n': 0}

        def policy(task):
            if not task.run.open:
                early['n'] += 1
                return (task.puzzle.answer + 1) % len(task.puzzle.choices)
            return task.puzzle.answer
        self.assertEqual(drive('shape_back', 3, policy, seed=2, steps=3000),
                         [1.0])
        self.assertGreater(early['n'], 10)

    def test_random_presses_are_paid_at_rung_one_within_twenty_trials(self):
        for task_id in NEW:
            if catalog.family_of(task_id) in CLOSED_WAIT:
                continue
            env = catalog.env_class(task_id)(seed=1, rung=1, trials=20,
                                             adaptive=False)
            rng = random.Random(11)
            scalars = []
            try:
                for _step in range(60000):
                    _obs, events, done = env.step(rng.randrange(
                        env.n_actions))
                    scalars += [e['scalar'] for e in events
                                if e.get('type') == 'outcome']
                    if done:
                        break
            finally:
                env.close()
            self.assertEqual(len(scalars), 20, task_id)
            self.assertGreaterEqual(sum(1 for s in scalars if s > 0), 1,
                                    task_id)

    def test_the_shuffle_holds_for_a_run_and_changes_between_runs(self):
        orders = set()
        for seed in range(8):
            env = catalog.env_class('marker_walk_shuffled')(
                seed=seed, rung=1, trials=3, adaptive=False)
            try:
                first = env.task.order
                self.assertEqual(env.task.puzzle.data['order'], first)
                for _step in range(40):
                    env.step(ministeps.good(env.task.puzzle,
                                            env.task.walk.state)[0]
                             if env.task.phase == 'playing' else None)
                    if env.task.phase == 'playing':
                        self.assertEqual(env.task.puzzle.data['order'],
                                         first)
                orders.add(first)
            finally:
                env.close()
        self.assertGreater(len(orders), 2)

    def test_the_rule_holds_for_a_run(self):
        env = catalog.env_class('which_rule')(seed=4, rung=5, trials=12,
                                              adaptive=True)
        try:
            rule, greens = env.task.rule, 0
            for _step in range(200):
                task = env.task
                port = (ruleguess.pick(rule, task.puzzle.things)
                        if task.phase == 'playing' else None)
                _obs, events, done = env.step(port)
                greens += sum(1 for e in events
                              if e.get('type') == 'outcome'
                              and e['scalar'] > 0)
                self.assertEqual(env.task.rule, rule)
                if done:
                    break
            self.assertEqual(greens, 12)
        finally:
            env.close()

    def paid(self, **how):
        env = catalog.env_class('short_maze_steps')(
            seed=2, rung=5, trials=1, adaptive=False, **how)
        scalars = []
        try:
            for _step in range(60):
                task = env.task
                port = (ministeps.good(task.puzzle, task.walk.state)[0]
                        if task.phase == 'playing' else None)
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done:
                    break
        finally:
            env.close()
        return scalars

    def test_each_right_step_is_paid_only_when_paying_by_the_press(self):
        self.assertEqual(self.paid(), [1.0])
        dense = [s for s in self.paid(neutral_outcomes=True) if s]
        self.assertEqual(dense, [1.0] * 5)


class TheCatalogue(unittest.TestCase):
    def test_every_new_task_has_a_row(self):
        self.assertEqual(len(NEW), 58)
        for task_id in NEW:
            self.assertIn(task_id, catalog.BY_ID)

    def test_each_held_out_task_is_from_a_family_of_its_own(self):
        # Three drawn with the first families, and one from each of
        # three of the families added since.
        self.assertGreaterEqual(len(catalog.HELD_OUT), 3)
        families = {name for name, tasks in catalog.FAMILIES.items()
                    for task in tasks if task in catalog.HELD_OUT}
        self.assertEqual(len(families), len(catalog.HELD_OUT))
        self.assertTrue(all(catalog.held_out(t) for t in catalog.HELD_OUT))
        self.assertFalse(catalog.held_out('maze'))

    def test_the_docs_do_not_describe_the_held_out_tasks(self):
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.join(here, '..')
        docs = os.path.join(root, 'docs')
        paths = [os.path.join(root, 'README.md'),
                 os.path.join(root, 'ADDING_A_TASK.md')] + [
            os.path.join(docs, name) for name in sorted(os.listdir(docs))
            if name.endswith('.md')]
        text = ''
        for path in paths:
            with open(path, encoding='utf-8') as handle:
                text += handle.read()
        for task_id in catalog.HELD_OUT:
            label = catalog.BY_ID[task_id].label
            # Another task's longer title may begin with this one's.
            rest = text
            for row in catalog.CATALOG:
                if row.label != label and label in row.label:
                    rest = rest.replace(row.label, '')
            self.assertNotIn(label, rest, task_id)
            self.assertNotIn(task_id, text)


if __name__ == '__main__':
    unittest.main()
