#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Desk Jockey: each rule, exceptions, precedence, memos, waiting forms,
the shift, the deal, the boundary

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import collections
import random
import unittest

from spatialsupport import drive, queued
from uisupport import needs_ui

from neural_workshop import deskjockey as M

GOOD = M.Form('A. Abbrin', M.KINDS.index('Equipment order'), 0, 10, 300,
              True, False, M.Card('A. Abbrin', 20), (100, 200))


def desk(rules, forms, order=None, memos=(), rung=22):
    rules = tuple(rules)
    buttons = [M.APPROVE, M.SEND_BACK, M.HOLD, M.FORWARD] + \
        [M.REJECT + r.n for r in rules]
    return M.Puzzle(M.grade(rung), rules,
                    tuple(order or [r.n for r in rules]), tuple(memos),
                    tuple(forms), tuple(buttons), (), 0, 0, '')


def rule(n, test, value=None, then=None, unless=None, save=None):
    return M.Rule(n, test, value, M.REJECT + n if then is None else then,
                  unless, save)


class TheRules(unittest.TestCase):

    def each(self, test, value, bad, then=None):
        r = rule(1, test, value, then)
        p = desk([r], [GOOD, bad])
        self.assertEqual(M.ruling(p, 0), M.APPROVE, test)
        self.assertEqual(M.ruling(p, 1), r.then, test)

    def test_each_rule_catches_what_it_says(self):
        self.each('unsigned', None, GOOD._replace(signed=False), M.SEND_BACK)
        self.each('no_card', None, GOOD._replace(card=None), M.SEND_BACK)
        self.each('no_receipt', None, GOOD._replace(receipts=None),
                  M.SEND_BACK)
        self.each('name', None,
                  GOOD._replace(card=M.Card('B. Abbrin', 20)))
        self.each('expired', None,
                  GOOD._replace(card=M.Card('A. Abbrin', 9)))
        self.each('sum', None, GOOD._replace(receipts=(100, 190)))
        self.each('over', 350, GOOD._replace(amount=360, receipts=(360,)))
        self.each('kind', 3, GOOD._replace(kind=3))
        self.each('dept', 2, GOOD._replace(dept=2), M.FORWARD)

    def test_a_card_good_until_the_form_s_day_has_not_expired(self):
        p = desk([rule(1, 'expired')],
                 [GOOD._replace(card=M.Card('A. Abbrin', 10))])
        self.assertEqual(M.ruling(p, 0), M.APPROVE)

    def test_a_missing_card_is_not_a_wrong_name(self):
        p = desk([rule(1, 'name'), rule(2, 'expired')],
                 [GOOD._replace(card=None)])
        self.assertEqual(M.ruling(p, 0), M.APPROVE)

    def test_unless_and_but_not_if(self):
        over = GOOD._replace(amount=600, receipts=(600,))
        r = rule(1, 'over', 500, unless=('counter', None))
        p = desk([r], [over, over._replace(counter=True)])
        self.assertEqual(M.ruling(p, 0), M.REJECT + 1)
        self.assertEqual(M.ruling(p, 1), M.APPROVE)
        r = r._replace(save=('dept', 2))
        p = desk([r], [over._replace(counter=True),
                       over._replace(counter=True, dept=2)])
        self.assertEqual(M.ruling(p, 0), M.APPROVE)
        self.assertEqual(M.ruling(p, 1), M.REJECT + 1)

    def test_the_first_rule_in_precedence_decides(self):
        bad = GOOD._replace(signed=False, amount=900, receipts=(900,))
        rules = [rule(1, 'unsigned', then=M.SEND_BACK), rule(2, 'over', 500)]
        self.assertEqual(M.ruling(desk(rules, [bad]), 0), M.SEND_BACK)
        self.assertEqual(M.ruling(desk(rules, [bad], order=(2, 1)), 0),
                         M.REJECT + 2)
        self.assertEqual(M.breaks(desk(rules, [bad]), 0), [1, 2])

    def test_a_memo_changes_a_rule_from_its_day_on(self):
        rules = [rule(1, 'over', 500), rule(2, 'kind', 3)]
        early = GOOD._replace(day=5, amount=400, receipts=(400,))
        late = early._replace(day=12)
        p = desk(rules, [early, late], memos=[M.Memo(10, 1, 300)])
        self.assertEqual(M.ruling(p, 0), M.APPROVE)
        self.assertEqual(M.ruling(p, 1), M.REJECT + 1)
        permit = GOOD._replace(kind=3)
        p = desk(rules, [permit._replace(day=5), permit._replace(day=12)],
                 memos=[M.Memo(10, 2, None)])
        self.assertEqual(M.ruling(p, 0), M.REJECT + 2)
        self.assertEqual(M.ruling(p, 1), M.APPROVE)

    def test_the_book_says_what_it_does(self):
        p = desk([rule(1, 'over', 500, unless=('counter', None),
                       save=('dept', 2)),
                  rule(2, 'dept', 1, M.FORWARD + 1)], [GOOD], order=(2, 1))
        self.assertEqual(M.say(p, p.rules[0]),
                         '1. Reject any amount over 500, unless it is '
                         'countersigned -- but not if it comes from Supply.')
        self.assertEqual(M.say(p, p.rules[1]),
                         '2. Forward to Purchasing every form from Works.')
        self.assertIn('2, 1', M.say_order(p))
        self.assertIn('lowest number', M.say_order(desk(p.rules, [GOOD])))
        self.assertIn('withdrawn', M.say_memo(M.Memo(9, 2, None)))


