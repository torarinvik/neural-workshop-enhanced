#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Held-out tasks.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import ast
import importlib
import os
import random
import unittest
from collections import deque

from cuesupport import job_now
from memorysupport import drive as frame_drive

from neural_workshop import (busybeads, carried, firstcome, framed,
                             inwindow, keydoor, ministeps, oddstripe,
                             leverlatch, ownpress, rollcall, roundagain,
                             standingorder, twins, waitandsee)
from nwenv import catalog

try:
    from uisupport import needs_ui
    from spatialsupport import drive
except Exception:                                      # pragma: no cover
    needs_ui = unittest.skip('no UI')
    drive = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TURNS = {0: (-1, 0), 1: (1, 0), 2: (0, -1), 3: (0, 1),
         4: (-1, -1), 5: (-1, 1), 6: (1, -1), 7: (1, 1)}
AFTER = {0: 2, 2: 3, 3: 1, 1: 0}


def _path(module):
    return os.path.join(ROOT, *module.split('.')) + '.py'


def _tree(module):
    with open(_path(module), encoding='utf-8') as f:
        return ast.parse(f.read())


class TheModules(unittest.TestCase):

    def test_each_held_out_task_lives_only_in_its_own_modules(self):
        for task_id in catalog.HELD_OUT:
            row = catalog.BY_ID[task_id]
            self.assertIn(row.env_module, catalog.HELD_OUT_MODULES)
            self.assertIn(row.ui_module, catalog.HELD_OUT_MODULES)
        for module in catalog.HELD_OUT_MODULES:
            self.assertTrue(os.path.exists(_path(module)), module)
            importlib.import_module(module)

    def test_no_open_module_names_a_held_out_class(self):
        names = {catalog.BY_ID[t].env_class for t in catalog.HELD_OUT} | \
                {catalog.BY_ID[t].ui_class for t in catalog.HELD_OUT}
        for task_id, row in catalog.BY_ID.items():
            if task_id in catalog.HELD_OUT:
                continue
            for module in (row.env_module, row.ui_module):
                if module in catalog.HELD_OUT_MODULES:
                    self.fail(module)
                tree = _tree(module)
                defined = {n.name for n in ast.walk(tree)
                           if isinstance(n, ast.ClassDef)}
                self.assertFalse(defined & names, module)

    def test_held_out_docstrings_are_titles(self):
        titles = {catalog.BY_ID[t].label for t in catalog.HELD_OUT}
        for module in catalog.HELD_OUT_MODULES:
            tree = _tree(module)
            for node in [tree] + [n for n in ast.walk(tree) if isinstance(
                    n, (ast.ClassDef, ast.FunctionDef))]:
                doc = ast.get_docstring(node)
                if doc is None:
                    continue
                first = doc.split('\n')[0].rstrip('.')
                self.assertIn(first, titles, (module, doc))
                rest = doc.split('\n', 1)[1:] or ['']
                self.assertIn(rest[0].strip(),
                              ('', 'SPDX-License-Identifier: '
                                   'GPL-2.0-or-later'), module)


def shortest(p):
    doors, goal, key = p.data['doors'], p.data['goal'], p.data['key']
    seen = {p.start: 0}
    queue = deque([p.start])
    while queue:
        (x, y), held = state = queue.popleft()
        if (x, y) == goal and held:
            return seen[state]
        for dx, dy in ministeps.STEPS:
            to = (x + dx, y + dy)
            if frozenset(((x, y), to)) not in doors:
                continue
            if to == goal and not held:
                continue
            nxt = (to, held or to == key)
            if nxt not in seen:
                seen[nxt] = seen[state] + 1
                queue.append(nxt)
    return None


