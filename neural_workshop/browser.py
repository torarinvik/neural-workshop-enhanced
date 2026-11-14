# -*- coding: utf-8 -*-
"""Browser: a drawn web shop, a shopping list, and a pointer to do it with.

A round deals a small shop -- a home page of departments, lists of
products that can be sorted and run over several pages, a page for each
product, and a cart -- and a goal on a card: *buy the cheapest kettle
that is in stock*. The player works the shop the way anyone works a
website: point, click links, scroll, go back, add to the cart, check out.
The round passes if the cart at checkout holds exactly what the goal
asks for, and it was done in no more clicks than par.

What the ladder asks for:

* rung 1: one department, two products, *buy the Brava K2*;
* from rung 3 *the cheapest*: the prices are in the list, and the list
  can be sorted;
* from rung 6 *in stock*, which only a product's own page says;
* from rung 9 *the lowest total*, price plus shipping, and shipping too
  is only on the product page;
* from rung 12 *rated 4 or more*, and lists run over pages of eight;
* from rung 15 two things to buy, in different departments;
* from rung 18 the prices in lists can be out of date -- the product
  page is what is charged -- so a sorted list is a hint, not an answer;
* from rung 21 three things to buy;

and more departments and products throughout.

Par counts clicks -- a click on nothing counts too -- and scrolling and
moving the pointer are free. It lies between two references on the
identical shop: the fewest clicks that can do it, which knows where
everything is, and a thorough shopper that opens every product in the
departments it needs and comes back. Par is the fewest plus a share of
the thorough shopper's extra clicks: all of them at rung one, under a
third by rung twenty, and almost none by rung thirty -- by then a sorted
list has to be read well enough to open little but the answer.

Nothing here touches pyglet: a page is a list of rectangles with words
and actions, in screen units of a 1000 by 640 window whose y runs down.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import random
from collections import deque
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from .i18n import _

SCREEN_W, SCREEN_H = 1000, 640
#: The page area: everything below the toolbar.
VIEW_TOP = 74
VIEW_H = SCREEN_H - VIEW_TOP
#: Pointer steps, as Desktop's: long, medium, short.
STEPS = (80, 20, 5)
DIRECTIONS = ((0, -1), (0, 1), (-1, 0), (1, 0))
SCROLL = 120
PER_PAGE = 8
ROW_H = 44
LIST_TOP = 110

KINDS = ('Kettles', 'Lamps', 'Chairs', 'Backpacks', 'Headphones', 'Tents',
         'Blenders', 'Desks')
BRANDS = ('Brava', 'Norde', 'Kelto', 'Vimra', 'Ostra', 'Lumio', 'Pexa',
          'Quill', 'Rayo', 'Sorn', 'Tavo', 'Ulma', 'Wendt', 'Zephi')
SHOPS = ('brightmart', 'cornerstore', 'goodshelf', 'homeline', 'shopwise')
SORTS = ('featured', 'price', 'rating')


class Grade(NamedTuple):
    rung: int
    departments: int
    products: int
    #: What the goals ask for, and how many things to buy.
    criteria: Tuple[str, ...]
    buys: int
    sorting: bool
    stock: bool
    shipping: bool
    paged: bool
    stale: bool
    #: The share of the thorough shopper's extra clicks par allows.
    slack: float


def grade(rung: int) -> Grade:
    r = max(1, int(rung))
    if r < 3:
        criteria = ('named',)
    elif r < 6:
        criteria = ('cheapest',)
    elif r < 9:
        criteria = ('cheapest_in_stock',)
    elif r < 12:
        criteria = ('lowest_total',)
    else:
        criteria = ('cheapest_in_stock', 'lowest_total', 'rated',
                    'best_rated')
    return Grade(
        rung=r,
        departments=min(5, 1 + (r - 1) // 4),
        products=min(24, 1 + r),
        criteria=criteria,
        buys=1 if r < 15 else (2 if r < 21 else 3),
        sorting=r >= 3,
        stock=r >= 6,
        shipping=r >= 9,
        paged=r >= 12,
        stale=r >= 18,
        slack=(1.0 - 0.7 * (r - 1) / 19.0) if r <= 20
        else max(0.05, 0.3 - 0.025 * (r - 20)),
    )


class Product(NamedTuple):
    pid: int
    department: int
    name: str
    price: int
    #: The price the lists show, out of date from rung 18.
    listed: int
    rating: float
    stock: bool
    shipping: int


class Deal(NamedTuple):
    seed: int
    level: Grade
    shop: str
    departments: Tuple[str, ...]
    products: Tuple[Product, ...]
    #: The deal on the home page.
    featured: int
    goals: Tuple[Tuple[str, int], ...]
    targets: Tuple[int, ...]

    def in_department(self, department: int) -> List[Product]:
        return [p for p in self.products if p.department == department]


def matches(criterion: str, items: Sequence[Product]) -> List[Product]:
    """The products a criterion picks from *items*, best first, ties
    together at the front."""
    if criterion == 'cheapest':
        key = lambda p: p.price
        pool = list(items)
    elif criterion == 'cheapest_in_stock':
        key = lambda p: p.price
        pool = [p for p in items if p.stock]
    elif criterion == 'lowest_total':
        key = lambda p: p.price + p.shipping
        pool = [p for p in items if p.stock]
    elif criterion == 'rated':
        key = lambda p: p.price
        pool = [p for p in items if p.stock and p.rating >= 4.0]
    elif criterion == 'best_rated':
        key = lambda p: -p.rating
        pool = [p for p in items if p.stock]
    else:
        return []
    return sorted(pool, key=key)


def _score(criterion: str, product: Product) -> float:
    return {'cheapest': product.price,
            'cheapest_in_stock': product.price,
            'lowest_total': product.price + product.shipping,
            'rated': product.price,
            'best_rated': -product.rating}[criterion]


def goal_words(dealt: Deal) -> str:
    parts = []
    for (criterion, department), target in zip(dealt.goals, dealt.targets):
        kind = dealt.departments[department].lower()[:-1]
        if criterion == 'named':
            parts.append(_('the %s') % dealt.products[target].name)
        elif criterion == 'cheapest':
            parts.append(_('the cheapest %s') % kind)
        elif criterion == 'cheapest_in_stock':
            parts.append(_('the cheapest %s in stock') % kind)
        elif criterion == 'lowest_total':
            parts.append(_('the %s in stock with the lowest price plus '
                           'shipping') % kind)
        elif criterion == 'rated':
            parts.append(_('the cheapest %s in stock rated 4 or more')
                         % kind)
        else:
            parts.append(_('the best-rated %s in stock') % kind)
    return _('Buy %s, then check out.') % _(' and ').join(parts)


def deal(rung: int, seed: Optional[int] = None,
         rng: Optional[random.Random] = None) -> Deal:
    if seed is None:
        seed = (rng or random).randrange(1 << 30)
    level = grade(rung)
    draw = random.Random(seed)
    for _attempt in range(500):
        found = _try_deal(level, seed, draw)
        if found is not None:
            return found
    raise RuntimeError('no shop could be dealt for rung %d' % rung)


def _try_deal(level: Grade, seed: int, draw: random.Random
              ) -> Optional[Deal]:
    kinds = draw.sample(KINDS, level.departments)
    products: List[Product] = []
    names = set()
    for department in range(level.departments):
        for _n in range(level.products):
            while True:
                name = '%s %s%d' % (draw.choice(BRANDS),
                                    kinds[department][0],
                                    draw.randint(1, 99))
                if name not in names:
                    names.add(name)
                    break
            price = draw.randint(12, 240)
            listed = price
            if level.stale and draw.random() < 0.3:
                listed = max(5, price + draw.choice((-1, 1))
                             * draw.randint(5, 40))
            products.append(Product(
                pid=len(products), department=department, name=name,
                price=price, listed=listed,
                rating=round(draw.uniform(1.5, 5.0), 1),
                stock=(draw.random() < 0.65) if level.stock else True,
                shipping=draw.choice((0, 5, 9, 15, 25))
                if level.shipping else 0))
    departments = draw.sample(range(level.departments),
                              min(level.buys, level.departments))
    goals, targets = [], []
    for department in departments:
        criterion = draw.choice(level.criteria)
        items = [p for p in products if p.department == department]
        if criterion == 'named':
            target = draw.choice(items)
        else:
            ranked = matches(criterion, items)
            if not ranked:
                return None
            if len(ranked) > 1 and _score(criterion, ranked[0]) == \
                    _score(criterion, ranked[1]):
                return None                     # the answer must be one
            target = ranked[0]
            if level.stale and target.listed == target.price \
                    and draw.random() < 0.5:
                # Often enough, the list's own order is the trap.
                return None
        goals.append((criterion, department))
        targets.append(target.pid)
    featured = draw.randrange(len(products))
    return Deal(seed, level, draw.choice(SHOPS), tuple(kinds),
                tuple(products), featured, tuple(goals), tuple(targets))


# --- pages ---------------------------------------------------------------

class Element(NamedTuple):
    #: Left, top, width, height in page units (top from the page's top).
    x: float
    y: float
    w: float
    h: float
    words: str
    #: 'title', 'text', 'link', 'button', 'muted', 'banner', 'good', 'bad'
    style: str
    #: What clicking it does, or None.
    action: Optional[Tuple] = None


Page = Tuple       # ('home',) ('list', d, n, sort) ('item', pid) ('cart',)


def sorted_list(dealt: Deal, department: int, sort: str) -> List[Product]:
    items = dealt.in_department(department)
    if sort == 'price':
        return sorted(items, key=lambda p: (p.listed, p.pid))
    if sort == 'rating':
        return sorted(items, key=lambda p: (-p.rating, p.pid))
    return items


def pages_of(dealt: Deal, department: int) -> int:
    count = len(dealt.in_department(department))
    return (count + PER_PAGE - 1) // PER_PAGE if dealt.level.paged else 1


def layout(dealt: Deal, page: Page, cart: Sequence[int],
           notice: str = '') -> List[Element]:
    """The page's elements, in page units."""
    kind = page[0]
    out: List[Element] = []
    if kind == 'home':
        out.append(Element(40, 20, 920, 40,
                           _('Welcome to %s') % dealt.shop.capitalize(),
                           'title'))
        out.append(Element(40, 70, 920, 25, _('Shop by department'),
                           'text'))
        for i, name in enumerate(dealt.departments):
            col, row = i % 3, i // 3
            out.append(Element(40 + col * 310, 110 + row * 90, 290, 70,
                               name, 'button', ('list', i, 0, 'featured')))
        deal_item = dealt.products[dealt.featured]
        out.append(Element(40, 330, 920, 60,
                           _("Today's deal: %s, $%d")
                           % (deal_item.name, deal_item.listed), 'banner',
                           ('item', deal_item.pid)))
        return out
    if kind == 'list':
        _k, department, number, sort = page
        out.append(Element(40, 15, 600, 40, dealt.departments[department],
                           'title'))
        y = 62
        if dealt.level.sorting:
            out.append(Element(40, y, 60, 30, _('Sort:'), 'text'))
            for i, (key, words) in enumerate((
                    ('featured', _('Featured')),
                    ('price', _('Price, low to high')),
                    ('rating', _('Rating, high to low')))):
                out.append(Element(110 + i * 230, y, 220, 30, words,
                                   'muted' if key == sort else 'link',
                                   None if key == sort else
                                   ('list', department, 0, key)))
        if dealt.level.stale:
            out.append(Element(620, 20, 360, 30,
                               _('List prices may be out of date'),
                               'muted'))
        items = sorted_list(dealt, department, sort)
        if dealt.level.paged:
            items = items[number * PER_PAGE:(number + 1) * PER_PAGE]
        y = LIST_TOP
        for product in items:
            out.append(Element(40, y, 470, 36, product.name, 'link',
                               ('item', product.pid)))
            out.append(Element(540, y, 160, 36, '$%d' % product.listed,
                               'text'))
            out.append(Element(720, y, 240, 36,
                               _('rated %.1f') % product.rating, 'text'))
            y += ROW_H
        pages = pages_of(dealt, department)
        if pages > 1:
            y += 10
            if number > 0:
                out.append(Element(40, y, 200, 34, _('Previous page'),
                                   'link',
                                   ('list', department, number - 1, sort)))
            out.append(Element(400, y, 200, 34,
                               _('Page %d of %d') % (number + 1, pages),
                               'text'))
            if number + 1 < pages:
                out.append(Element(760, y, 200, 34, _('Next page'), 'link',
                                   ('list', department, number + 1, sort)))
        return out
    if kind == 'item':
        product = dealt.products[page[1]]
        out.append(Element(40, 20, 920, 44, product.name, 'title'))
        out.append(Element(40, 80, 400, 34, _('Price: $%d') % product.price,
                           'text'))
        out.append(Element(40, 120, 400, 34,
                           _('Rated %.1f out of 5') % product.rating, 'text'))
        y = 160
        if dealt.level.stock:
            out.append(Element(40, y, 400, 34,
                               _('In stock') if product.stock
                               else _('Out of stock'),
                               'good' if product.stock else 'bad'))
            y += 40
        if dealt.level.shipping:
            out.append(Element(40, y, 400, 34,
                               _('Shipping: free') if not product.shipping
                               else _('Shipping: $%d') % product.shipping,
                               'text'))
            y += 40
        out.append(Element(40, y + 20, 260, 56, _('Add to cart'), 'button',
                           ('add', product.pid)))
        out.append(Element(340, y + 30, 400, 36,
                           _('More %s') % dealt.departments[
                               product.department].lower(), 'link',
                           ('list', product.department, 0, 'featured')))
        if notice:
            out.append(Element(40, y + 100, 700, 34, notice, 'text'))
        return out
    # The cart.
    out.append(Element(40, 20, 600, 44, _('Your cart'), 'title'))
    y = 80
    if not cart:
        out.append(Element(40, y, 600, 34, _('The cart is empty.'), 'text'))
    for slot, pid in enumerate(cart):
        product = dealt.products[pid]
        out.append(Element(40, y, 480, 36, product.name, 'text'))
        out.append(Element(540, y, 140, 36, '$%d' % product.price, 'text'))
        out.append(Element(720, y, 140, 36, _('Remove'), 'link',
                           ('remove', slot)))
        y += ROW_H
    total = sum(dealt.products[p].price + dealt.products[p].shipping
                for p in cart)
    out.append(Element(40, y + 10, 400, 34,
                       _('Total with shipping: $%d') % total, 'text'))
    out.append(Element(40, y + 60, 260, 56, _('Check out'), 'button',
                       ('checkout',)))
    return out