class WaitingForms(unittest.TestCase):

    def setUp(self):
        self.claim = GOOD._replace(kind=M.CLAIM)
        self.leave = GOOD._replace(kind=M.LEAVE)
        self.rules = [rule(1, 'needs'), rule(2, 'unsigned', then=M.SEND_BACK)]

    def test_a_claim_is_held_while_its_leave_request_is_in_the_tray(self):
        p = desk(self.rules, [self.claim, self.leave])
        self.assertEqual(M.solve(p), [M.HOLD, M.APPROVE, M.APPROVE])

    def test_it_goes_through_once_that_was_approved(self):
        p = desk(self.rules, [self.leave, self.claim])
        self.assertEqual(M.solve(p), [M.APPROVE, M.APPROVE])

    def test_it_is_rejected_if_that_was_not_or_there_is_none(self):
        p = desk(self.rules, [self.claim,
                              self.leave._replace(signed=False)])
        self.assertEqual(M.solve(p), [M.HOLD, M.SEND_BACK, M.REJECT + 1])
        p = desk(self.rules, [self.claim])
        self.assertEqual(M.solve(p), [M.REJECT + 1])
        other = self.leave._replace(name='B. Belcote')
        p = desk(self.rules, [self.claim, other])
        self.assertEqual(M.solve(p)[0], M.REJECT + 1)


class TheShift(unittest.TestCase):

    def test_one_wrong_ends_a_shift_that_allows_none(self):
        p = M.deal(5, seed=1)
        shift = M.Shift(p)
        want = shift.right()
        wrong = next(b for b in p.buttons if b != want)
        self.assertEqual(shift.act(wrong), False)
        self.assertEqual(shift.result[0], False)

    def test_a_slip_is_carried_where_the_rung_allows_one(self):
        p = M.deal(14, seed=1)
        self.assertEqual(p.level.slips, 1)
        shift = M.Shift(p)
        shift.act(next(b for b in p.buttons if b != shift.right()))
        self.assertIsNone(shift.result)
        while shift.result is None:
            shift.act(shift.right())
        self.assertEqual(shift.result[0], True)
        shift = M.Shift(p)
        for _k in range(2):
            shift.act(next(b for b in p.buttons if b != shift.right()))
        self.assertEqual(shift.result[0], False)

    def test_a_port_not_on_offer_does_nothing(self):
        p = M.deal(1, seed=1)
        shift = M.Shift(p)
        self.assertIsNone(shift.act(M.HOLD))
        self.assertIsNone(shift.act(M.REJECT + 7))
        self.assertEqual(len(shift.tray), len(p.forms))

    def test_a_memo_arrives_with_the_first_form_it_could_touch(self):
        for seed in range(10):
            p = M.deal(17, seed=seed)
            shift = M.Shift(p)
            while shift.result is None:
                top = p.forms[shift.top]
                for memo in p.memos:
                    self.assertEqual(memo in shift.memos(),
                                     memo.day <= max(
                                         [top.day] + [p.forms[a].day for
                                                      a, _b, _c in shift.done]))
                    if top.day >= memo.day:
                        self.assertIn(memo, shift.memos())
                shift.act(shift.right())