class KeyAndDoor(unittest.TestCase):

    def test_deals(self):
        for rung in range(1, 16):
            for seed in range(5):
                p = keydoor.deal(rung, random.Random(seed))
                self.assertEqual(p.par, rung + 1)
                self.assertEqual(shortest(p), rung + 1)
                self.assertEqual(keydoor.far(p, p.start), rung + 1)
                self.assertNotEqual(p.start[0], p.data['key'])
                self.assertNotEqual(p.data['key'], p.data['goal'])
                self.assertEqual(p.data['side'], 7)
                self.assertEqual(p.ports, 4)

    def test_door(self):
        for seed in range(60):
            p = keydoor.deal(2, random.Random(seed))
            goal = p.data['goal']
            for square in p.data['to_goal']:
                for port, (dx, dy) in enumerate(ministeps.STEPS):
                    if (square[0] + dx, square[1] + dy) == goal and \
                            frozenset((square, goal)) in p.data['doors']:
                        self.assertEqual(
                            keydoor.move(p, (square, False), port),
                            (square, False))
                        self.assertEqual(
                            keydoor.move(p, (square, True), port),
                            (goal, True))

    def test_random_presses(self):
        rng, wins = random.Random(1), 0
        for _d in range(3000):
            walk = keydoor.Walk(keydoor.deal(1, rng))
            while walk.result is None:
                walk.press(rng.randrange(4))
            wins += walk.result[0]
        self.assertAlmostEqual(wins / 3000, 0.17, delta=0.03)


class OddStripe(unittest.TestCase):

    def test_deals(self):
        for rung in (1, 2, 5, 9):
            for seed in range(40):
                p = oddstripe.deal(rung, random.Random(seed))
                items = p.data['items']
                n = len(items)
                self.assertEqual(n, twins.size('odd', rung))
                self.assertEqual(len(p.choices), n)
                odd = n - 1 - p.answer
                self.assertEqual(sum(i == items[odd] for i in items), 1)
                self.assertEqual(len(set(items)), 2)


class ArrowWalk(unittest.TestCase):

    def test_deals(self):
        for rung in (1, 2, 5, 12):
            for seed in range(40):
                p = carried.deal('arrows', rung, random.Random(seed), look=0)
                row, col = divmod(p.data['start'], 2)
                for arrow in p.data['arrows']:
                    dr, dc = TURNS[arrow]
                    row, col = (row + dr) % 2, (col + dc) % 2
                self.assertEqual(p.answer, framed.port_order(
                    0, carried.CARDS).index(row * 2 + col))

    def test_boundary(self):
        name = 'arrow_walk'
        for rung in (1, 3):
            self.assertEqual(frame_drive(name, lambda t: t.puzzle.answer,
                                         rung), [1.0], rung)
        self.assertEqual(frame_drive(name, lambda t: (t.puzzle.answer + 1)
                                     % 4), [-1.0])
        self.assertEqual(frame_drive(name, lambda t: t.puzzle.answer,
                                     early=0), [1.0])
        self.assertEqual(frame_drive(name, lambda t: None), [-1.0])


class RoundAgain(unittest.TestCase):

    def test_deals(self):
        for rung in (1, 2, 3, 6):
            rng, mine = random.Random(3), random.Random(103)
            ledger, log = ownpress.Ledger(), []
            for _t in range(300):
                p = roundagain.deal(rung, rng, ledger=ledger)
                press = mine.choice((0, 1, 2, 3, None))
                ledger.record(press)
                log.append((p, press))
            checked = 0
            for t, (p, _press) in enumerate(log):
                if t >= rung and log[t - rung][1] is not None:
                    self.assertEqual(p.answer, AFTER[log[t - rung][1]])
                    checked += 1
            self.assertGreater(checked, 150)