def page_height(elements: Sequence[Element]) -> float:
    return max((e.y + e.h for e in elements), default=0) + 30


def address(dealt: Deal, page: Page) -> str:
    site = '%s.example' % dealt.shop
    if page[0] == 'home':
        return site + '/'
    if page[0] == 'list':
        _k, department, number, sort = page
        path = '%s/%s' % (site, dealt.departments[department].lower())
        query = []
        if sort != 'featured':
            query.append('sort=' + sort)
        if number:
            query.append('page=%d' % (number + 1))
        return path + ('?' + '&'.join(query) if query else '')
    if page[0] == 'item':
        product = dealt.products[page[1]]
        return '%s/item/%s' % (site, product.name.lower().replace(' ', '-'))
    return site + '/cart'


# --- the browser ---------------------------------------------------------

#: Toolbar buttons, in screen units.
BACK = (10, 38, 70, 30)
HOME = (88, 38, 70, 30)
CART = (880, 38, 110, 30)


class Session:
    """A browser on a deal: the page, the history, the cart, the pointer."""

    def __init__(self, dealt: Deal) -> None:
        self.deal = dealt
        self.page: Page = ('home',)
        self.history: List[Page] = []
        self.cart: List[int] = []
        self.scroll = 0.0
        self.pointer = [SCREEN_W / 2, SCREEN_H / 2]
        self.clicks = 0
        self.notice = ''
        self.checked_out = False

    # --- what is where ---------------------------------------------------

    def elements(self) -> List[Element]:
        return layout(self.deal, self.page, self.cart, self.notice)

    def max_scroll(self) -> float:
        return max(0.0, page_height(self.elements()) - VIEW_H)

    def visible(self, element: Element) -> bool:
        top = VIEW_TOP + element.y - self.scroll
        return top >= VIEW_TOP and top + element.h <= SCREEN_H

    def on_screen(self, element: Element) -> Tuple[float, float, float,
                                                   float]:
        return (element.x, VIEW_TOP + element.y - self.scroll, element.w,
                element.h)

    def chrome(self) -> List[Tuple[Tuple, Tuple]]:
        """Toolbar buttons: (rect, action)."""
        return [(BACK, ('back',)), (HOME, ('home',)), (CART, ('cart',))]

    def target_at(self, x: float, y: float) -> Optional[Tuple]:
        for (bx, by, bw, bh), action in self.chrome():
            if bx <= x <= bx + bw and by <= y <= by + bh:
                return action
        if y < VIEW_TOP:
            return None
        for element in self.elements():
            if element.action is None or not self.visible(element):
                continue
            ex, ey, ew, eh = self.on_screen(element)
            if ex <= x <= ex + ew and ey <= y <= ey + eh:
                return element.action
        return None

    # --- hands -----------------------------------------------------------

    def move(self, dx: float, dy: float) -> None:
        self.pointer[0] = min(SCREEN_W, max(0, self.pointer[0] + dx))
        self.pointer[1] = min(SCREEN_H, max(0, self.pointer[1] + dy))

    def wheel(self, way: int) -> None:
        self.scroll = min(self.max_scroll(),
                          max(0.0, self.scroll + way * SCROLL))

    def click(self, x: Optional[float] = None,
              y: Optional[float] = None) -> Optional[Tuple]:
        if self.checked_out:
            return None
        if x is not None:
            self.pointer = [x, y]
        self.clicks += 1
        action = self.target_at(*self.pointer)
        if action is not None:
            self.do(action)
        return action

    def go(self, page: Page) -> None:
        if page != self.page:
            self.history.append(self.page)
        self.page = page
        self.scroll = 0.0
        self.notice = ''

    def do(self, action: Tuple) -> None:
        kind = action[0]
        if kind == 'back':
            if self.history:
                self.page = self.history.pop()
                self.scroll = 0.0
                self.notice = ''
        elif kind == 'home':
            self.go(('home',))
        elif kind == 'cart':
            self.go(('cart',))
        elif kind in ('list', 'item'):
            self.go(action)
        elif kind == 'add':
            product = self.deal.products[action[1]]
            if product.stock:
                self.cart.append(product.pid)
                self.notice = _('Added to the cart.')
            else:
                self.notice = _('Sorry, this is out of stock.')
        elif kind == 'remove':
            if 0 <= action[1] < len(self.cart):
                self.cart.pop(action[1])
        elif kind == 'checkout':
            if self.cart:
                self.checked_out = True

    def right(self) -> bool:
        return sorted(self.cart) == sorted(self.deal.targets)


