#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Browser: the shops, the pages, par, the pointer, the screen.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
import unittest

from uisupport import TASKS, close_overlays, display, needs_ui, \
    reset_window, state, taskoptions

from neural_workshop import browser as B


class TheLadder(unittest.TestCase):

    def test_every_rung_asks_at_least_what_the_last_did(self):
        last = B.grade(1)
        for rung in range(2, 40):
            level = B.grade(rung)
            for field in ('departments', 'products', 'buys', 'sorting',
                          'stock', 'shipping', 'paged', 'stale'):
                self.assertGreaterEqual(getattr(level, field),
                                        getattr(last, field), field)
            self.assertLessEqual(level.slack, last.slack)
            last = level

    def test_the_parts_come_in_on_their_rungs(self):
        self.assertEqual(B.grade(2).criteria, ('named',))
        self.assertEqual(B.grade(3).criteria, ('cheapest',))
        self.assertFalse(B.grade(5).stock)
        self.assertTrue(B.grade(6).stock)
        self.assertTrue(B.grade(9).shipping)
        self.assertTrue(B.grade(12).paged)
        self.assertEqual((B.grade(14).buys, B.grade(15).buys), (1, 2))
        self.assertTrue(B.grade(18).stale)
        self.assertEqual(B.grade(21).buys, 3)


class TheShops(unittest.TestCase):

    def test_a_deal_is_fixed_by_its_seed(self):
        self.assertEqual(B.deal(16, seed=5), B.deal(16, seed=5))

    def test_the_target_is_the_one_answer(self):
        for rung in (3, 7, 10, 13, 19, 24):
            for seed in range(15):
                dealt = B.deal(rung, seed=seed)
                for (criterion, department), target in zip(dealt.goals,
                                                           dealt.targets):
                    product = dealt.products[target]
                    self.assertEqual(product.department, department)
                    if criterion == 'named':
                        continue
                    ranked = B.matches(criterion,
                                       dealt.in_department(department))
                    self.assertEqual(ranked[0].pid, target)
                    self.assertNotEqual(B._score(criterion, ranked[0]),
                                        B._score(criterion, ranked[1])
                                        if len(ranked) > 1 else None)

    def test_two_things_come_from_two_departments(self):
        dealt = B.deal(17, seed=2)
        departments = [d for _c, d in dealt.goals]
        self.assertEqual(len(set(departments)), 2)

    def test_stock_and_shipping_are_only_on_the_product_page(self):
        dealt = B.deal(11, seed=1)
        listed = ' '.join(e.words for e in B.layout(
            dealt, ('list', 0, 0, 'featured'), ()))
        self.assertNotIn('stock', listed)
        self.assertNotIn('Shipping', listed)
        page = ' '.join(e.words for e in B.layout(dealt, ('item', 0), ()))
        self.assertIn('stock', page)
        self.assertIn('Shipping', page)

    def test_sorting_and_pages(self):
        dealt = B.deal(22, seed=3)
        by_price = B.sorted_list(dealt, 0, 'price')
        self.assertEqual([p.listed for p in by_price],
                         sorted(p.listed for p in by_price))
        self.assertGreater(B.pages_of(dealt, 0), 1)
        first = [e.action for e in B.layout(dealt, ('list', 0, 0, 'price'),
                                            ()) if e.action and
                 e.action[0] == 'item']
        self.assertEqual(len(first), B.PER_PAGE)

    def test_stale_list_prices_are_not_what_is_charged(self):
        stale = sum(p.listed != p.price for s in range(10)
                    for p in B.deal(19, seed=s).products)
        self.assertGreater(stale, 10)
        fresh = sum(p.listed != p.price for p in B.deal(17, seed=0).products)
        self.assertEqual(fresh, 0)