class InTheWindow(unittest.TestCase):

    def test_window(self):
        self.assertAlmostEqual(inwindow.window(1), 0.5)
        shares = [inwindow.window(r) for r in range(1, 12)]
        self.assertEqual(shares, sorted(shares, reverse=True))
        self.assertEqual(len(set(shares)), len(shares))

    def play(self, rung, policy, seed=0):
        run = inwindow.Run(inwindow.deal(rung, random.Random(seed)))
        while run.result is None:
            port = policy(run)
            if port in inwindow.EVENTS:
                inwindow.act(run, port)
            run.step(1 / 60.0, port)
        return run.result[0]

    def test_play(self):
        for rung in (1, 5, 12):
            for seed in range(10):
                self.assertTrue(self.play(rung, inwindow.pilot, seed))
                self.assertFalse(self.play(rung,
                                           lambda run: inwindow.WAIT, seed))

    def test_blind(self):
        for rung, lo, hi in ((1, 0.4, 0.6), (8, 0.07, 0.22)):
            wins = sum(self.play(rung, lambda run: inwindow.PRESS, s)
                       for s in range(400))
            self.assertTrue(lo < wins / 400.0 < hi, (rung, wins))


def _right(task):
    if hasattr(task, 'walk') and task.walk is not None:
        if hasattr(task.walk, 'good'):
            return task.walk.good()[0]
        return ministeps.good(task.puzzle, task.walk.state)[0]
    run = getattr(task, 'run', None)
    if run is not None and hasattr(run, 'dealt'):
        return inwindow.pilot(run)
    if run is not None and not run.open:
        return job_now(task) if hasattr(run, 'job') else None
    return task.puzzle.answer


def _wrong(task):
    if hasattr(task, 'walk') and task.walk is not None:
        ok = (task.walk.good() if hasattr(task.walk, 'good')
              else ministeps.good(task.puzzle, task.walk.state))
        return next(p for p in range(task.puzzle.ports) if p not in ok)
    run = getattr(task, 'run', None)
    if run is not None and hasattr(run, 'dealt'):
        return (inwindow.WAIT if inwindow.inside(run.dealt, run.at)
                else inwindow.PRESS)
    if run is not None and not run.open:
        return job_now(task) if hasattr(run, 'job') else None
    return (task.puzzle.answer + 1) % len(task.puzzle.choices)


@needs_ui
class TheBoundary(unittest.TestCase):
    def test_right_is_green_and_wrong_is_red(self):
        for task_id in sorted(catalog.HELD_OUT):
            for rung in (1, 8):
                self.assertEqual(drive(task_id, rung, _right, seed=3,
                                       steps=3000), [1.0], (task_id, rung))
                self.assertEqual(drive(task_id, rung, _wrong, seed=3,
                                       steps=3000), [-1.0], (task_id, rung))



class BusyBeads(unittest.TestCase):

    def test_deals(self):
        for rung in range(1, 7):
            for seed in range(10):
                p = busybeads.deal(rung, random.Random(seed))
                (_f, place, _c), = p.data['cues']
                self.assertEqual(p.data['look'], 1)
                self.assertEqual(p.answer, 3 - place)
                self.assertEqual(len(p.data['jobs']), rung)

    def test_boundary(self):
        from cuesupport import drive as cue_drive, job_now
        for hz in (2.0, 10.0):
            self.assertEqual(cue_drive('busy_beads', lambda t: t.puzzle.answer,
                                       2, wait=job_now, frame_hz=hz), [1.0])
            self.assertEqual(cue_drive('busy_beads', lambda t: t.puzzle.answer,
                                       2, frame_hz=hz), [-1.0])



class WaitAndSee(unittest.TestCase):

    def test_deals(self):
        for rung in range(1, 7):
            backs = set()
            for seed in range(40):
                p = waitandsee.deal(rung, random.Random(seed))
                (_f, place, _c), = p.data['cues']
                self.assertEqual(p.data['look'], 1)
                self.assertEqual(p.answer, 3 - place)
                backs.add(p.data['wait'])
            self.assertEqual(min(backs), rung)
            self.assertEqual(max(backs), 3 * rung)

    def test_boundary(self):
        from cuesupport import drive as cue_drive
        for hz in (2.0, 10.0):
            self.assertEqual(cue_drive('wait_and_see',
                                       lambda t: t.puzzle.answer, 2,
                                       frame_hz=hz), [1.0])
            self.assertEqual(cue_drive('wait_and_see',
                                       lambda t: t.puzzle.answer, 2,
                                       wait=lambda t: 0, frame_hz=hz), [-1.0])