# --- par -----------------------------------------------------------------

def links(dealt: Deal, page: Page, cart: Tuple[int, ...]) -> List[Tuple]:
    """Every action one click can take from *page* (Back aside)."""
    out = [('home',), ('cart',)]
    out += [e.action for e in layout(dealt, page, cart) if e.action]
    return out


def fewest(dealt: Deal) -> Tuple[int, List[Tuple]]:
    """The fewest clicks that buy exactly the targets and check out, and
    the actions that do it: a search over pages and carts."""
    wanted = tuple(sorted(dealt.targets))
    start = (('home',), ())
    seen = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        page, cart = node
        for action in links(dealt, page, cart):
            kind = action[0]
            if kind == 'checkout':
                if cart == wanted:
                    path = [action]
                    while seen[node] is not None:
                        node, step = seen[node]
                        path.append(step)
                    path.reverse()
                    return len(path), path
                continue
            if kind == 'add':
                pid = action[1]
                if pid not in wanted or pid in cart:
                    continue
                nxt = (page, tuple(sorted(cart + (pid,))))
            elif kind == 'remove':
                continue
            elif kind == 'home':
                nxt = (('home',), cart)
            elif kind == 'cart':
                nxt = (('cart',), cart)
            else:
                nxt = (action, cart)
            if nxt not in seen:
                seen[nxt] = (node, action)
                queue.append(nxt)
    raise RuntimeError('no way to buy the targets')


