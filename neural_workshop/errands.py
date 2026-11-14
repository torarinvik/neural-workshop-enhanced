# -*- coding: utf-8 -*-
"""Errands: work that runs across three apps on one small computer.

A strip along the top switches between **Mail**, **Shop** and
**Expenses**. The work is in the mail: someone asks for a thing to be
bought and the cost claimed back. Doing it means reading the request,
finding the thing in the shop (the Browser task's shop, all of it),
buying it, carrying the order number and the total from the shop's
confirmation page into an expense claim, picking the claim's category
and filing it -- then pressing Done. Nothing carries anything between
apps but the player.

The round passes if, when Done is pressed, exactly the things asked for
were bought, each as an order of its own, every order has one claim
with its number, its total and the right category, nothing else was
claimed, and the clicks came in at or under par.

The ladder:

* rung 1: no shopping -- a receipt in the mail to claim;
* rung 2: a second mail that is not work;
* from rung 3 a thing to buy, named; from rung 6 described (*the
  cheapest kettle in stock*), with the shop's own ladder behind it;
* from rung 9 the category is not in the request: a policy mail says
  which kind of thing goes where;
* from rung 12 a later mail changes the request -- the latest word is
  the one that counts;
* from rung 15 two errands from two people; three from rung 21;

and more mail that is not work throughout.

Par counts clicks, as Browser's does: a short reference path -- read
what is needed, buy, file, Done -- plus a share, shrinking with the
rung, of what a thorough worker spends reading every mail and opening
every product.

Units are those of a 1000 by 640 screen, y down. No pyglet here.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from . import browser
from .i18n import _

STRIP = 40
SCREEN_W, SCREEN_H = browser.SCREEN_W, browser.SCREEN_H
TABS = {'mail': (10, 5, 130, 30), 'shop': (150, 5, 130, 30),
        'expenses': (290, 5, 150, 30)}
DONE = (880, 5, 110, 30)
CATEGORIES = ('Office', 'Kitchen', 'Travel', 'Outdoor', 'Electronics')
CATEGORY_OF = {'Kettles': 'Kitchen', 'Blenders': 'Kitchen',
               'Lamps': 'Office', 'Chairs': 'Office', 'Desks': 'Office',
               'Headphones': 'Electronics', 'Backpacks': 'Travel',
               'Tents': 'Outdoor'}
PEOPLE = ('Dana', 'Kofi', 'Mira', 'Tomas', 'Ines', 'Arjun', 'Lena', 'Yusuf')
REASONS = ('the new starter', 'the meeting room', 'the team trip',
           'the front desk', 'the workshop', 'my desk')


class Grade(NamedTuple):
    rung: int
    errands: int
    shopping: bool
    shop_rung: int
    noise: int
    policy: bool
    amend: bool
    slack: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    return Grade(
        rung=r,
        errands=1 if r < 15 else (2 if r < 21 else 3),
        shopping=r >= 3,
        shop_rung=1 if r < 6 else min(30, r - 3),
        noise=0 if r < 2 else min(6, 1 + (r - 2) // 4),
        policy=r >= 9,
        amend=r >= 12,
        slack=(1.0 - 0.7 * (r - 1) / 19.0) if r <= 20
        else max(0.05, 0.3 - 0.025 * (r - 20)),
    )


class Mail(NamedTuple):
    sender: str
    subject: str
    body: str
    time: str
    needed: bool


class Claim(NamedTuple):
    order: str
    amount: str
    category: str


class Deal(NamedTuple):
    seed: int
    level: Grade
    shop: Optional[browser.Deal]
    mails: Tuple[Mail, ...]
    #: Without shopping: the claims the receipts ask for.
    receipts: Tuple[Claim, ...]
    #: With it: the category each target is to be claimed under.
    categories: Tuple[str, ...]
    numbers: Tuple[int, ...]


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    numbers = tuple(draw.sample(range(10000, 99999), 8))
    people = draw.sample(PEOPLE, len(PEOPLE))
    mails: List[Tuple[int, Mail]] = []       # (minutes, mail)
    clock = [9 * 60 + draw.randint(0, 40)]

    def stamp() -> Tuple[int, str]:
        clock[0] += draw.randint(3, 40)
        return clock[0], '%02d:%02d' % divmod(clock[0], 60)

    shop = None
    receipts: List[Claim] = []
    categories: List[str] = []
    if not level.shopping:
        person = people[0]
        category = draw.choice(CATEGORIES)
        amount = draw.randint(12, 260)
        number = numbers[0]
        at, time = stamp()
        mails.append((at, Mail(
            person, _('Receipt to claim'),
            _('Hi -- I paid for this with the team card. Could you file '
              'an expense claim for it under %s?\n\nOrder #%d\nTotal '
              'charged: $%d\n\nThanks, %s') % (category, number, amount,
                                              person),
            time, True)))
        receipts.append(Claim(str(number), str(amount), category))
    else:
        shop_level = browser.grade(level.shop_rung)._replace(
            buys=level.errands,
            departments=max(browser.grade(level.shop_rung).departments,
                            level.errands + (1 if level.amend else 0)))
        shop = browser.deal(level.shop_rung, seed=draw.randrange(1 << 30),
                            level=shop_level)
        if level.policy:
            at, time = stamp()
            lines = ['%s: %s' % (d, CATEGORY_OF[d])
                     for d in shop.departments]
            mails.append((at, Mail(
                'Accounts', _('Which category? (please keep)'),
                _('When you claim for something you bought, use the '
                  'category for its kind:\n\n%s\n\nAnything else: '
                  'Office.\n\n-- Accounts') % '\n'.join(lines),
                time, True)))
        for k, ((criterion, department), target) in enumerate(
                zip(shop.goals, shop.targets)):
            person = people[k]
            category = CATEGORY_OF[shop.departments[department]]
            categories.append(category)
            want = browser.phrase(shop, criterion, department, target)
            claim_words = ('' if level.policy else
                           _(' File the expense under %s.') % category)
            if level.amend and k == 0:
                others = [d for d in range(len(shop.departments))
                          if d not in [g[1] for g in shop.goals]]
                decoy_department = draw.choice(others) if others else \
                    department
                decoy = browser.phrase(
                    shop, 'cheapest', decoy_department,
                    shop.in_department(decoy_department)[0].pid) \
                    if decoy_department != department else \
                    _('two of them')
                at, time = stamp()
                mails.append((at, Mail(
                    person, _('Order for %s') % draw.choice(REASONS),
                    _('Hi -- could you order %s from %s.example? Buy it '
                      'as an order of its own and claim it back.%s\n\n'
                      'Thanks, %s') % (decoy, shop.shop, claim_words,
                                       person), time, True)))
                at, time = stamp()
                mails.append((at, Mail(
                    person, _('Change of plan'),
                    _('Sorry -- scrap my last request. Instead please '
                      'order %s, on its own as before, and claim it '
                      'back.%s\n\n%s') % (want, claim_words, person),
                    time, True)))
            else:
                at, time = stamp()
                mails.append((at, Mail(
                    person, _('Order for %s') % draw.choice(REASONS),
                    _('Hi -- could you order %s from %s.example? Buy it '
                      'as an order of its own and claim it back.%s\n\n'
                      'Thanks, %s') % (want, shop.shop, claim_words,
                                       person), time, True)))
    for _n in range(level.noise):
        at, time = stamp()
        mails.append((at, _noise(draw, shop, people)._replace(time=time)))
    # Newest at the top, as an inbox has it.
    mails.sort(key=lambda pair: -pair[0])
    return Deal(seed, level, shop, tuple(m for _a, m in mails),
                tuple(receipts), tuple(categories), numbers)


def _noise(draw: random.Random, shop, people) -> Mail:
    kind = draw.randrange(4)
    name = draw.choice(people)
    if kind == 0:
        return Mail('Newsletter', _('This week: 20% off everything'),
                    _('Big savings all week in every department. Offer '
                      'ends Sunday. You are receiving this because you '
                      'signed up.'), '', False)
    if kind == 1:
        return Mail(name, _('Lunch?'),
                    _('Anyone up for lunch at one? The usual place.\n\n%s')
                    % name, '', False)
    if kind == 2:
        number = draw.randint(10000, 99999)
        return Mail('Accounts', _('Claim #%d paid') % number,
                    _('Your expense claim #%d has been paid. Nothing more '
                      'to do.\n\n-- Accounts') % number, '', False)
    return Mail(name, _('Done: last week\'s order'),
                _('Thanks for ordering the chairs last week -- all '
                  'arrived, nothing more needed.\n\n%s') % name, '', False)


# --- the computer --------------------------------------------------------

class Order(NamedTuple):
    number: int
    items: Tuple[int, ...]
    total: int


class ErrandShop(browser.Session):
    """The shop as an app: checking out places an order, shows its
    confirmation, and empties the cart, rather than ending anything."""

    def __init__(self, dealt: browser.Deal, numbers: Sequence[int]) -> None:
        super().__init__(dealt, offset=STRIP)
        self.numbers = list(numbers)
        self.orders: List[Order] = []

    def elements(self) -> List[browser.Element]:
        if self.page[0] != 'placed':
            return super().elements()
        order = self.orders[self.page[1]]
        E = browser.Element
        out = [E(40, 20, 920, 44, _('Thank you -- order placed'), 'title'),
               E(40, 90, 600, 34, _('Order number: %d') % order.number,
                 'text'),
               E(40, 130, 600, 34, _('Total charged: $%d') % order.total,
                 'text')]
        y = 180
        for pid in order.items:
            out.append(E(40, y, 600, 34, self.deal.products[pid].name,
                         'muted'))
            y += 40
        out.append(E(40, y + 20, 300, 36, _('Continue shopping'), 'link',
                     ('home',)))
        return out

    def do(self, action: Tuple) -> None:
        if action[0] == 'checkout':
            if not self.cart:
                return
            total = sum(self.deal.products[p].price
                        + self.deal.products[p].shipping for p in self.cart)
            number = self.numbers[len(self.orders) % len(self.numbers)]
            self.orders.append(Order(number, tuple(self.cart), total))
            self.cart = []
            self.go(('placed', len(self.orders) - 1))
            return
        super().do(action)


#: Where things are in the Mail and Expenses apps.
INBOX_TOP, ROW_H = STRIP + 60, 44
FIELDS = {'order': (200, STRIP + 70, 260, 40),
          'amount': (200, STRIP + 130, 260, 40)}
KEYPAD = (520, STRIP + 70)
KEY = 64
SUBMIT = (40, STRIP + 470, 220, 50)


def keypad_rects() -> List[Tuple[str, Tuple[float, float, float, float]]]:
    labels = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'del', '0']
    out = []
    for i, label in enumerate(labels):
        row, col = divmod(i, 3)
        out.append((label, (KEYPAD[0] + col * (KEY + 8),
                            KEYPAD[1] + row * (KEY + 8), KEY, KEY)))
    return out


def category_rects() -> List[Tuple[str, Tuple[float, float, float, float]]]:
    return [(name, (200, STRIP + 200 + i * 48, 260, 40))
            for i, name in enumerate(CATEGORIES)]


class Office:
    """The whole computer: which app is up, and what each holds."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.app = 'mail'
        self.reading: Optional[int] = None
        self.read: set = set()
        self.shop = ErrandShop(dealt.shop, dealt.numbers) \
            if dealt.shop else None
        self.fields = {'order': '', 'amount': ''}
        self.focus = 'order'
        self.category: Optional[str] = None
        self.claims: List[Claim] = []
        self.pointer = [SCREEN_W / 2, SCREEN_H / 2]
        self.clicks = 0
        self.done = False
        self.notice = ''

    def apps(self) -> Tuple[str, ...]:
        return ('mail', 'shop', 'expenses') if self.shop else \
            ('mail', 'expenses')

    # --- what can be clicked ---------------------------------------------

    def targets(self) -> List[Tuple[Tuple, Tuple[float, float, float,
                                                 float]]]:
        """Every (action, rect) a click could hit, in screen units."""
        out = [(('app', app), TABS[app]) for app in self.apps()]
        out.append((('done',), DONE))
        if self.app == 'mail':
            if self.reading is None:
                for i, _mail in enumerate(self.deal.mails):
                    out.append((('open', i),
                                (20, INBOX_TOP + i * ROW_H, 960, ROW_H - 4)))
            else:
                out.append((('inbox',), (20, STRIP + 14, 200, 30)))
        elif self.app == 'expenses':
            for name, rect in FIELDS.items():
                out.append((('field', name), rect))
            for label, rect in keypad_rects():
                out.append((('key', label), rect))
            for name, rect in category_rects():
                out.append((('category', name), rect))
            out.append((('submit',), SUBMIT))
        return out

    def target_at(self, x: float, y: float) -> Optional[Tuple]:
        for action, (rx, ry, rw, rh) in self.targets():
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                return action
        if self.app == 'shop' and y >= STRIP:
            found = self.shop.target_at(x, y)
            return ('shop', found) if found else None
        return None

    # --- hands -----------------------------------------------------------

    def move(self, dx: float, dy: float) -> None:
        self.pointer[0] = min(SCREEN_W, max(0, self.pointer[0] + dx))
        self.pointer[1] = min(SCREEN_H, max(0, self.pointer[1] + dy))

    def wheel(self, way: int) -> None:
        if self.app == 'shop':
            self.shop.wheel(way)

    def click(self, x: Optional[float] = None,
              y: Optional[float] = None) -> Optional[Tuple]:
        if self.done:
            return None
        if x is not None:
            self.pointer = [x, y]
        self.clicks += 1
        action = self.target_at(*self.pointer)
        if action is not None:
            self.do(action)
        return action

    def do(self, action: Tuple) -> None:
        kind = action[0]
        self.notice = ''
        if kind == 'app':
            self.app = action[1]
        elif kind == 'done':
            self.done = True
        elif kind == 'open':
            self.reading = action[1]
            self.read.add(action[1])
        elif kind == 'inbox':
            self.reading = None
        elif kind == 'shop':
            self.shop.do(action[1])
        elif kind == 'field':
            self.focus = action[1]
        elif kind == 'key':
            text = self.fields[self.focus]
            if action[1] == 'del':
                self.fields[self.focus] = text[:-1]
            elif len(text) < 7:
                self.fields[self.focus] = text + action[1]
        elif kind == 'category':
            self.category = action[1]
        elif kind == 'submit':
            if self.fields['order'] and self.fields['amount'] \
                    and self.category:
                self.claims.append(Claim(self.fields['order'],
                                         self.fields['amount'],
                                         self.category))
                self.fields = {'order': '', 'amount': ''}
                self.focus = 'order'
                self.category = None
                self.notice = _('Claim filed.')
            else:
                self.notice = _('Fill in every part of the claim first.')

    # --- judging ---------------------------------------------------------

    def expected(self) -> Optional[List[Claim]]:
        """The claims that should exist given what was bought, or None
        when the buying itself was wrong."""
        dealt = self.deal
        if not dealt.shop:
            return list(dealt.receipts)
        orders = self.shop.orders
        targets = list(dealt.shop.targets)
        if len(orders) != len(targets) or \
                any(len(o.items) != 1 for o in orders) or \
                sorted(o.items[0] for o in orders) != sorted(targets):
            return None
        return [Claim(str(o.number), str(o.total),
                      dealt.categories[targets.index(o.items[0])])
                for o in orders]

    def mistakes(self) -> List[str]:
        wanted = self.expected()
        if wanted is None:
            return [_('the wrong things were bought')]
        out = []
        have = list(self.claims)
        for claim in wanted:
            if claim in have:
                have.remove(claim)
            else:
                out.append(_('no right claim for order %s') % claim.order)
        if have:
            out.append(_('%d claim(s) that should not be there')
                       % len(have))
        return out