class RollCall(unittest.TestCase):

    def test_deals(self):
        for rung in range(1, 6):
            for seed in range(20):
                p = rollcall.deal(rung, random.Random(seed))
                lit = {c: place for _f, place, c in p.data['cues']}
                self.assertEqual(p.data['look'], 1)
                self.assertEqual(len(lit), min(rung, 3) + 1)
                self.assertEqual(p.answer, 3 - lit[p.data['asked']])

    def test_boundary(self):
        from cuesupport import drive as cue_drive
        for hz in (2.0, 10.0):
            self.assertEqual(cue_drive('roll_call', lambda t: t.puzzle.answer,
                                       2, frame_hz=hz), [1.0])
            self.assertEqual(cue_drive('roll_call', lambda t: t.puzzle.answer,
                                       2, wait=lambda t: 0, frame_hz=hz),
                             [-1.0])



class FirstCome(unittest.TestCase):

    def test_deals(self):
        for rung in range(1, 6):
            for seed in range(20):
                p = firstcome.deal(rung, random.Random(seed))
                self.assertEqual(p.data['look'], 1)
                self.assertEqual(p.answer, 3 - p.data['cues'][0][1])

    def test_boundary(self):
        from cuesupport import drive as cue_drive
        for hz in (2.0, 10.0):
            self.assertEqual(cue_drive('first_come', lambda t: t.puzzle.answer,
                                       2, frame_hz=hz), [1.0])
            self.assertEqual(cue_drive('first_come', lambda t: t.puzzle.answer,
                                       2, wait=lambda t: 0, frame_hz=hz),
                             [-1.0])



class StandingOrder(unittest.TestCase):

    def test_deals(self):
        from neural_workshop import keptrule
        across = {0: 2, 1: 3, 2: 0, 3: 1}
        for rung in (1, 2, 4):
            rng, ledger, rule = random.Random(rung), keptrule.Ledger(), None
            for i in range(8 * rung):
                p = standingorder.deal(rung, rng, ledger=ledger)
                self.assertEqual(p.data['sign'] is not None, i % rung == 0)
                rule = p.data['sign'] or rule
                place = p.data['cues'][0][1]
                want = place if rule == 'same' else across[place]
                self.assertEqual(p.answer, 3 - want)

    def test_boundary(self):
        from cuesupport import drive as cue_drive
        for hz in (2.0, 10.0):
            self.assertEqual(cue_drive('standing_order',
                                       lambda t: t.puzzle.answer, 2,
                                       frame_hz=hz, trials=2), [1.0, 1.0])
            self.assertEqual(cue_drive('standing_order',
                                       lambda t: t.puzzle.answer, 2,
                                       wait=lambda t: 0, frame_hz=hz),
                             [-1.0])



class LeverAndLatch(unittest.TestCase):

    def test_deals(self):
        from neural_workshop import twostage
        ways = {0: (-1, 0), 1: (1, 0), 2: (0, 1), 3: (0, -1)}
        for rung in range(1, 10):
            for seed in range(4):
                p = leverlatch.deal(rung, random.Random(seed))
                self.assertEqual(p.par, rung + 1)
                self.assertEqual(twostage.far(p, p.start), rung + 1)
        p = leverlatch.deal(3, random.Random(1))
        for port, (dx, dy) in ways.items():
            (x, y), _s = p.start
            to = twostage.move(p, p.start, port)[0]
            self.assertIn(to, ((x, y), (x + dx, y + dy)))

    def test_random_presses(self):
        rng, wins = random.Random(1), 0
        for _d in range(2000):
            walk = leverlatch.twostage.Walk(leverlatch.deal(1, rng))
            while walk.result is None:
                walk.press(rng.randrange(4))
            wins += walk.result[0]
        self.assertGreater(wins / 2000, 0.08)


if __name__ == '__main__':
    unittest.main()