def thorough(dealt: Deal) -> int:
    """What the reference spends: the fewest clicks, plus opening every
    product of each department it shops and coming back, plus turning
    every page of its list."""
    best, _path = fewest(dealt)
    extra = 0
    for _criterion, department in dealt.goals:
        extra += 2 * len(dealt.in_department(department))
        extra += pages_of(dealt, department) - 1
    return best + extra


def par(dealt: Deal) -> int:
    best, _path = fewest(dealt)
    return best + int(round(dealt.level.slack * (thorough(dealt) - best)))


# --- driving the pointer -------------------------------------------------

def click_point(rect: Tuple[float, float, float, float]
                ) -> Tuple[float, float]:
    """A point inside *rect* on the pointer's five-unit grid."""
    x, y, w, h = rect
    px = 5 * round((x + w / 2) / 5)
    py = 5 * round((y + h / 2) / 5)
    if not x <= px <= x + w:
        px = 5 * int(x / 5 + 1)
    if not y <= py <= y + h:
        py = 5 * int(y / 5 + 1)
    return px, py


def moves_to(fx: float, fy: float, tx: float, ty: float) -> List[int]:
    """Pointer ports that carry it from (fx, fy) to (tx, ty)."""
    ports = []
    for axis, (here, there) in enumerate(((fx, tx), (fy, ty))):
        gap = int(round(there - here))
        neg, pos = (2, 3) if axis == 0 else (0, 1)
        direction = pos if gap > 0 else neg
        gap = abs(gap)
        for size_index, size in enumerate(STEPS):
            while gap >= size:
                ports.append(direction * 3 + size_index)
                gap -= size
    return ports