# --- the reference path, and par -----------------------------------------

def plan(dealt: Deal, thorough: bool = False) -> List[Tuple]:
    """A path of clicks that does the round: read, buy, file, Done."""
    out: List[Tuple] = []
    reading = [i for i, m in enumerate(dealt.mails)
               if m.needed or thorough]
    for k, i in enumerate(reading):
        out.append(('open', i))
        if k + 1 < len(reading):
            out.append(('inbox',))

    def claim(order: str, amount: str, category: str) -> None:
        out.append(('app', 'expenses'))
        out.append(('field', 'order'))
        out.extend(('key', d) for d in order)
        out.append(('field', 'amount'))
        out.extend(('key', d) for d in amount)
        out.append(('category', category))
        out.append(('submit',))

    if not dealt.shop:
        for receipt in dealt.receipts:
            claim(*receipt)
    else:
        shop = dealt.shop
        totals = []
        for k, ((criterion, department), target) in enumerate(
                zip(shop.goals, shop.targets)):
            one = shop._replace(goals=((criterion, department),),
                                targets=(target,))
            _count, path = browser.fewest(one)
            out.append(('app', 'shop'))
            if k:
                out.append(('shop', ('home',)))
            if thorough:
                for product in shop.in_department(department):
                    out.append(('shop', ('item', product.pid)))
                    out.append(('shop', ('back',)))
            out += [('shop', step) for step in path]
            product = shop.products[target]
            totals.append(product.price + product.shipping)
            claim(str(dealt.numbers[k]), str(totals[-1]),
                  dealt.categories[k])
    out.append(('done',))
    return out


def fewest(dealt: Deal) -> int:
    return len(plan(dealt))


def thorough(dealt: Deal) -> int:
    count = len(plan(dealt, thorough=True))
    if dealt.shop:
        for _criterion, department in dealt.shop.goals:
            count += browser.pages_of(dealt.shop, department) - 1
    return count


def par(dealt: Deal) -> int:
    best = fewest(dealt)
    # Room for slips as well as for looking around: three in ten clicks
    # at rung one, shrinking with the rest.
    slips = 0.3 * best
    return best + int(round(dealt.level.slack
                            * (thorough(dealt) - best + slips)))


def wrap(text: str, width: int = 86) -> List[str]:
    lines: List[str] = []
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split(' '):
            if line and len(line) + 1 + len(word) > width:
                lines.append(line)
                line = word
            else:
                line = (line + ' ' + word) if line else word
        lines.append(line)
    return lines
