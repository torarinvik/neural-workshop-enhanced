#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Errands: the mail, the computer, par, the boundary, the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import unittest

from uisupport import close_overlays, needs_ui, reset_window

from neural_workshop import errands as E


def run_plan(dealt, steps=None):
    office = E.Office(dealt)
    for action in (E.plan(dealt) if steps is None else steps):
        office.do(action)
    return office


class TheLadder(unittest.TestCase):

    def test_the_parts_come_in_on_their_rungs(self):
        self.assertFalse(E.grade(2).shopping)
        self.assertTrue(E.grade(3).shopping)
        self.assertFalse(E.grade(8).policy)
        self.assertTrue(E.grade(9).policy)
        self.assertFalse(E.grade(11).amend)
        self.assertTrue(E.grade(12).amend)
        self.assertEqual([E.grade(r).errands for r in (14, 15, 20, 21)],
                         [1, 2, 2, 3])
        self.assertGreater(E.grade(1).slack, E.grade(30).slack)


class TheOffice(unittest.TestCase):

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(E.deal(13, seed=4), E.deal(13, seed=4))

    def test_the_plan_does_every_rung_cleanly(self):
        for rung in range(1, 27):
            for seed in range(3):
                dealt = E.deal(rung, seed=seed)
                office = run_plan(dealt)
                self.assertTrue(office.done, (rung, seed))
                self.assertEqual(office.mistakes(), [], (rung, seed))

    def test_the_thorough_plan_does_too_and_costs_more(self):
        for rung in (2, 12, 21):
            dealt = E.deal(rung, seed=1)
            office = run_plan(dealt, E.plan(dealt, thorough=True))
            self.assertEqual(office.mistakes(), [])
            self.assertLess(E.fewest(dealt), E.par(dealt))
            self.assertLessEqual(E.par(dealt) - E.fewest(dealt),
                                 E.thorough(dealt) * 2)

    def test_par_tightens_up_the_ladder(self):
        def room(rung):
            dealt = E.deal(rung, seed=0)
            return E.par(dealt) / float(E.fewest(dealt))
        self.assertGreater(room(3), room(28))

    def test_doing_nothing_is_wrong(self):
        for rung in (1, 5, 13):
            office = E.Office(E.deal(rung, seed=2))
            office.do(('done',))
            self.assertTrue(office.mistakes(), rung)

    def test_a_wrong_category_is_caught(self):
        dealt = E.deal(10, seed=3)
        steps = E.plan(dealt)
        at = next(i for i, s in enumerate(steps) if s[0] == 'category')
        other = next(c for c in E.CATEGORIES if c != steps[at][1])
        steps[at] = ('category', other)
        self.assertTrue(run_plan(dealt, steps).mistakes())

    def test_a_claim_filed_twice_is_caught(self):
        dealt = E.deal(4, seed=1)
        steps = E.plan(dealt)
        first = next(i for i, s in enumerate(steps) if s == ('app',
                                                             'expenses'))
        claim = steps[first:-1]
        self.assertTrue(run_plan(dealt, steps[:-1] + claim
                                 + [('done',)]).mistakes())

    def test_the_change_of_plan_comes_after_the_request(self):
        """From rung 12 a later mail from the same sender replaces what an
        earlier one asked, so it sits above it in the inbox, and buying
        what the earlier mail named is wrong."""
        for seed in range(6):
            dealt = E.deal(12, seed=seed)
            mails = list(dealt.mails)
            change = next(i for i, m in enumerate(mails)
                          if m.subject == 'Change of plan')
            first = next(i for i, m in enumerate(mails)
                         if m.sender == mails[change].sender
                         and m.subject.startswith('Order for'))
            self.assertLess(change, first)
            self.assertNotEqual(mails[change].body, mails[first].body)

    def test_mails_wrap_to_the_pane(self):
        for line in E.wrap('word ' * 60):
            self.assertLessEqual(len(line), 86)


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, policy, seed=0):
        from nwenv import catalog
        env = catalog.env_class('errands')(seed=seed, rung=rung, trials=1,
                                           adaptive=False)
        queue, scalars = [], []
        try:
            for _step in range(3000):
                task = env.task
                port = None
                if task.phase == 'playing':
                    if not queue:
                        queue.extend(policy(task))
                    port = queue.pop(0)
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_the_reference_passes_a_receipt(self):
        from neural_workshop.ui.errands import reference_ports
        self.assertEqual(self.drive(1, reference_ports), [1.0])

    def test_and_a_changed_request_with_shopping(self):
        from neural_workshop.ui.errands import reference_ports
        self.assertEqual(self.drive(13, reference_ports, seed=2), [1.0])

    def test_and_two_errands(self):
        from neural_workshop.ui.errands import reference_ports
        self.assertEqual(self.drive(16, reference_ports, seed=1), [1.0])

    def test_pressing_done_at_once_fails(self):
        from neural_workshop import browser
        from neural_workshop.ui.errands import CLICK

        def hasty(task):
            office = task.office
            tx, ty = browser.click_point(E.DONE)
            return browser.moves_to(office.pointer[0], office.pointer[1],
                                    tx, ty) + [CLICK]
        self.assertEqual(self.drive(5, hasty), [-1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        import random
        from neural_workshop.ui.errands import Errands
        close_overlays()
        self.task = Errands()
        self.task.rng = random.Random(3)
        self.task.start_rung = 4
        self.task.total_trials = 1
        self.task.adaptive = False
        self.task.start_run()

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def test_every_app_draws(self):
        task = self.task
        for action in (('open', 0), ('app', 'shop'), ('app', 'expenses')):
            task.office.do(action)
            task._redraw()
            task.on_draw()

    def test_digit_keys_type_into_the_claim(self):
        from pyglet.window import key
        task = self.task
        task.office.do(('app', 'expenses'))
        clicks = task.office.clicks
        task._key(key._4, 0)
        task._key(key._2, 0)
        self.assertEqual(task.office.fields['order'], '42')
        self.assertEqual(task.office.clicks, clicks + 2)
        task._key(key.BACKSPACE, 0)
        self.assertEqual(task.office.fields['order'], '4')

    def test_the_plan_by_mouse_passes(self):
        from neural_workshop import browser
        task = self.task
        office = task.office
        shop = office.shop
        for action in E.plan(office.deal):
            if action[0] == 'shop' and action[1][0] not in ('home', 'cart',
                                                             'back'):
                element = next(e for e in shop.elements()
                               if e.action == action[1])
                while not shop.visible(element):
                    task.scroll(1 if shop.view_top + element.y - shop.scroll
                                > E.SCREEN_H / 2 else -1)
                rect = shop.on_screen(element)
            elif action[0] == 'shop':
                rect = dict((a[0], r) for r, a in shop.chrome())[
                    action[1][0]]
            else:
                rect = dict(office.targets())[action]
            task.click(*browser.click_point(rect))
        self.assertEqual(task.phase, 'judged')
        self.assertTrue(task.verdict_shown[0], task.verdict_shown)


if __name__ == '__main__':
    unittest.main()