class TheDeal(unittest.TestCase):

    RUNGS = (1, 4, 7, 10, 13, 16, 19, 22, 30)

    def test_the_ladder(self):
        self.assertEqual((M.grade(1).rules, M.grade(1).forms), (1, 3))
        self.assertFalse(M.grade(4).checks)
        self.assertTrue(M.grade(7).checks)
        self.assertTrue(M.grade(10).unless and M.grade(10).forwards)
        self.assertTrue(M.grade(13).order)
        self.assertEqual(M.grade(16).memos, 1)
        self.assertTrue(M.grade(19).needs)
        self.assertTrue(M.grade(22).deep)
        self.assertEqual(M.grade(40).rules, M.MOST_RULES)
        self.assertGreater(M.grade(40).forms, M.grade(22).forms)

    def test_a_shift_shows_what_its_rung_is_about(self):
        for rung in self.RUNGS:
            for seed in range(12):
                p = M.deal(rung, seed=seed)
                lv = p.level
                ports = M.solve(p)
                self.assertEqual(len(p.rules), lv.rules)
                self.assertEqual(len(p.forms), lv.forms)
                self.assertEqual(len(p.memos), lv.memos)
                self.assertIn(M.APPROVE, ports)
                self.assertGreater(len(set(ports)), 1)
                for port in ports:
                    self.assertIn(port, p.buttons)
                if lv.needs:
                    self.assertIn(M.HOLD, ports)
                if lv.memos:
                    plain = p._replace(memos=())
                    self.assertTrue(any(M.ruling(p, i) != M.ruling(plain, i)
                                        for i in range(lv.forms)))
                if lv.order:
                    plain = p._replace(order=tuple(sorted(p.order)))
                    self.assertTrue(any(M.ruling(p, i) != M.ruling(plain, i)
                                        for i in range(lv.forms)))
                if lv.unless:
                    plain = p._replace(rules=tuple(
                        r._replace(unless=None, save=None) for r in p.rules))
                    self.assertTrue(any(M.ruling(p, i) != M.ruling(plain, i)
                                        for i in range(lv.forms)))

    def test_forms_come_in_order_of_day_and_people_are_who_they_are(self):
        for rung in (7, 19, 30):
            for seed in range(10):
                p = M.deal(rung, seed=seed)
                days = [f.day for f in p.forms]
                self.assertEqual(days, sorted(days))
                self.assertTrue(all(1 <= d <= 28 for d in days))
                counts = collections.Counter(f.name for f in p.forms)
                self.assertLessEqual(max(counts.values()), 2)
                for f in p.forms:
                    if f.card is not None:
                        self.assertGreaterEqual(f.card.expires, 1)

    def test_a_seed_deals_the_same_shift(self):
        self.assertEqual(M.deal(20, seed=3), M.deal(20, seed=3))
        self.assertNotEqual(M.deal(20, seed=3).forms,
                            M.deal(20, seed=4).forms)

    def test_no_one_answer_and_no_guessing_clears_a_tray(self):
        rng = random.Random(4)
        for rung in (1, 4, 10, 19):
            for fixed in (M.APPROVE, M.SEND_BACK):
                wins = 0
                for seed in range(60):
                    shift = M.Shift(M.deal(rung, seed=seed))
                    while shift.result is None:
                        shift.act(fixed)
                    wins += shift.result[0]
                self.assertEqual(wins, 0, (rung, fixed))
            wins = 0
            for seed in range(120):
                p = M.deal(rung, seed=seed)
                shift = M.Shift(p)
                while shift.result is None:
                    shift.act(rng.choice(p.buttons))
                wins += shift.result[0]
            self.assertLessEqual(wins, 28 if rung == 1 else 2, rung)


def pilot(task):
    return [task.shift.right()]


@needs_ui
class TheBoundary(unittest.TestCase):

    def test_the_book_followed_clears_the_tray_through_the_ports(self):
        for rung in (1, 8, 14, 20, 26):
            self.assertEqual(drive('desk_jockey', rung,
                                   queued(pilot, lambda t: t), seed=2),
                             [1.0], rung)

    def test_wrong_fails_and_idle_is_never_paid(self):
        def wrong(task):
            want = task.shift.right()
            return next(b for b in task.puzzle.buttons if b != want)
        for rung in (1, 8, 14):
            self.assertEqual(drive('desk_jockey', rung, wrong, seed=2),
                             [-1.0], rung)
        self.assertEqual(drive('desk_jockey', 5, lambda task: None, seed=2,
                               steps=200), [])

    def test_every_rung_draws_a_button_for_every_port_on_offer(self):
        from neural_workshop.ui.deskjockey import DeskJockey
        from uisupport import close_overlays, reset_window
        close_overlays()
        task = DeskJockey()
        try:
            for rung in (1, 8, 17, 30):
                task.rng = random.Random(3)
                task.start_rung = rung
                task.total_trials = 1
                task.adaptive = False
                task.start_run()
                task.on_draw()
                self.assertEqual(len(task.hits), len(task.puzzle.buttons))
                for _k in range(3):
                    if task.phase != 'playing':
                        break
                    task.choose(task.shift.right())
                    task.on_draw()
                self.assertTrue(all(done[1] == done[2]
                                    for done in task.shift.done))
        finally:
            task.close()
            close_overlays()
            reset_window()

    def test_it_has_its_own_place_in_the_hub(self):
        from neural_workshop.ui import taskhub
        self.assertIn(('order', 'Accuracy and order'),
                      list(taskhub.CATEGORIES))
        self.assertIn('desk_jockey',
                      [t for t, _n in taskhub.tasks_for('order')])


if __name__ == '__main__':
    unittest.main()