class TheBrowser(unittest.TestCase):

    def test_back_home_and_the_cart(self):
        dealt = B.deal(8, seed=4)
        session = B.Session(dealt)
        session.do(('list', 0, 0, 'featured'))
        session.do(('item', 1))
        session.do(('back',))
        self.assertEqual(session.page, ('list', 0, 0, 'featured'))
        session.do(('home',))
        self.assertEqual(session.page, ('home',))
        session.do(('cart',))
        self.assertEqual(session.page, ('cart',))

    def test_out_of_stock_will_not_go_in_the_cart(self):
        dealt = B.deal(8, seed=4)
        out = next(p for p in dealt.products if not p.stock)
        session = B.Session(dealt)
        session.do(('add', out.pid))
        self.assertEqual(session.cart, [])
        self.assertIn('out of stock', session.notice)

    def test_a_click_on_nothing_still_counts(self):
        session = B.Session(B.deal(1, seed=0))
        session.click(995, 630)
        self.assertEqual(session.clicks, 1)
        self.assertEqual(session.page, ('home',))

    def test_long_lists_scroll(self):
        dealt = B.deal(11, seed=2)
        session = B.Session(dealt)
        session.do(('list', 0, 0, 'featured'))
        self.assertGreater(session.max_scroll(), 0)
        last = session.elements()[-1]
        self.assertFalse(session.visible(last))
        for _turn in range(10):
            session.wheel(1)
        self.assertTrue(session.visible(last))

    def test_the_pointer_reaches_any_click_point(self):
        for x, y in ((0, 0), (1000, 640), (335, 210), (500, 320)):
            for tx, ty in ((15, 40), (985, 600), (500, 320)):
                session = B.Session(B.deal(1, seed=0))
                session.pointer = [x, y]
                for port in B.moves_to(x, y, tx, ty):
                    dx, dy = B.DIRECTIONS[port // 3]
                    session.move(dx * B.STEPS[port % 3],
                                 dy * B.STEPS[port % 3])
                self.assertEqual(session.pointer, [tx, ty])


class Par(unittest.TestCase):

    def test_the_fewest_path_buys_exactly_the_targets(self):
        for rung in (1, 6, 13, 16, 22):
            for seed in range(5):
                dealt = B.deal(rung, seed=seed)
                session = B.Session(dealt)
                count, path = B.fewest(dealt)
                for action in path:
                    session.do(action)
                self.assertTrue(session.checked_out)
                self.assertTrue(session.right())
                self.assertEqual(len(path), count)

    def test_par_lies_between_the_fewest_and_the_thorough(self):
        for rung in (1, 10, 20, 30):
            dealt = B.deal(rung, seed=1)
            best, _path = B.fewest(dealt)
            self.assertLessEqual(best, B.par(dealt))
            self.assertLessEqual(B.par(dealt), B.thorough(dealt))
        dealt = B.deal(1, seed=1)
        self.assertEqual(B.par(dealt), B.thorough(dealt))


@needs_ui
class TheBoundary(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def drive(self, rung, policy, seed=0):
        from nwenv import catalog
        env = catalog.env_class('browser')(seed=seed, rung=rung, trials=1,
                                           adaptive=False)
        scalars, plan = [], None
        try:
            for _step in range(3000):
                task = env.task
                port = None
                if task.phase == 'playing':
                    if plan is None:
                        plan = policy(task)
                    port = plan.pop(0) if plan else None
                _obs, events, done = env.step(port)
                scalars += [e['scalar'] for e in events
                            if e.get('type') == 'outcome']
                if done or scalars:
                    break
        finally:
            env.close()
        return scalars

    def test_the_shortest_route_through_the_pointer_passes(self):
        from neural_workshop.ui.browser import reference_ports
        self.assertEqual(self.drive(4, reference_ports), [1.0])

    def test_and_with_two_things_to_buy_over_paged_lists(self):
        from neural_workshop.ui.browser import reference_ports
        self.assertEqual(self.drive(17, reference_ports), [1.0])

    def test_clicking_about_at_random_fails(self):
        def flail(task):
            rng = random.Random(1)
            return [rng.randrange(15) for _n in range(600)]
        self.assertNotEqual(self.drive(6, flail), [1.0])


@needs_ui
class TheScreen(unittest.TestCase):

    def setUp(self):
        from neural_workshop.ui.browser import Browser
        close_overlays()
        self.task = Browser()
        self.task.rng = random.Random(6)
        self.task.total_trials = 2
        self.now = 50.0
        self.task.clock = lambda: self.now

    def tearDown(self):
        self.task.close()
        close_overlays()
        reset_window()

    def press(self, model_x, model_y):
        from pyglet.window import mouse
        px, py = self.task.to_pixels(model_x, model_y)
        self.task.on_mouse_press(int(round(px)), int(round(py)),
                                 mouse.LEFT, 0)

    def test_a_mouse_click_follows_a_link(self):
        self.task.start_run()
        element = next(e for e in self.task.session.elements()
                       if e.action and e.action[0] == 'list')
        x, y, w, h = self.task.session.on_screen(element)
        self.press(x + w / 2, y + h / 2)
        self.assertEqual(self.task.session.page[0], 'list')
        self.assertEqual(self.task.session.clicks, 1)
        self.task.on_draw()

    def test_the_wheel_and_keys_scroll(self):
        from pyglet.window import key
        self.task.start_rung = 11
        self.task.start_run()
        self.task.session.do(('list', 0, 0, 'featured'))
        self.task.on_mouse_scroll(500, 500, 0, -1)
        self.assertGreater(self.task.session.scroll, 0)
        self.task.on_key_press(key.UP, 0)
        self.assertEqual(self.task.session.scroll, 0)

    def test_the_shortest_route_is_green_and_climbs(self):
        from neural_workshop.ui.browser import reference_ports
        self.task.start_rung = 9
        self.task.start_run()
        for port in reference_ports(self.task):
            self.task.steer(port)
        self.assertTrue(self.task.verdict_shown[0])
        self.assertEqual(self.task.rung, 10)
        self.task.on_draw()

    def test_the_wrong_thing_is_red(self):
        self.task.start_rung = 3
        self.task.start_run()
        session = self.task.session
        wrong = next(p for p in session.deal.products
                     if p.pid not in session.deal.targets and p.stock)
        session.do(('add', wrong.pid))
        session.do(('cart',))
        element = next(e for e in session.elements()
                       if e.action == ('checkout',))
        x, y, w, h = session.on_screen(element)
        self.press(x + w / 2, y + h / 2)
        self.assertEqual(self.task.phase, 'judged')
        self.assertFalse(self.task.verdict_shown[0])

    def test_everything_stays_above_the_verdict_band(self):
        from neural_workshop.ui.verdict import above_the_band
        from neural_workshop.geometry import from_bottom_edge
        self.task.start_rung = 22
        self.task.start_run()
        for size in ((1824, 1368), (1280, 720), (2560, 1080), (1024, 768)):
            state.window.set_size(*size)
            display.ensure_laid_out()
            self.task.relayout()
            floor = above_the_band(from_bottom_edge(58)) - 0.5
            _x, bottom_y = self.task.to_pixels(0, B.SCREEN_H)
            self.assertGreaterEqual(bottom_y, floor, size)
            for line in (self.task.facts, self.task.footnote,
                         self.task.status):
                self.assertLessEqual(line.content_width,
                                     state.window.width - 16, size)

    def test_closing_gives_back_its_handlers(self):
        from neural_workshop.ui.browser import Browser
        self.task.start_run()
        self.task.close()
        self.assertIsNone(Browser.instance)
        self.assertNotIn(self.task, display.open_overlays())


@needs_ui
class OnTheMenu(unittest.TestCase):

    def tearDown(self):
        close_overlays()
        reset_window()

    def test_it_is_listed_under_computer_use(self):
        self.assertIn('browser', [t for t, _l in TASKS['computer']])

    def test_the_hub_can_launch_it(self):
        from neural_workshop.ui.taskhub import launch_task
        from neural_workshop.ui.browser import Browser
        launch_task('browser')
        self.assertIsNotNone(Browser.instance)
        Browser.instance.close()

    def test_the_options_note_names_what_the_rung_adds(self):
        note = taskoptions.browser_note({'BROWSER_RUNG': 19})
        self.assertIn('out of date', note)


if __name__ == '__main__':
    unittest.main()
